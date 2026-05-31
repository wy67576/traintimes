#!/usr/bin/env python3
"""
traintimes CLI — 12306 train schedule & ticket availability from the terminal.

Usage:
    tt search 北京 上海 --date 2026-06-15
    tt schedule G119 --date 2026-06-15
    tt stations 虹桥
    tt monitor G119 北京 上海   (v0.2+)
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from . import __version__
from .client import TrainClient, TrainError
from .stations import Stations
from .display import (
    display_search,
    display_schedule,
    display_stations,
    Style,
)


def build_parser():
    import argparse

    p = argparse.ArgumentParser(
        prog="tt",
        description="查火车票·查时刻 — 12306命令行工具",
        epilog="示例:\n"
        "  tt search 北京 上海 --today\n"
        "  tt search 北京 上海 --date 2026-06-15\n"
        "  tt schedule G119 --date 2026-06-15\n"
        "  tt stations 虹桥",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--version", action="version", version=f"traintimes {__version__}",
    )

    sub = p.add_subparsers(dest="command", required=True)

    # ── search ──────────────────────────────────────────────────
    search_p = sub.add_parser(
        "search", aliases=["s", "查"],
        help="查余票 / Query ticket availability",
    )
    search_p.add_argument("from_station", help="出发站 (站名/拼音/代码)")
    search_p.add_argument("to_station", help="到达站")
    date_grp = search_p.add_mutually_exclusive_group()
    date_grp.add_argument("--date", "-d", help="日期 YYYY-MM-DD")
    date_grp.add_argument("--today", action="store_true", help="今天")
    date_grp.add_argument("--tomorrow", action="store_true", help="明天")

    # ── schedule ────────────────────────────────────────────────
    sched_p = sub.add_parser(
        "schedule", aliases=["时刻", "sched"],
        help="查时刻 / Query train schedule & stops",
    )
    sched_p.add_argument("train", help="车次号 (如 G119)")
    sched_p.add_argument("--from", dest="from_station", default=None,
                         help="出发站 (可选，用于确定始发站)")
    sched_p.add_argument("--to", dest="to_station", default=None,
                         help="到达站 (可选)")
    date_grp2 = sched_p.add_mutually_exclusive_group()
    date_grp2.add_argument("--date", "-d", help="日期 YYYY-MM-DD")
    date_grp2.add_argument("--today", action="store_true", help="今天")

    # ── stations ────────────────────────────────────────────────
    st_p = sub.add_parser(
        "stations", aliases=["站"],
        help="查车站 / Search stations by name or pinyin",
    )
    st_p.add_argument("query", nargs="?", default="", help="搜索关键词")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        client = TrainClient()
        stations = Stations()

        if args.command in ("search", "s", "查"):
            return _cmd_search(client, stations, args)
        elif args.command in ("schedule", "时刻", "sched"):
            return _cmd_schedule(client, stations, args)
        elif args.command in ("stations", "站"):
            return _cmd_stations(stations, args)
        else:
            parser.print_help()
            return 1

    except TrainError as exc:
        print(f"\n{Style.RED}Error: {exc}{Style.RESET}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print()
        return 1


def _resolve_date(args) -> str:
    if args.date:
        return args.date
    if args.today:
        return date.today().isoformat()
    if getattr(args, "tomorrow", False):
        return (date.today() + timedelta(days=1)).isoformat()
    return (date.today() + timedelta(days=1)).isoformat()  # default: tomorrow


def _cmd_search(client: TrainClient, stations: Stations, args) -> int:
    dt = _resolve_date(args)

    from_code = stations.resolve(args.from_station)
    to_code = stations.resolve(args.to_station)

    if not from_code:
        print(f"{Style.RED}Unknown station: {args.from_station}{Style.RESET}",
              file=sys.stderr)
        _suggest(stations, args.from_station)
        return 1
    if not to_code:
        print(f"{Style.RED}Unknown station: {args.to_station}{Style.RESET}",
              file=sys.stderr)
        _suggest(stations, args.to_station)
        return 1

    result = client.search(from_code, to_code, dt)
    print(display_search(result))
    return 0


def _cmd_schedule(client: TrainClient, stations: Stations, args) -> int:
    dt = _resolve_date(args)

    train_code = args.train.upper()

    # We need from_station/to_station for the schedule API.
    # If user didn't provide them, we first search today to find the train.
    if not args.from_station or not args.to_station:
        # Try a broad search — we need at least the start/end stations
        print(f"{Style.DIM}Auto-detecting route for {train_code}…{Style.RESET}",
              file=sys.stderr)
    else:
        from_code = stations.resolve(args.from_station)
        to_code = stations.resolve(args.to_station)
        if not from_code or not to_code:
            print(f"{Style.RED}Could not resolve station.{Style.RESET}",
                  file=sys.stderr)
            return 1

        # Search for this train number across a short date range
        for try_date in [dt, (date.fromisoformat(dt) - timedelta(days=1)).isoformat()]:
            try:
                result = client.search(from_code, to_code, try_date)
                train = result.by_code(train_code)
                if train:
                    # Found — parse train_no, from_code, to_code from result
                    stops = client.schedule(
                        train.train_no,
                        train.from_code,
                        train.to_code,
                        try_date,
                    )
                    print(display_schedule(stops, train_code=train_code))
                    return 0
            except TrainError:
                continue

        print(f"{Style.RED}Could not find schedule for {train_code}{Style.RESET}",
              file=sys.stderr)
        return 1

    return 1


def _cmd_stations(stations: Stations, args) -> int:
    if not args.query:
        print(f"\n{Style.BOLD}Cached stations:{Style.RESET} {len(stations.codes)}")
        print(f"{Style.DIM}Use 'tt stations <keyword>' to search.{Style.RESET}")
        return 0

    results = stations.search(args.query)
    print(display_stations(results))
    return 0


def _suggest(stations: Stations, text: str) -> None:
    suggestions = stations.suggest(text)
    if suggestions:
        print(
            f"{Style.YELLOW}Did you mean?{Style.RESET} "
            f"{', '.join(suggestions[:5])}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    sys.exit(main())
