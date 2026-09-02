# KonomiTV 録画 MPEG-2 TS 直接再生調査

KonomiTVの「録画MPEG-2 TSをブラウザーで直接再生する経路」について、シーク後の復帰時間、定常再生のFPS、コマ落ち、短いカクつき、長時間stallをコードと実機で調べた記録です。
リポジトリ名には調査開始時の`seek-investigation`が残っていますが、素材本来のcadenceを維持し、負荷やシークの後も安定した表示へ戻るまでを対象とします。

## 測定指標

**可視初画**は、シーク先に対応し、`seeked`の後も消えずに残る最初のYADIF canvas描画です。
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
overflow時刻圧縮をmergeする前の製品コード`e417d12`では、`tsukumijima/main` `52a3db5`との同条件比較で、Galaxyの`video.currentTime`起点の可視初画が中央値287.1→145.8msとなり、250ms以内が14/40→40/40になりました。

現在のintegrationをGalaxyで測ると、120秒定常再生は59.933fpsで、40ms超間隔、YADIFの`late`、`missed`、queue全resetはいずれも0でした。
`video.currentTime`起点の可視初画は40回の中央値160.5ms、p95 190.6ms、最大228.8msで、40/40が250ms以下でした。

同じintegrationを電源モード「最適な電力効率」のWindows Chromeで測ると、120秒定常再生は59.719fps、40ms超8回、queue全reset 0でした。
`video.currentTime`起点の可視初画は40回の中央値252.7msで、20/40が250msを超えました。

Windowsの遅い地点では、最初のappendが目的時刻の約75ms先までしか含まず、Chromeが約565ms先までbufferされるのを待っていました。
TSと現行Sessionの対応を調べると、次の安全なfragmentは要求時刻より74ms後から始まるため、正確なシークを保つ現行policyでは現在の選択が最適でした。

同一ホストのLinux Chromeでは、正常区間120秒が59.867fps、p99 17.7ms、queue全reset 0でした。
同じ40回の`video.currentTime`起点の可視初画は中央値131.7ms、p95 195.4ms、最大196.2msでしたが、LANクライアントの目標達成には数えません。

## PR候補の優先順位

優先順位は、確認できた効果、正しさへの影響、差分の理解しやすさ、レビュー負荷、将来の保守コストから決めています。
`軽`は局所的で契約変更がない変更、`中`は状態管理または小さなAPI追加、`重`は複数層を横断する変更です。

生成済み`dist`を追跡するtsukumijimaフォーク向けbranchでは、sourceとdistを別コミットにしています。
効果の数値はこの表をREADME内の正本とし、詳しい統計量と生値は[`results/`](results/)から参照できます。

| 順位 | Priority | PR候補branch | 提出先 | 目的 | 修正内容 | 確認できた効果 | 変更の重さ | 統合版 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P0 | [`fix/preserve-seek-probe-sample`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-seek-probe-sample) (`a10253e`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 実測したbyte→PTS標本を壊さない | first fragment時刻でprobe標本を上書きする5行を削除 | 追加probe 14/40→0/40。`seek-requested`起点の可視初画はtarget対応中央値−71.3ms、中央値296.3→244.3ms | **軽**。1ファイルの5行削除で、保守負荷は小さい | 採用 |
| 2 | P0 | [`feat/report-ts-restart-offsets`](https://github.com/libratechw/mpeg2toh264/tree/feat/report-ts-restart-offsets) (`787c7ba`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 再開可能なTS位置をcoreから安全に報告する | fragmentへ直近PAT/PMTを含む`restartOffset`を付与し、PTSとrestart位置を独立したmark列で保持する | 再開同値性試験が成功。PTSなし、restart位置ありのPESが先行PTSを隠す回帰は修正前に失敗し、修正後に成功。速度効果は次のplayer PRとの組み合わせで測る | **重**。TS demux、GOP、Session、WASM APIを横断。公開値は`restartOffset`だけに限定 | 採用 |
| 3 | P0 | [`perf/reuse-observed-ts-restarts`](https://github.com/libratechw/mpeg2toh264/tree/perf/reuse-observed-ts-restarts) (`ac4f879`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 一度確認した位置への後続seekでprobeと余分な復号を省く | 観測済みGOPと安全位置をplayer内だけに保持し、要求時刻以前1秒以内の最新位置を再利用 | 診断版A/Bはprobe 40→0、`seek-requested`起点の可視初画中央値226.5→161.5ms、p95 278.4→220.5ms。正式branch組み込み版も同じ起点で中央値159.1ms、p95 212.4ms、最大229.0ms、40/40が250ms以下 | **中**。worker 1ファイル、core PRに依存。永続形式は増やさない | 採用 |
| 4 | P0 | [`fix/separate-yadif-queue-recovery`](https://github.com/libratechw/mpeg2toh264/tree/fix/separate-yadif-queue-recovery) (source `26484fd`、dist `27b327e`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | queue満杯と時刻同期破綻を分け、カクつきと長時間stallを防ぐ | 容量不足は必要枚数だけFIFO破棄し、表示不能な未来時刻列だけqueue全reset | seek後停止7/90→0/90を維持。注入試験のqueue全reset 14〜15→0、最大lateness 83.3→32.6ms。通常30秒59.768fps | **中**。YADIF 1ファイルのqueue policy。fork固有機能として保守 | 採用 |
| 5 | P0 | [`fix/compress-yadif-overflow-schedule`](https://github.com/libratechw/mpeg2toh264/tree/fix/compress-yadif-overflow-schedule) (source `7ef6696`、dist `ac2a2a9`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | 容量確保で捨てた表示時刻の穴からFIFO破棄が連鎖するのを防ぐ | FIFO破棄したfieldの`duration`合計を、残った全fieldのpresentation deadlineから引く | 2秒注入の3走行平均で、GalaxyのFIFO破棄218.0→0.67 field、Windows 21.67→0.67 field。Galaxyで2/3走行に続いた連鎖とqueue全reset 1回を解消 | **軽〜中**。`#prepareQueue()`の8行。容量破棄時の時刻不変条件を保守 | 採用 |
| 6 | P0 | [`fix/preserve-destination-frame-on-seek`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-destination-frame-on-seek) (source `2d072f3`、dist `f3ba99d`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | seeked直前に描画済みの目的frameを消さない | playhead近傍の描画済みframeを記録し、同じseekの`seeked`でcanvasを再消去しない | `seek-requested`起点の可視初画は、Linux 40回のp95 246.5→178.9ms、最大280.0→180.4ms。Galaxyはp95 193.2ms、最大212.8msで退行なし | **中**。YADIF 1ファイルだがseeking/history状態のレビューが必要 | 採用 |
| 7 | P1 | [`fix/present-one-field-per-refresh`](https://github.com/libratechw/mpeg2toh264/tree/fix/present-one-field-per-refresh) (source `fb2e6e4`、dist `21cc3c3`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | 通常のcallback位相差で表示可能なfieldをFIFO破棄しない | 通常はFIFO順に1 fieldを表示し、最古fieldが2 refreshを超えて遅れた場合だけ追いつく | 120秒2走行平均でGalaxy 59.791→59.932fps、25ms超40→22.5回、`late` 9.5→0。Windows 59.354→59.783fps、25ms超127→43回、`late` 66→15.5。queue全reset 0 | **中**。YADIF 1関数のpresentation policy。閾値とqueue不変条件を保守 | 採用 |
| 8 | P1 | [`fix/mse-reset-inflight-append`](https://github.com/libratechw/mpeg2toh264/tree/fix/mse-reset-inflight-append) (`f8ab9c7`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 古いappend完了が新seekのinit segmentを失わせる競合を防ぐ | SourceBuffer操作とseek世代を対応付け、旧`updateend`を新queueへ適用しない | 修正前に失敗する競合試験が成功。通常seek平均251.4→250.1msで速度差はなく、実利用のstall削減量は未立証 | **中**。MSE状態管理と回帰試験。将来保守負荷は小〜中 | 採用 |
| 9 | P1 | [`feat/seek-timing-context`](https://github.com/libratechw/mpeg2toh264/tree/feat/seek-timing-context) (`58a9920`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | Rangeからdecoder提示までを同じseek IDで分解する | player、worker、transcoder、picture pool、MSEへtiming contextを伝播 | 直接の速度改善なし。probe標本の誤上書き、先頭IDR job 33〜40ms、append後変動を分離できた | **重**。10ファイルにわたり複数層を横断し、公開event契約の保守が必要 | 除外（計測専用） |
| 10 | P3 | [`fix/deliver-completed-fragments-early`](https://github.com/libratechw/mpeg2toh264/tree/fix/deliver-completed-fragments-early) (`30ad508`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 完成fragmentと後続変換を重ねる | transcoderから完成fragmentを逐次通知する | GalaxyとローカルSSD Chromeで初回fragmentと可視初画のどちらも一貫した短縮なし。後続throughput候補としてのみ残す | **中〜重**。transcoder、workerの順序、cancel、backpressureのレビューが必要 | 除外（効果未確認） |

順位2と3は別PRとし、coreの再開位置契約を先にレビューしてから、その祖先上でplayerの利用policyを提案します。
順位4を親として、順位5のoverflow時刻圧縮と順位7のpresentation policyを独立した兄弟PRとして提案します。

順位6はこれらとハンクが重ならないため、並行して提出できます。
fork固有のYADIF変更はupstream向け変更へ混ぜず、順位9は効果が立証できるまで提出を急ぎません。

## 採用した修正と根拠

- probe標本をfirst fragment時刻で上書きしない修正は、不要な追加probeをなくし、`seek-requested`起点の可視初画を代表値で71.3ms短縮しました。
- 観測済みのPAT/PMT安全位置を後続シークで再利用する修正は、Galaxyの診断版でprobeを40件から0件へ減らしました。永続indexは導入せず、coreの位置報告とplayerの利用policyを別PRにします。
- YADIFのqueue容量不足と時刻同期破綻を分ける修正は、seek後の表示停止を7/90から0/90へ減らしました。容量不足では必要数だけFIFO破棄し、表示不能な時刻列だけqueue全resetします。
- 通常は1 rAFにつき1 fieldを表示する修正は、Galaxyの120秒走行を代表値で59.791→59.932fpsへ改善しました。実遅延が2 refreshを超えた場合だけ追いつきます。
- FIFO破棄した時間だけ残りのdeadlineを詰める修正は、Galaxyの負荷注入でFIFO破棄を平均218.0→0.67 fieldへ減らしました。
- seeked直前に描画済みの目的frameを保持する修正は、Linuxで起きた約149msの待ち直しを除きました。Galaxyでは同じ競合が起きず、退行がないことを確認しました。
- MSE操作の世代管理は、旧append完了が新しいinit segmentを失わせる模擬競合を防ぎます。通常シークの短縮と実利用でのstall削減量は確認できていません。

## 試して採らなかった案

- Android Chromiumのcanvasへ`opacity: 0.999`を設定する案は、不透明な対照でも約60fpsを維持したため採用しません。DOM occlusionが原因だという説明も再現できませんでした。
- 完成fragmentを早く渡す案は、GalaxyとローカルSSD Chromeのどちらでも可視初画を一貫して短縮しませんでした。後続fragmentのthroughput候補としてのみ残します。
- AACが揃った完成GOPをさらに1 GOP保留しない案は、初回fragmentまでの入力を最大512KiB減らしました。しかしGalaxyの可視初画は180秒群で162.7→179.2msとなり、`first-byte`からのfragment生成も短縮しなかったため採用しません。
- 毎GOPをnon-IDR recovery pointにする案は、decoderが古いGOPを捨てる時間を約68ms減らしました。しかし次fragmentの生成待ちで相殺され、hardware decoder互換性も未確認なので採用しません。
- seek leadを1.0秒から0.5秒へ固定変更する案は可視初画を短縮しましたが、5地点中2地点で要求時刻を越えたため採用しません。
- PAT/PMTを含むRAPを毎seekで4〜8MiB先読みする案は、追加Rangeの費用を回収できず遅くなりました。再生中の学習やsidecarは、未知のpre-target RAPを取り逃す素材を再現できた場合に再評価します。
- YADIFへ1 frame分の固定reserveを置く案は、短時間のカクつきを隠しましたが、600秒で最大11.15秒の停止を生じました。queue容量を増やす案もfuture leadを増やすため採用しません。

## 測定を読むときの前提

- 主計測では録画TSをKonomiTVサーバー側のローカルNVMeへコピーし、コピー元とSHA-256が一致することを確認しています。CIFS経由の絶対時間は主結果へ使いません。
- TS内の時刻は、永続GOP indexではなく、小さなHTTP RangeでPTSを探すメモリ内indexから求めます。約43GBのTSでも各地点2 probeで収束し、毎回先頭から走査する構成ではありません。
- 乃木坂工事中fixtureには、映像開始から125.025秒付近に破損video packetが1個あります。このpacketを横切る走行は、コマ落ち0の判定から外します。
- Galaxyの絶対時間は、古い検証タブが設定と再生資源を残さないよう、対象タブ1枚で取り直しました。以前の絶対値は主結果から外しています。
- 既存`presented` eventは`video.seeking`解除後のbuffered frameを示し、可視初画とは一致しません。前景再生中の体感レイテンシには使いません。
- `droppedVideoFrames`はpredecodeまたは表示期限超過のdropを数え、最終YADIF canvasの可視コマ落ち数ではありません。Originalで数えた極短IDR recovery sampleのdropと、YADIF出力の表示間隔を分けて評価します。
- Windowsの値は、Ryzen 7 4700Uを電源モード「最適な電力効率」で測った補助条件です。同一モード内のbranch A/Bに使い、通常設定のWindowsやGalaxyとの絶対性能比較には使いません。
- 「乃木坂工事中」は確認区間だけを60 field候補、「MADDER」は確認区間だけを3:2候補として扱います。番組全体のcadenceを番組名から決めません。

## 長時間再生と反復シーク

既知の破損packetより後を使ったGalaxy全画面600秒走行では、入力video callback 29.972fpsに対し、double-rate YADIF canvasは59.942fpsでした。
canvasの40ms超間隔、YADIFの`late`、`degraded`、`discontinuities`、queue全reset、FIFO破棄はいずれも0でした。

同じbuildのGalaxy全画面40回では、`video.currentTime`起点の可視初画が中央値157.2ms、p95 187.1ms、最大197.3msで、40/40が250ms以下でした。
詳しい条件と生値は[600秒走行](results/galaxy-overflow-compression-clean-600s-summary.json)と[40回シーク](results/galaxy-overflow-compression-visible-seek-40.json)に保存しています。

## 詳細と公開範囲

詳しいデータフロー、仮説評価、改善候補は[REPORT.md](REPORT.md)にあります。
実機条件と素材ごとの結果は[results/device-results.md](results/device-results.md)、機械可読な集計値は[`results/`](results/)に置いています。

録画ファイル、認証情報、実際のLAN内アドレス、ローカルパス、アクセスログは含みません。
番組名は素材の識別用であり、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
