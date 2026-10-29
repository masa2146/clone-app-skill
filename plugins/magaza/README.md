# magaza

Google Play store listing for a game that is going to ship. The last stage after
`market-research → clone-app → clone-build` (or after an original game is built).

- `rakip.py` — competitor store pages in every target language → keyword and structure table.
- `denetle.py` — Play-policy checks: text limits, banned words per language, keyword stuffing,
  phrases copied from competitors, missing glyphs, image sizes/ratio/alpha/text area, trailer
  gameplay share.
- `gorsel.py` — screenshots and feature graphics in three styles (serit, panorama, odak) for
  every language.
- `fragman.py` — trailer with animated cards, transitions and per-language captions; full and
  short cut.
- `sayfa.py` — review page: language × style as Play shows it.

Rules and sources: `skills/magaza/reference/play-kurallari.md`.

## Tests
```bash
bash plugins/magaza/tests/run-all.sh
```
Needs Pillow, fontTools and ffmpeg; no network.
