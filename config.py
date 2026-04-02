"""
config.py - settings, logging, crypto, runtime paths and rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
import time
from pathlib import Path
from typing import Literal, Optional

from cryptography.fernet import Fernet
from loguru import logger
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_runtime_paths() -> tuple[Path, Path]:
    """Return writable BASE_DIR and executable directory."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        appdata = Path(os.environ.get("APPDATA") or str(Path.home())) / "XBot"
        appdata.mkdir(parents=True, exist_ok=True)
        return appdata, exe_dir

    base = Path(__file__).resolve().parent
    return base, base


BASE_DIR, EXE_DIR = _resolve_runtime_paths()
MEIPASS_DIR = Path(getattr(sys, "_MEIPASS", EXE_DIR))

_ENV_FILE = BASE_DIR / ".env"
_ALT_ENV_FILE = EXE_DIR / ".env"
_DB_DIR = BASE_DIR / "data"
_LOG_DIR = BASE_DIR / "logs"

for _d in (BASE_DIR, _DB_DIR, _LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def _effective_env_file() -> Path:
    """Prefer writable APPDATA env, but support migration from exe-local .env."""
    if _ENV_FILE.exists():
        return _ENV_FILE

    if getattr(sys, "frozen", False) and _ALT_ENV_FILE.exists():
        try:
            _ENV_FILE.write_text(_ALT_ENV_FILE.read_text(
                encoding="utf-8"), encoding="utf-8")
            return _ENV_FILE
        except Exception:
            return _ALT_ENV_FILE

    return _ENV_FILE


def _ensure_env_file() -> None:
    env_path = _effective_env_file()
    if env_path.exists():
        return

    key = Fernet.generate_key().decode()
    env_path.write_text(
        f"ENCRYPTION_KEY={key}\n"
        "OPENAI_API_KEY=\n"
        "GEMINI_API_KEY=\n"
        "PERPLEXITY_API_KEY=\n"
        "GROQ_API_KEY=\n"
        "TELEGRAM_BOT_TOKEN=\n"
        "TELEGRAM_ADMIN_IDS=\n"
        "DEFAULT_AI_PROVIDER=groq\n",
        encoding="utf-8",
    )


_ensure_env_file()
_ENV_IN_USE = _effective_env_file()


def save_env_value(key: str, value: str) -> None:
    lines = _ENV_IN_USE.read_text(
        encoding="utf-8").splitlines() if _ENV_IN_USE.exists() else []

    new_lines: list[str] = []
    updated = False

    for line in lines:
        if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{key}={value}")

    _ENV_IN_USE.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_IN_USE), extra="ignore")

    encryption_key: str = Field(alias="ENCRYPTION_KEY")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    perplexity_api_key: str = Field(default="", alias="PERPLEXITY_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_admin_ids: list[int] = Field(
        default_factory=list, alias="TELEGRAM_ADMIN_IDS")

    default_ai_provider: Literal["openai", "gemini", "perplexity", "groq"] = Field(
        default="groq",
        alias="DEFAULT_AI_PROVIDER",
    )

    db_path: Path = _DB_DIR / "xbot.db"
    log_file: Path = _LOG_DIR / "xbot.log"
    app_log_file: Path = _LOG_DIR / "app.log"
    log_level: str = "INFO"

    @field_validator("telegram_admin_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, v):
        if isinstance(v, list):
            return [int(x) for x in v if str(x).strip()]

        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            return [int(x.strip()) for x in s.split(",") if x.strip()]

        return []


class BotDefaults:
    search_mode = "keywords"
    min_likes = 20
    min_retweets = 0
    max_post_age_minutes = 180
    comment_sort = "likes"
    auto_publish = False
    min_delay_seconds = 5 * 60
    max_delay_seconds = 15 * 60
    daily_comment_limit = 120
    active_hours_start = 0
    active_hours_end = 0
    outside_sleep_min = 0
    comments_in_row = 1
    max_actions_per_cycle = 1
    action_pause_seconds = 20
    enable_manual_extra_actions = False
    hourly_cap = 12
    burst_30min_cap = 6
    simple_filters = False
    like_after_reply = True
    bookmark_after_reply = False
    visit_profile_after_reply = False
    license_enforced = False
    system_prompt = (
        "You are Marcus, an independent trader based in NYC. "
        "Write a concise, human reply in English only. "
        "Max 2 sentences, no hashtags, no emojis."
    )


_settings: Optional[AppSettings] = None
_fernet: Optional[Fernet] = None


def get_browser_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Origin": "https://x.com",
        "Referer": "https://x.com/",
        "Sec-Ch-Ua": '"Google Chrome";v="123", "Chromium";v="123", "Not:A-Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def get_settings() -> AppSettings:
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings


def reload_settings() -> AppSettings:
    global _settings, _fernet
    _settings = None
    _fernet = None
    return get_settings()


def _setup_logger() -> None:
    try:
        s = get_settings()
        level = s.log_level
        log_file = s.log_file
        app_log_file = s.app_log_file
    except Exception:
        level = "INFO"
        log_file = _LOG_DIR / "xbot.log"
        app_log_file = _LOG_DIR / "app.log"

    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )
    logger.add(
        str(log_file),
        level=level,
        enqueue=True,
        rotation="10 MB",
        retention=7,
    )
    logger.add(
        str(app_log_file),
        level="INFO",
        enqueue=True,
        rotation="10 MB",
        retention=7,
        backtrace=True,
        diagnose=True,
    )

    for noisy in ("httpx", "httpcore", "telegram", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(get_settings().encryption_key.encode())
    return _fernet


def encrypt(text: str) -> str:
    return _get_fernet().encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()


_CHROME_UAS = [
    # оставь здесь свой список user-agent'ов
]


class RateLimiter:
    def __init__(self):
        self._history: dict[int, list[float]] = {}

    def record(self, account_id: int) -> None:
        now = time.monotonic()
        self._history.setdefault(account_id, []).append(now)
        self._history[account_id] = [
            t for t in self._history[account_id] if t > now - 86400
        ]

    def count_last_30min(self, account_id: int) -> int:
        cutoff = time.monotonic() - 1800
        return sum(1 for t in self._history.get(account_id, []) if t > cutoff)

    def count_last_hour(self, account_id: int) -> int:
        cutoff = time.monotonic() - 3600
        return sum(1 for t in self._history.get(account_id, []) if t > cutoff)

    def count_today(self, account_id: int) -> int:
        cutoff = time.monotonic() - 86400
        return sum(1 for t in self._history.get(account_id, []) if t > cutoff)

    @staticmethod
    def _is_active_hours(start: int = 8, end: int = 23) -> bool:
        hour = time.localtime().tm_hour
        return start <= hour < end

    async def wait_if_needed(
        self,
        account_id: int,
        daily_limit: int = 300,
        active_hours_start: int = 0,
        active_hours_end: int = 0,
        outside_sleep_min: int = 300,
        hourly_cap: int = 12,
        burst_30min_cap: int = 6,
        wake_event: asyncio.Event | None = None,
    ) -> bool:
        if self.count_today(account_id) >= daily_limit:
            logger.warning(
                f"[Acc {account_id}] Daily limit reached ({daily_limit})")
            return False

        if not self._is_active_hours(active_hours_start, active_hours_end):
            wait_s = outside_sleep_min * 60
            h, m = divmod(outside_sleep_min, 60)
            label = f"{h}ч {m}м" if h else f"{m}м"

            logger.info(
                f"[Acc {account_id}] Outside active hours "
                f"({active_hours_start}:00-{active_hours_end}:00) - sleeping {label}"
            )

            if wake_event is not None:
                wake_event.clear()
                try:
                    await asyncio.wait_for(wake_event.wait(), timeout=wait_s)
                    logger.info(
                        f"[Acc {account_id}] Outside-hours sleep interrupted by force_wake")
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(wait_s)

        if hourly_cap > 0:
            per_hour = self.count_last_hour(account_id)
            if per_hour >= hourly_cap:
                wait = random.uniform(6 * 60, 12 * 60)
                logger.info(
                    f"[Acc {account_id}] Hourly cap ({per_hour}/{hourly_cap}) - wait {wait / 60:.0f}min"
                )
                await asyncio.sleep(wait)

        if burst_30min_cap > 0:
            per_30 = self.count_last_30min(account_id)
            if per_30 >= burst_30min_cap:
                wait = random.uniform(4 * 60, 8 * 60)
                logger.info(
                    f"[Acc {account_id}] Burst cap ({per_30}/{burst_30min_cap}) - wait {wait / 60:.0f}min"
                )
                await asyncio.sleep(wait)

        return True


async def read_delay(text: str = "") -> None:
    cps = random.uniform(8, 14)
    delay = max(1.0, len(text) / cps) if text else random.uniform(1.5, 4.0)
    await asyncio.sleep(delay)


async def compose_delay(reply_text: str) -> None:
    cps = random.uniform(3, 8)
    await asyncio.sleep(max(2.0, len(reply_text) / cps))


async def human_delay(min_seconds: float = 0.8, max_seconds: float = 2.5) -> None:
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


rate_limiter = RateLimiter()
_setup_logger()
