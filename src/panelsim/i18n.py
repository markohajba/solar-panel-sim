"""Tiny i18n layer: JSON locale files plus a ``t(key, **kwargs)`` lookup.

Equations are language-neutral (LaTeX); only surrounding prose is translated.
Missing keys fall back to English and then to the key itself, so a partial
translation degrades gracefully instead of crashing the UI.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

DEFAULT_LANG = "en"
SUPPORTED_LANGS: tuple[str, ...] = ("en", "hr")

_current = {"lang": DEFAULT_LANG}


def _locales_dir() -> Path:
    """Locate the ``locales/`` directory (repo root in the src layout)."""
    candidate = Path(__file__).resolve().parents[2] / "locales"
    if candidate.is_dir():
        return candidate
    # Fallback for unusual working directories.
    return Path.cwd() / "locales"


@cache
def load_locale(lang: str) -> dict[str, str]:
    """Load and cache the translation dictionary for ``lang``."""
    path = _locales_dir() / f"{lang}.json"
    if not path.is_file():
        path = _locales_dir() / f"{DEFAULT_LANG}.json"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def set_language(lang: str) -> None:
    """Set the active UI language (ignored if unsupported)."""
    _current["lang"] = lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def get_language() -> str:
    """Return the active UI language code."""
    return _current["lang"]


def t(key: str, lang: str | None = None, **kwargs: object) -> str:
    """Translate ``key``; interpolate ``{name}`` placeholders from ``kwargs``."""
    lang = lang or _current["lang"]
    text = load_locale(lang).get(key)
    if text is None:
        text = load_locale(DEFAULT_LANG).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return text
    return text


__all__ = [
    "DEFAULT_LANG",
    "SUPPORTED_LANGS",
    "load_locale",
    "set_language",
    "get_language",
    "t",
]
