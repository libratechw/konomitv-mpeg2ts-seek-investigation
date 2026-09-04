#!/usr/bin/env python3
"""Reduce a Windows anomalous-TS diagnostic campaign to public evidence."""

import argparse
import hashlib
import json
import statistics
from collections import Counter
from pathlib import Path


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def event_rate(events, key="at"):
    values = sorted(float(event[key]) for event in events)
    if len(values) < 2 or values[-1] <= values[0]:
        return None
    return (len(values) - 1) * 1000 / (values[-1] - values[0])


def unique_animation_rate(events):
    values = sorted({float(event["now"]) for event in events})
    if len(values) < 2 or values[-1] <= values[0]:
        return None
    return (len(values) - 1) * 1000 / (values[-1] - values[0])


def stats(values):
    if not values:
        return None
    return {
        "count": len(values),
        "minimum": min(values),
        "median": statistics.median(values),
        "maximum": max(values),
    }


def gap_stats(events, key="at"):
    values = sorted(float(event[key]) for event in events)
    return stats([after - before for before, after in zip(values, values[1:])])


def fatal_context_metrics(failure):
    context = failure.get("diagnostics") or {}
    video_frames = context.get("frames") or []
    canvas_draws = context.get("draws") or []
    animation_frames = context.get("animationFrames") or []
    animation_gaps = gap_stats(animation_frames)
    video_gaps = gap_stats(video_frames)
    canvas_gaps = gap_stats(canvas_draws)

    if animation_gaps and animation_gaps["maximum"] > 2000:
        boundary = "at-or-before-animation-frame-callback"
    elif video_gaps and video_gaps["maximum"] > 2000:
        boundary = "after-animation-frame-and-before-video-frame-callback"
    elif canvas_gaps and canvas_gaps["maximum"] > 2000:
        boundary = "after-video-frame-callback-and-before-canvas-draw"
    else:
        boundary = "not-localized-by-two-second-gaps"

    return {
        "trialIndex": failure.get("index"),
        "phase": failure.get("phase"),
        "elapsedMs": failure.get("elapsedMs"),
        "observedBoundary": boundary,
        "animationFrame": {
            "count": len(animation_frames),
            "rate": event_rate(animation_frames),
            "gapsMs": animation_gaps,
        },
        "videoFrame": {
            "count": len(video_frames),
            "rate": event_rate(video_frames),
            "gapsMs": video_gaps,
        },
        "canvasDraw": {
            "count": len(canvas_draws),
            "rate": event_rate(canvas_draws),
            "gapsMs": canvas_gaps,
        },
        "videoState": context.get("video"),
        "videoEventCounts": dict(
            sorted(Counter(event.get("type") for event in context.get("videoEvents") or []).items())
        ),
        "timingEventCount": len(context.get("timings") or []),
        "playerErrors": context.get("playerErrors") or [],
    }


def context_metrics(failure):
    context = failure.get("context") or {}
    video_frames = context.get("videoFrames") or []
    canvas_draws = context.get("canvasDraws") or []
    animation_frames = context.get("animationFrames") or []
    media_intervals = [
        (after["mediaTime"] - before["mediaTime"]) * 1000
        for before, after in zip(video_frames, video_frames[1:])
    ]
    presented_steps = Counter(
        int(after["presentedFrames"] - before["presentedFrames"])
        for before, after in zip(video_frames, video_frames[1:])
    )
    one_frame = sum(abs(value - 1001 / 30) <= 0.01 for value in media_intervals)
    two_frames = sum(abs(value - 1001 / 15) <= 0.01 for value in media_intervals)
    return {
        "videoCallbackFps": event_rate(video_frames),
        "canvasDrawFps": event_rate(canvas_draws),
        "uniqueAnimationFrameFps": unique_animation_rate(animation_frames),
        "videoCallbackCount": len(video_frames),
        "canvasDrawCount": len(canvas_draws),
        "uniqueAnimationFrameCount": len({event["now"] for event in animation_frames}),
        "mediaTimeIntervals": {
            "count": len(media_intervals),
            "oneSourceFrame": one_frame,
            "twoSourceFrames": two_frames,
            "other": len(media_intervals) - one_frame - two_frames,
        },
        "presentedFrameStepCounts": {
            str(key): value for key, value in sorted(presented_steps.items())
        },
        "videoState": context.get("video"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("blocks", nargs="+", type=Path)
    args = parser.parse_args()

    summary = json.loads(args.summary.read_text())
    expected = {block["file"]: block for block in summary["blocks"]}
    supplied_by_hash = {sha256(path): path for path in args.blocks}
    expected_hashes = {block["sha256"] for block in expected.values()}
    if (
        len(args.blocks) != len(expected)
        or len(supplied_by_hash) != len(args.blocks)
        or set(supplied_by_hash) != expected_hashes
    ):
        raise ValueError("the supplied block set does not match the campaign summary")

    block_results = []
    low_contexts = []
    other_contexts = []
    fatal_contexts = []
    for name, metadata in expected.items():
        path = supplied_by_hash[metadata["sha256"]]
        block = json.loads(path.read_text())
        failures = block["sample"].get("cadenceFailures") or []
        contexts = [context_metrics(failure) for failure in failures]
        block_fatal_contexts = [
            fatal_context_metrics(failure)
            for failure in block["sample"].get("failures") or []
        ]
        fatal_contexts.extend(block_fatal_contexts)
        video_rates = [
            context["videoCallbackFps"]
            for context in contexts
            if context["videoCallbackFps"] is not None
        ]
        canvas_rates = [
            context["canvasDrawFps"]
            for context in contexts
            if context["canvasDrawFps"] is not None
        ]
        low_presentation = (
            metadata["cadenceFailures"] == metadata["attempted"]
            and video_rates
            and canvas_rates
            and 18 <= statistics.median(video_rates) <= 22
            and 38 <= statistics.median(canvas_rates) <= 42
        )
        (low_contexts if low_presentation else other_contexts).extend(contexts)
        block_results.append(
            {
                **metadata,
                "cadenceFailureContext": {
                    "videoCallbackFps": stats(video_rates),
                    "canvasDrawFps": stats(canvas_rates),
                    "uniqueAnimationFrameFps": stats(
                        [
                            context["uniqueAnimationFrameFps"]
                            for context in contexts
                            if context["uniqueAnimationFrameFps"] is not None
                        ]
                    ),
                },
                "lowVideoPresentationSession": bool(low_presentation),
                "fatalDiagnostics": block_fatal_contexts,
            }
        )

    def aggregate_contexts(contexts):
        return {
            "count": len(contexts),
            "videoCallbackFps": stats(
                [value["videoCallbackFps"] for value in contexts if value["videoCallbackFps"]]
            ),
            "canvasDrawFps": stats(
                [value["canvasDrawFps"] for value in contexts if value["canvasDrawFps"]]
            ),
            "uniqueAnimationFrameFps": stats(
                [
                    value["uniqueAnimationFrameFps"]
                    for value in contexts
                    if value["uniqueAnimationFrameFps"]
                ]
            ),
            "mediaTimeIntervals": dict(
                sum(
                    (
                        Counter(context["mediaTimeIntervals"])
                        for context in contexts
                    ),
                    Counter(),
                )
            ),
            "presentedFrameStepCounts": dict(
                sum(
                    (
                        Counter(context["presentedFrameStepCounts"])
                        for context in contexts
                    ),
                    Counter(),
                )
            ),
            "videoStates": [
                context["videoState"] for context in contexts if context["videoState"] is not None
            ],
        }

    low_blocks = [
        block["file"] for block in block_results if block["lowVideoPresentationSession"]
    ]
    print(
        json.dumps(
            {
                "schemaVersion": 1,
                "source": {
                    "summarySha256": sha256(args.summary),
                    "blockHashesVerified": True,
                },
                "build": {
                    "variant": summary["variant"],
                    "sourceHash": summary["sourceHash"],
                    "distHash": summary["distHash"],
                    "distTreeSha256": summary["distTreeSha256"],
                    "asset": summary["asset"],
                    "assetSha256": summary["assetSha256"],
                    "clientRevision": summary["clientRevision"],
                    "konomiCommit": summary["konomiCommit"],
                    "fixtureSha256": summary["fixtureSha256"],
                },
                "conditions": {
                    "scope": summary["scope"],
                    "captureSeekDiagnostics": summary["captureSeekDiagnostics"],
                    "durationSeconds": summary["durationSeconds"],
                    "cleanupReserveSeconds": summary["cleanupReserveSeconds"],
                    "blockSize": summary["blockSize"],
                    "baseSeed": summary["baseSeed"],
                    "seekTime": summary["seekTime"],
                    "defectMediaTime": summary["defectMediaTime"],
                    "clientReset": summary["clientReset"],
                    "toolsSnapshot": summary["toolsSnapshot"],
                    "runnerSha256": summary["runnerSha256"],
                    "collectorSha256": summary["collectorSha256"],
                    "validatorSha256": summary["validatorSha256"],
                    "summarizerSha256": summary["summarizerSha256"],
                },
                "result": {
                    "status": summary["status"],
                    "attemptedCrossings": summary["attemptedCrossings"],
                    "completedCrossings": summary["completedCrossings"],
                    "fatalStops": summary["fatalStops"],
                    "cadenceFailures": summary["cadenceFailures"],
                    "measurementSeconds": summary["measurementSeconds"],
                    "wallClockElapsedSeconds": summary["wallClockElapsedSeconds"],
                    "coverageSatisfied": summary["coverageSatisfied"],
                    "hostLoad": summary["hostLoad"],
                    "cleanup": summary["cleanup"],
                },
                "blocks": block_results,
                "layerAnalysis": {
                    "lowVideoPresentationBlocks": low_blocks,
                    "lowVideoPresentation": aggregate_contexts(low_contexts),
                    "otherCadenceFailures": aggregate_contexts(other_contexts),
                    "animationFrameHistoryAvailable": any(
                        block["cadenceFailureContext"]["uniqueAnimationFrameFps"] is not None
                        for block in block_results
                    ),
                    "fatalDiagnostics": {
                        "count": len(fatal_contexts),
                        "observedBoundaryCounts": dict(
                            sorted(Counter(
                                context["observedBoundary"] for context in fatal_contexts
                            ).items())
                        ),
                        "contexts": fatal_contexts,
                    },
                },
                "interpretation": [
                    "A block is classified as a low-video-presentation session only when every trial fails cadence, median rVFC is 18-22 fps, and median canvas draw rate is 38-42 fps.",
                    "A one-source-frame media interval is 1001/30 ms; a two-source-frame interval is 1001/15 ms, each with 0.01 ms tolerance.",
                    "A presentedFrames step of one with alternating one- and two-source-frame media intervals means callbacks themselves were not skipped by the collector; Chrome presented a reduced subset of source media times.",
                    "Diagnostic instrumentation invalidates this run for formal latency or failure-rate claims.",
                    "Absent animation-frame history cannot distinguish a reduced compositor/rAF rate from video presentation reduction upstream of rVFC.",
                    "Fatal localization reports the first observed callback boundary with a gap over two seconds. An animation-frame gap does not distinguish browser callback suppression from an application loop that stopped requesting callbacks.",
                    "A continuing animation-frame stream with a video-frame gap places the observable failure after rAF and before rVFC, but does not by itself distinguish network, conversion, MSE, decoder, and browser video presentation.",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
