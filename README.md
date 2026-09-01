# KonomiTV 録画 TS シーク調査

KonomiTV の「録画 MPEG-2 TS をブラウザーで直接再生する経路」について、シーク後に映像が戻るまでの処理をコードと実機で調べた記録です。

主な結果は次のとおりです。

- シーク位置は、永続 GOP index ではなく、小さな HTTP Range で PTS を探すメモリ内 index から求めます。
- 6時間40分、約43GBのTSでも探索は各地点2 probe、約0.1秒で収束しました。この条件では、初回fragment生成とdecoder再開の方が長い待ちでした。
- Galaxy Tab S11 Ultra では、不透明なYADIF canvasがvideoを覆うとvideo callbackが約15Hzへ落ち、2倍レート出力が約30fpsになりました。`opacity: 0.999`で約60fpsへ戻りましたが、これは原因調査中の暫定回避策です。
- MSE queueの世代管理修正は模擬競合を防ぎますが、実Chromeの通常シークは平均251.4msから250.1msで、有意な短縮を確認できませんでした。実利用でのstall削減量も未立証です。
- 完成fragmentを早く渡す試作は、デスクトップの同じ3地点で初回fragmentを約9〜10ms短縮しました。

詳しいデータフロー、仮説評価、改善候補は [REPORT.md](REPORT.md) にあります。実機条件と素材ごとの結果は [results/device-results.md](results/device-results.md)、機械可読な集計値は [results](results/) に置いています。

録画ファイル、認証情報、LAN内アドレス、ローカルパス、アクセスログは含みません。番組名は素材の識別用であり、録画データ自体は配布しません。乃木坂工事中の全区間を60fps素材、MADDERの全区間を24fps素材とは扱っていません。

このリポジトリの文書とデータは [CC0 1.0](LICENSE) で公開します。
