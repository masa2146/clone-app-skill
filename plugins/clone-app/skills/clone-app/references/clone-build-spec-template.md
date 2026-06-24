# Clone Build Spec — {APP_TITLE}

> The standalone build contract. A fresh session with only this file and the
> `$WORK/` artifacts it references must be able to build a pixel-perfect,
> production-ready clone. Reference every artifact by **absolute path + summary**.

**Package:** {PACKAGE}  ·  **Date:** {DATE}  ·  **Selected stack:** {STACK}

## 1. Product overview & parity target
What the app does; the parity bar (pixel-perfect visual + feature-complete).

## 2. Design system
From `$WORK/design-tokens.json` (confidence: {…}): color palette + roles, type
scale (fonts + sizes), spacing scale, corner radii, light/dark theme. Note where
confidence is med/low and screenshots are the source of truth.

## 3. Screen-by-screen spec
For **each** screen: purpose · layout · components · states (empty/loading/error)
· navigation in/out · matching screenshot (`$WORK/screenshots/NN.png`).

## 4. Navigation map / IA
The full screen graph + entry points.

## 5. API contract
From `$WORK/payloads.json`: per endpoint — host, method, path, auth,
request body, response shape, headers.

## 6. Data model
Entities, fields, relationships (from payloads + RE digest).

## 7. Asset inventory
Icons, fonts, drawables — extract from `$WORK/output` or recreate. List each.

## 8. Acceptance criteria
Per screen and per flow — the testable definition of done for prod quality.

## 9. Out of scope / assumptions
Explicit exclusions and assumptions.

## 10. Artifact references
Absolute paths to: `design-tokens.json`, `design-digest.md`, `screenshots/`,
`payloads.json`, `re-digest.md` (+ `unity-digest.md`, `game-assets/` if Unity).

---

## Game variant (Unity)
Replace these sections:
- **§2 Design system** → art style + UI atlas inventory; palette from sprites.
- **§3 Screen-by-screen** → **scene/prefab-by-scene** spec (from `unity-digest.md`):
  each scene's objects, UI canvas, transitions; matching screenshot.
- **§5 API contract** → **netcode**: backend (Photon/PlayFab/Mirror/custom),
  message types, sync model (from the IL2CPP/Mono type model).
- **§7 Asset inventory** → `$WORK/game-assets/` manifest (sprites, atlases,
  audio, shaders, scenes, prefabs) + the AssetRipper project path.
