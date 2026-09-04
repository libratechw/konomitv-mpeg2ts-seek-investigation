# KonomiTV 録画再生のシーク遅延と表示品質

コードとChrome/Galaxy実測から、通常seekの主要な待ちは、PTS probeとRange応答、GOPとAACが揃うまでの読取・H.264変換、MSE投入とdecoder再開である。
「indexがなく、毎回先頭から走査するため遅い」という構成ではない。
42.9GB・6時間40分のTSでもPTS探索は各seek 2 probeで収束した。
当時の絶対時間はタブ数を記録していなかったため主結果から外すが、単一タブで取り直した短い録画でもresponse中央値50〜52msに対し、可視YADIF canvas初描画中央値215〜267msで、index探索以外の待ちが残った。

シークとは別に、単一タブ・全画面のGalaxy A/BでYADIF出力がほぼ停止する走行を、正式な基準版35/90、queue容量・時刻同期分離版1/90で再現した。
canvasのopacity変更は原因または修正ではなかった。
停止時もrAFとfilterは動作したが、fieldの表示予定が未来へ連鎖してqueueが飽和していた。
また、MSE resetと古いappend完了が競合すると新しいinit segmentが失われる問題を人工試験で再現し、別branchで修正した。
修正前挙動の実機計460回ではappend中resetを67回観測したが、古い完了時のqueueはすべて空で、新しいinit segmentの誤破棄は0回だった。

## 対象と証拠の範囲

| 対象 | 確認した版と範囲 |
| --- | --- |
| KonomiTV checkout | `master`、`e92fba8bb219589c8e4ada9609ed4a9d91b33c00` |
| checkout の依存指定 | mpeg2toh264 `52a3db5e8fb9833e6cade2167097849c668bdb1f` |
| YADIF opacity実験 | `upstream/main`基点の`6b825e8`で検証したが棄却。誤取り込み防止のため公開branchは削除し、結果だけ本リポジトリに保存 |
| YADIF queue容量・時刻同期 | 公開済みの測定点はsource `26484fd` / dist `27b327e`と、その子のsource `acfce36` / dist `63a5708`。保存traceでは、容量確保後も残る表示予定を動かさないことが致命的停止を維持した。必要最小限のFIFO破棄と捨てた時間分の表示予定圧縮だけを残し、独立した必要性を示せない閾値resetを外した候補を再測定中 |
| MSE修正 | 公開`fix/mse-reset-inflight-append`、`upstream/main`基点の`f8ab9c7` |
| seek計測 | 公開`feat/seek-timing-context`、計測実装`ffe2893`、`presented`の意味を実測に合わせて明記した現HEAD `58a9920` |
| 完成fragment早期受け渡し | 公開`fix/deliver-completed-fragments-early`、`upstream/main`基点の`30ad508` |
| seek probe標本の保持 | 公開`fix/preserve-seek-probe-sample`、`upstream/main`基点の`a10253e` |
| DPlayer | `DPlayer/`へclone。`master`の`a5f847877eada1390456aea4ed7da8e31b4c166e`（v1.33.1）がKonomiTVのlockfileと一致 |
| Windows補助端末 | Ryzen 7 4700U、Google Chrome。電源モードは「最適な電力効率」のまま維持し、低性能・電力制約下の補助条件として扱う |
| ローカルbackend | 公式`ghcr.io/tsukumijima/konomitv:latest`、revision `e92fba8bb219589c8e4ada9609ed4a9d91b33c00`、digest `sha256:4220e7ad65f877921b880eaa81822297e3694f83a6b3815b3569328398a740e4` |
| 共有された稼働環境 | 共有されたLAN内稼働環境。公開 API の版表記は `0.14.1`。版表記だけでは Git commit を特定できない |
| 共有環境で確認したWorker | `/assets/worker-Dl8lDoXO.BZ9fuFvy.js` が依存`52a3db5e`の`packages/player/dist/assets/worker-Dl8lDoXO.js`と一致 |
| 稼働 YADIF | 公開 `CaptureManager-C0PFUpsj.js` に新しい `seeked` 処理、`filmCombThreshold`、`queueResetted` を確認。bundle 全体とソースの同一性までは主張しない |
| サーバー配信依存 | ローカル公式コンテナのStarlette 1.6.0実体を確認。`FileResponse.chunk_size`は64KiB |

検証後の節目でremoteを再取得した結果、`otya128/main`は`d5df08b`、`tsukumijima/main`は`52a3db5`、KonomiTV `origin/master`は`e92fba8`のままで、関連する新しい修正はなかった。
このためqueue再同期はupstreamの既存挙動をフォーク拡張へ戻す変更として維持し、独自の`expectedDisplayTime`アンカーは優先度を下げたままとする。

Worker の SHA-256 は `d83906ec71e8eb9f503e9787f8ade32aaff133b791ef2ae185a098ef8bd8e1c7`。
固定依存のsource mapに含まれるplayer、worker、source、mse、pool、transcoderのTypeScriptは、今回参照した`52a3db5e`のソースと一致する。
MSE修正、seek計測、完成fragment早期受け渡しは、いずれも`otya128/mpeg2toh264`の`upstream/main` `d5df08b`から分けた独立branchとしてGitHubフォークへpush済みである。
YADIF opacity実験は追加計測で根拠を失ったため公開branchを削除し、ほかの3件もPRはまだ作成していない。
Galaxy実測時はKonomiTV依存`52a3db5e`へ同じsource変更を載せた一時buildを使用したが、誤ってtsukumijimaフォークへ取り込まれないよう、その基点の公開branchは削除した。

共有環境から取得したものは版情報、HTML、公開JavaScriptだけで、録画API、録画データ、設定、プロセスにはアクセスしていない。
KonomiTV checkoutを最新へfast-forwardし、clientをbuildしてViteで起動した単体試験に加え、公式コンテナを`127.0.0.1:7012`だけへ公開した隔離backendを起動した。
backendは新規DBを使い、ローカルにread-only mountした録画領域の3素材だけを個別にread-only mountした。
録画API、Starlette `FileResponse`、実DPlayer UIを含むend-to-end seekを、デスクトップGoogle ChromeとGalaxy Tab S11 UltraのGoogle Chromeで測定した。
実運用NASのcold cacheと聴感による実音声再開T11は未測定である。

## 直接再生のデータフロー

```text
DPlayer の録画シークバー
  → DPlayer.seek(time)
  → HTMLVideoElement.currentTime
  → Mpeg2TsPlayer の seeking handler
  → Worker の Playback.seek(time)
       ├─ 既存読み込みと変換の世代を中止、MSE reset
       └─ PTS probe 用 HTTP Range を最大4回
            → 補正した byte offset から終端までの HTTP Range
                 → KonomiTV GET /api/videos/{id}/download
                 → DB の recorded_video.file_path
                 → Python / Starlette FileResponse
                 → ファイル open / seek / read（サーバーで変換しない）
            ← MPEG-2 TS の生バイト列
       → ブラウザ Worker: TS 同期、PAT / PMT、PES 分離
       → MPEG-2 GOP、AAC ADTS 解析
       → Rust / WASM: MPEG-2 → H.264
           （利用可能なら picture Worker pool で並列変換）
       → 同じ Worker: H.264 と AAC を fMP4 に mux
       → MSE SourceBuffer（auto: Worker 対応時は Worker 内）
       → ブラウザの H.264 / AAC decoder
            ├─ 音声出力
            └─ video の提示フレーム
                 → 必要な端末では rVFC → WebGL YADIF / IVTC → rAF / canvas
                 → 不要な端末では video をそのまま表示
```

入口は [PlayerController.ts:486](https://github.com/tsukumijima/KonomiTV/blob/e92fba8bb219589c8e4ada9609ed4a9d91b33c00/client/src/services/player/PlayerController.ts#L486)、オプションは [同:707](https://github.com/tsukumijima/KonomiTV/blob/e92fba8bb219589c8e4ada9609ed4a9d91b33c00/client/src/services/player/PlayerController.ts#L707)。
対象は録画中でない MPEG-TS / MPEG-2 で、`passthrough:false`、`mediaSource:'auto'`、録画の service ID を指定する。
`VideoStream`、`VideoEncodingTask`、HLS segment のサーバー変換は、この直接再生経路を通らない。
サーバーの `TSKeyFrameSeeker` を高速化しても、この経路にはそのままでは効かない。

## UI からシーク先決定まで

### 指を離した時点で seek を実行する

[DPlayer controller.ts:168](https://github.com/tsukumijima/DPlayer/blob/a5f847877eada1390456aea4ed7da8e31b4c166e/src/ts/controller.ts#L168) の `thumbMove` は、バーと時刻表示を更新し、再生中なら pause する。
ドラッグ中の各 move では TS の seek を呼ばない。
`thumbUp` が座標を確定し、`DPlayer.seek(..., true)` と必要に応じて `video.play()` を呼ぶ。
[DPlayer player.ts:175](https://github.com/tsukumijima/DPlayer/blob/a5f847877eada1390456aea4ed7da8e31b4c166e/src/ts/player.ts#L175) は `video.currentTime` を同期的に設定する。
この経路に明示的な debounce、throttle、数百 ms の timeout はない。
サムネイル表示、バーの DOM 更新、danmaku の seek、ブラウザが `seeking` イベントを配送するまでの main thread 混雑は別に測る必要がある。

[player.ts:851](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/player.ts#L851) は、目的時刻が `video.buffered` 内なら Worker に seek を送らない。
この場合、新規 Range、再変換、MSE 全削除は発生せず、ブラウザ内の復号位置変更になる。
範囲外の場合だけ video timeline を消し、Worker に `seek` を送る。
200 ms の playhead 通知は先読みと eviction 用であり、seek 発火の debounce ではない。
KonomiTV の `waiting` / `playing` handler は主に spinner 表示を制御する。
録画の通常 seek で HLS 用の待ち処理や初回画質切替処理が走るとは扱わない。

### PTS で補正する小さなメモリ内 index がある

[worker.ts:306](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/worker.ts#L306) と [protocol.ts:63](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/protocol.ts#L63) の処理は次の通り。

1. `target - 1秒` を探索目標にする。先頭より前には進めない。
2. ファイル両端と既存 probe 結果から byte offset を線形補間する。情報がなければ平均 bitrate 相当。
3. その位置から **128 KiB** の単一 Range を読み切る。
4. 最初の PES PTS と、初回再生で決めた timeline origin の差を求める。
5. `{byte, seconds}` を `#index` に保存し、誤差が **±0.5秒**以内なら終了する。
6. 最大 **4回**まで補間と Range 読み取りを繰り返し、決めた offset から本体を再取得する。

probe は直列である。
通常、範囲外 seek は **1〜4 probe + 本体1本、計2〜5 HTTP request** から始まる。
再生の先読み上限に達した後の再開 request や異常応答は別に数える。
probe の先頭 timestamp だけで足りても、現状の `readRange()` は `arrayBuffer()` で128 KiB全部の到着を待つ。
probe のバイト列は本体変換に再利用されない。

初回 load の末尾 **1 MiB** probe から最後の PTS を取り、origin との差で duration を求める。
末尾 probe は seek ごとには繰り返さない。
suffix Range の応答がおかしい場合のみ、絶対位置の末尾 Range を追加する。
DB の `file_size`、`duration`、旧 `key_frames`、`segment_map` は存在するが、この player への seek index 入力になっていない。
PCR や GOP の byte position を使う永続 index も、この経路にはない。

[mpegts.rs:1405](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/crates/mpeg2toh264/src/container/mpegts.rs#L1405) の `walk_pts()` は PAT / PMT を待たず、全 PID の video / audio PES を対象とする。
これは短い probe の取得を可能にする一方、選択 service の video PTS に限定されない。
複数 service、A/V の時刻差、PTS 不連続、B-picture の提示順が補正の誤差要因になる。
全 recording で支配的な問題になると実測したわけではない。

`#byteFor()` の結果は TS packet 境界や I-picture に整列していない。
本体 demuxer が packet 同期を取り直す。
probe は I-picture、open GOP、sequence header を検査せず、直前の random access point を確定しない。
4回目の probe が外れた場合、最後に再補間した位置は未検証のまま採用される。
固定の1秒 lead は、長い GOP や tables の疎な素材でも目的時刻以前から再生できる保証にはならない。

もう一つの精度上の問題は [worker.ts:692](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/worker.ts#L692)。
最初の fragment の時刻を、実際の GOP 開始 byte ではなく `source.offset` と組にして index へ保存する。
Range 開始から tables / GOP まで捨てた区間があれば、同じ byte に対する probe の PTS より後の時刻で上書きする。
計測した12 seekでは、同じbyteのfirst fragment時刻はprobe PTSより0.17〜0.86秒後だった。
この上書きをやめると、最初の遠距離2 seek後の追加probeは、直接デモの実行順を反転した2比較でどちらも4/10から0/10になった。
実KonomiTVのDPlayerでもdesktopは2/10から0/10になった。

可視初画への効果は、最新KonomiTV `e92fba8`、Galaxy Tab S11 Ultra、Android 16、Chrome 151、60Hz、LAN直結、実DPlayerのOriginal再生、YADIF有効、`autoFilm:false`で再検証した。
公開YADIF後継`26484fd`と計測コードを共通基点にし、差分をfirst fragment時の誤ったindex書込み4行だけに限定した。
各ブロックを新規タブから開始し、600/900秒の2 seekをwarm-upとして除外した後、600/900〜609/909秒の20 seekを基準・修正・修正・基準の順で測った。

基準40 seekでは追加probeが14件、修正版40 seekでは0件だった（Fisherの正確確率検定、両側`p=0.0000308`）。
修正版は20地点中12地点で0.5005〜1.001秒後のGOPを選び、40 seekすべてで要求時刻を越えなかった。
first fragment到着のtarget対応効果は中央値−11.7ms、bootstrap 95%区間−19.6〜2.3msで、network/変換の短縮だけでは説明できない。
一方、browser frame提示は中央値−71.3ms（−83.7〜−24.2ms）、実際にcanvasを可視化した最初のYADIF描画は−71.3ms（−83.8〜−24.5ms）だった。
基準/修正版のcanvas中央値は296.3/244.3ms、p90は373.0/280.7msで、誤った標本が一つ前のGOPを選ばせ、Chromeに余分な映像を復号・破棄させることが体感遅延の原因だと確認した。
初回の計測hookは`drawArrays()`から戻った後のvisibility変更とrVFC callback登録順を扱えず、最初の可視描画を飛ばすことがあったため、callback中のmediaTimeを描画へ直接関連付けて全ブロックを取り直した。
修正版ではYADIF描画が既存`presented` eventより中央値3.5ms先で、初画を遅らせる独立したYADIF待ちは確認できなかった。
生値と除外走行は[probe標本の再検証](results/galaxy-probe-sample-revalidation.json)に保存した。
正しい byte / PTS の対応を保つ削除はsidecarより先に採用する。修正版は可視初画中央値で250msを下回ったが、p90は280.7msで安定250ms以下には未達である。

### 再生中に確認したTS再開位置の再利用

probeは未知の時刻をbyteへ変換するために必要だが、変換済みGOPについてはdemuxerが実際に通過したTS packetと、そのserviceのPAT/PMTを読める直前位置を確定できる。
診断版ではmedia fragmentへPAT/PMT安全位置を付け、playerのメモリ内だけに保持した。
後のseekで要求時刻以前かつ1秒以内の既知位置があれば、そのbyteから新しいSessionを開始し、PTS probeを省いた。
永続sidecarではなく、そのplayerが実際に確認した位置だけを再利用する方式である。

乃木坂工事中の同じ20地点を基準・再利用・再利用・基準の順で測ると、Galaxyの基準40回はprobe 40件、canvas中央値226.5ms、p95 278.4ms、250ms以下28/40だった。
再利用版40回はprobe 0件、中央値161.5ms、p95 220.5ms、250ms以下40/40だった。
Linuxも中央値179.5→104.7msだったが、p95は214.4→246.5msへ悪化した。
timelineを分離すると、早く届いた目的frameをfork固有`seeked`処理が隠す別競合がtailを作っており、目的frame保持を組み合わせた40回ではp95 178.9ms、最大180.4msとなった。

既知位置を要求時刻の直前まで使うとdecoderのrun-upが短すぎる可能性もあるため、0.5秒と0.1秒の最低leadを別に測った。
Galaxyの0.5秒版20回は中央値228.8ms、p95 307.9msで、前のGOPへ戻る利益はなかった。
0.1秒版40回は中央値175.1ms、p95 245.6ms、Linux40回は中央値113.5ms、p95 195.3msだった。
現在の素材では直前の安全位置と目的frame保持の組み合わせが最速だが、既知位置の密度、GOP間隔、decoderによって最適leadが変わる可能性がある。
固定leadを正式仕様へ増やす前に、異なる地点・素材で「直前位置が遅くなる条件」を特定する。

生値と追試は[Galaxy集計](results/galaxy-exact-restart-summary.json)と[Linux集計](results/linux-exact-restart-summary.json)に保存した。
TS demuxerが安全な再開位置を報告するcore変更は公開`feat/report-ts-restart-offsets`の`787c7ba`、それをseek policyへ使う変更は同branchを祖先にした公開`perf/reuse-observed-ts-restarts`の`ac4f879`へ分けた。
coreの公開APIは現在利用する`restartOffset`だけとし、診断版にあった未使用のGOP source byteは公開しない。
`restartOffset`だけを持つPTSなしPESが、直前のPTS付きmarkを隠す経路を回帰試験で再現した。
PTSとrestart位置を独立したmark列へ分け、値を持つPESだけが対応する事実を更新するようにした結果、再開同値性と先行PTSの両方を保った。

正式branch群を最新KonomiTVへ組み込み、Galaxy Chrome、LAN直結、body全画面、右パネルなし、単一タブで取り直した。
600秒と900秒をwarm-upした後の40 seekは追加probe 0件で、`seek-requested`から`seeked`後も残る可視canvas初画まで中央値159.1ms、p95 212.4ms、最大229.0msとなり、40/40が250ms以内だった。
長時間退行したYADIF presentation policyを除いた公開integration製品コードも、計測専用timing APIを含めないbuildで`video.currentTime`設定から同じ可視初画まで中央値159.7ms、p95 193.6ms、最大246.8msとなり、40/40が250ms以内だった。
同じKonomiTV、端末、画面条件、計測起点で`tsukumijima/main` `52a3db5`へ戻した基準は、中央値287.1ms、p95 349.1ms、最大410.2ms、250ms以内14/40だった。現在のintegrationは基準から中央値127.4ms（44.4%）、p95 155.5ms（44.5%）を短縮した。
正式候補timing版と公開integrationは計測起点とinstrumentationが異なるため、その差をMSE修正単独の効果とは扱わない。
正式候補の区間別中央値はRange headers待ち31.8ms、first byteからpicture jobs 24.6ms、最初のworker出力からstream先頭AU 29.7ms、append完了から`canplay`27.6msだった。
詳細と生値は[Galaxy正式候補とintegration](results/device-results.md#galaxyの正式候補と公開integration)を参照する。

PTSとrestart位置の独立管理、依存する再利用branch、fork固有のdiscontinuity reset接続まで祖先順にmergeし、長時間退行したpresentation policyを除いてintegrationを再構築した。
Galaxy Chrome、LAN直結、全画面、右パネルなし、単一タブ、60Hzで、既知の破損packetより後を600秒測るとrAFは59.998回/秒、入力video callbackは29.970回/秒、YADIFの`missed`と全resetは0だった。runtimeのplayerとYADIF JavaScriptは再構築したbranchの生成物とバイト一致する。[600秒A/Bと後片付け結果](results/galaxy-present-one-field-long-run-ab.json)を保存した。
同じ低負荷collectorで`tsukumijima/main` `52a3db5`も600秒測り直すと、YADIF生成field FPSは基準版59.939fps、integration 59.940fpsで、`missed`は両方0だった。この値はYADIFの`filtered` counterから求めており、WebGL canvas描画の直接計数ではない。[条件、計算式、証拠hash](results/galaxy-current-integration-vs-tsukumijima-main-steady-600s.json)を保存した。
同じbuildで180〜199秒と480〜499秒を交互に40回seekすると、持続表示される目的canvas初画まで中央値159.7ms、p90 181.6ms、p95 193.6ms、最大246.8msで、40/40が250ms以下だった。19/40は`seeking`中に到着したframeを保持した。[40回の生値と後片付け結果](results/galaxy-integration-without-present-seek-visible-40.json)を保存した。

### Linux Chromeの同一ホスト対照

EVO-X2、Ubuntu 26.04.1、Chrome 152.0.7977.64、59.96Hzで、同じKonomiTVとTSを同一ホストのLAN addressから開き、全画面、右パネルなし、単一タブで測った。
既知の正常区間を187.845秒から開始した120秒は、canvas 59.867fps、描画間隔p95 17.4ms、p99 17.7ms、40ms超2回、最大50.5msだった。rAFにも40ms超2回、最大50.0msがあり、YADIFは`late`が5、`missed`が2増え、全resetと入力discontinuityの増加は0だった。[120秒の生値](results/linux-integration-v2-steady-good-segment-120s.json)を保存した。

180〜199秒と480〜499秒を交互に測った40 seekは、持続表示される目的canvas初画まで中央値131.7ms、p95 195.4ms、最大196.2msで40/40が250ms以下だった。
180秒群は中央値147.6ms、480秒群は114.0msで、目的時刻より先への着地は0回だった。[40回の生値](results/linux-integration-v2-seek-visible-40.json)を保存した。
同一ホストの対照なのでLANクライアントの目標達成には数えないが、同じ地点差がWindowsより短い待ちで収まることと、integrationのLinux回帰がないことを示す。

### Windows Chromeの低電力条件

Lenovo IdeaPad Flex 5 14ARE05、Windows 11、AMD Radeon Graphics、Chrome 152.0.7977.65、60Hz、電源モード「最適な電力効率」で、同じKonomiTV、TS、LAN、全画面、右パネルなし、専用Chrome profileを使った。
120秒の定常再生はcanvas 59.719fps、40ms超8回、最大70.6msで、rAF自体にも40ms超3回、最大50.1msがあった。
YADIFは`late`が17、`missed`が2増え、全resetは0だった。
同じWindowsの旧integration 2走行は59.233 / 59.474fps、`late`増分80 / 52、1-field候補2走行は59.775 / 59.791fps、`late`増分16 / 15だった。この120秒比較では1-field policyが有利だったが、後述のGalaxy 600秒A/Bで長時間退行を確認したため、現在のintegrationからは外した。[120秒の生値](results/windows-integration-v2-steady-120s.json)を保存した。

180〜199秒と480〜499秒を交互に測った40 seekは、持続表示される目的canvas初画まで中央値252.7ms、p95 324.7ms、最大393.8msで、20/40が250msを超えた。
180秒群は中央値295.3msで20/20が250ms超、480秒群は中央値213.8msで20/20が250ms以内だった。
両群の区間中央値は`seek`→Range responseが50.3 / 57.5ms、first byte→first fragmentが107.5 / 108.9ms、first fragment→最初のappend完了が12.8 / 11.6msで、180秒群だけ`appended`→`playing`が115.6msとなった。480秒群は35.4msだった。

最初のappend完了時に`video.buffered`も読むと、180秒と181秒は目的時刻を含むが、その先が74 / 75msしかなく`readyState=1`と`seeking=true`だった。
buffer終端が目的時刻の565 / 568ms先まで伸びた後に`canplay`へ進んだ。
480秒と481秒は最初のappendで374 / 365ms先まで入り、そのbuffer範囲のまま31 / 34ms後に`canplay`へ進んだ。
したがってこの二群差はRange往復や最初のfragment生成ではなく、最初のfragmentが目的時刻後に持つ再生余裕と、Chromeが再開に要求する先読みが合わない場合の後続fragment待ちである。[40回の段階値](results/windows-integration-v2-seek-visible-timed-40.json)と[buffer範囲の4回確認](results/windows-integration-v2-seek-buffered-preflight-4.json)を保存した。

固定のseek leadを1.0秒から0.5秒へ変えた診断版は、同じ40地点で中央値252.7→246.0ms、p95 324.7→312.3ms、250ms超20→18回に留まり、180秒群の中央値は295.3→295.1msだった。
目的時刻より74ms先へ1回、374ms先へ1回着地したため、固定lead変更は速度効果が小さく正確性も壊す。この形は採用しない。[診断版40回](results/windows-integration-v2-lead-half-seek-visible-40.json)を保存した。
後続fragmentを先に作って待ちを移す方式も全体を短縮しないことは下記のGalaxy実験で確認済みである。

現行のin-memory restart indexが近い安全位置を取り逃している可能性も、180秒と480秒で直接確認した。
180秒では選択中のfragmentが179.573856秒から始まり、次のPAT/PMT安全位置は既知でもfragment開始が180.074356秒となるため、要求位置を越えない既定policyでは選べない。
480秒では479.873856秒から始まる安全位置を選べるため、現行indexがすでに利用している。
したがって180秒群では、indexを高密度化しても正確なseekのまま初回fragmentを近づけられない。
sidecar indexはcold seekのprobe削減には有効だが、このcadence位置の後続fragment待ちを単独では解消しない。[TS packet、restart位置、fragment時刻の対応](results/windows-restart-boundary-analysis.json)を保存した。

要求位置を越えないままWindowsの180秒群を短縮するには、Range応答と最初のfragment生成を短縮するか、目的時刻後のdecode余裕を現在より早く渡す必要がある。
要求位置から74ms後のGOPへ移るfast seekは別のoptionとしては評価できるが、既定の正確性policyを置き換えない。

修正版40 seekでは、first fragmentが要求時刻より前へ開く量と`appended`→`canplay`の相関がPearson 0.943、Spearman 0.879だった。
そこで、変換済みの後続fragmentから要求時刻以前で最も近いものだけをWorkerが渡せるか確認した。
乃木坂の実出力は約0.5005秒ごとにfragmentを生成し、600秒seekでは599.9939秒の先頭fragmentを152.0ms、600.4944秒の次fragmentを212.8msに生成した。
しかしproduction既定の`recoveryInterval=24`では、計測した600秒と900秒の両seekとも先頭だけが`randomAccess:true`で、後続fragmentはすべてdependentだった。

これはコード上も仕様通りである。
KonomiTVは`recoveryInterval`を指定せず、DPlayerも利用者optionをそのまま渡すため、WASMの既定24が使われる。
Sessionは先頭と24 GOPごとだけにrecovery pointを要求し、`Fragment.randomAccess`をIDR開始またはrecovery pointの場合だけtrueにする。
既定24とinterval 1のcore testは最新upstream `d5df08b`でどちらも成功した。
したがって先頭fragmentを捨て、後続fragmentだけをappendするWorker-only変更は、MediaCodecへ必要なdecoder stateを渡さず正しさを壊すため採用しない。
後続GOPを選ぶ実験は、選択GOP自体をrandom accessにする方法と、追加sample・byte量・変換時間・実decoderの復帰を先に評価する必要がある。
計測値は[fragmentのrandom-access性](results/galaxy-fragment-random-access.json)に保存した。

この上限を確かめるため、同じTSの16MiB区間でrecovery方式を比較した。
既定のIDR方式をinterval 24から1にすると、wall timeは平均0.730→0.865秒（+18.5%）、CPU timeは2.200→2.735秒（+24.3%）、出力は35,965,906→42,518,015 bytes（+18.2%）、video sampleは292→328になった。
一方、既存のnon-IDR recovery-point方式をinterval 1にすると追加cloneはなく、wall time 0.720秒、CPU time 2.190秒、33,907,475 bytes、290 samplesだった。

non-IDR recovery-pointを毎GOPへ入れ、seek後の先頭fragmentを意図的に捨てて第2fragmentからMediaCodecを開始する診断版をGalaxyでB-F-F-B比較した。
第2fragmentが要求時刻以前だった5地点10走行では、`appended`→`canplay`中央値が101.4→33.3msとなり、手前の約0.5秒をChromeが復号・破棄する時間を約68ms削減できることを確認した。
しかし第2fragmentを生成するまでappendがtarget対応中央値69.8ms遅れ、可視canvasのtarget対応差は中央値+5.7ms、平均+1.3msで改善しなかった。
さらに10地点中5地点は第2fragmentが要求時刻を0.294〜0.494秒越えた。
したがって「先に古いGOPを変換し、後続recovery fragmentを待つ」方式は棄却する。
この結果は、要求時刻以前に現在より近いRAPが実在する地点なら、そのbyte位置を変換前に得ることでdecoder discardを待ち時間なしで減らせる可能性を示す。
ただし上記のWindows 180秒地点には、その条件を満たす次のfragmentが存在しない。
詳細は[recovery fragment選択実験](results/galaxy-recovery-fragment-selection.json)に保存した。

## サーバーエンコードHLS経路

録画映像がMPEG-2 TSのOriginal直接再生条件を満たさない場合と、利用者が通常画質を選んだ場合は、DPlayerのhls.js経路を使う。
KonomiTVは録画TSの入力位置を解決してFFmpegを起動し、MPEG-TS形式のHLS segmentを生成する。
ブラウザー側はbuffer外へのseekで既存bufferをflushし、playlistを再取得して対象segmentを読み込む。

現在の[`VideoStream.getSegment()`](https://github.com/tsukumijima/KonomiTV/blob/e92fba8bb219589c8e4ada9609ed4a9d91b33c00/server/app/streams/VideoStream.py#L753-L859)は、対象segmentの`encoded_segment_ts_future`が完了するまでHTTP応答を返さない。
[`VideoEncodingTask`](https://github.com/tsukumijima/KonomiTV/blob/e92fba8bb219589c8e4ada9609ed4a9d91b33c00/server/app/streams/VideoEncodingTask.py#L1180-L1240)は、予定境界へ到達した後のrandom-access frameでsegmentを確定し、その時点でfutureへ全byte列を設定する。
乃木坂工事中fixtureでは仮想segment長が約6.006秒で、1080p60のFFmpeg出力はH.264、HEVCともGOP長180、約3秒だった。

Galaxy Chrome、LAN直結、全画面で、通常モードのH.264とHEVC 1080p60を各600秒測った。
主条件はrVFCを登録せず、開始・終了時だけ`getVideoPlaybackQuality()`、media time、映像・音声decode byteを読む。
認証と再生設定はwatch pageの初回実行前に投入し、各走行のサーバーログで要求品質のencoder sessionが1つだけであることを確認した。

| 出力 | 受理frame | `droppedVideoFrames` | media time | 音声decode |
| --- | ---: | ---: | ---: | ---: |
| H.264 1080p60 | 35,964 | 2 | 599.999秒 | 18,834,432 byte |
| HEVC 1080p60 | 35,966 | 0 | 600.001秒 | 14,601,318 byte |

HEVCのAPI要求は`1080p-60fps-hevc-10bit`だったが、今回のソフトウェアFFmpegが実際に生成した映像は`libx265 Main`、`yuv420p`の8bitだった。
したがって、この値は10bit HEVCの結果には数えない。

H.264は60000/1001fpsの理論frame数を受理しているため、サーバー出力のframe数不足ではない。
現行Chromiumでは、[`VideoRendererImpl`](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/media/renderers/video_renderer_impl.cc)が表示選択時のdrop数を統計へ加算し、[`VideoRendererAlgorithm`](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/media/filters/video_renderer_algorithm.cc)がdecoded frameのうち表示に選ばれず取り除かれたframeに加え、時刻が逆行したframeや1ms未満の間隔でqueueへ入ったframeもdropとして数える。
この計測だけでは両者を分離できない。
HEVCは同条件でdrop 0であり、計測中のThermal Statusも0だったため、60Hz表示や端末のthermal throttlingだけではH.264の2件を説明できない。

H.264のdrop発生位置を250ms周期で記録する別の600秒走行では、35,965 frame中1件をdropした。
発生時のmedia timeは950.070秒、`readyState=4`、buffer終端は981.464秒で、約31.4秒先までbuffer済みだった。
最寄りの6.006秒HLS segment境界から約1.36秒離れ、前後2秒にHLS errorはなかったため、この1件はbuffer枯渇やsegment切替では説明できない。

drop位置を含むsequence 157を、同じfixture、KonomiTV commit、エンコード設定で後のセッションから再生成し、サーバーMPEG-TSとhls.jsの`BUFFER_APPENDING`直前のvideo fMP4を保存した。
元のdrop走行のbyte列そのものではないため、同じsequenceを再生成した証拠として扱う。
TSとfMP4はいずれも440 frameで、隣接PTSは1501 tickが220件、1502 tickが219件、重複・逆行・1ms未満間隔は0件だった。
keyframe位置も一致し、FFmpegの厳格decodeで警告はなかった。
既知区間ではChromiumの逆行・重複・近接timestampによるenqueue drop条件が成立せず、decoded frameの表示期限超過を優先して調べる。

H.264のprofileとbitrateを、coded 1440×1080、SAR 4:3、表示1920×1080、60000/1001fps、GOP 180、AAC 256Kbpsのまま分けて各600秒測った。
既定のHigh・9.5/13Mbpsは開始側2/35,964 drop、終了側1/35,964 drop、Main・9.5/13Mbpsは2/35,964 dropだった。
High・3.5/5.2Mbpsは0/35,964 drop、Main・3.5/5.2Mbpsは1/35,964 dropだった。
通常bitrateの3走行合計は5/107,892、低bitrateの2走行合計は1/71,928で、低bitrate側に少ない傾向はあるが、事象数が少ないため効果は確定できない。
HighからMainへの変更単独では改善を確認できなかった。
低bitrate条件は原因切り分け用であり、画質を評価していないため製品設定の候補にはしない。

毎frameのrVFC情報を保持する診断走行では、H.264が2 drop、HEVCが1 dropだった。
ただしH.264はcallback 35,671回に対して`presentedFrames`が35,963進み、HEVCもcallback 35,731回に対して35,964進んだ。
したがってrVFC callback間隔の空きは、映像frameのdropと1対1には対応しない。
[主条件、診断条件、発生位置、全生値](results/galaxy-recorded-hls-1080p60-long-comparison.json)、[H.264 profile・bitrate比較](results/galaxy-recorded-hls-h264-profile-bitrate-comparison.json)、[drop区間のtimestamp検査](results/galaxy-recorded-hls-h264-drop-segment-timestamps.json)を保存した。

以前の8画質×2codecの5秒測定とHLSシーク測定は、watch pageを空の設定で一度起動してから要求画質へ切り替えていた。
初期既定の1080pと要求画質のencoder sessionが並行してサーバー負荷を混ぜたため、絶対値として採用しない。
測定器は設定を初回実行前に投入し、期待するcollector種別とhash、単一encoder sessionを照合するよう修正した。
他の14画質と既定HLSシークの絶対値はこの固定条件で再測定する。

コード上は、`VideoStream.getSegment()`が対象segmentの`encoded_segment_ts_future`完了までHTTP応答を返さず、約6秒の仮想segmentをrandom-access frameで確定してから全byte列を渡す。
HLSシークの支配候補はこのsegment完成待ちだが、修正後の単一encoder条件で段階別絶対値を取り直すまで効果量は確定しない。

## HTTP Range とファイル I/O

配信は [VideosRouter.py:706](https://github.com/tsukumijima/KonomiTV/blob/e92fba8bb219589c8e4ada9609ed4a9d91b33c00/server/app/routers/VideosRouter.py#L706) の `VideoDownloadAPI`。
各 request で `GetRecordedProgram` の DB query、`anyio.Path.is_file()`、`FileResponse` の stat を経る。
TS 解析、時間指定の探索、transcode は行わない。

[Starlette 1.6.0 responses.py:296](https://github.com/Kludex/starlette/blob/1.6.0/starlette/responses.py#L296) では `Accept-Ranges: bytes` を付け、単一 Range は `206 Partial Content`、`Content-Range`、その区間の `Content-Length` で返す。
`open_file('rb') → seek(start) → read(min(64 KiB, remaining))` で読み、各 response でファイルを開き直して閉じる。
HTTP の Range 粒度は byte 単位であり、64 KiB は ASGI body の chunk size である。
128 KiB probe は通常2 body chunkであり、2 HTTP requestではない。
Range より前をアプリケーションが読み戻す処理や、TS 固有の prefetch はない。
OS、Python buffered I/O、SMB client、NAS の読み込み粒度はこの値とは別である。

録画TSだけ`FileResponse.chunk_size`を64 / 256 / 512 KiB / 1 MiBへ変え、同じclientを使って全画面・LAN直結で順序を反転した比較を行った。
Galaxyの256 KiB版は64 KiB比の対応付き可視初画中央値が180秒群−7.0ms、480秒群−15.4msだったが、512 KiB版は+3.5ms / −5.1ms、1 MiB版は−2.3ms / −6.6msで、sizeに対して単調ではなかった。
Windowsで64 KiBと256 KiBを各40 seekへ増やすと、対応付き可視初画差は+1.7ms / −2.4ms、`first-byte`→`first-fragment`差は+1.2ms / +0.8msとなった。
したがってASGI body chunk拡大を共通のシーク改善として採用せず、branchも作らない。
別のtransportやstorageでchunk境界が安定したボトルネックとして再現した場合だけ再検討する。
[chunk size sweepの集計](results/file-response-chunk-size-analysis.json)と生データを保存した。

初期計測でread-only mountした録画領域はCIFS、`rsize=4 MiB`、`cache=strict`、`actimeo=1`だった。
KonomiTVと録画TSが同じPCにある主ユースケースとは異なるため、このCIFS経由の絶対時間は主結果から外した。
主条件では対象TSをサーバー側ローカルNVMeへコピーし、コピー元とSHA-256が一致することを確認して使う。
SMB 上なら open/stat/read の往復と cache miss が追加候補になるが、64 KiB の Python read がそのまま64 KiBの SMB requestになるとは限らない。
帯域十分という前提でも、直列の probe、各 request の DB/stat/open、probe 全体の到着待ちは残る。

[source.ts:41](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/source.ts#L41) は本体を `Range: bytes=offset-`、`cache:'no-store'` で取得し、`206` と開始 byte を検査する。
`Accept-Ranges` の表記だけには依存しない。
Worker は変換と並行して入力を先読みし、未変換入力が32 MiBに達すると request を abort、8 MiB以下へ減ると次の byteから再開する。
このため不要な先読みはあり得るが、常時小さい Range を連発する設計ではない。

### 切断後も続く FileResponse の処理

低電力Windowsの実KonomiTVでは、終端なしRangeを3 MiBで中断する操作を200回繰り返すと、3 MiB受信までの時間が最初の20回の中央値76.1msから最後の20回の1,083.1msへ悪化した。
同じ位置・受信量で3 MiBの有限Rangeを読み切る対照は38.6→35.0msだった。両条件とも新しいbackendで開始し、WindowsのNodeからbackendへ直接接続してChrome、Akebi、変換、MSE、decoderを除外した。

中断条件では、終了10秒後までのbackend論理読み込み増分が84.13GBとなり、client終了後の10秒間だけでも6.23GB増えた。
有限Rangeの対照は0.629GBで、終了後の追加読み込みは0だった。これはプロセスの論理I/Oであり、物理ディスクやネットワーク転送量ではない。[同条件の全400要求・集計方法・hash・終了確認](results/windows-range-abort-bounded-200.json)を公開している。

Starlette 1.6.0 と Uvicorn 0.52.4（httptools、ASGI 2.3）では、client が Range を中断しても、`FileResponse` が要求終端までファイルを読み続けることを再現した。
16 MiB の合成ファイルを実際の localhost HTTP で配信し、client が3 MiBを受信したところで接続を閉じた。

| 応答の条件 | client が受信した量 | FileResponse が ASGI に渡した総量 |
| --- | ---: | ---: |
| 終端なし Range、3 MiBで切断 | 3 MiB | 16 MiB（ファイル末尾まで） |
| 3 MiBの有限Range、最後まで受信 | 3 MiB | 3 MiB |
| 4 MiBの有限Range、3 MiBで切断 | 3 MiB | 4 MiB（要求終端まで） |
| 終端なし Range、切断監視を加えた診断用実装 | 3 MiB | 3 MiB + 64 KiB |

表の右列は、実際の `FileResponse` が `send()` に渡したbodyの合計であり、clientへ届いた量や物理ディスク読み込み量ではない。
各 `send()` 後に時刻待ちなしでevent loopへ制御を戻し、実際のUvicornとclientに切断を処理させた。[再現コード](scripts/reproduce-file-response-disconnect.py)と[全条件・生値・終了確認](results/file-response-disconnect-http-repro.json)を公開している。

原因は、[FileResponse](https://github.com/Kludex/starlette/blob/1.6.0/starlette/responses.py)が `http.disconnect` を監視せず、[Uvicornのhttptools実装](https://github.com/encode/uvicorn/blob/0.52.4/uvicorn/protocols/http/httptools_impl.py)が切断後の `send()` を例外なしで終了する組合せである。
このため読み込みループは切断を検出できず、`bytes=offset-` なら末尾まで進む。[Starlette #1301](https://github.com/Kludex/starlette/issues/1301)にも同じ問題の報告がある。

有限Rangeは中断後に残る処理量を制限するが、切断処理自体の修正にはならない。
サーバー側の切断監視は不要な処理を止める候補として分けて評価する。診断用実装はbackground task、pathsend、multipart、WebSocketを検証しておらず、正式な修正ではない。

この試験はHTTP配信処理の因果関係を示すもので、表示停止の全件がこの原因であることや、修正後のシーク時間を示すものではない。
playerを通したシーク復帰への効果は、別途検証する。

[Starlette候補 `d70956b`](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect) は、ASGI 2.4より前のHTTP streamingで切断を監視し、ファイルのcloseをキャンセルから保護する。
HEAD、pathsend、WebSocket、ASGI 2.4以降の送信経路は維持し、正常終了時にも監視taskを終了する。

候補自体を同じHTTP再現に使うと、診断用の外側listenerなしで、FileResponseがASGIの`send()`へ渡した総量は、終端なしRangeと4 MiB有限Rangeの両方で3 MiB + 64 KiBに留まった。
Starlette最新main `39fd0ff` に対する切断の12試験は修正前に失敗し、候補では既存試験を含む1,219件が成功、2件が期待された失敗となった。[候補の実HTTP結果・source commit・試験条件](results/file-response-disconnect-starlette-fix.json)を保存している。

Windowsの隔離KonomiTVで`responses.py`だけを候補へ置き換え、同じ位置・受信量・待ち間隔の200要求を再測定した。
終端なしRangeを途中で切断する条件は変えず、player側の有限Range化も加えていない。

| 条件 | 3 MiB受信時間・最初20回の中央値 | 最後20回の中央値 | 要求終了後10秒間の追加論理読み込み |
| --- | ---: | ---: | ---: |
| Starlette修正前 | 76.1ms | 1,083.1ms | 6.23GB |
| Starlette候補 `d70956b` | 26.1ms | 24.8ms | 0 byte |

この対照では、サーバー側の修正だけで切断後の読み込みと反復による劣化を抑えた。
各版1走行の順序固定比較であり、通常シークの改善量や致命的停止率は示さない。
試験後のプロセス停止と元ファイルへの復元を確認した。[全200要求・比較元・ファイルhash・終了確認](results/windows-range-abort-starlette-fix-200.json)を保存している。

同じStarlette候補と実Chromeを使い、Windowsの隔離KonomiTVとローカルTSだけで1時間の反復シーク試験も行った。
Chrome、page、player、Worker、decoder、MSE、YADIFを1,000要求ごとに作り直した5 sessionで、4,738回すべてが2秒以内に安定復帰し、致命的な表示停止は0件だった。
安定復帰時間は中央値565.7ms、p95 779.715ms、最大987.6msだった。
これは8回連続描画と100ms以上の持続まで待つ致命的停止検出器の値で、通常シークの初回描画200ms目標とは比較しない。
最後のsessionは時間上限で終了したため、要求5,000回のうち完了した4,738回だけを観測済みの復帰として数える。

この走行には同条件のStarlette修正前がなく、候補によるシーク完了時間や停止頻度の改善量は示さない。
選択したシーク区間は既知の破損packetを横切らないため、異常TSの1時間条件にも使わない。
全sessionの終了処理、Chromeとローカルruntimeの停止、Starlette実行ファイルの復元を確認した。[build、測定条件、各blockのhash、終了確認](results/windows-starlette-candidate-one-hour-seek.json)を保存している。

## TS 解析、変換、音声待ち

[worker.ts:530](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/worker.ts#L530) は seek 後に新しい `Transcoder` / Rust `Session` を作る。
timeline origin、指定 service、選択 audio PID、dual mono の選択は引き継ぐ。
WASM module と picture Worker pool は load 中に再利用される。
PAT / PMT、PES、sequence header、AAC config、GOP 途中状態は新しい session で再取得する。
指定 service ID があっても PMT の PID 表が不要になるわけではない。

初回 fragment の前に、次の条件を満たす必要がある。

| 条件 | 根拠と影響 |
| --- | --- |
| TS 同期、PAT / PMT | `MpegTsAvDemuxer` が取り直す。probe 用 PTS scan とは別処理 |
| PES と MPEG-2 sequence / GOP | 部分的な PES / picture からすぐ変換できるわけではない。新 session には以前の sequence prefix がない |
| 完成した GOP | [gop_stream.rs:246](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/crates/mpeg2toh264/src/mpeg2/gop_stream.rs#L246) は次の GOP header 等を見て前の GOP を確定する |
| AAC がある場合の追加 GOP | [session.rs:1033](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/crates/mpeg2toh264/src/session.rs#L1033) は通常時1 GOPを保留する。最初を出すには完成 GOP が2個必要で、通常は3つ目の GOP 境界まで読む |
| AAC config と必要フレーム数 | `pending_audio.len() < wanted` でも出力しない。映像 GOP の時間範囲を音声が満たすまで待つ |
| 変換対象 GOP の処理完了 | `Transcoder.push()` はその入力 chunk から処理可能な仕事をまとめて返す。最初の AU ができただけでは MSE へ渡らない |

GOP 長が0.5秒なら、2個の完成 GOP は約1秒分の素材を読むという意味である。
**1秒の実時間を必ず待つという意味ではない。**
録画は実時間より速く読めるため、所要時間は必要 byte数、配信応答、TS parse、変換速度に依存する。
I-picture の位置が既知でも、GOP全体の収集とAAC条件は残る。

追加GOP保留が実際の体感遅延を支配するか確かめるため、完成GOPに必要なAAC frame数が揃った時点で出力する候補を作った。
回帰試験は、後続GOPがなくても映像と音声の両`traf`を持つfragmentを出せることを確認し、現行コードでは失敗、候補では成功した。
乃木坂fixtureを64KiBずつ渡した単体計測では、180秒地点の初回fragmentまでの入力が2,228,224→1,703,936 bytes、480秒地点が1,900,544→1,572,864 bytesとなった。
両版の先頭3 fragmentはbyte列、時刻、sample数が一致した。

一方、全画面・LAN直結のB-F-F-B実機比較では短縮しなかった。
Galaxyの可視初画中央値は180秒群が162.7→179.2ms、480秒群が150.7→164.7ms、`first-byte`→`first-fragment`中央値も80.3→83.4ms、75.0→84.1msだった。
Windowsの可視初画中央値も180秒群が304.3→328.5ms、480秒群が222.4→265.1msで、同区間のfragment生成は116.4→124.5ms、116.0→120.8msだった。
入力byte数は減るがChromeへ届く初回fragmentと可視初画を短縮しないため、この変更は採用しない。
[単体計測と実機A/Bの集計](results/completed-gop-hold-analysis.json)および同JSONから参照する8ブロックの生データを保存した。

初期状態は IDR待ちで、[transcode.rs:582](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/crates/mpeg2toh264/src/transcode.rs#L582) が最初の利用可能な I-picture を H.264 IDR にする。
それ以前の P-pictureや参照が揃わない B-pictureは落とし、timeline 側も同じ picture を除外する。
open GOP の失われる先行表示区間は初期IDRの保持などで扱い、参照 cloneも生成する。
初期IDRは画素再構築を含むため、通常の係数領域のpicture変換より重い。
Galaxyの3地点では、最初のpicture jobsが揃ってから任意workerの最初の出力までは4.4〜7.2msだった一方、stream先頭のIDR access unitまでは33.0〜40.0ms、batch完了までは33.7〜53.7msだった。
同じ乃木坂工事中のWASM単体測定でもjob 0は33.260ms、後続12 jobsは3.241〜14.856msで、CPU profileにはIDR固有のluma/chroma予測と再構築が現れた。
したがって、worker pool全体が遅いのではなく、並列分割されない最初のIDR jobが変換側のcritical pathである。
生値は[picture-startup-stages.json](results/picture-startup-stages.json)に保存した。
既定の24 GOPごとの recovery interval は連続再生中の方針であり、seek後に24 GOP待つ設定ではない。
「元TSにH.264 IDRが現れるまで待つ」という処理でもない。

fMP4 は新しい init segment の `avcC` に SPS / PPSを格納し、`tfdt` と composition offset 等で timeline を再構築する。
AAC は通常再エンコードせず、ADTSからフレームを取り出して同じ fragmentへ格納する。
音声の AAC frame境界、PTS差、1024 samples単位の配置を維持するため、映像だけ先にできても `take_ready()` が止める場合がある。
48 kHzのAAC 1 frameは約21.33 msだが、その分の実時間待機を置くコードではない。
音声欠落には短い区間のフレーム複製、中程度の無音補完、長い区間のgap処理があり、seekごとに必ず固定長のsilenceを投入する構成ではない。

## MSE の待ちと再現できた競合

[mse.ts:343](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/mse.ts#L343) は範囲外 seekでキューとrandom access記録を消し、`remove(0, Infinity)` を予約する。
同じ MediaSource / SourceBufferを再利用する。
このseek経路に `SourceBuffer.abort()`、`timestampOffset`、`appendWindowStart/End` の設定はない。
codec MIMEが変わった場合だけ `changeType()` し、新しいinit segmentを投入する。

SourceBuffer側の順序は次の通り。

```text
古い append/remove が実行中なら updateend
  → remove(0, Infinity) → updateend
  → init appendBuffer → updateend
  → media appendBuffer → updateend
  → A/V の有効bufferと目的時刻を満たす → browser decode / presentation
```

ただし `Playback.seek()` は `sink.reset()` 完了を await せず、直後にPTS probeを開始する。
削除と探索はすでに重なっている。
変換ループは `sink.ready()` を待つため、古いbufferやqueueの状態によって後段の並行度は制限される。
各 `updateend` は復号完了や画面表示完了を意味しない。
`SourceBuffer.buffered` は音声と映像のintersectionなので、media投入直後でも再生可能とは限らない。

目安となる依存関係は以下で、全段階を単純に足すべきではない。

```text
初画まで ≈ UI/event配送
          + max(古いMSE処理とclear,
                PTS probe + 本体取得とstartup解析/変換)
          + init/media投入の残り + decode + presentation
```

`queueHighWaterMark=32 MiB`、`maxAheadSeconds=8`、`keepBehindSeconds=10` は上限や保持方針であり、再開前にその量を必ず貯める閾値ではない。
media queueは2 fragmentでも停止する。
後方bufferの通常evictionはquota不足時にRAP境界を考慮して行い、10秒を超えた瞬間に常に削除するわけではない。
`keepBehindSeconds` の値だけから「10秒戻れば確実にbuffer内」とは判断できない。

### 古い updateend が新しい init segment を消す

`reset()` はqueueを空にするが、進行中appendを表す `#operation` を残す。
新しいinit/mediaがqueueへ入った後で古いappendの `updateend` が来ると、[mse.ts:473](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/mse.ts#L473) が**現在のqueue先頭**を `shift()` する。
完了した古いappendと、その時点のqueue先頭が同じかを確認していない。

実際のTypeScriptをtranspileし、公開 `open/push/reset` と模擬SourceBufferの完了イベントだけで試験した。
出力は [mse-race.jsonl](results/mse-race.jsonl)。

| 条件 | 実際の呼び出し順 |
| --- | --- |
| 対照: 古いappend完了後にreset | old init → old media → remove → **new init** → new media |
| 競合: 古いappend未完了でreset、新queue到着後に完了 | old init → old media → remove → **new mediaだけ** |

これはSourceBufferの実際の処理時間を測る試験ではなく、許されるイベント順でqueue管理が壊れることの再現である。
Linux Headless Chrome 152と乃木坂工事中の同じ8地点で、通常seekを修正前後に測った。
`seek-requested`から最初の提示frameまでは修正前平均251.4ms、修正後平均250.1msで、差は-1.2msだった。
地点ごとの差は-104.5〜+123.0msで、decoder提示の変動より十分に小さい。
通常seekの短縮効果は測定できなかった。

最初のseekのmedia `appendBuffer()`開始時に別時刻を設定する強制試験も8組ずつ行った。
ブラウザーが2回目の`seeking`を受理した走行は修正前4組、修正後6組だった。
旧appendの完了前にresetへ入った走行はあったが、新init/mediaの生成は旧`updateend`より後で、模擬試験の「新initがqueueへ入ってから旧`updateend`」という条件には到達しなかった。
受理された走行は修正前4/4、修正後5/6でframe提示まで進み、修正後の1走行は新mediaの`updateend`後も5秒以内にframeが提示されなかった。
このstallはqueue先頭喪失とは異なる順序で、次の通常走行では再現しなかった。
したがって、実ブラウザーでの発生頻度とstall削減量は未立証である。
集計値は [mse-reset-browser-results.json](results/mse-reset-browser-results.json) に保存した。

initを失ったとき同一codecの再利用で表面化しないか、エラーか長いstallになるかも未測定である。
通常シーク遅延の最大要因とは断定しない。
修正はMSE ownerで進行中operationの対象と世代を保持し、古い完了が新queueを取り除かないようにするのが基本となる。
`abort()`追加だけではイベント順とclear状態の整合性を解決したことにならない。

## Decoder とデインターレース

新しいsessionの最初の利用可能GOPはIDRを含むため、「non-IDRのまま先へ送り、次の周期IDRまでdecoderが待つ」を通常経路の説明には使えない。
一方、初回fragmentが目的時刻より前に始まれば、そのIDRから目的時刻までの復号は必要になる。
MSEの `#startAtMedia()` はbuffer先頭を通知するが、player側は `currentTime` がその値より前の場合にだけ前進させる。
buffer先頭へ無条件に巻き戻しているわけではない。
先頭が目的時刻を越えた場合は前進補正になり、精度の問題として別に記録すべきである。

AndroidのMediaCodecには、非連続入力後の適切なkey frame境界、flush後のcodec-specific data等の条件がある。
ただしJavaScriptから `MediaCodec.flush()` を直接呼ぶコードはなく、Chromeがflushと再設定のどちらを選ぶかはブラウザ内部の判断である。
「Androidでは毎回reconfigureしている」「必ず何枚追加で待つ」とは本コードから確定できない。
[Android MediaCodec API](https://developer.android.com/reference/android/media/MediaCodec) と [MSE seeking仕様](https://www.w3.org/TR/media-source-2/#mediasource-seeking) を参照。

MPEG-2のinterlacing情報からH.264のMBAFF/field表現等を作る。
ハードウェアdecoder、field sample、参照画像、解像度やcodec config変更に対するAndroid側の復帰速度は実測対象である。
画面に見えるフレームについては `requestVideoFrameCallback` の `mediaTime`、`presentedFrames`、`processingDuration`、`expectedDisplayTime` を記録する。
`processingDuration` は対応する圧縮frameをdecoderに渡してから提示可能になるまでの時間で、networkやMSE全体の時間ではない。
rVFC自体もrawなdecode-complete通知ではなく提示に結び付くcallbackである。[web.dev の説明](https://web.dev/articles/requestvideoframecallback-rvfc)

YADIFのhistoryはprev/current/nextの3 decoded frames。
[deinterlace.ts:1361](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/yadif/src/deinterlace.ts#L1361) は1枚しかないとき同じframeを3役に使い、2枚のときも不足側を複製する。
3枚が揃うまで初画を全面的に止める処理ではない。
periodが未確定ならcanvasへ直接描画する経路も既存である。
したがって「最初の1〜2 frameだけ簡易処理で出す」は方向性としてすでに実装されている。

doubleRateの定常処理では2 fieldを出力queueへ入れ、初回deadlineに約1 decoded-frame周期の余裕を持たせる。
middle frameを使うYADIF本体にも1 frame相当の時間関係があるが、これらをそのまま初画の固定待ちとして合算しない。
新実装のqueue容量5 / output pool6は、5 field満杯になるまで表示しないという意味ではない。
autoFilmはhistoryがある時点で解析を始め、cadenceが確定するまではYADIFで表示する。
IVTC lock完了を待って映像全体を隠す構成ではない。

依存`52a3db5e`の`seeked` handlerはhistoryを消しcanvasを隠してvideoを見せる。
Linux Chromeの反復timelineでは、目的frameのrVFCが`seeking=true`の64.9〜65.7msに届いた2走行とも、直後の`seeked`（67.4〜68.8ms）が表示済みcanvasを隠し、次の目的frameが213.7〜214.7msに来るまで約149ms待ち直した。
目的時刻近傍かつ現在のbuffered範囲内のframeをseek先として記憶し、`seeked`で表示済みcanvasを消さない候補では、同じ早着が起きた5/5走行でcanvasを維持した。
既存playerの`presented` markは`seeking=false`後のframeだけを数えるため、修正版の早着frameより平均156.2ms遅かった。
可視初画は「目的frameのcanvas描画が`seeked`後もvisibleであり続ける最初の時刻」として別に測る必要がある。

exact restartとqueue回復候補を共通条件にした修正前後の全画面比較では、Linuxは40回の平均117.9→105.0ms、中央値104.7→97.2ms、p95 246.5→178.9ms、最大280.0→180.4msとなり、250ms以下は38/40→40/40だった。
Galaxyは再生中rAF 59.88Hzで、40回の平均168.1→157.7ms、中央値161.5→156.0ms、p95 220.5→193.2ms、最大243.1→212.8ms、250ms以下40/40だった。
Galaxyの修正版40回では早着条件自体は発生していないため、同端末では退行なしの証拠に留める。
生値と集計は[seek先frame保持の比較](results/exact-restart-seek-frame-summary.json)に保存した。

PCよりAndroidで増え得る区間は、WASM変換と初期IDR生成、MediaCodec復帰、video→WebGL texture upload、film解析のGPU readback、rVFC/rAFのmain thread待ちである。
PTS probe回数やAACのGOP保持条件自体は同じコードである。
Wi-FiのRTTとサーバー側I/Oは、decoderやGPU待ちと分けて記録する。

### Android Chromiumとcanvas opacity

GalaxyでYADIF出力が約30fpsへ落ち、canvasへ`opacity: 0.999`を設定した後に約60fpsへ戻る走行を観測した。
この走行だけから「不透明なcanvasがvideo callbackを約15Hzへ抑制した」と説明していたが、追加計測はその説明を支持しなかった。

生成時から不透明な変更前bundleを前景タブでクリーン起動すると、30秒走行はvideo rVFC 29.966Hz、document rAF 59.999Hz、YADIF出力57.09〜60.31fps、`late`増分3だった。
別の12秒走行もrVFC 29.994Hz、rAF 59.988Hz、YADIF出力59.87〜60.11fps、`late`増分0だった。
生成時から`opacity: 0.999999`にした走行は18秒後に60.095fpsだったが、不透明版も同じ水準なので改善効果を示さない。
実行中にopacityを切り替えると数秒遅れて約60fpsと約30fpsが入れ替わることがあったが、rVFCは約30Hz、rAFは約60Hzのままだった。
この遅延した状態遷移を即時の変更効果として扱うことはできない。
数値は[追加計測データ](results/galaxy-canvas-opacity.json)に保存した。

Chromiumコードには完全被覆を扱う経路がある。
[OcclusionTracker](https://chromium.googlesource.com/chromium/src/+/HEAD/cc/trees/occlusion_tracker.cc)は描画opacityが1未満のlayerを外側のocclusionへ加えず、[LayerImpl](https://chromium.googlesource.com/chromium/src/+/HEAD/cc/layers/layer_impl.cc)は表示領域が完全にoccludeされると`WillDraw()`をfalseにする。
[SurfaceLayerImpl](https://chromium.googlesource.com/chromium/src/+/HEAD/cc/layers/surface_layer_impl.cc)はこの状態をvideo surfaceのsubmission callbackへ渡し、[VideoFrameSubmitter](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/renderer/platform/graphics/video_frame_submitter.cc)は不可視surfaceのframe提出を止める。

しかし、この経路はrVFC抑制までを意味しない。
[offscreen rVFC対応CL](https://chromium.googlesource.com/chromium/src/+/4e43ae23f2cdd1fcb81c5da5984fc4cf0b674544)はcanvasやWebGLの利用者向けにBeginFrameを強制する処理を追加しており、現在の`VideoFrameSubmitter::IsDrivingFrameUpdates()`も`force_begin_frames`なら不可視surfaceで更新を続ける。
[VideoFrameCompositor](https://chromium.googlesource.com/chromium/src/+/HEAD/third_party/blink/renderer/platform/media/video_frame_compositor.cc)はWebGLなどの外部consumerがframeを取得した場合、そのframeをrender済みとして扱う。
YADIFは各rVFCでvideoをWebGL textureへ取り込むため、今回の実測どおりrVFCは不透明条件でも約30Hzを維持できる。
DOM canvasの完全被覆からMediaCodecを15Hzへ抑制する因果経路は確定できず、現在のChromiumコードと追加実測はむしろその説明を否定する。

約30fps状態ではYADIFの`late`が毎秒約30増えた。
これはvideo callback数の半減ではなく、2つのfieldの片方をpresentation queueが捨てたことを示す。
フォーク側には、rVFCとrAFの位相がずれた起動時にも最初のfieldを保持する修正`d4ccb98`がすでにあり、クリーンな不透明版2走行はこの修正を含んでいた。
opacity変更後の遅延した30fps遷移は残るため、位相、queue deadline、表示状態遷移を直接記録する回帰試験は追加できる。

`opacity: 0.999`の実験結果は本調査リポジトリに保存し、コードbranchは誤取り込み防止のため削除した。
`0.999`という値に固有の意味はなく、Chromiumの`opacity < 1`分岐へ入れるために選んだだけである。
クリーンな変更前対照で問題を再現できない以上、表示合成を常時変更する修正は採用できない。
原因に近い対策はYADIFのfield schedulingとvisibility遷移の再現試験であり、Chromiumへの変更案を出す根拠は現時点でない。

### Android seek後のYADIF queue飽和

最新KonomiTV `e92fba8`と依存`52a3db5`、Galaxy Chrome 151、表示60Hz、乃木坂工事中の540秒と900秒を交互にseekする条件でYADIF queue飽和を調べた。
タブ数を記録していなかった旧測定では、1.8秒後もYADIF出力が10fps未満、または`late`が30超増えた走行を30回中8回確認したが、この発生率は主結果から外す。

停止時もYADIFのrAF callbackは1.8秒に77〜110回呼ばれ、`startLoop`は既存loopを認識し、`stopLoop`は呼ばれていなかった。
したがってloop消失ではない。
filter済みfieldの表示予定は正常時に先頭約18ms、末尾約35〜52ms先だったが、停止時は末尾が最大351.9ms先へ伸びた。
表示可能になる前に6枚のoutput poolが埋まり、`#nextOutputSlot()`と`#filter()`が最古のfieldを`late`として交換する一方、次の時刻はqueue末尾からさらに未来へ連鎖するため、canvasへ出すfieldがほぼなくなっていた。

`otya128/main`の現行実装には、queueが5枚に達した時点でqueueを空にし、次のrVFC時刻へ再アンカーする処理がある。
フォーク版にも以前は同じ処理があったが、個別のlate破棄へ変更した際に`queueResetted`が互換用の常時0カウンターとなった。
Android seek後の先行callbackでは、個別破棄だけでは未来へ進んだ時刻列を戻せない。

提出する2ビルドを、単一タブ・全画面規則の下で直接測定した。
基準Aは`konomi/main` `52a3db5`、候補Bはsource `26484fd`とdist `27b327e`で、差分はこのbranchだけである。
各走行で読み込まれた`PlayerController` assetを照合し、WebGL2のdefault framebufferへの`drawArrays()`を直接数えた。
`drawFps < 10`または`late`増分30超を複合異常とした結果は次のとおりだった。

| 条件 | n | 複合異常 | drawFps<10 | `late`増分>30 | `late`増分合計 | 最低drawFps | queue全reset |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 基準 `52a3db5` | 90 | **35** | 18 | 31 | 1859 | 1.67 | 0 |
| 候補 `26484fd` | 90 | **1** | 0 | 1 | 294 | 29.98 | 51 |

候補の1件は`late`増分31で境界を1だけ超え、`drawFps < 10`は0件だった。
この1.8秒値にはseek応答中の無描画時間も含まれるため、定常fpsではなくseek直後の復帰窓である。
候補は平均fpsを上げる変更ではなく、未来へ進んだ時刻列を全resetで戻し、長時間stallを防ぐ正しさの修正として扱う。

容量圧迫も提出コードの制御ロジックで測り直した。
AとBへ同じ計測専用フックだけを加え、YADIF double-rateを明示的に開始した後、8秒窓のうち2秒間だけrVFC入力を維持したままpresentationを1/2 rAFへ制限した。
1 rAFにつき1 fieldへ変えるpolicyやqueue制御の変更は含めていない。
最大presentation latenessは、`#present()`が破棄する前のqueue先頭について`max(0, rAF時刻 - 表示予定時刻)`を測った値である。

| 制御ロジック | n | 容量FIFO破棄/走行 | presentation破棄/走行 | 合計破棄/走行 | 全reset/走行 | 最大lateness | 8秒窓draw fps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 基準 `52a3db5` | 3 | 55〜60 | 0〜4 | 59〜64 | 0 | 0ms | 52.46〜52.50 |
| 候補 `26484fd` | 3 | 0〜26 | 34〜61 | 60〜61 | 0 | 6.52ms | 52.24〜52.50 |

意図的に約60回のpresentation機会を失わせたため、合計破棄数は両版で同程度だった。
候補ではrAF位相により容量FIFOと既存presentation破棄の比率が変わったが、3走行ともqueue全resetはなく、破棄前の遅れも最大6.52msに収まった。
以前の全reset 14〜15回、最大83.3msという値は、削除済み前身と1 rAF 1 field policyを含む診断版の結果であり、提出buildの証拠には使わない。

全resetの閾値を`(queue容量 + 1) × max(refresh間隔, output間隔)`とする`+1`は、測定で選んだ係数ではない。
queue容量分は保持できるfieldを表し、残る1間隔はrVFCが同じcompositeのrAF直後に到着する通常の位相差を時刻破綻と誤認しないための余裕である。
これより小さいと次のcompositeを待つ正当なfieldをresetし得る一方、さらに広げると表示slotのない未来時刻列を余分に許容する。

presentation policyも同じbuildで分離した。
通常8秒を各3回測ると、1 rAFにつき1 field＋最小FIFOは59.91〜60.03fps、2 refresh以上遅れた場合だけcatch-upする二段階版は59.88〜60.04fps、従来の複数field消費は59.98〜60.00fpsで、全群の採取中`late`増分は0だった。
この短窓では差がなかったが、最新KonomiTVを通した120秒反復では自然負荷による通常fieldの誤破棄を再現した。
2走行平均でGalaxyは59.791→59.932fps、25ms超40→22.5回、`late` 9.5→0、Windowsは59.354→59.783fps、25ms超127→43回、`late` 66→15.5となった。
Windowsは全走行で電源モードが「最適な電力効率」だったことを後から確認した。この設定は変更せず、値は低性能・電力制約下の同一条件A/Bとして扱う。Galaxyとの絶対性能比較や通常設定のWindowsを代表する値には使わない。
全8走行でmedia timeは約120秒進み、全reset 0だったため、この時点では通常fieldの誤破棄を減らす独立候補とした。

その後、最新integrationからこのpolicyだけを外した対照を作り、Galaxy、60Hz、全画面、LAN直結、同じ188秒以降を軽量collectorで各600秒測った。policyありは3分後からrAFと入力callbackが徐々に低下し、全体rAF 56.662回/秒、入力callback 29.070回/秒、YADIFの`missed` 541、最大rAF間隔116.7msとなった。policyなしはrAF 59.998回/秒、入力callback 29.970回/秒、`missed` 0、最大rAF間隔33.3msを維持した。固定済みcallback traceだけをoffline replayするとpolicyありは163 field多く表示できるため、局所的なcatch-up判断自体は有利だったが、実再生では追加処理とcallback低下のfeedbackがその利点を上回った。両版の`droppedVideoFrames`増分は198で同じで、このcounterも長時間劣化を区別しなかった。[600秒A/B、分ごとの値、raw hash](results/galaxy-present-one-field-long-run-ab.json)を保存した。

policyなし版の40 seekはシーク完了時間の中央値159.7ms、p95 193.6ms、最大246.8msで40/40が当時の250ms判定以下だった。当時の判定を維持したまま長時間退行だけを除けるため、`fix/present-one-field-per-refresh`はPR候補とintegrationから外す。[40回の生値](results/galaxy-integration-without-present-seek-visible-40.json)を保存した。

同じGalaxy、全画面、単一タブ、LAN直結でvideo要素を直接測ると、Originalは30秒でrVFC 29.966fps、media time 30.008秒を維持しながら`droppedVideoFrames`が10増えた。
rVFCの898個の`mediaTime`差はすべて約33.367msで、入力video callbackに1 frame分の飛びはなかった。
サーバーエンコード1080p60は30秒でrVFC 59.632fps、counter増分0、120秒で59.683fps、counter増分0だった。
別PCのMirakurunから隔離KonomiTVへライブTSを入力し、電源モード「最適な電力効率」のWindows Chromeで600秒の対照試験も行った。最初の走行は保存済み画質`1080p`を引き継いで29.97pとなったため、低負荷対照としてだけ残した。主試験では`1080p (60fps)`を明示選択し、サーバー側FFmpegの`yadif=mode=1`と59.94p出力を確認した。29.97p対照は`presentedFrames`実効29.969fps、rVFC 29.942fps、counter増分1だった。59.94p主試験は`presentedFrames`実効59.935fps、rVFC 58.817fps、40ms超12回、最大66.8ms、counter増分1だった。60pはほぼ理論fpsで進んだがdrop 0ではなく、Windows / Chrome共通の稀な期限超過を否定できない。この経路はサーバー側`libx264`と通常のvideo要素を使い、録画OriginalのWASM / MSE / WebGL YADIF canvasを通らない比較対象である。[30p / 60p条件と全結果](results/windows-mirakurun-live-30p-60p-600s.json)を保存した。
[Media Playback Quality仕様](https://w3c.github.io/media-playback-quality/)では、このcounterはpredecodeまたはdecode後のdisplay deadline超過で落としたvideo frameを数える。
サーバーエンコード経路でも発生し得るが、サーバーで符号化前に間引かれ、bitstreamに存在しないframeはChromeから期待frameとして見えない。
Originalの最終表示はYADIF canvasなので、このcounterを最終可視fieldのdrop数や目標未達の根拠には使わない。

mpeg2toh264の既定`openGopRecovery: 'idr'`は24 GOPごとのrecovery境界で、元TSの新しい表示画像に対応しないIDRとreference cloneを2 sample追加する。各sampleのdurationは1 tickで、後続sampleから計2 tickを借りるため、全体のmedia durationは変わらない。同じ約140秒のMPEG-2 cutは元4193 frameに対し、既定変換が4238 sample、`recovery-point`変換が4194 sampleだった。既定版のGalaxy 120秒では`totalVideoFrames` 3636、`droppedVideoFrames` 40、rVFC 3596となり、`total - dropped`がrVFC数と一致した。counterは20回の境界で毎回2ずつ増えており、この極短sampleをChromeが表示しないことを数えている。

製品経路で`openGopRecovery: 'recovery-point'`だけを変えたGalaxy走行は、120秒でvideo media timeが120.000秒進み、rVFC 29.967fps、YADIF 59.925fps、YADIFの`late` / reset / drop増分0を維持し、`droppedVideoFrames`は0だった。ただし40ms超のcanvas間隔は既定版と同じく1回残り、約65ms空いたrVFC入力と一致した。40 seekは可視初画中央値149.1ms、p95 246.4ms、最大280.6ms、250ms以内39/40だった。同時刻の既定IDR対照20回は中央値160.9ms、p95 / 最大224.3ms、20/20が250ms以内で、方式による安定した短縮もtail悪化も立証していない。

したがってcounter増分の原因はperiodic IDR recovery copyで確定できるが、これをnon-IDR recovery pointへ変えることは可視カクつきの修正ではない。既定IDRはhardware decoderへ明確な再開点を与える互換性方針なので、Galaxyだけの成功を根拠に変更しない。[120秒trace](results/galaxy-recovery-point-steady-trace-120s.json)、[解析](results/galaxy-recovery-point-steady-trace-120s-analysis.json)、[seek 1](results/galaxy-recovery-point-seek-visible-1.json)、[seek 2](results/galaxy-recovery-point-seek-visible-2.json)、[既定IDR対照](results/galaxy-idr-current-control-seek-visible.json)を保存した。

残る40ms超のcanvas間隔ではrAFが約60Hzを維持し、同期`drawArrays()`も1ms未満だった一方、rVFC入力が約65ms空いていた。元TSとrVFCの`mediaTime`間隔は全区間約33.367msで、YADIFが入力callbackの揺れを吸収できず、生成済みfieldを使い切ったことが直接要因である。

queueが空のときの最初のfield deadlineを1入力frame分だけ後ろへ置く1行の固定reserve案を試した。120秒では59.940fps、40ms超0回、`late` / reset 0で、20 seekも中央値147.1ms、p95 / 最大213.6ms、20/20が250ms以内だった。しかし600秒へ延ばすと、約512秒から入力と表示clockの差でqueueが容量上限に張り付き、`late` 2071、reset 2、最大11.15秒のcanvas停止、全体56.370fpsとなった。短窓の成功だけでは分からない長期退行なので、この固定reserve案は採用しない。[120秒trace](results/galaxy-fixed-reserve-steady-trace-120s.json)、[同解析](results/galaxy-fixed-reserve-steady-trace-120s-analysis.json)、[600秒trace](results/galaxy-fixed-reserve-steady-trace-600s.json)、[同解析](results/galaxy-fixed-reserve-steady-trace-600s-analysis.json)、[seek](results/galaxy-fixed-reserve-seek-visible-20.json)を保存した。

入力callbackが遅れたときだけ最後の1 fieldを1 refresh保持する案は、120秒2走行で59.933fps、40ms超0回だった。しかし600秒ではqueue満杯時のFIFO破棄が連鎖し、`late` 4112、40ms超43回、53.087fpsへ悪化した。満杯時に最古fieldを捨てても残りの`at`を動かさないため、次に表示すべきfieldが約1 refresh先のまま残り、次の入力でも最古fieldを捨てる循環がコードと時系列の両方で成立した。

容量確保で捨てたfieldの`duration`合計だけ残りの`at`を手前へ詰めると、同じ保持刺激を含む600秒で59.938fps、40ms超0回、全reset 0となり、FIFO破棄は孤立した2 fieldだけで連鎖しなかった。ただし保持を加えないintegrationの600秒は`late` 0、最大33.6msで、組み合わせ版は`late` 2、最大39.1msだった。最後のfieldを保持するpolicyは採用せず、破棄した表示時刻の穴を閉じる変更だけをoverflowの正しさ修正として分離した。[条件、hash、主要統計、event抜粋](results/galaxy-yadif-input-gap-overflow-analysis.json)を保存した。

分離した変更は、`#prepareQueue()`が容量確保で捨てたfieldの`duration`合計を、残った全fieldの`at`から引く8行である。rVFC入力を保ったまま2秒だけpresentationを1回おきにする12秒試験を、WindowsとGalaxyで変更前後各3回行った。注入中は両版とも意図的に約30fpsとなるため、12秒窓の理論平均は約55fpsである。

WindowsではFIFO破棄fieldが平均21.67→0.67、40ms超間隔が平均0.33→0、解除後2秒の最大描画間隔が平均25.5→18.3msとなった。Galaxyでは変更前の2/3走行で破棄が解除後も連鎖し、破棄field平均218.0、12秒窓41.720fps、全reset合計1回だった。変更後は3/3走行とも直ちに約60fpsへ戻り、破棄field平均0.67、12秒窓54.997fps、全reset 0回だった。負荷注入中に失う約60 field自体を隠す変更ではなく、容量破棄後に残った時刻列から、すでに失ったpresentation momentだけを除く正しさ修正である。[全12走行、phase別統計、hash、後片付け結果](results/yadif-overflow-deadline-compression-ab.json)を保存した。

容量破棄前の表示時刻列を`a[i+1] = a[i] + d[i]`とすると、先頭からk fieldを破棄したときに引くduration合計は`a[k] - a[0]`である。圧縮後の先頭は元の先頭と同じ表示時刻になるため、残ったfieldを元の先頭より早く表示する変更ではない。

内容側の時刻も確認するため、順位4 source `26484fd` / dist `27b327e`と順位5 source `acfce36` / dist `63a5708`へ同じ計測だけを加え、KonomiTV `7307e0e`、Galaxy 60Hzで上の12秒負荷を各3回実行した。各fieldの映像時刻は、1 field目をrVFCの`mediaTime`、2 field目をそこから半frame後と定義し、canvasへ直接描画した時点の`video.currentTime`との差を測った。

| 対象 | 範囲 | 描画数 | 最小 | 中央値 | p95 | 最大 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 順位4 | 全描画 | 1,972 | -55.04ms | -35.52ms | -12.88ms | -6.19ms |
| 順位5 | 全描画 | 1,975 | -42.84ms | -13.14ms | -5.93ms | -2.20ms |
| 順位4 | FIFO破棄後も残ったfield | 68 | -45.75ms | -41.33ms | -38.52ms | -30.36ms |
| 順位5 | FIFO破棄後も残ったfield | 3 | -20.76ms | -15.19ms | -14.92ms | -14.89ms |

正の値は映像内容がmedia clockより先に出たことを表す。全3,947描画で正の値は0件で、順位5は遅れていた映像を順位4よりゼロ側へ近づけたが、media clockを追い越さなかった。音声decode byteも全6走行で増えた。順位5のFIFO破棄後の標本は3描画だけなので、この部分集合の差は均衡した効果推定には使わない。可聴音声とscan-outは測っていない。[定義、各走行、hash、集計](results/galaxy-yadif-overflow-av-lead-ab.json)と[6本の生trace](results/galaxy-yadif-overflow-av-lead-rank4-run-1.json)を保存した。

順位5のdist commit `63a5708`では、同commitの作業ツリーから`npm run build --workspace @mpeg2toh264/yadif`で再生成した`packages/yadif/dist/index.js`がcommit済み生成物とbyte単位で一致し、SHA-256はいずれも`6d94e0c…`だった。

通常のdouble-rate出力は`60000/1001fps`なので、1 fieldの`outputDuration`は約16.683msである。`#prepareQueue()`が未来時刻列の破綻を判定するhorizonは`6 × max(refreshMs, outputDuration)`で、60Hz、120Hz、144Hzのいずれでも`outputDuration`が支配し、約100.10msとなる。正常列の最大先読みも`6 × outputDuration`で、比較が`>`なので一致時にはresetしない。リフレッシュレートによってhorizonが約50.05msへ縮む境界はない。

Galaxy変更前の3走行目では、計測開始8.1ms後にqueue容量5から2 fieldをFIFO破棄した直後、残った先頭fieldが53.5ms先、末尾が120.2ms先となった。rVFC 133回、rAF 265回、video media time 4.404秒分が進む間もcanvas直接描画は0回で、計測開始4391.5ms後のqueue全resetに続き4419.0ms後に最初のcanvas描画が行われた。人工的なpresentation不足は計測開始2000ms後に始まるため、少なくともその前の1991.9msは人工負荷なしでfuture deadline待ちが継続していた。これにより、decoderやrAFの停止ではなく、FIFO破棄後のdeadline列が次の入力へ引き継がれる循環が4秒超の表示停止を維持したことを確認した。[元trace](results/galaxy-yadif-pre-injection-future-queue-stall-trace.json)と[機械集計](results/galaxy-yadif-pre-injection-future-queue-stall-summary.json)を保存した。

この診断buildには計測開始後に有効化する人工負荷フックが含まれる。負荷開始前から停止していたことは確認できるが、正式候補そのものに診断だけを加えた自然発生traceは別に取得し、branch単位の最終根拠とする。

正式候補は`fix/separate-yadif-queue-recovery`を親とする`fix/compress-yadif-overflow-schedule`で、source `7ef6696`と生成済みdist `ac2a2a9`を別コミットにした。長時間退行したpresentation policyを含まず、容量破棄後の時刻整合性だけを直す。

通常負荷の退行確認では、乃木坂工事中fixtureの既知の破損video packetより後にある187.845〜787.846秒を、Galaxy Chrome、LAN直結、全画面、単一タブ、60Hzで600秒測った。入力video callbackは29.972fps、media time差は600.001秒で、全17,982個のmedia time差が約33.367msだった。地デジのインターレース映像1 frameごとの入力callbackなので約30Hzは正常であり、double-rate YADIF canvasは59.942fpsだった。canvas描画間隔はp95 21.8ms、p99 23.2ms、最大39.7msで40ms超0回、WebGL drawは最大0.8msだった。YADIFの`late`、`degraded`、`discontinuities`、全reset、overflow破棄はすべて0だった。[正常負荷600秒の条件、統計、証拠hash、後片付け結果](results/galaxy-overflow-compression-clean-600s-summary.json)を保存した。

同じbuildで180〜199秒と480〜499秒を交互に40回seekすると、`video.currentTime`設定から`seeked`後も持続表示される目的canvas初画まで中央値157.2ms、p90 178.8ms、p95 187.1ms、最大197.3msで、40/40が250ms以下だった。18/40では目的frameを`seeking`中に描画し、`fix/preserve-destination-frame-on-seek`がそのまま保持した。正式なintegration bundleには計測用seek contextを含めないため、この走行は製品動作に近い可視初画を直接測っている。[40回の各走行と後片付け結果](results/galaxy-overflow-compression-visible-seek-40.json)を保存した。

queue容量を5から7へ広げた先行診断は600秒で59.940fps、40ms超0回だったが、future leadが最大約125msまで増えた。容量を可変遅延bufferとして使うため、A/V差とライブ遅延の上限が変更量から明確にならず、この形も正式候補にしない。5 / 6 / 7 slotの生値は[5 slot](results/galaxy-one-field-slack-five-slot-fullscreen-600s-120s.json)、[6 slot](results/galaxy-six-slot-fullscreen-600s-120s.json)、[7 slot 120秒](results/galaxy-seven-slot-fullscreen-600s-120s.json)、[7 slot 600秒](results/galaxy-seven-slot-fullscreen-600s-600s.json)に残す。次に検討できるのは、video media clockへ上限付きで同期し、通常の1 callback揺れだけを吸収しつつ、蓄積時は必要最小限を捨てるjitter bufferである。追加遅延、A/V差、ライブ追従、seek初画を同時に測れる設計が必要になる。

このqueue処理だけを`konomi/main`へ適用した正式候補をsource `26484fd`、生成済みdist `27b327e`の別コミットで公開した。正式な基準版との540/900秒交互90 seekでは、描画10fps未満18/90→0/90、複合異常35/90→1/90、`late`増分合計1859→294、最低draw 1.67→29.98fpsだった。候補のqueue全resetは51回で、`konomi/main`で加算されず常に0だった`queueResetted`が実際の再同期を再び表す。通常30秒では前身/正式候補が59.758/59.768fps、reset増分はいずれも0で、正式候補のMADDER確認区間3走行も23.7〜23.9fps、reset増分0だった。

overflow時刻圧縮の`autoFilm`回帰は、MADDER #04〜#07の別録画から無劣化で切り出した4本の固定3:2素材、通常60i対照、film↔video境界で確認した。60秒の3:2走行は`konomi/main`が24.21〜24.52fps、正式候補が24.17〜24.44fpsで、queue全resetは全走行0だった。境界30秒では両版ともfilm→videoとvideo→filmを観測し、通常60iは49.57 / 50.36fpsだった。候補固有の一貫した退行は観測しなかったが、3:2走行の描画間隔p95は両版とも約68〜71ms、通常60iも理論値60000/1001fpsを維持していないため、`autoFilm`の表示間隔は別の未解決問題である。[素材、build、全走行、除外理由](results/galaxy-autofilm-multi-fixture-regression.json)を保存した。

致命的な表示停止の定義と合格条件は、[測定方法の現行基準](METHODOLOGY.md#指標)を使う。上の1.8秒複合異常は、この判定には使わない。

この定義を直接判定するため、目的時刻のbuffered rVFC、`seeked`、`readyState >= 3`、可視canvasへの8回連続描画、100ms以上の持続、50msを超える描画間隔なしを安定復帰の条件にした。`tsukumijima/main` `52a3db5`の正確なbuildでは、同一seedの2回目、973.686秒へのseekで停止を再現した。`seeked`は151.8ms、目的rVFCは161.1msで、decoderは62 frame進み`droppedVideoFrames`は0だったが、canvas直接描画は2回だけ、最大間隔1790.6ms、YADIFの`late`は0→57、`outputFps`は59.973→1.936となった。ネットワーク・decoder完了後にYADIFの表示時刻列が回復しない事象である。[基準版smokeの生値](results/galaxy-fatal-detector-baseline-smoke-v2-20.json)を保存した。

queue容量確保と未来時刻列の再同期だけを分けた正式候補source `26484fd`、dist `27b327e`では、同じseedの先頭20回がすべて復帰した。[20回smoke](results/galaxy-fatal-detector-yadif-formal-smoke-20.json)に続き、240〜480秒と900〜1140秒を交互に選ぶ1000回pilotも停止0だった。厳しい安定復帰条件の時間は中央値697.6ms、p95 831.7ms、最大1303.5msで、通常の初回描画時間とは比較しない。[1000回pilotの生値](results/galaxy-fatal-detector-yadif-formal-pilot-1000.json)を保存した。

この1000回pilotだけでは1時間に達しないため、現在の合格判定には使わない。検出器、長時間反復、修正候補の安定性を確認した予備試験として扱う。

固定した試行間隔と表示更新に対するシーク開始時点の偏りを避けるため、各`video.currentTime`設定前に0〜33.37msの疑似乱数待ちを加え、blockごとにブラウザー、player、Worker、decoder、MSE、YADIFを作り直す自動試験を行った。正式候補の最初のblockは258回目に致命的停止を1件検出したため、その時点で自動停止した。`seeked`は250.3ms、目的rVFCは253.5msで成立し、2.5秒の観測中にdecoderは65 frame進んだが、canvasの最大描画間隔は1615ms、YADIFの`late`は25→91、queue全resetは4→5、終了時`outputFps`は0だった。1時間以内に停止を検出したため、正式候補は現在の合格条件を満たさない。[シーク前待ち時間を変えた試験の失敗記録](results/galaxy-fatal-yadif-formal-phase-randomized-failure.json)を保存した。

同じseed、同じ258回目を含む300回を診断計測付きで再生すると停止は再現せず、該当seekは735.8msで安定復帰した。地点と要求列だけで決まる事象ではない。[300回の再現試行](results/galaxy-fatal-yadif-formal-diagnostic-replay-300.json)も保存し、rAF、rVFC、WebGL直接描画を時系列記録する反復診断を続ける。

提出build source `26484fd` / dist `27b327e`を、読み取り専用snapshotへ固定したrunnerで再試験した。1,000 seekごとにChrome、page、player、Worker、decoder、MSE、YADIFを作り直し、各blockに別seedを使った。第4 blockの8回目、全体の3,008回目で致命的停止を1件検出し、1時間上限の試験を2,447.503秒で自動停止した。先行3 blockは各1,000回、合計3,000回が安定復帰していた。

停止時は`seeked`が178.6ms、目的rVFCが189.0msで成立し、`readyState`は4、video decoderは67 frame、音声decodeは61,270 byte進んだ。一方、canvasの最大描画間隔は1,679ms、YADIFの`late`は2→70、queue全resetは1→2、終了時`outputFps`は0だった。server、MSE入力、decoder、音声の停止ではなく、YADIF表示側で復帰しない点は以前の258回目と一致する。[全体集計](results/galaxy-yadif-rank4-one-hour-block-reset-summary.json)と[停止block](results/galaxy-yadif-rank4-one-hour-block-reset-block-003.json)を含む4 blockの生値を保存した。

同じ提出sourceへqueue時系列を記録する受動的な計測だけを加え、別seedで自然発生を反復した。4回目のseekで`seeked`は147.9ms、目的rVFCは154.4msで成立し、decoderは67 frame、音声decodeは63,454 byte進んだ。canvasの最後の直接描画は804.3msで、その後1,697.3msは直接描画がなかった。

最後の直接描画後もrVFCは51回進んだが、51回のqueue容量確保で計101 fieldをFIFO破棄した。各入力callbackの直前には古い先頭fieldが表示期限へ近づいていたが、2 fieldを破棄すると残った先頭が再び約3〜4 refresh先へ移る。rAFは表示対象を得られず、次の入力callbackが同じ破棄を繰り返した。これにより、自然発生した致命的停止の原因を、容量破棄後の空いたpresentation momentを残すYADIFの時刻列へ特定した。[受動計測を含む生値](results/galaxy-yadif-rank4-natural-fatal-timeline.json)を保存した。

この停止では、シークまたはmedia time不連続による既存のqueueクリア後にキューが積み直され、通常再生中に再び循環へ入った。キュー深さ5が連続した151 eventでは、先頭の先読みは11.86〜64.36msで、146 eventが`#present()`の期限である25msを超えた。残る5 eventはoverflow処理直前の標本で、先頭が期限へ近づいた後、容量確保で古いfieldを捨てると再び未来へ押し戻されていた。したがって、シーク前の古いqueueが残った停止ではない。

時刻破綻のhorizonは約100.10msで、判定に使うのは先頭ではなく末尾の先読みである。深さ5が続いた区間では、容量確保を始めた50 eventすべてで末尾がhorizon内にあり、最大97.73msだった。一方、field追加後の`future` 101 eventでは末尾がすべてhorizonを越えたが、次の容量確保までに時間が進むためqueue全resetを避けていた。唯一のqueue全resetはevent 36で末尾202.08msを検出して深さ5を1へ減らし、同時刻の描画を可能にしたが、その後に同じ容量破棄の循環へ再度入り、試行全体は復帰しなかった。

後続のoverflow時刻圧縮へ同じ受動計測を加え、同じseedの4回目、905.784979秒へのseekを比較した。順位4は2.5秒で復帰せず、overflow 54回、FIFO破棄104 field、future待ち116回、queue全reset 1回だった。差分をoverflow時刻圧縮だけにした順位5は、overflow 4回、FIFO破棄4 field、future待ち7回、queue全reset 0回で、508.5msの描画から安定列が始まり、692.6msで安定を確認した。decoder、音声、canvas描画も進み、先頭4 seekを完了した。[同一計装の順位5結果](results/galaxy-yadif-rank5-same-instrumentation-success.json)を保存した。これにより、空いたpresentation momentを詰める変更が自然発生した循環を止める因果を同一計装で確認した。

queue全reset単独の必要性は別に評価した。診断traceでは、末尾107.83msで閾値を越えたqueue全resetの66.6ms後に描画が戻った実例がある。ただし、その直前も容量破棄によって未来時刻列が連鎖しており、overflow時刻圧縮があってもqueue全resetだけが必要になる状態は保存済みtraceにない。したがって、閾値resetが実際に作動して描画を戻せることまでは確認できるが、時刻圧縮と独立した正式修正として必要だとはまだ立証できない。

`results/`全体を機械監査すると、`queueResetted`が正値のファイルは31件あったが、前後のキュー状態を保存した明示的な`clock-reset` eventは2ファイルだけだった。どちらも容量破棄で作られた未来時刻列の中で発火しており、閾値resetだけが必要な独立事象は確認できなかった。順位4の1時間停止blockはqueue全resetが1回増え、最大深さ5に達したが、queue時系列を保存していないため同じ機構とは確定しない。[停止別の機械集計と不足項目](results/yadif-fatal-queue-mechanism-audit.json)を保存した。

基準版`52a3db5`の異常TS反復試験では、利用者操作を検出する前に完了した20 blockの全20件で致命的停止を観測した。全件が異常区間通過後に最大キュー深さ5へ達し、queue全resetは0、`late`は22〜360だったため、容量上限へ張り付く署名が反復したことは確認できる。ただしqueueの先頭・末尾時刻を保存しておらず、各停止が同じdeadline循環だったことまでは確定しない。次のblockで`pointerdown`と`touchstart`を検出してrunnerが終了したため、これは1時間の合格判定や正式なA/B値には使わない。[完了blockのhash、集計、除外理由](results/galaxy-baseline-anomaly-interrupted-diagnostic.json)を保存した。

後続のoverflow時刻圧縮 source `7ef6696` / dist `ac2a2a9`では、単一の連続セッションで4,073 seek・停止0、実測3,572.682秒だった。ただし実行中のshell runnerを編集したため、collectorのraw出力後にrunnerが失敗した。blockごとの再生成も行っていない。この走行は[除外理由付きの参考値](results/galaxy-yadif-rank5-one-hour-continuous-excluded-summary.json)として残すが、順位5の合格根拠にも、順位4との効果比較にも使わない。順位5の因果効果には、同じ読み取り専用snapshotとblock再生成条件で別の1時間試験が必要である。

同じ正式buildでChrome、page、player、Worker、decoder、MSE、YADIFを1,000 seekごとに作り直す1時間試験は、5 session、実測3491.416秒で4,399 seekすべてが復帰した。ただし最初のblock中に、同じLinuxホストで上の順位5診断buildを実行した。発生した追加負荷を分離できないため、[高負荷を含む参考結果](results/galaxy-yadif-rank5-one-hour-high-load-reference.json)として残し、無負荷の1時間合格根拠には使わない。

順位5の正式build source `7ef6696` / dist `ac2a2a9`を最新KonomiTV `7307e0ec39aed6a4772908cdbfb44223da42be6d`へ組み込み、同じrunner、collector、fixture、各試行のシーク前待ち時間の列、block再生成条件で無負荷の1時間試験を行った。5 session、実測3,486.728秒で4,415回すべてが2秒以内に安定復帰し、致命的な表示停止は0件だった。安定復帰時間は中央値661.2ms、p95 804.0ms、最大1,213.5msだった。全blockの終了後に動画停止、fullscreen解除、検証tab閉鎖、Chrome停止、ADB forward解除、container停止を確認した。[集計とblock hash](results/galaxy-yadif-rank5-latest-one-hour-summary.json)および[5 blockの生値](results/galaxy-yadif-rank5-latest-one-hour-block-000.json)を保存した。

順位4の1時間試験はKonomiTV `e92fba8bb219589c8e4ada9609ed4a9d91b33c00`、順位5の上記試験は`7307e0e`であり、runner、collector、fixtureは一致するがKonomiTV revisionは一致しない。このため、順位5が現行の1時間条件を満たす根拠には使うが、3,008回目の停止が0件になった差を順位5だけの効果とは扱わない。順位5の因果効果は、同一計装、同一seed、同一目的時刻でFIFO破棄104→4 field、致命的停止→508.5msからの安定描画となった比較で評価する。

現在のintegration全体を正確に組み込んだbuildでは、同じseedと各試行のシーク前待ち時間の列による1000回すべてが2秒以内に安定復帰した。安定復帰時間は中央値614.4ms、p95 774.6ms、最大979.3msだった。この予備試験は走行時間が1時間に達しないため、単独では合格判定に使わない。[build manifest](results/galaxy-integration-exact-build-manifest.json)と[1000回の各試行](results/galaxy-integration-exact-fatal-phase-randomized-1000.json)を保存した。

最新KonomiTV client `7307e0e`へ基準版`52a3db5`とintegration `44e06a4`をそれぞれ組み込み、同じfixture、runner、seed、目的時刻、各試行のシーク前待ち時間の列で比較した。隔離backend imageは`e92fba8`だが、`e92fba8..7307e0e`の`server/`に差分はない。基準版は54回目に致命的な表示停止を検出し、53回の成功後に試験を終了した。integrationは最大1,000 seekごとにChrome、page、player、Worker、decoder、MSE、YADIFを作り直し、5 session、実測3,456.840秒で4,732回すべてが2秒以内に安定復帰した。壁時計では3,575.590秒で、致命的な表示停止は0件だった。基準版が停止した54回目と同じ目的時刻とシーク前待ち時間では、integrationは418.7msで安定復帰した。全blockで動画停止、fullscreen解除、検証tab閉鎖、Chrome停止、ADB forward解除、container停止を確認した。[同条件比較と各blockのhash](results/galaxy-formal-current-integration-comparison.json)を保存した。この結果は正常区間の反復seekに対する1時間条件を満たすが、正常TSの1時間連続再生や異常TSの1時間試験を兼ねない。

同じbuildで既知の破損video packetを1回横切る15秒traceを取得した。入力rVFCは125.019秒から125.587秒へ567.233ms進み、canvasの最大描画間隔は521.9msだった。表示は安定条件へ863.0msで復帰し、利用者操作、再seek、playback error、visibility変更はなかったため、この単発走行に致命的な表示停止はない。

表示進行の復帰直後にはdecoderの追いつきを含むため、定常cadenceと分けた。3秒以上にわたり期待値の±1%かつ40ms超の間隔0回となる最初の窓は欠陥直前から1,615ms後に始まり、4,627.5ms後に確認できた。trace末尾5秒のcanvas描画は60.01fpsで、期待値59.94fpsとの差は0.11%、40ms超は0回だった。一方、この窓でもChromeのdrop counterが2、YADIFの`late`が1増え、最大描画間隔は30.5msだった。canvasのdraw呼出しはcompositorのscanoutを証明しないため、可視コマ落ち0とは判定しない。

最新KonomiTV client `7307e0e`へ基準版`52a3db5`とintegration `44e06a4`をそれぞれ組み込み、同じfixture、runner、seed、seek時刻、欠陥時刻、各試行のシーク前待ち時間の列でこの破損packetを直接比較した。基準版は2回目に致命的な表示停止を検出し、1回の成功後に試験を終了した。integrationは20回すべてが2秒以内に安定復帰し、安定復帰時間は中央値911.0ms、p95 940.2ms、最大1,088.1msだった。同じ先頭2回では、基準版の2回目だけが停止し、integrationの対応する試行は920.1msで復帰した。

復帰後約3秒のcanvas FPSは、基準版で成功した1回が22.16fps、integrationは中央値53.94fps、範囲52.94〜55.62fpsだった。integrationも期待値60000/1001fpsの±1%かつ40ms超の描画間隔0回という判定を20回すべてで満たさなかった。音声decode byteは基準版2/2、integration 20/20で増えたが、可聴A/V同期は測っていない。全blockで動画停止、fullscreen解除、検証tab閉鎖、Chrome、WebAPK、ADB forward、隔離KonomiTVの停止を確認した。[直接比較、生値hash、集計条件](results/galaxy-formal-current-integration-comparison.json)を保存した。

Windows 11、Chrome 152、60Hz、電源モード「最適な電力効率」の補助条件でも、integration `44e06a4`と同じfixtureをWindows内の隔離KonomiTVから配信し、同じ破損位置を反復通過した。1時間を予定した走行は121回目で致命的停止を検出し、120回成功、停止1回で終了した。実測は1,867.642秒、壁時計は2,048.063秒なので、1時間条件を満たした走行ではない。成功した120回の安定確認は中央値734.2ms、最大1,733.1msで、FPS安定復帰失敗は39回だった。

停止時のrVFCはmedia time 123.284288秒から126.887888秒まで壁時計3,791.0ms途切れ、その後127.722055秒から131.892888秒まで5,730.9ms途切れた。media timeの飛びはそれぞれ3,603.6msと4,170.833msで、成功した120回の567.233〜600.600msより大きい。終了時のYADIFはqueue全reset 0、最大queue深さ4、`late` 72、`outputFps` 59.988で、playerは映像649 frame、音声1,060 frameを処理していた。以前確認したGalaxyの循環ではrVFCが進み続け、queue深さ5に張り付いていたため、同じ現象の署名はない。Windows traceにはqueue先頭・末尾の先読みとevent時系列がなく、同一機構ではないと証明することもできない。converter、MSE、decoder、Windowsの表示scheduleのどこがrVFC停止を作ったかは未確定である。

campaign内のruntime終了commandは時間切れになったが、直後の確認では対象portとprocessは残っておらず、再度の停止commandは全processを停止済みと報告した。Chrome、視聴tab、fullscreen、scheduled taskも残っていなかった。Search IndexerとFFmpegは全7回のhost負荷sampleで0だった。[条件、provenance、停止trace、後片付け](results/windows-anomaly-integration-44e06a4-until-fatal.json)を保存した。このWindows値は同一電源モード内の比較用であり、Galaxyとの絶対性能比較には使わない。

同じWindows補助条件で、overflow時刻圧縮 source `acfce36` / dist `63a5708`をmedia-internals計測付きで1時間走行した。11 session、217回すべてが2秒以内に復帰し、致命的停止は0件だった。一方、FPS安定復帰は217回すべて不合格で、復帰後の描画FPSは中央値39.776、最大描画間隔は中央値50.5msだった。1時間のcoverageと後片付けは成立し、Search IndexerとFFmpegも検出しなかった。この走行は以前のWindows停止走行とclient revisionと計装が異なるため修正効果の同条件比較には使わないが、致命的停止を観測しなかった状態でもcadence問題が独立して残ることを示す。[集計値とprovenance](results/windows-rank5-media-internals-one-hour.json)を保存した。

同じWindows buildへ診断計装を加え、停止時と同じseed `26260932`、同じ31.566msのシーク前待ち時間を、新しいclient sessionの先頭試行で再実行した。今回はシーク完了時間574.0ms、異常区間のrVFC gap 565.3ms、安定確認743.4msで復帰し、致命的停止は再現しなかった。したがって、停止はseedとシーク前待ち時間だけでは決まらず、client sessionやdecoder状態など別の状態変数を切り分ける必要がある。診断計装付き3試行は致命的停止0件、FPS安定復帰失敗1件だったが、発生率や正式なシーク完了時間には使わない。[同seedの診断結果](results/windows-anomaly-fatal-seed-diagnostic.json)を保存した。

Windows Chromeのdecoder状態を取得するため、測定終了後に`chrome://media-internals`の再生中playerを一意に選ぶ2試行の診断も行った。このsessionではChromeが最初に`D3D11VideoDecoder`を選び、試験用seekより前の初回decode errorで`FFmpegVideoDecoder`へfallbackしていた。したがって、この診断sessionの表示性能はsoftware decodeを含む。以前の長時間走行では同じ内部logを取得していないため、過去のWindows結果もsoftware decodeだったとは断定しない。[decoder event列、build hash、後片付け](results/windows-anomaly-decoder-fallback-smoke.json)を保存した。

同じbuildと欠陥を使い、Chrome、page、player、Worker、decoder、MSE、YADIFを20回ごとに作り直す計装付き1時間診断も行った。11 session、219回すべてが2秒以内に安定復帰し、致命的停止は0件だった。FPS安定復帰失敗は85回で、走行全体は不合格だった。Search IndexerとFFmpegは11回のhost負荷標本で0回、全sessionと最終cleanupは成功した。追加計装を含むため、この0/219を正式な発生率やシーク完了時間には使わない。

block 3、5、8は各20試行すべてが同じ低FPS状態になった。この60試行の3秒窓ではrVFCが中央値19.999fps、canvas直接描画が中央値39.996fpsだった。3,654個の隣接rVFCは`presentedFrames`がすべて1ずつ進んだが、映像時刻は1 frame分が1,852区間、2 frame分が1,802区間だった。他のFPS安定復帰失敗25回ではrVFC中央値29.508fps、canvas中央値59.016fpsだった。したがって約40fpsのsessionでは、YADIFが独立に描画を減らしたのではなく、Chromeが約20fpsでpresentationした映像をYADIFが2 fieldへ展開している。

この走行のFPS失敗contextにはrAF履歴がなく、compositor/rAF自体が約40fpsへ落ちた結果なのか、rAFが約60fpsのままvideo presentationだけが約20fpsへ落ちたのかは分離できない。次の診断では失敗窓のrAF、rVFC、canvas直接描画とvideo要素の`playbackRate`を同時に保存する。[summaryと全blockのhashを照合した層別集計](results/windows-anomaly-diagnostic-one-hour-layer-analysis.json)および[集計スクリプト](scripts/analyze-windows-anomaly-diagnostic.py)を公開した。

音声decodeは欠陥区間後69.4msで進んだが、独立した可聴音声clockを取得していないためA/V同期は未証明である。欠落packetと全復号依存frameの対応も未確定なので、17個の`droppedVideoFrames`が避けられない最小範囲であるとは主張しない。[schema version 2の解析](results/galaxy-integration-current-v3-anomalous-recovery-analysis.json)と[生trace](results/galaxy-integration-current-v3-anomalous-recovery-trace.json)を保存した。[解析器](scripts/analyze-anomalous-recovery-v2.mjs)と[回帰試験](scripts/test-anomalous-recovery-v2.mjs)も同じリポジトリで公開している。

元TSの不連続は、映像PID 256のbyte位置202,401,364でcontinuity counterが1から6へ飛んだ箇所だった。discontinuityの通知はなく、欠落数は16を法として4 packetに相当する。この位置はB-picture（temporal reference 7、PTS 502108869）のPES内にあり、FFprobeのcorrupt表示が指した直前のPES位置とは異なる。独立に読んだ周辺24 pictureの種類・PTS・PES位置はFFprobeと一致した。[TS byte解析・照合結果](results/nogizaka-transport-defect-localization.json)と[固定fixture用の再現スクリプト](scripts/inspect-nogizaka-transport-defect.py)を公開している。

耐障害性をこの1件から一般化しないため、別録画の「キッズアワー」も固定素材へ加えた。元録画5,260,616,188 byteの全2,798万packetを走査すると、同期エラー、TEI、discontinuity通知は0件で、映像PID 256のcontinuity counter不連続が2件あった。1件目は録画先頭の映像PTSから867.433秒、byte位置1,028,952,388でcounterが2から9へ飛び、欠落値は16を法として6だった。open GOP内のP frame picture（temporal reference 11、PTS 1165933447）が損傷していた。2件目は3277.875秒、byte位置4,838,639,848でcounterが2から8へ飛び、欠落値は5だった。open GOP内のB frame picture（temporal reference 12、PTS 1382873170）が損傷していた。

各不連続の約16MiB前から64MiBをTS packet境界で切り出し、再エンコードとremuxを行わず固定した。fixtureのSHA-256はP-picture側が`de453e5acd06b7072da20f38ed1a6b80ddf3dcf8332648fe6175a74a5e1bbef3`、B-picture側が`eada598bc1437d0739dec2cd439bc8d4a2706f5939b45b162997e3ad8ebabe93`で、各fixtureには対象の不連続が1件だけ含まれる。counterの飛びは欠落packet数を16を法として示すだけで、ブラウザーで失われる表示frame数を示さない。不可避な最小drop、画素、可聴A/V同期、実機の復帰性は未測定である。[全packet走査とpicture位置](results/kids-hour-transport-defects.json)および[一般化した検査スクリプト](scripts/inspect-ts-transport-defects.py)を公開した。

この2本を直接の親`52a3db5`と候補tip `e36dd0b`のconverter binaryでオフライン変換した。P-picture破損では候補が映像sampleを10個多く保持し、最大映像時刻間隔は567.233msから300.300msへ縮まった。B-picture破損では12個多く保持し、最大間隔は567.233msから166.833msへ縮まった。両fixtureとも音声sample数、各sampleのdecode時刻・duration・composition offset、音声trackの時刻範囲が一致した。

公開integration `44e06a4`と順位9を重ねた検証build `be568d8`でも同じ変換を行った。各fixtureで、integrationの出力は`52a3db5`と、検証buildの出力は`e36dd0b`とそれぞれbyte単位で一致した。したがって、このオフライン条件では順位9の作用をintegrationへ重ねても変わらない。実行したbinaryは結果内のSHA-256で識別し、source revisionは呼び出し側の宣言として区別した。この結果は実在するopen-GOP内のP/B frame picture破損に対する再現性を広げるが、ブラウザー、画素、可視scanout、不可避な最小drop、可聴A/V同期、field picture破損を証明しない。[4 buildの比較結果](results/kids-hour-defect-conversion-comparison.json)と[再現スクリプト](scripts/measure-fixed-anomaly-conversion.py)を公開した。

integration `44e06a4`は、PESの損傷通知を受けると蓄積中のGOPを破棄する。Galaxyで測った乃木坂工事中の損傷対象は後続pictureの参照元にならないB-pictureなので、正常なpictureまで破棄している可能性がある。ただし、変換後の各pictureとの対応と画素の正常性は未検証であり、「1 pictureだけ落とせば十分」とはまだ判定しない。

同じ固定byte windowを、integration `44e06a4`由来として記録したconverter binaryでオフライン変換した。source revisionは呼び出し側の宣言であり、実行したbinaryは結果JSONのSHA-256で識別する。出力fMP4をFFprobeで復号すると、隣接frameの表示時刻に最大567.233msの間隔があり、GalaxyのrVFCで観測したmedia timeの567.233ms飛びと0.002ms以内で一致した。したがって、Galaxyで見えた時刻の飛びはAndroid decoderやYADIFだけが作ったものではなく、converterの出力時刻列に既に含まれる。破損B-pictureを含む入力のkeyframe間隔は15 frame・500.5msだったが、固定windowは先頭と末尾がstream途中なので、入出力frame数の差から破棄picture数を決めない。画素の正常性、表示可能だった最小picture集合、A/V同期は引き続き未証明である。[変換結果](results/nogizaka-defect-conversion-timeline.json)と[再現スクリプト](scripts/measure-nogizaka-defect-conversion.py)を公開した。

公開候補`fix/preserve-complete-pictures-before-loss`は、packet欠落後のbyteを読む前に、次のpicture開始位置まで受信済みで完了を確認できるprefixをtranscoderへ渡し、完了を確認できない末尾を破棄する。同じ固定byte windowをsource `f27442d`から構築したbinaryで変換すると、出力video sampleは34から41へ増え、最大表示間隔は567.233msから300.300msへ短縮した。

fMP4の`tfdt`と`trun`を直接解析すると、映像trackの先頭decode時刻、末尾decode時刻、先頭presentation時刻、末尾presentation時刻は両版で一致した。音声trackも92 sample、先頭0、末尾94,208、最大間隔1,024 sampleで、各sampleのdecode時刻・duration・composition offsetから作ったSHA-256も一致した。mux上の音声fragment数は2から3へ変わったが、符号化済み音声sample時刻列は変わっていない。

このオフライン結果はconverter出力の映像改善と音声時刻列の不変を示すが、可聴音声clockやブラウザー出力を測っていないため、音ズレがないことの証明には使わない。実在するfield picture破損、画素の正常性、可聴A/V同期は引き続き未確認である。[基準版](results/nogizaka-defect-conversion-timeline.json)と[候補版](results/nogizaka-defect-preserve-complete-pictures.json)の変換結果を保存した。

修正単独の差を確認するため、最新KonomiTV `7307e0e`へ直接の親`52a3db5`と候補`f80154f`を組み込み、Galaxy、LAN直結、全画面、同じfixture、同じ113.67秒seekでB-C-C-Bの順に各2回測った。15秒traceはすべて既知の欠陥125.0249秒を横切り、利用者操作、playback error、visibility変更、致命的停止はなかった。

| build | FPS安定復帰までの最大映像時刻間隔 | FPS安定復帰までのcanvas最大描画間隔 | Chrome drop | YADIF degraded | discontinuity | 期待表示FPSへ復帰 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 基準1 | 600.600 ms | 569.6 ms | 17 | 3 | 1 | はい |
| 候補1 | 333.666 ms | 317.6 ms | 6 | 0 | 0 | はい |
| 候補2 | 333.666 ms | 318.1 ms | 6 | 0 | 0 | はい |
| 基準2 | 567.233 ms | 522.4 ms | 17 | 3 | 1 | いいえ |

候補は欠陥時刻を最初にまたぐrVFC映像時刻間隔を1 frame分へ縮めたが、その約200ms後に333.666msの映像時刻間隔が残った。FPS安定復帰までの最大値は基準版の567.233〜600.600msから333.666msへ、canvas最大描画間隔は522.4〜569.6msから317.6〜318.1msへ縮まった。基準版にあったYADIFのdegradedとdiscontinuityも起きなかった。この直接A/Bは同じ詳細計装を使った相対比較であり、絶対時間は低負荷の走行と分けて扱う。欠損したB pictureは`picture_structure=frame`で、`closed_gop=0`かつintra pictureより表示順が前のB pictureを2枚持つopen GOP内にある。したがって実在するopen GOP内の欠損はA/Bの対象だが、field picture欠損ではない。2走行では異常TSの1時間条件、可視scanout、最小限の不可避drop、可聴A/V同期、field picture、画素の正常性を証明しない。[packetとpicture構造](results/nogizaka-transport-defect-localization.json)と[A/B集計・全trace](results/galaxy-anomaly-preserve-complete-pictures-ab.json)を保存した。

公開branchには、interlaced `hd1080i.m2v`とcomplementary B fieldを含む`open_gop_leading_bb.m2v`へ2種類のpacket欠落位置を与えるSession回帰試験を`27eed22`で追加した。現在のtip `e36dd0b`で`cargo fmt --check`と`cargo test --release`を実行し、239件が成功、失敗0件だった。現在のdist `e36dd0b`はGalaxyで測った`f80154f`とruntime source・distがバイト一致し、差分は試験だけである。この固定fixtureは通常のfield pair・open-GOP filterを通るが、実在するfield pair・open GOP破損のブラウザー挙動を一般化しない。

順位9単独と、公開integration `44e06a4`へ順位9を重ねた検証build `be568d8`で実施した2本の1時間走行は、素材の不一致が判明したため採用しない。結果は`videoId=1`を乃木坂fixtureとして記録していたが、走行前から保存されていた両コンテナのDBでは、ID 1は`madder-24p-clean.ts`、乃木坂fixtureはID 2だった。旧runnerは宣言したfixture名とSHA-256を結果へ転記するだけで、APIのfile size、録画時間、download filename、`Content-Range`の総byte数を照合していなかった。

したがって、順位9単独の223回とintegrationへ重ねた224回から得た致命的停止件数、FPS安定復帰失敗件数、復帰時間を、乃木坂の固定欠損または順位9の効果の根拠には使わない。生のsummaryとblockは測定履歴として残し、[不一致の根拠と影響範囲](results/galaxy-anomaly-rank9-one-hour-fixture-mismatch.json)を別に記録した。再測定では、現行runnerのfail-closed preflightにより、API metadata、download filename、`Content-Range`、fixture SHA-256、video IDがすべて一致した場合だけ走行を開始する。

50msと250msの単発main-thread stallでは、両版とも次の1秒窓で約60fpsへ戻り、注入中の全reset増分はなかった。これはrAFとrVFCを同時に止めるため、queue容量差を単独では励起しなかった。正式A/Bの90 seekと、正式制御ロジックへ同一の計測フックだけを加えた容量圧迫3走行の全条件、生値、hash、後片付け結果は[正式build A/B](results/galaxy-yadif-queue-recovery-formal-ab.json)に保存した。[後継候補の実機結果](results/galaxy-yadif-queue-recovery-successor.json)も同じ値へ更新した。

初期video fieldを2 field先から1 field先へ置く比較は、従来presentation policyの3走行で8秒窓59.64〜59.84fpsから59.98〜60.00fpsへ上がったが、短窓かつ開始前resetが両群に混在した。
独立した効果としては未確定なので、これもqueue整合性修正へ混ぜず長窓A/Bを行う。
全runと、端末操作が入ったため除外した1 runは[full-screen scheduler ablation](results/galaxy-yadif-scheduler-ablation.json)に保存した。

比較用に、各rVFCの`expectedDisplayTime`へfield時刻を再アンカーする独自案も旧条件で測定した。
当時は停止0/30だったがタブ数を固定していないため効果量には使わず、upstreamのqueue設計とも異なるので優先度を下げる。
旧測定は[従来のqueue計測](results/yadif-seek-queue.json)、単一タブA/Bの全走行は[queue再同期A/B](results/galaxy-yadif-queue-single-tab-ab.json)に保存した。

`autoFilm`は区間依存である。
MADDERの420秒と900秒では`film`へ入り約23〜24fps、120秒では`video`のまま、1500秒では`video`から`film`への切替過渡を観測した。
番組全体を24fpsと扱わず、初画、mode lock、定常cadenceを別々に評価する。

固定した`autoFilm`回帰素材を作るため、MADDER全編をFFmpeg 8.1.2の`fieldmatch=mode=pc_n:combmatch=full:mchroma=0,decimate=cycle=5:mixed=1`で解析した。5入力frameごとにduplicateが1枚選ばれ、`fieldmatch`が残留インターレースを報告しない完全cycleの最長連続区間は、録画先頭から約1320.986〜1502.334秒の181.348秒だった。

キーフレーム境界のずれを吸収する余裕を取り、1325秒から172.8秒分を映像と主音声だけ`-c copy`で切り出した。実際のvideo packet範囲は1324.824〜1497.463秒、出力TSは約172.853秒である。1035個の完全cycleはすべて1 duplicateを除き、残留インターレース、40msを超えるvideo PTS間隔、映像・主音声のdecode errorは0だった。末尾の1 frameは5-frame cycleを作れないため、cadenceの主張から除外する。

この素材の期待表示速度は24.000fpsではなく、地上波の30000/1001fpsの3:2プルダウンから戻る24000/1001fpsである。ローカルSSD上の固定素材のSHA-256は`163f234e006145d75d794c7a233f874a05cd7c8ce1298cb8b82c86a91a53b6fb`で、[全編scan、上位区間、切り出し条件、検証値](results/madder-24p-clean-fixture.json)を保存した。

実写1本だけで`autoFilm`の改善を判断しないため、アニメの「サンダー3」と「ワールド イズ ダンシング」も全編を同じ`fieldmatch`・`decimate`条件で解析した。最長の連続3:2区間は、それぞれ477.477〜520.687秒の259 cycleと、1237.737〜1439.438秒の1209 cycleだった。

各区間の内側を映像と主音声だけ`-c copy`で切り出した。固定素材内で検証できた完全cycleは213個と1136個で、combed cycle、40msを超えるvideo DTS・PTS間隔、40msを超えるaudio PTS間隔、映像・主音声のdecode警告は0だった。末尾の不完全cycleはcadenceの主張から除外する。素材のSHA-256、切り出し条件、source packet位置の包絡、検証値は[アニメ固定素材の記録](results/anime-autofilm-clean-fixtures.json)に保存した。

KonomiTV `e92fba8`へ`tsukumijima/main` `52a3db5`と現在のintegrationをそれぞれ正確に組み込み、Galaxy Chrome、LAN直結、全画面、60Hzで、この固定素材を`autoFilm`有効で120秒ずつ各2回測った。入力video callbackは全走行29.964〜29.971fpsで、media timeは各走行とも約120秒進み、入力timestamp差はすべて約33.367msだった。

基準版のcanvas描画は27.641 / 27.774fps、integrationは27.181 / 26.971fpsだった。film/video判定の遷移は基準版28 / 28回、integration 38 / 33回で、両版とも期待するfilm cadenceを維持しなかった。YADIFの`missed`とqueue全resetは全走行0なので、入力停止やqueue全resetではなく、固定3:2区間で`autoFilm`判定を維持できないことが、期待するFPSを安定維持できない直接の観測である。integrationの方が低い差は観測したが、各2走行だけなので個別修正の退行量とは断定しない。Chromeの`droppedVideoFrames`増分40はcanvasの可視drop数とは扱わない。[4走行の集計、build hash、生値](results/galaxy-integration-exact-autofilm-24000-1001-summary.json)を保存した。

位相保持の試作がMADDER #04でfilmを維持できなかった走行では、YADIFの`missed`が302増え、毎秒statsの隣り合う標本間57区間すべてで増加していた。
同じ試作の他3走行は`missed`増分0で、毎秒statsのmodeがすべてfilmだった。Chromeのdrop counterは4走行とも20増えており、この不調を単独では区別できない。

`missed`はrVFC間の`presentedFrames`の飛びから数えるフレーム数である。
試作が使ったdeinterlacerは、その飛びを検出すると3フレームの履歴とfilm判定をリセットするため、位相の誤lockだけを原因とする根拠はない。
毎秒のstatsしかなく、フレームが飛ばされた理由や、同一区間内のmode変更との前後関係は未確定である。試作は採用せず、rVFCと履歴リセットをframe単位で照合してから対策を判断する。[既存5走行の再集計・counterの定義・source hash](results/galaxy-autofilm-callback-loss-review.json)を保存した。

[rVFCの仕様](https://wicg.github.io/video-rvfc/)は、callbackを描画更新に合わせて実行するが、各frameへ厳密に追従する保証はしない。
したがって`missed`をTSやdecoderの欠落と同一視せず、callbackの処理時間、遅れて呼ばれた時間、GPU読出しの待ち時間を分けて調べる。

## 連続 seek とキャンセル

通常のドラッグmoveはseekを送らず、指を離した時点で確定する。
複数回の確定や連打では、[worker.ts:486](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/worker.ts#L486) がAbortControllerをabortし、leg番号を進め、古い変換結果を無効化する。
probeと本体requestにはabort signalが渡る。
未配布のpicture jobは捨て、pool自体は再利用する。

[pool.ts:130](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/pool.ts#L130) の通り、すでに各Workerで実行中のWASM picture変換は途中停止できない。
そのpictureが終わってから新しい仕事に参加する。
poolなしの同期WASM処理中は、そもそもseekメッセージの処理開始が遅れる可能性もある。
1回のWASM入力chunk上限は1 MiBで、chunk間にはMessageChannelでevent loopを譲る処理がある。
キャンセル未実装ではないが、古いpictureの残余計算時間はT1→Worker受理や最初のGOP変換時間へ現れ得る。

## 実測できた範囲

### ローカルKonomiTV全体と実DPlayer UI

公式コンテナへ最新checkoutからbuildしたclientをread-only mountし、録画DB、`VideoDownloadAPI`、Starlette `FileResponse`、mpeg2toh264、MSE、Chrome decoderを通した。
詳細なイベント列は[device-results.md](results/device-results.md)に記録した。
実backendの該当Range応答はローカルaccess logで確認した。
生ログはLAN内情報を含むため公開せず、必要なstatusとRangeの結果だけを本報告へ転記した。
KonomiTVの保存済み画質設定では初期選択が`1080p` HLSだったため、DPlayerの画質UIから`Original (MPEG-2)`を明示的に選び、access logが`/api/streams/video/...`ではなく`/api/videos/2/download`の`206`になったことを確認してから測定した。

過去のGalaxy測定を監査すると、検証用の設定・視聴タブを閉じずに次のタブを開いた走行があった。
実際に古い設定タブのinputは有効なのに、新規視聴タブの`localStorage`は無効へ戻る不一致を確認した。
古いPinia状態の再保存だけでなく、Worker、MSE、decoder、canvas処理の残留も除外できない。
このため、Galaxyのend-to-end絶対時間は、開始前のCDP page targetが0件、測定中は対象の視聴タブ1枚だけであることを確認して取り直した次の値へ更新する。

| 素材と条件 | n | response中央値 | first AU中央値 | first fragment中央値 | appended中央値 | 可視canvas初描画中央値 / p90 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 乃木坂工事中、600/900秒台、`autoFilm:false` | 10 | 50.3 ms | 115.8 ms | 128.6 ms | 138.1 ms | 215.2 / 261.3 ms |
| MADDER #08、420/900秒台、`autoFilm:false` | 8 | 52.3 ms | 119.4 ms | 144.8 ms | 163.2 ms | 267.4 / 311.4 ms |

ここで初画は、YADIFのWebGL2 contextがdefault framebufferへ最初に`drawArrays()`した時刻である。
その時点で`.dplayer-video-wrap-aspect`のopacityは全走行`1`、`watch-player--loading`はなく、DPlayer spinnerは`display:none`だったため、canvasは隠されていなかった。
MADDERでは中央のbuffering表示が重なったが、canvas自体は表示され、初描画中央値267.4msに対して`playing`中央値は284.1msだった。

既存timing eventの`presented`は、append後のrVFCであっても`video.seeking`中のcallbackを捨てる。
MADDERでは目的位置のframeがcanvasへ描画済みでもこの条件で約200ms待ち、旧表の449.8msは画面初描画ではなく「seeking解除後に受理したrVFC」の中央値だったため、初画指標から外した。
同じ単一タブ内で`autoFilm:false/true`を6回ずつ交互にしたcanvas初描画中央値は269.4 / 251.1msで分布も重なり、今回の約200ms差をIVTC待ちで説明する仮説は支持されなかった。

既存`presented` event同士では、乃木坂の旧10回値245.8msに対して単一タブ値252.4ms、MADDERの旧10回値488.9msに対して単一タブ値449.8msだった。
1バッチ同士なので差をタブ競合の効果量とは断定せず、旧値を主結果から外す。
MADDERの各seek後には`video`と`film`の両方が現れ、定常7標本も`film` 6回の後に`video`へ遷移したため、420秒台と900秒台を含め録画全体を24fpsとは扱わない。
従来のtiming eventは[Galaxy LAN単一タブ再測定](results/galaxy-lan-single-tab-seek.json)、raw rVFC・canvas draw・可視状態を加えた全イベントは[可視初画再測定](results/galaxy-lan-single-tab-visible-frame.json)に保存した。

KonomiTVと録画TSが同じPCにある利用条件を再現するため、乃木坂工事中をサーバー側ローカルNVMeへコピーし、コピー元とSHA-256が一致することを確認した。
この素材を使い、完成fragment早期受け渡しだけを除いた基準版と追加した候補版を、Chromeのタブを各blockで閉じるB-F-F-B順で比較した。
計測専用hookからDPlayerの通常`seek()`を300秒と450秒へ1回だけ呼び、UIバーの座標誤差と時刻進行を除いた。
この走行では`playing`が出ておらず、停止状態のplayer内部比較である。

| target | 指標 | 基準 B1/B2 | 候補 F1/F2 | 候補平均−基準平均 |
| ---: | --- | ---: | ---: | ---: |
| 300秒 | first fragment | 83.7 / 81.3 ms | 76.2 / 78.6 ms | −5.1 ms |
| 300秒 | `presented` | 964.2 / 958.3 ms | 957.2 / 956.5 ms | −4.4 ms |
| 450秒 | first fragment | 69.0 / 62.4 ms | 65.3 / 75.8 ms | +4.9 ms |
| 450秒 | `presented` | 960.9 / 960.6 ms | 961.9 / 961.3 ms | +0.9 ms |

ローカルSSDでは最後のprobe完了が7.9〜17.2ms、本体first byteが14.0〜20.8ms、first fragmentが62.4〜83.7msだった。
したがって、以前のCIFS 128KiB probeが0.27〜0.59秒だった結果は、KonomiTVと録画が同じPCにある主条件の性能値として使わない。
候補版は300秒でfirst fragmentを平均5.1ms早めたが、450秒では平均4.9ms遅く、一貫した効果を示さなかった。
両版とも`presented`が約0.96秒に揃ったが、停止状態かつ前景性を確定していないため、この値を利用者が見る初画待ちとは扱わない。
完成fragment早期受け渡しの評価には、変換までのfirst fragmentと既存の前景Galaxy可視canvas測定を使う。
段階別データは[ローカルSSD early-fragment A/B](results/chrome-local-ssd-early-fragment-ab.json)に保存した。

各blockの最初に行った600秒seekはF1とB2で10秒以内に`presented`が出ず、次のseekで解消した。
variantの一方だけには偏らなかったため、完成fragment早期受け渡しの回帰とは断定せず、初回seekの独立したstall候補として残す。

以下の古い単発・連続UI測定は、UI入力からplayer受理までの経路と要求キャンセルの観察には使うが、タブ数を記録していないため現在のGalaxy絶対レイテンシ代表値には使わない。

Galaxyの「乃木坂工事中」1200秒への単発seekでは、実画面の`touchend`から`seeking`まで15.9ms、最初に観測したvideo frameまで270.1ms、`seeked`まで311.6ms、`playing`まで319.4msだった。
直後に4本の`206`完了を記録し、最初は`touchend`から126ms後だった。

異なる3位置を150〜180ms間隔で確定した連続seekでは、各`mouseup`から`seeking`まで7.0、4.9、4.4msだった。
最後の操作から`seeked`まで223.2ms、最初に観測したframeまで239.2msで、古い2操作の`seeked`は発生しなかった。
ただしサーバーには3本ずつ、計9本の即時`206`が到達しており、abort済みprobeの短いI/Oまで必ず消えるわけではない。

デスクトップの実DPlayer UIでは、`mouseup`から`seeking`まで52.8ms、`playing`まで286.2msだった。
Chrome拡張タブがbackground扱いになったため、rVFCで観測した536.7msは前景Galaxyとのdecoder比較には使わない。

計測branch `feat/seek-timing-context`を最新KonomiTVへ組み込んだGalaxy実UI seekでは、`touchend`からplayer受理まで10.2msだった。
player受理を0msとした内訳は、probe request 1.0ms、probe headers 47.7ms、probe body完了50.6ms、本体request 50.9ms、本体headers 60.7ms、first byte 61.3ms、first fragment 149.7ms、MSE appended 159.8ms、playing 298.3msだった。
この位置はwarm indexによりprobe 1本で収束した。

同じGalaxyからWi-Fiで隔離backendへ直接接続した600、900、1200秒では、全点が2 probeで、first byteは137.5、74.1、91.6ms、fragmentは225.0、154.9、185.7ms、rVFCは339.0、208.2、254.6ms、playingは334.8、197.3、265.9msだった。
`adb reverse`の同端末走行よりfirst byteが約30〜61ms長く、直列probeのRTTとbody待ちがLAN利用時には無視できない。
それでもfirst byte後の変換に約81〜88ms、append後のdecoder提示に約30〜101msを要し、ネットワークだけが支配した結果ではない。

3修正を合成した旧Galaxy実機確認では、乃木坂工事中1200秒が`touchend`からrVFC 311ms、playing 323.6msで復帰し、その後59.13〜60.13fpsを維持した。
MADDERは24fpsモードを一時的に有効化した900秒候補区間でrVFC 193ms、playing 219.4msとなり、以後のfilm標本は主に23.27〜24.58fpsだった。
これらもタブ数を記録していないため、上の単一タブ再測定へ絶対時間を置き換える。
乃木坂のCM/本編やMADDERの全区間へ、このカデンス判定を一般化しない。

### ローカル TS とネイティブ core の bounded 試験

最新依存`52a3db5e`のfresh Sessionへ「ばけばけ」の0%、50%、80%付近から64KiBずつ入力した補助試験では、初回fMP4まで1,835,008 / 1,966,080 / 1,179,648 B、123.1 / 152.5 / 112.6msだった。
この試験もHTTP、WASM、picture Worker pool、browser decoderを含まない。

以下は調査初期に旧フォークcommit`7134c2ae`で、GOP境界まで追加計測した結果である。
該当するGOP/AAC保持ロジックは最新依存でも同じだが、最新commitの性能値としては使わない。

素材は `LIFE!`の短い録画TS。
ファイルサイズ132,655,620 bytes、FFprobeのdurationは75.3759秒、MPEG-2、1440×1080、TFF、30000/1001fps。
FFprobeは開始付近で `Invalid frame dimensions 0x0` 警告を出した後、上記stream情報を取得した。
無傷な先頭という前提は置いていない。

core `7134c2ae` のソースを `/tmp` にRust 1.93.0 / `rustc -O`でビルドし、AMD Ryzen AI Max+ 395 / x86_64で実行した。
ファイルの0%、50%、80%のbyte位置からそれぞれ8 MiBだけをメモリへ読み、64 KiBずつfresh Sessionへ渡した。
service=43008、通常のAAC付き変換、default TranscodeOptions、picture poolなし。
この位置決定は**実playerのPTS補正seekではない**。
timeline originも各sessionで求めており、fragmentの `start` は本編の絶対seek時刻ではない。
別passのdemux / GOP splitterで初回video PES、最初と2番目の完成GOPの入力位置を記録した。
閾値の粒度は64 KiBである。

| 開始byte | 初回video PESまで | 完成GOP 1個目まで | 完成GOP 2個目 / 初回fMP4まで | native初回fMP4、3回 |
| ---: | ---: | ---: | ---: | --- |
| 0 | 327,680 B | 1,638,400 B | 2,490,368 B | 134.764 / 133.087 / 131.021 ms |
| 66,327,810 | 262,144 B | 1,572,864 B | 2,293,760 B | 139.756 / 139.369 / 139.727 ms |
| 106,124,496 | 458,752 B | 2,228,224 B | 3,080,192 B | 121.420 / 120.996 / 121.352 ms |

全ケースで最初のfragmentは `random_access=true`、video_samples=14、audio_samples=46/48/62。
出力fragmentは約1.84〜2.09 MiB。
最初の完成GOPができてから初回fMP4まで、さらに720,896〜851,968 bytesを読む必要があった。
この素材では「GOPを1個余分に保持する」というコード上の条件が、実際の初回出力条件にも現れた。
本試験はその条件を外した改善効果や、出力H.264の実機復号成功までは検証していない。

8 MiBのCIFS読み込み時間は各位置で173.635 / 127.520 / 116.878 msだった。
cacheを制御しておらず、open時間も含めず、HTTPを経由せず全8 MiBを先に読む試験なので、これをseekのnetwork latencyへ加算してはいけない。
native変換時間もAndroid / WASM / poolの時間へ換算できない。
初期GOPとA/V条件に必要な入力がMB単位になること、および変換が無視できるゼロ時間ではないことの参考値である。
詳細は [native-results.txt](results/native-results.txt)。

各8 MiB入力窓のSHA-256は以下。元ファイル全体のhashではない。

| 開始byte | SHA-256 |
| ---: | --- |
| 0 | `4aa1cb4437582ef356823b83df86262e82dd45d45ce01e16886e3110241fd1be` |
| 66,327,810 | `1f2070c51a2a1f18c9a9b4186cc52fae9f761370fc82741a0907fc5e500943a9` |
| 106,124,496 | `1cda799bdf0eafb5f6f045a4a52bc1fd519cdca6b133e60b91d1afd878953d4f` |

### ChromeとGalaxyの実測

詳細な条件、素材hash、全表は[device-results.md](results/device-results.md)に記録した。
既存の素材別表は最新clientと検証用Rangeサーバーを使った区間比較で、T0は検証ページが`video.currentTime`を設定する直前である。
それとは別に、公式KonomiTV backendと実DPlayer UIを通したデスクトップ/Galaxy計測を追加し、指離しからのT0/T1も確認した。

デスクトップChromeの「ばけばけ」4点は安定判定102〜202msだった。
Galaxyの旧素材別測定はタブ数を記録していなかったため、絶対時間の代表値から外す。
単一タブで取り直した最新KonomiTV実DPlayerの可視canvas初描画中央値 / p90は、乃木坂工事中215.2 / 261.3ms、MADDER 267.4 / 311.4msだった。
旧長時間TS 3点の360〜423msは、永続index仮説に対するprobe数と段階比率の参考には使うが、現在の端末絶対値には使わない。

長時間TSでは全点が2本の128KiB probeで収束した。
T0→responseは97〜115ms、response→first fragmentは155〜224ms、first fragment→frame提示は48〜118msだった。
通常のMSE clear/append自体は多くの点で数ms〜十数msだが、その後の`playing`/frame提示まで数十〜100ms程度残る。
今回の条件では、PTS probe単独、MSE remove単独、YADIF初画待ち単独のどれも全体を支配しなかった。

SourceBufferの個々の`remove()`開始と`updateend`は内部instrumentationしていない。
公開commit `0ce89d7`でseek ID、target、probe request/headers/body、本体request/headersを公開eventへ追加したが、`appended` markは最初の有効bufferができた時点で、init/media各operationのT7/T8を完全には分離しない。
MediaCodec内部のflush/reconfigure、GPU scan-out、聴感による実音声T11も未測定である。

## 計測を追加する位置

既存の `timing` eventは `seek / response / first-byte / first-fragment / opened / appended / playing` 等を通知する。
時刻はcontext間を比較するためepoch基準でWorkerから渡し、公開eventでは `sinceLoad` になる。
`sincePrevious` は複数contextのevent到着順に依存するので、各段階の時間差としてそのまま使わない。
seekごとのID、target、buffer内外、leg IDを紐付け、同じseekの絶対時刻同士を引く。

| 時点 | 計測位置 | 現状と注意 |
| --- | --- | --- |
| T0 UI確定 | DPlayer `thumbUp` 冒頭 | pointerを離したeventと、そのhandler実行時刻を分ける |
| T1 player受理 | DPlayer `seek`、`Mpeg2TsPlayer.#onSeeking` | `0ce89d7`の`seek-requested`でplayer受理、`seek`でWorker受理を分離。UI `thumbUp`はKonomiTV側で紐付ける |
| T2 request開始 | `source.ts` の `readRange` と `openSource` の `fetch` 直前 | `0ce89d7`の`probe-request`と`request`で実装。seek ID、attempt、offset、lengthを持つ |
| T3 headers / 初回body | probe observerと本体readerの最初のread | `probe-response`、`probe-complete`、本体`response`、`first-byte`で分離済み |
| T4 利用可能開始点 | Rust demuxのPAT/PMT確定、GOP splitterの初回unit確定、`take_ready()`がReadyを返す直前 | 一点へ潰さず `tables / first-gop / audio-ready` を分ける。累積bytes、PID、GOP PTSも記録 |
| T5 最初のH.264 AU | picture Workerのencode完了、またはRust encoder出力境界 | poolのrun ID / job indexとI-pictureを関連付ける。全GOP完了とは別 |
| T6 初回fMP4 | `Session::finish_gop/package` とWorker `first-fragment` | Rust内完成とJSへ返る時刻の差も見る。既存markはconverter.pushの返却後 |
| T7 append | `MseSink.#pump()` のappendBuffer直前 | init/media/old-new世代とbyte数を分ける |
| T8 updateend | `#onUpdateEnd` 冒頭 | clear/init/mediaの別と、完了したoperation自身の世代を記録。既存 `appended` は最初に有効bufferができた時点 |
| T9 frame提示 | video rVFC | seek先と一致するmediaTimeを選び、processingDuration等を記録。decode完了そのものとは呼ばない |
| T10 progressive描画 | YADIF `#render` の直接canvas経路、`#show`、native video経路 | draw呼び出しはGPU完了や画面scan-outではない。正確な表示はtraceや外部撮影が必要 |
| T11 音声再開 | `playing` / media time進行は補助。実音声はaudio traceか外部収録 | JS標準eventだけでスピーカーの実出音を確定しない。無音区間ではsignal検出も再開指標にならない |

clear開始/完了、probe開始/headers/body完了、最初の有効video時刻、要求targetとの差も記録する。
既存statsの `readingMs / waitingMs / conversion` は区間集計なので補助指標として使う。
全seekは `T9−T0`、`T10−T0`、音声の確認可能なproxy、連続再生へ安定するまでを別々に集計する。
1回だけの最短値でなく、buffer内/外、同じ場所の再seek、前後方向、連続確定を分けてmedian/p95を見る。

Galaxyで540秒と900秒を交互に30回seekした順次比較では、YADIF再同期だけの初画中央値305.5ms・playing中央値297.4msに対し、完成fragment早期受け渡しを加えた版は277.4ms・269.5ms、MSE世代修正も加えた版は273.6ms・267.0msだった。
YADIF停止はいずれも0/30だった。
build順をランダム化しておらず、当時のタブ数も記録していないため、約28msを早期受け渡しの効果量または現在の絶対時間として使わない。
MSE追加の数msも速度効果と判定しない。
停止が修正後0/30だった事実と、デスクトップ同一位置でfirst fragmentが約9〜10ms短縮した別測定は残す。
各走行は[Galaxy優先修正比較](results/galaxy-priority-fixes.json)に保存した。

古いタブを排除したGalaxyでは、完成fragment早期受け渡しだけが異なる基準・修正版を8ブロック、各40 seekで比較し直した。
各ブロックは開始前後のpage targetを0件へ戻し、測定中は前景の視聴タブ1枚だけとし、順序を基準・修正・修正・基準・修正・基準・基準・修正にした。
全80 seekは学習済み位置から1 probeで、本体response中央値は50.7→54.5ms、first fragmentは133.5→140.2ms、append完了は144.1→150.2ms、可視canvas初描画は257.1→274.5msだった。
修正版−基準版の中央値差に対する30,000回bootstrap 95%区間は、first fragmentが−2.0〜12.4ms、可視canvasが−9.0〜37.3msで、いずれも0を含んだ。
したがって、この端末・素材では初回fragmentまたは初画の短縮を確認できず、旧Galaxyの約28ms差を修正効果として扱わない。

一時的に早期通知callbackへmarkを入れた10 seekでは、最初の早期通知がfirst fragmentより前に来た走行は0/10で、差の中央値は+227.2msだった。
現在の実装が重ねるのは2個目以降の完成fragmentと後続処理であり、seek後の初画に必要な最初のmedia fragmentを早く渡していなかった。
変更は後続fragmentのthroughput候補として残すが、初画改善としての優先度はP2へ下げる。
全イベントと一時markは[単一タブ早期受け渡しA/B](results/galaxy-early-fragment-single-tab-ab.json)に保存した。

同じqueue再同期版と完成fragment早期受け渡しを組み合わせ、MADDERの420秒と900秒をfilm候補として交互に10回seekした。
全走行で初画が返り、中央値280.5ms、最大310.0msだった。
最後の1走行ではqueue resetが発生したが271.7msで初画が返った。
120秒と1500秒ではvideo/filmが切り替わったため、番組全体を24fpsとみなす根拠にはしない。
各走行は[MADDER film候補の計測](results/madder-film-seek.json)に保存した。

### picture jobと2個目のfragment

integration `47cca29`とKonomiTV `e92fba8`を基準に、診断用markだけを加えたbuildでpicture Workerごとの処理時間を測った。
素材はローカルSSD上の乃木坂工事中、Chrome全画面、LAN直結、既定と同じ4 Workerである。
Windowsは電源モード「最適な電力効率」の補助条件で、各preflightのCPU負荷中央値は3〜7%だった。
180〜184秒と480〜484秒を交互にseekし、各端末でwarmup後10回を測った。

Windowsの180秒側は、要求からfirst fragment中央値167.1ms、second fragment 262.0ms、second media updateend 272.8ms、`canplay` 298.2ms、表示復帰293.7msだった。
480秒側は最初のfragmentだけで`canplay`でき、表示復帰中央値221.5msだった。
同じbuildのGalaxyは180秒側でも表示復帰中央値160.6msで、second fragment中央値172.8msより前に目的canvasを描画できた。
したがって2個目のGOP待ちは全端末の固定条件ではなく、seek先が最初のfragment末尾に近いことと、Chromeのdecoderが最初のfragmentだけで目的frameを提示できるかの組み合わせで発生する。

各GOPは13〜15個のpicture jobを持ち、Windowsではindex 0と概ね3個ごとの大きなjobが25〜55ms、その他が7〜16msだった。
job byte数とencode時間のPearson相関は、Windowsの最初のGOPで0.957、2個目で0.912、Galaxyで0.947 / 0.890だった。
Workerへの投入から応答までの時間からWASM encode時間を引いた中央値は0.2〜0.3msで、転送は支配的でなかった。

byte数の大きいjobから投入する試作は、Windows 180秒側のfirst→second fragment中央値を94.0→91.8msと約2.2ms短縮したが、表示復帰は293.7→293.8msで変わらなかった。
4 Workerのsecond fragment後に50msの空白を置く診断も、second updateend→`canplay`が25.4→24.0ms、表示復帰が293.7→296.5msで、既定4 Workerのdecoder競合を支持しなかった。
一方、7 Workerはsecond fragmentを220.8msまで早めても表示復帰が312.3msへ悪化し、100msの診断用空白で276.4msへ戻った。
既定上限4は変換とdecoderのCPU競合を避ける役割を果たしており、単純なWorker増加は採用しない。

Windowsの該当位置をさらに短縮するには、2個目のGOP全体の完了を待たず、目的frameに必要な先頭pictureをfMP4へ確定する設計が必要になる。
現行`IncrementalTranscoder::complete()`は全pictureの成否から破損pictureを再計画し、全access unitを組み立てた後に`Session::finish_gop()`が音声とtimelineを含むfragmentを確定する。
部分出力は、破損判定、transcoder state、音声境界、MP4 sample timelineを分割して保持する必要があり、小変更ではない。
[集計と全走行](results/picture-job-critical-path-analysis.json)に、Windows / Galaxyの4 Worker、投入順試作、診断用CPU空白、7 Worker比較への参照を保存した。

## 仮説の評価と優先順位

実測を含む通常seekの候補順位は、(1) append後のdecoder提示、(2) GOP/AAC収集と最初のIDR jobを含む初期H.264/fMP4生成、(3) PTS probeとrequest往復、(4) PAT/PMTとheader再取得、(5)連続操作の残余計算である。
上位二つは位置と端末で順序が入れ替わる。
単一タブ再測定の中央値では、最初のpicture jobsからstream先頭AUまで乃木坂38.8ms、MADDER39.9msだった。
appendedから可視canvas初描画までは乃木坂77.1ms、MADDER104.2msだった。
MADDERの既存`presented`が示した約268.5msは`video.seeking`解除を待つ計測条件の差で、decoder・IVTCがその時間だけ初画を止めていた証拠ではない。
デスクトップの追加走行でもfragmentからappendは1.5ms、appendからcanplayは227.3msだった。
通常のMSE append自体より、初期IDR変換とdecoder準備の変動が大きい。
Androidの継続的な不滑らかさは別問題だが、opaque canvasによるvideo callback抑制という当初説明は追加計測で否定した。
MSE queue競合も通常時の平均ランキングとは別の、再現できたstall要因として扱う。

| 仮説 | 評価 |
| --- | --- |
| 1. indexなしの探索が最大要因 | 単独の最大要因ではない。永続GOP indexはないが、メモリ内PTS indexと最大4回の小Rangeがある。43GB素材でも2 probe、約0.1秒で収束した。ただしprobe標本を後のfragment時刻で上書きする欠陥は、最新のGalaxy B-F-F-Bで追加probe 14/40→0/40、browser提示と可視canvasのtarget対応中央値−71.3msとなった。修正版canvas中央値244.3msは当時の250ms判定内だが、現行の200ms目標は満たさず、p90も280.7msなので、探索後のdecoder tailも残る |
| 2. RAP不一致の余分な読み込み | 確認。offsetはRAP未整列。本体Rangeは初画までに数十MiBを読み、tables/PES/GOP再取得とA/V条件を含む。RAP indexで短縮余地はあるが後段は消えない |
| 3. MSE remove/flushが支配的 | 通常時の単独支配は否定寄り。clearとprobeは並行し、append markまで数ms〜十数msの点が多い。別途init喪失のqueue競合は再現・修正済み |
| 4. PAT/PMTの毎回再探索 | 確認。sessionを作り直すため。ただしWASMとWorker poolは再利用 |
| 5. IDR/recovery待ち | 初期IをIDR化するまでの入力と計算は必要。24 GOP周期待ちではない。最新のjob粒度計測では、WindowsとGalaxyの両方でjob byte数とencode時間の相関が0.89〜0.96、Worker往復の追加時間は中央値0.2〜0.3msだった。Windowsの一部seekは目的frame提示に2個目のGOP全体を必要とし、変換とfragment境界がcritical pathになった |
| 6. YADIF/IVTCの過剰な初画待ち | 正式buildの単一タブ乃木坂A/Bで描画10fps未満18/90→0/90、複合異常35/90→1/90となり、queue再同期によるseek直後の描画改善を確認。MADDER A/Bでは`autoFilm:false/true`のcanvas初描画分布が重なり、IVTC固有の初画待ちは支持されなかった |
| 7. 古い処理のキャンセルがない | abortと世代判定あり。ただし実行中WASM pictureは完了待ち、同期処理中のevent配送も遅れ得る |

## 実装済み変更と提出先

upstream向けに分離した候補に加え、フォーク固有YADIFのqueue容量確保と時刻再同期を分ける変更を別branchにした。
公開`fix/separate-yadif-queue-recovery`は、stall防止を立証した前身の全resetを、容量不足時の最小FIFO破棄と時刻同期破綻時の全resetへ分けた後継候補である。
後継の公開後、前身`fix/restore-yadif-queue-reset`は誤取り込みを防ぐためremoteとlocalから削除し、commit IDと測定結果だけを本調査記録へ残した。
YADIF opacity変更は棄却した実験である。
upstream向け候補branchは`otya128/mpeg2toh264`の`upstream/main`（`d5df08b`）へ適用できる形で公開した。
MSE修正とfragment早期受け渡しでは、tsukumijimaフォーク側の追加scriptと`package.json`の文脈だけが衝突するため、upstream用PRではscript登録を現在のupstreamに合わせて作り直す。

各修正の目的、修正内容、効果、実装の重さは[統合検証branchのREADME](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes#pr候補)にある。
提出の順位と、まだ提出しないものの理由は[README](README.md#提出の順序をどう決めたか)にある。

YADIF初回fieldの保持`d4ccb98`は本調査の候補ではなく、すでに`tsukumijima/mpeg2toh264`へ取り込まれ、KonomiTV固定依存`52a3db5`に含まれる既存の変更である。
cleanな不透明版は30秒と12秒で約60fpsを維持したが、この変更単独の同条件A/Bによる効果量は未確定である。

公開中のupstream向け候補ブランチは、すべて`upstream/main`（`d5df08b`）を土台として再構成した。
各公開refについて`upstream/main`が祖先で、`konomi/main`（`52a3db5`）が祖先でないことをGitHubへのpush後に読み戻して確認した。
upstreamは生成済み`dist`を追跡していないため、公開branchにはsource、README、必要な回帰試験だけを含める。
tsukumijimaフォークには、upstream採用前のbackport、またはフォーク固有API・YADIF拡張との接続だけを別branchで残す。

KonomiTVに出す変更は、Original再生UIのT0計測、download handlerのDB/stat/open/first body計測と実測に基づくI/O修正、必要性が確認された場合のrecording単位sidecar保存である。
DPlayerには今回修正を実装しておらず、現時点で直接PRにする根拠もない。

この表は、まだ提出していない候補だけを扱う。提出済みの7件は上のREADMEにある。

| Priority | 改善案 | 期待効果 | 実装難易度 | upstreamに出しやすいか | 所有者 |
| --- | --- | --- | --- | --- | --- |
| P2 | field時刻を各rVFCの`expectedDisplayTime`へ再アンカーする | 旧条件では過渡最低値が良かったが、単一タブA/Bは未実施 | 中 | △ | 比較実験。upstream復元後も過渡低下が再現する場合だけ再検討 |
| P2 | 初回fieldのleadを2 fieldから1 fieldへ戻す | 短い3走行では59.64〜59.84→59.98〜60.00fpsだが、reset条件が混在 | 小 | △ | `d4ccb98`の効果を長窓A/Bで再評価。新規修正とは扱わない |
| P2 | probeを選択service/video PID優先にする | 複数service TSで誤ったPTSを採る可能性を下げる | 中 | ○ | mpeg2toh264 source/core。標本上書き修正とは分離 |
| P2 | 初回IDRを独立slice/jobへ安全に分割してpicture poolで並列化する | 現在33〜40msの単一critical jobを短縮する余地。画質・bitstreamは変わり得る | 大 | △ | mpeg2toh264 core/job protocol。slice境界、intra予測、Safari/VideoToolbox検証が必要 |
| P2 | 有効probeを本体へ再利用、PTS検出後にprobe読取を止める | 重複128 KiBと待ちを削減。RTT自体は残る | 中 | ○ | mpeg2toh264 source/worker |
| P2 | 入力queueの32/8 MiB high/low waterを小さくする | seek後の不要な先読みと連続seek時のI/O競合を削減。初画短縮は未確認 | 小 | ◎ | mpeg2toh264 Worker。8/2 MiB試作は未採用 |
| P2 | 選択範囲のbufferを保持するseek、clearを必要範囲に限定 | 再seekの再変換削減。removeが支配的なら有効 | 中〜大 | ○ | mpeg2toh264 MSE。RAPとoverlapを再設計 |
| P3 | download handlerのDB/stat/open、chunk sizeを計測して必要箇所だけ改善 | 64〜1024KiB sweepはGalaxyで非単調、Windowsで中立。別transport/storageで再現した場合だけ再検討 | 小〜中 | △ | KonomiTV。Starlette一般問題は同upstream |
| P3 | AAC必要量が揃った完成GOPを次GOP境界前に出す | 単体では入力を320〜512KiB削減したが、GalaxyとWindowsのfragment生成・可視初画を短縮しなかった | 中 | △ | mpeg2toh264 Session。実機B-F-F-Bで不採用 |
| P1 | coreが実際のGOP/RAP byteを返し、再生中のin-memory indexへ学習する | 要求時刻以前に近いRAPが実在する地点ではdecoder discardを減らせる可能性。Windows 180秒地点は現行indexですでに最適で短縮不可 | 中 | ○ | mpeg2toh264 core/player。byteをRange先頭へ誤対応しない契約が必要 |
| P2 | 永続sidecarと有効なstream configを持つseek resolver | cold seekのprobeと、近いpre-target RAPがある地点の復号を削減。GOP cadenceで次候補がtarget後になる地点は短縮しない | 大 | ○ | KonomiTV固有保存、playerの汎用API |
| P2 | 初回のsub-GOP fragment、video/audioの段階投入 | Windowsの該当位置で約90msの2個目GOP全体待ちを短縮し、初画の理論的な下限を下げ得る | 大 | △ | mpeg2toh264 core/player。破損再計画、state、音声、MP4 timelineの分割が必要 |

P2のAAC/GOP保留変更は、単に条件を消してよいという提案ではない。
音声が遅れて多重化されるTS、mono/stereo/5.1変更、dual mono、PTS wrap/discontinuity、open GOP、field picture、破損素材、異なるMSE実装で確認する。
初回fragmentだけでなく全fragmentのA/V時刻と内容を比較し、速さと同値性を分けて検証する。
SourceBufferの同時remove/appendはできないので、同じbufferへの操作の並列化は提案しない。
既存のclearとnetworkの重なりを保ち、不要なclearやqueue待ちの削減を検討する。

### 小改善候補のメモ

採用していない案も消さず、現在の根拠と再評価条件を残す。
優先度を下げることと候補から削除することは分ける。
候補を削除できるのは、同条件の計測で効果がないことを確認した場合、正しさを壊すことを再現した場合、または上位案へ完全に包含されたことをコードで確認した場合だけとする。
その場合も、結果と証拠への参照を先に残してから状態を変更する。

| 案 | 現在の見込み | 保留理由・次の確認 |
| --- | --- | --- |
| probeでPTSを得た時点で128KiB全体の到着待ちを止める | LAN走行の6 offset中5点は先頭32KiB、全点は64KiB以内でPTSを取得できた。2 probeなら後半64KiBを2回省ける可能性 | RTTと次の直列probeは残る。stream reader化後にcancelしたresponse量とprobe-completeを同条件で測る |
| 最後のprobe byte列を本体変換へ再利用する | 128KiBの重複取得削減 | probe位置と採用offsetが一致する場合だけ有効。sessionへprefix入力する契約が要る |
| 実際に採用したGOP/PES byteをcoreから返してindexへ追加する | probe標本に加えてRAP近傍の対応点を増やせる可能性 | Windows 180秒地点では現行restart indexが次候補も把握できるが、開始がtarget後なので選べない。未知のpre-target RAPを取り逃す素材を再現してから追加する |
| seek直後の後続GOPをrandom access化し、要求時刻を含むfragmentからappendする | `appended`→`canplay`中央値101.4→33.3msでdecoder discard自体は減った | 第2fragment生成待ちがtarget対応中央値+69.8msとなり、可視初画は中央値+5.7ms、平均+1.3msで改善なし。10地点中5地点は要求時刻を越えたため、この方式は採用しない。変換前に正確なRAP byteを得る案へ置き換える。[生値](results/galaxy-recovery-fragment-selection.json) |
| `walk_pts()`を選択service/video PID優先にする | 複数service TSの誤probe削減 | PAT/PMT不要の短いprobeという利点を失わない設計が必要 |
| PAT/PMT、PID、sequence/AAC configをseek間で再利用する | 初回fragmentまでのscan短縮 | 放送中のPID/config変更とdiscontinuityをepochで拒否できる契約が必要 |
| packet欠落前に完了を確認できるpictureを保持する | Galaxyの同条件各2走行で、FPS安定復帰までの最大映像時刻間隔が567.233〜600.600→333.666ms、Chrome dropが17→6 | 公開候補[`fix/preserve-complete-pictures-before-loss`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-complete-pictures-before-loss)は、次のpicture開始位置を受信済みのprefixだけをtranscoderへ渡す。実在するopen GOP内のframe picture欠損と、固定interlaced・open-GOP fixtureのSession試験は確認済み。実在するfield picture破損、画素、A/V同期、異常TSの1時間条件を確認してからintegrationへ入れる。[A/B結果](results/galaxy-anomaly-preserve-complete-pictures-ab.json) |
| AAC必要量が揃った完成GOPを早く出す | 単体では初回fragmentまでの入力を320〜512KiB削減 | fragment内容は同一だったがGalaxyとWindowsの`first-byte`→`first-fragment`と可視初画を短縮しなかったため採用しない。[集計と生値](results/completed-gop-hold-analysis.json) |
| 録画TSの`FileResponse` body chunkを64KiBから増やす | Galaxyの一部条件で最大15.4msの対応付き差が出た | 64〜1024KiBで単調性がなく、Windows各40 seekは−2.4〜+1.7msで中立だったため採用しない。別transport/storageで再現した場合だけ再評価する。[集計と生値](results/file-response-chunk-size-analysis.json) |
| 完成fragmentを入力chunkの残処理より先に返す | 2個目以降のfragmentと後続変換を重ねられる | 単一タブGalaxyでは最初の早期callbackがfirst fragment後10/10で初画短縮なし。初回media fragmentを早める別設計と、output順序、picture pool、cancel、backpressureの確認が必要 |
| picture jobをbyte数の大きい順に投入する | job byte数とencode時間はWindows / Galaxyで強く相関した | Windows 180秒側のfirst→second fragmentは中央値約2.2ms短縮したが、表示復帰は293.7→293.8msで変わらなかった。正式変更にはせず、GOP内を部分出力する設計で優先jobを選ぶ場合の根拠として残す。[集計と全走行](results/picture-job-critical-path-analysis.json) |
| picture Workerを既定4より増やす | 7 Workerではsecond fragmentが中央値約41ms早まった | Windows 180秒側の表示復帰は312.3msへ悪化し、変換とdecoderのCPU競合を確認した。既定上限4は維持し、増加案は採用しない。[集計と全走行](results/picture-job-critical-path-analysis.json) |
| `maxAheadSeconds`を固定0.5秒へ下げる | 2個目のfragment後に既存backpressureを働かせ、decoder起動中の後続変換を止める | Windowsの180秒側は8秒版291.3ms、0.5秒版286.4 / 299.1msで短縮せず、0.5秒版の最大値は478.1 / 487.9msへ悪化した。0.1秒版は初回再生が`readyState=2`で停止したため、固定値の変更は採用しない。seek中だけの制御にはdecoder準備完了の通知と、2 fragmentで再生できない場合の再開条件が必要。[集計と全走行](results/windows-max-ahead-startup-diagnostic.json) |
| 入力queueのhigh/low waterを32/8 MiBから下げる | seek後の不要な読取量と、直後の再seekとの競合を削減 | Galaxyの8/2 MiB試作は初画を一貫して短縮しなかった。一方、canplay/playingまでの本体読込量は約38.4→11.4 MiB、別走行で約19.5→11.0 MiBへ減った。同じindex・probe数・decoder状態を揃えた連続seekで再評価する |
| MSE clearを全削除でなく対象範囲に限定する | 再seekで変換を省ける可能性 | 今回clear単独は支配的でない。RAPとbuffer overlap設計が先 |
| KonomiTV downloadのDB/stat/openを短縮・handle再利用する | NASのcold seekで数ms〜数十msの可能性 | warmな全backend計測では約0.3秒以内に復帰。cold cacheでDB/stat/open/first bodyを分離してから変更する |
| `autoFilm`のseek後lock/hysteresisを調整する | 3:2区間のmode安定を早める可能性 | 位相保持の試作は通常走行で23.97〜24.18fpsへ安定したが、MADDER #04の4走行中1回は58標本中57標本がvideo modeで、47.45fpsだった。この走行では`missed`が302増えた。検出時に履歴をリセットする実装のため、誤lockとは断定できない。復帰しない原因を分離するまで採用しない。[複数素材](results/galaxy-autofilm-multi-fixture-regression.json)・[入力欠落の再集計](results/galaxy-autofilm-callback-loss-review.json) |
| `autoFilm`解析の同期GPU読出しを減らす | rVFC間でフレームを取り逃すことを減らす可能性 | `#analyseFilm()`は1入力で2回`readPixels()`を行う。ただし各処理の所要時間と`missed`との関係は未計測であり、主因とは確定していない。fieldmatch・decimateの精度を変えずに短縮できるかは、待ち時間の測定後に判断する。 |
| seek直後だけ簡易deinterlaceにする | 初画数msの可能性 | 1〜2frame不足時の複製/直接描画は既に実装済み。通常は追加変更不要 |
| periodic IDR recovery copyをnon-IDR recovery pointへ変える | Galaxyでは120秒の`droppedVideoFrames`が40→0になり、YADIF 59.925fpsとmedia timeを維持 | counterは元TSの新しい表示画像に対応しない1 tick sampleをChromeが表示しないことを数え、可視40ms超間隔は1回残った。40 seekも既定IDRより安定して速くならず、hardware decoder互換性の広い検証なしには変更しない |
| queueが空のとき1入力frame分の固定reserveを置く | 120秒では40ms超1〜2回→0回、20 seekも20/20が250ms以内 | 600秒でclock差が蓄積し、`late` 2071、reset 2、最大11.15秒停止へ退行したため、この式は棄却。長窓とライブ追従を必須試験にする |
| YADIF queueを7 slotへ広げる | 600秒で59.940fps、40ms超0回 | future leadが最大約125msまで増え、容量依存の可変A/V差とライブ遅延になる。上限付きmedia-clock jitter bufferとして設計し直す場合だけ再評価 |
| 実行中picture jobを細粒度cancelする | 連続確定時の残余計算削減 | 通常のドラッグは指を離すまでseekしない。連打再現とjob時間の計測が先 |
| 目的時刻より後への着地を許し近傍RAPから再生する | 固定leadを1秒から0.5秒へ減らしたGalaxy 5地点の代理試験では、可視初画平均222.0→174.6ms、平均47.4ms（21.4%）短縮。約200msの応答に対する21%は官能評価対象として有意義 | 2/5地点で要求時刻より93ms、344ms先へ着地した。近傍RAP選択そのものではない非交互各5回の暫定値なので、upstreamの要求位置を欠落させない既定動作は維持する。固定leadの調整と直前RAP選択を分けて検証する |
| ユーザー時刻から固定量を引き、その時刻以後かつ元の時刻以前のRAPを選ぶ | `T-d`以後の最初のRAPが`T`以前なら、要求位置を越えず比較的新しいGOPを選べる | `T-d`を現行seek全体へ渡すだけではRange探索も前へ動くため速くならない。`[T-d,T]`にRAPがある保証も固定値だけでは作れない。RAP時刻を確認して`RAP <= T`を選ぶ方式として検証する |
| seekごとに4〜8MiBをscanして直前RAPを選ぶ | PAT/PMTを含む安全な開始点とMPEG-2 sequence/GOPを線形scanで求められ、約5MiBのscan自体は5.1msだった | Galaxyの300秒では現行と同じfragmentへ着地して221.4→240.3ms、900秒では概算が約7.4秒手前でRAPをbracketできずfallbackして191.1→238.9ms。毎seekの広域取得は採用しない。再生中に無償で学習するか永続indexから直接得られる場合だけ再評価する。[生値](results/galaxy-rap-probe-experiment.json) |
| IDR用`ReconstructedPicture`生成直後の重複`clear()`を除く | 理論上はplaneのzero fillを1回減らす | 80回交互測定で28.224→28.357ms、best 27.702→27.692ms、出力hash一致。効果なしと確認したため性能変更にはしない |

この表の案は、未検証または効果が小さいという理由で保留している。
候補自体を否定・削除したものではない。
重複`clear()`除去とseekごとの広域RAP scanは同条件の比較で効果がない、または遅くなることを確認したため、未検証候補ではなく採用しない案へ状態を変更した。
記録は削除していない。

### 未実施の高負荷試験

YADIF schedulerの余裕と復帰性を比較する試験は、次の順で追加する候補とする。

1. 100msごとに4、8、16msだけmain threadを止める。rAFとrVFCを同時に遅らせるため、UI処理、GC、短いtask集中に近く、周期的な長い描画間隔とFIFO破棄を再現しやすい。
2. CDP CPU 2倍throttling。renderer main threadの処理余裕を同一端末内で比較する。LinuxとGalaxyの倍率を同じ絶対性能とは解釈しない。
3. CPU 4倍、およびCPU 2倍と8ms/100ms stallの組み合わせ。通常条件で復帰境界が見えない場合の強い負荷とする。
4. Web WorkerのCPU競合。OS schedulerとthread競合を見る補助試験とし、MediaCodecやGPU負荷の代理にはしない。

現在の「presentationを1回おきに止める」注入は、rVFC入力を保ったままqueue制御だけを決定的に不足させる単体試験として残す。
周期stallはmain thread callback全体、CPU throttlingはrenderer main threadの処理余裕、Worker競合はOS thread競合を見るため、同じ結果を意味しない。
各条件は負荷前、負荷中、解除後に分け、canvas FPS、描画間隔p95/p99/最大、queue深度、FIFO破棄、全reset、presentation latenessを記録する。
解除後、2秒連続で理論FPSへ戻り、queueが基準+1以内、latenessが増えず、追加resetがない状態までを復帰時間とする。
これは未実施の診断試験であり、CPU throttlingもMediaCodec、GPU、別Worker、実際の熱・電力制御を一様に遅くするものではない。

## サイドカー index の判断と本格設計

**現時点では次に実装する必要はない。**
43GB素材でも2 probe、約0.1秒で収束し、初回fragment生成の方が長かった。
別のNAS・素材・cold cacheで最大4回のPTS probeが大半を占める、RAP未整列の余分な読み込みが大きい、または初回位置誤差が目標を満たせないと分かった場合に再評価する。
MSE競合やdecoder復帰が支配的ならindexでは解決しない。
既存Range seekの補正精度、GOP/AAC出力条件、初回fragmentの受け渡しを先に比較する。

導入する場合、KonomiTVがrecording単位の永続性を所有し、playerは汎用のseek location/config入力を受ける。
既存 `key_frames` / `segment_map` が必要精度と情報を満たすかを評価してから、別sidecarにするか決める。
HLS用segment mapをそのまま完全なGOP indexと見なさない。

保存候補はversion、file identity（size/mtimeに加え必要ならfingerprint）、TS packet形式、service ID、video/audio/PCR PID、tables/config変更epoch、timeline origin、PTS/DTS/PCRとwrap/discontinuity epoch、PES/sequence/GOP/I-pictureのbyte位置、closed/open GOPとleading picture情報。
全packetでなくRAP/GOP単位の記録でよい。
service IDとPIDだけでは、sequence extension、AAC config、PID切替などを復元できないため、対応する設定かその取得位置も持つ。

seekは「対象のtimeline epochを選ぶ → target以前の復号可能GOPを選ぶ → 必要なprefix位置から1本のRangeを開く → 選択位置の設定で新sessionを始める → targetまで復号する」を基本とする。
I-pictureの途中byteだけを返さない。
不一致や未対応のconfig再利用は明示的に拒否し、利用可能な通常Range seekへ戻す条件を仕様化する。
録画中やfile変更でstaleなindexを黙って適用しない。
録画完了後のscan、既存scanとの統合、初回再生と並行するindex生成を比較し、初回再生前に全ファイルscanを必須にしない。

「ほぼ瞬時」は、要求位置と一致する表示復帰、音声再開、定常frame cadenceまでを別の受け入れ条件にする。
シーク完了時間200ms以下を現行のシーク目標とし、要求位置との一致、音声再開、定常frame cadenceとは別々に確認する。
同じ端末、同じ表示更新頻度、同じ素材/target、同じcache条件で変更前後を比較する。
一時的なraw video表示だけを初画成功と数えず、deinterlaced frameの時刻と継続再生も確認する。

## Issue / PR の切り出し

公開済みの候補branchは[README](README.md#提出の順序をどう決めたか)にある。
ここに挙げるのは、まだbranchにしていない切り出し候補である。

### `otya128/mpeg2toh264`へ直接出すもの

1. **player: picture workerのstartup timing**。任意jobの最初の完了とstream先頭AUを区別する。基本timingと分けるかはAPIレビューで決める。
2. **YADIF: visibility遷移とfield schedulingの再現試験**。約30fps状態を自動再現できた場合に、既存`d4ccb98`で不足する境界条件をIssue化する。opacity変更は含めない。
3. **source/core: PTS probeのservice選択**。複数serviceでの誤選択を再現してから全PID probeを扱う。
4. **Session: AAC付き初回GOP出力の先読み削減**。A/V同値性の追加試験が通った場合だけ独立PRにする。
5. **Worker: seek入力queueの先読み上限**。連続seekの中止済みRange量とp95で効果を確認してから独立PRにする。
6. **core: 初回IDRの並列可能なslice/job設計**。bitstreamと複数decoderの互換性を確認する大規模変更として分離する。

### `tsukumijima/mpeg2toh264`へ出すもの

1. upstream採用までKonomiTVで必要な修正のbackport。upstream PR番号と対応commitを明記し、独自実装を増やさない。
2. upstreamの汎用変更を、フォーク固有の`autoFilm`、film detector、queue reset、公開APIへ接続する変更。これは汎用修正と同じPRへ混ぜない。
3. 現在公開済みのupstream向け候補ブランチを先にフォークへ採用する場合は、将来upstream版へ置換できる単位を保つ。棄却したYADIF opacity branchとpresentation policyは取り込まない。

### `KonomiTV`へ出すもの

1. **Original seekのUI・Range配信計測と必要なI/O改善**。T0、DB/stat/open/first bodyを測り、実測で根拠のある変更だけを行う。
2. **recording seek情報の保存と汎用player APIへの入力**。別環境で永続indexの必要性が確認された後に、保存側とplayer側を別PRにする。

### 現時点で出さないもの

- DPlayer変更。seek確定までのUI経路に今回の支配的遅延や欠陥は確認していない。
- IDR用`ReconstructedPicture.clear()`の削除。同条件80回で効果がなく、性能修正の根拠がない。
- AAC早期GOP、8/2 MiB入力queue、sidecar index。候補と試作結果は残すが、採用条件を満たしていない。
- 初回field leadを2から1へ戻す変更。短窓では良い値が出たが、現行`d4ccb98`と競合し、独立A/Bで必然性を示せていない。

設計レビューの8項目では、MSE世代修正はすべてYesとする。
YADIF後継`26484fd`はstall原因のownerであるqueue時刻へ届き、新しいscheduler層を足さず、同じqueue ownerで容量確保を最小FIFO破棄、表示不能な未来時刻列を全resetとして分ける。前身`f7b89eb`で不足していたinteraction reductionを満たす。
overflow時刻圧縮`7ef6696`も同じ`#prepareQueue()`で、破棄済みfieldと残存deadlineの不整合だけを直す。新しい状態、閾値、fallbackを増やさず、捨てたdurationという既存値から時刻列を修復するため、原因に対して局所的である。
presentation policyは容量回復とは別の判断として独立A/Bにしたが、600秒で長時間退行したため採用しない。
YADIF opacity実験は描画ownerに置いてGalaxyで比較したが、cleanな変更前対照が約60fpsだったため採用しない。
MSE修正は`MseSink`に置き、修正前に失敗する外部動作の回帰試験とGalaxyの通常seekを確認した。
KonomiTV側のretryや設定fallbackで原因を隠していない。

追加の設計レビューでは、PTSなし・restart位置ありのmarkが先行PTSを隠す指摘を再現できたため修正した。
一方、queueの将来lead上限と表示時の過去lagを共通`#tolerance()`へまとめる案は、異なるpolicyを計算式だけで結合するため採用しない。
production参照がないことだけを根拠に公開`Mpeg2GopStream::push` APIを削る案も、外部利用者が失う機能を確認できないため採用しない。
overflow時刻圧縮は`#prepareQueue()`で容量破棄後のscheduleだけを修復する。`#present()`へ追加した1 field表示とcatch-upは600秒で長時間退行したため削除し、異なるownerの判断を残さない。
scheduler policyを単体試験するため、queue操作を内部moduleへ抽出する案は採用しない。
低電力Windowsの同一区間・全画面120秒で、現在のintegrationへ戻したcontrolは59.724fps、40ms超11回、`late` 19だったのに対し、結果objectを毎refreshで返す抽出版3走行は59.458〜59.599fps、40ms超14〜18回、`late` 30〜46だった。
結果objectをなくした診断版2走行は59.641 / 59.650fps、40ms超13 / 17回、`late` 29 / 26まで回復したが、controlへは戻らなかった。
Linuxでは59.892fps、40回seekの中央値131.1ms、p95 181.7msで退行を示さなかったため、低負荷環境だけでこのhot pathの変更を合格にしない。
CI試験不足は残るが、productionのrefresh pathへ試験用の関数境界や一時objectを加えず、実ブラウザーで外部挙動を固定できる試験だけを候補とする。
このscheduler抽出診断版は公開`integration/current-useful-fixes`へ含めず、診断版の値を公開integrationの現行値として扱わない。
生値は[Linux定常](results/linux-scheduler-extraction-steady-120s.json)、[Linux seek](results/linux-scheduler-extraction-seek-visible-40.json)、[Windows control](results/windows-integration-v2-current-control-steady-120s.json)、[Windows抽出版1](results/windows-scheduler-extraction-steady-120s-r1.json)、[2](results/windows-scheduler-extraction-steady-120s-r2.json)、[3](results/windows-scheduler-extraction-steady-120s-r3.json)、[Windows seek](results/windows-scheduler-extraction-seek-visible-40.json)、[no-allocation版1](results/windows-scheduler-noalloc-steady-120s-r1.json)、[2](results/windows-scheduler-noalloc-steady-120s-r2.json)に保存した。
