import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const load = name => readFile(resolve(root, `results/${name}`), 'utf8').then(JSON.parse);

const median = values => {
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[middle - 1] + sorted[middle]) / 2
    : sorted[middle];
};
const percentile = (values, probability) => {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.max(0, Math.ceil(probability * sorted.length) - 1)];
};
const stats = values => ({
  count: values.length,
  mean: values.reduce((sum, value) => sum + value, 0) / values.length,
  median: median(values),
  p95: percentile(values, 0.95),
  p99: percentile(values, 0.99),
  max: Math.max(...values),
  atOrBelow250: values.filter(value => value <= 250).length,
  over250: values.filter(value => value > 250).length,
});

const groups = {
  linux: {
    previous: ['linux-exact-restart-f1.json', 'linux-exact-restart-f2.json'],
    fixed: [
      'linux-exact-restart-seek-frame-durable-l1.json',
      'linux-exact-restart-seek-frame-durable-l2.json',
    ],
  },
  galaxy: {
    previous: ['galaxy-exact-restart-f1.json', 'galaxy-exact-restart-f2.json'],
    fixed: [
      'galaxy-exact-restart-seek-frame-durable-g1.json',
      'galaxy-exact-restart-seek-frame-durable-g2.json',
    ],
  },
};

const summarizeBlocks = async (names, field) => {
  const blocks = await Promise.all(names.map(load));
  const runs = blocks.flatMap(block => block.sample.runs.filter(run => !run.warmup));
  return {
    files: names,
    assets: blocks.map(block => block.asset),
    sourceHashes: blocks.map(block => block.sourceHash).filter(Boolean),
    displayHz: blocks.map(block => block.displayHz),
    cleanupVerified: blocks.every(block => Object.entries(block.cleanup ?? {})
      .filter(([key]) => key !== 'unrelatedTabCount')
      .every(([, value]) => value === true)),
    probeRequests: runs.reduce((sum, run) => sum + run.probeRequests, 0),
    acceptedWhileSeeking: runs.filter(run => run.acceptedWhileSeeking).length,
    canvasMs: stats(runs.map(run => run[field])),
  };
};

const earlyCases = document => document.sample.runs
  .filter(run => !run.warmup)
  .map(run => {
    const early = run.events.find(event =>
      event.type === 'rvfc' && event.seeking === true &&
      Math.abs(event.mediaTime - run.target) <= 0.05
    );
    if (!early) return null;
    const seeked = run.events.find(event => event.type === 'seeked');
    const presented = run.marks.find(mark => mark.name === 'presented');
    const presentedMs = presented?.ms ?? presented?.sinceContext ?? null;
    return {
      target: run.target,
      earlyCanvasMs: early.ms,
      seekedMs: seeked?.ms ?? null,
      seekedVisibility: seeked?.visibility ?? null,
      playerPresentedMs: presentedMs,
      markerLagAfterEarlyCanvasMs: presentedMs === null ? null : presentedMs - early.ms,
    };
  })
  .filter(Boolean);

const output = {
  schema: 1,
  description: 'Keep a destination canvas frame that Chromium delivers immediately before seeked',
  revisions: {
    konomiTV: 'e92fba8bb219589c8e4ada9609ed4a9d91b33c00',
    tsukumijimaBase: '52a3db5e8fb9833e6cade2167097849c668bdb1f',
    otyaUpstream: 'd5df08b5f6215c2ed4994034d4a5855ad9bc3d69',
    sourceCommit: '2d072f31b10a38a2acee251c65bf37a3da860d8f',
    distCommit: 'f3ba99d6147c31c554d44a06d11384af8e107181',
    integratedValidationCommit: '627c091',
  },
  conditions: {
    transport: 'LAN direct',
    fullscreen: true,
    source: 'local NVMe MPEG-2 TS',
    material: '乃木坂工事中録画の600秒台・900秒台（CM区間かは未判定）',
    warmupsPerBlockExcluded: 2,
    previousMetric: 'first target canvas draw after video.seeking became false',
    fixedMetric: 'first target canvas draw that remains visible across seeked',
    comparisonNote: 'Without the fix, a target frame drawn while seeking is hidden by seeked, so the previous post-seeking draw is also its first durable draw.',
  },
  platforms: {},
};

for (const [platform, files] of Object.entries(groups)) {
  const previous = await summarizeBlocks(files.previous, 'firstPostSeekCanvasMs');
  const fixed = await summarizeBlocks(files.fixed, 'firstDurableCanvasMs');
  output.platforms[platform] = {
    previous,
    fixed,
    comparison: {
      meanReductionMs: previous.canvasMs.mean - fixed.canvasMs.mean,
      medianReductionMs: previous.canvasMs.median - fixed.canvasMs.median,
      p95ReductionMs: previous.canvasMs.p95 - fixed.canvasMs.p95,
      maxReductionMs: previous.canvasMs.max - fixed.canvasMs.max,
    },
  };
}

const beforeTimeline = await load('linux-exact-restart-presentation-timeline.json');
const afterTimeline = await load('linux-exact-restart-seek-frame-timeline.json');
const beforeEarly = earlyCases(beforeTimeline);
const afterEarly = earlyCases(afterTimeline);
output.causalTimeline = {
  before: {
    file: 'linux-exact-restart-presentation-timeline.json',
    earlyCases: beforeEarly.length,
    hiddenBySeeked: beforeEarly.filter(run => run.seekedVisibility === 'hidden').length,
    runs: beforeEarly,
  },
  fixed: {
    file: 'linux-exact-restart-seek-frame-timeline.json',
    earlyCases: afterEarly.length,
    retainedAcrossSeeked: afterEarly.filter(run => run.seekedVisibility === 'visible').length,
    markerLagAfterEarlyCanvasMs: stats(afterEarly.map(run => run.markerLagAfterEarlyCanvasMs)),
    runs: afterEarly,
  },
};

await writeFile(
  resolve(root, 'results/exact-restart-seek-frame-summary.json'),
  `${JSON.stringify(output, null, 2)}\n`,
);
