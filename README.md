<div align="center">

# traintimes 🚄

**查火车票·查时刻 — 12306 CLI/SDK from the terminal.**

[![Python versions](https://img.shields.io/badge/python-3.9%2B-blue)](https://pypi.org/project/traintimes)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/wy67576/traintimes?style=social)](https://github.com/wy67576/traintimes)

```bash
pip install traintimes
tt search 北京 上海 --tomorrow
tt schedule G21 --date 2026-06-15
```

</div>

---

## Demo

```
$ tt search 北京 上海 --tomorrow

━━━━━━━━━━━━━━━━━━━━━━ TICKET AVAILABILITY ━━━━━━━━━━━━━━━━━━━━━━━━
       车次   出发 → 到达          出发   到达   历时  座次
────────────────────────────────────────────────────────────────────
    🚄 G1      北京南 → 上海虹桥    09:00 13:28 04:28  二等座:有 一等座:有 商务座:12
    🚄 G5      北京南 → 上海虹桥    09:24 14:08 04:44  二等座:有 一等座:有 商务座:9
    🚄 G9      北京南 → 上海虹桥    09:58 14:23 04:25  二等座:有 一等座:有 商务座:17
    🚄 G11     北京南 → 上海虹桥    10:03 14:39 04:36  二等座:有 一等座:有 商务座:2
    ... (54 trains)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
54 train(s) found: 北京 → 上海 2026-06-01
```

```
$ tt schedule G21

━━━━━━━━━━━━━━━━ G21 SCHEDULE ━━━━━━━━━━━━━━━━
 站序    站名    到达      出发     停靠
────────────────────────────────────────────
 ●   1   北京南    ----    15:00
 ○   2   济南西  16:23    16:25   2分钟
 ○   3   南京南  18:24    18:26   2分钟
 ○   4   常州北  18:56    18:58   2分钟
 ■   5  上海虹桥  19:34     ----
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5 stop(s)
```

## Why?

12306.cn is the only way to check Chinese train schedules and ticket availability. But every query requires:

1. Open the browser
2. Navigate through forms
3. Type station names
4. Manually parse the table
5. Refresh to see changes

**`traintimes` changes that.** One command → train schedule + ticket availability with live data from 12306 official APIs.

## Features

- **CLI mode** — search tickets, check schedules with one command
- **Python SDK** — `TrainClient` class for programmatic access
- **Smart station lookup** — type `北京`, `beijing`, `bj`, `BJP` — it just works
- **Colorful terminal output** — emoji trains, color-coded seat availability
- **Zero GUI** — works headless, perfect for scripts and automation
- **No login required** — read-only public APIs, no account needed

## Quick start

### Install

```bash
pip install traintimes
```

### Search tickets

```bash
tt search 北京 上海 --date 2026-06-15

# Or use shortcuts:
tt search 北京 上海 --today
tt search 北京 上海 --tomorrow

# Station names are flexible:
tt search bj sh --tomorrow          # pinyin
tt search 北京南 上海虹桥 --tomorrow  # full name
```

### Check schedule

```bash
tt schedule G21 --date 2026-06-15
tt schedule G1  --today
```

### Search stations

```bash
tt stations 虹桥
tt stations beijing
```

## Usage

### CLI

```bash
# Search tickets
tt search <from> <to> [--date DATE | --today | --tomorrow]

# Schedule (stops × times)
tt schedule <train> [--date DATE]

# Station lookup
tt stations <keyword>
```

### Python SDK

```python
from traintimes import TrainClient, Stations

client = TrainClient()
stations = Stations()

# Search ticket availability
result = client.search_with_names("北京", "上海", "2026-06-15")

for train in result.trains:
    print(f"{train.train_code} {train.depart_time}→{train.arrive_time}")

# Get full schedule
train = result.by_code("G21")
stops = client.schedule(
    train.train_no,
    train.from_code,
    train.to_code,
    "2026-06-15",
)
for stop in stops:
    print(f"{stop.station_name} {stop.arrive_time}→{stop.depart_time}")
```

### Script: Monitor ticket availability

```python
from traintimes import TrainClient, Stations
import time

client = TrainClient()
stations = Stations()

while True:
    result = client.search_with_names("北京", "上海", "2026-06-15")
    g1 = result.by_code("G1")
    if g1:
        seats = g1.seat_types.get("商务座", "?")
        print(f"G1 商务座: {seats}")
    time.sleep(60)
```

## Data source

This project uses the **official 12306.cn public query APIs** — the same endpoints the official website and mobile app use. All queries are read-only:

- `/otn/leftTicket/queryX` — ticket availability
- `/otn/czxx/queryByTrainNo` — schedule/timetable
- `/otn/resources/js/framework/station_name.js` — station dictionary

No login, no ticket purchasing, no captcha.

## What traintimes does NOT do

- ❌ No ticket purchasing / booking
- ❌ No automated scalping
- ❌ No captcha solving
- ❌ No login / authentication

## License

MIT
