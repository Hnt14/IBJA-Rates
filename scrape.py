#!/usr/bin/env python3
"""Fetch IBJA gold/silver rates and save them to data/rates.json.

ibjarates.com ships stale placeholder numbers in its raw HTML (e.g. Gold 999 = 40,735); the real
numbers are filled in by the page's JavaScript. So we open the page in a headless browser
(Playwright) and read what a person would see. Gold is per 10 g, silver per 1 kg.

It also reads the page's "Previous 30 days" tables, so the app has a month of history for its
graphs from the very first run.

Safety: refuses to save if the page's newest date is stale or the numbers look implausible, so
wrong data never reaches the app. On failure it prints what the browser saw, to help debugging.

Run:  python scrape.py            (live; needs: pip install playwright && playwright install chromium)
      python scrape.py page.html  (parse a saved page, for testing)
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

URL = "https://www.ibjarates.com/index.html"
OUT = Path(__file__).parent / "data" / "rates.json"
IST = timezone(timedelta(hours=5, minutes=30))
SCHEMA = 2          # rows without v=2 came from the old stale-reading scraper and are dropped
MAX_AGE_DAYS = 5
NUM = r"[\d,]+(?:\.\d+)?"
ROWS = {"gold999": r"Gold\s*999", "gold995": r"Gold\s*995", "gold916": r"Gold\s*916",
        "gold750": r"Gold\s*750", "gold585": r"Gold\s*585", "silver999": r"Silver\s*999"}
# column order of the "Previous Dates Rate" tables
HIST_KEYS = ["gold999", "gold995", "gold916", "gold750", "gold585", "silver999", "platinum999"]


def num(s: str) -> float:
    return float(s.replace(",", ""))


def live_text():
    from playwright.sync_api import sync_playwright
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent="Mozilla/5.0 (personal rate tracker)")
        page.on("response", lambda r: seen.append(f"{r.status} {r.request.resource_type} {r.url}")
                if r.request.resource_type in ("xhr", "fetch") else None)
        page.goto(URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(6000)              # let the page's scripts fill in the rates
        text = page.inner_text("body")
        browser.close()
    return collapse(text), seen


def collapse(text: str) -> str:
    return re.sub(r"[\s|]+", " ", text)


def html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return collapse(re.sub(r"(?s)<[^>]+>", " | ", html).replace("&nbsp;", " "))


def parse_today(text: str) -> dict:
    out = {}
    for key, label in ROWS.items():
        m = re.search(label + rf"\s+({NUM})\s*(?:({NUM}))?", text)
        if m:
            out[key] = {"am": num(m.group(1)), "pm": num(m.group(2)) if m.group(2) else None}
    if "gold999" not in out or "silver999" not in out:
        raise RuntimeError("Could not find Gold 999 / Silver 999 rows - page layout may have changed")
    return out


def parse_history(text: str) -> dict:
    """date -> rates, from the two 'Previous Dates Rate' tables (first = AM, second = PM)."""
    rows = re.findall(r"(\d{2})/(\d{2})/(\d{4})((?:\s+" + NUM + r"){7})", text)
    seen, days = {}, {}
    for d, m, y, rest in rows:
        try:
            date = datetime(int(y), int(m), int(d)).date().isoformat()
        except ValueError:
            continue
        vals = [num(v) for v in rest.split()]
        slot = "am" if date not in seen else "pm"
        if date in seen and slot == "pm" and "pm" in seen[date]:
            continue
        seen.setdefault(date, {})[slot] = vals
    for date, d in seen.items():
        if "am" not in d:
            continue
        rates = {}
        for i, key in enumerate(HIST_KEYS[:6]):
            rates[key] = {"am": d["am"][i], "pm": d["pm"][i] if "pm" in d else None}
        if plausible(rates):
            days[date] = rates
    return days


def plausible(rates: dict) -> bool:
    try:
        return 30 <= rates["gold999"]["am"] * 100 / rates["silver999"]["am"] <= 150
    except (KeyError, ZeroDivisionError):
        return False


def newest_date(text: str):
    ds = []
    for d, m, y in re.findall(r"\b(\d{2})/(\d{2})/(\d{4})\b", text):
        try:
            ds.append(datetime(int(y), int(m), int(d)).date())
        except ValueError:
            pass
    return max(ds) if ds else None


def main() -> None:
    seen = []
    if len(sys.argv) > 1:
        text = html_to_text(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        text, seen = live_text()
    try:
        today_rates = parse_today(text)
        latest = newest_date(text)
        now = datetime.now(IST).date()
        if latest is None:
            raise RuntimeError("No date found on the page - refusing to save")
        if (now - latest).days > MAX_AGE_DAYS:
            raise RuntimeError(f"Page's newest date is {latest} (today {now}): page still shows stale data - refusing to save")
        if not plausible(today_rates):
            raise RuntimeError(f"Implausible numbers {today_rates['gold999']} / {today_rates['silver999']} - refusing to save")
    except RuntimeError:
        i = text.find("Gold 999")
        print("---- what the browser saw (around 'Gold 999') ----")
        print(text[max(0, i - 200): i + 1200] if i >= 0 else text[:1500])
        print("---- background requests ----")
        print("\n".join(seen[:25]) or "(none)")
        raise

    by_date = {}
    old = json.loads(OUT.read_text()) if OUT.exists() else []
    for h in old:
        if h.get("v") == SCHEMA:
            by_date[h["date"]] = h
    stamp = datetime.now(IST).isoformat(timespec="minutes")
    for date, rates in parse_history(text).items():          # 30-day backfill
        by_date[date] = {"v": SCHEMA, "date": date, "fetchedAt": stamp, "rates": rates}
    by_date[latest.isoformat()] = {"v": SCHEMA, "date": latest.isoformat(), "fetchedAt": stamp, "rates": today_rates}

    history = sorted(by_date.values(), key=lambda h: h["date"])[-400:]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(history, indent=1))
    print(f"{latest}: gold999={today_rates['gold999']} silver999={today_rates['silver999']}  ({len(history)} days saved)")


if __name__ == "__main__":
    main()
