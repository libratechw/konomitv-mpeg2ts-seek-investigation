#!/usr/bin/env python3
"""Measure the converter timeline around the fixed Nogizaka TS defect.

Usage:
  python3 measure-nogizaka-defect-conversion.py \
    /path/to/nogizaka.ts /path/to/mpeg2toh264 \
    --converter-source-revision 44e06a4 \
    --browser-analysis ../results/galaxy-integration-current-v3-anomalous-recovery-analysis.json

The full fixture and the extracted audiovisual window remain local.  JSON
written to stdout contains hashes and timing metadata only.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

FIXTURE_SHA = "2240bbb8848d0c244378498dc0482b9c4f34e71a722dff01a2b6bfe50d1ca845"
WINDOW_START = 200_484_140
WINDOW_LENGTH = 3_760_000
WINDOW_SHA = "c31cfc79cb38b2ec2f1e740031fa9b898f309179f3e21f099d8a323ee5a27f94"
DEFECT_PICTURE_PTS_90K = 502_108_869


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def probe_frames(path, loglevel):
    command = [
        "ffprobe", "-v", loglevel, "-select_streams", "v:0",
        "-show_frames", "-show_entries",
        "frame=key_frame,pts_time,pkt_pos,pict_type", "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, check=True)
    frames = json.loads(result.stdout)["frames"]
    return frames, re.sub(r" @ 0x[0-9a-f]+", "", result.stderr.decode())


def decimal_ms(value):
    return float(Decimal(value) * 1000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("converter", type=Path)
    parser.add_argument("--converter-source-revision", required=True)
    parser.add_argument("--browser-analysis", type=Path, required=True)
    args = parser.parse_args()

    fixture_sha = sha256(args.fixture)
    if fixture_sha != FIXTURE_SHA:
        raise ValueError("fixture SHA-256 mismatch")
    if not args.converter.is_file():
        raise ValueError("converter is not a file")

    browser = json.loads(args.browser_analysis.read_text())
    if browser["fixture"]["sha256"] != FIXTURE_SHA:
        raise ValueError("browser analysis uses another fixture")
    browser_gap_ms = float(browser["detectedInputGap"]["mediaTimeDeltaMs"])

    with tempfile.TemporaryDirectory() as directory:
        window = Path(directory) / "fixed-window.ts"
        output = Path(directory) / "converted.mp4"
        with args.fixture.open("rb") as source, window.open("wb") as target:
            source.seek(WINDOW_START)
            data = source.read(WINDOW_LENGTH)
            if len(data) != WINDOW_LENGTH:
                raise ValueError("short fixture read")
            target.write(data)
        window_sha = sha256(window)
        if window_sha != WINDOW_SHA:
            raise ValueError("fixed window SHA-256 mismatch")

        conversion = subprocess.run(
            [str(args.converter), str(window), str(output)],
            capture_output=True, text=True, check=True,
        )
        source_frames, source_warnings = probe_frames(window, "warning")
        output_frames, output_warnings = probe_frames(output, "warning")
        output_sha = sha256(output)

    summary_match = re.search(
        r"(?m)^(\d+) media fragments, (\d+) video samples, "
        r"(\d+) audio samples, (\d+) bytes,", conversion.stdout
    )
    if not summary_match:
        raise ValueError("converter summary was not recognized")
    conversion_summary = {
        "mediaFragments": int(summary_match.group(1)),
        "videoSamples": int(summary_match.group(2)),
        "audioSamples": int(summary_match.group(3)),
        "bytes": int(summary_match.group(4)),
    }

    defect_pts = Decimal(DEFECT_PICTURE_PTS_90K) / Decimal(90_000)
    defect_index = min(
        range(len(source_frames)),
        key=lambda index: abs(Decimal(source_frames[index]["pts_time"]) - defect_pts),
    )
    defect_frame = source_frames[defect_index]
    if defect_frame["pict_type"] != "B" or abs(Decimal(defect_frame["pts_time"]) - defect_pts) > Decimal("0.000001"):
        raise ValueError("ffprobe did not identify the damaged B-picture")
    previous_key = max(index for index in range(defect_index + 1)
                       if int(source_frames[index]["key_frame"]) == 1)
    next_key = min(index for index in range(defect_index + 1, len(source_frames))
                   if int(source_frames[index]["key_frame"]) == 1)

    ordered_output = sorted(output_frames, key=lambda frame: Decimal(frame["pts_time"]))
    intervals = [
        (Decimal(ordered_output[index + 1]["pts_time"]) - Decimal(ordered_output[index]["pts_time"]), index)
        for index in range(len(ordered_output) - 1)
    ]
    maximum_interval, before_index = max(intervals)
    output_gap_ms = float(maximum_interval * 1000)
    gap_difference_ms = abs(output_gap_ms - browser_gap_ms)
    if gap_difference_ms > 0.002:
        raise ValueError("converter and browser timeline gaps differ")

    print(json.dumps({
        "schemaVersion": 1,
        "fixture": {
            "sha256": fixture_sha,
            "sizeBytes": args.fixture.stat().st_size,
            "windowByteStart": WINDOW_START,
            "windowByteLength": WINDOW_LENGTH,
            "windowSha256": window_sha,
        },
        "converter": {
            "sourceRevisionDeclared": args.converter_source_revision,
            "binarySha256": sha256(args.converter),
            "outputSha256": output_sha,
            "summary": conversion_summary,
        },
        "sourceTimeline": {
            "decodedFrameCountInWindow": len(source_frames),
            "defectPicture": {
                "pts90k": DEFECT_PICTURE_PTS_90K,
                "ptsSeconds": float(defect_pts),
                "type": defect_frame["pict_type"],
                "frameIndexInWindow": defect_index,
            },
            "enclosingKeyframeInterval": {
                "firstFrameIndex": previous_key,
                "firstPtsSeconds": float(Decimal(source_frames[previous_key]["pts_time"])),
                "nextKeyframeIndex": next_key,
                "nextKeyframePtsSeconds": float(Decimal(source_frames[next_key]["pts_time"])),
                "frameCountBeforeNextKeyframe": next_key - previous_key,
                "durationMs": decimal_ms(Decimal(source_frames[next_key]["pts_time"]) - Decimal(source_frames[previous_key]["pts_time"])),
            },
        },
        "convertedTimeline": {
            "decodedFrameCountInWindow": len(output_frames),
            "maximumPresentationInterval": {
                "beforeFrameIndex": before_index,
                "beforePtsSeconds": float(Decimal(ordered_output[before_index]["pts_time"])),
                "afterFrameIndex": before_index + 1,
                "afterPtsSeconds": float(Decimal(ordered_output[before_index + 1]["pts_time"])),
                "intervalMs": output_gap_ms,
            },
        },
        "browserCrossCheck": {
            "analysisFile": args.browser_analysis.name,
            "inputMediaTimeDeltaMs": browser_gap_ms,
            "absoluteDifferenceMs": gap_difference_ms,
            "matchesWithinMs": 0.002,
        },
        "ffprobe": {
            "version": subprocess.check_output(["ffprobe", "-version"], text=True).splitlines()[0],
            "sourceWarnings": source_warnings,
            "outputWarnings": output_warnings,
        },
        "limitations": [
            "The converter source revision is a caller declaration; the binary SHA-256 is authoritative for this run.",
            "The fixed byte window starts and ends mid-stream, so input and output frame counts do not by themselves measure discarded pictures.",
            "The matching 567.233 ms timeline gap locates the observed browser jump in converter output, but does not identify every discarded source picture.",
            "Decoded frame metadata does not prove which damaged pixels could have been displayed safely.",
            "This offline conversion does not measure audible A/V synchronization or browser rendering.",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
