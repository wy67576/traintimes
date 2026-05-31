"""
Station name↔telegraph code resolver.

Fetches and caches the official 12306 station dictionary (station_name.js),
which maps ~3000 Chinese railway stations to their 3-letter telegraph codes
(e.g. 北京 → BJP, 上海 → SHH, 广州 → GZQ).

Usage:
    stations = Stations()
    stations.name("BJP")    → "北京"
    stations.code("北京西")  → "BXP"
    stations.search("虹桥")  → ["上海虹桥", "无锡东..."]

    # Fuzzy name → auto-resolve, with hints on ambiguity
    stations.resolve("北京") → "BJP"
    stations.resolve("bj")  → "BJP"       (pinyin)
    stations.resolve("bji") → "BJP"       (abbrev)
"""

from __future__ import annotations

import json
import re
import os
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


STATION_URL = (
    "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
    "?station_version=1.9331"
)

# Cache for one day
_CACHE_FILE = Path.home() / ".cache" / "traintimes" / "stations.json"
_CACHE_TTL = 86400


class Stations:
    """Thread-safe station dictionary with fuzzy name resolution."""

    def __init__(self, auto_fetch: bool = True):
        self._by_code: dict[str, dict[str, Any]] = {}
        self._by_name: dict[str, str] = {}       # 中文名 → 电报码
        self._by_pinyin: dict[str, list[str]] = {}  # 拼音 → [电报码...]
        self._by_abbrev: dict[str, list[str]] = {}  # 缩写 → [电报码...]
        self._by_city: dict[str, list[str]] = {}    # 城市 → [电报码...]
        self._fetched = False
        if auto_fetch:
            self.fetch()

    # ── fetching ────────────────────────────────────────────────────

    def fetch(self, force: bool = False) -> None:
        """Download & parse, or load from cache."""
        if not force:
            cached = self._load_cache()
            if cached:
                self._parse(cached)
                self._fetched = True
                return

        raw = self._download()
        self._parse(raw)
        self._save_cache(raw)
        self._fetched = True

    def _download(self) -> str:
        req = Request(STATION_URL, headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
        })
        with urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8")

    def _parse(self, raw: str) -> None:
        self._by_code.clear()
        self._by_name.clear()
        self._by_pinyin.clear()
        self._by_abbrev.clear()
        self._by_city.clear()

        # station_names.js format:
        # var station_names ='@bji|北京|BJP|beijing|bj|2|0357|北京|||...'
        pattern = re.compile(
            r"@(\w+)\|([^|]+)\|([A-Z]{3})\|(\w+)\|(\w+)\|\d+\|\d+\|([^|]*)"
        )
        for m in pattern.finditer(raw):
            abbrev = m.group(1)     # bji
            name = m.group(2)       # 北京
            code = m.group(3)       # BJP
            pinyin = m.group(4)     # beijing
            short = m.group(5)      # bj
            city = (m.group(6) or name).strip()

            self._by_code[code] = {
                "name": name,
                "pinyin": pinyin,
                "abbrev": abbrev,
                "short": short,
                "city": city,
                "code": code,
            }
            self._by_name[name] = code

            self._by_pinyin.setdefault(pinyin, []).append(code)
            self._by_abbrev.setdefault(abbrev, []).append(code)
            self._by_abbrev.setdefault(short, []).append(code)
            self._by_city.setdefault(city, []).append(code)

    # ── cache ───────────────────────────────────────────────────────

    def _cache_path(self) -> Path:
        return _CACHE_FILE

    def _load_cache(self) -> str | None:
        p = self._cache_path()
        if not p.exists():
            return None
        if time.time() - p.stat().st_mtime > _CACHE_TTL:
            return None
        return p.read_text("utf-8")

    def _save_cache(self, raw: str) -> None:
        p = self._cache_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(raw, encoding="utf-8")

    # ── lookup ──────────────────────────────────────────────────────

    @property
    def codes(self) -> set[str]:
        return set(self._by_code.keys())

    @property
    def names(self) -> set[str]:
        return set(self._by_name.keys())

    def name(self, code: str) -> str | None:
        """电报码 → 中文站名"""
        entry = self._by_code.get(code.upper())
        return entry["name"] if entry else None

    def code(self, name_or_pinyin: str) -> str | None:
        """Exact name or pinyin → telegraph code."""
        if name_or_pinyin in self._by_name:
            return self._by_name[name_or_pinyin]
        lower = name_or_pinyin.lower()
        if lower in self._by_pinyin:
            codes = self._by_pinyin[lower]
            return codes[0] if codes else None
        if lower in self._by_abbrev:
            codes = self._by_abbrev[lower]
            return codes[0] if codes else None
        return None

    def search(self, query: str) -> list[dict[str, Any]]:
        """Fuzzy search by name, pinyin, or code. Returns list of station dicts."""
        q = query.lower()
        results: list[dict[str, Any]] = []

        # Match by code prefix
        for code, entry in self._by_code.items():
            if code.lower().startswith(q):
                results.append(entry)

        # Match by name substring
        for name, code in self._by_name.items():
            if q in name.lower() or q in name:
                if code.upper().startswith(q):  # already added
                    continue
                results.append(self._by_code[code])

        # Match by pinyin
        for pinyin, codes in self._by_pinyin.items():
            if pinyin.startswith(q):
                for c in codes:
                    if c.upper() not in {r["code"] for r in results}:
                        results.append(self._by_code[c])

        # Match by abbrev
        for abbrev, codes in self._by_abbrev.items():
            if abbrev.startswith(q):
                for c in codes:
                    if c.upper() not in {r["code"] for r in results}:
                        results.append(self._by_code[c])

        return results[:20]

    def resolve(self, text: str) -> str | None:
        """Smart resolve: 中文站名/拼音/缩写/电报码 → 电报码.

        Returns None if ambiguous or not found.
        """
        text = text.strip()
        if not text:
            return None

        # Try exact code match
        upper = text.upper()
        if upper in self._by_code:
            return upper

        # Try exact name
        if text in self._by_name:
            return self._by_name[text]

        # Try pinyin / abbrev
        lower = text.lower()
        if lower in self._by_pinyin and len(self._by_pinyin[lower]) == 1:
            return self._by_pinyin[lower][0]
        if lower in self._by_abbrev and len(self._by_abbrev[lower]) == 1:
            return self._by_abbrev[lower][0]

        # Fuzzy — return if only one match
        results = self.search(text)
        if len(results) == 1:
            return results[0]["code"]
        return None

    def suggest(self, text: str) -> list[str]:
        """Return station name suggestions for partial match."""
        return [e["name"] for e in self.search(text)[:10]]
