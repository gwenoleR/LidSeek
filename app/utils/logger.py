import logging
import os
import json
from logging.handlers import RotatingFileHandler

# Environment-driven logging knobs
LOG_DIR = os.getenv('LOG_DIR', '/app/app/logs')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
JSON_LOGS = os.getenv('JSON_LOGS', 'false').lower() in {'1', 'true', 'yes'}
CONSOLE_LOGS = os.getenv('CONSOLE_LOGS', 'true').lower() in {'1', 'true', 'yes'}

class JsonFormatter(logging.Formatter):
    """Structured JSON formatter with common fields.

    Includes timestamp, logger name, level, message, and any `extra` fields.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'ts': self.formatTime(record, datefmt='%Y-%m-%d %H:%M:%S'),
            'logger': record.name,
            'level': record.levelname,
            'msg': record.getMessage(),
        }
        # Merge extra/custom attributes safely
        for key, value in record.__dict__.items():
            if key in ('msg', 'args', 'levelname', 'levelno', 'name', 'pathname', 'filename', 'module',
                       'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName', 'created', 'msecs',
                       'relativeCreated', 'thread', 'threadName', 'processName', 'process', 'ts'):
                continue
            payload[key] = value
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def setup_logger(name: str, log_file: str, level: int | None = None) -> logging.Logger:
    """Configure a logger with rotation and optional JSON output.

    - Uses `LOG_DIR`, `LOG_LEVEL`, `JSON_LOGS`, `CONSOLE_LOGS` env vars.
    - Creates per-service rotating file handlers.
    - Disables propagation to avoid duplicate logs.
    """

    os.makedirs(LOG_DIR, exist_ok=True)

    # Resolve level: env overrides passed-in default when not provided
    effective_level = level if level is not None else getattr(logging, LOG_LEVEL, logging.INFO)

    # Choose formatter
    if JSON_LOGS:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        os.path.join(LOG_DIR, log_file),
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)

    # Console handler (optional)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(effective_level)
    logger.propagate = False

    # Avoid handler duplication across multiple setup calls
    if not logger.handlers:
        logger.addHandler(file_handler)
        if CONSOLE_LOGS:
            logger.addHandler(console_handler)

    return logger

def with_context(logger: logging.Logger, **extra):
    """Return a LoggerAdapter injecting `extra` context fields.

    Example: `with_context(logger, album_mbid=..., track_mbid=...)`
    """
    return logging.LoggerAdapter(logger, extra)