"""
Shared utilities for all Captain Taxi agents.
"""
import time
import structlog
from functools import wraps
from typing import Any, Callable, Awaitable

log = structlog.get_logger()


def configure_logging(log_level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if log_level == "DEBUG" else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(__import__("logging"), log_level, 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def timed_async(label: str):
    """Decorator that logs execution time of async functions."""
    def decorator(fn: Callable[..., Awaitable[Any]]):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                log.debug(f"{label}_ok", duration_ms=elapsed_ms)
                return result
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - start) * 1000)
                log.error(f"{label}_error", error=str(exc), duration_ms=elapsed_ms)
                raise
        return wrapper
    return decorator


def format_phone(phone: str) -> str:
    """Normalize to E.164 format for Twilio."""
    digits = "".join(filter(str.isdigit, phone))
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return f"+{digits}"


def whatsapp_number(phone: str) -> str:
    return f"whatsapp:{format_phone(phone)}"


def truncate(text: str, max_len: int = 500) -> str:
    return text if len(text) <= max_len else text[:max_len - 3] + "..."
