#!/usr/bin/env python3
"""Prepare, assemble and join 24 fps Viggle Remake Swap and Edit segments locally."""

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
MIN_SWAP_GENERATION = 107
MIN_EDIT_GENERATION = 90
SAMPLE_RATE = 48000
SAMPLES_PER_FRAME = SAMPLE_RATE // FPS
WORKFLOWS = Path(__file__).resolve().parents[1] / "references/workflows"
SWAP_TEMPLATE = WORKFLOWS / "Viggle-Remake-单人换人-双参考图.api.json"
EDIT_TEMPLATE = WORKFLOWS / "Viggle-Remake-换背景-目标参考帧.api.json"


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


def aligned_frames(needed, minimum):
    return max(minimum, 5 + 17 * ((needed - 5 + 16) // 17))


def plan_segments(total, cuts, mode="swap"):
    if total < 1 or sorted(set(cuts)) != list(cuts) or any(not 0 < cut < total for cut in cuts):
        raise ValueError("切点须为原片内部严格递增的 24 fps 帧号")
    segments = []
    boundaries = [0, *cuts, total]
    if mode == "edit":
        for index, (start, end) in enumerate(zip(boundaries, boundaries[1:]), 1):
            if end - start > MAX_GENERATION:
                raise ValueError(f"Edit 第 {index} 段超过 345 帧，请按动作和机位补充切点")
            segments.append(Segment(index, start, end, 0, aligned_frames(end - start, MIN_EDIT_GENERATION), None))
        return segments

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
            generation = aligned_frames(needed, MIN_SWAP_GENERATION)
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
    segments = plan_segments(total, args.cut, args.mode)
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


def requested_segment(args):
    segments = read_plan(args.work)
    if not 1 <= args.segment <= len(segments):
        raise ValueError("段号超出分段计划")
    return segments[args.segment - 1]


def load_task(template, args, segment):
    nodes = json.loads(template.read_text(encoding="utf-8"))
    del nodes["66"], nodes["67"]
    nodes["42"]["inputs"]["frames"] = segment.generation
    nodes["72"]["inputs"]["switch"] = args.audio_conditioning == "source"
    nodes["62"]["inputs"]["file"] = args.source
    nodes["34"]["inputs"]["value"] = args.prompt.read_text(encoding="utf-8")
    nodes["65"]["inputs"]["filename_prefix"] = f"{args.output_prefix}/segment-{segment.index:03d}"
    if args.short_edge is not None:
        nodes["54"]["inputs"]["value"] = args.short_edge
    if args.seed is not None:
        if not 0 <= args.seed <= 2**64 - 1:
            raise ValueError("种子须在 0 到 2^64−1 之间")
        nodes["12"]["inputs"]["seed"] = args.seed
    return nodes


def graph(args):
    segment = requested_segment(args)
    if segment.generation < MIN_SWAP_GENERATION:
        raise ValueError("Swap 分段请用 prepare --mode swap 准备")
    if (segment.previous_prefix_at is not None) != bool(args.previous):
        raise ValueError("只有续接段须提供上一段原始生成结果的服务器输入名")
    nodes = load_task(SWAP_TEMPLATE, args, segment)
    nodes["9"]["inputs"]["image"] = args.face
    nodes["64"]["inputs"]["image"] = args.full_body
    if args.reference_order == "full-body-first":
        nodes["42"]["inputs"].update(ref_1=["64", 0], ref_2=["9", 0])
    if args.previous:
        nodes["69"] = {"class_type": "LoadVideo", "inputs": {"file": args.previous}}
        nodes["70"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["69", 0]}}
        nodes["71"] = {"class_type": "RemakePrefix", "inputs": {
            "vae": ["5", 0], "latent": ["42", 1], "prefix": ["70", 0],
            "prefix_frames": segment.head, "prefix_at": segment.previous_prefix_at,
        }}
        nodes["16"]["inputs"]["latent_image"] = ["71", 0]
    write_json(args.output, nodes)


def edit_graph(args):
    segment = requested_segment(args)
    if segment.head:
        raise ValueError("Edit 分段请用 prepare --mode edit 准备")
    if args.pin is not None and not 0 <= args.pin < segment.keep:
        raise ValueError(f"参考帧位须在当前段正文的第 0 到 {segment.keep - 1} 帧之间")
    nodes = load_task(EDIT_TEMPLATE, args, segment)
    nodes["9"]["inputs"]["image"] = args.reference
    nodes["42"]["inputs"]["pins"] = "" if args.pin is None else str(args.pin)
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


def add_graph_arguments(command):
    command.add_argument("work", type=Path, help="prepare 写入分段计划的本地目录")
    command.add_argument("segment", type=int, help="segments.json 中从 1 起算的段号")
    command.add_argument("--source", required=True, help="本段源视频上传后返回的服务器输入名")
    command.add_argument("--prompt", required=True, type=Path, help="本段六段式英文正文文件，UTF-8")
    command.add_argument("--audio-conditioning", choices=("source", "silent"), default="source",
                         help="source 参考原声（默认，可能影响口型）；silent 生成时静音，join 时封回原声")
    command.add_argument("--short-edge", type=int, choices=(480, 736), help="短边像素，省略沿用模板 480")
    command.add_argument("--seed", type=int, help="采样种子，省略沿用模板固定值")
    command.add_argument("--output-prefix", required=True, help="服务器输出目录前缀，工具附加段号")
    command.add_argument("--output", required=True, type=Path, help="要写入的本地 API JSON，不能已存在")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("prepare", help="按明确切点准备 24 fps 源片和分段计划")
    command.add_argument("source", type=Path)
    command.add_argument("work", type=Path)
    command.add_argument("--cut", type=int, action="append", default=[],
                         help="24 fps 源片中的切点帧号，从 0 起算，可重复")
    command.add_argument("--mode", choices=("swap", "edit"), default="swap",
                         help="默认 swap，超长镜头自动切分并规划续接；edit 按给定切点独立分段")
    command.set_defaults(run=prepare)
    command = commands.add_parser("graph", help="按实际上传名装配一个 Swap 分段请求")
    add_graph_arguments(command)
    command.add_argument("--face", required=True, help="面部参考图的服务器输入名")
    command.add_argument("--full-body", required=True, help="全身参考图的服务器输入名")
    command.add_argument("--reference-order", choices=("face-first", "full-body-first"), default="face-first",
                         help="默认面部图第一；反向时需同步正文 Picture 编号")
    command.add_argument("--previous", help="续接段上一段原始结果的服务器输入名")
    command.set_defaults(run=graph)
    command = commands.add_parser("edit-graph", help="按实际上传名装配一个 Edit 分段请求")
    add_graph_arguments(command)
    command.add_argument("--reference", required=True, help="目标参考帧图像的服务器输入名")
    command.add_argument("--pin", type=int, help="参考帧在段内从 0 起算的帧号，省略时作普通参考")
    command.set_defaults(run=edit_graph)
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
