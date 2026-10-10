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


# Monochrome SVG weather icons (E-ink safe; emoji often missing on old Kindle browser)
_CLOUD = '<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z" fill="#fff"/>'
_ICONS = {
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.2 5.2l1.4 1.4M17.4 17.4l1.4 1.4M5.2 18.8l1.4-1.4M17.4 6.6l1.4-1.4"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" fill="#000" stroke="none"/>',
    "partly_day": ('<circle cx="7" cy="7" r="2.6"/><path d="M7 2.8v1.4M7 10.2v1.4M2.8 7h1.4M10.2 7h1.4"/>'
                   '<g transform="translate(3,5) scale(0.8)">' + _CLOUD + '</g>'),
    "partly_night": ('<g transform="translate(-3,-3) scale(0.75)"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" fill="#000" stroke="none"/></g>'
                     '<g transform="translate(3,5) scale(0.8)">' + _CLOUD + '</g>'),
    "cloud": _CLOUD,
    "fog": '<path d="M5 10h14M8 14h8M5 18h14"/>',
    "shower": '<g transform="translate(0,-4)">' + _CLOUD + '</g><path d="M8.5 17.5l-1.2 3M15.5 17.5l-1.2 3"/>',
    "rain": '<g transform="translate(0,-4)">' + _CLOUD + '</g><path d="M7.5 17.5l-1.2 3M12 17.5l-1.2 3M16.5 17.5l-1.2 3"/>',
    "heavy_rain": '<g transform="translate(0,-4)">' + _CLOUD + '</g><path d="M7.5 17l-1.2 4.5M12 17l-1.2 4.5M16.5 17l-1.2 4.5"/>',
    "sleet": ('<g transform="translate(0,-4)">' + _CLOUD + '</g><path d="M9 17.5l-1.2 3"/>'
              '<circle cx="14" cy="19.5" r="1.2" fill="#000" stroke="none"/>'
              '<circle cx="18" cy="18.5" r="1.2" fill="#000" stroke="none"/>'),
    "snow": ('<g transform="translate(0,-5)">' + _CLOUD + '</g>'
             '<g transform="translate(8,19.5)"><path d="M-2 0H2M-1-1.7L1 1.7M1-1.7L-1 1.7"/></g>'
             '<g transform="translate(12.5,20.5)"><path d="M-2 0H2M-1-1.7L1 1.7M1-1.7L-1 1.7"/></g>'
             '<g transform="translate(17,19.5)"><path d="M-2 0H2M-1-1.7L1 1.7M1-1.7L-1 1.7"/></g>'),
    "thunder": ('<g transform="translate(0,-2)">' + _CLOUD + '</g>'
                '<path d="M13 14l-4 6h3.5L11 23l5-6.5h-3.5z" fill="#000" stroke="none"/>'),
}


def wx_icon(code, size=20):
    try:
        c = int(code)
    except (TypeError, ValueError):
        c = -1
    if c == 0:
        name = "sun"
    elif c == 1:
        name = "moon"
    elif c == 2:
        name = "partly_day"
    elif c == 3:
        name = "partly_night"
    elif c in (5, 6):
        name = "fog"
    elif c in (7, 8):
        name = "cloud"
    elif c in (9, 10):
        name = "shower"
    elif c in (11, 12):
        name = "rain"
    elif c in (13, 14, 15):
        name = "heavy_rain"
    elif c in (16, 17, 18):
        name = "sleet"
    elif 19 <= c <= 27:
        name = "snow"
    elif c in (28, 29, 30):
        name = "thunder"
    else:
        name = "cloud"
    return ('<svg width="%d" height="%d" viewBox="0 0 24 24" fill="none" stroke="#000" '
            'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">%s</svg>'
            % (size, size, _ICONS[name]))


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
    A("body{font-family:sans-serif;color:#000;background:#fff;margin:0;padding:6px 8px;font-size:14px;line-height:1.3;}")
    A("h1{font-size:20px;margin:0 0 2px 0;}")
    A("h1 .updated{font-size:11px;font-weight:normal;}")
    A("h2{font-size:15px;margin:8px 0 3px 0;border-bottom:2px solid #000;padding-bottom:2px;}")
    A(".cur{margin:2px 0;}")
    A(".bignum{font-size:28px;font-weight:bold;}")
    A(".cond{font-size:16px;font-weight:bold;}")
    A(".meta{font-size:12px;margin:2px 0;}")
    A("table{width:100%;border-collapse:collapse;margin-top:3px;}")
    A("th,td{border:1px solid #000;padding:2px 3px;text-align:center;font-size:12px;}")
    A("th{font-size:11px;}")
    A("table.lt{margin-top:0;}")
    A("td.lc{border:0;vertical-align:top;padding:2px;}")
    A("svg{vertical-align:middle;}")
    A(".foot{font-size:10px;margin-top:8px;border-top:2px solid #000;padding-top:3px;}")
    A("a{color:#000;}")
    A("</style></head><body>")

    A("<h1>Leeds 天氣 <span class=\"updated\">更新：%d月%d日 %02d:%02d（%s）· v4</span></h1>" % (
        now.month, now.day, now.hour, now.minute, "BST" if now.dst() else "GMT"))

    fx_lines = []
    fx_lines.append("<h2>港元滙率</h2>")
    fx_lines.append("<table>")
    fx_lines.append("<tr><th>貨幣</th><th>滙率</th></tr>")
    fx_lines.append("<tr><td>英鎊 GBP</td><td>1 GBP = %.3f HKD</td></tr>" % fx["gbp"])
    fx_lines.append("<tr><td>歐元 EUR</td><td>1 EUR = %.3f HKD</td></tr>" % fx["eur"])
    fx_lines.append("<tr><td>日圓 JPY</td><td>100 JPY = %.2f HKD</td></tr>" % fx["jpy100"])
    fx_lines.append("</table>")
    fx_lines.append("<p class=\"meta\">滙率日期：%s（Frankfurter）</p>" % fx["date"])

    if cur is None:
        A("<p>天氣數據首次更新中，請稍後再試。</p>")
        for L in fx_lines:
            A(L)
    else:
        A("<div class=\"cur\"><span class=\"bignum\">%s°C</span> <span class=\"cond\">%s</span></div>" % (
            esc_num(cur.get("screenTemperature")), wx_text(cur.get("significantWeatherCode"))))
        A("<p class=\"meta\">體感 %s°C　濕度 %s%%　降雨機率 %s%%　風速 %s km/h</p>" % (
            esc_num(cur.get("feelsLikeTemperature")),
            esc_num(cur.get("screenRelativeHumidity")),
            esc_num(cur.get("probOfPrecipitation")),
            wind_kmh(cur.get("windSpeed10m"), None)))

        A("<h2>今日逐小時（%d月%d日 %s）</h2>" % (now.month, now.day, WEEKDAY[now.weekday()]))
        mid = (len(rows) + 1) // 2
        A("<table class=\"lt\"><tr>")
        for chunk in (rows[:mid], rows[mid:]):
            A("<td class=\"lc\" width=\"50%\" valign=\"top\"><table>")
            A("<tr><th>時間</th><th>天氣</th><th>溫度</th><th>降雨機率</th></tr>")
            for e in chunk:
                t = parse_time(e["time"])
                A("<tr><td>%02d:00</td><td>%s</td><td>%s°C</td><td>%s%%</td></tr>" % (
                    t.hour, wx_text(e.get("significantWeatherCode")),
                    esc_num(e.get("screenTemperature")), esc_num(e.get("probOfPrecipitation"))))
            A("</table></td>")
        A("</tr></table>")

        A("<table class=\"lt\"><tr><td class=\"lc\" width=\"50%\" valign=\"top\">")
        if days:
            A("<h2>未來5日</h2>")
            A("<table><tr><th>日期</th><th>日間</th><th>夜間</th><th>最高</th><th>最低</th></tr>")
            for d in days:
                t = parse_time(d["time"])
                A("<tr><td>%d/%d %s</td><td>%s</td><td>%s</td><td>%s°C</td><td>%s°C</td></tr>" % (
                    t.month, t.day, WEEKDAY[t.weekday()],
                    wx_text(d.get("daySignificantWeatherCode")),
                    wx_text(d.get("nightSignificantWeatherCode")),
                    esc_num(d.get("dayMaxScreenTemperature")), esc_num(d.get("nightMinScreenTemperature"))))
            A("</table>")
        A("</td><td class=\"lc\" width=\"50%\" valign=\"top\">")
        for L in fx_lines:
            A(L)
        A("</td></tr></table>")

    A("<p class=\"foot\">天氣：UK Met Office　滙率：Frankfurter　每小時自動更新 · v4<br>")
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
