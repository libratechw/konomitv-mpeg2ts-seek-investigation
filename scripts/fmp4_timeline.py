#!/usr/bin/env python3
"""Summarize the encoded sample timeline in a fragmented MP4 file."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def read_u32(data, offset):
    return struct.unpack_from(">I", data, offset)[0]


def read_u64(data, offset):
    return struct.unpack_from(">Q", data, offset)[0]


def read_i32(data, offset):
    return struct.unpack_from(">i", data, offset)[0]


def iter_boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    offset = start
    while offset + 8 <= end:
        size = read_u32(data, offset)
        box_type = data[offset + 4:offset + 8].decode("latin1")
        header_size = 8
        if size == 1:
            if offset + 16 > end:
                raise ValueError("truncated extended-size MP4 box")
            size = read_u64(data, offset + 8)
            header_size = 16
        elif size == 0:
            size = end - offset
        if size < header_size or offset + size > end:
            raise ValueError(f"invalid {box_type} MP4 box size")
        yield box_type, offset + header_size, offset + size
        offset += size
    if offset != end:
        raise ValueError("trailing bytes outside an MP4 box")


def child_boxes(data, start, end, box_type):
    return [box for box in iter_boxes(data, start, end) if box[0] == box_type]


def only_child(data, start, end, box_type):
    matches = child_boxes(data, start, end, box_type)
    if len(matches) != 1:
        raise ValueError(f"expected one {box_type} box, found {len(matches)}")
    return matches[0]


def parse_full_box(data, start, end):
    if end - start < 4:
        raise ValueError("truncated full MP4 box")
    return data[start], int.from_bytes(data[start + 1:start + 4], "big"), start + 4


def parse_track_metadata(data):
    metadata = {}
    moov_boxes = [box for box in iter_boxes(data) if box[0] == "moov"]
    if len(moov_boxes) != 1:
        raise ValueError(f"expected one moov box, found {len(moov_boxes)}")
    _, moov_start, moov_end = moov_boxes[0]
    for _, track_start, track_end in child_boxes(data, moov_start, moov_end, "trak"):
        _, tkhd_start, tkhd_end = only_child(data, track_start, track_end, "tkhd")
        version, _, body = parse_full_box(data, tkhd_start, tkhd_end)
        if version not in {0, 1}:
            raise ValueError(f"unsupported tkhd version {version}")
        track_id = read_u32(data, body + (16 if version else 8))

        _, mdia_start, mdia_end = only_child(data, track_start, track_end, "mdia")
        _, mdhd_start, mdhd_end = only_child(data, mdia_start, mdia_end, "mdhd")
        version, _, body = parse_full_box(data, mdhd_start, mdhd_end)
        if version not in {0, 1}:
            raise ValueError(f"unsupported mdhd version {version}")
        time_scale = read_u32(data, body + (16 if version else 8))

        _, hdlr_start, hdlr_end = only_child(data, mdia_start, mdia_end, "hdlr")
        version, _, body = parse_full_box(data, hdlr_start, hdlr_end)
        if version != 0:
            raise ValueError(f"unsupported hdlr version {version}")
        media_type = data[body + 4:body + 8].decode("ascii")
        if media_type not in {"vide", "soun"}:
            continue
        if track_id in metadata:
            raise ValueError(f"duplicate MP4 track ID {track_id}")
        metadata[track_id] = {"mediaType": media_type, "timeScale": time_scale}
    return metadata


def parse_track_fragment(data, start, end):
    _, tfhd_start, tfhd_end = only_child(data, start, end, "tfhd")
    version, tfhd_flags, offset = parse_full_box(data, tfhd_start, tfhd_end)
    if version != 0:
        raise ValueError(f"unsupported tfhd version {version}")
    track_id = read_u32(data, offset)
    offset += 4
    if tfhd_flags & 0x000001:
        offset += 8
    if tfhd_flags & 0x000002:
        offset += 4
    default_duration = None
    if tfhd_flags & 0x000008:
        default_duration = read_u32(data, offset)
        offset += 4
    if tfhd_flags & 0x000010:
        offset += 4
    if tfhd_flags & 0x000020:
        offset += 4
    if offset != tfhd_end:
        raise ValueError("unsupported tfhd fields")

    _, tfdt_start, tfdt_end = only_child(data, start, end, "tfdt")
    version, _, offset = parse_full_box(data, tfdt_start, tfdt_end)
    if version not in {0, 1}:
        raise ValueError(f"unsupported tfdt version {version}")
    decode_time = read_u64(data, offset) if version else read_u32(data, offset)
    if offset + (8 if version else 4) != tfdt_end:
        raise ValueError("unsupported tfdt fields")

    samples = []
    for _, trun_start, trun_end in child_boxes(data, start, end, "trun"):
        version, trun_flags, offset = parse_full_box(data, trun_start, trun_end)
        if version not in {0, 1}:
            raise ValueError(f"unsupported trun version {version}")
        sample_count = read_u32(data, offset)
        offset += 4
        if trun_flags & 0x000001:
            offset += 4
        if trun_flags & 0x000004:
            offset += 4
        for _ in range(sample_count):
            duration = default_duration
            if trun_flags & 0x000100:
                duration = read_u32(data, offset)
                offset += 4
            if duration is None:
                raise ValueError("MP4 sample duration is absent")
            if trun_flags & 0x000200:
                offset += 4
            if trun_flags & 0x000400:
                offset += 4
            composition_offset = 0
            if trun_flags & 0x000800:
                composition_offset = read_i32(data, offset) if version else read_u32(data, offset)
                offset += 4
            samples.append({
                "decodeTime": decode_time,
                "duration": duration,
                "compositionOffset": composition_offset,
            })
            decode_time += duration
        if offset != trun_end:
            raise ValueError("unsupported trun fields")
    if not samples:
        raise ValueError(f"MP4 track {track_id} fragment has no samples")
    return track_id, samples


def summarize_track(track_id, metadata, fragments):
    samples = [sample for fragment in fragments for sample in fragment]
    presentations = sorted(
        (sample["decodeTime"] + sample["compositionOffset"], sample["duration"])
        for sample in samples
    )
    presentation_starts = [start for start, _ in presentations]
    intervals = [
        presentation_starts[index + 1] - presentation_starts[index]
        for index in range(len(presentation_starts) - 1)
    ]
    timeline = [
        [sample["decodeTime"], sample["duration"], sample["compositionOffset"]]
        for sample in samples
    ]
    time_scale = metadata["timeScale"]
    maximum_interval = max(intervals, default=0)
    return {
        "trackId": track_id,
        "timeScale": time_scale,
        "fragmentCount": len(fragments),
        "sampleCount": len(samples),
        "firstDecodeTime": min(sample["decodeTime"] for sample in samples),
        "lastDecodeEnd": max(sample["decodeTime"] + sample["duration"] for sample in samples),
        "firstPresentationTime": presentation_starts[0],
        "lastPresentationEnd": max(start + duration for start, duration in presentations),
        "maximumPresentationInterval": maximum_interval,
        "maximumPresentationIntervalMs": maximum_interval * 1000 / time_scale,
        "sampleTimingSha256": hashlib.sha256(
            json.dumps(timeline, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def parse_fmp4_timeline(path):
    data = path.read_bytes()
    metadata = parse_track_metadata(data)
    fragments_by_track = {track_id: [] for track_id in metadata}
    fragment_count = 0
    for box_type, moof_start, moof_end in iter_boxes(data):
        if box_type != "moof":
            continue
        fragment_count += 1
        for _, traf_start, traf_end in child_boxes(data, moof_start, moof_end, "traf"):
            track_id, samples = parse_track_fragment(data, traf_start, traf_end)
            if track_id not in fragments_by_track:
                raise ValueError(f"fragment refers to unknown MP4 track {track_id}")
            fragments_by_track[track_id].append(samples)

    tracks = {}
    for track_id, track_metadata in metadata.items():
        media_type = track_metadata["mediaType"]
        label = {"vide": "video", "soun": "audio"}[media_type]
        if label in tracks:
            raise ValueError(f"multiple {label} tracks are not supported")
        if not fragments_by_track[track_id]:
            raise ValueError(f"MP4 {label} track has no fragments")
        tracks[label] = summarize_track(track_id, track_metadata, fragments_by_track[track_id])
    if set(tracks) != {"video", "audio"}:
        raise ValueError("expected one video track and one audio track")
    return {"fragmentCount": fragment_count, "tracks": tracks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    print(json.dumps(parse_fmp4_timeline(args.input), indent=2))


if __name__ == "__main__":
    main()
