---
name: magaza
description: Use when preparing a game's Google Play store listing for release — store texts in many languages written from competitor research in our own words, screenshots and feature graphics in three distinct styles per language, an optional trailer with animated cards and transitions for YouTube, Play-policy checks, a review page to choose a style, and A/B variants for after release. Türkçe: mağaza girişi, mağaza görselleri, ekran görüntüleri, özellik grafiği, tanıtım videosu, fragman, açıklama yaz, çoklu dil, ASO, mağaza denemesi.
---

# Mağaza — store listing for a game that will ship

The listing is part of the release, not decoration after it. This skill assumes the project is
going to be published: it reads the game's name and package from `Docs/project.json` (written by
`/clone-build kur`) and closes the lifecycle task "Mağaza girişi" (T122) in `Docs/TASKS.md`.
If there is no `project.json`, ask for the name, the package and the target release date first.

Rules and their sources: `reference/play-kurallari.md` (read from Google's pages, with the
date). Banned words per language: `reference/diller.json`. Scripts:
`S=${CLAUDE_PLUGIN_ROOT}/skills/magaza/scripts` (Pillow, fontTools, ffmpeg).

## Who does what

The agent runs all of it: research, texts, images, trailer, the YouTube upload and every Play
Console form and upload, through a browser tool (gstack `/browse` when installed). The user only
does: login and two-step verification, legal declaration boxes, tax and payment, price approval,
the production release, deletions — and choosing the style on the review page.

## 1. Inputs (one plan file)

`Docs/store/magaza-plani.json` — start from `reference/plan-ornegi.json`. It holds the font, an
optional palette, up to 8 **real gameplay frames** (record them from the game; a mockup is
rejected), optional cut-out characters for the "odak" style, the logo, and per language the name,
short and full description, one caption per screenshot, the feature-graphic slogan, the trailer
captions and closing line.

For a clone: not one pixel of the original game's art, logo or name may appear. Play removes
listings with another game's marketing images, and the store images are the most visible place
for that mistake.

## 2. Competitor research

Pick 6–10 similar games (same genre, top of the category, the reference game if a clone):

```bash
python3 $S/rakip.py <pkg1> <pkg2> ... --diller tr-TR,en-US,de-DE,... --cikti Docs/store/rakip --gorseller
```

`rakip.md` lists per language each title's length, its first sentence, the screenshot count and
the words competitors share — the search vocabulary of that language. Take **structure and
keywords** from it: how long titles run, what the first line promises, which features they list,
how many frames show real gameplay. Write every sentence yourself.

## 3. Texts, in every language

Default languages (`diller.json` → `varsayilan`): en-US, tr-TR, de-DE, fr-FR, es-ES, es-419,
pt-BR, it-IT, ru-RU, ja-JP, ko-KR, id-ID. ar and hi need libraqm in Pillow (glyph shaping).
Do not translate word by word: write each language from that language's competitor keywords,
then back-translate into the user's language to check the meaning. Name ≤ 30, short ≤ 80, full ≤ 4000.

```bash
python3 $S/denetle.py metin --plan Docs/store/magaza-plani.json --rakip Docs/store/rakip/rakip.json
python3 $S/denetle.py glif  --plan Docs/store/magaza-plani.json
```

`metin` blocks banned words (ranking, price, "new", calls to action — per language), emoji and
all-caps names, keyword stuffing, comma keyword blocks, and any run of 6+ words (14+ characters
in Japanese/Korean) shared with a competitor. `glif` blocks a caption whose glyphs the chosen
font lacks — give that language its own font in `plan.fontlar` (e.g. a Noto CJK face).

## 4. Images: three styles

```bash
python3 $S/gorsel.py --plan Docs/store/magaza-plani.json --cikti captures/store
python3 $S/denetle.py gorsel captures/store/manifest.json
```

- **serit**: caption band on top, gameplay card below. The most readable; the category's common layout.
- **panorama**: the eight images make one continuous scene (a ribbon runs through all of them).
- **odak**: one big word, the frame as a tilted card, a magnified detail or the character
  breaking out of it. Stands out most in a crowded search result.

1080×1920 for phones (1080×2400 is rejected: long side over twice the short side), 1024×500
feature graphic, no alpha, text ≤ 20% of the image, the first three images show gameplay. The
palette comes from the plan or from the frames (deep dominant hue + bright accent; text colour
picked for contrast).

## 5. Trailer (optional, recommended for games)

```bash
python3 $S/fragman.py --plan Docs/store/magaza-plani.json --cikti captures/store/fragman
python3 $S/denetle.py video captures/store/fragman/fragman.json
```

A title card that zooms in, gameplay segments joined by rotating transitions (slide, zoom,
wipe, circle), one caption per segment in each language, a closing card with no call to action.
A full cut and a ≤ 15 s cut per language. Gameplay must start within 10 s and fill ≥ 80% of the
video; Play autoplays the first 30 s muted, so the captions carry the message.

YouTube (agent, in the browser): upload each language's full cut as **Unlisted**, monetisation
off, embedding allowed, not made for kids unless the target audience says so, no claimed music.
Put the plain watch URL (no playlist, no timestamp) into that language's listing.

## 6. Review page → the user chooses

```bash
python3 $S/sayfa.py captures/store/manifest.json --fragman captures/store/fragman/fragman.json \
  --plan Docs/store/magaza-plani.json --cikti captures/store/index.html
```

Every language × style as Play shows it (feature graphic then the strip) and the first three
images as a search result. Publish it as a multi-file artifact or open it locally, and ask one
question: which style goes to the default listing. Deliver with `teslim.py` when the project
has it.

## 7. Upload, then A/B

- Store listing per language: texts, the chosen style's 8 images and feature graphic, video URL,
  icon. Declare AI-generated assets one by one, honestly.
- After the listing is live: Play Console → Store listing experiments. Put the other two styles in
  as variants (default graphics experiment for the default language; localized experiments for up
  to 5 languages), one asset type per experiment, run at least a week, apply the winner.
- Record the final console screen in the delivery; mark T122 done only when the listing shows
  "ready to publish" (or is live).

## Errors

| Situation | Action |
|---|---|
| fewer than 3 gameplay frames | record more; never pad with mockups |
| `denetle` HATA | fix and rerun; never upload past a HATA |
| caption overflow at min size | shorten the caption in that language |
| glyphs missing | set `fontlar[<lang>]` to a font with that script |
| ar / hi without libraqm | drop the language or install Pillow with raqm |
| competitor page fails for one language | the table skips it; note the gap, continue |
