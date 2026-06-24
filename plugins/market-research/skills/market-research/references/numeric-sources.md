# Numeric Market-Data Sources (free, no API key)

Phase 2 uses this to turn "search the web" into "pull THESE numbers from THESE
places, and cite each." Prefer a real number with a source link over a vibe.
Every number that lands in the report carries the URL it came from.

## Sources & what to pull

| Source | Pull | How (free) |
|---|---|---|
| **Google Trends** | interest-over-time, % momentum, breakout/rising queries | `trends.py "<term>"`; on `{"ok":false}` fall back to WebSearch `google trends <term>`. |
| **play.google.com** | ranked Android packages, per-app installs/rating | `fetch-play-charts.py` for top/category charts; `play.py resolve` for per-app installs/rating. |
| **Sensor Tower (blog/reports)** | downloads, revenue, DAU, YoY growth | WebSearch `sensortower <category> revenue downloads 2026`; WebFetch the article; quote the figure + date. |
| **data.ai / Apptopia posts** | top-charts movement, market revenue | WebSearch `data.ai <category> market 2026`; WebFetch + cite. |
| **Statista (free public charts)** | market size $, user counts, CAGR | WebSearch `statista <category> market size`; use the visible free figure only; cite. |
| **SimilarWeb (free tier)** | incumbent web traffic, engagement | WebSearch `similarweb <incumbent domain>`; cite visits/engagement. |

## Query shaping (vary by the run's angles)

- Always bind a year: `... 2026` so figures are current.
- Bind a region when the angle is regional: `... <category> Brazil downloads`.
- For growth: `fastest growing <category> apps 2026`, `<category> market size 2026`.
- For incumbent weakness: `<incumbent> complaints reddit`, `<incumbent> alternative 2026`.

## Citation rule

Each extracted number is written as `<number> [<source>](<url>)` in the report.
A claim with no source link is downgraded to a qualitative note, not a number —
it must NOT be used to justify a numeric subscore (see scoring-guide.md).

## When a source is paywalled / JS-only

Do not scrape it. Use the figure only if it's visible free (article body, public
chart). Otherwise drop to the next source. Never invent a number to fill a gap.
