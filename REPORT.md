# 録画 MPEG-2 TS の直接再生とシーク遅延

コードとChrome/Galaxy実測から、通常seekの主要な待ちは、PTS probeとRange応答、GOPとAACが揃うまでの読取・H.264変換、MSE投入とdecoder再開である。
「indexがなく、毎回先頭から走査するため遅い」という構成ではない。
42.9GB・6時間40分のTSでもPTS探索は各seek 2 probeで収束した。
当時の絶対時間はタブ数を記録していなかったため主結果から外すが、単一タブで取り直した短い録画でもresponse中央値50〜52msに対し、可視YADIF canvas初描画中央値215〜267msで、index探索以外の待ちが残った。

シークとは別に、単一タブのGalaxy A/BでYADIF出力がほぼ停止する走行を基準版7/90、queue再同期版0/90で再現した。
canvasのopacity変更は原因または修正ではなかった。
停止時もrAFとfilterは動作したが、fieldの表示予定が未来へ連鎖してqueueが飽和していた。
また、MSE resetと古いappend完了が競合すると新しいinit segmentが失われる問題を再現し、別branchで修正した。

## 対象と証拠の範囲

| 対象 | 確認した版と範囲 |
| --- | --- |
| KonomiTV checkout | `master`、`e92fba8bb219589c8e4ada9609ed4a9d91b33c00` |
| checkout の依存指定 | mpeg2toh264 `52a3db5e8fb9833e6cade2167097849c668bdb1f` |
| YADIF opacity実験 | `upstream/main`基点の`6b825e8`で検証したが棄却。誤取り込み防止のため公開branchは削除し、結果だけ本リポジトリに保存 |
| YADIF queue再同期 | 公開`fix/restore-yadif-queue-reset`、`konomi/main`基点のsource `f7b89eb`、dist `4c75a02`。フォーク固有統合候補 |
| MSE修正 | 公開`fix/mse-reset-inflight-append`、`upstream/main`基点の`f8ab9c7` |
| seek計測 | 公開`feat/seek-timing-context`、計測実装`ffe2893`、`presented`の意味を実測に合わせて明記した現HEAD `58a9920` |
| 完成fragment早期受け渡し | 公開`fix/deliver-completed-fragments-early`、`upstream/main`基点の`30ad508` |
| seek probe標本の保持 | 公開`fix/preserve-seek-probe-sample`、`upstream/main`基点の`a10253e` |
| DPlayer | `DPlayer/`へclone。`master`の`a5f847877eada1390456aea4ed7da8e31b4c166e`（v1.33.1）がKonomiTVのlockfileと一致 |
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
この上書きをやめると、最初の遠距離2 seek後の10 seekにおける追加probeは、直接デモの実行順を反転した2比較でどちらも4回から0回になった。
実KonomiTVのDPlayerでもdesktopは2回から0回、Galaxyは4回から0回になった。
このため、正しい byte / PTS の対応を保つ5行削除をsidecarより先に採用する。

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

今回のローカル ローカルにread-only mountした録画領域 は読み取り専用 CIFS、`rsize=4 MiB`、`cache=strict`、`actimeo=1` だった。
これはローカル計測側の mount であり、共有されたサーバー自身の録画保存先が SMB であるという証拠ではない。
SMB 上なら open/stat/read の往復と cache miss が追加候補になるが、64 KiB の Python read がそのまま64 KiBの SMB requestになるとは限らない。
帯域十分という前提でも、直列の probe、各 request の DB/stat/open、probe 全体の到着待ちは残る。

[source.ts:41](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/source.ts#L41) は本体を `Range: bytes=offset-`、`cache:'no-store'` で取得し、`206` と開始 byte を検査する。
`Accept-Ranges` の表記だけには依存しない。
Worker は変換と並行して入力を先読みし、未変換入力が32 MiBに達すると request を abort、8 MiB以下へ減ると次の byteから再開する。
このため不要な先読みはあり得るが、常時小さい Range を連発する設計ではない。

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
I-picture の位置が既知でも、GOP全体の収集、追加 GOP保留、AAC条件は現状のまま残る。

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

[mse.ts:343](https://github.com/otya128/mpeg2toh264/blob/d5df08ba9c661a5576545d3d30464d8f3bf64639/packages/player/src/mse.ts#L343) は範囲外 seekで待ち行列とrandom access記録を消し、`remove(0, Infinity)` を予約する。
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
この分岐ではqueueとperiodを直接消さず、時間差やtimelineの変更処理にも依存する。
小さいseekや `seeked` とrVFCの順序による古いfieldの表示は候補として観測すべきだが、今回の試験では再現確認していない。

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

upstream実装と同様に、飽和時にqueueを消してcallback時刻へ戻す処理をフォークへ適合した正式候補を、単一タブ規則の下で再測定した。
各ブロック開始前にCDP page targetを0件へ戻し、測定中は前景の視聴page 1枚だけとした。
基準版と修正版の短窓ブロック順はB-F-F-B-B-F-F-Bとし、読み込まれた`PlayerController` assetも各走行で照合した。
WebGL2のdefault framebufferへの`drawArrays()`を直接数え、`drawFps < 10`または`late`増分30超を停止とした結果は次のとおりだった。

| 条件 | n | 停止 | 1.8秒窓drawFps中央値 | p10 | 最低 | queue reset |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 基準 `52a3db5` | 90 | **7** | 44.94 | 43.23 | 1.67 | 0 |
| queue再同期 `f7b89eb` | 90 | **0** | 44.97 | 40.53 | 14.98 | 29 |

基準版の7件はすべて540秒台で、4件はdrawFps 10未満、残る3件は`late`増分30超だった。
修正版のqueue再同期は29回作動し、停止を0件に抑えた。
停止率のWilson 95%区間は基準3.82〜15.19%、修正版0〜4.09%で、7対0の条件付きFisher両側確率は約0.0138だった。
一方、中央値差は0.03fpsでbootstrap 95%区間も-0.54〜0.59fpsだったため、通常走行の平均fpsを改善する変更とは扱わない。
この1.8秒値にはseek応答中の無描画時間も含まれ、定常fpsそのものではなくseek直後の復帰窓である。

4秒窓10回では基準版が中央値53.61fps・最低52.24fps、修正版が53.60fps・最低51.72fpsで、停止はどちらも0件だった。
したがってqueue再同期は、通常の復帰時間や定常fpsを一律に短縮する変更ではなく、稀に未来時刻列が戻らなくなる長時間stallを防ぐ正しさの修正として維持する。

比較用に、各rVFCの`expectedDisplayTime`へfield時刻を再アンカーする独自案も旧条件で測定した。
当時は停止0/30だったがタブ数を固定していないため効果量には使わず、upstreamのqueue設計とも異なるので優先度を下げる。
旧測定は[従来のqueue計測](results/yadif-seek-queue.json)、単一タブA/Bの全走行は[queue再同期A/B](results/galaxy-yadif-queue-single-tab-ab.json)に保存した。

`autoFilm`は区間依存である。
MADDERの420秒と900秒では`film`へ入り約23〜24fps、120秒では`video`のまま、1500秒では`video`から`film`への切替過渡を観測した。
番組全体を24fpsと扱わず、初画、mode lock、定常cadenceを別々に評価する。

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

同じqueue再同期版と完成fragment早期受け渡しを組み合わせ、MADDERの420秒と900秒をfilm候補として交互に10回seekした。
全走行で初画が返り、中央値280.5ms、最大310.0msだった。
最後の1走行ではqueue resetが発生したが271.7msで初画が返った。
120秒と1500秒ではvideo/filmが切り替わったため、番組全体を24fpsとみなす根拠にはしない。
各走行は[MADDER film候補の計測](results/madder-film-seek.json)に保存した。

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
| 1. indexなしの探索が最大要因 | 否定寄り。永続GOP indexはないが、メモリ内PTS indexと最大4回の小Rangeがある。43GB素材でも2 probe、約0.1秒で収束した。ただし学習標本を後のfragment時刻で上書きする欠陥があり、修正すると学習後の追加probeがdesktop 2/10→0/10、Galaxy 4/10→0/10になった |
| 2. RAP不一致の余分な読み込み | 確認。offsetはRAP未整列。本体Rangeは初画までに数十MiBを読み、tables/PES/GOP再取得とA/V条件を含む。RAP indexで短縮余地はあるが後段は消えない |
| 3. MSE remove/flushが支配的 | 通常時の単独支配は否定寄り。clearとprobeは並行し、append markまで数ms〜十数msの点が多い。別途init喪失のqueue競合は再現・修正済み |
| 4. PAT/PMTの毎回再探索 | 確認。sessionを作り直すため。ただしWASMとWorker poolは再利用 |
| 5. IDR/recovery待ち | 初期IをIDR化するまでの入力と計算は必要。24 GOP周期待ちではない。Galaxyでは最初のIDR jobだけでjobs後33〜40msを占め、任意の後続jobは4〜7msで先に終わった。IDR固有の予測・再構築が変換側critical path |
| 6. YADIF/IVTCの過剰な初画待ち | 単一タブの乃木坂A/BでYADIF停止7/90→0/90となり、queue再同期によるstall防止を確認。通常時中央値はほぼ不変。MADDER A/Bでは`autoFilm:false/true`のcanvas初描画分布が重なり、IVTC固有の初画待ちは支持されなかった |
| 7. 古い処理のキャンセルがない | abortと世代判定あり。ただし実行中WASM pictureは完了待ち、同期処理中のevent配送も遅れ得る |

## 実装済み変更と提出先

upstream向けに分離した4件に加え、フォーク固有YADIFへupstreamのqueue再同期を戻す変更を別branchにした。
YADIF opacity変更は棄却した実験である。
upstream向け4 branchは`otya128/mpeg2toh264`の`upstream/main`（`d5df08b`）へ適用できる形で公開した。
MSE修正とfragment早期受け渡しでは、tsukumijimaフォーク側の追加scriptと`package.json`の文脈だけが衝突するため、upstream用PRではscript登録を現在のupstreamに合わせて作り直す。

| 変更 | なぜ・目的 | 何を修正したか | 実測または確認できた効果 | 本来の提出先 |
| --- | --- | --- | --- | --- |
| YADIF canvasのopacity試作 | Galaxyで約30fps状態の後、`opacity: 0.999`版が約60fpsだったため | canvas生成時に`opacity: 0.999`を設定した | cleanなopaque対照は30秒と12秒の両方で約60fps。video rVFCも約30Hzを維持したため、改善効果と当初のChromium因果説明は立証できなかった | branchは削除。結果だけを本調査リポジトリに保存 |
| YADIF queue再同期の復元 | フォークの個別late破棄ではseek後の未来時刻を戻せず、表示が停止したため | upstreamにある飽和queueの再同期を、forkのstartup slackとfilm拡張を保って復元した | 単一タブA/Bで停止7/90→0/90、queue reset 29回。1.8秒窓中央値44.94→44.97fps、4秒窓中央値53.61→53.60fpsなので、平均fps改善ではなくstall防止 | `tsukumijima/mpeg2toh264` fork。source `f7b89eb`、専用dist `4c75a02` |
| MSE resetと古いappend完了の競合修正 | seek reset中に旧`updateend`が新queueをshiftし、新しいinit segmentを失い得るため | 実行中SourceBuffer操作とseek世代を追跡し、旧世代の完了を新queueへ適用しない | 修正前に失敗する模擬競合試験は修正後に成功。実Chrome通常seekは251.4→250.1msで有意な短縮なし。実利用のstall削減量も未立証 | `otya128/mpeg2toh264` player。公開commit `f8ab9c7` |
| seek単位の段階計測 | Range、picture変換、fragment、append、decoder提示のどこが遅いかを同一seekで分離できなかったため | seek IDとtargetを引き回し、probe PTSとbyte、本体Range、picture jobs、先頭AU、batch、fragment、appendを記録 | 直接の速度改善はない。Galaxyで先頭IDR jobが33〜40ms、append後のplayingが27〜149ms、LAN first byteがADB reverseより約30〜61ms遅いことと、probe標本の誤上書きを分離。`presented`は可視初画ではなくseek解除後のbuffered frameだと追補 | `otya128/mpeg2toh264` player。公開branch HEAD `58a9920` |
| probe標本をfirst fragment時刻で上書きしない | Range開始byteはGOP開始byteではなく、後続fragment時刻を対応付けると補間がずれるため | `source.offset`とfirst fragment時刻をindexへ記録する5行を削除し、実測したprobe標本を保持 | 学習後10 seekの追加probeは直接デモ4→0、実KonomiTV desktop 2→0、Galaxy 4→0。Galaxyのfirst fragment中央値122.1→98.1msだがbuild順非ランダムのため全差は帰属しない | `otya128/mpeg2toh264` worker。公開commit `a10253e` |
| 完成fragmentの早期受け渡し | 完成済み初回fragmentが、同じ入力chunk内の後続picture処理の完了までworkerに留まっていたため | transcoderが完成fragmentを逐次通知し、後続unit変換と受け渡しを重ねた | デスクトップ同一位置3点でfirst fragmentを約9〜10ms短縮。Galaxy順次比較は初画中央値305.5→277.4msだが順序差を含む | `otya128/mpeg2toh264` player/transcoder。公開commit `30ad508` |

公開中のupstream向け4ブランチは、すべて`upstream/main`（`d5df08b`）を直接の土台として再構成した。
各公開refについて`upstream/main`が祖先で、`konomi/main`（`52a3db5`）が祖先でないことをGitHubへのpush後に読み戻して確認した。
upstreamは生成済み`dist`を追跡していないため、公開branchにはsource、README、必要な回帰試験だけを含める。
tsukumijimaフォークには、upstream採用前のbackport、またはフォーク固有API・YADIF拡張との接続だけを別branchで残す。

KonomiTVに出す変更は、Original再生UIのT0計測、download handlerのDB/stat/open/first body計測と実測に基づくI/O修正、必要性が確認された場合のrecording単位sidecar保存である。
DPlayerには今回修正を実装しておらず、現時点で直接PRにする根拠もない。

| Priority | 改善案 | 期待効果 | 実装難易度 | upstreamに出しやすいか | 所有者 |
| --- | --- | --- | --- | --- | --- |
| P0 | upstreamのYADIF queue再同期をフォーク拡張へ復元する | 単一タブA/Bで長時間停止7/90→0/90。通常時中央値はほぼ不変 | 小 | ◎ | tsukumijimaフォークYADIF。upstream既存挙動との統合 |
| P0 | probeで測ったbyte→PTS標本をfirst fragment時刻で上書きしない | 学習後10 seekの追加probeをdesktop 2→0、Galaxy 4→0 | 小 | ◎ | mpeg2toh264 Worker。`a10253e`で実装済み |
| P2 | field時刻を各rVFCの`expectedDisplayTime`へ再アンカーする | 旧条件では過渡最低値が良かったが、単一タブA/Bは未実施 | 中 | △ | 比較実験。upstream復元後も過渡低下が再現する場合だけ再検討 |
| P1 | MSE reset中の古いappend完了を新queueへ適用しない | 到達可能なinit喪失競合を防ぐ。実利用の頻度とstall削減量は未立証 | 小〜中 | ○ | mpeg2toh264 player。`f8ab9c7`で実装済み |
| P0 | seek ID付き計測を正式API化し、probe、本体Range、picture worker段階を分離 | 原因選択への効果大。直接の速度改善なし | 小〜中 | ◎ | player。branch HEAD `58a9920`。MSE operation、raw rVFC、canvas描画は次段 |
| P2 | probeを選択service/video PID優先にする | 複数service TSで誤ったPTSを採る可能性を下げる | 中 | ○ | mpeg2toh264 source/core。標本上書き修正とは分離 |
| P1 | 完成済み初回fragmentを入力chunk内の後続処理より先に渡す | デスクトップ同位置3点でfirst fragmentを約9〜10ms短縮。位置依存で約66msの例もある | 中 | ○ | mpeg2toh264 Transcoder/Worker。`30ad508`で実装済み |
| P2 | 初回IDRを独立slice/jobへ安全に分割してpicture poolで並列化する | 現在33〜40msの単一critical jobを短縮する余地。画質・bitstreamは変わり得る | 大 | △ | mpeg2toh264 core/job protocol。slice境界、intra予測、Safari/VideoToolbox検証が必要 |
| P2 | 有効probeを本体へ再利用、PTS検出後にprobe読取を止める | 重複128 KiBと待ちを削減。RTT自体は残る | 中 | ○ | mpeg2toh264 source/worker |
| P2 | 入力queueの32/8 MiB high/low waterを小さくする | seek後の不要な先読みと連続seek時のI/O競合を削減。初画短縮は未確認 | 小 | ◎ | mpeg2toh264 Worker。8/2 MiB試作は未採用 |
| P2 | 選択範囲のbufferを保持するseek、clearを必要範囲に限定 | 再seekの再変換削減。removeが支配的なら有効 | 中〜大 | ○ | mpeg2toh264 MSE。RAPとoverlapを再設計 |
| P2 | download handlerのDB/stat/open、chunk sizeを計測して必要箇所だけ改善 | NAS/ASGI待ちが大きい環境で有効 | 小〜中 | ◎ | KonomiTV。Starlette一般問題は同upstream |
| P2 | AAC必要量が揃った完成GOPを次GOP境界前に出す | 128〜256KiB、0〜約22msの改善候補 | 中 | ○ | mpeg2toh264 Session。試作済み・保留 |
| P3 | 永続sidecarと有効なstream configを持つseek resolver | cold seekの約0.1秒とbootstrap読取を削減 | 大 | ○ | KonomiTV固有保存、playerの汎用API |
| P3 | 初回のsub-GOP fragment、video/audioの段階投入 | 初画の理論的な下限を下げ得る | 大 | △ | mpeg2toh264 core/player |

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
| 実際に採用したGOP/PES byteをcoreから返してindexへ追加する | probe標本に加えてRAP近傍の対応点を増やせる可能性 | `source.offset`への誤対応は`a10253e`で除去済み。追加APIはprobe標本だけで不足する素材を再現してから実装 |
| `walk_pts()`を選択service/video PID優先にする | 複数service TSの誤probe削減 | PAT/PMT不要の短いprobeという利点を失わない設計が必要 |
| PAT/PMT、PID、sequence/AAC configをseek間で再利用する | 初回fragmentまでのscan短縮 | 放送中のPID/config変更とdiscontinuityをepochで拒否できる契約が必要 |
| AAC必要量が揃った完成GOPを早く出す | 128〜256KiB、0〜約22ms候補 | 試作結果を[evidence](results/device-results.md)に保存。A/V同値性の追加試験待ち |
| 完成fragmentを入力chunkの残処理より先に返す | response→fragment最大区間の一部を短縮 | output順序、picture pool、cancel、backpressureを保つ必要がある |
| 入力queueのhigh/low waterを32/8 MiBから下げる | seek後の不要な読取量と、直後の再seekとの競合を削減 | Galaxyの8/2 MiB試作は初画を一貫して短縮しなかった。一方、canplay/playingまでの本体読込量は約38.4→11.4 MiB、別走行で約19.5→11.0 MiBへ減った。同じindex・probe数・decoder状態を揃えた連続seekで再評価する |
| MSE clearを全削除でなく対象範囲に限定する | 再seekで変換を省ける可能性 | 今回clear単独は支配的でない。RAPとbuffer overlap設計が先 |
| KonomiTV downloadのDB/stat/openを短縮・handle再利用する | NASのcold seekで数ms〜数十msの可能性 | warmな全backend計測では約0.3秒以内に復帰。cold cacheでDB/stat/open/first bodyを分離してから変更する |
| `autoFilm`のseek後lock/hysteresisを調整する | 24fps区間のモード安定を早める可能性 | 単一タブ初画A/Bでは改善余地を確認できず優先度を下げる。定常cadence、誤lock、CM境界の評価候補として残す |
| seek直後だけ簡易deinterlaceにする | 初画数msの可能性 | 1〜2frame不足時の複製/直接描画は既に実装済み。通常は追加変更不要 |
| 実行中picture jobを細粒度cancelする | 連続確定時の残余計算削減 | 通常のドラッグは指を離すまでseekしない。連打再現とjob時間の計測が先 |
| IDR用`ReconstructedPicture`生成直後の重複`clear()`を除く | 理論上はplaneのzero fillを1回減らす | 80回交互測定で28.224→28.357ms、best 27.702→27.692ms、出力hash一致。効果なしと確認したため性能変更にはしない |

この表の案は、未検証または効果が小さいという理由で保留している。
候補自体を否定・削除したものではない。
重複`clear()`除去だけは同条件で効果なしを確認したため、未検証候補ではなく採用しない案へ状態を変更した。
記録は削除していない。

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

「ほぼ瞬時」は、要求位置と一致する初画、音声再開、定常frame cadenceまでを別の受け入れ条件にする。
例えば初画200 ms以内という値は候補となるが、合意済みの達成基準や現在の達成値ではない。
同じ端末、同じ表示更新頻度、同じ素材/target、同じcache条件で変更前後を比較する。
一時的なraw video表示だけを初画成功と数えず、deinterlaced frameの時刻と継続再生も確認する。

## Issue / PR の切り出し

### `otya128/mpeg2toh264`へ直接出すもの

1. **player: reset中のSourceBuffer operationとqueueの世代整合性**。修正前に失敗する回帰試験を添付し、速度改善とは分離する。
2. **player: seek単位の基本timing**。seek ID、target、probe、本体Range、fragment、appendまでを1 PRにする。
3. **player: picture workerのstartup timing**。任意jobの最初の完了とstream先頭AUを区別する。基本timingと分けるかはAPIレビューで決める。
4. **player/transcoder: 完成fragmentの早期受け渡し**。出力順序、cancel、backpressureを回帰試験で固定する。
5. **YADIF: visibility遷移とfield schedulingの再現試験**。約30fps状態を自動再現できた場合に、既存`d4ccb98`で不足する境界条件をIssue化する。opacity変更は含めない。
6. **worker: probeで測ったbyte→PTS標本の保持**。Range先頭byteをGOP開始byteとみなす誤記録を削除する。公開commit `a10253e`と反復計測を添付する。
7. **source/core: PTS probeのservice選択**。複数serviceでの誤選択を再現してから全PID probeを扱う。
8. **Session: AAC付き初回GOP出力の先読み削減**。A/V同値性の追加試験が通った場合だけ独立PRにする。
9. **Worker: seek入力queueの先読み上限**。連続seekの中止済みRange量とp95で効果を確認してから独立PRにする。
10. **core: 初回IDRの並列可能なslice/job設計**。bitstreamと複数decoderの互換性を確認する大規模変更として分離する。

### `tsukumijima/mpeg2toh264`へ出すもの

1. upstream採用までKonomiTVで必要な修正のbackport。upstream PR番号と対応commitを明記し、独自実装を増やさない。
2. upstreamの汎用変更を、フォーク固有の`autoFilm`、film detector、queue reset、公開APIへ接続する変更。これは汎用修正と同じPRへ混ぜない。
3. 現在公開済みのupstream向け4ブランチを先にフォークへ採用する場合は、将来upstream版へ置換できる単位を保つ。棄却したYADIF opacity branchは取り込まない。

### `KonomiTV`へ出すもの

1. **Original seekのUI・Range配信計測と必要なI/O改善**。T0、DB/stat/open/first bodyを測り、実測で根拠のある変更だけを行う。
2. **recording seek情報の保存と汎用player APIへの入力**。別環境で永続indexの必要性が確認された後に、保存側とplayer側を別PRにする。

### 現時点で出さないもの

- DPlayer変更。seek確定までのUI経路に今回の支配的遅延や欠陥は確認していない。
- IDR用`ReconstructedPicture.clear()`の削除。同条件80回で効果がなく、性能修正の根拠がない。
- AAC早期GOP、8/2 MiB入力queue、sidecar index。候補と試作結果は残すが、採用条件を満たしていない。

設計レビューの8項目は、今回実装した2修正についてすべてYesとする。
YADIF opacity実験は描画ownerに置いてGalaxyで比較したが、cleanな変更前対照が約60fpsだったため採用しない。
MSE修正は`MseSink`に置き、修正前に失敗する外部動作の回帰試験とGalaxyの通常seekを確認した。
KonomiTV側のretryや設定fallbackで原因を隠していない。
