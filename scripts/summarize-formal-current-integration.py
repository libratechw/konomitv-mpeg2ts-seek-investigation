#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text())


def sha256(path: Path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def distribution(values):
    return {
        "count": len(values),
        "minimum": min(values, default=None),
        "median": statistics.median(values) if values else None,
        "p95": percentile(values, 0.95),
        "maximum": max(values, default=None),
    }


def assert_cleanup(block):
    cleanup = block["cleanup"]
    if not cleanup or not all(cleanup.values()):
        raise ValueError("block cleanup is incomplete")


def anomaly_statistics(block):
    sample = block["sample"]
    trials = sample["trials"]
    completed_trials = trials[: sample["completed"]]
    return {
        "attemptedCrossings": len(trials),
        "completedCrossings": sample["completed"],
        "fatalStops": len(sample["failures"]),
        "cadenceFailures": len(sample["cadenceFailures"]),
        "stableConfirmationMs": distribution(
            [trial["recovery"]["confirmedMs"] for trial in completed_trials]
        ),
        "postRecoveryCanvasFps": distribution(
            [trial["cadence"]["drawFps"] for trial in completed_trials]
        ),
        "maximumCanvasDrawIntervalMs": distribution(
            [trial["cadence"]["maximumIntervalMs"] for trial in completed_trials]
        ),
        "audioDecodeAdvanced": sum(
            trial["deltas"]["audioDecodedBytes"] > 0 for trial in trials
        ),
        "audioDecodeObservedTrials": len(trials),
        "mediaTimeGapMs": distribution(
            [trial["defect"]["mediaTimeGapMs"] for trial in trials]
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("normal_baseline_summary", type=Path)
    parser.add_argument("normal_baseline_block", type=Path)
    parser.add_argument("normal_integration_summary", type=Path)
    parser.add_argument("normal_integration_block", type=Path)
    parser.add_argument("anomaly_baseline_summary", type=Path)
    parser.add_argument("anomaly_baseline_block", type=Path)
    parser.add_argument("anomaly_integration_summary", type=Path)
    parser.add_argument("anomaly_integration_block", type=Path)
    args = parser.parse_args()

    paths = {name: value for name, value in vars(args).items()}
    documents = {name: load(path) for name, path in paths.items()}
    normal_baseline_summary = documents["normal_baseline_summary"]
    normal_baseline_block = documents["normal_baseline_block"]
    normal_integration_summary = documents["normal_integration_summary"]
    normal_integration_block = documents["normal_integration_block"]
    anomaly_baseline_summary = documents["anomaly_baseline_summary"]
    anomaly_baseline_block = documents["anomaly_baseline_block"]
    anomaly_integration_summary = documents["anomaly_integration_summary"]
    anomaly_integration_block = documents["anomaly_integration_block"]

    for block in (
        normal_baseline_block,
        normal_integration_block,
        anomaly_baseline_block,
        anomaly_integration_block,
    ):
        assert_cleanup(block)

    for field in (
        "fixtureName",
        "fixtureSha256",
        "videoId",
        "frameMode",
        "clientRevision",
    ):
        values = {
            normal_baseline_summary[field],
            normal_integration_summary[field],
        }
        if len(values) != 1:
            raise ValueError(f"normal comparison differs in {field}: {values}")
    for field in (
        "clientRevision",
        "runnerSha256",
        "collectorSha256",
        "fixtureName",
        "fixtureSha256",
        "videoId",
        "frameMode",
        "baseSeed",
    ):
        values = {
            anomaly_baseline_summary[field],
            anomaly_integration_summary[field],
        }
        if len(values) != 1:
            raise ValueError(f"anomaly comparison differs in {field}: {values}")
    for summary, block in (
        (anomaly_baseline_summary, anomaly_baseline_block),
        (anomaly_integration_summary, anomaly_integration_block),
    ):
        for field in (
            "variant",
            "sourceHash",
            "distHash",
            "asset",
            "fixtureName",
            "fixtureSha256",
            "videoId",
            "frameMode",
        ):
            if summary[field] != block[field]:
                raise ValueError(f"anomaly summary and block differ in {field}")

    baseline_sample = normal_baseline_block["sample"]
    integration_sample = normal_integration_block["sample"]
    failures = baseline_sample["failures"]
    if len(failures) != 1:
        raise ValueError("normal baseline must contain one fatal stop")
    failure = failures[0]
    index = failure["index"]
    if baseline_sample["seed"] != integration_sample["seed"]:
        raise ValueError("normal seeds differ")
    if (
        baseline_sample["targetTimesSeconds"]
        != integration_sample["targetTimesSeconds"][
            : len(baseline_sample["targetTimesSeconds"])
        ]
    ):
        raise ValueError("normal target sequence differs")
    if (
        baseline_sample["interSeekJitterMs"]
        != integration_sample["interSeekJitterMs"][
            : len(baseline_sample["interSeekJitterMs"])
        ]
    ):
        raise ValueError("normal phase-jitter sequence differs")

    anomaly_baseline_sample = anomaly_baseline_block["sample"]
    anomaly_integration_sample = anomaly_integration_block["sample"]
    for field in ("seed", "seekTime", "defectMediaTime"):
        if anomaly_baseline_sample[field] != anomaly_integration_sample[field]:
            raise ValueError(f"anomaly comparison differs in {field}")
    baseline_jitter = [trial["jitterMs"] for trial in anomaly_baseline_sample["trials"]]
    integration_jitter = [
        trial["jitterMs"] for trial in anomaly_integration_sample["trials"]
    ]
    if baseline_jitter != integration_jitter[: len(baseline_jitter)]:
        raise ValueError("anomaly phase-jitter sequence differs")

    output = {
        "schemaVersion": 1,
        "createdAt": datetime.now().astimezone().isoformat(),
        "sourceFiles": {
            name: {"file": path.name, "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "normalSeekFatalStop": {
            "sharedConditions": {
                "clientRevision": normal_baseline_summary["clientRevision"],
                "fixtureName": normal_baseline_summary["fixtureName"],
                "fixtureSha256": normal_baseline_summary["fixtureSha256"],
                "videoId": normal_baseline_summary["videoId"],
                "frameMode": normal_baseline_summary["frameMode"],
                "baseSeed": normal_baseline_summary["baseSeed"],
                "runnerSha256": normal_baseline_summary["runnerSha256"],
                "collectorSha256": normal_baseline_summary["collectorSha256"],
            },
            "baseline": {
                "variant": normal_baseline_summary["variant"],
                "sourceMarkerSha256": normal_baseline_summary["sourceHash"],
                "workerBundleSha256": normal_baseline_summary["distHash"],
                "asset": normal_baseline_summary["asset"],
                "assetSha256": normal_baseline_summary["assetSha256"],
                "attemptedSeeks": normal_baseline_summary["attemptedSeeks"],
                "completedSeeks": normal_baseline_summary["completedSeeks"],
                "fatalStops": normal_baseline_summary["fatalStops"],
                "wallClockElapsedSeconds": normal_baseline_summary[
                    "wallClockElapsedSeconds"
                ],
            },
            "integration": {
                "variant": normal_integration_summary["variant"],
                "sourceMarkerSha256": normal_integration_summary["sourceHash"],
                "workerBundleSha256": normal_integration_summary["distHash"],
                "asset": normal_integration_summary["asset"],
                "assetSha256": normal_integration_summary["assetSha256"],
                "attemptedSeeks": normal_integration_summary["attemptedSeeks"],
                "completedSeeks": normal_integration_summary["completedSeeks"],
                "fatalStops": normal_integration_summary["fatalStops"],
                "wallClockElapsedSeconds": normal_integration_summary[
                    "wallClockElapsedSeconds"
                ],
            },
            "matchedFailureTrial": {
                "index": index,
                "targetSeconds": failure["target"],
                "phaseJitterMs": baseline_sample["interSeekJitterMs"][index],
                "baselineOutcome": failure["outcome"],
                "baselineElapsedMs": failure["elapsedMs"],
                "baselineMaximumDrawGapMs": failure["maximumDrawGapMs"],
                "integrationStableConfirmationMs": integration_sample[
                    "stableLatenciesMs"
                ][index],
                "integrationMaximumDrawGapMs": integration_sample["maximumDrawGapsMs"][
                    index
                ],
            },
        },
        "anomalousTransportDefect": {
            "sharedConditions": {
                "clientRevision": anomaly_baseline_summary["clientRevision"],
                "runnerSha256": anomaly_baseline_summary["runnerSha256"],
                "collectorSha256": anomaly_baseline_summary["collectorSha256"],
                "fixtureName": anomaly_baseline_block["fixtureName"],
                "fixtureSha256": anomaly_baseline_block["fixtureSha256"],
                "videoId": anomaly_baseline_block["videoId"],
                "frameMode": anomaly_baseline_block["frameMode"],
                "seed": anomaly_baseline_sample["seed"],
                "seekTime": anomaly_baseline_sample["seekTime"],
                "defectMediaTime": anomaly_baseline_sample["defectMediaTime"],
            },
            "baseline": {
                "variant": anomaly_baseline_block["variant"],
                "sourceMarkerSha256": anomaly_baseline_block["sourceHash"],
                "workerBundleSha256": anomaly_baseline_block["distHash"],
                "asset": anomaly_baseline_block["asset"],
                **anomaly_statistics(anomaly_baseline_block),
            },
            "integration": {
                "variant": anomaly_integration_block["variant"],
                "sourceMarkerSha256": anomaly_integration_block["sourceHash"],
                "workerBundleSha256": anomaly_integration_block["distHash"],
                "asset": anomaly_integration_block["asset"],
                **anomaly_statistics(anomaly_integration_block),
            },
            "scope": (
                "Direct canvas draws and decoded-byte progress are observed. "
                "Compositor scanout, audible A/V synchronization, pixel correctness, "
                "and the minimum unavoidable frame loss are not proven."
            ),
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
