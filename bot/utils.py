from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


def configure_logging(log_level: str, logs_dir: str) -> logging.Logger:
    logger = logging.getLogger("instagram_bot")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(Path(logs_dir) / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def sleep_with_jitter(min_seconds: int, max_seconds: int) -> None:
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def safe_sleep(min_seconds: int, max_seconds: int) -> None:
    sleep_with_jitter(min_seconds, max_seconds)


def load_json(path: Path, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json_atomic(path: Path, data: Dict[str, Any]) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def append_jsonl(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=True) + "\n")


def stream_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    if not path.exists():
        return iter(())
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def read_jsonl_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    if not path.exists():
        return ids
    for entry in stream_jsonl(path):
        if "id" in entry and entry["id"] is not None:
            ids.add(str(entry["id"]))
    return ids


def normalize_user(user: Any) -> Dict[str, str]:
    if isinstance(user, dict):
        data = user
    elif hasattr(user, "dict"):
        data = user.dict()
    else:
        data = {
            "id": getattr(user, "pk", None) or getattr(user, "id", None),
            "username": getattr(user, "username", None),
            "full_name": getattr(user, "full_name", None),
        }

    return {
        "id": str(data.get("id")) if data.get("id") is not None else "",
        "username": str(data.get("username")) if data.get("username") else "",
        "full_name": str(data.get("full_name")) if data.get("full_name") else "",
    }


def build_retryable_exceptions() -> tuple[type[BaseException], ...]:
    extra: List[type[BaseException]] = []
    try:
        import requests

        extra.extend(
            [
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                requests.exceptions.RetryError,
                requests.exceptions.Timeout,
            ]
        )
    except Exception:
        pass

    try:
        from urllib3.exceptions import MaxRetryError, ResponseError

        extra.extend([MaxRetryError, ResponseError])
    except Exception:
        pass

    excs: List[type[BaseException]] = []
    excs.extend(extra)
    return tuple(excs) if excs else (Exception,)


def is_rate_limited_429(error: BaseException) -> bool:
    current: Optional[BaseException] = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if "429" in str(current):
            return True
        seen.add(id(current))
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False


def is_retryable_exception(error: BaseException) -> bool:
    retryable = build_retryable_exceptions()
    return isinstance(error, retryable) or is_rate_limited_429(error)
