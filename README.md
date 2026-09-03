# KonomiTV 録画再生のシーク・表示品質調査

KonomiTVの録画再生について、シーク後の表示復帰時間、定常再生のFPS、コマ落ち、短いカクつき、長時間stallをコードと実機で調べた記録です。
主対象はMPEG-2 TSのOriginal直接再生ですが、サーバーエンコードHLSとの違いも同じ指標で確認します。
リポジトリ名には調査開始時の`seek-investigation`が残っていますが、素材本来のcadenceを維持し、負荷やシークの後も安定した表示へ戻るまでを対象とします。

各修正が何をして、どれだけ効いたかは[統合検証branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes)にあります。
この文書は、何をどう測り、その数値をどこまで信じてよいか、どの順で提出するかを扱います。

## 何を測ったか

**表示復帰時間**は、シーク先の映像がYADIF canvasに出て、`seeked`の後も消えずに残るまでの時間です。
終点は共通ですが、起点は次の2種類があるため、数値には起点を併記します。

- **`video.currentTime`起点**：製品コードを使う測定で、シーク時刻をvideo要素へ設定した瞬間から測ります。
- **`seek-requested`起点**：計測版playerで、video要素の`seeking` eventを受け、buffer外シークを受理した瞬間から測ります。

異なる起点とinstrumentationで得た値は、個別修正の効果量として直接比較しません。
UIのtouch eventから`video.currentTime`設定までを含む値も、この2種類へ混ぜません。

YADIFの待ち行列を空にして時刻同期をやり直す処理は、**queue全reset**と呼びます。
容量確保や実遅延からの追いつきで古いfieldだけを捨てる処理と、その件数は、**FIFO破棄**と呼びます。

**致命的な表示停止**は、利用者が再シークなどを行わない限り、シーク要求から2秒以内に安定した表示進行へ復帰しない事象です。
合格条件は、正常TSと異常TSのそれぞれについて、試行条件を記録した1時間の自動試験で0件です。
これは再現可能な回帰試験の基準であり、一般的な発生率が0であることを示す統計的な推定ではありません。

正常TSの目標は、1時間連続再生でコマ落ち0件、40ms超の描画間隔0回、理論上の表示FPSの安定維持、シークの表示復帰時間200ms以下です。
番組1本を通して見ても、コマ落ち0件を目標とします。
異常TSは別に評価し、1時間の自動試験で致命的な表示停止0件、利用者操作なしでの継続または復帰、避けられない最小範囲だけのコマ落ち、復帰後の理論FPSと音声同期を必須条件とします。

これらを達成した後も、技術的な改善余地がなくなるまで検証と改善を続けます。

## この数値をどこまで信じてよいか

- 主計測では録画TSをKonomiTVサーバー側のローカルNVMeへコピーし、コピー元とSHA-256が一致することを確認しています。CIFS経由の絶対時間は主結果へ使いません。
- TS内の時刻は、永続GOP indexではなく、小さなHTTP RangeでPTSを探すメモリ内indexから求めます。約43GBのTSでも各地点2 probeで収束し、毎回先頭から走査する構成ではありません。
- 乃木坂工事中fixtureには、映像開始から125.025秒付近に破損video packetが1個あります。このpacketを横切る走行は正常TSの性能値へ混ぜず、異常TSの耐障害試験として別に評価します。
- Galaxyの絶対時間は、古い検証タブが設定と再生資源を残さないよう、対象タブ1枚で取り直しました。以前の絶対値は主結果から外しています。
- 別buildどうしの表示復帰時間は、中央値が数ms違っても効果や退行として扱いません。overflow時刻圧縮だけを載せたbuildと統合検証版は中央値157.2msと160.5msでしたが、他の修正も入った別buildの比較なので、この3.3msの差は判定に使っていません。
- 既存`presented` eventは`video.seeking`解除後のbuffered frameを示し、表示復帰時間とは一致しません。前景再生中の体感レイテンシには使いません。
- `droppedVideoFrames`はpredecodeまたは表示期限超過のdropを数え、最終YADIF canvasの可視コマ落ち数ではありません。Originalで数えた極短IDR recovery sampleのdropと、YADIF出力の表示間隔を分けて評価します。
- Windowsの値は、Ryzen 7 4700Uを電源モード「最適な電力効率」で測った補助条件です。同一モード内のbranch A/Bに使い、通常設定のWindowsやGalaxyとの絶対性能比較には使いません。
- 「乃木坂工事中」は確認区間だけを60 field候補として扱います。MADDER全編のFFmpeg解析で最長だった連続3:2区間から、映像と主音声を再エンコードせず約173秒切り出しました。`autoFilm`回帰では、期待値を`24000/1001`fps（約23.976fps）とする[固定素材](results/madder-24p-clean-fixture.json)を使います。24fpsは略称に限り、判定と誤差計算には使いません。

## 分かったこと

### MPEG-2 TS 直接再生

通常シークの主要な待ちは、PTS probeとRange応答、GOPとAACが揃うまでの読取とH.264変換、MSE投入とdecoder再開です。
「indexがなく毎回先頭から走査するため遅い」という構成ではありません。

支配的だったのは次の3つで、いずれも修正しました。

- probeで測ったbyte→PTS標本を、後続fragmentの時刻で上書きしていました。
- YADIFがqueue容量不足と時刻同期の破綻を区別せず、シーク後に表示がほぼ停止しました。
- MSE resetと古いappend完了が競合すると、新しいinit segmentを失い得ました。

7件の修正をまとめた統合検証版では、Galaxyの`video.currentTime`起点の表示復帰時間が中央値287.1→159.7msとなり、当時の250ms判定では14/40→40/40になりました。
代表指標の前後比較と回帰結果は[統合検証branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes#全体の効果)にあります。

正式候補へ受動的なqueue計測だけを加えた自然発生traceでは、最後のcanvas直接描画後もrVFCが51回進む一方、51回の容量確保で計101 fieldをFIFO破棄しました。
破棄のたびに次のfieldが再び将来へ移り、rAFが表示対象を得られない循環が続きました。[自然発生trace](results/galaxy-yadif-rank4-natural-fatal-timeline.json)に記録しています。

順位4の提出buildを1,000 seekごとに作り直す1時間上限の試験では、3,008回目に致命的な表示停止を1件検出しました。
video decoderは67 frame、音声decodeも61,270 byte進みましたが、canvasの最大描画間隔は1,679ms、YADIFの`late`は2→70、終了時`outputFps`は0でした。
順位4は通常のシーク停止を大幅に減らしますが、1時間0件の合格条件は満たしません。[集計と4 blockの生値](results/galaxy-yadif-rank4-one-hour-block-reset-summary.json)を公開しています。

順位5は、FIFO破棄したfieldが占めていた空の表示時間を詰めます。
順位4と順位5へ同じ受動計測を加え、同じseed、同じ4回目、同じ目的時刻を比較しました。
順位4は2.5秒で復帰せず104 fieldをFIFO破棄しましたが、順位5は4 fieldの破棄で止まり、508.5msから安定描画へ復帰しました。[同一計装の順位5結果](results/galaxy-yadif-rank5-same-instrumentation-success.json)を保存しています。

順位5の連続セッション試験では4,073 seek・停止0でしたが、実行中runnerを編集したため正式結果から除外しました。
blockごとの再生成も行っていないので、順位4との効果比較や順位5の合格根拠には使いません。[除外理由と参考値](results/galaxy-yadif-rank5-one-hour-continuous-excluded-summary.json)を残しています。

blockごとにブラウザーとplayer各層を作り直す別の1時間試験も4,399 seek・停止0でしたが、最初のblock中に同一ホストで診断buildを実行しました。
高負荷を含む参考結果として残し、無負荷の1時間合格根拠には使いません。[条件と全blockのhash](results/galaxy-yadif-rank5-one-hour-high-load-reference.json)を保存しています。

順位5の正式buildを最新KonomiTVへ組み込んだ無負荷の1時間試験では、4,415回のseekすべてが2秒以内に安定復帰し、致命的な表示停止は0件でした。
この結果は順位5の1時間条件を満たしますが、順位4の1時間試験とはKonomiTV revisionが異なるため、停止率の差を順位5だけの効果とは扱いません。[集計と各blockの生値](results/galaxy-yadif-rank5-latest-one-hour-summary.json)を公開しています。

現在のintegrationを固定した無負荷の1時間試験は、4,644回のseekすべてが2秒以内に安定復帰し、致命的な表示停止0件でした。
この試験は正常区間だけを選ぶ反復seekであり、正常TSの1時間連続再生や異常TSの1時間試験を兼ねません。
[集計と各blockの生値](results/galaxy-integration-current-v3-one-hour-summary.json)を公開しています。

同じbuildで既知の破損video packetを1回横切ると、利用者操作なしで表示が復帰し、致命的な表示停止はありませんでした。
復帰途中を除いた末尾5秒のcanvas描画は60.01fpsで、期待する59.94fpsの±1%へ戻り、40ms超の間隔は0回でした。
一方、同じ窓でChromeのdrop counterが2、YADIFの`late`が1増えています。canvasのdraw呼出しはcompositorの表示そのものではないため、可視コマ落ち0、A/V同期、入力欠落から避けられない最小dropは未証明です。[単発の異常区間解析](results/galaxy-integration-current-v3-anomalous-recovery-analysis.json)を保存しています。

同じ破損区間をintegrationのconverterでオフライン変換すると、出力映像の表示時刻に567.233msの間隔が生じました。Galaxyで観測したmedia timeの飛びと一致するため、この飛びはAndroidのdecoderやYADIFだけが作ったものではなく、converterの出力時刻列に既に含まれます。[変換結果と照合値](results/nogizaka-defect-conversion-timeline.json)を保存しています。

`autoFilm`のcadence維持も目標を達成していません。
到達点と、達成根拠にできない理由は統合検証branchのREADMEにあります。

### サーバーエンコードHLS

最新KonomiTVの録画HLS 1080p60を、Galaxy Chrome、LAN直結、全画面で10分測りました。
毎frameの計測を外した主条件では、H.264は理論値どおり35,964 frameを受理しましたが2 frameをdropし、HEVCは35,966 frameを受理してdrop 0でした。
両方ともmedia timeは約600秒進み、音声のdecodeも継続しました。

| 出力 | 受理frame | `droppedVideoFrames` | media time | 判定 |
| --- | ---: | ---: | ---: | --- |
| H.264 1080p60 | 35,964 | 2 | 599.999秒 | コマ落ち0は未達 |
| HEVC 1080p60 | 35,966 | 0 | 600.001秒 | 今回の10分走行は達成 |

HEVCのAPI要求は10bitでしたが、ソフトウェアFFmpegの実出力は`libx265 Main`、`yuv420p`の8bitでした。
10bit HEVCの結果には数えません。

H.264のprofileとbitrateを分けた10分走行では、既定のHigh・9.5Mbpsが開始側2 drop、終了側1 drop、Main・9.5Mbpsが2 dropでした。
High・3.5Mbpsは0 drop、Main・3.5Mbpsは1 dropでした。

profile変更単独の改善は確認できず、低bitrate側は少ない傾向ですが、合計6件の低頻度事象なので効果はまだ確定できません。
3.5Mbpsは原因切り分け用で、画質を評価していないため製品設定の候補ではありません。

rVFC診断版ではH.264が2 drop、HEVCが1 dropでしたが、callback数は`presentedFrames`増分より少なく、callback間隔の空きと映像dropは1対1ではありません。
主判定には、開始・終了時だけcounterを読む低負荷collectorを使っています。
H.264の発生位置を調べる別の10分走行では1 frameをdropしました。
発生時は`readyState=4`で約31.4秒先までbuffer済み、最寄りのHLS segment境界から約1.36秒離れ、前後2秒にHLS errorはありませんでした。
同じfixture・sequence・設定で再生成したsegmentは、サーバーTSとhls.js変換後のfMP4の全440 frameが1501/1502 tickの理想PTS列でした。
元走行のbyte列そのものではありませんが、重複・逆行・1ms未満間隔はなく、表示期限超過側を優先して切り分けます。

詳しい条件と生値は[1080p60長時間比較](results/galaxy-recorded-hls-1080p60-long-comparison.json)、[H.264 profile・bitrate比較](results/galaxy-recorded-hls-h264-profile-bitrate-comparison.json)、[drop区間のtimestamp検査](results/galaxy-recorded-hls-h264-drop-segment-timestamps.json)に保存しています。

他の14画質とHLSシークは、再生設定をwatch pageの初回実行前に投入するよう測定器を直した条件で再測定が必要です。
修正前の測定は、初期既定の1080pと要求画質のencoder sessionが並行したため、現在の絶対値には使いません。

### 長時間再生と反復シーク

**定常再生の判定は600秒で行い、120秒の結果は補助として扱います。**
120秒では検出できない劣化があるためです。
1 rAFにつき1 fieldだけ表示する案は120秒で改善しましたが、600秒では3分後から徐々に悪化しました。
このため定常再生の判定は600秒で行い、120秒の結果は補助として扱います。

生値は[overflow時刻圧縮の600秒走行](results/galaxy-overflow-compression-clean-600s-summary.json)、[presentation policyの600秒A/B](results/galaxy-present-one-field-long-run-ab.json)、[統合検証版の40回シーク](results/galaxy-integration-without-present-seek-visible-40.json)に保存しています。

## 提出の順序をどう決めたか

優先順位は、確認できた効果、正しさへの影響、差分の理解しやすさ、レビュー負荷、将来の保守コストから決めています。
**P0**は効果を実測で確認し、変更範囲が原因に届いているものです。
**P1**は正しさを守る修正ですが、実利用での改善量を立証できていないものです。

提出先は[`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264)、[`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264)、ファイル配信を所有する[`Kludex/starlette`](https://github.com/Kludex/starlette)です。
tsukumijimaフォークは生成済み`dist`を追跡するため、sourceとdistを別コミットにしています。

| | 順位 | branch | 提出先 | source | dist |
| --- | ---: | --- | --- | --- | --- |
| P0 | 1 | [`fix/preserve-seek-probe-sample`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-seek-probe-sample) | otya128 | `a10253e` | — |
| P0 | 2 | [`feat/report-ts-restart-offsets`](https://github.com/libratechw/mpeg2toh264/tree/feat/report-ts-restart-offsets) | otya128 | `787c7ba` | — |
| P0 | 3 | [`perf/reuse-observed-ts-restarts`](https://github.com/libratechw/mpeg2toh264/tree/perf/reuse-observed-ts-restarts) | otya128 | `ac4f879` | — |
| P0 | 4 | [`fix/separate-yadif-queue-recovery`](https://github.com/libratechw/mpeg2toh264/tree/fix/separate-yadif-queue-recovery) | tsukumijima | `26484fd` | `27b327e` |
| P0 | 5 | [`fix/compress-yadif-overflow-schedule`](https://github.com/libratechw/mpeg2toh264/tree/fix/compress-yadif-overflow-schedule) | tsukumijima | `7ef6696` | `ac2a2a9` |
| P0 | 6 | [`fix/preserve-destination-frame-on-seek`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-destination-frame-on-seek) | tsukumijima | `2d072f3` | `f3ba99d` |
| P1 | 7 | [`fix/mse-reset-inflight-append`](https://github.com/libratechw/mpeg2toh264/tree/fix/mse-reset-inflight-append) | otya128 | `f8ab9c7` | — |
| P1 | 8 | [`codex/fix-file-response-disconnect`](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect) | Kludex/starlette | `d70956b` | — |
| P1 | 9 | [`fix/preserve-complete-pictures-before-loss`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-complete-pictures-before-loss) | tsukumijima | `f27442d` | `e36dd0b` |

順位1〜7の目的、修正内容、効果、実装の重さは[統合検証branchのPR候補一覧](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes#pr候補)にあります。

順位8は、client切断後もファイル応答が末尾まで読み続ける問題を止めます。
Windowsの実KonomiTVで3 MiB受信後の切断を200回繰り返すと、修正前は受信時間が76.1→1,083.1msへ悪化し、修正後は26.1→24.8msで推移しました（最初・最後の20回の中央値）。
実Chromeを使う候補単独の1時間試験では、4,738回すべてが2秒以内に安定復帰し、致命的な表示停止は0件でした。
同条件のStarlette修正前を測っていないため、表示復帰時間や停止頻度の改善量は未確定です。[1時間試験の条件と結果](results/windows-starlette-candidate-one-hour-seek.json)を公開しています。

変更はFileResponseのtaskキャンセルとファイルcloseに限られ、レビュー負荷は中、保守対象はASGIの切断・終了処理です。[条件と根拠](REPORT.md#切断後も続く-fileresponse-の処理)を参照してください。

順位8は別の依存ライブラリの修正であり、mpeg2toh264のintegrationには含めていません。

順位9はTS packet欠落時に、完了を確認できない末尾pictureだけでなく、同じ蓄積中GOPの正常な先行pictureまで破棄する範囲を縮めます。
同じKonomiTV revisionとGalaxyで基準版と候補版を各2回測ると、既知の破損をまたぐ映像時刻の間隔は567.233〜600.600msから33.367msへ縮まり、Chromeのdrop counterは17から6へ減りました。
候補版の2走行にはYADIFのdegradedとdiscontinuityがなく、どちらも期待表示FPSへ復帰しました。[同条件A/B](results/galaxy-anomaly-preserve-complete-pictures-ab.json)を公開しています。
実装はGOP分割と既存transcoderの責務境界に限られ、レビュー負荷と保守コストは中です。
候補単独の1時間上限の自動試験では、固定欠損を223回通過して致命的な表示停止は0件でしたが、復帰後の約3秒間に9回のcadence不合格を検出しました。
この候補は順位4・5を含まないため、cadence不合格が順位9の変更に起因するかは未確定です。[集計と全block](results/galaxy-anomaly-rank9-one-hour-summary.json)を公開しています。

既存のinterlaced・open-GOP fixtureを使うSession回帰試験は通過しています。Galaxy A/Bの実在欠損はopen GOP内のframe pictureにあることも確認しました。fMP4の音声sample時刻列は基準版と候補版で一致しましたが、実在するfield picture破損、画素の正常性、ブラウザー上の可聴A/V同期は未確認です。異常TSの1時間条件もcadence不合格により満たさないため、integrationにはまだ含めていません。[packetとpicture構造](results/nogizaka-transport-defect-localization.json)と[映像・音声時刻列](results/nogizaka-defect-preserve-complete-pictures.json)も参照してください。

順位2はcoreの再開位置契約なので、先にレビューを終えてから順位3のplayer利用policyを出します。
順位4はqueue policyの土台で、順位5はその子PRです。
順位1、6、7、9は他と修正箇所が重ならず、いつでも並行して提出できます。
提出先ごとに整理した依存の図は[レビューの順序](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes#レビューの順序)にあります。

tsukumijimaフォーク固有のYADIF変更は、otya128向けの変更へ混ぜません。

### まだ提出しないもの

[`feat/seek-timing-context`](https://github.com/libratechw/mpeg2toh264/tree/feat/seek-timing-context) `58a9920`は計測専用です。
player、worker、transcoder、picture pool、MSEへ同じseek IDのtiming contextを伝播し、probe標本の誤上書きなどを分離できました。
直接の速度改善はなく、10ファイルにわたる横断と公開event契約の保守が必要なため、効果が立証できるまで提出を急ぎません。

[`fix/deliver-completed-fragments-early`](https://github.com/libratechw/mpeg2toh264/tree/fix/deliver-completed-fragments-early) `30ad508`は効果が確認できていません。
transcoderから完成fragmentを逐次通知しますが、初回fragmentと表示復帰のどちらも一貫して短縮しませんでした。
transcoderとworkerの順序、cancel、backpressureのレビューが必要な規模でもあるため、後続throughputの候補としてのみ残します。

## 採らなかった案と理由

- Android Chromiumのcanvasへ`opacity: 0.999`を設定する案は、不透明な対照でも約60fpsを維持したため採用しません。DOM occlusionが原因だという説明も再現できませんでした。
- 完成fragmentを早く渡す案は、GalaxyとローカルSSD Chromeのどちらでも表示復帰時間を一貫して短縮しませんでした。後続fragmentのthroughput候補としてのみ残します。
- AACが揃った完成GOPをさらに1 GOP保留しない案は、初回fragmentまでの入力を最大512KiB減らしました。しかしGalaxyの表示復帰時間は180秒群で162.7→179.2msとなり、`first-byte`からのfragment生成も短縮しなかったため採用しません。
- 毎GOPをnon-IDR recovery pointにする案は、decoderが古いGOPを捨てる時間を約68ms減らしました。しかし次fragmentの生成待ちで相殺され、hardware decoder互換性も未確認なので採用しません。
- seek leadを1.0秒から0.5秒へ固定変更する案は表示復帰時間を短縮しましたが、5地点中2地点で要求時刻を越えたため採用しません。
- PAT/PMTを含むRAPを毎seekで4〜8MiB先読みする案は、追加Rangeの費用を回収できず遅くなりました。再生中の学習やsidecarは、未知のpre-target RAPを取り逃す素材を再現できた場合に再評価します。
- YADIFへ1 frame分の固定reserveを置く案は、短時間のカクつきを隠しましたが、600秒で最大11.15秒の停止を生じました。queue容量を増やす案もfuture leadを増やすため採用しません。
- 通常は1 rAFにつき1 fieldだけ表示する案は120秒では59.791→59.932fpsへ改善しましたが、600秒ではrAF 56.662回/秒、`missed` 541まで徐々に悪化しました。同じintegrationからこの案だけを外すとrAF 59.998回/秒、`missed` 0だったため採用しません。branchは削除し、測定と判断だけを残しています。
- 録画TSの`FileResponse` body chunkを増やす案は、Galaxyで小さな差が出ましたがsizeに対して単調でなく、Windowsの対応付き比較も−2.4〜+1.7msで中立だったため採用しません。

棄却に至った測定の条件と生値は[REPORT.md](REPORT.md)にあります。

## データの所在

| 知りたいこと | 場所 |
| --- | --- |
| 各修正が何をして、どれだけ効いたか | [統合検証branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes) |
| データフロー、仮説の評価、まだ採用していない候補、将来設計 | [REPORT.md](REPORT.md) |
| 実機条件と素材ごとの結果 | [results/device-results.md](results/device-results.md) |
| 機械可読な集計値と生値 | [`results/`](results/) |
| 公開可能な集計・再現スクリプト | [`scripts/`](scripts/)（[切断後のFileResponse処理](scripts/reproduce-file-response-disconnect.py)、[異常TSのpacketとpictureの照合](scripts/inspect-nogizaka-transport-defect.py)、[fMP4時刻列の解析](scripts/fmp4_timeline.py)、[破損区間の変換比較](scripts/measure-nogizaka-defect-conversion.py)を含む） |

録画ファイル、認証情報、実際のLAN内アドレス、ローカルパス、アクセスログは含みません。
番組名は素材の識別用であり、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
