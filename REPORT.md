# KonomiTV 録画・テレビ再生の安定性

この文書は、KonomiTVで確認済みの問題、採否判断に使える証拠、未確認範囲をまとめます。指標と合格条件は[`METHODOLOGY.md`](METHODOLOGY.md)、公開コードは[`README.md`](README.md)を参照してください。

## 評価基準

KonomiTV向けの判断は、測定開始前にfetchした`tsukumijima/mpeg2toh264`の`main`を基準にします。結果は必ずmpeg2toh264、KonomiTV、client asset、fixture、runnerのcommitまたはhashへ固定します。

Worker描画へ移行した後の最初の基準snapshotは次の組み合わせです。

| 対象 | commit |
| --- | --- |
| `tsukumijima/mpeg2toh264` | `faf1464e66693133fc9f4b8618992b0f557f0bc3` |
| KonomiTV | `ea1962f84c22265c1d31081dfe41cc3b53e9a555` |
| Worker観測source | `2348434033fe3e313ac94cdfee9eb640d8762c0f` |
| Worker観測dist | `5d588dcbfa177e875456712264dfede502baa63f` |

`faf1464`より前のcandidateとintegrationの値は、そのbuildで起きた事象の証拠です。`faf1464`の合否や効果量には使いません。

## 判定

`faf1464`は自動testとbuildを通過しています。Galaxyの正常60i短時間条件はmain-thread描画への切り替えで理論FPSへ戻りましたが、同じ異常TSを繰り返し通過する長時間条件では2秒以内に安定表示へ復帰しない試行が1件ありました。走行を2秒で打ち切ったため、その後の自動復帰は不明です。

| 対象 | 判定 | 必要な証拠 |
| --- | --- | --- |
| MPEG-2 TS正常60i | 未判定 | main-thread / Worker短時間比較後、1時間連続再生 |
| MPEG-2 TS異常 | 不合格 | 1種類の実在欠損を繰り返す走行で2秒以内の安定復帰に失敗し、その後は未観測。原因特定後、独立した欠損へ拡張 |
| `autoFilm` | 未判定 | 正常3:2素材5種類、film / video境界、60i復帰 |
| 録画シーク | 未判定 | 実DPlayer UI、LAN直結、位置精度を維持した200ms以下 |
| 録画H.264 / HEVC | 未判定 | 対象画質ごとの1時間試験とA/V同期 |
| テレビ再生 | 未判定 | 放送時刻に対する遅延が継続蓄積しないこと |
| 可聴A/V同期・scanout | 未判定 | counterや描画submitとは別の実表示・音声確認 |

## `faf1464`で確認済みの範囲

- Rust release test 247件、WASM build、workspace typecheck、player・YADIF build、MSE test、IVTC testは成功しました。
- YADIF distはLinuxで再生成した内容と一致しました。
- KonomiTV `ea1962f`へ計装distを組み込んだclientはtypecheckとbuildに成功しました。
- client asset、YADIF Worker asset、build環境、source・dist hashをread-only snapshotへ固定しました。
- 観測source `2348434` / dist `5d588dc`の実映像smokeでは、LinuxとWindowsのWorker描画、GalaxyのWorker / main-thread描画でtrace契約を確認しました。短時間のcadence判定はLinux・WindowsのWorkerとGalaxyのmain-threadが合格、GalaxyのWorkerが不合格でした。WindowsはLAN経由の隔離サーバーを使う診断で、Windows内完結の正式結果ではありません。

これらはbuildと計測経路の証拠であり、再生品質の合格を示しません。

## 採否判断に残る証拠

### iOSのOriginal画質切替

`faf1464`とMediaSourceを`load()`中に接続するcandidate `c09808a`を、iOS実機でA-B-A比較しました。テレビの1080p (60fps)からOriginalへ切り替えると、どちらも再生を開始しませんでした。candidateによる改善と退行は確認できないため、MediaSourceの接続順序をこのライブ開始失敗の修正候補から外します。

録画は両版ともOriginalで再生できました。ただし1080p (60fps)とOriginalの切り替えを繰り返すと、両版とも数回から10回に1回ほど`Error: The object is in an invalid state.`を表示しました。発生後は観測終了まで自動復帰せず、シークでも再開しなかったため、画質切替、プレイヤーの再起動、または再生を終了して始め直す必要がありました。復帰結果は画質切替後の`user-action-required`です。iPhone 15の診断buildでは、`SourceBuffer.appendBuffer()`が失敗し、その時点で`mediaSource=closed`、ライブラリ側の`closed=false`、`sourceBuffer=present`、`updating=false`、`operation=none`、`queue=3`、`epoch=1`でした。DPlayerの表示guardにより、画面のmpeg2toh264エラーは表示時点で現行videoに結び付いた現行pluginから出たことを確認できます。MediaSourceを閉じた処理は未確定です。操作名と失敗時stateをエラーへ付加する診断専用branchを、mpeg2toh264 `diagnostic/mse-operation-context`とKonomiTVの同名branchへ公開しました。これは修正候補ではなく、branch全体の取り込みを想定しません。

Starletteの切断処理修正版と同じMSE診断buildを配信した環境でも、この停止は残りました。利用者の反復操作では、iPad Air第5世代で約20〜30回に1回、iPad mini第6世代で約5〜10回に1回発生しました。iPad Air第5世代の1回の画面収録では、Originalから1080p (60fps)へ切り替え、Originalへ戻した直後に`InvalidStateError`となり、動画読込失敗、Native decode error、player再起動、前回位置への復帰、再度の`InvalidStateError`が続きました。この頻度は固定runnerによる統制測定ではありません。Starlette修正版がクライアント側の停止を解消しないことは確認できますが、頻度を変えたかは判断しません。

DPlayer `8e49bb7`とStarlette修正版を組み込んだdogfoodでも、iPhone 15が「数分間のエールを」のOriginalへの切替後に自動復帰しない同種の停止を起こしました。この回は`appendBuffer()`時に`mediaSource=closed`、ライブラリ側の`closed=false`、`operation=none`、`queue=1`、`epoch=0`でした。同時刻にserverはOriginalのRange要求へ206を返し、切替前のHLS生成も画面の停止後まで進んでいたため、serverの応答成功だけでclientの再生成功とは判定できません。

さらに操作名と時刻を追加した診断版で再現し、MediaSourceが開いて858ms後に閉じ、その64ms後の`appendBuffer()`が`InvalidStateError`になったことを確認しました。この時点でライブラリ側は`closed=false`、SourceBuffer参照あり、`updating=false`、実行中operationなし、queue 1件、seek後のepoch 1でした。閉じたMediaSourceへのappendは確定しましたが、MSEのownerとclass、Safariのライフサイクル、画質切替時のvideo操作、旧playerの遅延処理のどれが閉じたかは未確定です。診断版を使った反復回数は利用者の概算であるため、発生率には使いません。

同じdogfoodで、iPad mini第6世代が異常TS「NHK高校講座 情報Ⅰ」のOriginalへ切り替えて約20秒再生した後、シーク操作なしで`InvalidStateError`により停止しました。停止後のシークでは復帰せず、別の再起動操作を要しました。録画には約9.710秒の既知burst欠損があり、画面の停止表示は約17秒でしたが、この位置関係だけでは欠損を原因と判断できません。停止までの関連時間帯にserverはOriginalのRange要求へ9回206を返し、ERROR / WARNINGは記録していません。画面の汎用エラーだけでは、iPhone 15で確認した`appendBuffer()`失敗と同じ経路かも未確定です。

復帰結果はどちらも`user-action-required`ですが、iPad mini第6世代の事象は利用者操作なしの再生中に発生したため、画質切替直後に起きた事象より上位に調べます。

mpeg2toh264は変換エラー時にMSEを破棄して`error`状態へ入り、この状態ではシーク要求を処理しません。KonomiTVもmpeg2toh264のエラーを受けるとプレイヤーを一時停止します。このため、シークだけで復帰せず、プレイヤーを作り直す操作で復帰することは現行コードと一致します。これはエラー後の挙動を説明しますが、最初に失敗したMSE操作の特定には使いません。

candidateは、メインスレッドがMediaSourceを所有する環境で、最初の`play()`より前に最終的なMediaSourceをvideoへ接続します。この順序と同期eventからの再入耐性は自動testで確認しましたが、今回の利用者障害に対する効果は立証できませんでした。WorkerがMediaSourceを所有する環境には接続順序の変更が作用しません。

DPlayer v1.33.1では、画質切替ごとに共有event handlerが増え、取り外したvideoのeventと遅延した`play()`拒否が切替後のvideoへ作用します。DPlayerだけを変更したcandidate `8e49bb7`とのGalaxy A/Bでは、旧videoのevent relayが1回から0回、旧`play()`拒否による現行videoのpauseが1回から0回になりました。現行videoのevent relayと拒否時のpause、画質切替完了、fullscreen、capture、再生進行は維持しました。[実機比較](results/galaxy-dplayer-stale-video-lifecycle-ab.json)にbuildと計測条件を記録しています。この修正は品質切替後の旧処理干渉を解消しますが、iOSの`InvalidStateError`、ライブOriginal開始失敗、同じvideo要素を再利用する`switchVideo()`まで直すとは判断しません。

KonomiTV側にも別のhandler蓄積があります。録画再生ではHLS画質へ入るたび、Native `error` handlerを共有DPlayer event busへ追加し、Originalへ戻っても外しません。このためOriginal側でvideo errorが起きた際にも、先にHLS用として登録されたhandlerが現在の`video.error`を読み、`Native: 3`としてplayer再起動を要求できます。iPad Air第5世代の通知順序とは整合しますが、収録時にこのhandlerが発火したことは未計装です。DPlayer candidateのiOS確認では、旧videoの除外だけでなく、このKonomiTV handlerの登録数と発火元も記録する必要があります。

### Android ChromeのYADIF描画先

GalaxyのChromeをPC版サイト表示にすると、User-AgentはLinux desktopを示しますが、`navigator.platform`はARM Linux、`maxTouchPoints`は5を返します。KonomiTV側でmpeg2toh264を`faf1464`へ更新し、YADIF生成箇所だけでこの端末条件を補足してmain-thread描画を選ぶcandidateを測定しました。

正常60iの10秒測定3回は`outputFps`中央値59.934〜59.952、`missed`増分0、`late`増分0〜3でした。600秒台と900秒台を往復する20回の直接シークでは、対象位置の永続canvas表示が最大180.8ms、p95 179.8ms、位置の絶対誤差が最大18.8msでした。900秒へシークして5秒後から測った10秒間も`outputFps`中央値59.922、`missed`・`late`増分0、media time進行10.000秒でした。[条件と結果](results/galaxy-android-yadif-main-thread-candidate.json)を公開しています。

Galaxyでは1時間の正常60iも約59.85fpsで継続しましたが、POCO X3 GTでは結果が逆転しました。同じ`faf1464`、KonomiTV `ea1962f`、正常60iを使った30秒A-B-A-Bで、Workerは再生中の表示modeが120Hz設定から60Hzへ切り替わり、YADIFの`outputFps`は57.662〜58.777でした。main-thread強制では表示modeが120Hzのまま、実描画は55.166〜56.732fps、YADIFの`late`増分は91〜126でした。両描画先とも再生は30秒進み、playback eventとerrorはありませんでした。[端末差の結果](results/poco-yadif-rendering-device-variance.json)に条件とhashを記録しています。

同じ条件の10分走行でも、Workerはmedia timeが600.004秒進み、YADIFの`late`増分640、browser drop増分274でした。main-thread強制はmedia timeが600.002秒進みましたが、実描画は54.292fps、40ms超の描画間隔532回、`late`増分2,848、browser drop増分397でした。双方とも停止とplayback eventは0件で、前後のactive mode IDは5でした。

Workerの最終canvas submitはpage側から観測できないため、Workerの値を実描画FPSとは扱いません。active modeも前後snapshotであり、走行中の変化は分かりません。短時間と10分の結果はいずれも全Androidをmain-threadへ切り替える条件を支持しないため、公開candidateを撤回し、branchを削除しました。Galaxyで得た効果は端末固有の証拠として残します。端末能力から描画先を選ぶ条件と可聴A/V同期は未確定です。

GalaxyのライブOriginalを、端末表示を固定60Hzと固定120Hzにして各60秒測定しました。提示frameに対するrVFC callbackの欠落は60Hzで419 / 1,799 frame（23.29%）、120Hzで407 / 1,796 frame（22.66%）でした。両条件ともWorker / pageのrAF間隔中央値は33.3msで、表示を120Hzへ固定しても約23%のcallback欠落は解消しませんでした。[固定条件と生値](results/galaxy-live-original-refresh-60-120.json)に、build、runner、表示sample、実要求、実効`autoFilm`の照合結果を記録しています。

同じ放送の異なる60秒区間を各1回測った比較であるため、12 frame、0.63ポイントの差を表示更新設定の効果量とは扱いません。端末の「最適化」設定では開始時の120Hzから、Chrome再生中の87 sample中86 sampleが30Hzへ移行しました。この走行は端末の適応表示動作を示す診断資料として残し、固定120Hzとの比較には採用していません。

放送区間の差を除くため、同じ固定MPEG-2 TSをライブOriginal経路へ入力し、固定120→60→120Hzの各30秒を2反復しました。提示frameに対するrVFC callback欠落は、第1反復が91 / 151 / 163 frame、第2反復が134 / 128 / 180 frameでした。各区間の57表示sampleはすべて指定Hzに一致し、Original実要求、Worker、実効`autoFilm=false`、映像進行、trace欠落0、Mirakurunの新規利用なしを確認しています。120Hz区間内の差が60Hzとの差より大きく、固定120Hzによる改善は再現しませんでした。[固定入力のA-B-A結果](results/galaxy-fixed-input-original-refresh-aba.json)に生値とhashを記録しています。rVFCはcallbackの観測であり、画面へscanoutされた可視frameの欠落数とは断定しません。

同じ固定入力とGalaxyで、Chromeの`AndroidSurfaceControl`を通常→無効→通常の順に各30秒比較しました。提示frameに対するrVFC callback欠落は0 / 9 / 16 frameで、無効化による改善は確認できませんでした。無効化区間ではswitchの受理をBrowser APIで確認しましたが、固定120Hz設定中にも57表示sample中2件だけ30Hzを記録しました。通常区間は双方とも57件すべて120Hzでした。この表示状態の差を含むため、同じ実効表示条件だけを変数とした因果比較には使いません。Original実要求、Worker、`autoFilm=false`、映像進行、Mirakurunの新規利用なし、通常状態への復元を確認しています。[SurfaceControl無効化のA-B-A結果](results/galaxy-fixed-input-original-surfacecontrol-aba.json)に生値とhashを記録しています。1反復の固定入力試験であり、実放送入力の長時間安定性や画面へscanoutされたframeは評価していません。

POCO X3 GTでもライブOriginalを5分測定し、Workerの最終描画submitを17,557回、観測区間平均58.52fpsで記録しました。描画間隔のp95は23.6ms、p99は34.4ms、最大は240.7msで、100ms超は3回でした。途中に約332msのバッファ待ちがあり、自動復帰しました。この待ちと重なる描画間隔は1回で、残る2回は別の時点です。[条件と結果](results/poco-live-original-five-minute.json)に全配信ファイル・測定器の前後照合と、時計の起点を揃えた時刻対応を記録しています。Galaxyとは異なる放送区間のため端末差の効果量には使わず、画面の実表示、画素、可聴A/V同期の合格とも扱いません。

### `autoFilm`の表示負荷

同じcandidateとGalaxyで、正常3:2の3素材を24fps modeで10秒ずつ測ると、`outputFps`中央値は46.570〜47.833、`missed`増分は38〜47、film modeは各stats窓の0〜2回だけでした。同じキッズアワー素材で24fps modeだけを無効にすると、中央値59.958、`missed`・`degraded`増分0になり、1 frame当たりの処理時間中央値も11.627msから2.042msへ下がりました。[素材別の結果](results/galaxy-autofilm-normal-fixture-comparison.json)を公開しています。

同じキッズアワーのrVFCを直接比較した1走行では、autoFilm ONは映像が299 frame進む間に50 callbackを取り逃し、OFFは298 frameに対して欠落0でした。callback間隔中央値は42.0ms対33.4ms、decoderの`processingDuration`中央値は17.2ms対17.1ms、canvas draw呼び出しは両方とも中央値0msでした。decoderや最終描画ではなくautoFilmの同期解析がmain threadを塞ぐ層まで絞れています。一方、同じ未計装buildの再走行では欠落0だったため、欠落の発生率は未確定です。

位相計測では、1 frame当たりの中央値は2回のGPU readbackが合計約8.8ms、CPU側のfield matchとdecimateが合計約7.6msでした。comb scoreの行参照をpixel loop外へ移す候補では、Galaxyの1走行でcomb scoreが3.4msから3.0ms、field matchが4.6msから4.1ms、同期解析全体が17.7msから16.8msへ短縮しました。4素材のオフライン解析でも処理時間が約6〜9%短くなり、判定結果は一致しました。[位相別の条件と結果](results/galaxy-autofilm-analysis-phase-comparison.json)を公開しています。診断build各1走行の比較であり、長時間の欠落率や他端末での効果は未確認です。

映画「数分間のエールを」の全編を、低電力Windowsと240Hz Windowsで基準版と候補版を入れ替えて1回ずつ再生しました。4走行はすべてOriginalの実要求と`autoFilm=true`を確認し、予期した終端まで操作なしで完走し、途中停止と`queueResetted`は0件でした。同一端末のcandidate−baselineは、rVFC回数が低電力機で-38回、240Hz機で-1回、videoのdrop増分が+1枚と0枚で、候補の優位性は確認できませんでした。[全編A/Bの条件と結果](results/windows-autofilm-full-movie-ab.json)に4走行のhashと集計を記録しています。

このcollectorでは全走行の`draws`が0で、Workerが最終canvasへ提出した描画間隔を観測できません。したがって、長尺で操作なしの停止0件は確認できますが、表示cadence、コマ落ち0件、画素、可聴A/V同期の合格には使いません。

### YADIFのqueue recovery fallback

`faf1464`には、queue末尾の表示予定が時刻差の上限を超えたときにqueue全体を空にする処理と、空き出力slotがないときに最古のqueued slotを上書きするfallbackがあります。前者は一時的な予定時刻のずれをqueue破棄として扱い、後者は表示待ちのpictureを暗黙に失わせます。

候補では両方を削除し、容量超過時に先頭だけを破棄して残りの表示時刻を詰める既存処理を残しました。公開statsの`queueResetted`は互換性のため残しています。出力pool 6、queue上限5、1回に必要な出力1または2の全6386状態を列挙し、容量整理後のslot割り当て失敗が0件であることを確認しました。WASM・YADIF build、workspace typecheck、IVTC・MSE test、Rust release test 247件も成功しています。公開branchのsource `0c5d12a`とdist `2bc48a0`は、実機測定に使ったsource `8b6fe78`とdist `f287e23`にREADMEだけを加えた同一コードです。

Galaxyの正常60iを同条件で10秒測ると、基準版と候補の描画は59.793fpsと59.697fpsで、双方とも40ms超の描画間隔、`missed`・`late`・`queueResetted`増分は0でした。「NHK高校講座 情報Ⅰ」から固定した映像・主音声のburst欠損を跨ぐ走行も、双方とも約0.45秒で安定した表示進行へ自動復帰し、末尾は約59.5fpsでした。[条件と結果](results/galaxy-yadif-queue-recovery-removal.json)を公開しています。

同じ欠損を1 client sessionで繰り返す長時間走行では、候補が144回目、`faf1464`が228回目の通過で、どちらも2秒以内に安定表示へ復帰できませんでした。`faf1464`の失敗trialでは`queueResetted`増分0、最終statsの`maxQueuedFields`は2であり、時刻差による全resetは発火していません。queued slot再利用fallbackには専用counterがないため、発火有無は未確認です。[長時間比較](results/galaxy-yadif-queue-recovery-long-anomaly-comparison.json)を公開しています。

両版に同じ失敗があるため、候補固有の退行や発生率差は立証されていません。一方、候補自身が2秒以内の自動復帰条件を満たさず、削除の実機効果も確認できていないため、採用候補にはしません。この試行は2秒で打ち切っており、その後に自動復帰したかは不明です。コード上のqueue時間上限とslot不変条件は確認でき、既知の候補固有退行もないため、取り込み側で追加検証する暫定候補として公開します。削除したqueue全消去条件への到達、queued slot再利用の発火、Worker描画、正常再生の1時間安定性、可聴A/V同期、compositor scanout、入力欠損から避けられない最小dropは未確認です。

### watchdogによるフレーム通知復旧

watchdogが補った観測値と実rVFC metadataを分離する診断candidateはsource `12dbd87` / dist `353210c`です。同じcollectorとseedの300秒比較では、診断計装付きbaseline `24f9d98` / `3825261`とcandidateがともに欠損通過18回、legacy `fatalStops` 0件、cadence失敗2件でした。この比較では改善を確認できず、原因も未確定です。

candidateの約1時間走行は欠損通過244回、legacy `fatalStops` 0件でしたが、cadence失敗10件で不合格でした。collectorが異なるbaselineの長時間結果を、候補の効果量には使いません。通知の復旧と安定した表示間隔は別々に確認する必要があります。

### 異常TSで完成済みpictureを保つ案

`52a3db5`を基点とした実験では、transport lossより前に完成していたpictureを残しました。2種類の実在欠損をオフライン変換すると、旧基準版に対して次の差がありました。

| 欠損 | 映像sample増加 | 最大映像時刻間隔 |
| --- | ---: | ---: |
| open GOP内P-picture | 10 | 567.233ms → 300.300ms |
| open GOP内B-picture | 12 | 567.233ms → 166.833ms |

音声sample数と音声時刻列は両方で一致しました。[変換結果](results/kids-hour-defect-conversion-comparison.json)と[fixture構造](results/kids-hour-transport-defects.json)を公開しています。

`faf1464`とcandidateを、Galaxy、同じ欠損fixture、runner、collector、seed、KonomiTV clientで約1時間ずつ比較しました。`faf1464`は欠損243回、candidateは258回を通過し、legacy `fatalStops`は両方0件、cadence失敗は両方29件でした。一方、Chromeの`droppedVideoFrames`は欠損1回あたり中央値13枚から2枚へ減りました。[実機比較](results/galaxy-anomaly-preserve-complete-pictures-ab.json)に条件とhashを記録しています。

完成済みpictureを保持する変更は、現行mainにも残る欠落を実機で減らしましたが、異常TS通過後のcadence不良は解消しません。正常TS、別の欠損、画素、可聴A/V同期、不可避な最小dropを確認していないため、暫定候補のままとします。

### サーバーエンコードHLS

KonomiTV `e92fba8`を基点とする隔離buildで、Galaxy Chrome、LAN直結、1080p60を600秒測定しました。H.264は35,964 frame中2 frameをdropし、HEVCは35,966 frame中drop 0でした。両方ともmedia timeは約600秒進みました。[条件と生値](results/galaxy-recorded-hls-1080p60-long-comparison.json)を公開しています。

これは10分・1走行の切り分けです。H.264の低頻度drop原因、1時間条件、全画質、A/V同期は未判定です。HEVCの実出力は8bitだったため、10bit HEVCの証拠には使いません。

### HTTP Range切断

低電力Windowsの隔離KonomiTVで、3MiB受信後に切断するRange要求を200回繰り返すと、Starlette基準版は応答が走行後半ほど悪化しました。`codex/fix-file-response-disconnect`では、ASGI disconnect後にfile送信を止めることで同じ悪化を再現しませんでした。[200要求の比較](results/windows-range-abort-starlette-fix-200.json)と[単体回帰試験](results/file-response-disconnect-starlette-fix.json)を公開しています。

Starletteには同じ問題を扱う[PR #3390](https://github.com/Kludex/starlette/pull/3390)があります。独自PRは作らず、比較実装、テスト、ベンチマーク、loopback再測定を[PRコメント](https://github.com/Kludex/starlette/pull/3390#issuecomment-5548572632)として共有しました。`codex/fix-file-response-disconnect`は、その検証材料として保持しています。

KonomiTVへの実視聴影響は、測定結果を添えて[Issue #279](https://github.com/tsukumijima/KonomiTV/issues/279)へ報告しました。

物理Chromeと隔離KonomiTVを使う実視聴条件でも、同一の200シーク列をB-A-A-B順で比較しました。ここでの復帰時間は、シークを指定してから映像が対象位置で安定表示を再開するまでです。Starlette基準版はB1で143回、B2で140回の復帰後に、この復帰時間が2秒の上限を超えたため走行を打ち切りました。修正版はA1/A2とも200回を完了し、同じ上限超過は0件でした。基準版の復帰時間中央値は先頭20回の482.4ms / 557.2msから末尾20回の1,627.9ms / 1,580.9msへ悪化しました。修正版は442.7ms / 452.4msから537.7ms / 559.9msでした。[実視聴比較](results/windows-starlette-viewing-seek-baba-200.json)に復帰・打切りの定義、各シークの生値、打切り位置、buildとfixtureのhashを記録しています。

この比較ではKonomiTV `ea1962f`、mpeg2toh264 `52a3db5`、同じ録画fixture、物理Chrome、fullscreen、rVFCによる表示復帰判定を固定しました。修正版の各走行後にStarlette基準fileのhashが復元されたこと、全4走行のcleanup成功と残存portなしも確認しました。2秒超過後に操作なしで復帰するかは測っていません。1台の低電力Windowsと1素材による比較であり、iOSの画質切替時に起きる`InvalidStateError`への効果や、別端末・別素材での再現性は未確認です。

同じ素材と低電力Windowsで、Original実要求と`playerState=converting`を拒否条件にした現行runnerを新しいsessionで反復しました。修正版はA1/A2とも200回を完了し、2秒上限超過は0件でした。基準版はB1で115回、B2で143回の復帰後に上限へ達して打ち切りました。4走行が共通して完了した先頭115回では、同一seek番号ごとの修正版−基準版は平均-461.0ms、中央値-447.6ms、p95 -73.5msでした。先頭20回から末尾20回への中央値変化は基準版が+754.3ms / +1,113.0ms、修正版が+67.6ms / +148.7msでした。[現行runnerでの反復結果](results/windows-starlette-viewing-seek-original-fixture-repeat2-baba-200.json)に全復帰時間とhashを記録しています。打ち切り後の自動復帰は観測していないため、結果中の`fatalStops`は2秒以内に判定を満たさなかった回数であり、利用者操作が必要だったことを示しません。

同じ端末とrunnerで録画素材を「ワールド イズ ダンシング」へ替え、10〜80秒と100〜175秒のseek帯をB-A-A-B順で追試しました。4走行とも200回を完了し、2秒上限超過は0件でした。同一seek番号ごとの2走行平均では、基準版の復帰時間は平均841.2ms、修正版は752.6msで、差は-88.7msでした。先頭20回から末尾20回への中央値変化は基準版+60.1ms、修正版+73.0msで、最初の素材で見えた大きな後半悪化は再現しませんでした。[別素材の実視聴比較](results/windows-starlette-viewing-seek-world-baba-200.json)に全800回の生値と固定条件を記録しています。同じ条件を新しいsessionで反復すると、基準版867.5ms、修正版746.5ms、差-121.1msで、先頭20回から末尾20回への中央値変化は+146.0msと+104.9msでした。[反復結果](results/windows-starlette-viewing-seek-world-repeat-baba-200.json)も全4走行がOriginal実要求、`playerState=converting`、同一seek列、cleanup、Starlette復元の検証を通過しています。約89〜121msの差は反復しましたが、最初の素材で見えた大きな後半悪化は再現しておらず、修正版の効果量は素材やseek帯によって異なる可能性があります。

同じ素材、build、seek列を高性能WindowsでもB-A-A-B順で追試すると、4走行とも200回を完了し、2秒上限超過は0件でした。基準版の復帰時間は平均384.7ms、修正版は380.8msで、同一seek番号ごとの差は平均-3.9msでした。先頭20回から末尾20回への中央値変化は基準版+27.5ms、修正版+55.0msで、線形傾きはそれぞれ1 seekあたり+0.229ms、+0.227msでした。この端末では、低電力Windowsで見えた大きな復帰時間の差を再現していません。[高性能Windowsでの実視聴比較](results/windows-starlette-viewing-seek-world-leveli-baba-200.json)には全800回の生値、実測したOS・電源・表示・CPU条件、Originalのdownload要求、mpeg2toh264 playerとdeinterlacerの状態を記録しています。専用のWorker実行telemetry、可聴A/V同期、主観画質は測定していません。修正版の実視聴効果は端末負荷を含む条件に依存する可能性があり、2端末だけでは条件を特定できません。

最初に低電力Windowsで後半悪化を確認した録画素材を同じ高性能Windowsへ移し、240〜480秒と900〜1,140秒のseek帯を同じrunnerでB-A-A-B比較しました。全4走行が200回を完了し、2秒上限超過は0件でしたが、基準版の復帰時間は平均941.8ms、修正版は271.1msで、同一seek番号ごとの差は平均-670.6msでした。先頭20回から末尾20回への中央値変化は基準版+1,284.9ms、修正版+33.4ms、線形傾きは1 seekあたり+7.308msと+0.291msでした。[元の素材を使った高性能Windowsでの再現試験](results/windows-starlette-viewing-seek-original-fixture-leveli-baba-200.json)に全800回の生値、実測環境、Original要求とplayer状態を記録しています。同じ端末でも素材とseek帯を替えると差の有無が変わったため、高性能端末であることだけでは修正版の効果が小さかった追試結果を説明できません。どのファイル特性や読出し条件が差を生むかは未確定です。

### 固定fixture

正常3:2区間は、実写とアニメを含む5素材を固定しました。[scan結果](results/anime-autofilm-clean-fixtures.json)にcadence、decode error、transport error、SHA-256を記録しています。

異常TSは、乃木坂工事中の既知欠損に加え、キッズアワーからopen GOP内P-picture欠損とB-picture欠損、「NHK高校講座 情報Ⅰ」から映像・主音声が同時に複数欠損する2区間を独立fixtureとして固定しました。単一素材の成功を耐障害性全体へ一般化しません。

## 測定経路

Worker観測branchは次を記録します。

- 要求backendと実backend
- Worker内のrAFと描画submit
- Worker世代、再起動、main-thread fallback
- event sequenceとbuffer欠落数
- queue depthと描画path

最初に実映像で時刻原点、描画submit、event欠落0件を確認します。次に同じsource、fixture、端末でmain-thread / Workerを比較し、計装あり・なしの表示挙動も比較します。診断計装を含む走行は正式な性能値へ使いません。

短時間preflightを通過した対象から実機測定し、MPEG-2 TS直接再生、H.264、HEVC、テレビ再生へ広げます。問題間の優先順位と並列割当はworkspaceの`STATUS.md`に従います。長時間試験の前にもupstreamをfetchし、基準commitが変わっていればbuildと計画を更新します。

## Follow-upを作る条件

次をすべて満たす問題だけを変更候補にします。

1. fetch後の`tsukumijima/main`で再現する。
2. KonomiTV end-to-endで利用者影響を測定できる。
3. 原因ownerを特定できる。
4. upstreamの設計意図、シーク位置の意味、公開APIを壊さない。
5. 同じ条件の修正前後で効果と退行を確認できる。

測定器の不足、旧branchの未提出、過去の効果だけを理由にfollow-upを作りません。
