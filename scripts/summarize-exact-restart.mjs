import { readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const groups = {
  baseline: ['b1', 'b2'],
  exactRestart: ['f1', 'f2'],
};

const configurations = [
  {
    prefix: 'galaxy',
    output: 'galaxy-exact-restart-summary.json',
    description: 'Galaxy Tab S11 Ultra exact TS restart offset B-F-F-B summary',
    conditions: {
      device: 'Galaxy Tab S11 Ultra (SM-X930)',
      browser: 'Google Chrome',
      displayHz: 60,
      transport: 'LAN direct',
      fullscreen: true,
      source: 'local NVMe MPEG-2 TS',
      material: '乃木坂工事中録画の600秒台・900秒台（CM区間かは未判定）',
      order: ['baseline', 'exactRestart', 'exactRestart', 'baseline'],
      warmupsPerBlockExcluded: 2,
      excludedRuns: [
        {
          file: 'galaxy-exact-restart-b2-excluded-user-touch.json',
          reason: '端末操作が入ったため、同条件で取り直して集計から除外',
        },
      ],
    },
    followups: {
      minimumRestartLead500ms: ['galaxy-exact-restart-preroll-g1.json'],
      minimumRestartLead100ms: [
        'galaxy-exact-restart-preroll100-g1.json',
        'galaxy-exact-restart-preroll100-g2.json',
      ],
    },
  },
  {
    prefix: 'linux',
    output: 'linux-exact-restart-summary.json',
    description: 'Linux Chrome exact TS restart offset B-F-F-B summary',
    conditions: {
      device: 'Linux desktop',
      browser: 'Google Chrome 152',
      displayHz: 60,
      transport: 'LAN direct',
      fullscreen: true,
      source: 'local NVMe MPEG-2 TS',
      material: '乃木坂工事中録画の600秒台・900秒台（CM区間かは未判定）',
      order: ['baseline', 'exactRestart', 'exactRestart', 'baseline'],
      warmupsPerBlockExcluded: 2,
    },
    followups: {
      minimumRestartLead100ms: [
        'linux-exact-restart-preroll100-l1.json',
        'linux-exact-restart-preroll100-l2.json',
      ],
    },
  },
];

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
  max: Math.max(...values),
});

const markMs = (run, name) => run.marks.find(mark => mark.name === name)?.ms;
const summarize = runs => {
  const canvas = runs.map(run => run.firstPostSeekCanvasMs);
  const marks = Object.fromEntries([
    'request',
    'response',
    'first-byte',
    'first-picture-jobs',
    'first-picture-output',
    'first-access-unit',
    'first-picture-batch',
    'first-fragment',
    'append',
    'appended',
    'presented',
  ].map(name => {
    const values = runs.map(run => markMs(run, name)).filter(value => value !== undefined);
    return values.length === 0 ? null : [name, stats(values)];
  }).filter(Boolean));
  const firstFragmentLead = runs.map(run => {
    const first = run.marks.find(mark => mark.name === 'first-fragment');
    return first.mediaTime - run.target;
  });
  const presentedLead = runs.map(run => {
    const presented = run.marks.find(mark => mark.name === 'presented');
    return presented.mediaTime - run.target;
  });
  const appendToPresented = runs.map(run =>
    markMs(run, 'presented') - markMs(run, 'appended')
  );
  const appendToCanvas = runs.map(run =>
    run.firstPostSeekCanvasMs - markMs(run, 'appended')
  );
  return {
    measuredSeeks: runs.length,
    probeRequests: runs.reduce((sum, run) => sum + run.probeRequests, 0),
    canvasMs: {
      ...stats(canvas),
      atOrBelow250: canvas.filter(value => value <= 250).length,
      over250: canvas.filter(value => value > 250).length,
    },
    firstFragmentMinusTargetSeconds: stats(firstFragmentLead),
    presentedMinusTargetSeconds: stats(presentedLead),
    appendedToPresentedMs: stats(appendToPresented),
    appendedToCanvasMs: stats(appendToCanvas),
    marksMs: marks,
  };
};

for (const configuration of configurations) {
  const output = {
    schema: 1,
    description: configuration.description,
    conditions: configuration.conditions,
    variants: {},
  };

  for (const [name, suffixes] of Object.entries(groups)) {
    const blocks = await Promise.all(suffixes.map(async suffix =>
      JSON.parse(await readFile(
        resolve(root, `results/${configuration.prefix}-exact-restart-${suffix}.json`),
        'utf8',
      ))
    ));
    const runs = blocks.flatMap(block => block.sample.runs.filter(run => !run.warmup));
    output.variants[name] = {
      assets: blocks.map(block => block.asset),
      sourceHashes: blocks.map(block => block.sourceHash).filter(Boolean),
      cleanupVerified: blocks.every(block => Object.entries(block.cleanup ?? {})
        .filter(([key]) => key !== 'unrelatedTabCount')
        .every(([, value]) => value === true)),
      ...summarize(runs),
    };
  }

  output.followups = {};
  for (const [name, files] of Object.entries(configuration.followups)) {
    const blocks = await Promise.all(files.map(async file =>
      JSON.parse(await readFile(resolve(root, `results/${file}`), 'utf8'))
    ));
    const runs = blocks.flatMap(block => block.sample.runs.filter(run => !run.warmup));
    output.followups[name] = {
      files,
      cleanupVerified: blocks.every(block => Object.entries(block.cleanup ?? {})
        .filter(([key]) => key !== 'unrelatedTabCount')
        .every(([, value]) => value === true)),
      ...summarize(runs),
    };
  }

  const baseline = output.variants.baseline.canvasMs;
  const candidate = output.variants.exactRestart.canvasMs;
  output.comparison = {
    medianReductionMs: baseline.median - candidate.median,
    medianReductionPercent: (baseline.median - candidate.median) / baseline.median * 100,
    p95ReductionMs: baseline.p95 - candidate.p95,
    p95ReductionPercent: (baseline.p95 - candidate.p95) / baseline.p95 * 100,
  };

  await writeFile(
    resolve(root, `results/${configuration.output}`),
    `${JSON.stringify(output, null, 2)}\n`,
  );
}
