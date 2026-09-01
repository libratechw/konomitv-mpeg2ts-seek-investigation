# KonomiTV 録画 MPEG-2 TS 直接再生調査

KonomiTV の「録画 MPEG-2 TS をブラウザーで直接再生する経路」について、シーク後の復帰時間、定常再生のFPS、コマ落ち、短いカクつき、長時間stallをコードと実機で調べた記録です。

リポジトリ名には調査開始時の `seek-investigation` が残っていますが、対象はシークだけではありません。素材本来のcadenceを維持し、コマ落ちせず、負荷やシークの後も安定した表示へ戻るまでを扱います。

## PR候補の優先順位

優先順位は、確認できた効果、正しさへの影響、差分の理解しやすさ、レビュー負荷、将来の保守コストから決めています。`軽`は局所的で契約変更がない変更、`中`は状態管理または小さなAPI追加、`重`は複数層を横断する変更です。生成済み`dist`を追跡するtsukumijimaフォーク向けbranchでは、sourceとdistを別コミットにしています。

| 順位 | Priority | PR候補branch | 提出先 | 目的 | 修正内容 | 確認できた効果 | 変更の重さ |
| ---: | --- | --- | --- | --- | --- | --- | --- |
| 1 | P0 | [`fix/preserve-seek-probe-sample`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-seek-probe-sample) (`a10253e`) | otya128 | 実測したbyte→PTS標本を壊さない | first fragment時刻でprobe標本を上書きする5行を削除 | 追加probe 14/40→0/40。可視初画のtarget対応中央値−71.3ms、中央値296.3→244.3ms | **軽**。1ファイル・5行削除、保守負荷小 |
| 2 | P0 | [`feat/report-ts-restart-offsets`](https://github.com/libratechw/mpeg2toh264/tree/feat/report-ts-restart-offsets) (`bfefdf8`) | otya128 | 再開可能なTS位置をcoreから安全に報告する | fragmentへ直近PAT/PMTを含む`restartOffset`を付与し、別Sessionで同じGOPと音声を再開できる試験を追加 | core単体の再開同値性試験と全Rust testが成功。速度効果は次のplayer PRとの組み合わせで測る | **重**。TS demux、GOP、Session、WASM APIを横断。公開値は`restartOffset`だけに限定 |
| 3 | P0 | [`perf/reuse-observed-ts-restarts`](https://github.com/libratechw/mpeg2toh264/tree/perf/reuse-observed-ts-restarts) (`295b692`) | otya128 | 一度確認した位置への後続seekでprobeと余分な復号を省く | 観測済みGOPと安全位置をplayer内だけに保持し、要求時刻以前1秒以内の最新位置を再利用 | 同等試作ではGalaxyのprobe 40→0、canvas中央値226.5→161.5ms、p95 278.4→220.5ms、40/40が250ms以下。正式branchを組み込んだ再測定は進行中 | **中**。worker 1ファイル、core PRに依存。永続形式は増やさない |
| 4 | P0 | [`fix/separate-yadif-queue-recovery`](https://github.com/libratechw/mpeg2toh264/tree/fix/separate-yadif-queue-recovery) (source `26484fd`、dist `27b327e`) | tsukumijima | queue満杯と時刻同期破綻を分け、カクつきと長時間stallを防ぐ | 容量不足は必要枚数だけFIFO破棄し、表示不能な未来時刻列だけ全reset | seek後停止7/90→0/90を維持。注入試験の全reset 14〜15→0、最大lateness 83.3→32.6ms。通常30秒59.768fps | **中**。YADIF 1ファイルのqueue policy。fork固有機能として保守 |
| 5 | P0 | [`fix/preserve-destination-frame-on-seek`](https://github.com/libratechw/mpeg2toh264/tree/fix/preserve-destination-frame-on-seek) (source `2d072f3`、dist `f3ba99d`) | tsukumijima | seeked直前に描画済みの目的frameを消さない | playhead近傍の描画済みframeを記録し、同じseekの`seeked`でcanvasを再消去しない | Linux 40回のp95 246.5→178.9ms、最大280.0→180.4ms。Galaxyはp95 193.2ms、最大212.8msで退行なし | **中**。YADIF 1ファイルだがseeking/history状態のレビューが必要 |
| 6 | P1 | [`fix/mse-reset-inflight-append`](https://github.com/libratechw/mpeg2toh264/tree/fix/mse-reset-inflight-append) (`f8ab9c7`) | otya128 | 古いappend完了が新seekのinit segmentを失わせる競合を防ぐ | SourceBuffer操作とseek世代を対応付け、旧`updateend`を新queueへ適用しない | 修正前に失敗する競合試験が成功。通常seek平均251.4→250.1msで速度差はなく、実利用のstall削減量は未立証 | **中**。MSE状態管理と回帰試験。将来保守負荷は小〜中 |
| 7 | P1 | [`feat/seek-timing-context`](https://github.com/libratechw/mpeg2toh264/tree/feat/seek-timing-context) (`58a9920`) | otya128 | Rangeからdecoder提示までを同じseek IDで分解する | player、worker、transcoder、picture pool、MSEへtiming contextを伝播 | 直接の速度改善なし。probe標本の誤上書き、先頭IDR job 33〜40ms、append後変動を分離できた | **重**。10ファイル・複数層を横断し、公開イベント契約の保守が必要 |
| 8 | P3 | [`fix/deliver-completed-fragments-early`](https://github.com/libratechw/mpeg2toh264/tree/fix/deliver-completed-fragments-early) (`30ad508`) | otya128 | 完成fragmentと後続変換を重ねる | transcoderから完成fragmentを逐次通知する | GalaxyとローカルSSD Chromeで初回fragment・初画の一貫した短縮なし。後続throughput候補としてのみ残す | **中〜重**。transcoder/workerの順序、cancel、backpressureのレビューが必要 |

順位2と3は別PRです。coreの再開位置契約を先にレビューし、その祖先上でplayerの利用policyを提案します。順位4と5はtsukumijimaフォーク固有YADIFの独立PRで、upstream向け変更へ混ぜません。順位8は効果が立証できるまで提出を急ぎません。

主な結果は次のとおりです。

- シーク位置は、永続 GOP index ではなく、小さな HTTP Range で PTS を探すメモリ内 index から求めます。
- 6時間40分、約43GBのTSでも探索は各地点2 probeで収束しました。当時はタブ数を記録していないため絶対時間は主結果から外しましたが、毎回先頭から全体走査する構成ではありません。
- Galaxy Tab S11 Ultra でYADIF出力が約30fpsへ落ち、`opacity: 0.999`の試作後に約60fpsへ戻る走行がありました。しかし、生成時から不透明な対照を再試験すると30秒と12秒の両方で約60fpsを維持しました。`opacity`変更は再現性のある修正ではないため、PR候補から外しています。
- Galaxyの単一タブA/Bで、YADIFの表示がほぼ停止する状態を基準版7/90、upstreamのqueue再同期をフォークへ戻した版0/90で確認しました。修正版ではqueue resetが29回作動しましたが、通常時の1.8秒窓中央値は44.94→44.97fpsでほぼ同じです。この変更は平均fps改善ではなく、未来へ連鎖したfield時刻を戻して稀な長時間stallを防ぐ修正です。
- queue満杯と時刻同期破綻を分ける全画面注入試験では、全消去版だけ14〜15回のresetと最大83.3msのlatenessが発生しました。必要枚数だけFIFO破棄する版は全reset 0回、最大32.6msでした。このqueue処理だけを公開`fix/separate-yadif-queue-recovery`へ分離し、前身と同じ90回seekで停止0件、通常30秒59.77fpsを確認しました。1 rAFにつき1 field化の通常時改善は確認できなかったため、別候補として保留しています。
- Linux Chromeでは、目的frameが`seeking=true`のまま描画された直後にfork固有の`seeked`処理がcanvasを隠し、次frameまで約149ms待ち直す競合を確認しました。公開`fix/preserve-destination-frame-on-seek`では早着した5/5走行でcanvasを保持しました。全画面40回のp95 / 最大はLinuxで246.5 / 280.0msから178.9 / 180.4msとなり、Galaxyでも193.2 / 212.8msで40/40回が250ms以下でした。Galaxyでは早着条件自体が発生しなかったため、同端末の値は退行なしの証拠です。
- MSE queueの世代管理修正は模擬競合を防ぎますが、実Chromeの通常シークは平均251.4msから250.1msで、有意な短縮を確認できませんでした。実利用でのstall削減量も未立証です。
- 完成fragmentを早く渡す試作は、デスクトップの同じ3地点で初回fragmentを約9〜10ms短縮しました。しかし、不要タブを閉じたGalaxyの8ブロック・各40 seek A/Bでは、first fragment中央値133.5→140.2ms、可視canvas初描画257.1→274.5msで、差の95%区間はいずれも0を含みました。一時markでも最初の早期通知はfirst fragment後10/10だったため、初画改善としては優先度を下げ、後続fragmentのthroughput候補として残しています。
- KonomiTVと録画TSが同じPCにある条件へ合わせ、乃木坂工事中をサーバー側ローカルNVMeへコピーしてChromeでB-F-F-B比較を追加しました。300秒ではfirst fragment平均82.5→77.4ms、450秒では65.7→70.6msで、完成fragment早期受け渡しによる一貫した短縮はありませんでした。この走行では`playing`が出ておらず、停止状態のplayer内部比較です。約0.96秒だった`presented`は前景再生中の体感レイテンシに使いません。
- probeで測ったRange開始byteとPTSの対応を、後続のfirst fragment時刻で上書きしていました。Galaxyの新規タブ・全画面・LAN直結B-F-F-B再検証では、この上書きをやめると追加probeが14/40から0/40になり、20地点中12地点で要求時刻を越えない範囲の新しいGOPを選びました。実際にcanvasを可視化した初画はtarget対応中央値71.3ms短縮し、中央値296.3→244.3ms、p90 373.0→280.7msでした。中央値は250ms目標内ですが、安定達成には残るtailの改善が必要です。
- 一度変換したGOPのTS byteとPAT/PMT安全位置をplayer内で再利用する診断版では、Galaxyの反復seek 40回でprobeが40件から0件になり、canvas中央値226.5→161.5ms、p95 278.4→220.5ms、250ms以下28/40→40/40でした。永続indexではなく実際に確認した位置だけを再利用します。正式化する場合は、coreの位置報告とplayerのseek policyを別の変更にします。
- 既定では先頭fragmentだけがrandom accessで、後続約0.5秒fragmentは先頭へ依存していました。毎GOPにnon-IDR recovery pointを入れ、第2fragmentからMediaCodecを開始すると`appended`→`canplay`中央値は101.4→33.3msとなり、約68msの復号・破棄を確認できました。しかし第2fragment生成待ちでappendが中央値69.8ms遅れ、可視初画は中央値+5.7ms、平均+1.3msで改善しませんでした。次の有力案は後続fragmentを待つことではなく、変換前に要求時刻以前で最新のRAP byteを得て、そこを最初のfragmentにすることです。
- queue再同期版の旧MADDER試験はfilm候補2区間への10回seekすべてで初画が返りましたが、絶対時間はタブ状態を固定した新測定へ置き換えました。区間によってvideo/film判定が切り替わるため、録画全体を24fpsとは扱っていません。
- 古い検証タブが設定と再生資源を残し得ることが分かったため、Galaxyの絶対時間を対象タブ1枚だけで再測定しました。可視YADIF canvas初描画の中央値 / p90は乃木坂工事中215.2 / 261.3ms、MADDER #08 267.4 / 311.4msです。既存`presented` eventは`video.seeking`解除を待ってMADDERを約200ms過大評価していたため、画面初画の指標から外しました。以前の絶対値も主結果から外しています。
- 目的時刻より前から復号する量を1秒から0.5秒へ減らす試作では、乃木坂工事中の同じ5地点で可視初画が平均222.0→174.6ms（平均47.4ms、約21%短縮）でした。約200msの操作応答に対する21%は官能評価する価値があります。ただし2/5地点では要求時刻より93ms、344ms先へ着地しました。これは近傍RAP方式そのものではなく固定leadを変えた1走行の代理試験であり、mpeg2toh264 upstreamの「要求位置を欠落させない」既定方針は変更しません。
- `lead=1.0`と`0.9`を単一タブで交互比較すると、確認できた4地点では両版が同じkeyframeを選びました。小さい固定補正だけではGOP選択も速度も変わらない場合があります。先行を許さず短縮する案は、固定量を引いた時刻を現行seekへ渡すのでなく、RAP時刻を確認して元の要求時刻以前で最新のRAPを選ぶ方式として検討します。
- PAT/PMTを含む安全な直前RAPを選ぶ線形scannerは約5MiBを5.1msで処理できました。しかしseekごとに4〜8MiBを先読みする試作は、300秒で現行と同じfragmentへ着地して221.4→240.3ms、900秒でRAPをbracketできずfallbackして191.1→238.9msでした。毎seekの広域scanは採用せず、再生中の学習や永続indexから追加取得なしでRAPを得られる場合だけ再評価します。

詳しいデータフロー、仮説評価、改善候補は [REPORT.md](REPORT.md) にあります。実機条件と素材ごとの結果は [results/device-results.md](results/device-results.md)、機械可読な集計値は [results](results/) に置いています。

録画ファイル、認証情報、実際のLAN内アドレス、ローカルパス、アクセスログは含みません。番組名は素材の識別用であり、録画データ自体は配布しません。乃木坂工事中の全区間を60fps素材、MADDERの全区間を24fps素材とは扱っていません。

このリポジトリの文書とデータは [CC0 1.0](LICENSE) で公開します。
