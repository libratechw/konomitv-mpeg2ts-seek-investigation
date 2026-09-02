# KonomiTV 録画 MPEG-2 TS 直接再生調査

KonomiTV の「録画 MPEG-2 TS をブラウザーで直接再生する経路」について、シーク後の復帰時間、定常再生のFPS、コマ落ち、短いカクつき、長時間stallをコードと実機で調べた記録です。

リポジトリ名には調査開始時の `seek-investigation` が残っていますが、対象はシークだけではありません。
素材本来のcadenceを維持し、コマ落ちせず、負荷やシークの後も安定した表示へ戻るまでを扱います。

## PR候補の優先順位

優先順位は、確認できた効果、正しさへの影響、差分の理解しやすさ、レビュー負荷、将来の保守コストから決めています。
`軽`は局所的で契約変更がない変更、`中`は状態管理または小さなAPI追加、`重`は複数層を横断する変更です。
生成済み`dist`を追跡するtsukumijimaフォーク向けbranchでは、sourceとdistを別コミットにしています。

総合検証用の[`integration/current-useful-fixes`](https://github.com/libratechw/mpeg2toh264/tree/integration/current-useful-fixes)は、表で「採用」とした互換性のある修正をまとめたbranchです。
upstreamへそのままmergeする対象ではなく、個別PR候補の境界を保ったままKonomiTVで総合効果を測るために使います。
branch固有READMEに、全修正適用前後の比較と、各修正branchへのリンク、目的、内容、効果、レビューコスト、保守コストを掲載しています。
Galaxyの同条件40 seekでは、`tsukumijima/main`からintegrationへの変更で可視初画中央値287.1→145.8ms、p95 349.1→213.4ms、250ms以内14/40→40/40でした。
この総合値は新しいoverflow時刻圧縮をmergeする前の製品コード`e417d12`までで測った値であり、順位5の負荷注入A/Bとは分けています。
PTSとrestart位置の独立管理まで含めてintegrationを再構築した後のGalaxy回帰では、120秒のcanvasが59.933fps、40ms超間隔、YADIFの`late`、`missed`、全resetはいずれも0でした。
40 seekは中央値160.5ms、p95 190.6ms、最大228.8msで、40/40が250ms以下でした。

| 順位 | Priority | PR候補branch | 提出先 | 目的 | 修正内容 | 確認できた効果 | 変更の重さ | 統合版 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P0 | [`fix/preserve-seek-probe-sample`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-seek-probe-sample) (`a10253e`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 実測したbyte→PTS標本を壊さない | first fragment時刻でprobe標本を上書きする5行を削除 | 追加probe 14/40→0/40。可視初画のtarget対応中央値−71.3ms、中央値296.3→244.3ms | **軽**。1ファイルの5行削除で、保守負荷は小さい | 採用 |
| 2 | P0 | [`feat/report-ts-restart-offsets`](https://github.com/libratechw/mpeg2toh264/tree/feat/report-ts-restart-offsets) (`787c7ba`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 再開可能なTS位置をcoreから安全に報告する | fragmentへ直近PAT/PMTを含む`restartOffset`を付与し、PTSとrestart位置を独立したmark列で保持する | 再開同値性試験が成功。PTSなし・restart位置ありのPESが先行PTSを隠す回帰は修正前に失敗し、修正後に成功。速度効果は次のplayer PRとの組み合わせで測る | **重**。TS demux、GOP、Session、WASM APIを横断。公開値は`restartOffset`だけに限定 | 採用 |
| 3 | P0 | [`perf/reuse-observed-ts-restarts`](https://github.com/libratechw/mpeg2toh264/tree/perf/reuse-observed-ts-restarts) (`ac4f879`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 一度確認した位置への後続seekでprobeと余分な復号を省く | 観測済みGOPと安全位置をplayer内だけに保持し、要求時刻以前1秒以内の最新位置を再利用 | 診断版A/Bはprobe 40→0、canvas中央値226.5→161.5ms、p95 278.4→220.5ms。正式branch組み込み版は中央値159.1ms、p95 212.4ms、最大229.0msで40/40が250ms以下 | **中**。worker 1ファイル、core PRに依存。永続形式は増やさない | 採用 |
| 4 | P0 | [`fix/separate-yadif-queue-recovery`](https://github.com/libratechw/mpeg2toh264/tree/fix/separate-yadif-queue-recovery) (source `26484fd`、dist `27b327e`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | queue満杯と時刻同期破綻を分け、カクつきと長時間stallを防ぐ | 容量不足は必要枚数だけFIFO破棄し、表示不能な未来時刻列だけ全reset | seek後停止7/90→0/90を維持。注入試験の全reset 14〜15→0、最大lateness 83.3→32.6ms。通常30秒59.768fps | **中**。YADIF 1ファイルのqueue policy。fork固有機能として保守 | 採用 |
| 5 | P0 | [`fix/compress-yadif-overflow-schedule`](https://github.com/libratechw/mpeg2toh264/tree/fix/compress-yadif-overflow-schedule) (source `7ef6696`、dist `ac2a2a9`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | 容量確保で捨てた表示時刻の穴からFIFO破棄が連鎖するのを防ぐ | 捨てたfieldの`duration`合計を、残った全fieldのpresentation deadlineから引く | 2秒注入の3走行平均で、Galaxyの破棄218.0→0.67 field、Windows 21.67→0.67 field。Galaxyで2/3走行に続いた連鎖と全reset 1回を解消 | **軽〜中**。`#prepareQueue()`の8行。容量破棄時の時刻不変条件を保守 | 採用 |
| 6 | P0 | [`fix/preserve-destination-frame-on-seek`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-destination-frame-on-seek) (source `2d072f3`、dist `f3ba99d`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | seeked直前に描画済みの目的frameを消さない | playhead近傍の描画済みframeを記録し、同じseekの`seeked`でcanvasを再消去しない | Linux 40回のp95 246.5→178.9ms、最大280.0→180.4ms。Galaxyはp95 193.2ms、最大212.8msで退行なし | **中**。YADIF 1ファイルだがseeking/history状態のレビューが必要 | 採用 |
| 7 | P1 | [`fix/present-one-field-per-refresh`](https://github.com/libratechw/mpeg2toh264/tree/fix/present-one-field-per-refresh) (source `fb2e6e4`、dist `21cc3c3`) | [`tsukumijima/mpeg2toh264`](https://github.com/tsukumijima/mpeg2toh264) | 通常のcallback位相差で表示可能なfieldを誤破棄しない | 通常はFIFO順に1 fieldを表示し、最古fieldが2 refreshを超えて遅れた場合だけ追いつく | 120秒2走行平均でGalaxy 59.791→59.932fps、25ms超40→22.5回、`late` 9.5→0。Windows 59.354→59.783fps、25ms超127→43回、`late` 66→15.5。全reset 0 | **中**。YADIF 1関数のpresentation policy。閾値とqueue不変条件を保守 | 採用 |
| 8 | P1 | [`fix/mse-reset-inflight-append`](https://github.com/libratechw/mpeg2toh264/tree/fix/mse-reset-inflight-append) (`f8ab9c7`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 古いappend完了が新seekのinit segmentを失わせる競合を防ぐ | SourceBuffer操作とseek世代を対応付け、旧`updateend`を新queueへ適用しない | 修正前に失敗する競合試験が成功。通常seek平均251.4→250.1msで速度差はなく、実利用のstall削減量は未立証 | **中**。MSE状態管理と回帰試験。将来保守負荷は小〜中 | 採用 |
| 9 | P1 | [`feat/seek-timing-context`](https://github.com/libratechw/mpeg2toh264/tree/feat/seek-timing-context) (`58a9920`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | Rangeからdecoder提示までを同じseek IDで分解する | player、worker、transcoder、picture pool、MSEへtiming contextを伝播 | 直接の速度改善なし。probe標本の誤上書き、先頭IDR job 33〜40ms、append後変動を分離できた | **重**。10ファイルにわたり複数層を横断し、公開イベント契約の保守が必要 | 除外（計測専用） |
| 10 | P3 | [`fix/deliver-completed-fragments-early`](https://github.com/libratechw/mpeg2toh264/tree/fix/deliver-completed-fragments-early) (`30ad508`) | [`otya128/mpeg2toh264`](https://github.com/otya128/mpeg2toh264) | 完成fragmentと後続変換を重ねる | transcoderから完成fragmentを逐次通知する | GalaxyとローカルSSD Chromeで初回fragmentと初画のどちらも一貫した短縮なし。後続throughput候補としてのみ残す | **中〜重**。transcoder/workerの順序、cancel、backpressureのレビューが必要 | 除外（効果未確認） |

順位2と3は別PRです。
coreの再開位置契約を先にレビューし、その祖先上でplayerの利用policyを提案します。
順位4を先にレビューし、その祖先上で順位5のoverflow時刻圧縮と順位7のpresentation policyを独立した兄弟PRとして提案します。
順位6はこれらとハンクが重ならず、並行して提出できます。
これらのfork固有YADIF変更はupstream向け変更へ混ぜません。
順位9は効果が立証できるまで提出を急ぎません。

順位5と7のWindows値は、Ryzen 7 4700Uを電源モード「最適な電力効率」で測った低性能かつ電力制約下の補助条件です。
同一モード内のbranch A/Bとして扱い、Galaxyとの絶対性能比較や通常設定のWindowsを代表する値には使いません。

主な結果は次のとおりです。

- シーク位置は、永続 GOP index ではなく、小さな HTTP Range で PTS を探すメモリ内 index から求めます。
- 6時間40分、約43GBのTSでも探索は各地点2 probeで収束しました。
  当時はタブ数を記録していないため絶対時間は主結果から外しましたが、毎回先頭から全体走査する構成ではありません。
- Galaxy Tab S11 Ultra でYADIF出力が約30fpsへ落ち、`opacity: 0.999`の試作後に約60fpsへ戻る走行がありました。
  しかし、生成時から不透明な対照を再試験すると30秒と12秒の両方で約60fpsを維持しました。
  `opacity`変更は再現性のある修正ではないため、PR候補から外しています。
- Galaxyの単一タブA/Bで、YADIFの表示がほぼ停止する状態を基準版7/90、upstreamのqueue再同期をフォークへ戻した版0/90で確認しました。
  修正版ではqueue resetが29回作動しましたが、通常時の1.8秒窓中央値は44.94→44.97fpsでほぼ同じです。
  この変更は平均fps改善ではなく、未来へ連鎖したfield時刻を戻して稀な長時間stallを防ぐ修正です。
- queue満杯と時刻同期破綻を分ける全画面注入試験では、全消去版だけ14〜15回のresetと最大83.3msのlatenessが発生しました。
  必要枚数だけFIFO破棄する版は全reset 0回、最大32.6msでした。
  このqueue処理だけを公開`fix/separate-yadif-queue-recovery`へ分離し、前身と同じ90回seekで停止0件、通常30秒59.77fpsを確認しました。
  さらに通常は1 rAFにつき1 fieldをFIFO表示し、2 refresh超の実遅延時だけcatch-upする`fix/present-one-field-per-refresh`を別候補にしました。
  GalaxyとWindowsの120秒反復でFPS、25ms超間隔、`late`が改善し、media time進行と全reset 0を維持しました。
- Linux Chromeでは、目的frameが`seeking=true`のまま描画された直後にfork固有の`seeked`処理がcanvasを隠し、次frameまで約149ms待ち直す競合を確認しました。
  公開`fix/preserve-destination-frame-on-seek`では早着した5/5走行でcanvasを保持しました。
  全画面40回のp95 / 最大はLinuxで246.5 / 280.0msから178.9 / 180.4msとなり、Galaxyでも193.2 / 212.8msで40/40回が250ms以下でした。
  Galaxyでは早着条件自体が発生しなかったため、同端末の値は退行なしの証拠です。
- MSE queueの世代管理修正は模擬競合を防ぎますが、実Chromeの通常シークは平均251.4msから250.1msで、有意な短縮を確認できませんでした。
  実利用でのstall削減量も未立証です。
- 完成fragmentを早く渡す試作は、デスクトップの同じ3地点で初回fragmentを約9〜10ms短縮しました。
  しかし、不要タブを閉じたGalaxyの8ブロック、各40 seek A/Bでは、first fragment中央値133.5→140.2ms、可視canvas初描画257.1→274.5msで、差の95%区間はいずれも0を含みました。
  一時markでも最初の早期通知はfirst fragment後10/10だったため、初画改善としては優先度を下げ、後続fragmentのthroughput候補として残しています。
- KonomiTVと録画TSが同じPCにある条件へ合わせ、乃木坂工事中をサーバー側ローカルNVMeへコピーしてChromeでB-F-F-B比較を追加しました。
  300秒ではfirst fragment平均82.5→77.4ms、450秒では65.7→70.6msで、完成fragment早期受け渡しによる一貫した短縮はありませんでした。
  この走行では`playing`が出ておらず、停止状態のplayer内部比較です。
  約0.96秒だった`presented`は前景再生中の体感レイテンシに使いません。
- probeで測ったRange開始byteとPTSの対応を、後続のfirst fragment時刻で上書きしていました。
  Galaxyの新規タブ、全画面、LAN直結のB-F-F-B再検証では、この上書きをやめると追加probeが14/40から0/40になり、20地点中12地点で要求時刻を越えない範囲の新しいGOPを選びました。
  実際にcanvasを可視化した初画はtarget対応中央値71.3ms短縮し、中央値296.3→244.3ms、p90 373.0→280.7msでした。
  中央値は250ms目標内ですが、安定達成には残るtailの改善が必要です。
- 一度変換したGOPのTS byteとPAT/PMT安全位置をplayer内で再利用する診断版では、Galaxyの反復seek 40回でprobeが40件から0件になり、canvas中央値226.5→161.5ms、p95 278.4→220.5ms、250ms以下28/40→40/40でした。
  永続indexではなく実際に確認した位置だけを再利用します。
  正式化する場合は、coreの位置報告とplayerのseek policyを別の変更にします。
- 正式branchを組み込んだtiming版を、Galaxy Chrome、LAN直結、body全画面、右パネルなし、単一タブで40回測ると、`seek-requested`から可視canvas初画は中央値159.1ms、p95 212.4ms、最大229.0msで、全走行が250ms以内でした。
  warm-upで600秒と900秒の安全位置を学習した後の反復seekであり、coldな未知位置の値ではありません。
- 追加YADIF候補まで含む公開integration製品コードを同じ画面条件で40回測ると、`video.currentTime`設定から可視canvas初画は中央値145.8ms、p95 213.4ms、最大232.5msで、40/40が250ms以内でした。
  同じKonomiTVで`tsukumijima/main` `52a3db5`へ戻した40回は中央値287.1ms、p95 349.1ms、最大410.2ms、250ms以内14/40でした。
  120秒定常再生はbaselineが0 / 54.191fps、integrationが59.939 / 59.924fpsでした。
  Original内部videoは30秒でrVFC 29.97fpsを維持しながら`droppedVideoFrames`が10増え、サーバーエンコード1080p60は120秒でrVFC 59.68fps、増分0でした。
  W3C上もこのcounterはpredecodeまたは表示期限超過のdropであり、Originalの最終YADIF canvas上の可視コマ落ち数ではありません。
- Originalの`droppedVideoFrames`は、24 GOPごとに追加される元TSの新しい表示画像に対応しない2個の極短IDR recovery sampleをChromeが表示しないことを数えていました。
  non-IDR recovery pointへ変えるとGalaxyの120秒で40→0になりましたが、可視40ms超間隔は1回残り、シークも既定IDRより安定して速くなりませんでした。
  hardware decoder互換性を優先し、この設定変更は採用しません。
- 残る40ms超canvas間隔は、rAFとWebGL処理が正常なままrVFC入力が約65ms空き、YADIFが保持fieldを使い切ることで発生しました。
  1入力frame分の固定reserveは120秒で40ms超0回でしたが、600秒ではclock差が蓄積して`late` 2071、最大11.15秒停止へ退行したため棄却しました。
  7 slot版は600秒で40ms超0回でもfuture leadが約125msとなるため、可変A/V差を生む形では採用しません。
- 容量確保でFIFOからfieldを捨てても残りのpresentation deadlineを詰めないため、捨てた表示時刻が穴として残り、次の破棄を連鎖させることをコードと時系列で確認しました。
  2秒だけpresentationを1回おきにする試験をWindowsとGalaxyで各3回行うと、deadline圧縮前はGalaxyの2/3走行で連鎖し、破棄fieldは平均218.0、全resetは合計1回でした。
  捨てた`duration`合計を残りのdeadlineから引く`fix/compress-yadif-overflow-schedule`では、GalaxyとWindowsの破棄がともに平均0.67 fieldとなり、Galaxyの全resetも0回でした。
  注入中は意図的に約30fpsへ落とす試験であり、解除後の60fps復帰と連鎖防止を評価しています。
- 乃木坂工事中のローカルSSD fixtureには、映像開始から125.025秒、byte位置202,364,140付近に破損video packetが1個ありました。
  FFprobeの全54,399 video packet走査、FFmpegのdecode警告、GalaxyのrVFC入力停止が同じDTSで一致しました。
  このpacketを横切る走行はコマ落ち目標の判定から外しました。
  [fixture破損と実機traceの対応](results/nogizaka-fixture-video-corruption.json)を保存しました。
- 既知の破損packetより後の187.845〜787.846秒を使ったGalaxy全画面600秒走行では、入力video callback 29.972fpsに対し、double-rate YADIF canvasは59.942fpsでした。
  canvasの40ms超間隔、YADIFの`late`、`degraded`、`discontinuities`、全reset、overflow破棄はすべて0です。
  入力の約30Hzはインターレース映像1 frameごとのcallbackで、最終表示は約59.94 field/秒です。
  [正常負荷600秒の要約](results/galaxy-overflow-compression-clean-600s-summary.json)を保存しました。
- 同じbuildのGalaxy全画面40回seekでは、操作から持続表示される目的canvas初画まで中央値157.2ms、p95 187.1ms、最大197.3msで、40/40が250ms以下でした。
  [40回の各走行](results/galaxy-overflow-compression-visible-seek-40.json)を保存しました。
- 既定では先頭fragmentだけがrandom accessで、後続約0.5秒fragmentは先頭へ依存していました。
  毎GOPにnon-IDR recovery pointを入れ、第2fragmentからMediaCodecを開始すると`appended`→`canplay`中央値は101.4→33.3msとなり、約68msの復号と破棄を確認できました。
  しかし第2fragment生成待ちでappendが中央値69.8ms遅れ、可視初画は中央値+5.7ms、平均+1.3msで改善しませんでした。
  次の有力案は後続fragmentを待つことではなく、変換前に要求時刻以前で最新のRAP byteを得て、そこを最初のfragmentにすることです。
- queue再同期版の旧MADDER試験はfilm候補2区間への10回seekすべてで初画が返りましたが、絶対時間はタブ状態を固定した新測定へ置き換えました。
  区間によってvideo/film判定が切り替わるため、録画全体を24fpsとは扱っていません。
- 古い検証タブが設定と再生資源を残し得ることが分かったため、Galaxyの絶対時間を対象タブ1枚だけで再測定しました。
  可視YADIF canvas初描画の中央値 / p90は乃木坂工事中215.2 / 261.3ms、MADDER #08 267.4 / 311.4msです。
  既存`presented` eventは`video.seeking`解除を待ってMADDERを約200ms過大評価していたため、画面初画の指標から外しました。
  以前の絶対値も主結果から外しています。
- 目的時刻より前から復号する量を1秒から0.5秒へ減らす試作では、乃木坂工事中の同じ5地点で可視初画が平均222.0→174.6ms（平均47.4ms、約21%短縮）でした。
  約200msの操作応答に対する21%は官能評価する価値があります。
  ただし2/5地点では要求時刻より93ms、344ms先へ着地しました。
  これは近傍RAP方式そのものではなく固定leadを変えた1走行の代理試験であり、mpeg2toh264 upstreamの「要求位置を欠落させない」既定方針は変更しません。
- `lead=1.0`と`0.9`を単一タブで交互比較すると、確認できた4地点では両版が同じkeyframeを選びました。
  小さい固定補正だけではGOP選択も速度も変わらない場合があります。
  先行を許さず短縮する案は、固定量を引いた時刻を現行seekへ渡すのでなく、RAP時刻を確認して元の要求時刻以前で最新のRAPを選ぶ方式として検討します。
- PAT/PMTを含む安全な直前RAPを選ぶ線形scannerは約5MiBを5.1msで処理できました。
  しかしseekごとに4〜8MiBを先読みする試作は、300秒で現行と同じfragmentへ着地して221.4→240.3ms、900秒でRAPをbracketできずfallbackして191.1→238.9msでした。
  毎seekの広域scanは採用せず、再生中の学習や永続indexから追加取得なしでRAPを得られる場合だけ再評価します。

詳しいデータフロー、仮説評価、改善候補は [REPORT.md](REPORT.md) にあります。
実機条件と素材ごとの結果は [results/device-results.md](results/device-results.md)、機械可読な集計値は [results](results/) に置いています。

録画ファイル、認証情報、実際のLAN内アドレス、ローカルパス、アクセスログは含みません。
番組名は素材の識別用であり、録画データ自体は配布しません。
乃木坂工事中の全区間を60fps素材、MADDERの全区間を24fps素材とは扱っていません。

このリポジトリの文書とデータは [CC0 1.0](LICENSE) で公開します。
