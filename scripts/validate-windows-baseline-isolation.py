#!/usr/bin/env python3
"""Baseline-only fixed-band 200-seek isolation contract (offline, stdlib only).

Owner: existing Windows measurement tooling under
``reports/seek-investigation/scripts/``; validity owner is
``docs/MEASUREMENT.md`` with outcome taxonomy from
``reports/seek-investigation/METHODOLOGY.md``.

Scope: the root Windows measurement manager executes the two live runs
(low ``[240, 480]`` then high ``[900, 1140]`` seconds, baseline only,
200 completed seeks each). This module never drives a browser, never
touches the network or production, and never reads private evidence. It
provides the deterministic seek-sequence generator plus the fail-closed
validator the manager runs before and after each live run, and the
sanitized deterministic summary suitable for later publication review.

Tracked schema reuse: stable-recovery and fatal-stop definitions,
``recoveryOutcome`` taxonomy, ``blockSize 200``, ``baseSeed``,
``originalRequestPath`` / ``playerState=converting`` route proof, and
hash-pinned inputs mirror the published Windows Starlette viewing-seek
results (``results/windows-starlette-viewing-seek-*.json``).

Usage (all offline, hermetic)::

    python3 validate-windows-baseline-isolation.py sequence \
        --base-seed 20260906 --band low --count 200 --out seq.json
    python3 validate-windows-baseline-isolation.py validate \
        --manifest manifest.json --evidence evidence.json --out summary.json
    python3 validate-windows-baseline-isolation.py hash --path <file>

Any missing input, hash mismatch, route mismatch, sequence mismatch,
incomplete/fatal block, idle-proof gap, or cleanup/restoration gap
refuses the run: exit nonzero, no summary written.
"""

import argparse
import hashlib
import json
import math
import re
import statistics
import sys
from pathlib import Path

SCHEMA_VERSION = 1
BLOCK_SIZE = 200
RECOVERY_CUTOFF_MS = 2000.0

FIXED_BANDS = {
    "low": (240.0, 480.0),
    "high": (900.0, 1140.0),
}

STABLE_RECOVERY = (
    "target rVFC observed in buffered media; seeked; visible canvas; "
    "readyState >= 3; eight consecutive video frames spanning at least "
    "100 ms with no gap over 50 ms; recovery time is the first frame of "
    "that confirmed run"
)
FATAL_STOP = (
    "stable display did not recover within 2000 ms of assigning "
    "video.currentTime without another user operation"
)

OUTCOMES = (
    "automatic-within-2s",
    "automatic-after-2s",
    "user-action-required",
    "unknown-after-2s-cutoff",
)

REQUIRED_HOST_IDLE = (
    "noBuildLoad",
    "noIndexerLoad",
    "noAnalysisLoad",
    "noStrayMeasurementProcesses",
)
REQUIRED_CLEANUP = (
    "videoStopped",
    "fullscreenOff",
    "tabClosed",
    "browserStopped",
    "transferStopped",
    "isolatedServerStopped",
)

IDENTITY_FIELDS = (
    "baselineCommit",
    "baselineFileSha256",
    "konomiCommit",
    "sourceCommit",
    "distCommit",
    "sourceHash",
    "distHash",
    "distTreeSha256",
    "asset",
    "playerAssetHash",
    "fixtureName",
    "fixtureSha256",
    "runnerSha256",
)

_ORIGINAL_ROUTE_RE = re.compile(r"^/api/videos/[0-9]+/download$")
_BROWSER_RE = re.compile(r"^Chrome/[0-9]+(\.[0-9]+)+$")
_SAFE_LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_ASSET_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.js$")
_FIXTURE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.ts$")


def _is_hex(value, length):
    return (
        isinstance(value, str)
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def resolve_band(band):
    """Map a band label or explicit pair to its fixed (lo, hi) seconds."""
    if isinstance(band, str) and band in FIXED_BANDS:
        return FIXED_BANDS[band]
    if (
        isinstance(band, (list, tuple))
        and len(band) == 2
        and all(isinstance(v, (int, float)) for v in band)
    ):
        pair = (float(band[0]), float(band[1]))
        if pair in (FIXED_BANDS["low"], FIXED_BANDS["high"]):
            return pair
    raise ValueError("band must be 'low', 'high', [240.0, 480.0], or [900.0, 1140.0]")


def band_label(band):
    lo, hi = resolve_band(band)
    for label, pair in FIXED_BANDS.items():
        if (lo, hi) == pair:
            return label
    raise ValueError("unreachable band")  # pragma: no cover


def generate_sequence(base_seed, band, count=BLOCK_SIZE):
    """Deterministically generate ``count`` seek targets inside ``band``.

    Mapping: ``SHA-256("{seed}:{lo}:{hi}:{index}")`` digest as a uniform
    fraction scaled into ``[lo, hi]``, quantized to whole microseconds so
    JSON round-trips are exact across platforms.
    """
    if not isinstance(base_seed, int) or isinstance(base_seed, bool):
        raise ValueError("base_seed must be an int")
    if count != BLOCK_SIZE:
        raise ValueError("count must be %d for this isolation" % BLOCK_SIZE)
    lo, hi = resolve_band(band)
    width = hi - lo
    targets = []
    for index in range(count):
        payload = ("%d:%.1f:%.1f:%d" % (base_seed, lo, hi, index)).encode()
        digest = hashlib.sha256(payload).digest()
        fraction = int.from_bytes(digest, "big") / float(1 << 256)
        micros = int(round((lo + fraction * width) * 1_000_000))
        targets.append(micros / 1_000_000.0)
    return targets


def sequence_sha256(targets):
    body = "".join("%.6f\n" % float(t) for t in targets).encode()
    return hashlib.sha256(body).hexdigest()


def sha256_file(path):
    value = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            value.update(chunk)
    return value.hexdigest()


def _percentile(values, fraction):
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def _distribution(values):
    return {
        "count": len(values),
        "meanMs": sum(values) / len(values),
        "medianMs": statistics.median(values),
        "p95Ms": _percentile(values, 0.95),
        "p99Ms": _percentile(values, 0.99),
        "maximumMs": max(values),
        "minimumMs": min(values),
    }


def _slope_ms_per_seek(values):
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    denom = sum((i - mean_x) ** 2 for i in range(n))
    if denom == 0:
        return 0.0
    return sum((i - mean_x) * (y - mean_y) for i, y in enumerate(values)) / denom


def check_manifest(manifest):
    """Fail-closed validation of the root-frozen immutable inputs."""
    errors = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    for field in ("konomiCommit", "sourceCommit", "distCommit"):
        if not _is_hex(manifest.get(field), 40):
            errors.append("manifest.%s must be 40-char lowercase hex" % field)
    for field in (
        "sourceHash",
        "distHash",
        "distTreeSha256",
        "playerAssetHash",
        "fixtureSha256",
        "baselineFileSha256",
        "runnerSha256",
    ):
        if not _is_hex(manifest.get(field), 64):
            errors.append("manifest.%s must be 64-char lowercase hex" % field)
    if not isinstance(manifest.get("baselineCommit"), str) or not _SAFE_LABEL_RE.match(
        manifest.get("baselineCommit")
    ):
        errors.append("manifest.baselineCommit must be a safe label")
    asset = manifest.get("asset")
    if not isinstance(asset, str) or not _ASSET_RE.match(asset):
        errors.append("manifest.asset must be a safe .js filename")
    fixture_name = manifest.get("fixtureName")
    if not isinstance(fixture_name, str) or not _FIXTURE_RE.match(fixture_name):
        errors.append("manifest.fixtureName must be a safe .ts filename")
    path = manifest.get("originalRequestPath")
    if not isinstance(path, str) or not _ORIGINAL_ROUTE_RE.match(path):
        errors.append(
            "manifest.originalRequestPath must be /api/videos/<numeric-id>/download"
        )
    if manifest.get("playerState") != "converting":
        errors.append("manifest.playerState must be 'converting'")
    if manifest.get("quality") != "Original (MPEG-2)":
        errors.append("manifest.quality must be 'Original (MPEG-2)'")
    browser = manifest.get("browser")
    if not isinstance(browser, str) or not _BROWSER_RE.match(browser):
        errors.append("manifest.browser must be Chrome/<dotted-numeric-version>")
    if manifest.get("transport") != "Windows-local":
        errors.append("manifest.transport must be 'Windows-local'")
    if manifest.get("fullscreen") is not True:
        errors.append("manifest.fullscreen must be true")
    band_ok = True
    try:
        manifest_band = resolve_band(manifest.get("band"))
    except ValueError:
        errors.append("manifest.band must be 'low', 'high', or the fixed pair")
        manifest_band = None
        band_ok = False
    seed_ok = type(manifest.get("baseSeed")) is int
    if not seed_ok:
        errors.append("manifest.baseSeed must be an int")
    block_ok = type(manifest.get("blockSize")) is int and manifest.get(
        "blockSize"
    ) == BLOCK_SIZE
    if not block_ok:
        errors.append("manifest.blockSize must be %d" % BLOCK_SIZE)
    expected = manifest.get("expectedSequenceSha256")
    if not _is_hex(expected, 64):
        errors.append("manifest.expectedSequenceSha256 must be 64-char hex")
    elif band_ok and seed_ok and block_ok:
        try:
            canonical = sequence_sha256(
                generate_sequence(
                    manifest.get("baseSeed"), manifest.get("band"), BLOCK_SIZE
                )
            )
        except ValueError:
            errors.append("manifest band/seed cannot produce a canonical sequence")
        else:
            if expected != canonical:
                errors.append(
                    "manifest.expectedSequenceSha256 does not match the "
                    "canonical sequence for baseSeed/band/blockSize"
                )
    return errors


def check_evidence(manifest, evidence):
    """Fail-closed validation of one live-run evidence object."""
    errors = []
    if not isinstance(evidence, dict):
        return ["evidence must be a JSON object"]

    # Route proof: every live route field must equal the frozen manifest.
    for field in (
        "originalRequestPath",
        "playerState",
        "quality",
        "browser",
        "transport",
        "fullscreen",
    ):
        if evidence.get(field) != manifest.get(field):
            errors.append("route mismatch: %s" % field)
    # Identity proof: every frozen runtime identity must be carried by
    # the evidence and equal the manifest. No literal pins live here.
    for field in IDENTITY_FIELDS:
        if field not in evidence:
            errors.append("evidence missing identity: %s" % field)
        elif evidence.get(field) != manifest.get(field):
            errors.append("identity mismatch: %s" % field)

    # Fixed-band proof.
    try:
        manifest_band = resolve_band(manifest.get("band"))
        evidence_band = resolve_band(evidence.get("band"))
        if manifest_band != evidence_band:
            errors.append("band mismatch between manifest and evidence")
        lo, hi = manifest_band
    except ValueError:
        errors.append("evidence.band must be the fixed low or high band")
        lo, hi = (None, None)

    if type(evidence.get("baseSeed")) is not int:
        errors.append("evidence.baseSeed must be an int")
    elif evidence.get("baseSeed") != manifest.get("baseSeed"):
        errors.append("seed mismatch between manifest and evidence")

    # Deterministic sequence proof.
    targets = evidence.get("targets")
    if not isinstance(targets, list) or len(targets) != BLOCK_SIZE:
        errors.append("evidence.targets must hold exactly %d entries" % BLOCK_SIZE)
        targets = None
    elif lo is not None and any(
        not isinstance(t, (int, float)) or isinstance(t, bool) or not math.isfinite(t)
        or t < lo
        or t > hi
        for t in targets
    ):
        errors.append("evidence.targets must all lie inside the fixed band")
    if targets is not None:
        try:
            if sequence_sha256(targets) != manifest.get("expectedSequenceSha256"):
                errors.append("seek sequence does not match the frozen sequence hash")
        except (TypeError, ValueError):
            errors.append("evidence.targets are not hashable seek times")

    # Completion proof: exactly 200 completed seeks, no fatal record.
    if type(evidence.get("completedSeeks")) is not int or evidence.get(
        "completedSeeks"
    ) != BLOCK_SIZE:
        errors.append("evidence.completedSeeks must be %d" % BLOCK_SIZE)
    latencies = evidence.get("latenciesMs")
    if not isinstance(latencies, list) or len(latencies) != BLOCK_SIZE:
        errors.append("evidence.latenciesMs must hold exactly %d entries" % BLOCK_SIZE)
        latencies = None
    elif any(
        not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v)
        or v < 0
        for v in latencies
    ):
        errors.append("evidence.latenciesMs must hold finite non-negative numbers")
        latencies = None
    counts = evidence.get("recoveryOutcomeCounts")
    if not isinstance(counts, dict) or set(counts) != set(OUTCOMES):
        errors.append("evidence.recoveryOutcomeCounts must hold exactly the 4 outcomes")
        counts = None
    elif any(
        not isinstance(counts[k], int) or isinstance(counts[k], bool) or counts[k] < 0
        for k in OUTCOMES
    ):
        errors.append("evidence.recoveryOutcomeCounts must hold non-negative ints")
    if "fatalStop" not in evidence:
        errors.append("evidence.fatalStop key is required (null for a completed block)")
        fatal = None
    else:
        fatal = evidence.get("fatalStop")
    if fatal is not None:
        errors.append("fatalStop present: block did not complete 200 clean seeks")
        if isinstance(fatal, dict):
            outcome = fatal.get("recoveryOutcome")
            if outcome != "unknown-after-2s-cutoff":
                errors.append(
                    "fatalStop.recoveryOutcome must stay "
                    "'unknown-after-2s-cutoff', never reclassified"
                )
            if fatal.get("automaticRecoveryTimeMs") is not None:
                errors.append(
                    "cutoff fatalStop must not claim an automatic recovery time"
                )
            if fatal.get("requiredRecoveryAction") is not None:
                errors.append(
                    "cutoff fatalStop must not claim a recovery action; "
                    "'user-action-required' is a separate outcome"
                )
    if counts is not None:
        if counts["unknown-after-2s-cutoff"] != 0:
            errors.append("unknown-after-2s-cutoff must be 0 for a 200/200 block")
        if counts["user-action-required"] != 0:
            errors.append("user-action-required must be 0 for a 200/200 block")
        if counts["automatic-after-2s"] != 0:
            errors.append("automatic-after-2s must be 0 under the 2 s cutoff design")
        if counts["automatic-within-2s"] != BLOCK_SIZE:
            errors.append("automatic-within-2s must be %d" % BLOCK_SIZE)
        if latencies is not None and any(v > RECOVERY_CUTOFF_MS for v in latencies):
            errors.append("latenciesMs holds a >2000 ms entry without a cutoff record")

    # Host-idle proof.
    idle = evidence.get("hostIdle")
    if not isinstance(idle, dict):
        errors.append("evidence.hostIdle proof is required")
    else:
        for key in REQUIRED_HOST_IDLE:
            if idle.get(key) is not True:
                errors.append("host not idle: %s" % key)

    # Cleanup and restoration proof.
    cleanup = evidence.get("cleanup")
    if not isinstance(cleanup, dict):
        errors.append("evidence.cleanup proof is required")
    else:
        for key in REQUIRED_CLEANUP:
            if cleanup.get(key) is not True:
                errors.append("cleanup incomplete: %s" % key)
    restoration = evidence.get("restoration")
    if not isinstance(restoration, dict):
        errors.append("evidence.restoration proof is required")
    else:
        if restoration.get("starletteBaselineFileSha256") != manifest.get(
            "baselineFileSha256"
        ):
            errors.append("restoration baseline file hash mismatch")
        if restoration.get("noRemainingPorts") is not True:
            errors.append("restoration must confirm no remaining ports")

    seconds = evidence.get("measurementSeconds")
    if (
        not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
        or not math.isfinite(seconds)
        or seconds <= 0
    ):
        errors.append("evidence.measurementSeconds must be a positive number")
    return errors


def build_summary(manifest, evidence):
    """Build the sanitized deterministic publication-ready summary."""
    latencies = [float(v) for v in evidence["latenciesMs"]]
    label = band_label(manifest["band"])
    first20 = latencies[:20]
    last20 = latencies[-20:]
    summary = {
        "schemaVersion": SCHEMA_VERSION,
        "purpose": "Baseline-only fixed-band 200-seek isolation for the "
        "Windows Starlette viewing-seek investigation.",
        "band": label,
        "baseSeed": manifest["baseSeed"],
        "sequenceSha256": manifest["expectedSequenceSha256"],
        "blockSize": BLOCK_SIZE,
        "completedSeeks": BLOCK_SIZE,
        "recoveryOutcomeCounts": {
            key: evidence["recoveryOutcomeCounts"][key] for key in OUTCOMES
        },
        "stableRecoveryLatencyMs": {
            "all": _distribution(latencies),
            "first20": _distribution(first20),
            "last20": _distribution(last20),
            "last20MinusFirst20MedianMs": statistics.median(last20)
            - statistics.median(first20),
            "linearSlopeMsPerSeek": _slope_ms_per_seek(latencies),
        },
        "measurementSeconds": float(evidence["measurementSeconds"]),
        "route": {
            "transport": manifest["transport"],
            "fullscreen": True,
            "quality": manifest["quality"],
            "originalRequestPath": manifest["originalRequestPath"],
            "browser": manifest["browser"],
            "playerState": manifest["playerState"],
        },
        "identity": {
            "konomiCommit": manifest["konomiCommit"],
            "sourceCommit": manifest["sourceCommit"],
            "distCommit": manifest["distCommit"],
            "sourceHash": manifest["sourceHash"],
            "distHash": manifest["distHash"],
            "distTreeSha256": manifest["distTreeSha256"],
            "asset": manifest["asset"],
            "playerAssetHash": manifest["playerAssetHash"],
            "fixtureName": manifest["fixtureName"],
            "fixtureSha256": manifest["fixtureSha256"],
            "baselineCommit": manifest["baselineCommit"],
            "baselineFileSha256": manifest["baselineFileSha256"],
            "runnerSha256": manifest["runnerSha256"],
        },
        "definitions": {
            "stableRecovery": STABLE_RECOVERY,
            "fatalStop": FATAL_STOP,
        },
        "limitations": [
            "Baseline-only isolation: no candidate comparison is made from "
            "this summary alone.",
            "A 200/200 block with zero 2 s cutoffs does not establish "
            "recovery behavior after a longer failure or without user "
            "action outside the measured window.",
            "This summary covers one Windows host, one fixture, one "
            "browser, one fixed seek band, and one deterministic 200-seek "
            "sequence.",
            "Audible A/V sync and subjective picture quality were not "
            "measured.",
        ],
    }
    return summary


def cmd_sequence(args):
    targets = generate_sequence(args.base_seed, args.band, args.count)
    payload = {
        "baseSeed": args.base_seed,
        "band": band_label(args.band),
        "targetBandSeconds": list(resolve_band(args.band)),
        "count": len(targets),
        "targets": targets,
        "sequenceSha256": sequence_sha256(targets),
    }
    Path(args.out).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def cmd_validate(args):
    try:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("refused: cannot load inputs: %s" % exc, file=sys.stderr)
        return 2
    errors = check_manifest(manifest)
    if errors:
        for error in errors:
            print("refused: %s" % error, file=sys.stderr)
        return 2
    errors = check_evidence(manifest, evidence)
    if errors:
        for error in errors:
            print("refused: %s" % error, file=sys.stderr)
        return 2
    summary = build_summary(manifest, evidence)
    Path(args.out).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Windows baseline-only fixed-band isolation contract."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    seq = sub.add_parser("sequence", help="emit a deterministic seek sequence")
    seq.add_argument("--base-seed", type=int, required=True)
    seq.add_argument("--band", required=True, help="'low' or 'high'")
    seq.add_argument("--count", type=int, default=BLOCK_SIZE)
    seq.add_argument("--out", required=True)
    val = sub.add_parser("validate", help="validate evidence, emit summary")
    val.add_argument("--manifest", required=True)
    val.add_argument("--evidence", required=True)
    val.add_argument("--out", required=True)
    hsh = sub.add_parser("hash", help="print SHA-256 of a file")
    hsh.add_argument("--path", required=True)
    args = parser.parse_args(argv)
    if args.command == "sequence":
        return cmd_sequence(args)
    if args.command == "validate":
        return cmd_validate(args)
    print(sha256_file(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
