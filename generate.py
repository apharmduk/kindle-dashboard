#!/usr/bin/env python3
"""Generate a Kindle-Paperwhite-friendly dashboard page (Leeds weather + HKD FX rates).

Data sources:
  - UK Met Office Weather DataHub, Global Spot site-specific (hourly + daily),
    key passed via METOFFICE_API_KEY env var (GitHub Actions secret at runtime).
  - Frankfurter (ECB-based) FX rates, no key needed.

If METOFFICE_API_KEY is unset, falls back to mock_*.json in this directory
(local testing only; mock files are not pushed to the repo).
"""
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LAT, LON = 53.796, -1.548  # Leeds city centre
TZ = ZoneInfo("Europe/London")
BASE = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point"
HERE = os.path.dirname(os.path.abspath(__file__))

WX = {
    0: "晴夜", 1: "晴朗", 2: "多雲夜", 3: "間中有雲",
    5: "薄霧", 6: "濃霧", 7: "多雲", 8: "陰天",
    9: "夜間驟雨", 10: "驟雨", 11: "毛毛雨", 12: "微雨",
    13: "夜間大驟雨", 14: "大驟雨", 15: "大雨",
    16: "夜間雨夾雪", 17: "雨夾雪", 18: "雨夾雪",
    19: "夜間冰雹", 20: "冰雹", 21: "冰雹",
    22: "夜間小雪", 23: "小雪", 24: "小雪",
    25: "夜間大雪", 26: "大雪", 27: "大雪",
    28: "夜間雷暴", 29: "雷暴", 30: "雷暴",
}
WEEKDAY = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


def wx_text(code):
    try:
        return WX.get(int(code), "-")
    except (TypeError, ValueError):
        return "-"


UA = {"User-Agent": "kindle-dashboard/1.0 (+personal use)", "Accept": "application/json"}


def fetch_json(url, headers=None, timeout=30):
    h = dict(UA)
    h.update(headers or {})
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def metoffice(endpoint):
    key = os.environ.get("METOFFICE_API_KEY", "").strip()
    if not key:
        with open(os.path.join(HERE, "mock_%s.json" % endpoint)) as f:
            doc = json.load(f)
    else:
        url = ("%s/%s?latitude=%s&longitude=%s&includeLocationName=true"
               % (BASE, endpoint, LAT, LON))
        doc = fetch_json(url, headers={"apikey": key, "Accept": "application/json"})
    props = doc["features"][0]["properties"]
    return props.get("timeSeries", [])


def get_fx():
    # Primary: Frankfurter (ECB reference rates). Fallback: open.er-api.com.
    try:
        doc = fetch_json("https://api.frankfurter.app/latest?base=HKD&symbols=GBP,JPY,EUR")
        r = doc["rates"]
        return {
            "date": doc.get("date", ""),
            "gbp": 1.0 / r["GBP"],       # HKD per 1 GBP
            "eur": 1.0 / r["EUR"],       # HKD per 1 EUR
            "jpy100": 100.0 / r["JPY"],  # HKD per 100 JPY
        }
    except Exception as e:
        print("frankfurter failed (%s), trying er-api" % e, file=sys.stderr)
    doc = fetch_json("https://open.er-api.com/v6/latest/HKD")
    r = doc["rates"]
    return {
        "date": doc.get("time_last_update_utc", "")[:16],
        "gbp": 1.0 / r["GBP"],
        "eur": 1.0 / r["EUR"],
        "jpy100": 100.0 / r["JPY"],
    }


def parse_time(s):
    # ISO-8601, DataHub uses Zulu
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ)


def wind_kmh(value, unit):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "-"
    u = (unit or "").lower()
    if "mph" in u or "mile" in u:
        return str(round(v * 1.60934))
    return str(round(v * 3.6))  # default m/s


def esc_num(v, nd=0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "-"
    if nd:
        s = "%.*f" % (nd, f)
        return s.rstrip("0").rstrip(".")
    return str(int(round(f)))


def render(now, hourly, daily, fx):
    today = now.date()
    # current: latest hourly step at or before now
    cur = None
    for e in hourly:
        if parse_time(e["time"]) <= now:
            cur = e
    # today's remaining hourly rows
    hour0 = now.replace(minute=0, second=0, microsecond=0)
    rows = [e for e in hourly
            if parse_time(e["time"]).date() == today and parse_time(e["time"]) >= hour0]
    days = [d for d in daily
            if "daySignificantWeatherCode" in d
            and parse_time(d["time"]).date() >= today][:5]

    p = []
    A = p.append
    A("<!DOCTYPE html>")
    A('<html lang="zh-Hant"><head>')
    A('<meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width, initial-scale=1">')
    A('<meta http-equiv="refresh" content="3600">')
    A("<title>Leeds 天氣＋滙率</title>")
    A("<style>")
    A("body{font-family:sans-serif;color:#000;background:#fff;margin:0;padding:16px;font-size:22px;line-height:1.4;}")
    A("h1{font-size:40px;margin:0 0 4px 0;}")
    A("h2{font-size:30px;margin:28px 0 8px 0;border-bottom:3px solid #000;padding-bottom:4px;}")
    A(".updated{font-size:18px;margin:0 0 8px 0;}")
    A(".bignum{font-size:72px;font-weight:bold;margin:8px 0;}")
    A(".cond{font-size:30px;font-weight:bold;}")
    A(".meta{font-size:20px;}")
    A("table{width:100%;border-collapse:collapse;margin-top:8px;}")
    A("th,td{border:2px solid #000;padding:10px 8px;text-align:center;font-size:22px;}")
    A("th{font-size:20px;}")
    A(".foot{font-size:16px;margin-top:28px;border-top:2px solid #000;padding-top:8px;}")
    A("a{color:#000;}")
    A("</style></head><body>")

    A("<h1>Leeds 天氣</h1>")
    A("<p class=\"updated\">更新時間：%d年%d月%d日 %02d:%02d（%s）</p>" % (
        now.year, now.month, now.day, now.hour, now.minute,
        "BST" if now.dst() else "GMT"))

    if cur is None:
        A("<h2>即時天氣</h2><p>天氣數據首次更新中，請稍後再試。</p>")
    else:
        A("<h2>即時天氣</h2>")
        A("<div class=\"bignum\">%s°C</div>" % esc_num(cur.get("screenTemperature")))
        A("<div class=\"cond\">%s</div>" % wx_text(cur.get("significantWeatherCode")))
        A("<p class=\"meta\">體感 %s°C　濕度 %s%%　降雨機率 %s%%　風速 %s km/h</p>" % (
            esc_num(cur.get("feelsLikeTemperature")),
            esc_num(cur.get("screenRelativeHumidity")),
            esc_num(cur.get("probOfPrecipitation")),
            wind_kmh(cur.get("windSpeed10m"), None)))

        A("<h2>今日逐小時（%d月%d日 %s）</h2>" % (now.month, now.day, WEEKDAY[now.weekday()]))
        A("<table><tr><th>時間</th><th>天氣</th><th>溫度</th><th>降雨機率</th></tr>")
        for e in rows:
            t = parse_time(e["time"])
            A("<tr><td>%02d:00</td><td>%s</td><td>%s°C</td><td>%s%%</td></tr>" % (
                t.hour, wx_text(e.get("significantWeatherCode")),
                esc_num(e.get("screenTemperature")), esc_num(e.get("probOfPrecipitation"))))
        A("</table>")

        if days:
            A("<h2>未來5日</h2>")
            A("<table><tr><th>日期</th><th>日間</th><th>夜間</th><th>最高</th><th>最低</th></tr>")
            for d in days:
                t = parse_time(d["time"])
                A("<tr><td>%d/%d<br>%s</td><td>%s</td><td>%s</td><td>%s°C</td><td>%s°C</td></tr>" % (
                    t.month, t.day, WEEKDAY[t.weekday()],
                    wx_text(d.get("daySignificantWeatherCode")),
                    wx_text(d.get("nightSignificantWeatherCode")),
                    esc_num(d.get("dayMaxScreenTemperature")), esc_num(d.get("nightMinScreenTemperature"))))
            A("</table>")

    A("<h2>港元滙率</h2>")
    A("<table>")
    A("<tr><th>貨幣</th><th>滙率</th></tr>")
    A("<tr><td>英鎊 GBP</td><td>1 GBP = %.3f HKD</td></tr>" % fx["gbp"])
    A("<tr><td>歐元 EUR</td><td>1 EUR = %.3f HKD</td></tr>" % fx["eur"])
    A("<tr><td>日圓 JPY</td><td>100 JPY = %.2f HKD</td></tr>" % fx["jpy100"])
    A("</table>")
    A("<p class=\"meta\">滙率日期：%s（Frankfurter／歐洲央行參考價）</p>" % fx["date"])

    A("<p class=\"foot\">天氣數據：UK Met Office　滙率：Frankfurter　每小時自動更新<br>")
    A("<a href=\"\">撳呢度即時重新整理</a></p>")
    A("</body></html>")
    return "\n".join(p)


def main():
    now = datetime.now(TZ)
    key = os.environ.get("METOFFICE_API_KEY", "").strip()
    try:
        hourly = metoffice("hourly")
    except Exception as e:
        print("hourly fetch failed: %s" % e, file=sys.stderr)
        hourly = []
    try:
        daily = metoffice("daily")
    except Exception as e:
        print("daily fetch failed: %s" % e, file=sys.stderr)
        daily = []
    try:
        fx = get_fx()
    except Exception as e:
        print("fx fetch failed: %s" % e, file=sys.stderr)
        sys.exit(1)
    if key and not hourly:
        print("weather fetch failed with real key; keeping previous page", file=sys.stderr)
        sys.exit(1)
    html = render(now, hourly, daily, fx)
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote index.html (%d bytes)" % len(html.encode("utf-8")))


if __name__ == "__main__":
    main()
