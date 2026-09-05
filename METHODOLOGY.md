# 測定方法と判定基準

この文書は、KonomiTV録画・テレビ再生の調査で使う指標、合格条件、結果の有効範囲の正本です。個別の測定結果と採否は[`REPORT.md`](REPORT.md)、公開branchと提出先は[`README.md`](README.md)を参照してください。

## 指標

**シーク完了時間**は、シーク先の映像がYADIF canvasに出て、`seeked`の後も消えずに残るまでの時間です。起点は`video.currentTime`を設定した瞬間、または計測版playerがbuffer外シークを受理した`seek-requested`とし、結果に併記します。異なる起点、UI入力を含む値、異なるinstrumentationの値を個別修正の効果量として直接比較しません。

**queue全reset**とは、YADIFのキューを空にして時刻同期をやり直す処理です。

**FIFO破棄**とは、容量確保や実遅延からの追いつきで、キューの先頭から古いfieldだけを捨てる処理です。

**致命的な表示停止**は、利用者が再シークなどを行わない限り、2秒以内に安定した表示進行へ復帰しない事象です。シーク後、通常再生中、異常TS通過時のすべてに適用し、シーク後はシーク要求を起点に判定します。200msのシーク目標を超えただけの事象、2秒未満の一時停止、短い描画間隔の乱れは別の性能指標として扱います。

**FPS安定復帰**は、シーク、異常区間の通過、再生mode切り替え、一時的な負荷などの後に、安定した表示進行へ復帰した直後から可視YADIF canvasへの直接描画を連続3秒間測り、素材とmodeから決まる期待FPSの±1%以内となる状態です。通常のdouble-rate区間では40msを超える描画間隔0回も条件とします。`autoFilm`区間では理論間隔が約41.7msとなるため40msを適用せず、素材の有理数cadenceと表示refreshから決まる表示機会に対して出力が欠けていないことを確認します。端点の計測誤差を考慮し、2.9秒以上を有効な評価窓とします。結果には「シーク後」「異常区間通過後」のように基準事象を付けます。

**FPS安定復帰失敗**は、2.9秒以上の評価窓を取得できた試行がFPS安定復帰の条件を満たさない事象です。評価窓が短い試行は成功にも失敗にも数えず、評価不能として再測定します。

**FPS安定維持**は、基準事象のない定常再生について、走行全体のFPS、描画間隔、dropを評価する指標です。FPS安定復帰の短い3秒窓を長時間の安定維持の根拠へ流用しません。

FPS安定復帰とFPS安定維持は、描画を所有するrealmで既定framebufferへの`drawArrays()`が戻った直後を**描画submit時刻**として観測する回帰判定です。main-thread描画ではpage、OffscreenCanvas Worker描画ではWorker内で記録します。これはcompositorへのscanout時刻ではありません。実際に選ばれた描画backend、Workerの世代・再起動・fallback、時刻原点、計装bufferの欠落数を同時に記録し、想定backendを観測できない走行やtrace欠落がある走行は採用しません。

描画submitの計装を正式なFPS判定に使う前に、同じsource、fixture、設定、端末で計装あり・なしの短時間比較を行い、既存の表示指標に計装固有の退行がないことを確認します。新しい許容閾値は設けません。compositorへのscanout、可視コマ落ち0、画素の正常性、入力欠落と復号依存から避けられない最小drop、可聴A/V同期は別の証拠で確認します。

## 合格条件と性能目標

正常TSと異常TSの致命的な表示停止は、それぞれ試行条件を記録した1時間の自動試験で0件を合格条件とします。これは再現可能な回帰試験の範囲を定めるもので、一般的な発生率が0であることやppm上限を示しません。

正常TSは、1時間連続再生でコマ落ち0件と、素材とdeinterlace設定から決まる理論上の表示FPSの安定維持を目標とします。通常のdouble-rate区間は40msを超える描画間隔0回、`autoFilm`区間は期待する表示機会に対する出力欠落0件を目標とします。番組1本を通したコマ落ちも0件を目標とします。

LAN内clientからのシーク完了時間は200ms以下を目標とします。速度と位置精度が競合する場合は、KonomiTV、DPlayer、mpeg2toh264 upstreamが定める「狙った位置」の意味と優先順位を尊重し、性能だけを理由にシークのsemanticsを変えません。

異常TSは、利用者操作なしで再生を継続または2秒以内に安定復帰し、コマ落ちを入力欠落と復号依存から避けられない最小範囲に抑え、復帰後に理論FPSと音声同期へ戻ることを必須条件とします。致命的停止とFPS安定復帰失敗を別々に集計します。

`autoFilm`のfilm区間は`24000/1001fps`、通常のdouble-rate区間は`60000/1001fps`を期待値とし、film↔video境界と通常60iへの復帰も確認します。24fpsや60fpsへの丸め値を判定に使いません。表示refreshで割り切れないfilm区間は、一定間隔の描画を要求せず、各出力が有理数cadenceに対応する表示機会へ割り当てられているかで評価します。

テレビのリアルタイム再生では、時間経過とともに放送時刻に対する再生遅延が継続的に蓄積しないことも確認します。数値基準が確立していない間は、根拠なく閾値を定義しません。

目標達成後も、技術的に妥当な改善余地がなくなるまで検証を続けます。

## Fixture

正常TSの性能試験には、TS packet破損、PTS / DTS不連続、欠落frameがないことをFFprobe / FFmpegと実機traceで確認した区間を使います。素材側の欠陥に一致するdropをplayer固有の回帰へ数えません。

異常TSは、欠陥の種類、byte位置、時刻、影響packetとpicture、fixtureのSHA-256を固定します。packet欠落数、GOP内位置、picture type、picture structureが異なる複数録画の独立した実在欠陥を使い、得られていないfield picture、音声、PAT / PMT、PTS / PCR、splice異常は合成fixtureで補います。実在欠陥と合成欠陥の結果を区別します。

3:2素材は映像を再encodeせず`-c copy`で切り出し、切り出し後の開始・終了時刻、cadence、decode error、SHA-256を確認します。実写とanimeを別群にし、単一素材や低動き区間だけで一般化しません。

## 結果を採用する条件

- targetとcontrolは同じfixture、SHA-256、設定、経路、表示条件、runnerで比較します。
- 主計測では録画TSをKonomiTV server側のローカルNVMeへcopyし、copy元とSHA-256を照合します。CIFS経由の絶対時間を主結果へ使いません。
- source、生成済みdist、KonomiTV client、実配信asset、fixture、runner、collector、validator、summarizerを走行前にhashで固定します。
- 主張ごとに、その数値を出したbuildを対応付けます。診断buildや別branchの値を評価対象buildへ流用しません。
- 測定中にbuild、script、fixture、設定を変更した走行や、同一hostのbuild・FFmpeg解析・indexer負荷が混ざった走行は採用しません。
- GalaxyのLAN絶対時間は端末から隔離serverへLAN直結した結果を使います。`adb reverse`はbrowser、decoder、deinterlacerの確認に限ります。
- Windowsは指定した同一電源mode内のbranch A/Bに使い、通常設定Windowsや他端末との絶対比較に使いません。
- 全画面を主条件とし、非全画面はUI負荷を含む補助条件として分けます。
- 正常TSと異常TS、単体demoとend-to-end、診断計装と正式計測を混ぜません。
- 低頻度事象を比較するときは、走行時間だけでなく事象の機会数を示し、機会の独立性や条件差を確認したうえで、主張に対応する信頼区間または検定方法を定めます。1本の走行で0件だったことだけを、別のbuildより優れている根拠にはしません。
- targetが独立した必須条件に失敗した場合、controlの結果は原因がtarget固有か共通かを切り分ける証拠として扱い、targetの不合格を取り消す根拠にはしません。
- 終了時にvideo停止、fullscreen解除、検証tab閉鎖、専用browser・転送・隔離server停止を確認できない走行は採用しません。

`droppedVideoFrames`はpredecodeまたは表示期限超過のdropであり、最終YADIF canvasの可視コマ落ち数ではありません。音声decode byteの進行も可聴A/V同期を直接示しません。各観測値が証明する層を越えて主張しません。
