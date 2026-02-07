"""Pipeline-style logging for ShopLens API.

Produces colourful, structured output inspired by run_pipeline.py:
  ──────────────────────────────────────────────────────────────
  [fn] search_youtube_reviews("iPhone 17", limit=3)
    ✓ Found 3 YouTube video(s)  (0.9s)
  ──────────────────────────────────────────────────────────────
"""

import logging
import os
import sys
import time
import warnings
from typing import Any

from app.core.config import settings

# Suppress Pydantic field shadowing warnings from third-party libraries (google-genai, firecrawl)
warnings.filterwarnings("ignore", message="Field name .* shadows an attribute in parent", category=UserWarning)

# ── ANSI colours ────────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"

# Enable colours if stdout is a TTY or FORCE_COLOR is set (e.g. in Docker)
_use_colour = sys.stdout.isatty() or os.environ.get("FORCE_COLOR", "") == "1"
if not _use_colour:
    BOLD = DIM = RESET = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = ""

LINE = f"{DIM}{'─' * 62}{RESET}"
DOUBLE_LINE = f"{BOLD}{'═' * 62}{RESET}"


# ── Health-check filter ─────────────────────────────────────────────────────

class _HealthCheckFilter(logging.Filter):
    """Drop noisy health-check access log lines."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "/health" in msg and ("200" in msg or "GET" in msg):
            return False
        return True


# ── Custom formatter ────────────────────────────────────────────────────────

_LEVEL_COLOURS = {
    "DEBUG": DIM,
    "INFO": CYAN,
    "WARNING": YELLOW,
    "ERROR": RED,
    "CRITICAL": f"{BOLD}{RED}",
}


class ShopLensFormatter(logging.Formatter):
    """Compact, colourful formatter.

    Output format:
      HH:MM:SS │ LEVEL │ short_name │ message
    """

    def format(self, record: logging.LogRecord) -> str:
        ts = time.strftime("%H:%M:%S", time.localtime(record.created))

        level = record.levelname
        colour = _LEVEL_COLOURS.get(level, "")

        # Shorten logger name: "app.functions.review_tools" → "review_tools"
        name = record.name.rsplit(".", 1)[-1] if "." in record.name else record.name
        # Cap width
        name = name[:18]

        msg = record.getMessage()

        # Exceptions
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg = f"{msg}\n{record.exc_text}"

        return f"{DIM}{ts}{RESET} {colour}{level:<7}{RESET} {DIM}│{RESET} {BOLD}{name:<18}{RESET} {DIM}│{RESET} {msg}"


# ── Setup ───────────────────────────────────────────────────────────────────

def setup_logging() -> None:
    """Configure application logging — call once at startup."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Remove any existing handlers on root
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(ShopLensFormatter())
    root.addHandler(handler)
    root.setLevel(log_level)

    # Uvicorn access — attach health-check filter
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addFilter(_HealthCheckFilter())

    # Always suppress SQL echo (engine echo=False in session.py)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)

    # Suppress noisy HTTP client loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)
    logging.getLogger("httpx._client").setLevel(logging.WARNING)

    # Suppress google-genai internal logs
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


# ── Pipeline-style helpers ──────────────────────────────────────────────────
# Use these in chat_service / review_tools for structured output.

def log_header(logger: logging.Logger, title: str) -> None:
    """Print a pipeline section header."""
    logger.info(f"{LINE}")
    logger.info(f"{BOLD}{title}{RESET}")
    logger.info(f"{LINE}")


def log_step(logger: logging.Logger, step: int, total: int, title: str) -> None:
    """Print a numbered pipeline step header."""
    logger.info(f"{LINE}")
    logger.info(f"{BOLD}{CYAN}[Step {step}/{total}]{RESET} {BOLD}{title}{RESET}")


def log_success(logger: logging.Logger, msg: str) -> None:
    """Print a success line."""
    logger.info(f"  {GREEN}✓{RESET} {msg}")


def log_warn(logger: logging.Logger, msg: str) -> None:
    """Print a warning line."""
    logger.warning(f"  {YELLOW}⚠{RESET} {msg}")


def log_fail(logger: logging.Logger, msg: str) -> None:
    """Print an error line."""
    logger.error(f"  {RED}✗{RESET} {msg}")


def log_detail(logger: logging.Logger, msg: str) -> None:
    """Print a dim detail line."""
    logger.info(f"  {DIM}{msg}{RESET}")


def elapsed_str(start: float) -> str:
    """Format elapsed time since *start*."""
    return f"{DIM}({time.time() - start:.1f}s){RESET}"
