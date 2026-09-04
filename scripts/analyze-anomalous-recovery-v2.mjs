import fs from 'node:fs';

const input = process.argv[2];
const defectMediaTime = Number(process.argv[3]);
const expectedDrawFps = Number(process.argv[4] ?? (60000 / 1001));
if (!input || !Number.isFinite(defectMediaTime) ||
    !Number.isFinite(expectedDrawFps) || expectedDrawFps <= 0) {
  throw new Error(
    'usage: node analyze-galaxy-anomalous-recovery.mjs INPUT_JSON DEFECT_MEDIA_TIME [EXPECTED_DRAW_FPS]',
  );
}

const document = JSON.parse(fs.readFileSync(input, 'utf8'));
const sample = document.sample ?? document;
const startedAt = sample.performanceTimeRange?.startedAt;
if (!Number.isFinite(startedAt) || !Number.isFinite(sample.performanceTimeRange?.endedAt) ||
    !Array.isArray(sample.videoFrames) ||
    !Array.isArray(sample.draws) || sample.videoFrames.length < 2 || sample.draws.length < 8) {
  throw new Error('input does not contain a complete steady trace');
}

const intervals = entries => entries.slice(1).map((after, index) => ({
  before: entries[index],
  after,
  intervalMs: after.at - entries[index].at,
}));
const videoIntervals = intervals(sample.videoFrames).map(interval => ({
  ...interval,
  mediaTimeDeltaMs: (interval.after.mediaTime - interval.before.mediaTime) * 1000,
}));
const drawIntervals = intervals(sample.draws);
const spanning = videoIntervals.find(interval =>
  interval.before.mediaTime <= defectMediaTime && interval.after.mediaTime >= defectMediaTime
);
if (!spanning) throw new Error('no video interval spans the known defect media time');
const defectInterval = spanning;

const stableDrawCount = 8;
const maximumStableIntervalMs = 50;
const minimumStableSpanMs = 100;
const firstDrawIndex = sample.draws.findIndex(draw => draw.at >= defectInterval.after.at);
let stable = null;
for (let index = firstDrawIndex; index >= 0 && index + stableDrawCount <= sample.draws.length; index++) {
  const sequence = sample.draws.slice(index, index + stableDrawCount);
  const sequenceIntervals = intervals(sequence).map(interval => interval.intervalMs);
  const spanMs = sequence.at(-1).at - sequence[0].at;
  if (sequenceIntervals.every(value => value <= maximumStableIntervalMs) &&
      spanMs >= minimumStableSpanMs) {
    stable = {
      firstDrawAt: sequence[0].at,
      confirmedAt: sequence.at(-1).at,
      spanMs,
      maximumIntervalMs: Math.max(...sequenceIntervals),
    };
    break;
  }
}

const fatalDeadlineMs = 2000;
const stableConfirmationMs = stable ? stable.confirmedAt - defectInterval.before.at : null;
const surroundingDrawIntervals = drawIntervals.filter(interval =>
  interval.before.at <= defectInterval.after.at && interval.after.at >= defectInterval.before.at
);
const largestSurroundingDrawGap = surroundingDrawIntervals.reduce(
  (largest, interval) => largest === null || interval.intervalMs > largest.intervalMs ? interval : largest,
  null,
);

const expectedFpsToleranceRatio = 0.01;
const cadenceWindowMs = 3000;
const trailingWindowTargetMs = 5000;
const summarizeDrawWindow = draws => {
  const windowIntervals = intervals(draws).map(interval => interval.intervalMs);
  const durationMs = draws.length > 1 ? draws.at(-1).at - draws[0].at : 0;
  const drawFps = durationMs > 0 ? (draws.length - 1) * 1000 / durationMs : null;
  const fpsErrorRatio = drawFps === null
    ? null
    : Math.abs(drawFps - expectedDrawFps) / expectedDrawFps;
  return {
    drawCount: draws.length,
    durationMs,
    drawFps,
    fpsErrorRatio,
    fpsWithinOnePercent: fpsErrorRatio === null ? null : fpsErrorRatio <= expectedFpsToleranceRatio,
    intervalsOver40Ms: windowIntervals.filter(value => value > 40).length,
    maximumIntervalMs: windowIntervals.length > 0 ? Math.max(...windowIntervals) : null,
  };
};
const afterDefectDraws = sample.draws.filter(draw => draw.at >= defectInterval.after.at);
let cadence = null;
let cadenceEndIndex = 0;
for (let startIndex = 0; startIndex < afterDefectDraws.length; startIndex++) {
  cadenceEndIndex = Math.max(cadenceEndIndex, startIndex + 1);
  while (cadenceEndIndex < afterDefectDraws.length &&
         afterDefectDraws[cadenceEndIndex].at - afterDefectDraws[startIndex].at < cadenceWindowMs) {
    cadenceEndIndex++;
  }
  if (cadenceEndIndex >= afterDefectDraws.length) break;
  const window = afterDefectDraws.slice(startIndex, cadenceEndIndex + 1);
  const summary = summarizeDrawWindow(window);
  if (summary.fpsWithinOnePercent && summary.intervalsOver40Ms === 0) {
    cadence = {
      startsAt: window[0].at,
      confirmedAt: window.at(-1).at,
      ...summary,
    };
    break;
  }
}
const trailingWindowStart = Math.max(
  defectInterval.after.at,
  sample.performanceTimeRange.endedAt - trailingWindowTargetMs,
);
const trailingDraws = sample.draws.filter(draw =>
  draw.at >= trailingWindowStart && draw.at <= sample.performanceTimeRange.endedAt
);
const trailing = summarizeDrawWindow(trailingDraws);
const trailingWindowSufficient = trailing.durationMs >= cadenceWindowMs;

// A transport loss can affect pictures presented after the first interval that
// crosses its media time, especially in an open GOP.  Keep the trigger interval
// separate from the whole recovery region so a later, larger gap is not hidden.
const recoveryRegionEndAt = cadence?.startsAt ?? sample.performanceTimeRange.endedAt;
const recoveryVideoIntervals = videoIntervals.filter(interval =>
  interval.before.at <= recoveryRegionEndAt && interval.after.at >= defectInterval.before.at
);
const recoveryDrawIntervals = drawIntervals.filter(interval =>
  interval.before.at <= recoveryRegionEndAt && interval.after.at >= defectInterval.before.at
);
const largest = (entries, value) => entries.reduce(
  (current, entry) => current === null || value(entry) > value(current) ? entry : current,
  null,
);
const largestRecoveryVideoInterval = largest(
  recoveryVideoIntervals,
  interval => interval.mediaTimeDeltaMs,
);
const largestRecoveryDrawInterval = largest(
  recoveryDrawIntervals,
  interval => interval.intervalMs,
);
const fatalStop = stableConfirmationMs === null || stableConfirmationMs > fatalDeadlineMs ||
  (largestRecoveryDrawInterval?.intervalMs ?? 0) > fatalDeadlineMs;

const decoderSamples = sample.decoderSamples ?? [];
const lastDecoderBefore = decoderSamples.filter(entry => entry.at <= defectInterval.before.at).at(-1) ?? null;
const firstAudioProgress = lastDecoderBefore?.audioDecodedBytes === null ||
  lastDecoderBefore?.audioDecodedBytes === undefined ? null : decoderSamples.find(entry =>
    entry.at > defectInterval.before.at &&
    entry.audioDecodedBytes !== null &&
    entry.audioDecodedBytes > lastDecoderBefore.audioDecodedBytes
  ) ?? null;
const playerStats = sample.playerStats ?? [];
const stats = sample.stats ?? [];
const localDelta = (entries, key, startAt, endAt) => {
  const before = entries.filter(entry => entry.at <= startAt).at(-1);
  const after = entries.filter(entry => entry.at <= endAt).at(-1);
  return before && after && Number.isFinite(before[key]) && Number.isFinite(after[key])
    ? after[key] - before[key]
    : null;
};
const recoveryWindowEnd = sample.performanceTimeRange.endedAt;
const playbackErrors = (sample.playbackEvents ?? []).filter(event => event.type === 'error');
const visibilityChanges = (sample.playbackEvents ?? []).filter(
  event => event.type === 'visibilitychange',
);
const userInteractionEvents = sample.userInteractionEvents ?? [];
const requiredCleanupKeys = [
  'videoPausedBeforeClose',
  'fullscreenExitedBeforeClose',
  'testPagesClosed',
  'chromeStopped',
  'webapkStopped',
  'adbForwardRemoved',
  'containerStopped',
];
const cleanupVerified = requiredCleanupKeys.every(key => document.cleanup?.[key] === true);

const output = {
  schemaVersion: 2,
  fixture: {
    name: document.fixtureName ?? null,
    sha256: document.fixtureSha256 ?? null,
    defectMediaTime,
  },
  build: {
    sourceHash: document.sourceHash ?? null,
    distHash: document.distHash ?? null,
    asset: document.asset ?? null,
  },
  detectedInputGap: {
    spansKnownDefect: true,
    beforeMediaTime: defectInterval.before.mediaTime,
    afterMediaTime: defectInterval.after.mediaTime,
    mediaTimeDeltaMs: defectInterval.mediaTimeDeltaMs,
    callbackIntervalMs: defectInterval.intervalMs,
    startsAtMs: defectInterval.before.at - startedAt,
    endsAtMs: defectInterval.after.at - startedAt,
  },
  recoveryRegion: {
    startsAtMs: defectInterval.before.at - startedAt,
    endsAtMs: recoveryRegionEndAt - startedAt,
    endReason: cadence === null ? 'trace-ended-before-stable-cadence' : 'stable-cadence-started',
    maximumVideoInterval: largestRecoveryVideoInterval === null ? null : {
      beforeMediaTime: largestRecoveryVideoInterval.before.mediaTime,
      afterMediaTime: largestRecoveryVideoInterval.after.mediaTime,
      mediaTimeDeltaMs: largestRecoveryVideoInterval.mediaTimeDeltaMs,
      callbackIntervalMs: largestRecoveryVideoInterval.intervalMs,
    },
    maximumCanvasDrawIntervalMs: largestRecoveryDrawInterval?.intervalMs ?? null,
  },
  displayRecovery: {
    fatalDefinitionMs: fatalDeadlineMs,
    fatalStop,
    stableDrawCount,
    maximumStableIntervalMs,
    minimumStableSpanMs,
    stableConfirmationMs,
    firstStableDrawAfterGapMs: stable ? stable.firstDrawAt - defectInterval.before.at : null,
    largestSurroundingDrawGapMs: largestSurroundingDrawGap?.intervalMs ?? null,
  },
  cadenceRecovery: {
    expectedDrawFps,
    expectedFpsToleranceRatio,
    qualifyingWindowMs: cadenceWindowMs,
    found: cadence !== null,
    firstQualifyingWindowStartsAfterGapMs: cadence
      ? cadence.startsAt - defectInterval.before.at
      : null,
    confirmedAfterGapMs: cadence ? cadence.confirmedAt - defectInterval.before.at : null,
    firstQualifyingWindow: cadence ? {
      drawCount: cadence.drawCount,
      durationMs: cadence.durationMs,
      drawFps: cadence.drawFps,
      fpsErrorRatio: cadence.fpsErrorRatio,
      intervalsOver40Ms: cadence.intervalsOver40Ms,
      maximumIntervalMs: cadence.maximumIntervalMs,
    } : null,
    trailingWindowTargetMs,
    trailingWindowSufficient,
    trailingWindow: {
      ...trailing,
      browserDroppedFramesDelta: localDelta(
        sample.videoFrames, 'droppedVideoFrames', trailingWindowStart,
        sample.performanceTimeRange.endedAt,
      ),
      yadifLateDelta: localDelta(
        stats, 'late', trailingWindowStart, sample.performanceTimeRange.endedAt,
      ),
    },
    expectedRateRecovered: trailingWindowSufficient &&
      trailing.fpsWithinOnePercent === true && trailing.intervalsOver40Ms === 0,
    zeroVisibleDropProven: false,
    zeroVisibleDropReason: 'Canvas draw calls do not prove compositor scanout, and a skipped 60 Hz presentation can remain below the 40 ms gap threshold.',
  },
  decoderRecovery: {
    audioDecodedBytesAdvanced: firstAudioProgress !== null,
    audioFirstAdvancedAfterGapMs: firstAudioProgress
      ? firstAudioProgress.at - defectInterval.before.at
      : null,
    audioDecodedBytesTotalDelta: sample.decodedBytes?.delta?.audio ?? null,
    videoDecodedBytesTotalDelta: sample.decodedBytes?.delta?.video ?? null,
    browserDroppedFrames: sample.quality?.delta?.dropped ?? null,
  },
  streamRecovery: {
    windowStartsAt: defectInterval.before.at,
    windowEndsAt: recoveryWindowEnd,
    playerDroppedPacketsDelta: localDelta(
      playerStats, 'dropped', defectInterval.before.at, recoveryWindowEnd,
    ),
    playerErrorsDelta: localDelta(playerStats, 'errors', defectInterval.before.at, recoveryWindowEnd),
    playerAudioFramesDelta: localDelta(
      playerStats, 'audioFrames', defectInterval.before.at, recoveryWindowEnd,
    ),
    playerVideoFramesDelta: localDelta(
      playerStats, 'videoFrames', defectInterval.before.at, recoveryWindowEnd,
    ),
    yadifDiscontinuitiesDelta: localDelta(
      stats, 'discontinuities', defectInterval.before.at, recoveryWindowEnd,
    ),
    yadifDegradedDelta: localDelta(stats, 'degraded', defectInterval.before.at, recoveryWindowEnd),
    yadifLateDelta: localDelta(stats, 'late', defectInterval.before.at, recoveryWindowEnd),
    yadifQueueResetDelta: localDelta(
      stats, 'queueResetted', defectInterval.before.at, recoveryWindowEnd,
    ),
    minimumUnavoidableDropProven: false,
    minimumUnavoidableDropReason: 'The trace does not identify every missing input frame and its decode dependencies.',
  },
  unattended: {
    userInteractionEvents,
    playbackErrors,
    visibilityChanges,
    passed: userInteractionEvents.length === 0 && playbackErrors.length === 0 &&
      visibilityChanges.length === 0,
  },
  audioSync: {
    proven: false,
    reason: 'Decoded-byte progress proves that audio decoding continued, but a media element does not expose an independent audible audio clock. A/V sync needs a mux-timeline check or captured-output comparison.',
  },
  cleanup: {
    verified: cleanupVerified,
    requiredKeys: requiredCleanupKeys,
    observed: document.cleanup ?? null,
  },
};

process.stdout.write(`${JSON.stringify(output, null, 2)}\n`);
