#!/usr/bin/env python3
"""Summarize a YADIF queue stall that begins before synthetic load."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def first(events: list[dict], kind: str) -> dict | None:
    return next((event for event in events if event["kind"] == kind), None)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} INPUT_JSON OUTPUT_JSON")

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    document = json.loads(input_path.read_text())
    sample = document["sample"]
    started_at = sample["performanceTimeRange"]["startedAt"]
    injection_at = started_at + sample["presentationThrottle"]["delayMs"]
    events = sample["queueTimelineDiagnostic"]["events"]
    draws = sample["draws"]
    if not draws:
        raise ValueError("the trace contains no direct canvas draw")

    first_draw_at = draws[0]["at"]
    overflow = first(events, "overflow")
    future = first(events, "future")
    reset = first(events, "clock-reset")
    if overflow is None or future is None or reset is None:
        raise ValueError("the trace does not contain overflow, future, and reset events")
    if not (overflow["at"] < injection_at and future["at"] < injection_at):
        raise ValueError("queue pressure did not begin before synthetic load")
    if reset["at"] >= first_draw_at:
        raise ValueError("the first queue reset did not precede the first draw")

    video_frames_before_draw = [
        frame
        for frame in sample["videoFrames"]
        if started_at <= frame["at"] < first_draw_at
    ]
    rafs_before_draw = [
        at for at in sample["rafs"] if started_at <= at < first_draw_at
    ]
    media_advance = (
        video_frames_before_draw[-1]["mediaTime"]
        - video_frames_before_draw[0]["mediaTime"]
        if len(video_frames_before_draw) > 1
        else None
    )

    output = {
        "schema": 1,
        "source": {
            "file": input_path.name,
            "variant": document["variant"],
            "sourceSha256": document["sourceHash"],
            "asset": document["asset"],
            "device": document["device"],
            "browser": document["browser"],
            "displayModeConfigured": document["displayModeConfigured"],
            "transport": document["transport"],
            "fullscreen": document["fullscreen"],
            "cleanup": document["cleanup"],
        },
        "timing": {
            "measurementStartedAt": started_at,
            "syntheticLoadStartsAt": injection_at,
            "firstOverflowAt": overflow["at"],
            "firstFutureWaitAt": future["at"],
            "clockResetAt": reset["at"],
            "firstDirectCanvasDrawAt": first_draw_at,
            "firstOverflowSinceMeasurementMs": overflow["at"] - started_at,
            "clockResetSinceMeasurementMs": reset["at"] - started_at,
            "firstDrawSinceMeasurementMs": first_draw_at - started_at,
            "futureQueueWaitBeforeSyntheticLoadMs": injection_at - future["at"],
        },
        "queueAtFirstOverflow": {
            "depthBeforeRetirement": overflow["queueDepth"],
            "retired": overflow["retired"],
            "requiredOutputs": overflow["requiredOutputs"],
            "firstLeadMs": overflow["firstLeadMs"],
            "lastLeadMs": overflow["lastLeadMs"],
        },
        "queueAfterFirstRetirement": {
            "depth": future["queueDepth"],
            "firstLeadMs": future["firstLeadMs"],
            "lastLeadMs": future["lastLeadMs"],
        },
        "decoderAndDisplayDuringNoDrawInterval": {
            "videoFrameCallbacks": len(video_frames_before_draw),
            "animationFrames": len(rafs_before_draw),
            "mediaTimeAdvanceSeconds": media_advance,
            "directCanvasDraws": 0,
        },
        "interpretation": [
            "The queue was already full and waiting on future deadlines before the synthetic presentation shortage began.",
            "Video frame callbacks and animation frames continued while no direct canvas draw occurred.",
            "The first direct canvas draw followed the queue clock reset, which localizes this stall to YADIF presentation scheduling rather than decoder starvation.",
            "The source build included a later synthetic-load hook, so an exact submission-build natural-failure trace is still required before treating this as the final branch-level proof.",
        ],
    }
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
