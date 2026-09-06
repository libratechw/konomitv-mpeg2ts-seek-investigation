# KonomiTV 録画・テレビ再生の安定性調査

KonomiTVのMPEG-2 TS直接再生、サーバーエンコードHLS、テレビ再生について、表示FPS、コマ落ち、A/V同期、シーク、異常TSからの復帰、長時間の遅延蓄積を調べています。

## 文書とデータ

- 指標と合格条件: [`METHODOLOGY.md`](METHODOLOGY.md)
- 確認済みの結果、未達条件、採否判断: [`REPORT.md`](REPORT.md)
- 公開可能な生値と機械集計: [`results/`](results/)

測定結果はsource、dist、KonomiTV、client asset、fixture、runnerのhashへ対応付けます。別commitの結果を評価対象へ流用しません。

## 評価対象

KonomiTV向けの判断は、測定開始前にfetchした`tsukumijima/mpeg2toh264`の`main`を基準にします。KonomiTV側の依存pinが遅れている場合も、隔離KonomiTVへ`main`を組み込んで測定します。

Worker描画へ移行した後の最初の基準snapshotは、mpeg2toh264 `faf1464`、KonomiTV `ea1962f`です。これより前のcandidateとintegrationは、過去の測定値の出所であり、新しい実装や合否判定の基点ではありません。

## 公開コード

この節を、KonomiTV、mpeg2toh264、DPlayerなど提出先をまたぐ全公開候補の一覧とします。公開branchは、実機で効果と関連する退行を確認した「採用候補」と、論理・不変条件・自動testを確認したが実機測定が残る「暫定候補」に分けます。暫定候補はfetch後のupstreamへ適用でき、既知の破壊的退行がなく、branch内READMEに未計測範囲と取り込み側で必要な検証を明記したものに限ります。診断・測定branchと棄却・撤回済み実験はどちらにも含めません。

### 採用候補

| 提出先 | branch・先端 | 確認済みの効果 | 残る確認 |
| --- | --- | --- | --- |
| `tsukumijima/mpeg2toh264` | [`codex/autofilm-comb-score-indexing`](https://github.com/libratechw/mpeg2toh264/tree/codex/autofilm-comb-score-indexing) `dcfe571` | `autoFilm`のcomb判定で行参照をpixel loop外へ移し、4素材の判定を変えず解析時間を約6〜9%短縮 | Windowsの同一runner長時間A/B、Galaxy以外の実表示、画素、可聴A/V同期 |
| `tsukumijima/DPlayer` | [`codex/ignore-stale-video-events`](https://github.com/libratechw/DPlayer/tree/codex/ignore-stale-video-events) `8e49bb7` | 旧videoのeventと遅延した`play()`拒否が画質切替後のvideoへ作用する経路を解消。Galaxy A/Bで現行videoのevent、失敗処理、画質切替、fullscreen、capture、再生進行を維持 | iOSの`InvalidStateError`とライブOriginal開始失敗への効果、同じvideoを使う`switchVideo()` |

### 暫定候補

| 提出先 | branch・先端 | 確認済みの効果 | 残る確認 |
| --- | --- | --- | --- |
| `tsukumijima/KonomiTV` | [`provisional/register-native-error-once`](https://github.com/libratechw/KonomiTV/tree/provisional/register-native-error-once) `03143a5` | DPlayerのNative `error` handlerを画質切替ごとの登録からDPlayerごとの1回へ集約し、現在のvideoと再生backendを受付時とライブの待機後に照合する。型検査、ESLint、提出前レビューを通過 | iOSのHLS→Original反復切替で再起動連鎖が消えること、現在のHLS videoのNative errorで従来どおり1回再起動すること、ライブの1秒待機中に画質切替・再生成した場合の実機挙動 |
| `tsukumijima/mpeg2toh264` | [`provisional/preserve-complete-pictures-before-loss`](https://github.com/libratechw/mpeg2toh264/tree/provisional/preserve-complete-pictures-before-loss) `c3406ab` | TS packet欠落時に完了済みpictureを保持し、2種類の欠損で映像sampleを10〜12枚増加。Galaxyの1時間比較で欠損1回あたりのbrowser drop中央値を13枚から2枚へ低減 | 正常TS、別の欠損、画素、可聴A/V同期、異常通過後のcadence不良 |
| `tsukumijima/mpeg2toh264` | [`provisional/yadif-queue-fallback-removal`](https://github.com/libratechw/mpeg2toh264/tree/provisional/yadif-queue-fallback-removal) `2bc48a0` | queue全消去とqueued slot再利用を削除。全6386状態の列挙で容量整理後のslot割当失敗0件、正常60i短時間の既知退行なし | 削除経路の実機効果、異常TSの長時間復帰、Worker実描画、可聴A/V同期 |

暫定候補は`provisional/`で始め、取り込み側の検証が必要なことをbranch内READMEにも明記します。

### 既存PRへの検証材料

Starletteの`FileResponse`切断処理には、既存の[PR #3390](https://github.com/Kludex/starlette/pull/3390)があります。独立したPRは作らず、[`codex/fix-file-response-disconnect`](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect)の実装、テスト、ベンチマーク、測定結果を[コメント](https://github.com/Kludex/starlette/pull/3390#issuecomment-5548572632)として共有しています。KonomiTVの実視聴への影響は[Issue #279](https://github.com/tsukumijima/KonomiTV/issues/279)へ報告しました。別の録画素材を使った[低電力Windowsでの追試](results/windows-starlette-viewing-seek-world-baba-200.json)、同じ素材を使った[高性能Windowsでの追試](results/windows-starlette-viewing-seek-world-leveli-baba-200.json)、最初に悪化を確認した素材を高性能Windowsへ移した[再現試験](results/windows-starlette-viewing-seek-original-fixture-leveli-baba-200.json)、Original実要求とplayer状態を拒否条件にした[低電力Windowsでの反復](results/windows-starlette-viewing-seek-original-fixture-repeat2-baba-200.json)も公開しています。同じv14 runnerでhostとseek帯を組み合わせた2×2追試は、[低電力・低帯域](results/windows-starlette-viewing-seek-world-v14-ideapad-lowband-baba-200.json)、[低電力・高帯域](results/windows-starlette-viewing-seek-world-v14-ideapad-highband-baba-200.json)、[高性能・低帯域](results/windows-starlette-viewing-seek-world-v14-leveli-lowband-baba-200.json)、[高性能・高帯域](results/windows-starlette-viewing-seek-world-v14-leveli-highband-baba-200.json)に分け、各元summary / blockのSHA-256を保持しています。このbranchは比較と再利用のために保持し、独立した採用候補として扱いません。

KonomiTV向けの変更は`tsukumijima/main`を追跡し、取り込み候補はまずfork branchとして公開します。数日間取り込まれず、fetch後の`main`にも必要な場合だけPRを作成します。`otya128/mpeg2toh264`は実装の由来を確認する参照先であり、通常の提出先にはしません。

`tsukumijima/main`へ取り込まれた変更の旧branchは提出対象ではありません。公開branchの一覧ではなく、`main`のコードと履歴を正本とします。

## 測定専用コード

[`codex/worker-presentation-observability`](https://github.com/libratechw/mpeg2toh264/tree/codex/worker-presentation-observability)は、`faf1464`の描画backend、rAF、描画submit、frame取込、presentation queue、output poolを同じ時系列で記録する診断branchです。source `24f9d98`とdist `3825261`で構成し、製品APIや採用候補にはしません。

[`codex/autofilm-analysis-observability`](https://github.com/libratechw/mpeg2toh264/tree/codex/autofilm-analysis-observability)は、`autoFilm`のGPU readback、field match、decimateと、そのCPU内訳を記録する診断branchです。製品APIや採用候補にはせず、branch全体の取り込みも想定しません。

mpeg2toh264とKonomiTVの[`diagnostic/mse-operation-context`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/mse-operation-context)は、MSE操作名、失敗時state、load開始からの経過、MediaSourceの接続状態を`InvalidStateError`へ対応付ける一組の診断branchです。KonomiTV側は[`4b307e9`](https://github.com/libratechw/KonomiTV/tree/diagnostic/mse-operation-context)、mpeg2toh264側は[`a3c0cd3`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/mse-operation-context)です。iPhone 15で再現したdogfoodのDPlayer修正とStarlette pinを保った統合診断版は、KonomiTVの[`diagnostic/dogfood-mse-operation-context`](https://github.com/libratechw/KonomiTV/tree/diagnostic/dogfood-mse-operation-context) `748d0b0`です。いずれもiOS実機で最初に失敗する操作と旧player・現行playerの世代を特定するためだけに使い、修正候補として取り込みません。

branch全体を取り込まず、同じsourceのmain-thread / Worker比較と、計装あり・なしの表示挙動比較だけに使います。このREADMEの採用候補・暫定候補にないfork branchは、直接取り込み候補ではありません。

## 取り込み判断

`tsukumijima/main`で再現し、KonomiTVへの影響を実測できた問題だけをfollow-up対象にします。性能差だけでなく、入力欠落から避けられない範囲、シーク位置の意味、公開API、レビュー負荷、保守負荷を確認します。

測定器、単体demo、オフライン変換、診断buildの成功を、KonomiTV end-to-endの合格とは扱いません。未確認範囲は[`REPORT.md`](REPORT.md)にまとめています。

## 公開範囲

`results/`にはLAN情報、録画名、ローカルpathを除いた結果だけを置きます。fixtureはSHA-256と欠陥構造で識別し、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
