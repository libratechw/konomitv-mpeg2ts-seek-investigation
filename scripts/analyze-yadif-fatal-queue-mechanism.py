#!/usr/bin/env python3
"""Summarize the saved YADIF fatal-stop traces without changing their meaning."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUTPUT = RESULTS / "yadif-fatal-queue-mechanism-audit.json"

REFRESH_MS = 1000 / 60
OUTPUT_DURATION_MS = 1001 / 60
PRESENT_DEADLINE_LEAD_MS = REFRESH_MS * 1.5
HORIZON_MS = 6 * max(REFRESH_MS, OUTPUT_DURATION_MS)


def load(name: str) -> dict:
    with (RESULTS / name).open(encoding="utf-8") as source:
        return json.load(source)


def sha256(name: str) -> str:
    return hashlib.sha256((RESULTS / name).read_bytes()).hexdigest()


def longest_depth_run(events: list[dict], depth: int) -> tuple[int, int]:
    best = (0, -1)
    start = None
    for index, event in enumerate(events + [{"queueDepth": None}]):
        if event.get("queueDepth") == depth:
            if start is None:
                start = index
        elif start is not None:
            if index - start > best[1] - best[0] + 1:
                best = (start, index - 1)
            start = None
    return best


def main() -> None:
    natural_name = "galaxy-yadif-rank4-natural-fatal-timeline.json"
    formal_name = "galaxy-yadif-rank4-one-hour-block-reset-block-003.json"
    diagnostic_name = "galaxy-yadif-pre-injection-future-queue-stall-trace.json"
    windows_name = "windows-anomaly-integration-44e06a4-until-fatal.json"

    natural = load(natural_name)
    failure = natural["sample"]["failures"][0]
    events = failure["queueTimelineEvents"]
    run_start, run_end = longest_depth_run(events, 5)
    depth_run = events[run_start : run_end + 1]
    depth_run_overflows = [event for event in depth_run if event["kind"] == "overflow"]
    depth_run_future = [event for event in depth_run if event["kind"] == "future"]
    clock_index = next(
        index for index, event in enumerate(events) if event["kind"] == "clock-reset"
    )
    clock = events[clock_index]

    formal = load(formal_name)["sample"]["failures"][0]
    diagnostic = load(diagnostic_name)["sample"]["queueTimelineDiagnostic"]["events"]
    diagnostic_clock_index = next(
        index for index, event in enumerate(diagnostic) if event["kind"] == "clock-reset"
    )
    diagnostic_clock = diagnostic[diagnostic_clock_index]
    diagnostic_draw_index = next(
        index
        for index in range(diagnostic_clock_index + 1, len(diagnostic))
        if diagnostic[index]["kind"] == "draw-gap"
    )
    windows = load(windows_name)["fatalStop"]

    result = {
        "schemaVersion": 1,
        "constants": {
            "displayHz": 60,
            "refreshMs": REFRESH_MS,
            "outputFps": "60000/1001",
            "outputDurationMs": OUTPUT_DURATION_MS,
            "presentDeadlineLeadMs": PRESENT_DEADLINE_LEAD_MS,
            "queueCapacity": 5,
            "horizonFormula": "6 * max(refreshMs, outputDurationMs)",
            "horizonMs": HORIZON_MS,
        },
        "rank4NaturalFatal": {
            "source": natural_name,
            "sha256": sha256(natural_name),
            "outcome": failure["outcome"],
            "elapsedMs": failure["elapsedMs"],
            "maximumDrawGapMs": failure["maximumDrawGapMs"],
            "stableAtMs": failure["stableAtMs"],
            "eventCount": len(events),
            "eventKindCounts": dict(Counter(event["kind"] for event in events)),
            "longestConsecutiveFullQueue": {
                "startEventIndex": run_start,
                "endEventIndex": run_end,
                "eventCount": len(depth_run),
                "startAtMs": depth_run[0]["at"],
                "endAtMs": depth_run[-1]["at"],
                "firstLeadMinMs": min(event["firstLeadMs"] for event in depth_run),
                "firstLeadMaxMs": max(event["firstLeadMs"] for event in depth_run),
                "firstLeadAbovePresentDeadlineCount": sum(
                    event["firstLeadMs"] > PRESENT_DEADLINE_LEAD_MS
                    for event in depth_run
                ),
                "capacityPreparationEventCount": len(depth_run_overflows),
                "capacityPreparationLastLeadMaximumMs": max(
                    event["lastLeadMs"] for event in depth_run_overflows
                ),
                "futureEventCount": len(depth_run_future),
                "futureLastLeadAboveHorizonCount": sum(
                    event["lastLeadMs"] > HORIZON_MS for event in depth_run_future
                ),
            },
            "clockReset": {
                "eventIndex": clock_index,
                "event": clock,
                "previousEvent": events[clock_index - 1],
                "nextEvent": events[clock_index + 1],
                "result": (
                    "the reset emptied the full queue and allowed a subsequent draw, "
                    "but the same trial later entered the full-queue retirement cycle "
                    "again and ended as a fatal display stop"
                ),
            },
            "classification": (
                "confirmed YADIF capacity-retirement loop: the head approaches the "
                "presentation deadline, capacity retirement removes old fields without "
                "closing their presentation moments, and the surviving head returns to "
                "roughly three to four refreshes in the future"
            ),
        },
        "rank4FormalOneHourFatal": {
            "source": formal_name,
            "sha256": sha256(formal_name),
            "maximumDrawGapMs": formal["maximumDrawGapMs"],
            "stableAtMs": formal["stableAtMs"],
            "queueResettedBefore": formal["statsBefore"]["queueResetted"],
            "queueResettedAfter": formal["statsAfter"]["queueResetted"],
            "maxQueuedFieldsBefore": formal["statsBefore"]["maxQueuedFields"],
            "maxQueuedFieldsAfter": formal["statsAfter"]["maxQueuedFields"],
            "missingEvidence": [
                "queue head deadline and lead over time",
                "queue depth over time",
                "each queue push, retirement, compression, and reset event",
            ],
            "classification": (
                "the layer and counters are consistent with the natural Galaxy fatal, "
                "but this block has no queue timeline and cannot prove the same mechanism"
            ),
        },
        "thresholdResetRecoveryExample": {
            "source": diagnostic_name,
            "sha256": sha256(diagnostic_name),
            "clockResetEventIndex": diagnostic_clock_index,
            "clockResetEvent": diagnostic_clock,
            "firstLaterDrawEventIndex": diagnostic_draw_index,
            "firstLaterDrawEvent": diagnostic[diagnostic_draw_index],
            "drawAfterResetMs": (
                diagnostic[diagnostic_draw_index]["at"] - diagnostic_clock["at"]
            ),
            "scope": (
                "this diagnostic trace shows that the threshold reset can restore a "
                "draw after an overflow-driven future queue, but does not show a state "
                "that only the threshold reset, rather than deadline compression, can recover"
            ),
        },
        "windowsFatal": {
            "source": windows_name,
            "sha256": sha256(windows_name),
            "videoCallbackGapsOverTwoSeconds": windows[
                "videoCallbackGapsOverTwoSeconds"
            ],
            "finalYadifStats": windows["finalYadifStats"],
            "missingEvidence": [
                "queue head deadline and lead over time",
                "queue depth over time",
                "queue events sharing timestamps with video callbacks",
            ],
            "classification": (
                "not established as the YADIF capacity-retirement loop; the saved trace "
                "instead records two multi-second video-callback gaps, max queue depth 4, "
                "zero queue resets, and about 60 fps in the final YADIF snapshot"
            ),
        },
        "conclusions": {
            "overflowDeadlineCompression": (
                "directly supported as the fix for the recorded natural Galaxy full-queue loop"
            ),
            "clockDivergenceReset": (
                "observed to fire and to restore a draw once, but no saved trace proves "
                "a stable recovery that uniquely requires this reset after overflow "
                "deadline compression is present"
            ),
            "windowsFatal": "requires a separate cause investigation",
        },
    }
    with OUTPUT.open("w", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2)
        destination.write("\n")


if __name__ == "__main__":
    main()
