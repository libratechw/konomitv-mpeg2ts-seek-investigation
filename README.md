# KonomiTV 利用体験の改善 — 修正候補と検証結果

KonomiTVと関連ライブラリについて、修正案とその検証結果をまとめています。個別に確認できる公開コードを先に示し、統合版で検証中の変更と未解決の問題を後に続けます。KonomiTV本体の配布リポジトリではありません。

## 公開済みの修正候補

2026年9月12日時点。以下は上流への提案を検討している変更で、採用済み・提出準備完了を意味しません。各リンク先でコードを確認できます。確認済みの効果と、取り込み判断に残る検証を併記しています。

### 画質切替後に古い映像のイベントが干渉する問題

**DPlayer：切替前のvideoから届くイベントと、遅れて返る`play()`の拒否を、切替後のvideoへ作用させない修正です。** Galaxyの比較試験では、現行videoのイベント・失敗処理、画質切替、全画面、キャプチャ、再生進行を維持しました。

iOSの`InvalidStateError`やライブOriginal開始失敗への効果、同じvideoを使う`switchVideo()`は未確認です。後述の「切替中に押した再生・停止が引き継がれない問題」とは別の変更です。

[コード：ignore-stale-video-events](https://github.com/libratechw/DPlayer/tree/candidate/ignore-stale-video-events) · 検証対象 `8e49bb7`

### 画質切替ごとにエラー処理が重複登録される問題

**KonomiTV：DPlayerのNative error handlerを、画質切替ごとではなくDPlayerごとに1回だけ登録します。** エラーの受付時とライブの待機後に、対象videoと再生backendが現在のものかを照合します。型検査・ESLint・提出前レビューを通過しています。

iOSでのHLS→Original反復切替、現行HLS videoのエラーによる再起動、待機中の画質切替・再生成について、実機確認が残っています。再起動連鎖の解消を実機で確認した段階ではありません。

[コード：register-native-error-once](https://github.com/libratechw/KonomiTV/tree/candidate/register-native-error-once) · 検証対象 `03143a5`

### autoFilmの解析負荷を減らす

**mpeg2toh264：autoFilmの判定結果を変えずに、解析処理を短縮する変更です。** 4素材のオフライン解析で約6〜9%短縮し、Galaxyの診断でも同期解析時間の短縮を確認しました。

これは解析時間の改善であり、全端末でコマ落ちや音ずれが減ることを示すものではありません。Windowsの同一runnerによる長時間比較、Galaxy以外の実表示、画素・可聴A/V同期の確認が残っています。

[コード：autofilm-comb-score-indexing](https://github.com/libratechw/mpeg2toh264/tree/candidate/autofilm-comb-score-indexing) · `dcfe571` · [結果と限界](REPORT.md#autofilmの表示負荷)

### TSの欠損前に完成していた映像を残す

**mpeg2toh264：TS packetの欠落を検出したとき、既に完成したpictureまで捨てない修正です。** 2種類の欠損で映像sampleを10〜12枚多く保持し、Galaxyの1時間比較では、欠損1回あたりのbrowser drop中央値が13枚から2枚へ減りました。

正常TS、別の欠損、画素・可聴A/V同期の確認が残っています。異常区間の通過後にフレーム間隔が乱れる問題は、この修正で解消したとは判断していません。

[コード：preserve-complete-pictures-before-loss](https://github.com/libratechw/mpeg2toh264/tree/candidate/preserve-complete-pictures-before-loss) · `c3406ab`

### 描画待ちのフレームをまとめて捨てる処理を除く

**mpeg2toh264：YADIFのqueue全消去と、queue内のslotを再利用するfallbackを削除する変更です。** 全6,386状態の列挙では、容量整理後のslot割当失敗は0件でした。正常60iの短時間試験でも既知の退行はありません。

実機での改善効果、異常TSからの長時間復帰、Worker描画、可聴A/V同期は未確認です。状態列挙の成功だけで、実際の表示品質が改善するとは判断しません。

[コード：yadif-queue-fallback-removal](https://github.com/libratechw/mpeg2toh264/tree/candidate/yadif-queue-fallback-removal) · `2bc48a0`

### 録画の終端でHTTP rangeが416になる場合の完了処理

**mpeg2toh264：既知のファイル総量以降へのrange要求がHTTP 416で拒否された場合に限り、変換済み出力を処理して再生を完了させます。** それ以外の失敗は、range位置を添えて従来どおり停止します。実装を直接使う`test-range-eof`、型検査、既存テスト、ビルド、独立レビューを通過しています。

iPadの録画Originalでの再現・効果確認、正常TS、画素・可聴A/V同期は未確認です。

[コード：complete-exhausted-http-range-v2](https://github.com/libratechw/mpeg2toh264/tree/candidate/complete-exhausted-http-range-v2) · 先端・dist `d011466` / source `9c0b1c7`（基点 `faf1464`）

## 設計を再検討している公開案

### タッチ端末の中央操作ボタン表示

KonomiTVの表示判定を補う変更では、Galaxyの横画面・録画再生・中央タップで操作ボタンが表示されることを確認しました。ただし、画面タップがUI表示ではなく再生・停止になる挙動もあり、ボタン表示だけでなくデスクトップ／モバイルの操作判定を含めて見直しています。**この表示補正だけを最終案として推奨しているわけではありません。**

POCOの実タップ、全画面、視認性、長時間操作は未確認です。Windowsは候補版の非タッチ表示のみ確認しています。

[現行案：touch-center-controls](https://github.com/libratechw/KonomiTV/tree/candidate/touch-center-controls) · `45d9a59` · [実機比較](results/galaxy-touch-center-controls-live-ab.json)

## dogfoodで検証中の修正

複数の変更を組み合わせる日常利用版は、[KonomiTVの`dogfood/integration`](https://github.com/libratechw/KonomiTV/tree/dogfood/integration)です。個別修正の取り込み先ではなく、統合した状態での評価用です。構成はbranch内の`Readme.md`を参照してください。以下の結果は記載した版に限り、branchの最新先端全体を保証しません。

### TVライブの一時停止と再開

KonomiTV側に、利用者の明示的な停止をplayer再構築後も引き継ぐ変更を入れています。2026年9月12日に確認した統合版はsource `3b8aed1` / dist `56f83a7`、DPlayer `2467f23`です。

Original設定で120秒一時停止し、再生ボタンを1回押す試験を行いました。

| 環境 | 試行数 | 停止・再開の結果 |
| --- | --- | --- |
| POCO / Android Chrome | 低遅延OFF・ON各2回 | 待機中に勝手に再生されないことは4/4で確認。操作後15秒以内の復帰はOFF 2/2、ON 1/2。一方、再構築で停止時の再生位置は4/4で失われました。 |
| Mac / Safari | 低遅延OFF・ON各1回 | 120秒待機後、単一操作で再生時刻・フレーム数が進行。厳密な映像要求経路は未捕捉。 |

**停止を保つことと、再生ボタン1回で確実に復帰することは別で、後者は未解決です。** POCOのON失敗例では、操作直後のvideo交換後に時刻0のまま15秒停止しました。物理表示、可聴音声・A/V同期は両環境とも未確認です。少数試行の成功率を、旧版からの改善量とは扱いません。[比較版・条件・残課題](REPORT.md#tvライブの一時停止と再開)

### 画質切替中に押した再生・停止が引き継がれない問題

DPlayerの`switchQuality()`には、切替開始時の`video.paused`を保存し、その後の利用者操作を新しいvideoの再生判断へ反映しない経路があります。再生・停止の両方向で状態が食い違う可能性をコード上で確認し、DPlayer自身が持つ論理的な停止状態を参照する修正を検証しています。

POCOの復帰失敗と整合する原因候補ですが、その失敗がこの経路だけで起きたとはまだ確定していません。修正前後の実機比較は未完了で、単独の公開候補もありません。KonomiTV側へ同じ切替意図を重複して管理させる案にはしていません。

### TVライブOriginalの開始時に不正な位置へ同期する問題

DPlayerの同期先が非有限値や負の値のときに、videoへ代入しない変更をdogfoodへ反映しています。iPad Air 5の限定比較では再生進行を確認し、iPhone 15・iPad mini 6でも初期Original、画質・チャンネル切替、低遅延OFF/ONで再生できました。

ただし、未修正上流と単独候補の同条件比較は未完了です。POCOでは未修正上流版でも、開始不能は12試行で一度も再現していません。全環境共通の原因や修正効果とは判断していません。[実装と確認範囲](REPORT.md#tvライブoriginalの開始不能) · [iPadの測定集計](results/ipad-live-original-negative-sync-guard.json)

## 継続して確認している問題

- **初期設定Originalで自動開始しない問題**：iPhone・iPadでは再生ボタンが必要でした。この利用時の観測はビルドを特定しておらず、上記の統合版での再現確認とは扱いません。ボタンを押しても進まない開始不能や、一時停止後の復帰とは分けて調査します。
- **Windowsネイティブ環境のAMD VCE**：IdeaPadとVCEEncC 9.12でTVライブ1080pの短時間再生を確認しました。長時間安定性・可聴A/V同期の受入はまだ完了していません。Windowsでの成功をLinuxのAMD runtime互換性の証拠にはしません。[確認条件](REPORT.md#windowsネイティブ環境のvce再生)
- **Safariの録画Original停止と、異常TS通過後の復帰**：ライブ開始や古いvideoのイベントを修正した結果だけで、これらも解消したとは判断していません。
- **端末ごとの描画差**：Androidの描画を一律にメインスレッドへ移す案は、GalaxyとPOCOで結果が逆転したため撤回しました。

## 既存PRへの検証材料

Starletteの`FileResponse`切断処理は、既存の[PR #3390](https://github.com/Kludex/starlette/pull/3390)へ[実装と測定結果を共有](https://github.com/Kludex/starlette/pull/3390#issuecomment-5548572632)しました。KonomiTVでの影響は[Issue #279](https://github.com/tsukumijima/KonomiTV/issues/279)にも報告しています。

Windowsの反復シーク試験では復帰時間の改善を確認しましたが、効果は端末・録画素材・シーク位置によって異なります。[比較条件と全結果](REPORT.md#http-range切断)を参照してください。[比較用branch](https://github.com/libratechw/starlette/tree/codex/fix-file-response-disconnect)は検証材料として保持し、別の提出候補には数えません。

## 詳細な証拠とコードの読み方

- [調査報告](REPORT.md)：問題別の原因、比較条件、採否判断、残る確認。
- [測定方法](METHODOLOGY.md)：指標と判定方法。
- [公開結果](results/)：測定集計と元記録のhash。試行数と、1試行中の状態取得回数は区別します。

結果は測定したsource・dist・素材・runnerに対応付けます。診断コードや単体テストの成功を、KonomiTVでの実表示・音声・操作の合格へ読み替えません。公開候補は`candidate/`、測定専用は`diagnostic/`、統合評価は`dogfood/integration`で区別し、検証の進展だけではbranch名を変えません。

<details>
<summary>測定専用branchと過去の基準版</summary>

[`diagnostic/worker-presentation-observability`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/worker-presentation-observability)は、`faf1464`の描画backend、rAF、描画submit、frame取込、presentation queue、output poolを同じ時系列で記録する診断branchです。source `24f9d98`とdist `3825261`で構成し、製品APIや修正候補にはしません。

[`diagnostic/autofilm-analysis-observability`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/autofilm-analysis-observability)は、`autoFilm`のGPU readback、field match、decimateと、そのCPU内訳を記録する診断branchです。製品APIや修正候補にはせず、branch全体の取り込みも想定しません。

mpeg2toh264とKonomiTVの[`diagnostic/mse-operation-context`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/mse-operation-context)は、MSE操作名、失敗時state、load開始からの経過、MediaSourceの接続状態を`InvalidStateError`へ対応付ける一組の診断branchです。KonomiTV側は[`4b307e9`](https://github.com/libratechw/KonomiTV/tree/diagnostic/mse-operation-context)、mpeg2toh264側は[`a3c0cd3`](https://github.com/libratechw/mpeg2toh264/tree/diagnostic/mse-operation-context)です。iPhone 15で再現したdogfoodのDPlayer修正とStarlette pinを保った統合診断版は、KonomiTVの[`diagnostic/dogfood-mse-operation-context`](https://github.com/libratechw/KonomiTV/tree/diagnostic/dogfood-mse-operation-context) `748d0b0`です。いずれもiOS実機で最初に失敗する操作と旧player・現行playerの世代を特定するためだけに使い、修正候補として取り込みません。

branch全体を取り込まず、同じsourceのmain-thread / Worker比較と、計装あり・なしの表示挙動比較だけに使います。このREADMEの修正候補にないfork branchは、直接取り込み候補ではありません。

Worker描画への移行後、最初の基準snapshotはmpeg2toh264 `faf1464`、KonomiTV `ea1962f`です。過去の結果はその版の記録として残し、現在の評価対象へ無条件に流用しません。mpeg2toh264の提案先は`tsukumijima/mpeg2toh264`の`main`を基準に、提出前に現行コードと既存の議論を確認します。

</details>

## 公開範囲

録画データ自体は配布せず、fixtureはSHA-256と欠陥構造で識別します。`results/`にはLAN情報、録画名、ローカルpathを除いた結果を置きます。このリポジトリの文書とデータは[CC0 1.0](LICENSE)です。
