#!/usr/bin/env python3
"""Compare converter outputs for one fixed anomalous TS fixture.

The fixture itself may remain private.  The JSON written to stdout contains
only file names, hashes, converter summaries, and fMP4 sample timing.
"""

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from fmp4_timeline import parse_fmp4_timeline


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def parse_variant(values):
    label, source_revision, converter = values
    return label, source_revision, Path(converter)


def convert(fixture, label, source_revision, converter, directory):
    if not converter.is_file():
        raise ValueError(f"converter is not a file: {converter}")
    output = directory / f"{label}.mp4"
    result = subprocess.run(
        [str(converter), str(fixture), str(output)],
        capture_output=True,
        text=True,
        check=True,
    )
    summary_match = re.search(
        r"(?m)^(\d+) media fragments, (\d+) video samples, "
        r"(\d+) audio samples, (\d+) bytes,",
        result.stdout,
    )
    if not summary_match:
        raise ValueError(f"converter summary was not recognized for {label}")
    return {
        "sourceRevisionDeclared": source_revision,
        "binaryFileName": converter.name,
        "binarySha256": sha256(converter),
        "outputSha256": sha256(output),
        "summary": {
            "mediaFragments": int(summary_match.group(1)),
            "videoSamples": int(summary_match.group(2)),
            "audioSamples": int(summary_match.group(3)),
            "bytes": int(summary_match.group(4)),
        },
        "fmp4Timeline": parse_fmp4_timeline(output),
    }


def comparison(variants, before_label, after_label):
    before = variants[before_label]
    after = variants[after_label]
    before_video = before["fmp4Timeline"]["tracks"]["video"]
    after_video = after["fmp4Timeline"]["tracks"]["video"]
    before_audio = before["fmp4Timeline"]["tracks"]["audio"]
    after_audio = after["fmp4Timeline"]["tracks"]["audio"]
    return {
        "before": before_label,
        "after": after_label,
        "videoSampleDelta": (
            after["summary"]["videoSamples"] - before["summary"]["videoSamples"]
        ),
        "maximumVideoPresentationIntervalMs": {
            "before": before_video["maximumPresentationIntervalMs"],
            "after": after_video["maximumPresentationIntervalMs"],
            "delta": (
                after_video["maximumPresentationIntervalMs"]
                - before_video["maximumPresentationIntervalMs"]
            ),
        },
        "audioSampleCountEqual": (
            before["summary"]["audioSamples"] == after["summary"]["audioSamples"]
        ),
        "audioSampleTimingEqual": (
            before_audio["sampleTimingSha256"] == after_audio["sampleTimingSha256"]
        ),
        "audioTimelineBoundsEqual": all(
            before_audio[key] == after_audio[key]
            for key in (
                "firstDecodeTime",
                "lastDecodeEnd",
                "firstPresentationTime",
                "lastPresentationEnd",
            )
        ),
        "outputByteIdentical": before["outputSha256"] == after["outputSha256"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--fixture-label", required=True)
    parser.add_argument("--expected-fixture-sha256", required=True)
    parser.add_argument(
        "--variant",
        action="append",
        nargs=3,
        metavar=("LABEL", "SOURCE_REVISION", "CONVERTER"),
        required=True,
    )
    parser.add_argument(
        "--comparison",
        action="append",
        nargs=2,
        metavar=("BEFORE", "AFTER"),
        default=[],
    )
    args = parser.parse_args()

    fixture_sha256 = sha256(args.fixture)
    if fixture_sha256 != args.expected_fixture_sha256:
        raise ValueError("fixture SHA-256 mismatch")

    variant_specs = [parse_variant(values) for values in args.variant]
    labels = [label for label, _, _ in variant_specs]
    if len(labels) != len(set(labels)):
        raise ValueError("variant labels must be unique")

    with tempfile.TemporaryDirectory() as temporary_directory:
        directory = Path(temporary_directory)
        variants = {
            label: convert(args.fixture, label, revision, converter, directory)
            for label, revision, converter in variant_specs
        }

    for before, after in args.comparison:
        if before not in variants or after not in variants:
            raise ValueError(f"comparison refers to an unknown variant: {before}, {after}")

    print(
        json.dumps(
            {
                "schemaVersion": 1,
                "fixture": {
                    "label": args.fixture_label,
                    "fileName": args.fixture.name,
                    "sha256": fixture_sha256,
                    "sizeBytes": args.fixture.stat().st_size,
                },
                "variants": variants,
                "comparisons": [
                    comparison(variants, before, after)
                    for before, after in args.comparison
                ],
                "limitations": [
                    "Converter source revisions are caller declarations; binary SHA-256 values identify the executed programs.",
                    "The fixed fixture begins and ends mid-stream, so total sample counts do not by themselves measure every discarded source picture.",
                    "fMP4 sample timing does not prove pixel correctness, visible scanout, audible A/V synchronization, or the minimum unavoidable loss.",
                    "This offline conversion does not exercise a browser, decoder, or deinterlacer.",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
