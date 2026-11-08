"""Objective video stream/container metadata; no business adoption."""
from fractions import Fraction
import json
import shutil
import subprocess

def probe(path):
    """Read stream/container facts only; no frame scan, ASR, quality score or rehash."""
    executable = shutil.which('ffprobe')
    if executable is None:
        raise FileNotFoundError('视频媒体信息读取缺少ffprobe；未改写为Agent人工检查')
    state = path.stat()
    try:
        result = subprocess.run([executable, '-v', 'error', '-show_entries',
            'stream=codec_type,codec_name,width,height,avg_frame_rate,duration,nb_frames,bit_rate,channels,sample_rate:format=duration,bit_rate',
            '-of', 'json', str(path)], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as error:
        raise ValueError('视频媒体信息读取超时；不自动重生成') from error
    if result.returncode:
        raise ValueError('视频媒体信息读取失败：'+result.stderr.strip()[:500])
    data = json.loads(result.stdout)
    video = next((stream for stream in data['streams'] if stream['codec_type']=='video'), None)
    if video is None:
        raise ValueError('实际成果没有可读取的视频轨')
    current = path.stat()
    if (state.st_size, state.st_mtime_ns)!=(current.st_size,current.st_mtime_ns):
        raise ValueError('读取媒体信息期间视频发生变化')
    def number(value):
        return None if value in (None, 'N/A', '0/0') else float(Fraction(value))
    return dict(stamp=[state.st_size,state.st_mtime_ns], width=video['width'], height=video['height'],
        codec=video['codec_name'], frame_rate=number(video.get('avg_frame_rate')),
        duration=number(video.get('duration') or data['format'].get('duration')),
        frames=number(video.get('nb_frames')), video_mbps=(number(video['bit_rate'])/1e6 if video.get('bit_rate') not in (None,'N/A') else None),
        total_mbps=(number(data['format']['bit_rate'])/1e6 if data['format'].get('bit_rate') not in (None,'N/A') else None),
        audio=[stream for stream in data['streams'] if stream['codec_type']=='audio'], source='ffprobe stream/container metadata')
