"""Shared immutable media storage, scoped to one project or isolated test."""
import os
import filecmp
import shutil
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'studio-comfyui/scripts'))
from project_paths import project_file


def store_media(project, destination, raw=None, *, source=None, replace=False, prior=None):
    """Preserve immutable media bytes within one project or isolated test; shared files are read-only, updates replace paths."""
    project = Path(project).resolve()
    destination = project_file(project, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = Path(source).resolve() if source is not None and Path(source).is_absolute() else (project / source).resolve() if source is not None else None
    size = len(raw) if raw is not None else source.stat().st_size
    def equal(path):
        return path.read_bytes() == raw if raw is not None else filecmp.cmp(path, source, shallow=False)
    before = destination.stat() if destination.exists() else None
    same = before is not None and before.st_size == size and equal(destination)
    if before is not None and not same and (destination.parent / '版本信息.json').is_file():
        raise ValueError('资源版本不可覆盖：' + str(destination))
    if before is not None and not same and not replace:
        raise ValueError('媒体已有不同内容，不覆盖：' + str(destination))
    reuse = None
    if source is not None:
        source = Path(source)
        source = (source if source.is_absolute() else project / source).resolve()
        if (source != destination and source.is_relative_to(project)
                and source.stat().st_dev == destination.parent.stat().st_dev and equal(source)):
            reuse = source
    if reuse is None:
        for folder, dirs, names in os.walk(project, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in {'.git', '.venv', 'node_modules', '__pycache__'}
                             and not name.startswith(('.png-save-', '.media-save-'))
                             and not (Path(folder) / name).is_symlink())
            for name in sorted(names):
                candidate = Path(folder) / name
                if candidate.suffix.lower() != destination.suffix.lower() or candidate == destination or candidate.is_symlink():
                    continue
                state = candidate.stat()
                if (not state.st_mode & 0o222 and state.st_size == size
                        and state.st_dev == destination.parent.stat().st_dev and equal(candidate)):
                    reuse = candidate
                    break
            if reuse is not None:
                break
    if same and (reuse is None or destination.samefile(reuse)):
        destination.chmod(before.st_mode & ~0o222)
        return
    if reuse is not None:
        reuse.chmod(reuse.stat().st_mode & ~0o222)
    with tempfile.TemporaryDirectory(prefix='.media-save-', dir=destination.parent) as folder:
        pending = Path(folder) / ('media' + destination.suffix)
        if reuse is not None:
            os.link(reuse, pending)
        else:
            if raw is None:
                shutil.copyfile(source, pending)
            else:
                pending.write_bytes(raw)
            pending.chmod(pending.stat().st_mode & ~0o222)
        try:
            expected = prior if replace and not same else ([before.st_size, before.st_mtime_ns] if before else None)
            current = destination.stat() if destination.exists() else None
            if ([current.st_size, current.st_mtime_ns] if current else None) != expected:
                raise ValueError('媒体保存期间目标变化，不覆盖：' + str(destination))
            if current is None:
                os.link(pending, destination)
                if sys.platform == 'win32':
                    pending.chmod(pending.stat().st_mode | 0o200)
                    try:
                        pending.unlink()
                    finally:
                        destination.chmod(destination.stat().st_mode & ~0o222)
            elif sys.platform == 'win32':
                # Windows refuses replacing a read-only destination. Retain the old inode
                # while clearing that attribute, then restore its shared links' protection.
                previous = pending.parent / ('previous' + destination.suffix)
                peer = None
                if current.st_nlink > 1:
                    for other in project.rglob('*' + destination.suffix):
                        if (other not in (destination, pending) and not other.is_symlink()
                                and not any(part.startswith(('.png-save-', '.media-save-')) for part in other.relative_to(project).parts)
                                and other.samefile(destination)):
                            peer = other
                            break
                    if peer is None:
                        raise ValueError('共享原版本缺少项目内保留入口，不解除只读保护')
                os.link(destination, previous)
                try:
                    destination.chmod(current.st_mode | 0o200)
                    pending.replace(destination)
                finally:
                    previous.unlink()
                    if peer is not None:
                        peer.chmod(current.st_mode & ~0o222)
                    elif destination.exists() and destination.stat().st_ino == current.st_ino:
                        destination.chmod(current.st_mode & ~0o222)
            else:
                pending.replace(destination)
        finally:
            if sys.platform == 'win32' and pending.exists():
                peer = reuse
                if peer is None and destination.exists() and pending.samefile(destination):
                    peer = destination
                pending.chmod(pending.stat().st_mode | 0o200)
                pending.unlink()
                if peer is not None:
                    peer.chmod(peer.stat().st_mode & ~0o222)
