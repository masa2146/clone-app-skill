# Art pipeline — from "what should it look like" to pixels on the phone

Read this before the first task that changes what the player sees (T011, T013, T017, T018, T030, T060's
visual twin, T122 store art). It is the visual half of the two shipped clones' experience, and the half the
first version of this skill left out: two later games were built with it, both played correctly, and both
looked far below their references. In one, art was a single task, the agent recommended "generate it in
code", and soldiers became spheres with eyes, walls became textured boxes. Nobody showed the user a single
option before the meshes were in the game.

## 0. Hard rules

1. **Art is a phase with user gates, not a task.** The agent never marks a look approved by itself. A look
   is approved when the user picked it from a board, and the pick is a numbered line in `KARARLAR.md` with
   the board's full path.
2. **The asset-class table (§2) picks the tool.** It is decided once (T011) and not re-argued per object.
   Code-drawn art and engine primitives are allowed only where the table says so. A character, a hero
   prop, an obstacle with identity, an icon or a background is never built from spheres, boxes and
   cylinders: "procedural" loses on characters, complex shapes and painted texture, and the user reads it
   as cheap at a glance.
3. **Design before model; target in the game frame.** Anything that stays on screen is first drawn INTO a
   real capture of the game (or a grey layout draft at the game camera), at real size, with all of its
   states (idle, hit, lit/unlit). A pretty 3/4 drawing alone on grey is not a target: the game camera
   crushes it (see §5), and it gets shrunk to fit a corner. One such object came out "ugly, scary, no
   charm, wrong size" and every patch afterwards made it worse.
4. **Every option is shown in the game frame, side by side, and the source's own quality level is one of
   the options.** A board of loose objects hides the real problem; without the original level as a choice,
   "more vivid" turns into glare the user rejects ("too shiny, hurts the eyes").
5. **One scene, one pipeline.** A painted image-to-3D prop next to flat-palette code props looks wrong in
   colour and finish even when each is fine alone. When the pipeline changes, the whole set changes.
6. **Judge only in-game captures, on the phone — with a calibrated capture rig.** HD capture plus a 3× close-up of what changed. Editor
   previews and Blender renders lied every time (ice and wood looked rich in Blender, washed out in game;
   a text outline worked in the editor and vanished on the phone). The capture itself lied in many ways (wrong
   resolution, a curtain left open, adaptive quality lowering physics) until its self-tests (T005) were green.
   A comparison applies the SAME mask to both images — a box that swallowed a shadow on one side made every
   number in a hand-off wrong.
7. **The source game's art never goes into a generator.** Only the agent looks at it, to learn function,
   size and quality bar. The brief is written in our words, at function level. If a FORM line describes
   the original's composition, the generator copies it: rewrite it next to the original before generating.
8. **No text, numbers or logos inside generated images.** Text is set in the engine (localisation). One
   exception: a style-board frame keeps the game's own HUD and gate numbers from our capture so the user
   sees the real screen; the prompt says "keep the HUD, progress bar and numbers exactly as in the input",
   and anything the generator mangles is noted on the board, never fixed by hand.

## 1. The gates in order

| Step | Task | What happens | User sees | Gate |
|---|---|---|---|---|
| A. Quality bar | T011 | Ask the user for 1–3 games or clips they like the look of. Capture 3–5 games at the same aspect; measure outline width, saturation, brightness, tube/sprite share of the screen. Every adjective ("vivid", "soft", "premium") is tied to a number or to a frame. Fill the asset-class table (§2) for this game. | one board of quality frames with numbers on them | G2 |
| B. Style lock | T013 | Three styles drawn over **our** game frame (A/B/C), one of them the source's level. Use 1–2 captures that together show every core element (friendly unit, enemy, both gate kinds, a tower/boss, HUD). Redraw, do not repaint (§3). User picks. The pick becomes the fixed STYLE line of every prompt and a style contract with numbers: palette, brightness range, outline width, shadow tone, material family, light direction, colour-blind check (closest pair under deuteranopia, ΔE ≥ 20). | board A/B/C in the game frame, then the contract | G3 |
| C. Object batches | T018 | 5–10 objects per batch, not all at once. Per object: one line saying where it is used and what it must make the player read; 2–3 alternatives; an object sheet (16:9 grey: front/side/back on top, the game-camera view in its colours below) **and** an in-frame rehearsal (`ctx.py`). | per-batch board: original · ours A/B/C · in-frame | G4, G9 |
| D. Numbers + blockout | T018 | Proportions as numbers (height in cells or in character units, where the light sits, what moves). A rough blockout in the engine, in the same frame as the target. | target and blockout side by side | G9 |
| E. Production | T018 | The tool from §2. Moving parts are generated separately or cut along a flat boundary — say so in the design. | in-game HD + 3× close-up, next to the target | G9, G10 |
| F. Phone check | T018, T100 | Android build on the phone (or emulator `-gpu host` for text/material), HD + close-up, dark and light colour of the same material checked. | phone screenshot next to the target | G12 |

Batches never skip C → D. When the model does not match the target, go back to the target; patching a
model in code (tilting, cutting, refilling) does not rescue proportion and harmony.

## 2. Asset class → tool

| Class | Primary | Fallback | Accepted when |
|---|---|---|---|
| 2D painted scene, character art, card, poster, loading screen | Gemini image (§3) with the approved STYLE + character sheet as one reference image | user's own drawing | in the game frame at real size, palette holds, licence row |
| UI icon (gear, coin, power-up) | Gemini, flat #808080 background, one icon per image → `fit.py` | OFL/CC0 set | reads at phone size at a glance; code-drawn icons were called "cheap, disgusting" |
| UI frame, button, panel, badge (9-slice) | code (`sprite-generator:procedural-sprites`), all parts from one kit palette file | Gemini texture + 9-slice | at the source's UI size, simulated at every real size (a full half-circle end turns into a lens on a small button; superellipse n≈4 fixed it) |
| 3D hero object (character, mascot, tower, machine) | target in frame → numbers → blockout → image-to-3D (§4) → `tripo_prep.py` → toon shading | user's model + Blender | silhouette ratios hold, every state works, one outline per part |
| 3D simple geometric prop (box, stone, ice block, tile) | Blender script with the kit's shape rules: real bevel, pillow edges, rich material (grain, rings, moss, nail holes) | image-to-3D | fits its cell, visual-rule tests green, looks like a set when tiled |
| Mesh the source itself generates in code (rings, tubes, rails) | code mesh + our shader, like the source | — | measured widths and segment counts match |
| Emblem on a block / unlock card | Blender render of the same 3D object, glossy, thick dark outline that still reads at in-game size (e.g. on a ~55 px block), saturation ≥ 0.7 | — | a flat PIL "sticker" emblem was rejected as stale |
| Effect | engine particles + code texture, timing from the reference | — | side by side at ¼ speed; total light within ±10 % of the reference; flames as two hard-edged cartoon layers (a soft blurred flame read as mud) |
| Picture-based level art | Gemini pixel art in the game's colours (§6) → converter with a tone ramp | rules-based drawing | subject fills the board, flat background, 2–3 tones per part |
| Store and ad art (T122) | approved game art composed into a layout mock-up first, one hook line | — | a raw gameplay crop read as amateur; a cloud of coins and blurred colour fill were flagged "gambling" by an ad classifier |
| Sound / music | CC0 libraries, signature sounds synthesised, music generated or CC0 | licensed library | plays on the same events as the reference, licence row |
| Font | Google Fonts OFL | another OFL | all target-language glyphs |
| Toon shader | decided in T011: bought (licence row before the first store upload) or our own, proved by ΔE per material | — | licence row exists |

## 3. Gemini (image and video)

**Driver:** `scripts/art/gem.sh` drives gemini.google.com through the gstack browser (`/browse`). Set
`GEM_PY` to a python with Pillow if plain `python3` lacks it. Set
`GEM_BROWSE_ROOT` to the repo whose browser profile is signed in; the browse daemon is chosen by git root,
so a worktree opens a fresh signed-out browser. When another session shares the browser, pass `GEM_TAB`.
The driver depends on Gemini's UI and breaks when it changes (seen: a promo popover whose invisible
backdrop blocked every click; the model picker renamed from "3 Pro" to "4 Neon/Hydrogen/Carbon"). It now
fails fast with the step that broke. Fix the driver in the plugin (a subagent may patch a copy to finish its
batch, and must report the diff), do not route around it. `GEM_MODEL` picks the model by name.

```
gem.sh gen   prompt.txt 16:9 /abs/out.png [/abs/ref.png]   # new chat, Pro image model
gem.sh again fix.txt /abs/out2.png                          # same chat: "change only X, keep everything else"
```

**Style board: redraw, do not repaint.** Told to "keep the layout" of a weak capture, Gemini keeps its
flatness too: the first round of a real style board came back as our own frame with new colours, and the
hero units were pixel-identical in all three options. Give the capture as a *composition sketch*: "use the
input only for camera, layout and HUD positions; redraw every object, material and character from scratch
at the quality of a top-grossing 3D mobile game; the units must be redesigned in this style". Then check
the layout held. When no single capture shows every core element, paste the missing piece from another of
OUR captures onto the main frame (one composite input — two frames side by side make Gemini draw two
panels), or describe it in words ("about 15 red enemy slimes beyond the gates"). The source's quality level is set in words (§0.7: its frames are never uploaded); the
user board may show the source's own frame as a labelled reference cell — it never goes to the generator.
Gemini returns about 1536×2752 for 9:16 (0.558, our captures 0.5625): `pano.py` scales to one height;
crop, never stretch, when an exact aspect matters.

**Prompt shape:** `OBJECT` (what, where used, what it must read as) / `FORM` (our own composition) /
`STYLE` (the one fixed line from step B, e.g. "true 3D CGI toy look, not a flat painted illustration" +
palette + light). Keep a one-line `fix` file per asset: the reason it was rejected, appended to the next
try, kept across sessions. A fix never overrides the FORM line.

**Traps (each cost a day):**
- Ask for "plain flat #808080 grey background, never a checkerboard"; "transparent" draws a fake checkerboard.
- Upload references as ONE combined image; three separate uploads make the request drop silently. Wait
  ~8 s after a paste; compare the downloaded file's md5 with the previous one.
- Percent positions ("horizon at 30 %") and left/right are not followed. Crop instead; for direction,
  mirror the source, ask for the opposite side, mirror the result back.
- Notes like "the frame is drawn in game" make it draw a frame: write "never draw a frame".
- "Tilt-shift" or "miniature" adds depth-of-field blur: far gates and numbers become unreadable. Never use
  it for a game frame. Say "everything in sharp focus".
- An edit round ("change only the materials") can still drift the HUD (a progress bar grew): add "do not
  touch the HUD".
- Sample objects on a character sheet leak into the scene: "ignore the sample objects on the sheet".
- Resolution sometimes drops to 1K: upload the accepted 1K image alone and ask to redraw it at the
  highest resolution, unchanged.
- Under load the image tool click is skipped and a text answer comes back: retry until the image chip shows.
- Outpainting and pasting back leave seams and rectangles; prefer one image whose centre is what the
  phone shows (measure which part of a full-screen image the camera actually shows — a poster can be
  shown 2× with only its middle third visible).
- Grey-furred subjects on grey: `fit.py ... box=x,y,w,h` keeps the normal cut inside the subject box (the fur
  survives) and a tight cut (tol 22, tiny holes) outside. The closed-hole pass can punch the subject's own
  grey or steel faces (an armpit, a steel band): shrink `holes` or use `box=`.
- References must be PNG (the paste path reads PNG only, macOS only); convert JPEGs first.
- The Gemini browser is one shared resource: one generation at a time across all sessions and subagents.
  Copying its signed-in session to a second browser signed the first one out.

**Cut and fit:** `fit.py raw.png out.png WxH` (border + closed grey holes, 2 px eroded soft edge, fit).
**Rehearse in frame:** `ctx.py original_sprite.png capture.png ours.png sheet.jpg` erases the original in
a real capture and drops ours in its box — the most valuable step: it catches size, contrast and style
clashes before anything enters the engine. A 3D object has no sprite to search for: crop the object's box
from the capture, pass the crop as the "original" with `BOX=` that box and `FILL=1`. A whole-look option
(style board) is a Gemini redraw over our capture as described above, not a rehearsal. **Board:**
`pano.py --cols=4 --zoom=fx,fy,fw,fh --note="..."`: full frames on top, the same close-up box (e.g. the crowd
and the nearest gate) below, defects the generator made in the note line.

**No Gemini Pro account or no signed-in browser:** the pipeline does not stop. The user generates the
images by hand (or supplies drawings), drops them in a folder, and `fit.py` / `ctx.py` / `pano.py` run as
usual; write the fallback to KARARLAR. If the profile has several Google accounts, set `GEM_ACCOUNT` to the
one with Pro — the default account may be free tier, where the Pro click silently does nothing and a
low-quality image comes back.

## 4. Image → 3D

- Feed a clean, shaded 3/4 image of the object alone on grey, generated from the approved target.
- Tripo-class service: texture on, "remove lighting" on, PBR off. A job can silently drop in the queue
  (credits come back): resubmit after 30 min. Never click by coordinates near an upgrade/payment dialog.
- `tripo_prep.py` (Blender, headless): join, base to z 0, centre, weld, decimate to the face budget, keep
  UV and the painted texture. Flattening the painted texture into a few role colours killed the charm.
- Use it only where shape is weak and the object is large on screen. Readability problems are design
  problems; a better model does not fix them.
- Local open models (e.g. Hunyuan3D) turned rounded toys into boxes from flat views and need ~16 min and
  most of a 16 GB machine; their licence may exclude the EU, UK and South Korea. Settle the licence before
  shipping anything they made.

## 5. In-engine rules (toon look)

- Shadow colour comes from one function of the base colour, never `colour × 0.35` (the shader multiplies
  again; dark reds turned to coal). Check one dark and one light colour of every material.
- One outline per part (a welded, averaged-normal shell child), not the shader's per-region outline,
  which breaks into arcs at region borders. Inner parts (mouths, holes, light strips) have no outline.
- Natural materials (stone, wood, soil) are matte: no specular, no fresnel, chiselled not domed. No white
  fresnel rim on large surfaces. Liveliness comes from form (rounded, domed, pillow edges), not from a
  bigger highlight.
- When "only colour" reads, sample the reference's edge column (highlight line, dark crease, rim, dark
  bottom) and bake those colours into a ramp; raising light gain did nothing.
- A top-down camera (e.g. 70°) crushes vertical motion and height (cos 70 ≈ 0.34): tilt objects BACK to
  show a face, put ears to the sides like leaves, swing tools in the screen plane, tilt tall objects so
  their side profile reads (a balloon read as a ball).
- Obstacles: the body is the obstacle (trunk to the ground), never a cube pedestal (players shoot the
  pedestal); organic silhouette clearly taller than a cell; rich material; distinguishing marks (a hose is
  thin, matte, ribbed — a thick glossy tube read as toothpaste); debris irregular in size, scattered.
- A shape that changes collision is a mechanic change and needs the user.
- If URP `postProcessData` is null no Volume works; check before tuning grading.
- Visual rules become EditMode tests on day one (one outline per part, no black shadows, no baked text).

## 6. Picture-based levels

Hand- or code-drawn level pictures were called "unprofessional, unclear, always the same". What worked:
the subject fills the board edge to edge, flat single-colour background, every part in 2–3 tones from
the game palette (yellow shades to orange), and the style changes from level to level (cute character,
emoji face, neon gradient, stained glass). Gemini draws, a converter reads it into cells with a tone ramp
(a flat mapping lost the shading). The user picks the style family from a few examples first.

## 7. Asking the user

- **Main session only** (subagents cannot reach the user). Build the board with `pano.py`: options in the game frame, labelled A/B/C, the source level as one
  option or as a reference cell. Send it (`SendUserFile`) and give the full `/Users/...` path in a code block.
- Then ask with `AskUserQuestion`: at most 3 options, recommendation first with one reason, and for each
  option what the player will see on screen. End with "A mı, B mi?".
- UI tint multiplies and can only darken: if a colour is wrong, the sprite is wrong; a tint does not save it.
- An aesthetic complaint ("dull", "cheap") gets a request for a reference game or clip BEFORE any
  prototype. Numeric fixes without a reference frame (saturation +8 %, bloom, rim) were rejected and
  rolled back.
- A pick is written to `KARARLAR.md` with the board path; never ask it again. Right after the pick, still in
  T013, the main session writes the style contract (palette hex values measured from the picked image,
  brightness range, outline, shadow tone, material, light) and runs the colour-blind check on it; an old
  decision that contradicts the pick (e.g. "art is drawn in code") is struck through in the same edit. "Continue with your
  recommendation" covers the same kind of next step, not a new kind.
- Independent reviewer agents disagree with themselves; act only on a note that repeats or that a pixel
  measurement confirms, and after ~3 rounds without convergence give the user the round history.

## 8. Performance budget (T017)

Measured on a mid-range phone AND one low-end phone, not the emulator (it does not represent a cheap phone).
If only one class was measured, the result holds for that class only — say which.
- Set `Application.targetFrameRate = 60` at boot — the first device day of one game found it running at 30.
- A development build takes a level id by intent extra, runs the auto-player, and logs one `[perf]` line
  per second (average and worst frame, main thread, physics, memory) plus one line per slow frame and an
  8 s profiler capture. The profile disproved the agent's guess: the hitch was an effect creating 61 UI
  objects in one frame at level start → pool in Awake.
- What a shipped game reached on an upper-mid phone: 59.4–59.7 fps over 10 min, 0.33 % slow frames, cold start first frame
  ~0.5 s, level load ~2.1 s, PSS ~600 MB in the menu (the reference ~900 MB). Draw calls were not
  measured; write "not measured" instead of a number.
- Budgets per asset class are set in T017 from measurement and written to KARARLAR. Unmeasured starting
  points, to be replaced by measurement: crowd unit 1.5–3k triangles, hero/boss 10–15k, textures ≤ 1024
  unless the object fills the screen. In a crowd game the real risk is hundreds of skinned meshes: measure a
  full crowd early (GPU instancing / baked animation if needed). Every new hero model is checked against them.
- Android: compress with LZ4HC (the default chunked compression re-opened 1 MB chunks on every read and
  start-up sat on a black screen for 3 minutes). Adaptive quality systems lower physics or render
  quality under capture load: turn them off while measuring and recording. A Unity batch run on a Mac restarts the adb server and kills logcat streams.
- A new field on a remotely updated visuals object drove Android start-up to 4.4 GB and a crash; remote
  updates replace existing fields only.

## 9. Tools (`scripts/art/`)

| Script | Does |
|---|---|
| `gem.sh` | Gemini image/video driver over the gstack browser (`gen`, `again`, `dl`, `vid`) |
| `fit.py` | cut a grey-background object (border + closed holes), soft edge, fit to W×H; `--full`, `--bottom`, `--keep` |
| `ctx.py` | in-frame rehearsal: find the original in a capture, erase it, place ours, write the comparison sheet |
| `pano.py` | labelled decision board, one height, optional grid; `--zoom` same-box close-up row (crop to one aspect, never stretch); `--note` defect line |
| `tripo_prep.py` | Blender: prepare an image-to-3D GLB keeping its painted texture |

Dependencies: Pillow, numpy, scipy; `ctx.py` also opencv-python-headless. `tests/test-art-tools.py` checks them.
