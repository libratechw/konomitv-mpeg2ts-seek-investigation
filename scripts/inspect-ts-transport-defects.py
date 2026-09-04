#!/usr/bin/env python3
"""Locate transport-stream continuity defects and their MPEG-2 pictures.

The script reads an unmodified 188-byte-packet TS file.  It does not export
audio or video payload.  For each continuity-counter gap on the selected video
PID, it inspects a bounded byte window and reports the damaged picture and its
immediate neighbours.
"""

import argparse
import bisect
import hashlib
import json
import re
from pathlib import Path

PACKET_SIZE = 188
PTS_WRAP = 1 << 33


def bits(data, start, length):
    value = 0
    for offset in range(start, start + length):
        value = (value << 1) | (
            (data[offset // 8] >> (7 - offset % 8)) & 1
        )
    return value


def decode_pts(data):
    if len(data) != 5 or not (data[0] & data[2] & data[4] & 1):
        raise ValueError("invalid PTS")
    return (
        ((data[0] >> 1 & 7) << 30)
        | (data[1] << 22)
        | ((data[2] >> 1) << 15)
        | (data[3] << 7)
        | (data[4] >> 1)
    )


def scan_transport(path, video_pid):
    digest = hashlib.sha256()
    previous = {}
    anomalies = []
    first_video_pts = None
    packet_count = 0
    tei_count = 0
    declared_discontinuities = 0

    with path.open("rb") as source:
        offset = 0
        while True:
            chunk = source.read(PACKET_SIZE * 32768)
            if not chunk:
                break
            digest.update(chunk)
            if len(chunk) % PACKET_SIZE:
                raise ValueError("file size is not a multiple of 188 bytes")
            for relative in range(0, len(chunk), PACKET_SIZE):
                packet = chunk[relative:relative + PACKET_SIZE]
                absolute = offset + relative
                packet_count += 1
                if packet[0] != 0x47:
                    raise ValueError(f"TS sync lost at byte {absolute}")
                tei = bool(packet[1] & 0x80)
                pusi = bool(packet[1] & 0x40)
                pid = ((packet[1] & 31) << 8) | packet[2]
                afc = (packet[3] >> 4) & 3
                cc = packet[3] & 15
                if tei:
                    tei_count += 1
                    anomalies.append({
                        "type": "transport-error-indicator",
                        "byteOffset": absolute,
                        "pid": pid,
                        "cc": cc,
                        "pusi": pusi,
                    })
                if afc == 0:
                    anomalies.append({
                        "type": "reserved-adaptation-field-control",
                        "byteOffset": absolute,
                        "pid": pid,
                    })
                    continue
                payload_start = 4
                discontinuity = False
                if afc & 2:
                    if packet[4] > 0:
                        discontinuity = bool(packet[5] & 0x80)
                    payload_start = 5 + packet[4]
                if discontinuity:
                    declared_discontinuities += 1
                has_payload = bool(afc & 1 and payload_start < PACKET_SIZE)
                if not has_payload:
                    continue

                if pid != 0x1FFF:
                    old = previous.get(pid)
                    if old is not None and not discontinuity:
                        expected = (old["cc"] + 1) & 15
                        if cc == old["cc"]:
                            if packet != old["packet"]:
                                anomalies.append({
                                    "type": "same-cc-different-packet",
                                    "byteOffset": absolute,
                                    "previousByteOffset": old["byteOffset"],
                                    "pid": pid,
                                    "previousCC": old["cc"],
                                    "cc": cc,
                                    "pusi": pusi,
                                })
                        elif cc != expected:
                            anomalies.append({
                                "type": "cc-gap",
                                "byteOffset": absolute,
                                "previousByteOffset": old["byteOffset"],
                                "pid": pid,
                                "previousCC": old["cc"],
                                "cc": cc,
                                "missingCounterValuesModulo16": (
                                    cc - old["cc"] - 1
                                ) & 15,
                                "pusi": pusi,
                            })
                    previous[pid] = {
                        "cc": cc,
                        "byteOffset": absolute,
                        "packet": packet,
                    }

                if (
                    pid == video_pid
                    and first_video_pts is None
                    and pusi
                    and payload_start + 14 <= PACKET_SIZE
                    and packet[payload_start:payload_start + 4]
                    == b"\x00\x00\x01\xe0"
                    and packet[payload_start + 7] & 0x80
                ):
                    first_video_pts = decode_pts(
                        packet[payload_start + 9:payload_start + 14]
                    )
            offset += len(chunk)

    return {
        "sha256": digest.hexdigest(),
        "sizeBytes": path.stat().st_size,
        "packetCount": packet_count,
        "teiCount": tei_count,
        "declaredDiscontinuityCount": declared_discontinuities,
        "firstVideoPts90k": first_video_pts,
        "anomalies": anomalies,
    }


def inspect_video_window(path, start, length, video_pid, target_offset):
    with path.open("rb") as source:
        source.seek(start)
        data = source.read(length)
    if len(data) != length:
        raise ValueError("short window read")

    es = bytearray()
    mapping = []
    pes = []
    previous_cc = None
    gap_es_offset = None
    for relative in range(0, len(data), PACKET_SIZE):
        packet = data[relative:relative + PACKET_SIZE]
        absolute = start + relative
        pid = ((packet[1] & 31) << 8) | packet[2]
        afc = (packet[3] >> 4) & 3
        cc = packet[3] & 15
        payload_start = 4 + (1 + packet[4] if afc & 2 else 0)
        has_payload = bool(afc & 1 and payload_start < PACKET_SIZE)
        if pid != video_pid or not has_payload:
            continue
        discontinuity = bool(afc & 2 and packet[4] and packet[5] & 0x80)
        if (
            previous_cc is not None
            and not discontinuity
            and cc != previous_cc
            and cc != ((previous_cc + 1) & 15)
            and absolute == target_offset
        ):
            gap_es_offset = len(es)
        previous_cc = cc
        if packet[1] & 0x40:
            if packet[payload_start:payload_start + 4] != b"\x00\x00\x01\xe0":
                raise ValueError("unexpected video PES start")
            header_end = payload_start + 9 + packet[payload_start + 8]
            if header_end > PACKET_SIZE:
                raise ValueError("split PES header is outside the supported fixture")
            pts = None
            if packet[payload_start + 7] & 0x80:
                pts = decode_pts(packet[payload_start + 9:payload_start + 14])
            pes.append((len(es), absolute, pts))
            payload_start = header_end
        mapping.append((len(es), absolute + payload_start))
        es.extend(packet[payload_start:])

    if gap_es_offset is None:
        raise ValueError("target video continuity gap was not found in its window")

    start_codes = [
        (match.start(), match.group(1)[0])
        for match in re.finditer(b"\x00\x00\x01(.)", es, re.DOTALL)
    ]
    current_gop = None
    pictures = []
    mapping_offsets = [entry[0] for entry in mapping]
    pes_offsets = [entry[0] for entry in pes]
    for index, (at, code) in enumerate(start_codes):
        if code == 0xB8:
            payload = es[at + 4:at + 8]
            current_gop = {
                "closedGop": bool(bits(payload, 25, 1)),
                "brokenLink": bool(bits(payload, 26, 1)),
            }
            continue
        if code != 0x00:
            continue
        header = int.from_bytes(es[at + 4:at + 6], "big")
        kind = (header >> 3) & 7
        if kind not in (1, 2, 3):
            continue
        coding = {}
        for extension_at, extension_code in start_codes[index + 1:]:
            if extension_code in (0x00, 0xB3, 0xB8):
                break
            if extension_code != 0xB5:
                continue
            payload = es[extension_at + 4:extension_at + 10]
            if len(payload) >= 6 and bits(payload, 0, 4) == 8:
                coding = {
                    "pictureStructure": {
                        1: "top-field",
                        2: "bottom-field",
                        3: "frame",
                    }.get(bits(payload, 22, 2), "unknown"),
                    "progressiveFrame": bool(bits(payload, 32, 1)),
                }
                break
        mapping_index = bisect.bisect_right(mapping_offsets, at) - 1
        pes_index = bisect.bisect_right(pes_offsets, at) - 1
        picture = {
            "pictureByteOffset": (
                mapping[mapping_index][1] + at - mapping[mapping_index][0]
                if mapping_index >= 0 else None
            ),
            "pesByteOffset": pes[pes_index][1] if pes_index >= 0 else None,
            "pts90k": pes[pes_index][2] if pes_index >= 0 else None,
            "type": "?IPB"[kind],
            "temporalReference": header >> 6,
            "gop": current_gop,
            **coding,
            "esByteOffset": at,
        }
        pictures.append(picture)

    picture_offsets = [picture["esByteOffset"] for picture in pictures]
    damaged_index = bisect.bisect_right(picture_offsets, gap_es_offset) - 1
    if damaged_index < 0:
        raise ValueError("continuity gap precedes the first picture in the window")

    def public_picture(index):
        if not 0 <= index < len(pictures):
            return None
        return {
            key: value for key, value in pictures[index].items()
            if key != "esByteOffset"
        }

    damaged = public_picture(damaged_index)
    target_gop = pictures[damaged_index]["gop"]
    same_gop = [
        picture for picture in pictures if picture["gop"] is target_gop
    ]
    intra_references = [
        picture["temporalReference"] for picture in same_gop
        if picture["type"] == "I"
    ]
    leading_b = []
    if intra_references:
        leading_b = [
            picture["temporalReference"] for picture in same_gop
            if picture["type"] == "B"
            and picture["temporalReference"] < intra_references[0]
        ]
    damaged["leadingBPictureTemporalReferences"] = leading_b
    damaged["openGopConfirmed"] = bool(
        target_gop
        and not target_gop["closedGop"]
        and leading_b
    )

    return {
        "byteStart": start,
        "byteLength": length,
        "sha256": hashlib.sha256(data).hexdigest(),
        "gapByteOffsetInWindow": target_offset - start,
        "pictureCount": len(pictures),
        "previousPicture": public_picture(damaged_index - 1),
        "damagedPicture": damaged,
        "nextPicture": public_picture(damaged_index + 1),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--video-pid", type=lambda value: int(value, 0), default=0x100)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--window-mib", type=int, default=64)
    parser.add_argument("--pre-gap-mib", type=int, default=16)
    args = parser.parse_args()

    transport = scan_transport(args.fixture, args.video_pid)
    if args.expected_sha256 and transport["sha256"] != args.expected_sha256:
        raise ValueError("fixture SHA-256 mismatch")

    window_length = (
        args.window_mib * 1024 * 1024 // PACKET_SIZE
    ) * PACKET_SIZE
    pre_gap = (
        args.pre_gap_mib * 1024 * 1024 // PACKET_SIZE
    ) * PACKET_SIZE
    video_gaps = [
        anomaly for anomaly in transport["anomalies"]
        if anomaly["type"] == "cc-gap" and anomaly["pid"] == args.video_pid
    ]
    first_pts = transport["firstVideoPts90k"]
    defects = []
    for anomaly in video_gaps:
        start = max(0, anomaly["byteOffset"] - pre_gap)
        start = start // PACKET_SIZE * PACKET_SIZE
        length = min(window_length, transport["sizeBytes"] - start)
        length = length // PACKET_SIZE * PACKET_SIZE
        window = inspect_video_window(
            args.fixture, start, length, args.video_pid, anomaly["byteOffset"]
        )
        damaged_pts = window["damagedPicture"]["pts90k"]
        media_time = None
        if first_pts is not None and damaged_pts is not None:
            media_time = ((damaged_pts - first_pts) % PTS_WRAP) / 90000
        defects.append({
            "transport": anomaly,
            "mediaTimeFromFirstVideoPtsSeconds": media_time,
            "window": window,
        })

    print(json.dumps({
        "schemaVersion": 1,
        "fixture": {
            key: transport[key] for key in (
                "sha256", "sizeBytes", "packetCount", "teiCount",
                "declaredDiscontinuityCount", "firstVideoPts90k",
            )
        },
        "videoPid": args.video_pid,
        "transportAnomalies": transport["anomalies"],
        "videoDefects": defects,
        "limitations": [
            "A counter gap gives a missing count modulo 16, not an exact lost-packet count.",
            "A damaged coded picture does not by itself determine the number of browser display frames lost.",
            "Decoded output, visible pixels, unavoidable minimum loss, and audible A/V sync are not evaluated.",
            "The bounded windows start mid-stream; this script does not treat decoder startup warnings as source defects.",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
