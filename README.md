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

公開branchは、実機で効果と退行を確認した「採用候補」と、論理・不変条件・自動testを確認したが実機測定が残る「暫定候補」に分けます。暫定候補はfetch後のupstreamへ適用でき、既知の破壊的退行がなく、branch内READMEに未計測範囲と取り込み側で必要な検証を明記したものに限ります。診断・測定branchと棄却実験はどちらにも含めません。

### 採用候補

| 提出先 | branch | 役割 |
| --- | --- | --- |
| `tsukumijima/KonomiTV` | [`fix/android-yadif-main-thread`](https://github.com/libratechw/KonomiTV/tree/fix/android-yadif-main-thread) | Android Chromeのデスクトップ表示でも端末を識別し、YADIF描画をメインスレッドへ切り替える候補。先行commitでmpeg2toh264を`faf1464`へ更新する |
| `tsukumijima/mpeg2toh264` | [`codex/autofilm-comb-score-indexing`](https://github.com/libratechw/mpeg2toh264/tree/codex/autofilm-comb-score-indexing) | `autoFilm`のcomb判定で行参照をpixel loopの外へ移し、判定を変えずにCPU負荷を下げる候補 |

### 暫定候補

| 提出先 | branch | 役割 |
| --- | --- | --- |
| `tsukumijima/mpeg2toh264` | [`provisional/attach-main-mse-before-load`](https://github.com/libratechw/mpeg2toh264/tree/provisional/attach-main-mse-before-load) | メインスレッドがMSEを所有する環境で、`load()`中にメディアソースを接続する暫定候補。同期eventからの再入耐性と自動testは確認済みだが、iPhone / iPadでのOriginal切替、可聴再生、映像進行は採用前に実機確認が必要 |
| `tsukumijima/mpeg2toh264` | [`provisional/yadif-queue-fallback-removal`](https://github.com/libratechw/mpeg2toh264/tree/provisional/yadif-queue-fallback-removal) | YADIFのqueue全消去とqueued slot再利用を削除する暫定候補。slot不変条件と自動testは確認済みだが、削除経路の実機効果、長時間復帰、A/V同期は採用前に検証が必要 |

暫定候補は`provisional/`で始め、取り込み側の検証が必要なことをbranch内READMEにも明記します。

### 既存PRへの検証材料

Starletteの`FileResponse`切断処理には、既存の[PR #3390](https://github.com/Kludex/starlette/pull/3390)があります。独立したPRは作らず、[`codex/fix-file-response-disconnect`](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect)の実装、テスト、ベンチマーク、測定結果を[コメント](https://github.com/Kludex/starlette/pull/3390#issuecomment-5548572632)として共有しています。このbranchは比較と再利用のために保持し、独立した採用候補として扱いません。

KonomiTV向けの変更は`tsukumijima/main`を追跡し、取り込み候補はまずfork branchとして公開します。数日間取り込まれず、fetch後の`main`にも必要な場合だけPRを作成します。`otya128/mpeg2toh264`は実装の由来を確認する参照先であり、通常の提出先にはしません。

`tsukumijima/main`へ取り込まれた変更の旧branchは提出対象ではありません。公開branchの一覧ではなく、`main`のコードと履歴を正本とします。

## 測定専用コード

[`codex/worker-presentation-observability`](https://github.com/libratechw/mpeg2toh264/tree/codex/worker-presentation-observability)は、`faf1464`の描画backend、rAF、描画submit、frame取込、presentation queue、output poolを同じ時系列で記録する診断branchです。source `24f9d98`とdist `3825261`で構成し、製品APIや採用候補にはしません。

[`codex/autofilm-analysis-observability`](https://github.com/libratechw/mpeg2toh264/tree/codex/autofilm-analysis-observability)は、`autoFilm`のGPU readback、field match、decimateと、そのCPU内訳を記録する診断branchです。製品APIや採用候補にはせず、branch全体の取り込みも想定しません。

branch全体を取り込まず、同じsourceのmain-thread / Worker比較と、計装あり・なしの表示挙動比較だけに使います。このREADMEに採用候補として記載していないfork branchは、履歴・診断・棄却実験として扱います。

## 取り込み判断

`tsukumijima/main`で再現し、KonomiTVへの影響を実測できた問題だけをfollow-up対象にします。性能差だけでなく、入力欠落から避けられない範囲、シーク位置の意味、公開API、レビュー負荷、保守負荷を確認します。

測定器、単体demo、オフライン変換、診断buildの成功を、KonomiTV end-to-endの合格とは扱いません。未確認範囲は[`REPORT.md`](REPORT.md)にまとめています。

## 公開範囲

`results/`にはLAN情報、録画名、ローカルpathを除いた結果だけを置きます。fixtureはSHA-256と欠陥構造で識別し、録画データ自体は配布しません。

このリポジトリの文書とデータは[CC0 1.0](LICENSE)で公開します。
