"""Bound the service log and keep normal status polling out of access logs."""
import logging
from logging.handlers import RotatingFileHandler
import re
import sys
from urllib.parse import urlsplit

LOG_BYTES = 10 * 1024 * 1024
LOG_BACKUPS = 2
POLL = re.compile(r'^/api/(?:workspaces/[^/]+/)?(?:service|projects|comfy/tasks|task-monitor(?:/history)?|projects/[^/]+/status)$')


class PollFilter(logging.Filter):
    def filter(self, record):
        if not record.args or len(record.args) != 5:
            return True
        _, method, path, _, status = record.args
        return not (method == 'GET' and status in (200, 304) and POLL.fullmatch(urlsplit(path).path))


def configure(runtime):
    # The managed worker owns these paths now; no previous worker is still writing.
    trimmed = []
    for name in ('server.log', 'server.log.1', 'server.log.2'):
        path = runtime / name
        if path.exists() and path.stat().st_size > LOG_BYTES:
            size = path.stat().st_size
            with path.open('rb') as stream:
                stream.seek(-2 * 1024 * 1024, 2)
                tail = stream.read().split(b'\n', 1)[-1]
            path.write_bytes(tail)
            trimmed.append((name, size, len(tail)))
    handler = RotatingFileHandler(runtime / 'server.log', maxBytes=LOG_BYTES,
                                  backupCount=LOG_BACKUPS, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger('uvicorn.access').addFilter(PollFilter())

    def uncaught(kind, value, traceback):
        logging.getLogger('launcher').critical('未处理的服务异常', exc_info=(kind, value, traceback))

    sys.excepthook = uncaught
    for name, before, after in trimmed:
        logging.getLogger('launcher').info('历史日志保留近期尾部：%s %d -> %d bytes', name, before, after)
    return handler
