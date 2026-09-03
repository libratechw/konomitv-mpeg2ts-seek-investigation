#!/usr/bin/env python3
"""Inspect the fixed fixture without exporting its audiovisual payload.

Usage: python3 inspect-nogizaka-transport-defect.py /path/to/nogizaka.ts
Requires ffprobe on PATH. The fixed byte window is intentionally not a general
TS parser: PES headers must fit in their first packet, as verified here.
"""
import argparse
import bisect
import hashlib
import json
import re
import subprocess
from pathlib import Path

FIXTURE_SHA = "2240bbb8848d0c244378498dc0482b9c4f34e71a722dff01a2b6bfe50d1ca845"
START = 200484140
LENGTH = 3760000
VIDEO_PID = 256
DEFECT_PICTURE_PTS_90K = 502_108_869


def read_bits(data, start, length):
    value = 0
    for offset in range(start, start + length):
        value = (value << 1) | ((data[offset // 8] >> (7 - offset % 8)) & 1)
    return value


def inspect(data):
    es = bytearray()
    mapping, pes, anomalies = [], [], []
    previous = {}
    for i in range(0, len(data), 188):
        packet = data[i:i + 188]
        if len(packet) != 188 or packet[0] != 0x47:
            raise ValueError(f"TS alignment at {START + i}")
        pid = ((packet[1] & 31) << 8) | packet[2]
        afc, cc = (packet[3] >> 4) & 3, packet[3] & 15
        if afc == 0 or packet[1] & 128:
            raise ValueError(f"invalid header or TEI at {START + i}")
        if not afc & 1:
            continue
        payload = 4 + (1 + packet[4] if afc & 2 else 0)
        if payload >= 188:
            raise ValueError("invalid payload boundary")
        discontinuity = bool(afc & 2 and packet[4] and packet[5] & 128)
        if pid != 8191 and pid in previous:
            old_cc, old_offset, old_packet = previous[pid]
            if cc != (old_cc + 1) % 16 and packet != old_packet:
                anomalies.append({
                    "byteOffset": START + i, "pid": pid,
                    "previousByteOffset": old_offset, "previousCC": old_cc,
                    "cc": cc, "discontinuityIndicator": discontinuity,
                    "missingCounterValuesModulo16": (cc - old_cc - 1) % 16,
                })
        previous[pid] = (cc, START + i, packet)
        if pid != VIDEO_PID:
            continue
        if packet[1] & 64:
            if packet[payload:payload + 4] != b"\0\0\1\xe0":
                raise ValueError("unexpected video PES")
            end = payload + 9 + packet[payload + 8]
            if end > 188 or not packet[payload + 7] & 128:
                raise ValueError("PES header split or missing PTS")
            b = packet[payload + 9:payload + 14]
            if not (b[0] & b[2] & b[4] & 1):
                raise ValueError("invalid PTS marker")
            pts = ((b[0] >> 1 & 7) << 30) | (b[1] << 22) | ((b[2] >> 1) << 15) | (b[3] << 7) | (b[4] >> 1)
            pes.append((len(es), START + i, pts))
            payload = end
        mapping.append((len(es), START + i + payload))
        es.extend(packet[payload:])
    map_offsets = [item[0] for item in mapping]
    pes_offsets = [item[0] for item in pes]
    start_codes = [(match.start(), match.group(1)[0])
                   for match in re.finditer(b"\x00\x00\x01(.)", es, re.DOTALL)]
    picture_coding = {}
    current_gop = None
    for index, (at, code) in enumerate(start_codes):
        if code == 0xB8:
            payload = es[at + 4:at + 8]
            current_gop = {
                "esByteOffset": at,
                "closedGop": bool(read_bits(payload, 25, 1)),
                "brokenLink": bool(read_bits(payload, 26, 1)),
            }
            continue
        if code != 0x00:
            continue
        coding = {"gop": current_gop}
        for extension_at, extension_code in start_codes[index + 1:]:
            if extension_code in (0x00, 0xB3, 0xB8):
                break
            if extension_code != 0xB5:
                continue
            payload = es[extension_at + 4:extension_at + 10]
            if read_bits(payload, 0, 4) != 8:
                continue
            coding.update({
                "pictureStructure": {
                    1: "top-field", 2: "bottom-field", 3: "frame",
                }[read_bits(payload, 22, 2)],
                "progressiveFrame": bool(read_bits(payload, 32, 1)),
            })
            break
        if "pictureStructure" not in coding:
            raise ValueError("picture coding extension not found")
        picture_coding[at] = coding

    pictures = []
    picture_records = []
    for match in re.finditer(b"\x00\x00\x01\x00", es):
        at = match.start()
        index = bisect.bisect_right(pes_offsets, at) - 1
        if index < 0:
            continue  # Window starts inside a PES; it has no verified timestamp.
        source = mapping[bisect.bisect_right(map_offsets, at) - 1]
        bits = int.from_bytes(es[at + 4:at + 6], "big")
        kind = (bits >> 3) & 7
        if kind not in (1, 2, 3):
            raise ValueError("invalid picture type")
        picture = {"pictureByteOffset": source[1] + at - source[0],
                   "pesByteOffset": pes[index][1], "pts90k": pes[index][2],
                   "type": "?IPB"[kind], "temporalReference": bits >> 6}
        pictures.append(picture)
        picture_records.append((picture, picture_coding[at]))
    defect_records = [
        record for record in picture_records
        if record[0]["pts90k"] == DEFECT_PICTURE_PTS_90K
    ]
    if len(defect_records) != 1:
        raise ValueError("fixed defect picture is missing or ambiguous")
    defect_record = defect_records[0]
    defect_picture, coding = defect_record
    gop = coding["gop"]
    if gop is None:
        raise ValueError("defect picture has no GOP header in the fixed window")
    same_gop = [picture for picture, candidate_coding in picture_records
                if candidate_coding["gop"] is gop]
    intra_temporal_reference = next(
        picture["temporalReference"] for picture in same_gop
        if picture["type"] == "I"
    )
    leading_b = [
        picture["temporalReference"] for picture in same_gop
        if picture["type"] == "B"
        and picture["temporalReference"] < intra_temporal_reference
    ]
    gop_source = mapping[bisect.bisect_right(map_offsets, gop["esByteOffset"]) - 1]
    defect_picture_coding = {
        **defect_picture,
        "pictureStructure": coding["pictureStructure"],
        "progressiveFrame": coding["progressiveFrame"],
        "gopHeaderByteOffset": (
            gop_source[1] + gop["esByteOffset"] - gop_source[0]
        ),
        "closedGop": gop["closedGop"],
        "brokenLink": gop["brokenLink"],
        "leadingBPictureTemporalReferences": leading_b,
        "openGopConfirmed": not gop["closedGop"] and bool(leading_b),
    }
    return anomalies, pictures, defect_picture_coding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    with args.fixture.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
        if digest != FIXTURE_SHA:
            raise ValueError("fixture SHA-256 mismatch")
        source.seek(START)
        data = source.read(LENGTH)
    if len(data) != LENGTH:
        raise ValueError("short read")
    anomalies, pictures, defect_picture_coding = inspect(data)
    command = ["ffprobe", "-v", "warning", "-f", "mpegts", "-i", "pipe:0",
               "-select_streams", "v:0", "-show_frames", "-show_entries",
               "frame=pts,pkt_pos,pict_type", "-of", "json"]
    probe = subprocess.run(command, input=data, capture_output=True, check=True)
    frames = json.loads(probe.stdout)["frames"]
    reference = {(int(f["pkt_pos"]) + START, int(f["pts"])): f["pict_type"]
                 for f in frames if "pkt_pos" in f and "pts" in f}
    local = [p for p in pictures if 201700000 < p["pictureByteOffset"] < 203400000]
    for p in local:
        if reference.get((p["pesByteOffset"], p["pts90k"])) != p["type"]:
            raise ValueError("picture metadata disagrees with ffprobe")
    print(json.dumps({
        "schemaVersion": 1, "fixtureSha256": digest,
        "fixtureSizeBytes": args.fixture.stat().st_size,
        "window": {"byteStart": START, "byteLength": LENGTH,
                   "sha256": hashlib.sha256(data).hexdigest()},
        "videoPid": VIDEO_PID, "continuityAnomalies": anomalies,
        "defectPictureCoding": defect_picture_coding,
        "pictures": local, "ffprobeCrossCheckCount": len(local),
        "ffprobeVersion": subprocess.check_output(["ffprobe", "-version"], text=True).splitlines()[0],
        "ffprobeFrames": frames,
        "ffprobeWarnings": re.sub(r" @ 0x[0-9a-f]+", "", probe.stderr.decode()),
        "limitations": [
            "Counter gaps give a missing count modulo 16, not the exact number of lost packets.",
            "Only the fixed byte window was inspected for transport anomalies.",
            "ffprobe may conceal damage; decoded frames do not prove undamaged pixels.",
            "A frame picture with progressive_frame=0 is interlaced-coded, but it is not a field picture.",
            "The byte window starts mid-stream; startup warnings are not additional fixture defects.",
            "This does not prove browser drop attribution or minimum recoverable frame loss.",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
