from __future__ import annotations

from dataclasses import dataclass

from config import BotDefaults


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
        max_age = _to_int(settings.get("max_age_min"), BotDefaults.max_post_age_minutes)
        lang = str(settings.get("lang_filter", "en") or "").strip()

        if simple:
            min_likes = 0
            min_retweets = 0
            max_age = max(max_age, 24 * 60)
            lang = ""

        return FilterConfig(
            min_likes=max(0, min_likes),
            min_retweets=max(0, min_retweets),
            max_age_minutes=max(5, max_age),
            lang=lang,
        )
