#!/usr/bin/env python3
"""Prepare frame-accurate Remake segments, bind native prefixes, and join the results."""

import argparse
from dataclasses import asdict, dataclass
from fractions import Fraction
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

FPS = 24
PREFIX = 17
MAX_GENERATION = 345
MIN_GENERATION = 107
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "references/workflows/Viggle-Remake-单人换人-双参考图.api.json"
)


@dataclass
class Segment:
    index: int
    start: int
    end: int
    head: int
    generation: int
    previous_prefix_at: int | None

    @property
    def keep(self):
        return self.end - self.start

    @property
    def name(self):
        return f"segment-{self.index:03d}.mp4"


def plan_segments(total, cuts):
    if total < 1 or sorted(set(cuts)) != list(cuts) or any(not 0 < cut < total for cut in cuts):
        raise ValueError("切点须为原片内部严格递增的 24 fps 帧号")
    segments = []
    boundaries = [0, *cuts, total]
    for shot_start, shot_end in zip(boundaries, boundaries[1:]):
        length = shot_end - shot_start
        continuation_capacity = MAX_GENERATION - PREFIX
        parts = max(1, (length - PREFIX + continuation_capacity - 1) // continuation_capacity)
        first = max((length + parts - 1) // parts, length - (parts - 1) * continuation_capacity)
        size, extra = divmod(length - first, max(1, parts - 1))
        start = shot_start
        for offset in range(parts):
            keep = first if offset == 0 else size + int(offset <= extra)
            head = PREFIX if offset else 0
            needed = keep + head
            generation = max(MIN_GENERATION, 5 + 17 * ((needed - 5 + 16) // 17))
            # Three segments per chain. A fresh chain still uses the matching source preroll.
            previous = segments[-1] if offset % 3 else None
            prefix_at = previous.head + previous.keep - PREFIX if previous else None
            segments.append(Segment(len(segments) + 1, start, start + keep, head, generation, prefix_at))
            start += keep
    return segments


def probe(path):
    data = subprocess.check_output([
        "ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path)
    ])
    streams = json.loads(data)["streams"]
    video = next((stream for stream in streams if stream["codec_type"] == "video"), None)
    if video is None or Fraction(video["avg_frame_rate"]) != FPS or Fraction(video["r_frame_rate"]) != FPS:
        raise ValueError(f"{path} 须先规范为恒定 24 fps")
    return int(video["nb_read_frames"]), any(stream["codec_type"] == "audio" for stream in streams)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-n", *map(str, args)], check=True)


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_plan(work):
    return [Segment(**row) for row in json.loads((work / "segments.json").read_text())]


def prepare(args):
    source = args.source.resolve()
    total, has_audio = probe(source)
    segments = plan_segments(total, args.cut)
    args.work.mkdir(parents=True, exist_ok=True)
    inputs = args.work / "sources"
    inputs.mkdir()
    for segment in segments:
        start = segment.start - segment.head
        tail = segment.generation - segment.keep - segment.head
        output = inputs / segment.name
        video = f"trim=start_frame={start}:end_frame={segment.end},setpts=PTS-STARTPTS"
        video += f",tpad=stop_mode=clone:stop={tail}"
        audio = []
        if has_audio:
            audio_filter = (
                f"aresample={SAMPLE_RATE}:async=1:first_pts=0,"
                f"atrim=start_sample={start * SAMPLES_PER_FRAME}:end_sample={segment.end * SAMPLES_PER_FRAME},"
                f"asetpts=PTS-STARTPTS,apad=whole_len={segment.generation * SAMPLES_PER_FRAME}"
            )
            audio = ["-map", "0:a:0", "-af", audio_filter, "-c:a", "aac", "-b:a", "192k"]
        ffmpeg("-i", source, "-map", "0:v:0", "-vf", video, "-c:v", "libx264",
               "-crf", 16, "-pix_fmt", "yuv420p", *audio, output)
        if probe(output)[0] != segment.generation:
            raise ValueError(f"{output} 的实际帧数与生成计划不一致")
    write_json(args.work / "segments.json", [asdict(segment) for segment in segments])


def graph(args):
    segments = read_plan(args.work)
    if not 1 <= args.segment <= len(segments):
        raise ValueError("段号超出分段计划")
    segment = segments[args.segment - 1]
    if (segment.previous_prefix_at is not None) != bool(args.previous):
        raise ValueError("只有续接段须提供上一段原始生成结果的服务器输入名")
    nodes = json.loads(TEMPLATE.read_text())
    del nodes["66"], nodes["67"]
    nodes["42"]["inputs"]["frames"] = segment.generation
    nodes["62"]["inputs"]["file"] = args.source
    nodes["9"]["inputs"]["image"] = args.face
    nodes["64"]["inputs"]["image"] = args.full_body
    nodes["34"]["inputs"]["value"] = args.prompt.read_text(encoding="utf-8")
    nodes["65"]["inputs"]["filename_prefix"] = f"{args.output_prefix}/segment-{segment.index:03d}"
    if args.previous:
        nodes["69"] = {"class_type": "LoadVideo", "inputs": {"file": args.previous}}
        nodes["70"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["69", 0]}}
        nodes["71"] = {"class_type": "RemakePrefix", "inputs": {
            "vae": ["5", 0], "latent": ["42", 1], "prefix": ["70", 0],
            "prefix_frames": segment.head, "prefix_at": segment.previous_prefix_at,
        }}
        nodes["16"]["inputs"]["latent_image"] = ["71", 0]
    write_json(args.output, nodes)


def join(args):
    segments = read_plan(args.work)
    total, has_audio = probe(args.source)
    if total != segments[-1].end:
        raise ValueError("原片帧数与分段计划不一致")
    with TemporaryDirectory(prefix="viggle-remake-") as directory:
        temporary = Path(directory)
        entries = []
        for segment in segments:
            raw = args.results / segment.name
            if probe(raw)[0] != segment.generation:
                raise ValueError(f"{raw} 的实际帧数与生成计划不一致")
            trim = f"trim=start_frame={segment.head}:end_frame={segment.head + segment.keep},setpts=PTS-STARTPTS"
            ffmpeg("-i", raw, "-map", "0:v:0", "-vf", trim, "-c:v", "libx264",
                   "-crf", 16, "-pix_fmt", "yuv420p", temporary / segment.name)
            entries.append(f"file '{segment.name}'\nduration {segment.keep / FPS:.9f}\n")
        concat = temporary / "segments.ffconcat"
        concat.write_text("".join(entries))
        merged = temporary / "merged.mp4"
        ffmpeg("-f", "concat", "-i", concat, "-i", args.source,
               "-map", "0:v:0", "-map", "1:a:0?", "-c", "copy", "-movflags", "+faststart", merged)
        if probe(merged) != (total, has_audio):
            raise ValueError("合片的帧数或音轨存在状态与原片不一致")
        ffmpeg("-i", merged, "-map", "0", "-c", "copy", "-movflags", "+faststart", args.output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("prepare", help="按明确切点准备 24 fps 源片和分段计划")
    command.add_argument("source", type=Path)
    command.add_argument("work", type=Path)
    command.add_argument("--cut", type=int, action="append", default=[], help="原片已有切点的帧号，可重复")
    command.set_defaults(run=prepare)
    command = commands.add_parser("graph", help="按实际上传名装配一个分段请求")
    command.add_argument("work", type=Path)
    command.add_argument("segment", type=int)
    command.add_argument("--source", required=True)
    command.add_argument("--face", required=True)
    command.add_argument("--full-body", required=True)
    command.add_argument("--prompt", required=True, type=Path)
    command.add_argument("--previous")
    command.add_argument("--output-prefix", required=True)
    command.add_argument("--output", required=True, type=Path)
    command.set_defaults(run=graph)
    command = commands.add_parser("join", help="按分段计划裁头尾、合片并恢复原声")
    command.add_argument("source", type=Path)
    command.add_argument("work", type=Path)
    command.add_argument("results", type=Path, help="按 segment-NNN.mp4 保存的原始生成结果")
    command.add_argument("output", type=Path)
    command.set_defaults(run=join)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
