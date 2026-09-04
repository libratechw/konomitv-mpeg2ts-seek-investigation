# KonomiTV 録画再生のシーク・表示品質調査

KonomiTVの録画再生について、シーク完了時間、定常再生のFPS、コマ落ち、短いカクつき、長時間stallをコードと実機で調べた記録です。
主対象はMPEG-2 TSのOriginal直接再生ですが、サーバーエンコードHLSとの違いも同じ指標で確認します。
リポジトリ名には調査開始時の`seek-investigation`が残っていますが、素材本来のFPSを安定して維持し、負荷やシークの後も安定した表示へ戻るまでを対象とします。

各修正が何をして、どれだけ効いたかは[統合検証branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes)にあります。
この文書は、何をどう測り、その数値をどこまで信じてよいか、どの順で提出するかを扱います。

## 測定方法

指標、合格条件、fixtureの扱い、結果を採用する条件は[`METHODOLOGY.md`](METHODOLOGY.md)を正本とします。

このREADMEでは、現在分かっていること、公開branch、提出先、優先順位だけを扱います。各数値のbuild、条件、生値、採用・除外理由は[`REPORT.md`](REPORT.md)と`results/`を参照してください。

現在のintegration候補は`21e6917`です。clean YADIF候補`8b1f66b`を含む最新tipから再構築し、静的検証と自動試験を完了しました。コードと生成物は`84e916b`から変わらず、`21e6917`はREADMEだけを更新しています。現行コードの異常TS 1時間試験では致命的停止は0/229でしたが、FPS安定復帰失敗は229/229で、異常TSの総合条件は不合格でした。正常TSの1時間連続再生と他の実機条件は未測定です。

## 分かったこと

### MPEG-2 TS 直接再生

通常シークの主要な待ちは、PTS probeとRange応答、GOPとAACが揃うまでの読取とH.264変換、MSE投入とdecoder再開です。
「indexがなく毎回先頭から走査するため遅い」という構成ではありません。

支配的だったのは次の3つで、いずれも修正しました。

- probeで測ったbyte→PTS標本を、後続fragmentの時刻で上書きしていました。
- YADIFがqueue容量不足と時刻同期の破綻を区別せず、シーク後に表示がほぼ停止しました。
- MSE resetと古いappend完了が競合すると、新しいinit segmentを失い得ました。

当時の統合検証版`44e06a4`では、Galaxyの`video.currentTime`起点のシーク完了時間が中央値287.1→159.7msとなり、当時の250ms判定では14/40→40/40になりました。
代表指標の条件と回帰結果は[`REPORT.md`](REPORT.md)と`results/`にあります。

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

KonomiTV client `7307e0e`へ基準版`52a3db5`と当時のintegration `44e06a4`をそれぞれ組み込み、同じfixture、runner、seed、目的時刻、各試行のシーク前待ち時間の列で比較しました。
基準版は54回目に致命的な表示停止を起こして終了し、integrationは1時間で4,732回すべてが2秒以内に安定復帰しました。
基準版が停止した54回目と同じ目的時刻とシーク前待ち時間では、integrationは418.7msで安定復帰しました。
この試験は正常区間だけを選ぶ反復seekであり、正常TSの1時間連続再生や異常TSの1時間試験を兼ねません。
[同条件比較と各blockの生値](results/galaxy-formal-current-integration-comparison.json)を公開しています。

同じKonomiTV client、fixture、runner、seed、各試行のシーク前待ち時間の列で既知の破損video packetを反復して横切ると、基準版は2回目に致命的な表示停止を起こし、そこで試験を終了しました。
integrationは20回すべてが2秒以内に安定復帰し、安定復帰時間は中央値911.0ms、最大1,088.1msでした。

復帰後約3秒のcanvas FPSは、基準版で成功した1回が22.16fps、integrationは中央値53.94fpsでした。
integrationは、異常区間通過後のFPS安定復帰に20回すべてで失敗しました。
停止は改善しましたが、FPS安定復帰、可視コマ落ち0、A/V同期、入力欠落から避けられない最小dropは未達または未証明です。[正常区間と異常区間の同条件比較](results/galaxy-formal-current-integration-comparison.json)を保存しています。

現行integrationのコード`84e916b`を同じ既知欠損へ1時間反復した試験では、229回すべてが利用者操作なしに2秒以内で表示進行へ復帰し、致命的停止は0件でした。
一方、復帰直後約3秒のcanvas FPSは中央値53.95fpsで、229回すべてがFPS安定復帰に失敗しました。
試験時間、fixture、build、負荷、後片付けの条件は成立しているため、現行integrationは異常TSの致命的停止条件を今回の1時間走行で満たしましたが、異常TSの総合合格条件は満たしません。[現行integrationの1時間結果と各試行](results/galaxy-formal-anomaly-integration-84e916b-one-hour-summary.json)を公開しています。

補助条件のWindowsでは、同じintegrationと破損区間で1時間試験を開始しましたが、121回目に致命的停止を検出して終了しました。
先行する120回のうちFPS安定復帰失敗は39回でした。
停止時はvideo callbackが3.791秒と5.731秒途切れ、YADIFのqueue全resetは0回でした。
1時間を完走していないため合格判定には使わず、converter、MSE、decoderのどこで進行が止まったかを診断します。[Windows補助条件の結果](results/windows-anomaly-integration-44e06a4-until-fatal.json)を保存しています。

同じbuildの計装付き1時間診断では、219回すべてが2秒以内に復帰し、致命的停止は0件でしたが、FPS安定復帰失敗を85回検出しました。
11回作り直したclient sessionのうち3回は、そのsessionの20試行すべてでvideo callbackが中央値20.00fps、canvasが中央値40.00fpsでした。
この60試行では`presentedFrames`が常に1ずつ進み、映像時刻だけが1 frame分と2 frame分の間隔を交互に進んだため、YADIFより前のvideo presentationで表示対象が減っています。
この診断には同じ窓のrAF履歴がなく、compositorの更新頻度低下とvideo presentation固有の低下はまだ分離できません。追加計装を含むため、正式な発生率やシーク完了時間には使いません。[1時間診断の層別集計](results/windows-anomaly-diagnostic-one-hour-layer-analysis.json)を保存しています。

同じ破損区間をintegrationのconverterでオフライン変換すると、出力映像の表示時刻に567.233msの間隔が生じました。Galaxyで観測したmedia timeの飛びと一致するため、この飛びはAndroidのdecoderやYADIFだけが作ったものではなく、converterの出力時刻列に既に含まれます。[変換結果と照合値](results/nogizaka-defect-conversion-timeline.json)を保存しています。

耐障害性を1種類の欠損だけで判断しないため、「キッズアワー」の別録画から2本の固定fixtureを追加しました。
全2,798万packetの走査では同期エラーとTEIが0件、映像PIDのcontinuity counter不連続が2件でした。
1件目は6 counter値相当を失ったopen GOP内のP frame picture、2件目は5 counter値相当を失ったopen GOP内のB frame pictureです。
各欠損の約16MiB前から64MiBを無変換で固定し、各fixtureに対象の不連続が1件だけ含まれることを確認しました。
順位9の候補版は基準版より、P-picture側で映像sampleを10個、B-picture側で12個多く保持しました。
最大映像時刻間隔は、P-picture側が567.233→300.300ms、B-picture側が567.233→166.833msへ縮まりました。
両fixtureとも音声sample数と時刻列は一致しています。
ブラウザーで失われる表示frame数、不可避な最小drop、画素、可聴A/V同期、実機での復帰は未測定です。[packet位置、picture構造、fixture hash](results/kids-hour-transport-defects.json)、[変換結果](results/kids-hour-defect-conversion-comparison.json)、[packet検査](scripts/inspect-ts-transport-defects.py)と[変換比較](scripts/measure-fixed-anomaly-conversion.py)の再現スクリプトを公開しています。

`autoFilm`のFPS安定維持も目標を達成していません。
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

提出先は[`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264)、[`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264)、ファイル配信を所有する[`Kludex/starlette`](https://github.com/Kludex/starlette)の3つです。
レビュアーが異なるため、提出先ごとに独立した列として扱います。
表の順位番号は候補を指す識別子で、測定結果のファイル名にも同じ番号を使っています。提出先が異なる候補どうしの順位の大小は、提出順を意味しません。
tsukumijimaフォークは生成済み`dist`を追跡するため、sourceとdistを別コミットにしています。

各候補の目的、修正内容、効果、実装の重さと依存関係は[統合検証branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes)にあります。

### otya128/mpeg2toh264 へ出すもの

| | 順位 | branch | source | 状態 |
| --- | ---: | --- | --- | --- |
| P0 | 1 | [`fix/preserve-seek-probe-sample`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-seek-probe-sample) | `a10253e` | [PR #1](https://github.com/otya128/mpeg2toh264/pull/1)を提出済み |
| P0 | 2 | [`feat/report-ts-restart-offsets`](https://github.com/libratechw/mpeg2toh264/tree/feat/report-ts-restart-offsets) | `787c7ba` | 未提出。順位3の前提 |
| P0 | 3 | [`perf/reuse-observed-ts-restarts`](https://github.com/libratechw/mpeg2toh264/tree/perf/reuse-observed-ts-restarts) | `ac4f879` | 未提出。順位2のレビュー後 |
| P1 | 7 | [`fix/mse-reset-inflight-append`](https://github.com/libratechw/mpeg2toh264/tree/fix/mse-reset-inflight-append) | `f8ab9c7` | 未提出。他と修正箇所が重ならない |

順位2はcoreの再開位置契約なので、先にレビューを終えてから順位3のplayer利用policyを出します。

順位2・3・7は、順位1が削除する誤書き込みが残った基点から分岐しています。
順位2と7はその行に触れていないので、順位1の取り込み後にmergeしても削除は維持されます。最終tipで回帰試験を再実行します。
**順位3は、効果を測った基点にその誤書き込みが残っています。** 誤って上書きされた標本を再利用で回避していた可能性があるため、順位1を含む基点でA/Bを取り直すまで、追加probe 40→0という値は順位3単独の効果として使いません。

### tsukumijima/mpeg2toh264 へ出すもの

fork固有のYADIFに対する修正です。otya128向けの変更へ混ぜません。

| | 順位 | branch | source | dist | 状態 |
| --- | ---: | --- | --- | --- | --- |
| P0 | 4と5 | [`fix/compress-yadif-overflow-schedule`](https://github.com/libratechw/mpeg2toh264/tree/fix/compress-yadif-overflow-schedule) | `e7e3ea2` | `8b1f66b` | PR草案レビュー済み。現行integrationの異常TS 1時間試験は停止0/229、FPS安定復帰は未達。候補単独の再測定前 |
| P0 | 6 | [`fix/preserve-destination-frame-on-seek`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-destination-frame-on-seek) | `2d072f3` | `f3ba99d` | 未提出。他と修正箇所が重ならない |
| P1 | 9 | [`fix/preserve-complete-pictures-before-loss`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-complete-pictures-before-loss) | `f27442d` | `e36dd0b` | 保留。異常TSの1時間条件が未達 |

順位4・5は、保存済みtraceで原因が立証された範囲だけを1本のPR候補にしています。
観測した停止は、容量確保で古いfieldを捨てた後も残る表示予定を動かさず、次の入力でも同じ破棄を繰り返す循環でした。
旧順位4の閾値resetはこの循環から一度描画を戻しましたが、停止全体は解消せず、時刻圧縮と独立して必要になる状態も保存済みtraceにはありません。
最終候補は、必要最小限のFIFO破棄と捨てた時間分の表示予定圧縮だけを残し、根拠を示せない閾値resetをsourceと履歴から外しました。output poolが完全なのに利用可能slotがない場合は、queue内slotを暗黙に再利用せずinvariant errorにします。

旧`fix/separate-yadif-queue-recovery`は棄却した閾値resetを含むため削除します。3,007 seekの測定点はcommit `26484fd`と下記の結果fileで追跡し、取り込み可能な公開branchとして残しません。

順位4単独の1時間試験は、3,007 seekで致命的な表示停止を1件検出しました。
この結果は、旧中間点`26484fd`だけでは残る問題を示します。最終候補`e7e3ea2` / `8b1f66b`では旧中間点の履歴を使わず、`konomi/main` `52a3db5`からa＋cだけを構成しています。

### Kludex/starlette へ出すもの

| | 順位 | branch | source | 状態 |
| --- | ---: | --- | --- | --- |
| P1 | 8 | [`codex/fix-file-response-disconnect`](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect) | `d70956b` | 未提出。他の候補と依存しない |

順位8は、client切断後もファイル応答が末尾まで読み続ける問題を止めます。
Windowsの実KonomiTVで3 MiB受信後の切断を200回繰り返すと、修正前は受信時間が76.1→1,083.1msへ悪化し、修正後は26.1→24.8msで推移しました（最初・最後の20回の中央値）。
実Chromeを使う候補単独の1時間試験では、4,738回すべてが2秒以内に安定復帰し、致命的な表示停止は0件でした。
同条件のStarlette修正前を測っていないため、シーク完了時間や停止頻度の改善量は未確定です。[1時間試験の条件と結果](results/windows-starlette-candidate-one-hour-seek.json)を公開しています。

変更はFileResponseのtaskキャンセルとファイルcloseに限られ、レビュー負荷は中、保守対象はASGIの切断・終了処理です。[条件と根拠](REPORT.md#切断後も続く-fileresponse-の処理)を参照してください。

順位8は別の依存ライブラリの修正であり、mpeg2toh264のintegrationには含めていません。

### 順位9を保留している理由

順位9はTS packet欠落時に、完了を確認できない末尾pictureだけでなく、同じ蓄積中GOPの正常な先行pictureまで破棄する範囲を縮めます。
同じKonomiTV revisionとGalaxyで基準版と候補版を各2回測ると、既知の破損をまたぐ映像時刻の間隔は567.233〜600.600msから333.666msへ縮まり、Chromeのdrop counterは17から6へ減りました。
候補版の2走行にはYADIFのdegradedとdiscontinuityがなく、どちらも期待表示FPSへ復帰しました。[同条件A/B](results/galaxy-anomaly-preserve-complete-pictures-ab.json)を公開しています。
実装はGOP分割と既存transcoderの責務境界に限られ、レビュー負荷と保守コストは中です。

保留しているのは、**異常TSの1時間条件が未測定**だからです。
候補単独と、順位1〜7の統合版へ重ねた検証buildの2本を1時間走らせましたが、runnerが指定した乃木坂fixtureではなくMADDERを再生していました。
どちらも順位9の評価には使えません。[無効の理由とfixture IDの照合](results/galaxy-anomaly-rank9-one-hour-fixture-mismatch.json)を公開しています。

以前ここに載せていた通過回数とFPS安定復帰失敗の件数は、この不一致により取り下げました。
fixtureの同一性を走行前に検証し、不一致なら異常終了するrunnerで測り直します。

既存のinterlaced・open-GOP fixtureを使うSession回帰試験は通過しています。Galaxy A/Bの実在欠損はopen GOP内のframe pictureにあることも確認しました。fMP4の音声sample時刻列は、Galaxyで使ったB-picture破損と、キッズアワーのP/B-picture破損のすべてで基準版と候補版が一致しました。実在するfield picture破損、画素の正常性、ブラウザー上の可聴A/V同期は未確認です。統合版へ重ねてもFPS安定復帰失敗が残るため、integrationにはまだ含めていません。[packetとpicture構造](results/nogizaka-transport-defect-localization.json)、[Galaxyで使った映像・音声時刻列](results/nogizaka-defect-preserve-complete-pictures.json)、[キッズアワー2欠損の時刻列](results/kids-hour-defect-conversion-comparison.json)も参照してください。

### まだ提出しないもの

[`feat/seek-timing-context`](https://github.com/libratechw/mpeg2toh264/tree/feat/seek-timing-context) `58a9920`は計測専用です。
player、worker、transcoder、picture pool、MSEへ同じseek IDのtiming contextを伝播し、probe標本の誤上書きなどを分離できました。
直接の速度改善はなく、10ファイルにわたる横断と公開event契約の保守が必要なため、効果が立証できるまで提出を急ぎません。

[`fix/deliver-completed-fragments-early`](https://github.com/libratechw/mpeg2toh264/tree/fix/deliver-completed-fragments-early) `30ad508`は効果が確認できていません。
transcoderから完成fragmentを逐次通知しますが、初回fragmentとシーク完了時間のどちらも一貫して短縮しませんでした。
transcoderとworkerの順序、cancel、backpressureのレビューが必要な規模でもあるため、後続throughputの候補としてのみ残します。

## 採らなかった案と理由

- Android Chromiumのcanvasへ`opacity: 0.999`を設定する案は、不透明な対照でも約60fpsを維持したため採用しません。DOM occlusionが原因だという説明も再現できませんでした。
- 完成fragmentを早く渡す案は、GalaxyとローカルSSD Chromeのどちらでもシーク完了時間を一貫して短縮しませんでした。後続fragmentのthroughput候補としてのみ残します。
- AACが揃った完成GOPをさらに1 GOP保留しない案は、初回fragmentまでの入力を最大512KiB減らしました。しかしGalaxyのシーク完了時間は180秒群で162.7→179.2msとなり、`first-byte`からのfragment生成も短縮しなかったため採用しません。
- 毎GOPをnon-IDR recovery pointにする案は、decoderが古いGOPを捨てる時間を約68ms減らしました。しかし次fragmentの生成待ちで相殺され、hardware decoder互換性も未確認なので採用しません。
- seek leadを1.0秒から0.5秒へ固定変更する案はシーク完了時間を短縮しましたが、5地点中2地点で要求時刻を越えたため採用しません。
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
| 公開可能な集計・再現スクリプト | [`scripts/`](scripts/)（[切断後のFileResponse処理](scripts/reproduce-file-response-disconnect.py)、[TS全体の欠損とpictureの照合](scripts/inspect-ts-transport-defects.py)、[既存fixtureの詳細照合](scripts/inspect-nogizaka-transport-defect.py)、[fMP4時刻列の解析](scripts/fmp4_timeline.py)、[破損区間の変換比較](scripts/measure-nogizaka-defect-conversion.py)、[Windows異常TS診断](scripts/analyze-windows-anomaly-diagnostic.py)を含む） |

録画ファイル、認証情報、実際のLAN内アドレス、ローカルパス、アクセスログは含みません。
番組名は素材の識別用であり、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
