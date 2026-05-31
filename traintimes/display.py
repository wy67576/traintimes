"""
Terminal display formatter for train schedule / ticket info.

Outputs colorful text tables with emoji — designed for terminal
reading and B站/知乎 demo screenshots.
"""

from __future__ import annotations

import shutil
from typing import Any

from .client import TrainInfo, SearchResult, StopInfo


# ANSI color codes
class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_GREEN_BRIGHT = "\033[102m"
    BG_YELLOW_BRIGHT = "\033[103m"
    BG_BLUE_BRIGHT = "\033[104m"


def _train_emoji(code: str) -> str:
    if code.startswith("G"):
        return "🚄"
    elif code.startswith("D"):
        return "🚄"
    elif code.startswith("C"):
        return "🚄"
    elif code.startswith("Z"):
        return "🚃"
    elif code.startswith("T"):
        return "🚃"
    elif code.startswith("K"):
        return "🚃"
    elif code.startswith("Y"):
        return "🚃"
    return "🚂"


def _fmt(code: str) -> str:
    if code.startswith(("G", "C", "D")):
        return f"{Style.BOLD}{Style.MAGENTA}{code}{Style.RESET}"
    elif code.startswith("Z"):
        return f"{Style.BOLD}{Style.BLUE}{code}{Style.RESET}"
    elif code.startswith("T"):
        return f"{Style.BOLD}{Style.GREEN}{code}{Style.RESET}"
    elif code.startswith("K"):
        return f"{Style.BOLD}{Style.YELLOW}{code}{Style.RESET}"
    return f"{Style.BOLD}{code}{Style.RESET}"


def _seat_color(val: str) -> str:
    val = val.strip()
    if val in ("有",):
        return f"{Style.GREEN}{Style.BOLD}{val}{Style.RESET}"
    if val.isdigit():
        n = int(val)
        if n > 10:
            return f"{Style.GREEN}{val}{Style.RESET}"
        elif n > 0:
            return f"{Style.YELLOW}{val}{Style.RESET}"
        else:
            return f"{Style.RED}{val}{Style.RESET}"
    if val in ("*",):
        return f"{Style.DIM}{val}{Style.RESET}"
    if val in ("无",):
        return f"{Style.RED}{Style.DIM}{val}{Style.RESET}"
    return val


def terminal_width() -> int:
    w = shutil.get_terminal_size((80, 24)).columns
    return max(w, 60)


def _hr(title: str = "", char: str = "━") -> str:
    w = terminal_width()
    if title:
        side = (w - len(title) - 2) // 2
        return f"{char * side} {title} {char * side}"
    return char * w


# ── Search result display ────────────────────────────────────────────


def display_search(result: SearchResult) -> str:
    """Format a ticket availability search result as a colorful table."""
    if not result.trains:
        return f"\n{Style.DIM}No trains found.{Style.RESET}\n"

    lines: list[str] = []
    lines.append("")
    lines.append(
        f"{Style.BOLD}{Style.CYAN}"
        f"{_hr('TICKET AVAILABILITY')}"
        f"{Style.RESET}"
    )

    # Column widths
    w = terminal_width()
    code_w = max(8, min(10, w // 8))
    station_w = max(8, w // 8)
    time_w = 10
    dur_w = 6
    seats_avail = w - code_w - station_w * 2 - time_w - dur_w - 8
    if seats_avail < 10:
        seats_avail = 10
    seat_w = seats_avail // 3

    # Header
    header = (
        f"{'车次':>{code_w}}"
        f" {'出发':>{station_w}} → {'到达':<{station_w}}"
        f" {'出发':>5} {'到达':>5} {'历时':>5}"
        f"  {'座次':<{seat_w * 3}}"
    )
    lines.append(f"{Style.DIM}{header}{Style.RESET}")
    lines.append(Style.DIM + ("─" * w) + Style.RESET)

    for t in result.trains:
        emoji = _train_emoji(t.train_code)
        code_str = f"{emoji} {_fmt(t.train_code)}"

        depart = t.depart_time
        arrive = t.arrive_time
        dur = t.duration

        # Station names — truncate if too long
        fs = t.from_station[:station_w]
        ts = t.to_station[:station_w]

        # Seat info
        seat_parts = []
        for stype, sval in t.seat_types.items():
            if sval not in ("-", "", "*", "无"):
                seat_parts.append(f"{stype}:{_seat_color(sval)}")

        seat_str = " ".join(seat_parts) if seat_parts else "—"

        line = (
            f"{code_str:>{code_w + 3}}"
            f" {fs:>{station_w}} → {ts:<{station_w}}"
            f" {depart:>5} {arrive:>5} {dur:>5}"
            f"  {seat_str}"
        )
        lines.append(line)

    lines.append(
        f"{Style.DIM}{Style.CYAN}"
        f"{_hr()}"
        f"{Style.RESET}"
    )
    lines.append(
        f"{Style.DIM}{len(result.trains)} train(s) found{Style.RESET}"
    )
    return "\n".join(lines)


# ── Schedule display ─────────────────────────────────────────────────


def display_schedule(stops: list[StopInfo], train_code: str = "") -> str:
    """Format train schedule as a vertical timeline."""
    if not stops:
        return f"\n{Style.DIM}No schedule data.{Style.RESET}\n"

    lines: list[str] = []
    title = f" {train_code} SCHEDULE " if train_code else " SCHEDULE "
    lines.append("")
    lines.append(
        f"{Style.BOLD}{Style.CYAN}"
        f"{_hr(title)}"
        f"{Style.RESET}"
    )

    w = terminal_width()
    name_w = max(8, w // 4)
    time_w = 10
    stopover_w = 8

    header = (
        f"{'站序':>4} {'站名':>{name_w}} {'到达':>8} {'出发':>8} {'停靠':>6}"
    )
    lines.append(f"{Style.DIM}{header}{Style.RESET}")
    lines.append(Style.DIM + ("─" * w) + Style.RESET)

    for s in stops:
        no = s.station_no
        name = s.station_name[:name_w]

        arr = s.arrive_time if s.arrive_time and s.arrive_time != "----" else ""
        dep = s.depart_time if s.depart_time and s.depart_time != "----" else ""
        stopover = s.stopover if not s.is_end and s.stopover else ""

        # Marker
        if s.is_start:
            marker = f"{Style.GREEN}●{Style.RESET}"
        elif s.is_end:
            marker = f"{Style.RED}■{Style.RESET}"
        else:
            marker = f"{Style.DIM}○{Style.RESET}"

        line = (
            f" {marker}"
            f" {no:>3}"
            f" {name:>{name_w}}"
            f" {arr:>8}"
            f" {dep:>8}"
            f" {stopover:>6}"
        )
        lines.append(line)

    lines.append(
        f"{Style.CYAN}{Style.DIM}{_hr()}{Style.RESET}"
    )
    lines.append(
        f"{Style.DIM}{len(stops)} stop(s){Style.RESET}"
    )
    return "\n".join(lines)


# ── Stations search display ──────────────────────────────────────────


def display_stations(stations_list: list[dict[str, Any]]) -> str:
    """Format station search results."""
    if not stations_list:
        return f"\n{Style.DIM}No matching stations.{Style.RESET}\n"

    lines: list[str] = []
    lines.append("")
    lines.append(
        f"{Style.BOLD}{Style.CYAN}"
        f"{_hr('STATIONS')}"
        f"{Style.RESET}"
    )

    for s in stations_list:
        code = s.get("code", "")
        name = s.get("name", "")
        pinyin = s.get("pinyin", "")
        city = s.get("city", "")
        lines.append(
            f" {Style.BOLD}{name}{Style.RESET}"
            f"  [{Style.YELLOW}{code}{Style.RESET}]"
            f"  {Style.DIM}{pinyin}{Style.RESET}"
            f"  {Style.DIM}({city}){Style.RESET}"
        )

    lines.append(
        f"{Style.CYAN}{Style.DIM}{_hr()}{Style.RESET}"
    )
    return "\n".join(lines)
