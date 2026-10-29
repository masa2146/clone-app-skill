# Google Play store listing and promotional asset rules (games)

All pages read 2026-10-27. Help Center pages carry no "last updated" date (footer only "(c)2026 Google").
Developer Program Policy read is the version "effective September 30, 2026".
Tags: [REQ] = Google calls it a requirement ("failure to meet requirements may result in removal or suspension"),
[REC] = "Highly recommended" (does not block the listing, but limits promotion/recommendation),
[UNOFFICIAL] = third-party source, [UNCERTAIN] = official pages conflict or are silent.
Note: play.google.com/console/about/* now 301-redirects to google.play/business/* (Google-owned marketing pages).

Key URLs (short names used below):
- PA = https://support.google.com/googleplay/android-developer/answer/9866151 (Add preview assets)
- MD = https://support.google.com/googleplay/android-developer/answer/9898842 (Metadata policy)
- BP = https://support.google.com/googleplay/android-developer/answer/13393723 (Best practices for store listing)
- SU = https://support.google.com/googleplay/android-developer/answer/9859152 (Create and set up your app)
- DPP = https://support.google.com/googleplay/android-developer/answer/18258653 (Developer Program Policy, eff. 2026-09-30)

## 1. Icon, feature graphic, screenshots

### App icon
- [REQ] 512 x 512 px, 32-bit PNG with alpha, max 1024 KB. — PA
- [REQ] sRGB; full square, do NOT pre-round corners (Play applies mask, radius = 30% of size); no drop shadow (Play adds it). — https://developer.android.com/distribute/google-play/resources/icon-design-specifications
- [REQ] Icon must not use text/graphics that indicate ranking, promote deals/incentivise installs, indicate a Play program, or mislead. — same URL
- [REQ] No misleading symbols (e.g. fake new-message dot, download/install arrow when app isn't about downloading). — MD, DPP
- [REQ] No emojis, emoticons, repeated special characters; no ALL CAPS unless brand. Applies to title, icon, developer name. — MD
- [REQ] Must not resemble an existing product's icon so users could download the wrong app. — BP; DPP (Impersonation)
- [REC] Avoid transparency (transparent areas show Play UI background); use keyline grid for logos, full-bleed for illustrations. — icon spec URL
- [REC] Match style/colours of the other graphics. — BP
- Legacy icons not on the new spec are shrunk to 75% (384 px) of the keyline grid. — icon spec URL

### Feature graphic
- [REQ] Required to publish. 1024 x 500 px, JPEG or 24-bit PNG, NO alpha. — PA
- Used as cover image of the preview video (play button overlaid when video doesn't autoplay). — PA
- [REC] Keep logo, app name, slogan, main UI out of cutoff zones, focal point centred (zone sizes only shown in an image, no numbers in text). — PA
- [REC] Avoid pure white, black, dark grey backgrounds (blend into Play UI); avoid small details. — PA
- [REC] Don't just duplicate the app icon branding; minimise text; localise graphic and branding text. — PA, BP
- [REQ] No Google Play / other store badges, no device imagery, no unlicensed third-party trademarks. — PA
- [REC] Alt text <= 140 characters. — PA

### Phone screenshots
- [REQ] Minimum 2 screenshots (across device types) to publish; up to 8 per device type. — PA
- [REQ] JPEG or 24-bit PNG, no alpha; longest side 320..3840 px; longest side must not exceed 2x the shortest side. — PA
  - Consequence: 1080x2400 (20:9 = 2.22) is REJECTED; 1080x1920 (9:16 = 1.78) is fine. Derived arithmetic, not a quoted rule.
- [REC] Recommendation eligibility, GAMES: at least 3 screenshots in 9:16 portrait (min 1080 x 1920) or 16:9 landscape (min 1920 x 1080), showing the actual in-game experience. — PA
- [REC] (Apps, for comparison: 4 screenshots, min 1080 px, 16:9 or 9:16.) — PA
- [REC] Real in-game footage, not mockups; no people/fingers holding devices. — PA
- [REC] First 3 screenshots should prioritise UI/gameplay; stylised multi-image layouts allowed. — PA
- [REC] Taglines must not exceed 20% of the image; no small/cluttered text. — PA
- [REC] No blurry, stretched, pixelated, compressed, rotated or skewed images. — PA
- [REC] Status bar: remove notifications and carrier name, battery/Wi-Fi/signal full. — PA
- [REC] Alt text <= 140 characters, don't start with "photo of"/"image of". — PA
- [REC] Screenshots for every supported device type and orientation; text-bearing screenshots need one version per language. — BP

### Tablets / Chromebooks (large screens)
- [REC] Minimum 4 screenshots, each side 1080..7680 px, 16:9 landscape or 9:16 portrait; keep extra text out of the core experience. — PA
- Google Play Games on PC: game cards need a background and a logo set together; portrait-only games get black bars on PC. [UNCERTAIN, only seen in search snippet] — https://developer.android.com/games/playgames/graphics

## 2. Preview (promo) video

- [REQ] One YouTube video URL; not a playlist or channel URL; no extra parameters (e.g. timecodes). — PA
- [REQ] Public or Unlisted (not Private). — PA
- [REQ] Ads disabled: monetisation off, or a video with no monetisation claims (copyright claims can still trigger ads, e.g. claimed music). — PA
- [REQ] Not age-restricted; must be embeddable. — PA
- Embedding is a YouTube Studio setting: Content > Details > Show more > "Allow embedding". Age-restricted videos can't be watched on most third-party sites. — https://support.google.com/youtube/answer/171780
- [REC] Actual gameplay within the first 10 seconds; at least 80% of the video is real user experience; limit title screens, logos, cutscenes. — PA
  - So motion-graphics intros are allowed but must be short; a video that is mostly animated title cards fails the 80% guidance.
- [REC] Keep it short: only the first 30 s autoplay. No official max length for the store preview video. — PA
- [REC] Landscape OR portrait, whichever fits the game; no black bars on a portrait video. — PA
- [REC] Localised versions (UI, taglines, audio); captions; on-screen copy readable and long enough to read, since autoplay is muted. — PA
- Autoplay: inline, muted, up to 30 s, depending on device, settings, network. — PA
- Order: video is shown before screenshots; feature graphic is its cover. May also appear on Home and Search. — PA
- Video is optional for apps, but "Your game requires a preview video to be shown in certain parts of Google Play" (large-format game sections). — PA
- [REC] Same content rules as stills: no ranking/price/CTA words; "Best Of" Google Play awards are the one exception allowed in video copy. — PA
- Separate feature "YouTube videos" (Grow users > Store presence > YouTube videos): Premium growth tools only; games may link several channels/playlists; videos must be public, owned, non-monetised, embeddable, not live, < 30 min; games: uploaded in last 90 days (store listing) / 21 days (Games tab). — https://support.google.com/googleplay/android-developer/answer/15501235
- "Full-screen portrait/vertical videos" are advertised on the store listings marketing page; no spec page found. [UNCERTAIN] — https://google.play/business/storelistings/
- [UNOFFICIAL, older advice] 30 s - 2 min length; not found on any current Google page.

## 3. Text

- [REQ] App name <= 30 chars; short description <= 80; full description <= 4000 (same limit for full-width and half-width characters). — SU
- [REQ] Repetitive or irrelevant keywords in name/short/full description can lead to suspension. — SU
- [REQ] No store performance/ranking claims: "App of the year", "#1", "Best of Play 20XX", "Popular", award icons. — MD, DPP
- [REQ] No price/promotional claims: "10% off", "$50 cash back", "free for limited time only". — MD, DPP
- [REQ] No references to Play programs: "Editor's choice", "New". — MD, DPP
- [REQ] Title/developer name: no "Free", "No Ads" deal words; no emojis/emoticons/kaomoji/repeated special chars; no ALL CAPS unless brand. — BP, MD
- [REQ] Graphics too: no "Best", "#1", "Top", "New", "Free", "Discount", "Sale", "Million Downloads". — PA
- [REQ] No calls to action in assets ("Download now", "Try now"). — PA
- [REQ] No unattributed/anonymous testimonials; no data comparisons with other apps/brands; no word blocks or vertical/horizontal keyword lists; no deceptive superlatives ("best game ever"). — MD, BP
- [REQ] No profane/vulgar language; no celebrity name or brand logo without permission. — MD
- [REC] Full description: don't repeat the short description verbatim; facts over hype; first sentences matter most. — BP
- [REC] Avoid time-sensitive copy; swap seasonal content promptly. — PA
- Localisation: metadata policy applies to every translation; untranslated languages may get an automatic Google Translate version or the default language. — BP, SU
- Localised graphics are shown when the user's language matches an added language. — SU
- [REQ] Listing must not appeal to children (cartoon characters, young-looking animation) unless child age groups are declared in Target audience; otherwise remove those elements. — BP

## 4. Misleading content, IP, AI labelling

- [REQ] No false or misleading info "in the description, title, icon, and screenshots"; example: a puzzle game shown as a racing game in screenshots. — DPP (Misleading Claims); https://support.google.com/googleplay/android-developer/answer/9888077
- [REQ] "Accurate disclosure, description and images/video of their functionality in all parts of the metadata"; features that vary by device/region must be disclosed prominently. — https://support.google.com/googleplay/android-developer/answer/9888077
- [REQ] Don't mimic OS/other-app warnings or notifications (fake system UI). — same URL
- [REQ] Screenshots and videos should reflect the app's actual experience; promo images/videos suitable for a general audience; no prominent graphic violence, sexual content, drug use. — MD
- [REQ] No copyrighted characters/artwork without authorisation, incl. "marketing images from ... video games" and "fan art indistinguishable from the original". — https://support.google.com/googleplay/android-developer/answer/9888072
- [REQ] No other parties' trademarks/logos/brand names without permission; with written permission, contact Play before submitting. — same URL
- [REQ] Titles/icons so similar to existing products that users may be misled are Impersonation. — DPP
- [REQ] Developer's own ads must not be deceptive or sexually explicit when driving users to the listing; developer is responsible for ad networks/affiliates. — DPP (App Promotion)
- [REQ] Ads shown in-app must not be significantly more mature than the app. — DPP (Content Ratings)
- [REQ] AI labelling: "You must provide a self-declaration for any submitted assets"; each asset declared on its own merits via a checkbox in Store listings and Promotional content flows (also editable in Asset Library). Scope: "Images and videos used in your Store listings, Promotional content, YouTube videos etc." Declared assets are shown AI-labelled on Play. Page does not define AI-assisted vs AI-generated, regions or penalties. — https://support.google.com/googleplay/android-developer/answer/17262077
- [UNOFFICIAL] Labels reportedly visible to EU users first (Play Store v52.3, July 2026). — https://deesu.org/blog/google-play-ai-labeling-asset-declaration-requirements
- The AI-Generated Content policy itself covers apps that generate AI content (in-app reporting), not marketing assets. — https://support.google.com/googleplay/android-developer/answer/13985936
- July 15, 2026 policy announcement: no store-listing/metadata changes. — https://support.google.com/googleplay/android-developer/answer/17134731

## 5. Store listing experiments

- Eligibility: published apps; runs on default AND custom store listings; listing must be fully rolled out first. — https://support.google.com/googleplay/android-developer/answer/6227309
- Default graphics experiment: icon, feature graphic, screenshots, default language only; 1 at a time per app; users with a localised-graphics language are excluded. — same URL
- Localized experiment: icon, feature graphic, screenshots and/or descriptions, up to 5 languages; up to 5 localized experiments in parallel (+1 default graphics). — same URL; https://support.google.com/googleplay/android-developer/answer/12053285
- App name and preview video are not listed as testable in the Help Center. [UNCERTAIN: google.play/business page names "icons, videos, and screenshots"] — https://google.play/business/store-listing-experiments/
- Variants: up to 2 against the current listing; recommended one asset change per experiment. — 6227309
- Audience: "experiment audience percentage" of visitors sees a variant; split equally among variants; no default stated. — 6227309
- Target metric (current Help Center): unique user install clicks / open clicks / pre-registration clicks; installs counted only for users without the app on any other device. — 6227309
- [UNCERTAIN] Older docs and third-party guides use "first-time installers" and "retained first-time installers (1 day)"; marketing page still reports acquisition rate and 1-day retention per variant. — https://google.play/business/store-listing-experiments/
- Settings: minimum detectable effect (smaller difference = "draw") and confidence level; no defaults published; defaults = fastest result with reasonable accuracy. — 6227309
- Duration: setup page estimates time and installs needed; no fixed minimum in Help Center; auto-stops after 6 months (traffic reverts, nothing applied). — 6227309
- [REC] Run at least a week (weekday vs weekend traffic). — https://google.play/business/store-listing-experiments/
- Results: winner/draw explained via confidence interval and MDE; "More data needed" state; console warns when a result is < 1 week away; "Apply" or "Keep current listing". — 6227309
- Minimum traffic: not published by Google. [UNOFFICIAL] low-traffic apps should prefer the non-retained metric for smaller samples. — https://www.apptweak.com/en/aso-blog/store-listing-experiments-a-guide-to-play-store-a-b-testing
- Experiment name <= 50 characters. — 6227309

## 6. Custom store listings and Promotional content

### Custom store listings — https://support.google.com/googleplay/android-developer/answer/9867158
- Up to 50; requires a published app with a default listing.
- Targeting: country/region (each country in only one custom listing), unique URL (`&listing=<param>`, lowercase/digits/.-_~), Google Ads traffic (AdMob only, not Play search ads), pre-registration, search keywords, churned/lapsed users (not for new apps), buyer states, custom audiences.
- Each listing needs: internal name (not editable later), targeting, default language, app name, short + full description, graphics; not auto-translated; store listing groups let listings inherit assets.
- Same metadata policy applies; experiments can run on custom listings (see 6227309).

### Promotional content (LiveOps)
- Eligibility: all games; apps only with Premium growth tools. Featuring requests, deep links, audience targeting need Premium growth tools (criteria not published). — https://support.google.com/googleplay/android-developer/answer/12932229
- Types: Offer (discount, value-add, free reward, sub trial; everyone or new users only), Time-limited event (competition/challenge, real-time, special), Major update (features, new content, pre-registration). — https://support.google.com/googleplay/android-developer/answer/12932541
- Surfaces: details page, Apps/Games tab, Events tab (games, 17 countries incl. Türkiye, US, UK), search. Content that fails quality review shows only on the details page. — https://support.google.com/googleplay/android-developer/answer/12929029 ; https://support.google.com/googleplay/android-developer/answer/12932123
- Must be new and noteworthy; evergreen/routine content and generic ongoing offers are rejected; no sweepstakes/tournaments as offers. — 12932123
- Timing: submit no earlier than 60 days and at least 4 days before start (review up to 4 days, usually < 24 h); with featuring request at least 14 days before; max run 4 weeks; time-limited events end within 30 days; major updates 28 days; pre-reg announcements 1 week; start > 24 h in future; preview up to 14 days before; all country-group start dates in one quarter. — 12932541, https://support.google.com/googleplay/android-developer/answer/12929944
- No two identical/very similar events live at once. — 12932229
- Primary image [REQ]: 1920 x 1080, 16:9, JPG or 24-bit PNG; safe zone 15% top / 10% sides / 20% bottom; no borders, no rounded corners; <= 1 MB for Spotlight. — 12929944
- Square image required; size not stated officially. [UNOFFICIAL] detail-page image 1080 x 1920 (9:16). — 12932541; https://asomobile.net/en/blog/promotional-content-on-google-play-2024/
- NO TEXT in images/animations: no logo, slogan, game name, event name, offer text ("50% off"); exceptions: collab partner logos, text that is part of a product. No fake buttons/toggles/CTA, no store badges. — 12929944, 12932541
- Animation (optional): Lottie JSON, 16:9, <= 200 KB, 60 fps, <= 6 s, seamless loop, safe zone 15% top / 20% sides / 20% bottom, static image required. — https://support.google.com/googleplay/android-developer/answer/16009268
- Video: landscape only, monetisation off, embeddable, localised; primary image required with it. [UNCERTAIN] 12929944 says public or unlisted, 12932541 says public. — 12929944, 12932541
- Tagline <= 80 chars (Spotlight: 48 single-byte / 23 double-byte); offer value in first 40 chars; no line breaks, no ellipsis, no CTA ("Play now"), no all caps. — 12929944, 12932123
- Description <= 500 chars (>= 100 recommended); no bullets; must not repeat the tagline in its first 40 chars; max one "!" or "?" in a row; em dash only. — 12929944, 12932123
- Localisation: users only see promos in languages provided; wrong-language text is a top rejection reason; local currency symbol for discounts. — 12929944, 12932541

## 7. Game-specific

- Games' recommendation formats need the 3 x 9:16 (or 16:9) >= 1080 px in-game screenshots and, for some sections, a preview video. — PA
- "Gameplay first": gameplay within 10 s, >= 80% real gameplay in the video; real footage, not mockups, in screenshots. — PA
- Featuring is quality-gated (core value, UX, technical quality, privacy); games judged on art, audio, controls, mechanics; titles over the bad-behaviour threshold aren't promoted on those devices; nomination form exists for premium sales. — https://google.play/business/guides/featuring/
- Play Games Services: display name and description should match the store listing; all PGS properties (description, category, graphics) required before PGS publish. — https://developer.android.com/games/pgs/console/setup
- Level Up (revamped): voluntary, enrolment from 2026-09-01; >= 10 achievements (40+ recommended), PC availability, 60 fps targets; promo content on the "You" tab is tied to Level Up [UNOFFICIAL for the You-tab claim]. — https://developer.android.com/games/guidelines
- Asset Library: one place to upload/reuse/crop/tag assets for main + custom listings, experiments, events; AI declaration editable there. — https://support.google.com/googleplay/android-developer/answer/16386748
