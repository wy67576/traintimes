"""
12306 Public Query API client.

All read-only — no login, no booking, no captcha. Pure schedule/ticket
availability queries backed by the official 12306 public endpoints.

Core APIs implemented:
  - LeftTicket queryX      余票查询
  - Schedule queryByTrainNo 时刻表查询
  - Ticket price           票价查询 (v0.2+)
"""

from __future__ import annotations

import json
from typing import Any
from urllib.request import (
    Request, urlopen, build_opener,
    HTTPCookieProcessor, install_opener,
)
from urllib.error import URLError, HTTPError
from http.cookiejar import CookieJar


BASE = "https://kyfw.12306.cn"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class TrainClient:
    """HTTP client for 12306 read-only query APIs with cookie handling."""

    def __init__(self, timeout: int = 15):
        self._timeout = timeout
        self._opener = build_opener(HTTPCookieProcessor(CookieJar()))
        self._opener.addheaders = [
            ("User-Agent", UA),
            ("Accept-Language", "zh-CN,zh;q=0.9"),
        ]
        self._session_ready = False

    # ── Session management ─────────────────────────────────────────

    def _ensure_session(self) -> None:
        if self._session_ready:
            return
        # Hit init page to get route + BIGipServerotn + JSESSIONID cookies
        init_url = f"{BASE}/otn/leftTicket/init?linktypeid=dc"
        req = Request(init_url, headers={"Accept": "text/html,*/*"})
        try:
            with self._opener.open(req, timeout=self._timeout):
                pass
            self._session_ready = True
        except HTTPError as exc:
            raise TrainError(f"Session init failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise TrainError(f"Session init failed: {exc.reason}") from exc

    def _request(self, path: str, params: dict[str, str] | None = None) -> dict:
        """GET request with proper session cookies."""
        self._ensure_session()

        url = f"{BASE}{path}"
        if params:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{qs}"

        req = Request(url, headers={
            "Accept": "*/*",
            "Referer": f"{BASE}/otn/leftTicket/init?linktypeid=dc",
        })

        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                raw = resp.read()
                # Try UTF-8-SIG first (BOM), fall back to UTF-8
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = raw.decode("utf-8", errors="replace")
                return json.loads(text)
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise TrainError(f"HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise TrainError(f"Connection failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise TrainError(
                f"Invalid JSON response: {exc}\n"
                f"Raw (first 300): {raw[:300]!r}"
            ) from exc

    # ── Left ticket query ⭐ ────────────────────────────────────────

    def search(
        self,
        from_code: str,
        to_code: str,
        date: str,
        purpose: str = "ADULT",
    ) -> SearchResult:
        """Query ticket availability between two stations."""
        data = self._request("/otn/leftTicket/queryX", {
            "leftTicketDTO.train_date": date,
            "leftTicketDTO.from_station": from_code,
            "leftTicketDTO.to_station": to_code,
            "purpose_codes": purpose,
        })

        if not data.get("status"):
            msg = "; ".join(data.get("messages", [])) or "query returned false"
            raise TrainError(msg)

        raw = data.get("data", {})
        result_list: list[str] = raw.get("result", [])
        station_map: dict[str, str] = raw.get("map", {})

        trains = []
        for item in result_list:
            f = item.split("|")
            if len(f) < 36:
                continue

            seat_types: dict[str, str] = {}
            if f[3].startswith(("G", "D", "C")):
                seat_types = {
                    "二等座": f[30] if len(f) > 30 else "-",
                    "一等座": f[31] if len(f) > 31 else "-",
                    "商务座": f[32] if len(f) > 32 else "-",
                    "动卧": f[33] if len(f) > 33 else "-",
                    "无座": f[26] if len(f) > 26 else "-",
                }
            else:
                seat_types = {
                    "硬座": f[29] if len(f) > 29 else "-",
                    "软座": f[28] if len(f) > 28 else "-",
                    "硬卧": f[28] if len(f) > 28 else "-",
                    "软卧": f[23] if len(f) > 23 else "-",
                    "无座": f[26] if len(f) > 26 else "-",
                }

            trains.append(TrainInfo(
                train_no=f[2],
                train_code=f[3],
                from_station=station_map.get(f[6], f[6]),
                to_station=station_map.get(f[7], f[7]),
                depart_time=f[8],
                arrive_time=f[9],
                duration=f[10],
                seat_types=seat_types,
                from_code=f[6],
                to_code=f[7],
            ))

        return SearchResult(trains=trains, station_map=station_map)

    # ── Schedule / Timetable ⭐ ─────────────────────────────────────

    def schedule(
        self,
        train_no: str,
        from_code: str,
        to_code: str,
        date: str,
    ) -> list[StopInfo]:
        """Get the full station schedule for a train."""
        data = self._request("/otn/czxx/queryByTrainNo", {
            "train_no": train_no,
            "from_station_telecode": from_code,
            "to_station_telecode": to_code,
            "depart_date": date,
        })

        if not data.get("status"):
            raise TrainError("schedule query returned false")

        raw_stops = (data.get("data") or {}).get("data", [])
        stops = []
        for s in raw_stops:
            stops.append(StopInfo(
                station_no=int(s.get("station_no", "0")),
                station_name=s.get("station_name", ""),
                arrive_time=s.get("arrive_time", ""),
                depart_time=s.get("start_time", ""),
                stopover=s.get("stopover_time", ""),
                is_start=s.get("is_start", False),
                is_end=s.get("is_end", False),
                telecode=s.get("station_telecode", ""),
            ))
        return stops

    # ── Convenience ─────────────────────────────────────────────────

    def search_with_names(
        self,
        from_station_name: str,
        to_station_name: str,
        date: str,
        stations_lookup,
    ) -> SearchResult:
        """Search using Chinese station names (auto-resolves to codes)."""
        from_code = stations_lookup.resolve(from_station_name)
        to_code = stations_lookup.resolve(to_station_name)
        if not from_code:
            raise TrainError(f"Unknown station: {from_station_name}")
        if not to_code:
            raise TrainError(f"Unknown station: {to_station_name}")
        return self.search(from_code, to_code, date)


# ── Data classes ─────────────────────────────────────────────────────


class TrainInfo:
    """A single train entry from the ticket availability query."""

    __slots__ = (
        "train_no", "train_code", "from_station", "to_station",
        "depart_time", "arrive_time", "duration", "seat_types",
        "from_code", "to_code",
    )

    def __init__(
        self,
        train_no: str,
        train_code: str,
        from_station: str,
        to_station: str,
        depart_time: str,
        arrive_time: str,
        duration: str,
        seat_types: dict[str, str],
        from_code: str = "",
        to_code: str = "",
    ):
        self.train_no = train_no
        self.train_code = train_code
        self.from_station = from_station
        self.to_station = to_station
        self.depart_time = depart_time
        self.arrive_time = arrive_time
        self.duration = duration
        self.seat_types = seat_types
        self.from_code = from_code
        self.to_code = to_code


class SearchResult:
    """Result of a ticket availability query."""

    __slots__ = ("trains", "station_map")

    def __init__(
        self,
        trains: list[TrainInfo],
        station_map: dict[str, str],
    ):
        self.trains = trains
        self.station_map = station_map

    def __len__(self) -> int:
        return len(self.trains)

    def __bool__(self) -> bool:
        return len(self.trains) > 0

    def by_code(self, code: str) -> TrainInfo | None:
        for t in self.trains:
            if t.train_code == code:
                return t
        return None


class StopInfo:
    """A single station stop on a train's route."""

    __slots__ = (
        "station_no", "station_name", "arrive_time", "depart_time",
        "stopover", "is_start", "is_end", "telecode",
    )

    def __init__(
        self,
        station_no: int,
        station_name: str,
        arrive_time: str,
        depart_time: str,
        stopover: str,
        is_start: bool,
        is_end: bool,
        telecode: str,
    ):
        self.station_no = station_no
        self.station_name = station_name
        self.arrive_time = arrive_time
        self.depart_time = depart_time
        self.stopover = stopover
        self.is_start = is_start
        self.is_end = is_end
        self.telecode = telecode


class TrainError(Exception):
    """12306 API error."""
