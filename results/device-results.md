# Chrome と Galaxy のシーク・カデンス計測

## タブ状態の監査とGalaxy単一タブ再測定

過去の一部Galaxy測定では、検証用の設定・視聴タブを閉じずに次のタブを開いていた。
古い設定タブのinputと新規視聴タブの`localStorage`が食い違う状態を実際に確認し、Worker、MSE、decoder、canvas処理の残留も除外できなかった。
このため、開始前のCDP page target 0件、測定中は対象の視聴タブ1枚だけ、再生中、LANから隔離KonomiTVへ直接接続、実DPlayer Originalという条件で取り直した。

| 素材 | seek系列 | autoFilm | n | response中央値 | first fragment中央値 | appended中央値 | 可視canvas初描画中央値 | p90 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 乃木坂工事中 | 600/900秒台を交互 | false | 10 | 50.3 ms | 128.6 ms | 138.1 ms | 215.2 ms | 261.3 ms |
| MADDER #08 | 420/900秒台を交互 | false | 8 | 52.3 ms | 144.8 ms | 163.2 ms | 267.4 ms | 311.4 ms |

初画は、YADIFのWebGL2 contextがdefault framebufferへ最初に`drawArrays()`した時刻とした。
全走行で親要素opacityは`1`、`watch-player--loading`はなく、DPlayer spinnerは`display:none`だった。
MADDERではKonomiTVの中央buffering表示が重なったがcanvasは隠れず、canvas初描画中央値267.4ms、`playing`中央値284.1msだった。

既存`presented` eventは`video.seeking`中のrVFCを捨てるため、MADDERで目的frameのcanvas描画後も約200ms遅れる走行があった。
旧表のMADDER 449.8 / 546.5msは可視初画ではなく、この受理条件を満たしたrVFCの中央値 / p90だったので初画指標から外した。
同じ単一タブで`autoFilm:false/true`を6回ずつ交互にしたcanvas初描画中央値は269.4 / 251.1msで分布も重なり、IVTCが約200ms差の原因という仮説は支持されなかった。

乃木坂の定常標本は約60fpsの`video`だった。
MADDERは各seek後に`video`と`film`が混在し、定常7標本も約24fpsの`film` 6回の後に`video`へ遷移した。
番組全区間やCM区間のcadenceへ一般化しない。

既存`presented` event同士では、旧10回値から単一タブ値への変化は乃木坂245.8→252.4ms、MADDER488.9→449.8msだった。
1バッチ同士なので差をタブ競合の効果量とは断定せず、旧値を主結果から外す。
従来のtiming eventは[galaxy-lan-single-tab-seek.json](galaxy-lan-single-tab-seek.json)、raw rVFC・canvas draw・可視状態を含む再測定は[galaxy-lan-single-tab-visible-frame.json](galaxy-lan-single-tab-visible-frame.json)に保存した。

### 完成fragment早期受け渡しの単一タブA/B

旧Galaxy順次比較はタブ数を記録しておらず、build順も固定だったため、早期受け渡しだけが異なる2 buildを8ブロックで測り直した。
各ブロックの開始前後はpage target 0件、測定中は前景の視聴タブ1枚とし、600秒と900秒のwarmup後に601/901〜605/905秒を測った。

| variant | n | response中央値 | first fragment中央値 | appended中央値 | playing中央値 | 可視canvas初描画中央値 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 基準 | 40 | 50.7 ms | 133.5 ms | 144.1 ms | 245.1 ms | 257.1 ms |
| 早期受け渡し | 40 | 54.5 ms | 140.2 ms | 150.2 ms | 261.3 ms | 274.5 ms |

修正版−基準版の中央値差に対する30,000回bootstrap 95%区間は、first fragmentが−2.0〜12.4ms、appendedが−2.5〜11.8ms、可視canvasが−9.0〜37.3msだった。
すべて0を含み、この条件では短縮を確認できなかった。

一時markを入れた別の10 seekでは、早期通知callbackの最初の発火はfirst fragmentより5.5〜1084.8ms後、中央値227.2ms後だった。
最初のmedia fragmentより前に発火した走行はなく、現行変更は2個目以降のfragmentと後続処理を重ねるものだと分かった。
匿名化した全走行は[galaxy-early-fragment-single-tab-ab.json](galaxy-early-fragment-single-tab-ab.json)に保存した。

以下の旧Galaxy測定は、タブ数を記録していない限り、機能再現、同一走行内の段階比率、同一タブ内A/Bの参考として扱う。
現在の端末end-to-end絶対時間には上の単一タブ再測定を使う。

## KonomiTV backendと実DPlayer UI

公式`ghcr.io/tsukumijima/konomitv:latest`を`127.0.0.1:7012`だけへ公開し、新規DBと次の3ファイルだけを個別にread-only mountした。
image labelのrevisionは`e92fba8bb219589c8e4ada9609ed4a9d91b33c00`、digestは`sha256:4220e7ad65f877921b880eaa81822297e3694f83a6b3815b3569328398a740e4`だった。
APIのversionは`0.14.1`で、3録画のscanとthumbnail生成が完了してから測定した。

### デスクトップGoogle Chrome

Chrome拡張で開いたKonomiTVの`/videos/watch/2`を、DPlayerの画質UIから`Original (MPEG-2)`へ切り替えた。
実seek barの1200秒位置を操作した結果は次の通り。

| 区間 | 時間 |
| --- | ---: |
| `mouseup` → `seeking` | 52.8 ms |
| `seeking` → `playing` | 233.4 ms |
| `mouseup` → `playing` | 286.2 ms |
| `mouseup` → 最初に観測したrVFC | 536.7 ms |

`mouseup`は2026-09-01 09:34:22.704 JSTだった。
access logには09:34:22.764、.776、.781に3本の`206`完了があり、継続Rangeは09:34:29.387だった。
このChrome拡張タブはbackground扱いだったため、rVFC値を前景Galaxyとのdecoder比較には使わない。

### Galaxy Tab S11 Ultraの単発seek

端末はSM-X930、Google Chrome 151、ADB reverseで同じローカルbackendへ接続した。
実画面の中央をタップして再生を開始し、200ms後にseek barの約1200秒位置をタップした。

| 区間 | 時間 |
| --- | ---: |
| bar `touchend` → `seeking` | 15.9 ms |
| bar `touchend` → 最初に観測したrVFC | 270.1 ms |
| bar `touchend` → `seeked` | 311.6 ms |
| bar `touchend` → `playing` | 319.4 ms |

bar `touchend`は09:44:59.598だった。
access logには09:44:59.724、.741、.755、.764に4本の`206`完了があり、継続Rangeは09:45:03.802だった。
最初の4本には旧streamのabort完了が含まれ得るため、これだけからprobe本数を4本とは数えない。

### Galaxyの3連続seek

再生を止めた状態で、約376秒、1468秒、880秒の3位置を150〜180ms間隔で確定した。

| 操作 | `mouseup` → `seeking` |
| ---: | ---: |
| 1 | 7.0 ms |
| 2 | 4.9 ms |
| 3 | 4.4 ms |

最後の`mouseup`から`seeked`までは223.2ms、同じ最終位置のrVFCまでは239.2msだった。
古い2位置の`seeked`は発生せず、3つ登録されたrVFC callbackはすべて最終位置880.474秒の同じ提示frameで完了した。
access logには各操作の直後に3本ずつ、計9本の`206`完了があり、古いlegの結果は捨てても開始済みの短いRange I/Oは残ることを確認した。

### seek ID付きtiming試作

branch `feat/seek-timing-context`（source `f4b16bc`、dist `ed66f49`。履歴整理前とtree同一）をKonomiTV clientへ組み込み、Galaxyの実DPlayer UIで約604秒へseekした。
bar `touchend`から`seek-requested`までは10.2ms、互換mouse eventの`mouseup`からは6.2msだった。

| mark | player受理から |
| --- | ---: |
| `seek-requested` | 0.0 ms |
| Worker `seek` | 0.5 ms |
| `probe-request` | 1.0 ms |
| `probe-response` | 47.7 ms |
| `probe-complete` | 50.6 ms |
| stream `request` | 50.9 ms |
| stream `response` | 60.7 ms |
| `first-byte` | 61.3 ms |
| `first-fragment` | 149.7 ms |
| `opened` | 149.8 ms |
| `appended` | 159.8 ms |
| `canplay` | 298.2 ms |
| `playing` | 298.3 ms |

この位置はメモリ内indexがwarmでprobe 1本だった。
最終buildでは`seekId`、`targetTime`、`at`、`sinceContext`、`sinceContextPrevious`、probeの`attempt`、`byteOffset`、`byteLength`が実イベントへ出ることを再確認した。
`sincePrevious`は既存互換のため全contextの直前markとの差を保つ。

### 初回picture batchの段階分解

timing branchのsource `4d4e65f`でpicture poolの段階markを追加し、任意のworkerが最初に完了した時刻、stream順のjob 0が完了した時刻、batch全体が完了した時刻を分けた。
生値は[picture-startup-stages.json](picture-startup-stages.json)に保存した。

Galaxyの乃木坂工事中600、900、1200秒では、`first-picture-jobs`から任意の最初の出力までは4.4〜7.2msだったが、stream先頭のaccess unitまでは33.0〜40.0ms、batch全体までは33.7〜53.7msだった。
4 workerから7 workerへ増やした試作でもbatch短縮は約1〜6msに留まり、probeとdecoderの揺らぎを超えるend-to-end改善にはならなかった。
先頭のrandom-access picture自体がcritical pathなので、worker数だけを増やす案は採用しない。

Chrome拡張のvisibleなデスクトップタブで600秒へ直接`currentTime`を設定した走行は、2 probe完了28.4ms、first byte 32.6ms、picture jobs 48.0ms、stream先頭AU 77.6ms、batch 85.6ms、fragment 92.3ms、append 93.8ms、canplay 321.1msだった。
`play()`はuser gestureとして受理されなかったため、この走行のplayingとpause中に遅れて返ったrVFCは端末比較に使わない。
一方、appendからcanplayまで227.3msかかり、SourceBufferへの投入自体はfragmentから1.5msだったので、変換後のdecoder準備が独立した大きな変動要因になり得ることは確認できる。

同じservice IDと約600秒のRange位置からWASM単体で最初のbatchを取り出すと、13 jobsのjob 0は33.260ms、後続は3.241〜14.856msだった。
job 0は310,026 Bから541,501 Bを出し、CPU profileにはIDR固有の`IntraState::store_luma`、`residual_8x8`、`luma_8x8_dc`、chroma再構築が現れた。
最初のfragmentはvideo 14 samples、audio 57 samplesを持ち、全job返却後の`Session.complete()`は6.219msだった。
初回IDRの画素再構築が、通常pictureより重いことを関数単位でも確認した。

`ReconstructedPicture::new()`直後の重複`clear()`だけを除く小変更も測った。
80回交互測定の平均は28.224msから28.357ms、bestは27.702msから27.692msで、出力SHA-256は一致した。
効果は測定できなかったため性能変更として採用しないが、検証済みの小候補として記録を残す。

### GalaxyからWi-Fi LANを直接通した計測

GalaxyのWi-Fiアドレスだけを許可した一時relayで、端末から`一時LAN relay`へ直接接続した。
転送先は同じ隔離KonomiTV backendで、`adb reverse`はこの通信経路に使っていない。
実DPlayerのOriginal経路を再生中にし、UI pointer配送を除いたnetwork以降を比較するため`video.currentTime`で600、900、1200秒へ順にseekした。

| target | probe | first byte | jobs | stream先頭AU | fragment | append | rVFC | playing |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 600 s | 2 | 137.5 ms | 174.4 ms | 212.0 ms | 225.0 ms | 237.4 ms | 339.0 ms | 334.8 ms |
| 900 s | 2 | 74.1 ms | 108.0 ms | 142.7 ms | 154.9 ms | 166.7 ms | 208.2 ms | 197.3 ms |
| 1200 s | 2 | 91.6 ms | 127.0 ms | 164.2 ms | 185.7 ms | 195.4 ms | 254.6 ms | 265.9 ms |

同じ端末の`adb reverse`走行に対し、LAN走行はfirst byteまでおおむね30〜61ms長かった。
Wi-Fiでは各probeと本体Rangeの応答時間が加算されるため、128KiBの直列probeを減らす改善価値はローカル転送より大きい。
一方、first byte後にも約81〜88msでfragment、さらに約30〜101msでframe提示またはplayingへ達しており、LANだけを短縮しても変換とdecoder待ちは残る。
実シークバーのpointer終了からplayer受理までの約10〜16msは別の実UI測定で確認済みで、この表には加えていない。

### 3修正を合成した実機確認

検証専用worktreeでYADIF source `4efff3f`、MSE reset source `b1ffef4`、seek timing source `f4b16bc`とtree同一の差分だけを合成し、最新KonomiTV clientをbuildして同じbackendへread-only mountした。
この合成worktreeはPR対象ではなく、正式な3branchは各1commitのまま維持した。

乃木坂工事中の約1200秒では、bar `touchend`からplayer受理11.8ms、probe 2本完了59.6ms、first fragment171.8ms、appended186.4ms、最初に観測したrVFC311ms、playing323.6msだった。
YADIF canvasは`opacity: 0.999`で、以後の8標本は59.13〜60.13fps、`mode: video`、`outputFps`も同値付近だった。
この区間を番組本編全体の代表とは扱わない。

MADDERは既定の「ビデオ24fpsモード: オフ」では約420秒でも`mode: video`、59.48〜60.18fpsだった。
ローカル検証設定だけを一時的にオンにし、約900秒へseekすると、bar `touchend`からplayer受理9.3ms、first fragment128.9ms、appended140.7ms、最初に観測したrVFC193ms、playing219.4msだった。
観測後半は`mode: film`で、カット等の過渡と思われる26〜31fpsの標本を挟みつつ、多くは23.27〜24.58fpsだった。
設定は測定後に元のオフへ戻した。
MADDER全区間を24fpsとは扱わず、900秒の短い候補区間の結果として記録する。

## デスクトップGoogle Chrome

Linux版Google Chrome 152.0.7977.64で、最新KonomiTV clientとローカルRangeサーバーを使い、「ばけばけ」の60、300、600、120秒へシークした。
YADIFは無効にした。

| target | T0→response | T0→first fragment | T0→append済み | T0→playing | 安定判定 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 60 s | 66.0 ms | 109.0 ms | 112.0 ms | 200.0 ms | 202.0 ms |
| 300 s | 32.6 ms | 103.2 ms | 106.4 ms | 150.0 ms | 161.5 ms |
| 600 s | 21.1 ms | 62.6 ms | 66.5 ms | 91.0 ms | 101.6 ms |
| 120 s | 17.1 ms | 94.5 ms | 108.9 ms | 140.0 ms | 142.1 ms |

ChatGPT Chrome拡張で開いた通常タブでもresponse、fragment、append、playingは同程度だった。
ただしそのタブはbackground扱いでrVFCが500〜900ms遅れたため、frame提示時間の比較には使わなかった。

## 条件

- KonomiTV: `e92fba8bb219589c8e4ada9609ed4a9d91b33c00`
- player dependency: `52a3db5e8fb9833e6cade2167097849c668bdb1f`
- YADIF: source `4efff3f`。`opacity: 0.999`の実験変更を含む。この変更は後のclean対照で効果を立証できず、PR候補から外した
- 端末: Galaxy Tab S11 Ultra `SM-X930`、Android 16
- ブラウザー: Google Chrome 151.0.7922.174
- 表示: 計測時の `renderFrameRate` は 60Hz
- 配信: ローカルにread-only mountした録画領域 のTSをローカルRangeサーバーから64KiB chunkで配信し、ADB reverseを使用
- player設定: `mediaSource: auto`、`passthrough: false`、`splitFieldSamples: true`、YADIF `doubleRate: true`

KonomiTVの最新clientと実際の`Mpeg2TsPlayer`を使ったが、録画APIは起動せず、HTTP配信部分は検証用Rangeサーバーで置き換えた。
サーバー側DB、Starlette `FileResponse`、実運用NAS経路を含むend-to-end計測ではない。

## 素材

| 役割 | ファイル | size | duration | SHA-256 |
| --- | --- | ---: | ---: | --- |
| 60フィールド動作の候補 | `2026-08-31_乃木坂工事中【白熱!初耳情報バトルゲーム 意外な素顔が続々発覚】.ts` | 3,066,534,364 B | 1815.493 s | `2240bbb8848d0c244378498dc0482b9c4f34e71a722dff01a2b6bfe50d1ca845` |
| 3:2とモード遷移の候補 | `2026-08-28_MADDER(マダー) #08 乃木坂46五百城茉央、flumpool山村隆太.ts` | 3,115,609,884 B | 1815.405 s | `894c063b789a5bff24ec6441883ec6b11a024e553d62c2d367ef8123cfe9178e` |

両方ともMPEG-2、1440×1080、TFF、30000/1001fpsである。
番組単位でカデンスを決めつけない。
乃木坂工事中にもCM等があり、MADDERも全区間が24fpsではない。
以下は指定時刻の短い区間だけの結果である。

## 乃木坂工事中

`autoFilm: false`で60、600、1200、300秒へ順にシークした。

| target | T0→response | T0→first fragment | T0→append済み | T0→playing | T0→YADIF表示 | 安定判定 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 s | 178.7 ms | 257.1 ms | 263.9 ms | 361.2 ms | 375.6 ms | 383.6 ms |
| 600 s | 48.2 ms | 145.2 ms | 156.7 ms | 179.4 ms | 183.3 ms | 188.6 ms |
| 1200 s | 44.5 ms | 138.5 ms | 146.9 ms | 203.6 ms | 283.5 ms | 288.2 ms |
| 300 s | 42.9 ms | 137.8 ms | 153.0 ms | 275.4 ms | 282.5 ms | 285.7 ms |

シーク後の定常YADIF出力は59.95〜60.06fpsだった。
300秒では復帰直後に49.2fps、1200秒ではvideo frame提示からcanvas再表示まで約98msの過渡があった。
選択区間が本編かCMかは映像内容と突き合わせていないため、この走行だけで各区間を真の60フィールド素材とは確定しない。

## MADDER

`autoFilm: true`で120、420、900、1500秒へ順にシークし、各区間を6秒観測した。

| target | T0→response | T0→first fragment | T0→append済み | T0→playing | T0→YADIF表示 | 安定判定 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 120 s | 172.8 ms | 295.2 ms | 304.9 ms | 333.2 ms | 339.7 ms | 342.5 ms |
| 420 s | 48.8 ms | 162.0 ms | 184.4 ms | 249.1 ms | 456.6 ms | 463.2 ms |
| 900 s | 45.2 ms | 254.4 ms | 271.4 ms | 342.1 ms | 345.8 ms | 349.9 ms |
| 1500 s | 61.5 ms | 258.3 ms | 274.4 ms | 350.3 ms | 358.8 ms | 366.0 ms |

区間ごとの判定は次のように分かれた。

- 120秒: 6秒間`video`。出力34〜55fpsで過渡的なlate増加あり
- 420秒: `film`。多くの標本が23.6〜24.3fps
- 900秒: 最初の`video`から`film`へ移行。以後おおむね22〜24fps
- 1500秒: `video`から約11秒後に`film`へ移行。切替時にlateとdropが増加

420秒と900秒は3:2代表候補、120秒は非film比較候補、1500秒はモード遷移のストレス候補として扱う。
CM、本編、テロップ、カット境界のどれに当たるかは別途画面内容を確認する。

## 読み取れること

- `opacity: 0.999`版は選んだ乃木坂区間で60fps出力を維持したが、後のcleanなopaque版も30秒と12秒の両方で約60fpsだったため、opacityの効果とは判定しない
- YADIF描画自体は多くのseekで`playing`から数ms〜十数ms後に再開したが、1200秒とMADDER 420秒には100〜200ms級の過渡があった
- HTTP responseまではwarm seekで約43〜62ms、初回fragmentまでは約138〜258msだった
- MSE append完了から`playing`までは約22〜98msで、通常のSourceBuffer clearだけが全区間を支配した形ではない
- `autoFilm`のモード確定や切替は区間依存であり、24fps素材のシーク評価では初画と定常cadenceを分けて測る必要がある

## YADIF queueの反復seek試験

タブ数未記録の旧30回試験では、YADIF出力10fps未満または`late`増分30超の走行が8/30だった。
停止時もrAFは動いていたが、field queue末尾の表示予定が最大351.9ms先まで伸びていたため、原因分析は残し、発生率は主結果から外す。

単一タブ再測定では、各ブロック開始前にpage targetを0件へ戻し、基準・修正の順序をB-F-F-B-B-F-F-Bとして各版90回測定した。
WebGL2 default framebufferへのdrawを直接数えた結果は次のとおりだった。

| 条件 | n | 停止 | 1.8秒窓drawFps中央値 | p10 | 最低 | queue reset |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 基準 `52a3db5` | 90 | **7** | 44.94 | 43.23 | 1.67 | 0 |
| queue再同期 `f7b89eb` | 90 | **0** | 44.97 | 40.53 | 14.98 | 29 |

停止7件はすべて540秒台で、条件付きFisher両側確率は約0.0138だった。
通常時中央値はほぼ不変なので、平均fps改善ではなくstall防止効果と判定する。
4秒窓10回も基準53.61fps、修正版53.60fpsで差はなかった。
独自の`expectedDisplayTime`アンカーは単一タブA/B未実施でupstreamと異なるため、候補を残したまま優先度を下げる。
旧走行は[yadif-seek-queue.json](yadif-seek-queue.json)、単一タブA/Bは[galaxy-yadif-queue-single-tab-ab.json](galaxy-yadif-queue-single-tab-ab.json)に保存した。

## 優先修正のGalaxy合成確認

540秒と900秒を交互に30回seekし、YADIF queue再同期だけ、完成fragment早期受け渡しを追加、MSE世代修正も追加、の3 buildを順番に測定した。

| build | 初画 median | 初画 p95 | playing median | playing p95 | YADIF停止 |
| --- | ---: | ---: | ---: | ---: | ---: |
| YADIF再同期 | 305.5 ms | 372.2 ms | 297.4 ms | 358.7 ms | 0/30 |
| + 完成fragment早期受け渡し | 277.4 ms | 301.6 ms | 269.5 ms | 300.9 ms | 0/30 |
| + MSE世代修正 | 273.6 ms | 297.6 ms | 267.0 ms | 288.4 ms | 0/30 |

各buildを順番に測定しており、順序はランダム化していない。
MSE世代修正の追加差は数msなので速度改善とは判定せず、到達可能なinit喪失競合を防ぐ正しさの修正として扱う。
各走行は[galaxy-priority-fixes.json](galaxy-priority-fixes.json)に保存した。

## queue再同期修正後のMADDER film候補区間

upstreamのqueue再同期をフォークへ復元した版に完成fragment早期受け渡しを加え、`autoFilm: true`で120、420、900、1500秒を各6秒観測した。
これはYADIFのfilm経路がqueue再同期後も復帰するかを見る結合試験であり、2変更の速度寄与を分離する比較ではない。

| target | 初画 | playing | 観測したmode | 6秒後 |
| ---: | ---: | ---: | --- | --- |
| 120 s | 186.8 ms | 172.9 ms | video / film | video、37.9fps |
| 420 s | 186.1 ms | 230.1 ms | film | film、24.0fps |
| 900 s | 276.8 ms | 263.9 ms | video / film | film、23.9fps |
| 1500 s | 310.9 ms | 304.5 ms | video / film | video、49.1fps |

420秒と900秒を交互に10回seekして各4秒観測すると、10/10で目的時刻のframeが提示された。
初画は中央値280.5ms、最大310.0ms、playingは中央値270.9msだった。
最後の走行でqueue reset counterが2から3へ増えたが、その走行も初画271.7msで復帰し、4秒後はfilm判定だった。

120秒と1500秒ではmodeが切り替わり、420秒と900秒でも一部の走行は過渡的にvideoを経由した。
したがってMADDER全区間を24fpsとは扱わず、420秒と900秒も今回観測した短いfilm候補区間としてだけ使う。
各走行は[madder-film-seek.json](madder-film-seek.json)に保存した。

## 長時間TSの遠距離シーク

時間からbyte位置を求める処理が長時間録画で悪化するか確認するため、42,955,071,712 B、duration 24,014.62秒の「ミュージックステーション SUPER LIVE 2025」で3600、12000、22000秒へシークした。
YADIFは無効にし、player、Rangeサーバー、Galaxy Chromeは上と同じ条件を使った。

| target | probe | T0→response | T0→first fragment | T0→append済み | T0→frame | 安定判定 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3600 s | 2 × 128 KiB | 101.2 ms | 296.2 ms | 306.6 ms | 344.9 ms | 360.5 ms |
| 12000 s | 2 × 128 KiB | 96.6 ms | 320.3 ms | 329.3 ms | 374.9 ms | 423.0 ms |
| 22000 s | 2 × 128 KiB | 114.5 ms | 272.1 ms | 280.9 ms | 389.9 ms | 403.7 ms |

全3点でPTS探索は2 probeで収束し、4回上限には達しなかった。
本体Rangeの初回転送量は約41〜46MiBだった。
22000秒では先読み停止後の継続Rangeが1本追加されたが、初画後のrequestであり初画遅延には含めない。
この素材では永続indexで省けるのは主にT0からresponseまでの約0.1秒で、first fragmentまでの残り約0.16〜0.22秒とdecoder提示までの待ちは残る。

## seek probe標本の上書き修正

Workerは128KiB probeで得た`{Range開始byte, 最初のPTS}`をメモリ内indexへ保存する。
現行コードは本体変換の最初のfragmentができた時にも、同じRange開始byteへfragment開始時刻を記録していた。
Range開始からPAT/PMT、PES、GOPまでの読み捨てがあるため、12 seekでfragment時刻は同じbyteのprobe PTSより0.17〜0.86秒後だった。

後者の5行を削除し、測定したprobe標本を保持する版を、乃木坂工事中の600秒台と900秒台を交互に動かして比較した。
最初の遠距離2 seekはindex学習用として集計から除いた。

| 経路 | 現行の追加probe | 修正後の追加probe | 現行first fragment中央値 | 修正後first fragment中央値 |
| --- | ---: | ---: | ---: | ---: |
| 直接デモ、現行→修正 | 4/10 | 0/10 | 55.7〜81.2ms | 56.3ms |
| 直接デモ、修正→現行の逆順 | 4/10 | 0/10 | 55.7ms | 53.6ms |
| 実KonomiTV / desktop Chrome | 2/10 | 0/10 | 78.5ms | 83.1ms |
| 実KonomiTV / Galaxy Chrome、旧順次比較 | 4/10 | 0/10 | 122.1ms | 98.1ms |
| 実KonomiTV / Galaxy Chrome、単一タブLAN A/B | 7/20 | 0/20 | 141.0ms | 144.3ms |

直接デモではbuild順とtarget順を反転しても追加probeの差が再現した。
したがって「補間の誤学習による余分なRange requestを除く」効果は修正へ帰属できる。
旧実KonomiTV比較の初画中央値はdesktop 304.7→229.6ms、Galaxy 320.8→195.9msだったが、buildを交互実行しておらず、Galaxyはタブ状態も記録していなかったため効果量には使わない。

Galaxyは各ブロックの開始前後をpage/worker target 0件、測定中を前景視聴タブ1枚に固定し、基準・修正・修正・基準の順で再測定した。
最初の遠距離2 seekを各タブのindex学習として除いた20 seekでは、追加probeを含む走行が7/20から0/20になった（Fisherの正確確率検定、両側`p=0.0083`）。
response中央値は62.4→59.5ms、first fragmentは141.0→144.3ms、append完了は153.4→157.0msだった。
修正版のplayingとpost-seek canvas初描画は54〜56ms早かったが、first fragmentまでの短縮を伴わず、このindex更新が当該seekのdecoder復帰を直接変える経路もないため、修正効果とは扱わない。
全イベントは[単一タブprobe標本A/B](galaxy-probe-sample-single-tab-ab.json)に保存した。

修正は`otya128/mpeg2toh264`向けの公開branch `fix/preserve-seek-probe-sample`、commit `a10253e`に分離した。
計測用のprobe byte、PTS、first fragment時刻は`feat/seek-timing-context`の`ffe2893`に分離し、`presented`の意味を可視初画と区別する文書追補後のbranch HEADは`58a9920`である。
全走行は[seek-index-sample.json](seek-index-sample.json)に保存した。

## 試作して保留した小改善

### 要求時刻より後への着地を許す場合の上限試験

mpeg2toh264は目的時刻の1秒前を探索し、後続GOPから変換する。
目的時刻より後へ着地して見たい場面を欠落させないための余裕である。
この契約を緩めた場合の効果量を見るため、固定leadだけを0.5秒へ変え、Galaxy Tab S11 Ultraの単一前景タブで乃木坂工事中の同じ5地点を1回ずつ比較した。

| 指標 | 1秒lead | 0.5秒lead | 差 |
| --- | ---: | ---: | ---: |
| 可視canvas初描画 平均 | 222.0ms | 174.6ms | -47.4ms (-21.4%) |
| 可視canvas初描画 中央値 | 221.5ms | 174.9ms | -46.6ms |
| 可視canvas初描画 範囲 | 172.5〜273.3ms | 151.7〜197.7ms | 地点別 -14.1〜-83.1ms |
| `seeked` 平均 | 219.7ms | 162.5ms | -57.2ms (-26.1%) |

1秒leadでは2/5地点で最初のmedia fragmentが目的時刻まで届かず、Chromeのdemux seekが2個目のfragmentを待った。
その2地点では、最初のmedia append完了からdecoder outputまで84.8ms、68.9msだった。
0.5秒leadでは全5地点が最初のfragmentで復帰し、同区間は18.5〜23.3msだった。
したがって短縮の主因はMediaCodec自体ではなく、目的時刻を含む2個目のfragment待ちを避けたことである。

一方、0.5秒leadは2/5地点で目的時刻より93ms、344ms先のkeyframeへ着地した。
また、これはGOPを比較して近いRAPを選ぶ実装ではなく、固定leadを変えただけの代理試験であり、各variant 5回・非交互の暫定値である。
約47msの平均短縮は体感上の小〜中改善だが、精密シークの契約を捨てるほど高い価値とは判断しない。
upstreamの既定動作は維持し、この案は採用しない。
集計値は[0.5秒lead比較](galaxy-seek-lead-half.json)に保存した。

AAC付きsessionの一律1 GOP保留を外し、完成GOPの時間範囲に必要なAAC frameがすでに揃った場合だけ早く出す試作を行った。
「ばけばけ」の3 byte位置で、初回fragmentまでの入力は1,835,008→1,572,864 B、1,966,080→1,703,936 B、1,179,648→1,048,576 Bとなり、128〜256KiB減った。
CPU時間は123.1→127.0ms、152.5→155.8ms、112.6→90.9msで、改善は0〜約22ms、2点は測定揺らぎの範囲で悪化した。
`cargo test -p mpeg2toh264 --test streaming`の54本は通過した。

小さく改善する可能性は残るが、MSEへ渡すaudio/video fragment境界の設計意図を変える割に、今回の支配的な約160〜220msを大きく縮めなかったため採用しなかった。
異なるAAC構成、PID切替、dual mono、PTS不連続、chunk分割でA/V同値性を追加検証できる独立候補として残す。

## MSE reset競合の修正確認

branch `fix/mse-reset-inflight-append`、source commit `b1ffef4`では、進行中appendにqueue entryとseek epochを保持する。
旧appendの`updateend`がreset後に届いても、新しいqueueの先頭をshiftしない。

回帰試験は修正前コードで失敗し、新initの代わりにnew mediaが先にappendされることを再現した。
修正後は同じ試験、player typecheck、Prettier checkが通過した。
修正distをKonomiTVのpackageへ一時配置したGalaxy Chrome試験では、「ばけばけ」の60、600、120秒すべてでappendとframe提示まで完了し、player errorはなかった。
安定判定は361.0、463.0、404.9msだった。
公式KonomiTV backendと実DPlayer UIへ3修正を合成した確認でも、乃木坂1200秒とMADDER900秒のreset後にinit/media append、rVFC、playingまで完了し、player errorはなかった。

この修正は通常seekの平均時間を短縮するものではない。
resetと古いappend完了が競合した場合のinit喪失を防ぐ信頼性修正として扱う。
実利用の長いstall削減量は未立証であり、採用しないYADIF opacity試作とも分離する。

## 完成fragmentの早期受け渡し

branch `fix/deliver-completed-fragments-early`では、入力chunk内ですでに完成したfragmentを、同じchunkから得た後続picture jobの完了前にWorkerへ渡す。
source commitは`43fc440`、Git依存用dist commitは`4ec2092`である。
同期的なreceiver、receiverなし、picture pool、出力順序を対象にした回帰試験とplayer build/typecheckを通した。

デスクトップChromeの実DPlayer UIで、timingだけを加えた対照と早期受け渡し版を同じ録画位置で比較した。
900、1200、1500秒の`seek-requested`から`first-fragment`は、72.1→62.7ms、70.9→61.0ms、79.8→69.4msだった。
`appended`は77.2→67.5ms、76.2→64.9ms、83.9→72.8msだった。
3点ではfirst fragmentを約9〜10ms、appendを約10〜11ms短縮した。
600秒には130.0→64.0msの例があったが、probe数とsessionのwarm状態が一致しないため、約66msを一般的な効果とは扱わない。

## Galaxyの入力先読み上限試作

Galaxy Tab S11 Ultraの実DPlayer UI、ローカルKonomiTV backend、`adb reverse`経路で、Workerの入力queueを32/8 MiBから8/2 MiBへ一時変更した。
各イベントの値は[galaxy-input-prefetch.json](galaxy-input-prefetch.json)に保存した。
この経路はGalaxy上のChrome、decoder、YADIFを通るが、LAN / Wi-FiのRTTや帯域を測るものではない。

600秒では32/8 MiB版が2 probe、first byte 79.1ms、first fragment 139.7ms、append 151.5ms、playing 272.7msだった。
8/2 MiB版は1 probe、first byte 37.4ms、first fragment 134.5ms、append 144.8ms、canplay 213.4msで、操作前がpause状態だったためplayingは比較できない。
first fragmentまでの本体読込量は約12.0 MiB対約11.4 MiBだった。
canplay/playingまででは約38.4 MiB対約11.4 MiBだった。

901秒の再生中seekでは、8/2 MiB版が2 probe、first byte 64.0ms、first fragment 142.5ms、append 149.1ms、playing 272.5msだった。
32/8 MiB版は1 probe、first byte 41.2ms、first fragment 116.3ms、append 135.4ms、playing 153.3msだった。
canplay/playingまでの本体読込量は約11.0 MiB対約19.5 MiBだった。

試作は不要な先読みを減らしたが、初画と再生再開を一貫して短縮しなかった。
走行間でin-memory index、probe数、Range開始位置、decoder状態が一致していないため、901秒の逆転を設定差による悪化とも断定しない。
8/2 MiB変更は正式branchへ入れず、同じseek系列を交互に実行し、中止済みRange量とmedian/p95を比較する候補として残す。
