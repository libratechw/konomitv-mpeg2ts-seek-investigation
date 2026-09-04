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

`faf1464`は自動testとbuildを通過しています。Galaxyの正常60i短時間条件はmain-thread描画への切り替えで理論FPSへ戻りましたが、同じ異常TSを繰り返し通過する長時間条件では致命的な表示停止が1件発生しました。

| 対象 | 判定 | 必要な証拠 |
| --- | --- | --- |
| MPEG-2 TS正常60i | 未判定 | main-thread / Worker短時間比較後、1時間連続再生 |
| MPEG-2 TS異常 | 不合格 | 1種類の実在欠損を繰り返す走行で2秒以内の安定復帰に失敗。原因特定後、独立した欠損へ拡張 |
| `autoFilm` | 未判定 | 正常3:2素材4種類、film / video境界、60i復帰 |
| 録画シーク | 未判定 | 実DPlayer UI、LAN直結、位置精度を維持した200ms以下 |
| 録画H.264 / HEVC | 未判定 | 対象画質ごとの1時間試験とA/V同期 |
| テレビ再生 | 未判定 | 放送時刻に対する遅延が継続蓄積しないこと |
| 可聴A/V同期・scanout | 未判定 | counterや描画submitとは別の実表示・音声確認 |

## `faf1464`で確認済みの範囲

- Rust release test 247件、WASM build、workspace typecheck、player・YADIF build、MSE test、IVTC testは成功しました。
- YADIF distはLinuxで再生成した内容と一致しました。
- KonomiTV `ea1962f`へ計装distを組み込んだclientはtypecheckとbuildに成功しました。
- client asset、YADIF Worker asset、build環境、source・dist hashをread-only snapshotへ固定しました。
- 実映像を使わないブラウザーsmokeでは、Worker backendの開始、Worker内rAF、世代、event sequenceを取得できました。描画submitと端末間の時刻対応は、実映像preflightで確認します。

これらはbuildと計測経路の証拠であり、再生品質の合格を示しません。

## 採否判断に残る証拠

### Android ChromeのYADIF描画先

GalaxyのChromeをPC版サイト表示にすると、User-AgentはLinux desktopを示しますが、`navigator.platform`はARM Linux、`maxTouchPoints`は5を返します。KonomiTV側でmpeg2toh264を`faf1464`へ更新し、YADIF生成箇所だけでこの端末条件を補足してmain-thread描画を選ぶcandidateを作成しました。

正常60iの10秒測定3回は`outputFps`中央値59.934〜59.952、`missed`増分0、`late`増分0〜3でした。600秒台と900秒台を往復する20回の直接シークでは、対象位置の永続canvas表示が最大180.8ms、p95 179.8ms、位置の絶対誤差が最大18.8msでした。900秒へシークして5秒後から測った10秒間も`outputFps`中央値59.922、`missed`・`late`増分0、media time進行10.000秒でした。[条件と結果](results/galaxy-android-yadif-main-thread-candidate.json)を公開しています。

これはGalaxy 1台、正常60i、短時間、`video.currentTime`によるシークの結果です。実DPlayer UI、他のAndroid端末、1時間条件、可聴A/V同期は未確認です。

### `autoFilm`の表示負荷

同じcandidateとGalaxyで、正常3:2の3素材を24fps modeで10秒ずつ測ると、`outputFps`中央値は46.570〜47.833、`missed`増分は38〜47、film modeは各stats窓の0〜2回だけでした。同じキッズアワー素材で24fps modeだけを無効にすると、中央値59.958、`missed`・`degraded`増分0になり、1 frame当たりの処理時間中央値も11.627msから2.042msへ下がりました。[素材別の結果](results/galaxy-autofilm-normal-fixture-comparison.json)を公開しています。

同じキッズアワーのrVFCを直接比較した1走行では、autoFilm ONは映像が299 frame進む間に50 callbackを取り逃し、OFFは298 frameに対して欠落0でした。callback間隔中央値は42.0ms対33.4ms、decoderの`processingDuration`中央値は17.2ms対17.1ms、canvas draw呼び出しは両方とも中央値0msでした。decoderや最終描画ではなくautoFilmの同期解析がmain threadを塞ぐ層まで絞れています。一方、同じ未計装buildの再走行では欠落0だったため、欠落の発生率は未確定です。

位相計測では、1 frame当たりの中央値は2回のGPU readbackが合計約8.8ms、CPU側のfield matchとdecimateが合計約7.6msでした。comb scoreの行参照をpixel loop外へ移す候補では、Galaxyの1走行でcomb scoreが3.4msから3.0ms、field matchが4.6msから4.1ms、同期解析全体が17.7msから16.8msへ短縮しました。4素材のオフライン解析でも処理時間が約6〜9%短くなり、判定結果は一致しました。[位相別の条件と結果](results/galaxy-autofilm-analysis-phase-comparison.json)を公開しています。診断build各1走行の比較であり、長時間の欠落率や他端末での効果は未確認です。

### YADIFのqueue recovery fallback

`faf1464`には、queue末尾の表示予定が時刻差の上限を超えたときにqueue全体を空にする処理と、空き出力slotがないときに最古のqueued slotを上書きするfallbackがあります。前者は一時的な予定時刻のずれをqueue破棄として扱い、後者は表示待ちのpictureを暗黙に失わせます。

候補では両方を削除し、容量超過時に先頭だけを破棄して残りの表示時刻を詰める既存処理を残しました。公開statsの`queueResetted`は互換性のため残しています。出力pool 6、queue上限5、1回に必要な出力1または2の全6386状態を列挙し、容量整理後のslot割り当て失敗が0件であることを確認しました。WASM・YADIF build、workspace typecheck、IVTC・MSE test、Rust release test 247件も成功しています。公開branchのsource `0c5d12a`とdist `2bc48a0`は、実機測定に使ったsource `8b6fe78`とdist `f287e23`にREADMEだけを加えた同一コードです。

Galaxyの正常60iを同条件で10秒測ると、基準版と候補の描画は59.793fpsと59.697fpsで、双方とも40ms超の描画間隔、`missed`・`late`・`queueResetted`増分は0でした。「NHK高校講座 情報Ⅰ」から固定した映像・主音声のburst欠損を跨ぐ走行も、双方とも致命的な表示停止はなく、約0.45秒で安定した表示進行を確認し、末尾は約59.5fpsでした。[条件と結果](results/galaxy-yadif-queue-recovery-removal.json)を公開しています。

同じ欠損を1 client sessionで繰り返す長時間走行では、候補が144回目、`faf1464`が228回目の通過で、どちらも2秒以内に安定表示へ復帰できませんでした。`faf1464`の失敗trialでは`queueResetted`増分0、最終statsの`maxQueuedFields`は2であり、時刻差による全resetは発火していません。queued slot再利用fallbackには専用counterがないため、発火有無は未確認です。[長時間比較](results/galaxy-yadif-queue-recovery-long-anomaly-comparison.json)を公開しています。

両版に同じ失敗があるため、候補固有の退行や発生率差は立証されていません。一方、候補自身が致命的停止0件の必須条件を満たさず、削除の実機効果も確認できていないため、採用候補にはしません。コード上のqueue時間上限とslot不変条件は確認でき、既知の候補固有退行もないため、取り込み側で追加検証する暫定候補として公開します。削除したqueue全消去条件への到達、queued slot再利用の発火、Worker描画、正常再生の1時間安定性、可聴A/V同期、compositor scanout、入力欠損から避けられない最小dropは未確認です。

### 異常TSで完成済みpictureを保つ案

`52a3db5`を基点とした実験では、transport lossより前に完成していたpictureを残しました。2種類の実在欠損をオフライン変換すると、旧基準版に対して次の差がありました。

| 欠損 | 映像sample増加 | 最大映像時刻間隔 |
| --- | ---: | ---: |
| open GOP内P-picture | 10 | 567.233ms → 300.300ms |
| open GOP内B-picture | 12 | 567.233ms → 166.833ms |

音声sample数と音声時刻列は両方で一致しました。[変換結果](results/kids-hour-defect-conversion-comparison.json)と[fixture構造](results/kids-hour-transport-defects.json)を公開しています。

この結果はbrowser、decoder、YADIF、画素、可聴A/V同期、不可避な最小dropを確認していません。`faf1464`で同じ問題が残ることと実機効果を確認するまで、採用候補にはしません。

### サーバーエンコードHLS

KonomiTV `e92fba8`を基点とする隔離buildで、Galaxy Chrome、LAN直結、1080p60を600秒測定しました。H.264は35,964 frame中2 frameをdropし、HEVCは35,966 frame中drop 0でした。両方ともmedia timeは約600秒進みました。[条件と生値](results/galaxy-recorded-hls-1080p60-long-comparison.json)を公開しています。

これは10分・1走行の切り分けです。H.264の低頻度drop原因、1時間条件、全画質、A/V同期は未判定です。HEVCの実出力は8bitだったため、10bit HEVCの証拠には使いません。

### HTTP Range切断

低電力Windowsの隔離KonomiTVで、3MiB受信後に切断するRange要求を200回繰り返すと、Starlette基準版は応答が走行後半ほど悪化しました。`codex/fix-file-response-disconnect`では、ASGI disconnect後にfile送信を止めることで同じ悪化を再現しませんでした。[200要求の比較](results/windows-range-abort-starlette-fix-200.json)と[単体回帰試験](results/file-response-disconnect-starlette-fix.json)を公開しています。

この結果はbackendの切断処理を対象とし、Chrome、Akebi、converter、MSE、decoderを含むシーク時間の効果量ではありません。

### 固定fixture

正常3:2区間は、実写とアニメを含む4素材を固定しました。[scan結果](results/anime-autofilm-clean-fixtures.json)にcadence、decode error、transport error、SHA-256を記録しています。

異常TSは、乃木坂工事中の既知欠損に加え、キッズアワーからopen GOP内P-picture欠損とB-picture欠損、「NHK高校講座 情報Ⅰ」から映像・主音声が同時に複数欠損する2区間を独立fixtureとして固定しました。単一素材の成功を耐障害性全体へ一般化しません。

## 測定経路

Worker観測branchは次を記録します。

- 要求backendと実backend
- Worker内のrAFと描画submit
- Worker世代、再起動、main-thread fallback
- event sequenceとbuffer欠落数
- queue depthと描画path

最初に実映像で時刻原点、描画submit、event欠落0件を確認します。次に同じsource、fixture、端末でmain-thread / Workerを比較し、計装あり・なしの表示挙動も比較します。診断計装を含む走行は正式な性能値へ使いません。

短時間preflightを通過した後、正常60i、正常3:2、異常TSの順に実機測定し、MPEG-2 TS直接再生、H.264、HEVC、テレビ再生へ広げます。長時間試験の前にもupstreamをfetchし、基準commitが変わっていればbuildと計画を更新します。

## Follow-upを作る条件

次をすべて満たす問題だけを変更候補にします。

1. fetch後の`tsukumijima/main`で再現する。
2. KonomiTV end-to-endで利用者影響を測定できる。
3. 原因ownerを特定できる。
4. upstreamの設計意図、シーク位置の意味、公開APIを壊さない。
5. 同じ条件の修正前後で効果と退行を確認できる。

測定器の不足、旧branchの未提出、過去の効果だけを理由にfollow-upを作りません。
