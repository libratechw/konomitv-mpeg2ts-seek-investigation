# KonomiTV 録画再生のシーク・表示品質調査

KonomiTVの録画再生について、シーク後の表示復帰時間、定常再生のFPS、コマ落ち、短いカクつき、長時間stallをコードと実機で調べた記録です。
主対象はMPEG-2 TSのOriginal直接再生ですが、サーバーエンコードHLSとの違いも同じ指標で確認します。
リポジトリ名には調査開始時の`seek-investigation`が残っていますが、素材本来のcadenceを維持し、負荷やシークの後も安定した表示へ戻るまでを対象とします。

## 測定指標

**表示復帰時間**は、シーク先の映像がYADIF canvasに出て、`seeked`の後も消えずに残るまでの時間です。
終点は共通ですが、起点は次の2種類があるため、数値には起点を併記します。

- **`video.currentTime`起点**：製品コードを使う測定で、シーク時刻をvideo要素へ設定した瞬間から測ります。
- **`seek-requested`起点**：計測版playerで、video要素の`seeking` eventを受け、buffer外シークを受理した瞬間から測ります。

異なる起点とinstrumentationで得た値は、個別修正の効果量として直接比較しません。
UIのtouch eventから`video.currentTime`設定までを含む値も、この2種類へ混ぜません。

YADIFの待ち行列を空にして時刻同期をやり直す処理は、**queue全reset**と呼びます。
容量確保や実遅延からの追いつきで古いfieldだけを捨てる処理と、その件数は、**FIFO破棄**と呼びます。

## 現在の到達点

総合検証用の[`integration/current-useful-fixes`](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes)は、表で「採用」とした互換性のある修正をまとめたbranchです。
個別PR候補の境界と祖先関係を保ったままKonomiTVで総合効果を測るためのもので、upstreamへそのままmergeする対象ではありません。

branch固有READMEには、全修正適用前後の比較と、各修正branchへのリンク、目的、内容、効果、レビューコスト、保守コストを掲載しています。
overflow時刻圧縮をmergeする前の製品コード`e417d12`では、`tsukumijima/main` `52a3db5`との同条件比較で、Galaxyの`video.currentTime`起点の表示復帰時間が中央値287.1→145.8msとなり、250ms以内が14/40→40/40になりました。

現在のintegrationをGalaxyで測ると、600秒定常再生はrAF 59.998回/秒、入力video callback 29.970回/秒で、YADIFの`missed`とqueue全resetはいずれも0でした。
`video.currentTime`起点の表示復帰時間は40回の中央値159.7ms、p95 193.6ms、最大246.8msで、40/40が250ms以下でした。

同じintegrationを電源モード「最適な電力効率」のWindows Chromeで測ると、120秒定常再生は59.719fps、40ms超8回、queue全reset 0でした。
`video.currentTime`起点の表示復帰時間は40回の中央値252.7msで、20/40が250msを超えました。

Windowsの遅い地点では、最初のappendが目的時刻の約75ms先までしか含まず、Chromeが約565ms先までbufferされるのを待っていました。
TSと現行Sessionの対応を調べると、次の安全なfragmentは要求時刻より74ms後から始まるため、正確なシークを保つ現行policyでは現在の選択が最適でした。

同一ホストのLinux Chromeでは、正常区間120秒が59.867fps、p99 17.7ms、queue全reset 0でした。
同じ40回の`video.currentTime`起点の表示復帰時間は中央値131.7ms、p95 195.4ms、最大196.2msでしたが、LANクライアントの目標達成には数えません。

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
この1件はbuffer枯渇やsegment切替では説明できず、H.264のdecodeまたは表示期限超過側を優先して切り分けます。
詳しい条件と生値は[1080p60長時間比較](results/galaxy-recorded-hls-1080p60-long-comparison.json)と[H.264 profile・bitrate比較](results/galaxy-recorded-hls-h264-profile-bitrate-comparison.json)に保存しています。

他の14画質とHLSシークは、再生設定をwatch pageの初回実行前に投入するよう測定器を直した条件で再測定が必要です。
修正前の測定は、初期既定の1080pと要求画質のencoder sessionが並行したため、現在の絶対値には使いません。

## PR候補の優先順位

優先順位は、確認できた効果、正しさへの影響、差分の理解しやすさ、レビュー負荷、将来の保守コストから決めています。
`軽`は局所的で契約変更がない変更、`中`は状態管理または小さなAPI追加、`重`は複数層を横断する変更です。

提出先は [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) と [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) の2つです。
生成済み`dist`を追跡するtsukumijimaフォーク向けbranchでは、sourceとdistを別コミットにしています。
効果の数値はこの表をREADME内の正本とし、詳しい統計量と生値は[`results/`](results/)から参照できます。

### P0

| 順位 | branch | 提出先 | 修正内容 | 効果 | 重さ |
| ---: | --- | --- | --- | --- | --- |
| 1 | [`fix/preserve-seek-probe-sample`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-seek-probe-sample) `a10253e` | otya128 | first fragment時刻でprobe標本を上書きする5行を削除 | 追加probe 14/40→0/40。表示復帰時間 296.3→244.3ms | **軽**。1ファイル5行の削除 |
| 2 | [`feat/report-ts-restart-offsets`](https://github.com/libratechw/mpeg2toh264/tree/feat/report-ts-restart-offsets) `787c7ba` | otya128 | fragmentへ`restartOffset`を付与し、PTSとrestart位置を別のmark列で持つ | 再開同値性と回帰の試験が成功。単独の速度効果はなく、順位3の前提 | **重**。TS demuxからWASMまで横断 |
| 3 | [`perf/reuse-observed-ts-restarts`](https://github.com/libratechw/mpeg2toh264/tree/perf/reuse-observed-ts-restarts) `ac4f879` | otya128 | 観測済みの安全位置をplayer内に保持し、要求時刻以前1秒以内の最新位置を再利用 | 診断版A/Bでprobe 40→0、表示復帰時間 226.5→161.5ms | **中**。worker 1ファイル。順位2に依存 |
| 4 | [`fix/separate-yadif-queue-recovery`](https://github.com/libratechw/mpeg2toh264/tree/fix/separate-yadif-queue-recovery) source `26484fd` | tsukumijima | 容量不足は必要枚数だけFIFO破棄し、表示不能な未来時刻列だけqueue全reset | seek後の表示停止 35/90→1/90。2秒注入は全reset 0、最大lateness 6.52ms | **中**。YADIF 1ファイルのqueue policy |
| 5 | [`fix/compress-yadif-overflow-schedule`](https://github.com/libratechw/mpeg2toh264/tree/fix/compress-yadif-overflow-schedule) source `7ef6696` | tsukumijima | FIFO破棄したfieldの`duration`合計を、残ったfieldのdeadlineから引く | 2秒注入の3走行平均で、GalaxyのFIFO破棄 218.0→0.67 field | **軽〜中**。`#prepareQueue()`の8行 |
| 6 | [`fix/preserve-destination-frame-on-seek`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-destination-frame-on-seek) source `2d072f3` | tsukumijima | playhead近傍の描画済みframeを記録し、同じseekの`seeked`で消さない | Linux 40回の表示復帰時間 p95 246.5→178.9ms。Galaxyは退行なし | **中**。seeking/history状態のレビューが必要 |

### P1

| 順位 | branch | 提出先 | 修正内容 | 効果 | 重さ |
| ---: | --- | --- | --- | --- | --- |
| 7 | [`fix/mse-reset-inflight-append`](https://github.com/libratechw/mpeg2toh264/tree/fix/mse-reset-inflight-append) `f8ab9c7` | otya128 | SourceBuffer操作にseek世代を対応付け、旧`updateend`を新queueへ適用しない | 460回のseekでappend中resetを67回観測。新initの誤破棄は0回 | **中**。MSE状態管理と回帰試験 |

tsukumijimaフォーク向けの順位4から6は、source と生成済み`dist`を別コミットにしています。
dist側のcommitは順に `27b327e`、`ac2a2a9`、`f3ba99d` です。

### 推奨するマージの順序

順位2はcoreの再開位置契約なので、先にレビューを終えてから順位3のplayer利用policyを出します。
順位4はqueue policyの土台で、順位5はその子PRです。
順位1、6、7は他と修正箇所が重ならず、いつでも並行して提出できます。

tsukumijimaフォーク固有のYADIF変更は、otya128向けの変更へ混ぜません。
提出先ごとに整理した図は[integration branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes#レビューの順序)にあります。

### このブランチに含めていない変更

[`feat/seek-timing-context`](https://github.com/libratechw/mpeg2toh264/tree/feat/seek-timing-context) `58a9920` は計測専用のため含めていません。
player、worker、transcoder、picture pool、MSEへ同じseek IDのtiming contextを伝播し、probe標本の誤上書きなどを分離できました。
直接の速度改善はなく、10ファイルにわたる横断と公開event契約の保守が必要なため、効果が立証できるまで提出を急ぎません。

[`fix/deliver-completed-fragments-early`](https://github.com/libratechw/mpeg2toh264/tree/fix/deliver-completed-fragments-early) `30ad508` は効果が確認できないため含めていません。
transcoderから完成fragmentを逐次通知しますが、初回fragmentと表示復帰のどちらも一貫して短縮しませんでした。
transcoderとworkerの順序、cancel、backpressureのレビューが必要な規模でもあるため、後続throughputの候補としてのみ残します。

## 採用した修正と根拠

表の順位と、対応するsource commitを添えます。

- 順位1 [`a10253e`](https://github.com/libratechw/mpeg2toh264/commit/a10253e)：probe標本をfirst fragment時刻で上書きしない修正は、不要な追加probeをなくし、`seek-requested`起点の表示復帰時間を代表値で71.3ms短縮しました。
- 順位2 [`787c7ba`](https://github.com/libratechw/mpeg2toh264/commit/787c7ba)：media fragmentへ再開可能なTS位置を付ける修正は、別Sessionで同じGOPと音声を再開できることを試験で確認しました。単独の速度効果はなく、順位3の前提です。
- 順位3 [`ac4f879`](https://github.com/libratechw/mpeg2toh264/commit/ac4f879)：観測済みのPAT/PMT安全位置を後続シークで再利用する修正は、Galaxyの診断版でprobeを40件から0件へ減らしました。永続indexは導入していません。
- 順位4 [`26484fd`](https://github.com/libratechw/mpeg2toh264/commit/26484fd)：YADIFのqueue容量不足と時刻同期破綻を分ける修正は、正式な基準版との直接比較でseek後の表示停止を35/90から1/90へ減らしました。容量不足では必要数だけFIFO破棄し、表示不能な時刻列だけqueue全resetします。提出ロジックへの2秒注入3走行では全reset 0、最大lateness 6.52msでした。
- 順位5 [`7ef6696`](https://github.com/libratechw/mpeg2toh264/commit/7ef6696)：FIFO破棄した時間だけ残りのdeadlineを詰める修正は、Galaxyの負荷注入でFIFO破棄を平均218.0→0.67 fieldへ減らしました。
- 順位6 [`2d072f3`](https://github.com/libratechw/mpeg2toh264/commit/2d072f3)：seeked直前に描画済みの目的frameを保持する修正は、Linuxで起きた約149msの待ち直しを除きました。Galaxyでは同じ競合が起きず、退行がないことを確認しました。
- 順位7 [`f8ab9c7`](https://github.com/libratechw/mpeg2toh264/commit/f8ab9c7)：MSE操作の世代管理は、旧append完了が新しいinit segmentを失わせる模擬競合を防ぎます。GalaxyとWindowsの計460回ではappend中resetを67回観測しましたが、新initの誤破棄は0回でした。

## 試して採らなかった案

- Android Chromiumのcanvasへ`opacity: 0.999`を設定する案は、不透明な対照でも約60fpsを維持したため採用しません。DOM occlusionが原因だという説明も再現できませんでした。
- 完成fragmentを早く渡す案は、GalaxyとローカルSSD Chromeのどちらでも表示復帰時間を一貫して短縮しませんでした。後続fragmentのthroughput候補としてのみ残します。
- AACが揃った完成GOPをさらに1 GOP保留しない案は、初回fragmentまでの入力を最大512KiB減らしました。しかしGalaxyの表示復帰時間は180秒群で162.7→179.2msとなり、`first-byte`からのfragment生成も短縮しなかったため採用しません。
- 毎GOPをnon-IDR recovery pointにする案は、decoderが古いGOPを捨てる時間を約68ms減らしました。しかし次fragmentの生成待ちで相殺され、hardware decoder互換性も未確認なので採用しません。
- seek leadを1.0秒から0.5秒へ固定変更する案は表示復帰時間を短縮しましたが、5地点中2地点で要求時刻を越えたため採用しません。
- PAT/PMTを含むRAPを毎seekで4〜8MiB先読みする案は、追加Rangeの費用を回収できず遅くなりました。再生中の学習やsidecarは、未知のpre-target RAPを取り逃す素材を再現できた場合に再評価します。
- YADIFへ1 frame分の固定reserveを置く案は、短時間のカクつきを隠しましたが、600秒で最大11.15秒の停止を生じました。queue容量を増やす案もfuture leadを増やすため採用しません。
- 通常は1 rAFにつき1 fieldだけ表示する案は120秒では59.791→59.932fpsへ改善しましたが、600秒ではrAF 56.662回/秒、`missed` 541まで徐々に悪化しました。同じintegrationからこの案だけを外すとrAF 59.998回/秒、`missed` 0だったため採用しません。
- 録画TSの`FileResponse` body chunkを増やす案は、Galaxyで小さな差が出ましたがsizeに対して単調でなく、Windowsの対応付き比較も−2.4〜+1.7msで中立だったため採用しません。

## 測定を読むときの前提

- 主計測では録画TSをKonomiTVサーバー側のローカルNVMeへコピーし、コピー元とSHA-256が一致することを確認しています。CIFS経由の絶対時間は主結果へ使いません。
- TS内の時刻は、永続GOP indexではなく、小さなHTTP RangeでPTSを探すメモリ内indexから求めます。約43GBのTSでも各地点2 probeで収束し、毎回先頭から走査する構成ではありません。
- 乃木坂工事中fixtureには、映像開始から125.025秒付近に破損video packetが1個あります。このpacketを横切る走行は、コマ落ち0の判定から外します。
- Galaxyの絶対時間は、古い検証タブが設定と再生資源を残さないよう、対象タブ1枚で取り直しました。以前の絶対値は主結果から外しています。
- 既存`presented` eventは`video.seeking`解除後のbuffered frameを示し、表示復帰時間とは一致しません。前景再生中の体感レイテンシには使いません。
- `droppedVideoFrames`はpredecodeまたは表示期限超過のdropを数え、最終YADIF canvasの可視コマ落ち数ではありません。Originalで数えた極短IDR recovery sampleのdropと、YADIF出力の表示間隔を分けて評価します。
- Windowsの値は、Ryzen 7 4700Uを電源モード「最適な電力効率」で測った補助条件です。同一モード内のbranch A/Bに使い、通常設定のWindowsやGalaxyとの絶対性能比較には使いません。
- 「乃木坂工事中」は確認区間だけを60 field候補、「MADDER」は確認区間だけを3:2候補として扱います。番組全体のcadenceを番組名から決めません。

## 長時間再生と反復シーク

10分間の連続再生で表示が劣化しないかを、順位4を親に持つ順位5のoverflow時刻圧縮branch（source `7ef6696`）を適用したbuildで確認しました。
現在のintegrationにもこのbranchを含みますが、他の修正も加わった別buildです。
表示復帰時間の中央値157.2msと160.5msは近く、どちらも40/40が250ms以下でしたが、3.3msの差を修正効果や退行としては扱いません。

既知の破損packetより後を使ったGalaxy全画面600秒走行では、入力video callback 29.972fpsに対し、double-rate YADIF canvasは59.942fpsでした。
canvasの40ms超間隔、YADIFの`late`、`degraded`、`discontinuities`、queue全reset、FIFO破棄はいずれも0でした。

同じbuildのGalaxy全画面40回では、`video.currentTime`起点の表示復帰時間が中央値157.2ms、p95 187.1ms、最大197.3msで、40/40が250ms以下でした。
シーク地点は「現在の到達点」と同じ180秒と480秒です。

現在のintegrationでは、1 rAFにつき1 fieldだけ表示する案を含む版と、その案だけを外した版を同じ軽量collectorで600秒比較しました。
含む版は3分後から徐々に低下し、全体rAF 56.662回/秒、入力callback 29.070回/秒、YADIFの`missed` 541となりました。

外した版はrAF 59.998回/秒、入力callback 29.970回/秒、`missed` 0を維持したため、この案をintegrationとPR候補から外しました。

外した版の40回seekは中央値159.7ms、p95 193.6ms、最大246.8msで、40/40が250ms以下でした。
詳しい条件と生値は[overflow時刻圧縮の600秒走行](results/galaxy-overflow-compression-clean-600s-summary.json)、[presentation policyの600秒A/B](results/galaxy-present-one-field-long-run-ab.json)、[新integrationの40回シーク](results/galaxy-integration-without-present-seek-visible-40.json)に保存しています。

## 詳細と公開範囲

詳しいデータフロー、仮説評価、改善候補は[REPORT.md](REPORT.md)にあります。
実機条件と素材ごとの結果は[results/device-results.md](results/device-results.md)、機械可読な集計値は[`results/`](results/)に置いています。

録画ファイル、認証情報、実際のLAN内アドレス、ローカルパス、アクセスログは含みません。
番組名は素材の識別用であり、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
