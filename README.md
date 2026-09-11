# KonomiTV 録画・テレビ再生の安定性調査

KonomiTVのMPEG-2 TS直接再生、サーバーエンコードHLS、テレビ再生について、表示FPS、コマ落ち、A/V同期、シーク、異常TSからの復帰、長時間の遅延蓄積を調べています。

## 現在の到達点

2026年9月11日時点。修正をまとめて日常利用するdogfood版と、上流へ個別に提案する候補を区別しています。

- **TVライブのOriginalが開始できない問題**では、DPlayerの不正な同期先指定から停止に至る経路を特定しました。非有限値と負の値を指定しない修正をdogfoodへ反映し、iPad Air 5の消音・短時間試験で、低遅延ON/OFF・直接開始・画質切替による再生の進行を確認しています。利用者からもiPhone 15・iPad mini 6で正常再生の報告があります。[実装と確認範囲](REPORT.md#tvライブoriginalの開始不能)・[測定集計](results/ipad-live-original-negative-sync-guard.json)
- **TVライブOriginalの一時停止後に再開できない問題は調査中です**。iPadで日常利用版（dogfood）を使った際、一時停止してしばらく待った後に再生ボタンを押しても再生しませんでした。再生開始不能とは別の症状として追跡しており、原因や必要な修正が共通するかは、まだ分かっていません。
- **画質切替後に古い映像の処理が干渉する問題**には、DPlayer側で古い映像のイベントを除外する修正があります。Galaxyで効果と関連動作を確認しました。ただし、Safariの録画Original停止をすべて解消するとは判断していません。
- **処理時間と欠損映像の改善**では、autoFilmの解析時間を約6〜9%短縮する候補と、TSの欠損前に完成した映像を保持する候補を公開しています。全端末でのコマ落ちや音ずれの解消は未確認です。
- **端末差と録画の停止は引き続き調査中です。** Androidの描画を一律にメインスレッドへ移す案は、GalaxyとPOCOで結果が逆転したため撤回しました。Safariの録画Original、異常TS通過後の復帰、実際の音声と映像の同期には確認が残っています。

このページは実装候補の索引、[調査報告](REPORT.md)は問題別の結論と証拠、[測定方法](METHODOLOGY.md)は指標の定義を扱います。

<details>
<summary>測定データの読み方と過去の基準版</summary>

## 文書とデータ

- 指標と合格条件: [`METHODOLOGY.md`](METHODOLOGY.md)
- 確認済みの結果、未達条件、採否判断: [`REPORT.md`](REPORT.md)
- 公開可能な生値と機械集計: [`results/`](results/)

測定結果はsource、dist、KonomiTV、client asset、fixture、runnerのhashへ対応付けます。別commitの結果を評価対象へ流用しません。GalaxyとPOCOを同じライブOriginalへ接続した[固定60Hz・10分・2反復の結果](results/galaxy-poco-live-original-fixed60-paired-repeat.json)、Galaxyを[固定60Hz・120Hzで各2反復した比較](results/galaxy-live-original-fixed60-fixed120-paired-repeat.json)、Galaxyの30Hz遷移を同一走行内で分けた[4Hz page-damage A-B-A](results/galaxy-live-original-page-damage-4hz-aba.json)、[timer-only対照と1×1 pixel更新](results/galaxy-live-original-page-update-1px-timer-controls.json)では、実経路とlifecycleを機械検証しています。

## 評価対象

KonomiTV向けの判断は、測定開始前にfetchした`tsukumijima/mpeg2toh264`の`main`を基準にします。KonomiTV側の依存pinが遅れている場合も、隔離KonomiTVへ`main`を組み込んで測定します。

Worker描画へ移行した後の最初の基準snapshotは、mpeg2toh264 `faf1464`、KonomiTV `ea1962f`です。これより前のcandidateとintegrationは、過去の測定値の出所であり、新しい実装や合否判定の基点ではありません。

</details>

## KonomiTV dogfood

日常利用用のdogfoodは[`dogfood/integration`](https://github.com/libratechw/KonomiTV/tree/dogfood/integration)へ統合しました。現在の役割と構成はbranch内の`Readme.md`を正本とし、この調査リポジトリでは重複して管理しません。過去のbranchを使った測定は、各結果に固定したcommitを出所として参照します。

## 公開コード

公開済みの修正候補を、提出先をまたいでまとめています。ここでいう修正には、性能や操作性の改善も含みます。上流での採用済みを意味せず、確認済みの条件と残る確認を候補ごとに示します。診断用コードや撤回済みの案は含めません。

公開時に確認した上流コードへ適用でき、既知の破壊的な退行がないことを条件とします。実機確認の有無だけで候補を二段階に分けず、効果・互換性・未確認事項から取り込みの可否を判断します。各branchのREADMEにも、その版の検証範囲と残る確認を記載しています。

### 修正候補

| 提出先 | branch・先端 | 確認済み | 未確認・残課題 |
| --- | --- | --- | --- |
| `tsukumijima/mpeg2toh264` | [`candidate/autofilm-comb-score-indexing`](https://github.com/libratechw/mpeg2toh264/tree/candidate/autofilm-comb-score-indexing) `dcfe571` | 4素材のオフライン解析で判定を変えず約6〜9%短縮。Galaxyの診断でも同期解析時間を短縮。[結果と限界](REPORT.md#autofilmの表示負荷) | Windowsの同一runner長時間A/B、Galaxy以外の実表示、画素、可聴A/V同期 |
| `tsukumijima/DPlayer` | [`candidate/ignore-stale-video-events`](https://github.com/libratechw/DPlayer/tree/candidate/ignore-stale-video-events) `8e49bb7` | 旧videoのeventと遅延した`play()`拒否が画質切替後のvideoへ作用する経路を解消。Galaxy A/Bで現行videoのevent、失敗処理、画質切替、fullscreen、capture、再生進行を維持 | iOSの`InvalidStateError`とライブOriginal開始失敗への効果、同じvideoを使う`switchVideo()` |
| `tsukumijima/KonomiTV` | [`candidate/register-native-error-once`](https://github.com/libratechw/KonomiTV/tree/candidate/register-native-error-once) `03143a5` | DPlayerのNative `error` handlerを画質切替ごとの登録からDPlayerごとの1回へ集約し、現在のvideoと再生backendを受付時とライブの待機後に照合する。型検査、ESLint、提出前レビューを通過 | iOSのHLS→Original反復切替で再起動連鎖が消えること、現在のHLS videoのNative errorで従来どおり1回再起動すること、ライブの1秒待機中に画質切替・再生成した場合の実機挙動 |
| `tsukumijima/KonomiTV` | [`candidate/touch-center-controls`](https://github.com/libratechw/KonomiTV/tree/candidate/touch-center-controls) `45d9a59` | タッチ操作向けの表示判定を見直し、Galaxyの横画面・録画再生・中央タップで操作ボタンの表示を確認。[条件と実機比較](results/galaxy-touch-center-controls-live-ab.json) | POCOの実タップ、全画面、視認性、長時間操作。Windowsは候補版の非タッチ表示のみ確認 |
| `tsukumijima/mpeg2toh264` | [`candidate/preserve-complete-pictures-before-loss`](https://github.com/libratechw/mpeg2toh264/tree/candidate/preserve-complete-pictures-before-loss) `c3406ab` | TS packet欠落時に完了済みpictureを保持し、2種類の欠損で映像sampleを10〜12枚増加。Galaxyの1時間比較で欠損1回あたりのbrowser drop中央値を13枚から2枚へ低減 | 正常TS、別の欠損、画素、可聴A/V同期、異常通過後のcadence不良 |
| `tsukumijima/mpeg2toh264` | [`candidate/yadif-queue-fallback-removal`](https://github.com/libratechw/mpeg2toh264/tree/candidate/yadif-queue-fallback-removal) `2bc48a0` | queue全消去とqueued slot再利用を削除。全6386状態の列挙で容量整理後のslot割当失敗0件、正常60i短時間の既知退行なし | 削除経路の実機効果、異常TSの長時間復帰、Worker実描画、可聴A/V同期 |
| `tsukumijima/mpeg2toh264` | [`candidate/complete-exhausted-http-range-v2`](https://github.com/libratechw/mpeg2toh264/tree/candidate/complete-exhausted-http-range-v2) `d011466`（基点`tsukumijima/mpeg2toh264@faf1464`、source `9c0b1c7`、dist `d011466`） | 既知の総量以降を開くHTTP rangeが数値status 416で拒否された場合だけ、変換済み出力をdrainして再生を完了する。その他の失敗はrange位置を付けて従来どおり停止する。実装を直接使う`test-range-eof`、型検査、既存test、生成build、独立レビューを通過 | iPadの録画Originalでの再現確認、正常TS・画素・可聴A/V同期 |

修正候補は`candidate/`、診断・測定専用は`diagnostic/`で始めます。検証の進み具合によってbranch名は変えません。日常利用版の入口は`dogfood/integration`に固定します。過去の測定記録には改名前の`codex/`・`provisional/`が残りますが、現在の参照先はこのページのリンクを使ってください。

### 既存PRへの検証材料

Starletteの`FileResponse`切断処理については、既存の[PR #3390](https://github.com/Kludex/starlette/pull/3390)へ[実装と測定結果を共有](https://github.com/Kludex/starlette/pull/3390#issuecomment-5548572632)しました。KonomiTVでの影響は[Issue #279](https://github.com/tsukumijima/KonomiTV/issues/279)にも報告しています。

Windowsの反復シーク試験では復帰時間の改善を確認しましたが、効果の大きさは端末・録画素材・シーク位置によって異なります。[比較条件と全測定結果](REPORT.md#http-range切断)を参照してください。[比較用branch](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect)は再利用のために保持し、独立して提出する修正候補には含めません。

mpeg2toh264の変更は`tsukumijima/mpeg2toh264`の`main`を基準にし、提案前に現行コードと既存の議論を確認します。必要な根拠とレビューが揃った候補を草案にまとめ、ユーザーがPRを提出します。一律の日数を待つことは提出条件にしません。`otya128/mpeg2toh264`は実装の由来を確認する参照先であり、通常の提出先にはしません。

`tsukumijima/mpeg2toh264`の`main`へ取り込まれた変更の旧branchは提出対象ではありません。公開branchの一覧ではなく、`main`のコードと履歴を正本とします。

## 測定専用コード

[`diagnostic/worker-presentation-observability`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/worker-presentation-observability)は、`faf1464`の描画backend、rAF、描画submit、frame取込、presentation queue、output poolを同じ時系列で記録する診断branchです。source `24f9d98`とdist `3825261`で構成し、製品APIや修正候補にはしません。

[`diagnostic/autofilm-analysis-observability`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/autofilm-analysis-observability)は、`autoFilm`のGPU readback、field match、decimateと、そのCPU内訳を記録する診断branchです。製品APIや修正候補にはせず、branch全体の取り込みも想定しません。

mpeg2toh264とKonomiTVの[`diagnostic/mse-operation-context`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/mse-operation-context)は、MSE操作名、失敗時state、load開始からの経過、MediaSourceの接続状態を`InvalidStateError`へ対応付ける一組の診断branchです。KonomiTV側は[`4b307e9`](https://github.com/libratechw/KonomiTV/tree/diagnostic/mse-operation-context)、mpeg2toh264側は[`a3c0cd3`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/mse-operation-context)です。iPhone 15で再現したdogfoodのDPlayer修正とStarlette pinを保った統合診断版は、KonomiTVの[`diagnostic/dogfood-mse-operation-context`](https://github.com/libratechw/KonomiTV/tree/diagnostic/dogfood-mse-operation-context) `748d0b0`です。いずれもiOS実機で最初に失敗する操作と旧player・現行playerの世代を特定するためだけに使い、修正候補として取り込みません。

branch全体を取り込まず、同じsourceのmain-thread / Worker比較と、計装あり・なしの表示挙動比較だけに使います。このREADMEの修正候補にないfork branchは、直接取り込み候補ではありません。

## 取り込み判断

各提出先の現行コードに対し、原因と修正の対応、関連動作への影響、検証の十分さを確認します。局所的な不具合修正は再現と短い回帰確認を、性能や長期安定性の変更は条件を揃えた比較と実利用の証拠を重視します。入力欠落から避けられない影響、シーク位置の意味、公開API、レビュー・保守の負担も判断に含めます。

測定器、単体demo、オフライン変換、診断buildの成功を、KonomiTV end-to-endの合格とは扱いません。未確認範囲は[`REPORT.md`](REPORT.md)にまとめています。

## 公開範囲

`results/`にはLAN情報、録画名、ローカルpathを除いた結果だけを置きます。fixtureはSHA-256と欠陥構造で識別し、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
