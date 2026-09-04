import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const analyzer = path.join(import.meta.dirname, 'analyze-anomalous-recovery-v2.mjs');
const temporaryDirectory = fs.mkdtempSync(path.join(os.tmpdir(), 'anomalous-recovery-test-'));

const cleanup = {
  videoPausedBeforeClose: true,
  fullscreenExitedBeforeClose: true,
  testPagesClosed: true,
  chromeStopped: true,
  webapkStopped: true,
  adbForwardRemoved: true,
  containerStopped: true,
};
const frameIntervalMs = 1001 / 60;
const postGapDraws = Array.from({length: 330}, (_, index) => ({
  at: 1510 + index * frameIntervalMs,
}));
const valid = {
  fixtureName: 'fixture.ts',
  fixtureSha256: 'fixture-sha256',
  sourceHash: 'source-hash',
  distHash: 'dist-hash',
  asset: 'asset.js',
  sample: {
    performanceTimeRange: {startedAt: 0, endedAt: 7200},
    videoFrames: [
      {at: 900, mediaTime: 9.9},
      {at: 1000, mediaTime: 10},
      {at: 1500, mediaTime: 10.5},
      {at: 1517, mediaTime: 10.517},
    ],
    draws: [{at: 900}, {at: 917}, ...postGapDraws],
    decoderSamples: [
      {at: 900, audioDecodedBytes: 100},
      {at: 1600, audioDecodedBytes: 200},
    ],
    playbackEvents: [],
    userInteractionEvents: [],
    playerStats: [],
    stats: [],
  },
  cleanup,
};

const analyze = (name, document, defectMediaTime = 10.2) => {
  const input = path.join(temporaryDirectory, `${name}.json`);
  fs.writeFileSync(input, JSON.stringify(document));
  return spawnSync(process.execPath, [analyzer, input, String(defectMediaTime)], {
    encoding: 'utf8',
  });
};

try {
  const success = analyze('success', valid);
  assert.equal(success.status, 0, success.stderr);
  const result = JSON.parse(success.stdout);
  assert.equal(result.schemaVersion, 2);
  assert.equal(result.detectedInputGap.spansKnownDefect, true);
  assert.equal(result.recoveryRegion.maximumVideoInterval.mediaTimeDeltaMs, 500);
  assert.equal(result.recoveryRegion.maximumCanvasDrawIntervalMs, 593);
  assert.equal(result.displayRecovery.fatalStop, false);
  assert.equal(result.cadenceRecovery.found, true);
  assert.equal(result.cadenceRecovery.trailingWindowSufficient, true);
  assert.equal(result.cadenceRecovery.expectedRateRecovered, true);
  assert.equal(result.cadenceRecovery.zeroVisibleDropProven, false);
  assert.equal(result.unattended.passed, true);
  assert.equal(result.cleanup.verified, true);
  assert.equal(result.audioSync.proven, false);
  assert.equal(result.streamRecovery.minimumUnavoidableDropProven, false);

  const delayedLargerGap = structuredClone(valid);
  delayedLargerGap.sample.videoFrames = [
    {at: 900, mediaTime: 9.9},
    {at: 1000, mediaTime: 10},
    {at: 1030, mediaTime: 10.25},
    {at: 1380, mediaTime: 10.6},
    {at: 1413, mediaTime: 10.633},
  ];
  delayedLargerGap.sample.draws = [
    {at: 900}, {at: 917}, {at: 1010}, {at: 1027}, {at: 1044}, {at: 1061},
    {at: 1390}, ...Array.from({length: 330}, (_, index) => ({at: 1407 + index * frameIntervalMs})),
  ];
  const delayed = analyze('delayed-larger-gap', delayedLargerGap);
  assert.equal(delayed.status, 0, delayed.stderr);
  const delayedResult = JSON.parse(delayed.stdout);
  assert.equal(delayedResult.detectedInputGap.mediaTimeDeltaMs, 250);
  assert.ok(Math.abs(
    delayedResult.recoveryRegion.maximumVideoInterval.mediaTimeDeltaMs - 350,
  ) < 1e-9);
  assert.equal(delayedResult.recoveryRegion.maximumCanvasDrawIntervalMs, 329);

  const earlyStableThenFatalGap = structuredClone(delayedLargerGap);
  earlyStableThenFatalGap.sample.draws = [
    {at: 900}, {at: 917},
    ...Array.from({length: 10}, (_, index) => ({at: 1010 + index * frameIntervalMs})),
    {at: 3300},
    ...Array.from({length: 330}, (_, index) => ({at: 3300 + (index + 1) * frameIntervalMs})),
  ];
  const lateFatal = analyze('early-stable-then-fatal-gap', earlyStableThenFatalGap);
  assert.equal(lateFatal.status, 0, lateFatal.stderr);
  const lateFatalResult = JSON.parse(lateFatal.stdout);
  assert.ok(lateFatalResult.displayRecovery.stableConfirmationMs < 2000);
  assert.ok(lateFatalResult.recoveryRegion.maximumCanvasDrawIntervalMs > 2000);
  assert.equal(lateFatalResult.displayRecovery.fatalStop, true);

  const noPostDraw = structuredClone(valid);
  noPostDraw.sample.draws = Array.from({length: 8}, (_, index) => ({at: 800 + index * 17}));
  const fatal = analyze('no-post-draw', noPostDraw);
  assert.equal(fatal.status, 0, fatal.stderr);
  const fatalResult = JSON.parse(fatal.stdout);
  assert.equal(fatalResult.displayRecovery.fatalStop, true);
  assert.equal(fatalResult.displayRecovery.stableConfirmationMs, null);

  const slowCadence = structuredClone(valid);
  slowCadence.sample.draws = [
    {at: 900}, {at: 917},
    ...Array.from({length: 150}, (_, index) => ({at: 1510 + index * 40})),
  ];
  const cadenceFailure = analyze('slow-cadence', slowCadence);
  assert.equal(cadenceFailure.status, 0, cadenceFailure.stderr);
  const cadenceFailureResult = JSON.parse(cadenceFailure.stdout);
  assert.equal(cadenceFailureResult.displayRecovery.fatalStop, false);
  assert.equal(cadenceFailureResult.cadenceRecovery.found, false);
  assert.equal(cadenceFailureResult.cadenceRecovery.expectedRateRecovered, false);

  const noSpanningInterval = structuredClone(valid);
  noSpanningInterval.sample.videoFrames = [
    {at: 900, mediaTime: 9.9},
    {at: 1000, mediaTime: 10},
  ];
  const insufficient = analyze('no-spanning-interval', noSpanningInterval);
  assert.notEqual(insufficient.status, 0);
  assert.match(insufficient.stderr, /no video interval spans the known defect media time/);

  process.stdout.write('anomalous recovery analyzer tests passed\n');
} finally {
  fs.rmSync(temporaryDirectory, {recursive: true, force: true});
}
