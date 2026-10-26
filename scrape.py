#!/usr/bin/env python3
"""Fetch today's IBJA gold/silver rates and append them to data/rates.json.

Gold is quoted per 10 g, silver per 1 kg (as shown on ibjarates.com).
Run:  python scrape.py            (live fetch)
      python scrape.py page.html  (parse a saved page, for testing)
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://www.ibjarates.com/index.html"
OUT = Path(__file__).parent / "data" / "rates.json"
IST = timezone(timedelta(hours=5, minutes=30))
ROWS = {"gold999": r"Gold\s*999", "gold995": r"Gold\s*995", "gold916": r"Gold\s*916",
        "gold750": r"Gold\s*750", "gold585": r"Gold\s*585", "silver999": r"Silver\s*999"}


def fetch() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (personal rate tracker)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " | ", html)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return re.sub(r"[\s|]+", " ", text)


def parse(html: str) -> dict:
    text = to_text(html)
    out = {}
    for key, label in ROWS.items():
        # "Gold 999 40735 40791" -> AM then PM (a missing PM shows as blank/-)
        m = re.search(label + r"\s+([\d,]+(?:\.\d+)?)\s*(?:([\d,]+(?:\.\d+)?))?", text)
        if not m:
            continue
        am = float(m.group(1).replace(",", ""))
        pm = float(m.group(2).replace(",", "")) if m.group(2) else None
        out[key] = {"am": am, "pm": pm}
    if "gold999" not in out or "silver999" not in out:
        raise RuntimeError("Could not find Gold 999 / Silver 999 rows - page layout may have changed")
    return out


def main() -> None:
    html = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else fetch()
    rates = parse(html)
    today = datetime.now(IST).strftime("%Y-%m-%d")
    history = json.loads(OUT.read_text()) if OUT.exists() else []
    entry = {"date": today, "fetchedAt": datetime.now(IST).isoformat(timespec="minutes"), "rates": rates}
    history = [h for h in history if h["date"] != today] + [entry]   # one row per day, latest wins
    history.sort(key=lambda h: h["date"])
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(history[-400:], indent=1))
    print(f"{today}: gold999={rates['gold999']} silver999={rates['silver999']}")


if __name__ == "__main__":
    main()
