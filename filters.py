from __future__ import annotations

from dataclasses import dataclass

from config import BotDefaults
from config import logger


def _to_int(v, default: int) -> int:
    try:
        return int(v) if v not in ("", None) else default
    except (TypeError, ValueError):
        return default


@dataclass
class FilterConfig:
    min_likes: int
    min_retweets: int
    max_age_minutes: int
    lang: str


class TweetFilterPolicy:
    @staticmethod
    def from_settings(settings: dict) -> FilterConfig:
        simple = bool(settings.get("simple_filters", BotDefaults.simple_filters))
        min_likes = _to_int(settings.get("min_likes"), BotDefaults.min_likes)
        min_retweets = _to_int(settings.get("min_retweets"), BotDefaults.min_retweets)
        max_age = _to_int(
            settings.get("max_age_minutes", settings.get("max_age_min")),
            BotDefaults.max_post_age_minutes,
        )
        lang = str(settings.get("lang_filter", BotDefaults.lang_filter) or "").strip()

        if simple:
            logger.debug("[Filters] simple_filters enabled: using simplified 4-parameter policy")

        legacy_keys = [
            "comment_sort",
            "reply_mode",
            "daily_limit",
            "hourly_cap",
            "burst_30min_cap",
        ]
        ignored_legacy = [k for k in legacy_keys if k in settings]
        if ignored_legacy:
            logger.debug(f"[Filters] Ignoring legacy/non-search filters: {', '.join(ignored_legacy)}")

        cfg = FilterConfig(
            min_likes=max(0, min_likes),
            min_retweets=max(0, min_retweets),
            max_age_minutes=max(5, max_age),
            lang=lang,
        )
        logger.info(
            f"[Filters] Applied: min_likes={cfg.min_likes} min_retweets={cfg.min_retweets} "
            f"max_age_minutes={cfg.max_age_minutes} lang={cfg.lang or 'any'}"
        )
        return cfg
