# clone-app: Design Capture + Standalone Build Spec (+ Unity/Game Support) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `clone-app` capture the target app's design system + screenshots + (for Unity games) C# type model and game assets, and emit one standalone `clone-build-spec.md` so a fresh session can build a pixel-perfect, production-ready clone.

**Architecture:** Add three helper scripts (`extract-design.py`, `detect-unity.sh`, plus two thin .NET-tool wrappers `il2cpp-dump.sh` / `unity-assets.sh`), extend `scrape-play-store.py` to emit screenshots, add three reference rubrics, update two existing references, and extend `SKILL.md` with design-extraction + Unity branches in Phase 2, screenshot download in Phase 3, and a new Phase 8 that assembles the build spec before invoking `writing-plans`. Design/Unity extraction runs inside the existing isolated Phase-2 RE subagent so decompiled sources/assets never flood the orchestrator context.

**Tech Stack:** bash 4+ (`#!/usr/bin/env bash`, run with `bash <path>`), Python 3 stdlib-only (`xml.etree.ElementTree`, `json`, `re`, `urllib`, `zipfile`), external .NET tools driven via wrappers (Il2CppInspectorRedux, AssetRipper, ILSpy `ilspycmd`).

## Global Constraints

- `plugins/android-reverse-engineering/` is vendored upstream — MUST stay byte-identical. `git status --porcelain plugins/android-reverse-engineering/` MUST print nothing. All new logic lives under `plugins/clone-app/`.
- Python is stdlib-only: no pip, no virtualenv.
- Scripts use `#!/usr/bin/env bash`; bash tests use `set -uo pipefail` (not `-e`) and aggregate failures into a `fail` var so every assertion runs.
- Python scrapers/parsers are tested offline against `tests/fixtures/` via file flags — never hitting the network.
- Working dir is `./work/<pkg>/` relative to the user's cwd, never inside the plugin.
- Effort is measured in "AI Sprints", never calendar time.
- Conventional Commits scoped to the plugin: `feat(clone-app): …`, `test(clone-app): …`, `docs(clone-app): …`.
- External .NET tools are NOT bundled; scripts detect them and degrade gracefully with install guidance when absent.
- New `test-*.sh` / `test-*.py` files under `tests/` are auto-discovered by `tests/run-all.sh` (it globs) — no `run-all.sh` edit needed.

---

### Task 1: `extract-design.py` — design tokens from decompiled resources

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/extract-design.py`
- Create: `plugins/clone-app/tests/fixtures/design-sample/res/values/colors.xml`
- Create: `plugins/clone-app/tests/fixtures/design-sample/res/values/dimens.xml`
- Create: `plugins/clone-app/tests/fixtures/design-sample/res/values/themes.xml`
- Create: `plugins/clone-app/tests/fixtures/design-sample/res/layout/activity_main.xml`
- Create: `plugins/clone-app/tests/fixtures/design-sample/res/font/inter_regular.ttf`
- Test: `plugins/clone-app/tests/test-extract-design.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: CLI `python3 extract-design.py <decompile-root> [--framework F] [--out tokens.json] [--digest digest.md]`. Writes a `design-tokens.json` object (also printed to stdout when `--out` omitted) with top-level keys: `package` (always `null` here — caller fills), `source` (`"apk-resources"`), `framework`, `colors`, `dimens`, `typography`, `shapes`, `theme`, `icon`, `layouts`. Each of `colors/dimens/typography/shapes/theme/icon/layouts` is an object `{ "values": …, "confidence": "high"|"med"|"low" }`.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-extract-design.py`:

```python
#!/usr/bin/env python3
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "skills", "clone-app", "scripts", "extract-design.py")
ROOT = os.path.join(HERE, "fixtures", "design-sample")

def run():
    out = subprocess.check_output([sys.executable, SCRIPT, ROOT])
    return json.loads(out)

def main():
    d = run()
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)
    check("source", d["source"] == "apk-resources")
    check("colors parsed", d["colors"]["values"].get("colorPrimary") == "#FF6200EE")
    check("colors accent", d["colors"]["values"].get("colorAccent") == "#FF03DAC5")
    check("colors confidence high", d["colors"]["confidence"] == "high")
    check("dimens parsed", d["dimens"]["values"].get("spacing_small") == "8dp")
    check("text size dimen", d["dimens"]["values"].get("text_size_body") == "14sp")
    check("theme parent", d["theme"]["values"].get("parent") == "Theme.Material3.DayNight")
    check("theme is_dark flag present", "is_dark" in d["theme"]["values"])
    check("fonts list", "inter_regular.ttf" in d["typography"]["values"]["fonts"])
    check("layout count", d["layouts"]["values"]["count"] == 1)
    for k in ["package","source","framework","colors","dimens","typography","shapes","theme","icon","layouts"]:
        check(f"key present: {k}", k in d)
    sys.exit(1 if fails else 0)

main()
```

- [ ] **Step 2: Create the fixtures**

`plugins/clone-app/tests/fixtures/design-sample/res/values/colors.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="colorPrimary">#FF6200EE</color>
    <color name="colorAccent">#FF03DAC5</color>
</resources>
```

`plugins/clone-app/tests/fixtures/design-sample/res/values/dimens.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <dimen name="spacing_small">8dp</dimen>
    <dimen name="text_size_body">14sp</dimen>
</resources>
```

`plugins/clone-app/tests/fixtures/design-sample/res/values/themes.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.App" parent="Theme.Material3.DayNight">
        <item name="colorPrimary">@color/colorPrimary</item>
        <item name="android:windowBackground">@android:color/white</item>
    </style>
</resources>
```

`plugins/clone-app/tests/fixtures/design-sample/res/layout/activity_main.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent" />
```

`plugins/clone-app/tests/fixtures/design-sample/res/font/inter_regular.ttf` — create as an empty placeholder file (content irrelevant; only the filename is inventoried):

```bash
mkdir -p plugins/clone-app/tests/fixtures/design-sample/res/font
: > plugins/clone-app/tests/fixtures/design-sample/res/font/inter_regular.ttf
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 plugins/clone-app/tests/test-extract-design.py`
Expected: FAIL — `extract-design.py` does not exist (subprocess raises / non-zero).

- [ ] **Step 4: Write the implementation**

Create `plugins/clone-app/skills/clone-app/scripts/extract-design.py`:

```python
#!/usr/bin/env python3
"""Extract a design-token digest from a decompiled APK resource tree.

Reads res/values/{colors,dimens,styles,themes}.xml, the res/font/ dir, the
drawable*/mipmap* inventory, and counts res/layout/*.xml. Stdlib-only.

Emits a design-tokens.json object on stdout (or --out FILE) and, with --digest
FILE, a markdown design summary. Framework-aware: native apps have a rich XML
layer (confidence high); Compose keeps tokens in res/values but no layouts
(med); Flutter/React Native keep almost nothing in Android res (low) so the
caller leans on screenshots. Pass --framework to override the auto guess.
"""
import sys, os, json, re, argparse, glob
import xml.etree.ElementTree as ET

def _find_res_dirs(root):
    """All res/ dirs under root that contain a values/ subdir (jadx puts these
    under <out>/resources/res; apktool under <out>/res — search either)."""
    hits = []
    for p in glob.glob(os.path.join(root, "**", "res"), recursive=True):
        if os.path.isdir(os.path.join(p, "values")) or glob.glob(os.path.join(p, "values*")):
            hits.append(p)
    return sorted(set(hits))

def _iter_value_files(res_dirs, basename):
    for res in res_dirs:
        for vdir in glob.glob(os.path.join(res, "values*")):
            f = os.path.join(vdir, basename)
            if os.path.isfile(f):
                yield f

def _parse_named(res_dirs, basename, tag):
    """Collect <tag name="X">value</tag> entries from every values*/basename."""
    out = {}
    for f in _iter_value_files(res_dirs, basename):
        try:
            tree = ET.parse(f)
        except ET.ParseError:
            continue
        for el in tree.getroot().iter(tag):
            name = el.get("name")
            if name and (el.text is not None):
                out[name] = el.text.strip()
    return out

def _parse_themes(res_dirs):
    """First <style> whose name contains 'Theme' — parent + items + dark guess."""
    for base in ("themes.xml", "styles.xml"):
        for f in _iter_value_files(res_dirs, base):
            try:
                tree = ET.parse(f)
            except ET.ParseError:
                continue
            for st in tree.getroot().iter("style"):
                name = st.get("name", "")
                if "Theme" not in name:
                    continue
                parent = st.get("parent", "")
                items = {it.get("name"): (it.text or "").strip()
                         for it in st.iter("item") if it.get("name")}
                hay = (name + " " + parent).lower()
                is_dark = ("night" in hay) or ("dark" in hay)
                return {"name": name, "parent": parent, "items": items,
                        "is_dark": is_dark}
    return {}

def _font_files(res_dirs):
    fonts = []
    for res in res_dirs:
        for fdir in glob.glob(os.path.join(res, "font*")):
            for f in sorted(glob.glob(os.path.join(fdir, "*"))):
                fonts.append(os.path.basename(f))
    return sorted(set(fonts))

def _layout_files(res_dirs):
    files = []
    for res in res_dirs:
        for ldir in glob.glob(os.path.join(res, "layout*")):
            files += [os.path.basename(x) for x in glob.glob(os.path.join(ldir, "*.xml"))]
    return sorted(set(files))

def _drawable_count(res_dirs):
    n = 0
    for res in res_dirs:
        for ddir in glob.glob(os.path.join(res, "drawable*")) + glob.glob(os.path.join(res, "mipmap*")):
            n += len(glob.glob(os.path.join(ddir, "*")))
    return n

def _icon(res_dirs):
    for res in res_dirs:
        for ddir in sorted(glob.glob(os.path.join(res, "mipmap*")), reverse=True):
            hits = glob.glob(os.path.join(ddir, "ic_launcher*"))
            if hits:
                return os.path.relpath(sorted(hits)[0])
    return None

def _guess_framework(root):
    for _ in (1,):
        if glob.glob(os.path.join(root, "**", "libil2cpp.so"), recursive=True) or \
           glob.glob(os.path.join(root, "**", "libunity.so"), recursive=True):
            return "unity"
        if glob.glob(os.path.join(root, "**", "libflutter.so"), recursive=True) or \
           glob.glob(os.path.join(root, "**", "flutter_assets"), recursive=True):
            return "flutter"
        if glob.glob(os.path.join(root, "**", "index.android.bundle"), recursive=True):
            return "react-native"
    return "android"

# confidence per framework: native android = high, compose-ish (no layouts but
# res present) = med, flutter/rn/unity = low.
def _confidence(framework, layouts_count):
    if framework in ("flutter", "react-native", "unity"):
        return "low"
    if layouts_count == 0:
        return "med"
    return "high"

def extract(root, framework=None):
    res_dirs = _find_res_dirs(root)
    fw = framework or _guess_framework(root)
    layouts = _layout_files(res_dirs)
    conf = _confidence(fw, len(layouts))
    colors = _parse_named(res_dirs, "colors.xml", "color")
    dimens = _parse_named(res_dirs, "dimens.xml", "dimen")
    theme = _parse_themes(res_dirs)
    text_sizes = {k: v for k, v in dimens.items() if v.endswith("sp")}
    return {
        "package": None,
        "source": "apk-resources",
        "framework": fw,
        "colors":     {"values": colors, "confidence": conf},
        "dimens":     {"values": dimens, "confidence": conf},
        "typography": {"values": {"fonts": _font_files(res_dirs),
                                  "text_sizes": text_sizes}, "confidence": conf},
        "shapes":     {"values": {"corner_dimens":
                                  {k: v for k, v in dimens.items()
                                   if "corner" in k or "radius" in k}},
                       "confidence": conf},
        "theme":      {"values": theme, "confidence": conf},
        "icon":       {"values": {"path": _icon(res_dirs)}, "confidence": conf},
        "layouts":    {"values": {"count": len(layouts), "files": layouts},
                       "confidence": conf},
    }

def digest_md(d):
    L = [f"# Design Digest — {d.get('package') or '(unknown)'}",
         f"Framework: {d['framework']}  ·  source: {d['source']}", ""]
    L.append(f"## Colors ({d['colors']['confidence']})")
    for k, v in d["colors"]["values"].items():
        L.append(f"- `{k}` = {v}")
    L.append(f"\n## Dimens ({d['dimens']['confidence']})")
    for k, v in d["dimens"]["values"].items():
        L.append(f"- `{k}` = {v}")
    th = d["theme"]["values"]
    L.append(f"\n## Theme ({d['theme']['confidence']})")
    L.append(f"- name: {th.get('name')}  parent: {th.get('parent')}  dark: {th.get('is_dark')}")
    L.append(f"\n## Typography ({d['typography']['confidence']})")
    L.append(f"- fonts: {', '.join(d['typography']['values']['fonts']) or '(none in res)'}")
    L.append(f"\n## Layouts ({d['layouts']['confidence']})")
    L.append(f"- count: {d['layouts']['values']['count']}")
    L.append(f"\n## Icon\n- {d['icon']['values']['path']}")
    return "\n".join(L) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="decompile output root")
    ap.add_argument("--framework")
    ap.add_argument("--package")
    ap.add_argument("--out")
    ap.add_argument("--digest")
    args = ap.parse_args()
    d = extract(args.root, args.framework)
    if args.package:
        d["package"] = args.package
    text = json.dumps(d, indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)
    if args.digest:
        with open(args.digest, "w") as f:
            f.write(digest_md(d))

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 plugins/clone-app/tests/test-extract-design.py`
Expected: PASS — every check prints PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/extract-design.py \
        plugins/clone-app/tests/test-extract-design.py \
        plugins/clone-app/tests/fixtures/design-sample
git commit -m "feat(clone-app): extract-design.py — design tokens from decompiled res/"
```

---

### Task 2: `detect-unity.sh` — classify Unity APKs

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/detect-unity.sh`
- Test: `plugins/clone-app/tests/test-detect-unity.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: CLI `bash detect-unity.sh <apk-or-xapk>` → prints exactly one of `il2cpp` | `mono` | `none` to stdout, exit 0. Exit 2 on usage/read error. Used by SKILL Phase 2 to pick the Unity branch.

- [ ] **Step 1: Write the failing test**

Create `plugins/clone-app/tests/test-detect-unity.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../skills/clone-app/scripts/detect-unity.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}

# Build three fixture zips with python's zipfile (portable, no `zip` needed).
mkzip() { python3 - "$1" "${@:2}" <<'PY'
import sys, zipfile
out = sys.argv[1]
with zipfile.ZipFile(out, "w") as z:
    for entry in sys.argv[2:]:
        z.writestr(entry, "x")
PY
}

mkzip "$TMP/il2cpp.apk" "lib/arm64-v8a/libil2cpp.so" "assets/bin/Data/Managed/Metadata/global-metadata.dat"
mkzip "$TMP/mono.apk"   "assets/bin/Data/Managed/Assembly-CSharp.dll"
mkzip "$TMP/plain.apk"  "classes.dex" "AndroidManifest.xml"

check "il2cpp"  "il2cpp" "$(bash "$SCRIPT" "$TMP/il2cpp.apk")"
check "mono"    "mono"   "$(bash "$SCRIPT" "$TMP/mono.apk")"
check "none"    "none"   "$(bash "$SCRIPT" "$TMP/plain.apk")"

bash "$SCRIPT" >/dev/null 2>&1; rc=$?
check "usage exit 2" "2" "$rc"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-detect-unity.sh`
Expected: FAIL — script missing.

- [ ] **Step 3: Write the implementation**

Create `plugins/clone-app/skills/clone-app/scripts/detect-unity.sh`:

```bash
#!/usr/bin/env bash
# Classify an APK/XAPK as a Unity build: il2cpp | mono | none.
set -uo pipefail

APK="${1:-}"
if [[ -z "$APK" || ! -f "$APK" ]]; then
  echo "ERROR: usage: detect-unity.sh <apk-or-xapk>" >&2
  exit 2
fi

listing="$(unzip -Z1 "$APK" 2>/dev/null)" || {
  echo "ERROR: cannot read zip: $APK" >&2; exit 2; }

if grep -q 'global-metadata\.dat' <<<"$listing" \
   && grep -qi 'libil2cpp\.so' <<<"$listing"; then
  echo il2cpp; exit 0
fi
if grep -Eq 'assets/bin/Data/Managed/.*\.dll' <<<"$listing"; then
  echo mono; exit 0
fi
echo none
exit 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bash plugins/clone-app/tests/test-detect-unity.sh`
Expected: PASS — all four checks PASS, exit 0.

- [ ] **Step 5: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/detect-unity.sh \
        plugins/clone-app/tests/test-detect-unity.sh
git commit -m "feat(clone-app): detect-unity.sh — classify il2cpp/mono/none APKs"
```

---

### Task 3: extend `scrape-play-store.py` with screenshots + description

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/scripts/scrape-play-store.py`
- Modify: `plugins/clone-app/tests/fixtures/play-sample.html`
- Modify: `plugins/clone-app/tests/test-scrape-play-store.py`

**Interfaces:**
- Consumes: nothing.
- Produces: the scrape JSON gains three keys — `screenshot_urls` (list of strings), `feature_graphic` (string|null), `description` (string|null) — parsed from the ld+json `screenshot`, `image`, and `description` fields. Phase 3 downloads `screenshot_urls` into `$WORK/screenshots/`.

- [ ] **Step 1: Update the fixture's ld+json**

Open `plugins/clone-app/tests/fixtures/play-sample.html`, find the
`<script type="application/ld+json">` block whose JSON has
`"@type": "SoftwareApplication"`, and add these three members inside that JSON
object (alongside `name`, `author`, etc.):

```json
"description": "An example puzzle app.",
"image": "https://play-lh.googleusercontent.com/feature.png",
"screenshot": [
  "https://play-lh.googleusercontent.com/shot1.png",
  "https://play-lh.googleusercontent.com/shot2.png"
]
```

(Keep the JSON valid — comma-separate from the existing members.)

- [ ] **Step 2: Add failing assertions to the test**

In `plugins/clone-app/tests/test-scrape-play-store.py`, after the existing
`check("source", …)` line, add:

```python
    check("description", d["description"] == "An example puzzle app.")
    check("feature_graphic", d["feature_graphic"] == "https://play-lh.googleusercontent.com/feature.png")
    check("screenshot count", len(d["screenshot_urls"]) == 2)
    check("screenshot url", d["screenshot_urls"][0] == "https://play-lh.googleusercontent.com/shot1.png")
```

And extend the "all expected keys present" loop list to include the new keys:

```python
    for k in ["package","title","rating","rating_count","installs","category","developer","updated","source","screenshot_urls","feature_graphic","description"]:
        check(f"key present: {k}", k in d)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 plugins/clone-app/tests/test-scrape-play-store.py`
Expected: FAIL — `KeyError`/FAIL on `description`, `feature_graphic`, `screenshot_urls`.

- [ ] **Step 4: Implement the new fields**

In `scrape-play-store.py`, change the `KEYS` list (line 9-10) to add the three keys:

```python
KEYS = ["package", "title", "rating", "rating_count", "installs",
        "category", "developer", "updated", "source",
        "screenshot_urls", "feature_graphic", "description"]
```

Then inside the `SoftwareApplication` branch of `parse()` (just before the
`break`), add:

```python
            out["description"] = data.get("description")
            img = data.get("image")
            if isinstance(img, list):
                img = img[0] if img else None
            out["feature_graphic"] = img
            shots = data.get("screenshot") or []
            if isinstance(shots, dict):
                shots = [shots]
            urls = []
            for s in shots:
                if isinstance(s, str):
                    urls.append(s)
                elif isinstance(s, dict) and s.get("url"):
                    urls.append(s["url"])
            out["screenshot_urls"] = urls
```

(`out` is initialized from `KEYS`, so `screenshot_urls` defaults to `None`; the
assignment above replaces it with a list when the block is found. If no
ld+json block matches, `screenshot_urls` stays `None` — callers treat
`None`/`[]` the same.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 plugins/clone-app/tests/test-scrape-play-store.py`
Expected: PASS — all checks PASS including the new ones, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/scrape-play-store.py \
        plugins/clone-app/tests/test-scrape-play-store.py \
        plugins/clone-app/tests/fixtures/play-sample.html
git commit -m "feat(clone-app): scrape screenshots, feature graphic, description from Play"
```

---

### Task 4: Unity tool wrappers `il2cpp-dump.sh` + `unity-assets.sh`

**Files:**
- Create: `plugins/clone-app/skills/clone-app/scripts/il2cpp-dump.sh`
- Create: `plugins/clone-app/skills/clone-app/scripts/unity-assets.sh`
- Test: `plugins/clone-app/tests/test-unity-wrappers.sh`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `bash il2cpp-dump.sh <libil2cpp.so> <global-metadata.dat> <out-dir>` — runs Il2CppInspectorRedux CLI (binary name from `$IL2CPP_INSPECTOR_CLI`, default `Il2CppInspector`); writes C# type model into `<out-dir>`. Exit 2 = bad usage, exit 3 = tool missing (+ install guidance on stderr).
  - `bash unity-assets.sh <apk> <out-dir>` — runs AssetRipper CLI (binary from `$ASSETRIPPER_CLI`, default `AssetRipper`); extracts assets into `<out-dir>`. Exit 2 = bad usage, exit 3 = tool missing.

- [ ] **Step 1: Write the failing test** (covers usage + tool-missing paths only; the real tool runs are binary/network-heavy and out of scope)

Create `plugins/clone-app/tests/test-unity-wrappers.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
S="$HERE/../skills/clone-app/scripts"
fail=0
check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then echo "PASS: $desc"
  else echo "FAIL: $desc — expected '$expected' got '$actual'"; fail=1; fi
}

# usage errors → exit 2
bash "$S/il2cpp-dump.sh" >/dev/null 2>&1; check "il2cpp usage" "2" "$?"
bash "$S/unity-assets.sh" >/dev/null 2>&1; check "assets usage" "2" "$?"

# tool missing → exit 3 + guidance text on stderr
err="$(IL2CPP_INSPECTOR_CLI=/no/such/bin bash "$S/il2cpp-dump.sh" a b c 2>&1 >/dev/null)"; rc=$?
check "il2cpp missing exit 3" "3" "$rc"
grep -q "Il2CppInspectorRedux" <<<"$err" && echo "PASS: il2cpp guidance" || { echo "FAIL: il2cpp guidance"; fail=1; }

err="$(ASSETRIPPER_CLI=/no/such/bin bash "$S/unity-assets.sh" a b 2>&1 >/dev/null)"; rc=$?
check "assets missing exit 3" "3" "$rc"
grep -q "AssetRipper" <<<"$err" && echo "PASS: assets guidance" || { echo "FAIL: assets guidance"; fail=1; }

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-unity-wrappers.sh`
Expected: FAIL — scripts missing.

- [ ] **Step 3: Write `il2cpp-dump.sh`**

Create `plugins/clone-app/skills/clone-app/scripts/il2cpp-dump.sh`:

```bash
#!/usr/bin/env bash
# Recover the C# type model from a Unity IL2CPP build via Il2CppInspectorRedux.
# Flags follow the Il2CppInspector CLI; adjust to your installed CLI version if
# they differ. Only the tool-missing path is exercised by tests.
set -uo pipefail

SO="${1:-}"; META="${2:-}"; OUT="${3:-}"
if [[ -z "$SO" || -z "$META" || -z "$OUT" ]]; then
  echo "ERROR: usage: il2cpp-dump.sh <libil2cpp.so> <global-metadata.dat> <out-dir>" >&2
  exit 2
fi

BIN="${IL2CPP_INSPECTOR_CLI:-Il2CppInspector}"
if ! command -v "$BIN" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: Il2CppInspectorRedux CLI not found.
Install it (needs the .NET SDK): https://github.com/LukeFZ/Il2CppInspectorRedux
Build the CLI, put it on PATH, or set IL2CPP_INSPECTOR_CLI=/path/to/cli.
EOF
  exit 3
fi

mkdir -p "$OUT"
# Produce C# stub headers + a metadata JSON describing types/methods/fields.
"$BIN" --bin "$SO" --metadata "$META" \
       --select-outputs --cs-out "$OUT/types.cs" --json-out "$OUT/metadata.json"
```

- [ ] **Step 4: Write `unity-assets.sh`**

Create `plugins/clone-app/skills/clone-app/scripts/unity-assets.sh`:

```bash
#!/usr/bin/env bash
# Extract Unity game assets (textures, sprites, audio, scenes, prefabs) from an
# APK via AssetRipper's CLI. Only the tool-missing path is exercised by tests.
set -uo pipefail

APK="${1:-}"; OUT="${2:-}"
if [[ -z "$APK" || -z "$OUT" ]]; then
  echo "ERROR: usage: unity-assets.sh <apk> <out-dir>" >&2
  exit 2
fi

BIN="${ASSETRIPPER_CLI:-AssetRipper}"
if ! command -v "$BIN" >/dev/null 2>&1; then
  cat >&2 <<'EOF'
ERROR: AssetRipper CLI not found.
Install it (needs the .NET runtime): https://github.com/AssetRipper/AssetRipper
Put the CLI on PATH, or set ASSETRIPPER_CLI=/path/to/AssetRipper.
EOF
  exit 3
fi

mkdir -p "$OUT"
"$BIN" "$APK" -o "$OUT"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `bash plugins/clone-app/tests/test-unity-wrappers.sh`
Expected: PASS — all six checks PASS, exit 0.

- [ ] **Step 6: Commit**

```bash
git add plugins/clone-app/skills/clone-app/scripts/il2cpp-dump.sh \
        plugins/clone-app/skills/clone-app/scripts/unity-assets.sh \
        plugins/clone-app/tests/test-unity-wrappers.sh
git commit -m "feat(clone-app): Unity tool wrappers (Il2CppInspectorRedux, AssetRipper)"
```

---

### Task 5: reference rubrics + contract/template updates

**Files:**
- Create: `plugins/clone-app/skills/clone-app/references/design-capture-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/unity-re-guide.md`
- Create: `plugins/clone-app/skills/clone-app/references/clone-build-spec-template.md`
- Modify: `plugins/clone-app/skills/clone-app/references/re-digest-contract.md`
- Modify: `plugins/clone-app/skills/clone-app/references/report-template.md`
- Test: `plugins/clone-app/tests/test-references-content.sh`

**Interfaces:**
- Consumes: the artifacts produced by Tasks 1-4 (token/unity/screenshot file names).
- Produces: rubrics SKILL.md Phase 2/6/8 read; the build-spec template Phase 8 fills.

- [ ] **Step 1: Write the failing content test**

Create `plugins/clone-app/tests/test-references-content.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
R="$HERE/../skills/clone-app/references"
fail=0
has() { # file substring
  if grep -qF "$2" "$1" 2>/dev/null; then echo "PASS: $(basename "$1") has '$2'"
  else echo "FAIL: $(basename "$1") missing '$2'"; fail=1; fi
}

has "$R/design-capture-guide.md" "design-tokens.json"
has "$R/design-capture-guide.md" "confidence"
has "$R/design-capture-guide.md" "screenshots"
has "$R/unity-re-guide.md" "Il2CppInspectorRedux"
has "$R/unity-re-guide.md" "AssetRipper"
has "$R/unity-re-guide.md" "ilspycmd"
has "$R/clone-build-spec-template.md" "Screen-by-screen"
has "$R/clone-build-spec-template.md" "Acceptance criteria"
has "$R/clone-build-spec-template.md" "Game variant"
has "$R/re-digest-contract.md" "design-tokens.json"
has "$R/re-digest-contract.md" "unity-digest.md"
has "$R/report-template.md" "Design System"
has "$R/report-template.md" "Game Assets"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-references-content.sh`
Expected: FAIL — new reference files absent, existing files lack the new strings.

- [ ] **Step 3: Create `design-capture-guide.md`**

```markdown
# Design Capture Guide

Goal: recover enough of the target's visual design to clone it **pixel-perfect**.
Two sources, always combined:

1. **APK resources** (`extract-design.py` on the decompile root) →
   `design-tokens.json` + `design-digest.md`. Real colors, dimens, theme,
   fonts, layout inventory, launcher icon.
2. **Play Store screenshots** (`scrape-play-store.py` → `screenshot_urls`,
   downloaded to `$WORK/screenshots/`). The visual ground truth for layout,
   composition, and anything not in res.

## Framework-aware reading (confidence)

| Framework | What's in Android res | Confidence | Fallback |
|---|---|---|---|
| Native (XML views) | colors, dimens, themes, **layouts** | high | — |
| Jetpack Compose | colors/dimens often in res; **no layouts** (UI in Kotlin) | med | grep sources for `Color(0x…)`, `.dp`, `.sp`; screenshots |
| Flutter | almost nothing (Dart owns design) | low | screenshots primary; note low confidence |
| React Native | almost nothing (JS owns styles) | low | screenshots primary |
| Unity | n/a — use `unity-re-guide.md` | low | game assets + screenshots |

`extract-design.py` stamps each token group with `confidence`. When `med`/`low`,
the build spec relies more on screenshots and says so.

## What to record in `design-tokens.json`

colors · dimens (spacing + `sp` text sizes) · typography (font files, text
sizes) · shapes (corner/radius dimens) · theme (name, parent, dark flag, items)
· icon path · layout inventory (count + file names). The caller fills `package`.

## Turning tokens into a spec

Map each token group into the build spec's "Design system" section: palette
(named colors → roles), type scale (text sizes + fonts), spacing scale (dimens),
corner radii, light/dark. Pair every screen in the spec with its closest
`screenshots/NN.png`.
```

- [ ] **Step 4: Create `unity-re-guide.md`**

```markdown
# Unity Reverse-Engineering Guide

Unity ships game logic as native IL2CPP or as managed Mono assemblies. jadx is
blind to IL2CPP — detect the build first with `detect-unity.sh`.

## IL2CPP (`detect-unity.sh` → `il2cpp`)

Inputs: `lib/<abi>/libil2cpp.so` + `assets/bin/Data/Managed/Metadata/global-metadata.dat`.
Run `il2cpp-dump.sh <so> <metadata> <out>` (wraps **Il2CppInspectorRedux**,
https://github.com/LukeFZ/Il2CppInspectorRedux, needs .NET).

**Recoverable:** class / method / field / enum signatures, type hierarchy,
serialized fields, network/RPC type shapes → data model + feature inventory.
**Not recoverable:** C# method *bodies* (compiled to native ARM in the .so).

## Mono (`detect-unity.sh` → `mono`)

Inputs: `assets/bin/Data/Managed/*.dll` (real .NET assemblies). Decompile to
near-source C# with `ilspycmd` (ILSpy CLI): `ilspycmd Assembly-CSharp.dll -o <out>`.
Best case — full logic recovered.

## Assets (both branches)

`unity-assets.sh <apk> <out>` wraps **AssetRipper**
(https://github.com/AssetRipper/AssetRipper). Extracts textures, sprites, UI
atlases, fonts, audio, shaders, **scenes, prefabs** → the game's design system.

## Graceful degradation

If a tool is absent, its wrapper exits 3 with install guidance. The subagent
then writes a partial `unity-digest.md` and sets `RE Method: limited: unity-no-tools`.

## Legal

Extracted game art is copyrighted. Outside authorized use (own game, lawful
research), treat extracted assets as **reference only** and recreate in the same
style — do not ship them.
```

- [ ] **Step 5: Create `clone-build-spec-template.md`**

```markdown
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
```

- [ ] **Step 6: Update `re-digest-contract.md`**

Append a new section to the end of `re-digest-contract.md`:

```markdown
## Design & Unity outputs (clone-app additions)

Beyond the three RE files, the Phase 2 subagent ALSO writes:

- `$WORK/design-tokens.json` + `$WORK/design-digest.md` — from
  `extract-design.py` on the decompile root (standard apps). Schema and
  confidence rules: see `design-capture-guide.md`.
- For Unity builds (`detect-unity.sh` → `il2cpp`/`mono`): `$WORK/unity-digest.md`
  (C# type model + netcode) and `$WORK/game-assets/` + `manifest.json` (via
  `il2cpp-dump.sh`/`ilspycmd` + `unity-assets.sh`). See `unity-re-guide.md`.

The subagent returns the short `design-summary` (and `unity-summary` when Unity)
plus these paths — never raw resources, sources, or assets.

### RE Method addition
| Value | Meaning |
|---|---|
| `limited: unity-no-tools` | Unity build but Il2CppInspectorRedux/AssetRipper absent — partial digest, assets/types may be empty. |
```

- [ ] **Step 7: Update `report-template.md`**

In `report-template.md`, insert a new section after section 4 ("Feature List")
and renumber the rest is NOT required — just add these two sections before
"## 5. Effort Estimate":

```markdown
## 4a. Design System (Detected)
- Palette: {key colors} · Type: {fonts + scale} · Theme: {light/dark}
- Confidence: {high/med/low} (source: APK res + {n} Play screenshots)
- Full tokens: `$WORK/design-tokens.json`; screenshots: `$WORK/screenshots/`

## 4b. Game Assets (if Unity)
- Build type: {il2cpp/mono} · Type model: `$WORK/unity-digest.md`
- Extracted assets: `$WORK/game-assets/` ({n} sprites, {n} scenes, …)
- Omit this section entirely for non-Unity apps.
```

- [ ] **Step 8: Run test to verify it passes**

Run: `bash plugins/clone-app/tests/test-references-content.sh`
Expected: PASS — all `has` checks PASS, exit 0.

- [ ] **Step 9: Commit**

```bash
git add plugins/clone-app/skills/clone-app/references/ \
        plugins/clone-app/tests/test-references-content.sh
git commit -m "docs(clone-app): design-capture, unity-re, build-spec rubrics + contract/report updates"
```

---

### Task 6: wire the new phases into `SKILL.md`

**Files:**
- Modify: `plugins/clone-app/skills/clone-app/SKILL.md`
- Test: `plugins/clone-app/tests/test-skill-phases.sh`

**Interfaces:**
- Consumes: every script/reference from Tasks 1-5 (by path/name).
- Produces: the orchestration prose. No code interface; verified by content grep.

- [ ] **Step 1: Write the failing content test**

Create `plugins/clone-app/tests/test-skill-phases.sh`:

```bash
#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$HERE/../skills/clone-app/SKILL.md"
fail=0
has() {
  if grep -qF "$1" "$SKILL"; then echo "PASS: SKILL has '$1'"
  else echo "FAIL: SKILL missing '$1'"; fail=1; fi
}

has "extract-design.py"
has "detect-unity.sh"
has "il2cpp-dump.sh"
has "unity-assets.sh"
has "design-tokens.json"
has "screenshots/"
has "## Phase 8"
has "clone-build-spec.md"
has "clone-build-spec-template.md"
has "unity-re-guide.md"
has "design-capture-guide.md"

exit $fail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bash plugins/clone-app/tests/test-skill-phases.sh`
Expected: FAIL — none of the new strings present yet.

- [ ] **Step 3: Extend Phase 2b (subagent instructions)**

In `SKILL.md`, in the Phase 2b numbered subagent instructions, after step 1
("Run RE per branch.") insert a new step (renumber the following steps +1):

```markdown
2. **Detect Unity & capture design.** After decompile:
   - `UNITY="$(bash "$RE_DIR/../../clone-app/skills/clone-app/scripts/detect-unity.sh" "$APK")"`
     — but resolve clone-app's own scripts via `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`
     (the subagent is told this dir). Use that dir below as `$CA`.
   - **Non-Unity:** run
     `python3 "$CA/extract-design.py" "$WORK/output" --package "$PKG" --out "$WORK/design-tokens.json" --digest "$WORK/design-digest.md"`
     per `design-capture-guide.md`.
   - **Unity (`il2cpp`):** locate `libil2cpp.so` + `global-metadata.dat` under
     `$WORK/output` (or unzip from `$APK`); run
     `bash "$CA/il2cpp-dump.sh" <so> <metadata> "$WORK/unity-out"` and
     `bash "$CA/unity-assets.sh" "$APK" "$WORK/game-assets"`; write
     `$WORK/unity-digest.md` (type model + netcode) per `unity-re-guide.md`.
   - **Unity (`mono`):** `ilspycmd` the `Managed/*.dll`, plus `unity-assets.sh`;
     write `$WORK/unity-digest.md`.
   - If a Unity tool exits 3 (missing), continue with a partial digest and set
     `RE Method: limited: unity-no-tools`.
```

Update Phase 2b's final "Write"/"Return" steps to also produce
`design-tokens.json`/`design-digest.md` (+ `unity-digest.md`/`game-assets/` when
Unity) and return a short `design-summary` (and `unity-summary`) per
`re-digest-contract.md` — never raw resources/sources/assets. Tell the subagent
its clone-app scripts dir is `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/scripts/`
(pass it explicitly).

- [ ] **Step 4: Extend Phase 3 (download screenshots)**

In `SKILL.md` Phase 3, after the `scrape-play-store.py` call, add:

```markdown
Download the screenshots for visual ground truth:
```bash
mkdir -p "$WORK/screenshots"
python3 - "$WORK/play.json" "$WORK/screenshots" <<'PY'
import json, sys, os, urllib.request
play, outdir = sys.argv[1], sys.argv[2]
urls = (json.load(open(play)).get("screenshot_urls") or [])
man = []
for i, u in enumerate(urls, 1):
    dest = os.path.join(outdir, f"{i:02d}.png")
    try:
        urllib.request.urlretrieve(u, dest); man.append({"order": i, "url": u, "path": dest})
    except Exception as e:
        print(f"WARN: screenshot {i} failed: {e}", file=sys.stderr)
json.dump(man, open(os.path.join(outdir, "manifest.json"), "w"), indent=2)
print(f"saved {len(man)} screenshots")
PY
```
If `screenshot_urls` is null/empty (layout change), note it and rely on
`design-tokens.json` + a web image search for visual reference.
```

- [ ] **Step 5: Extend Phase 6 (report) + strengthen legal note**

In Phase 6 prose, add a sentence: after filling the report, also fill the new
"Design System" (and, for Unity, "Game Assets") sections from
`design-tokens.json` / `unity-digest.md` per `report-template.md`.

In the "## Legal note" block near the top, append:

```markdown
Pixel-perfect cloning and extracting copyrighted assets (especially game art via
AssetRipper) is high-risk. Proceed only for authorized use; the build spec
recreates assets in the same style and treats extracted assets as reference, not
ship-ready, outside authorized contexts.
```

- [ ] **Step 6: Add Phase 8 + renumber the decision gate**

Rename the current "## Phase 7: Decision Gate" to keep Phase 7 as the gate, and
change its **Yes** branch to point at Phase 8 instead of directly invoking
writing-plans. Then add Phase 8 after it:

```markdown
## Phase 8: Assemble the Clone Build Spec

Read `${CLAUDE_PLUGIN_ROOT}/skills/clone-app/references/clone-build-spec-template.md`.
Assemble `$WORK/clone-build-spec.md` filling every section from the artifacts:
- §2 from `$WORK/design-tokens.json` (+ `design-digest.md`),
- §3 one entry per screen, each paired with `$WORK/screenshots/NN.png`,
- §5 from `$WORK/payloads.json`, §6 data model from the RE digest,
- §7 asset inventory from `$WORK/output` (or `$WORK/game-assets/` for Unity),
- §8 acceptance criteria per screen + flow,
- §10 absolute paths to every `$WORK/` artifact.
Use the **Game variant** sections when RE Method indicated Unity.

Then invoke `superpowers:writing-plans`, passing `$WORK/clone-build-spec.md` as
the spec (NOT the feasibility report). The build spec is the single standalone
input — a fresh session with it + `$WORK/` can build the clone.
```

- [ ] **Step 7: Update the Error Handling Summary table**

Add rows to the Phase-final error table:

```markdown
| Unity build detected | run IL2CPP/Mono branch + AssetRipper |
| Unity tool missing | continue, partial digest, RE Method `limited: unity-no-tools` |
| No screenshots on Play | note it, rely on design-tokens + web image search |
```

- [ ] **Step 8: Run test to verify it passes**

Run: `bash plugins/clone-app/tests/test-skill-phases.sh`
Expected: PASS — all `has` checks PASS, exit 0.

- [ ] **Step 9: Commit**

```bash
git add plugins/clone-app/skills/clone-app/SKILL.md \
        plugins/clone-app/tests/test-skill-phases.sh
git commit -m "feat(clone-app): wire design capture, Unity branch, Phase 8 build spec into SKILL"
```

---

### Task 7: smoke-structure coverage + full suite green

**Files:**
- Modify: `plugins/clone-app/tests/smoke-structure.sh`

**Interfaces:**
- Consumes: all files from Tasks 1-6.
- Produces: structural guarantee that new scripts/references exist (+ executable for `.sh`).

- [ ] **Step 1: Add new files to `smoke-structure.sh`**

In `smoke-structure.sh`, extend the executable-scripts loop (line 13) to include
the new bash scripts:

```bash
for s in extract-package.sh download-apk.sh resolve-re-scripts.sh detect-unity.sh il2cpp-dump.sh unity-assets.sh; do
  must_exist "$P/skills/clone-app/scripts/$s"; must_exec "$P/skills/clone-app/scripts/$s"
done
```

Extend the python-scripts loop (line 16) to include `extract-design.py`:

```bash
for s in scrape-play-store.py check-appstore.py extract-design.py; do
  must_exist "$P/skills/clone-app/scripts/$s"
done
```

Extend the references loop (line 19) to include the three new rubrics:

```bash
for r in stack-recommendation-guide effort-estimation-guide infra-cost-guide report-template re-digest-contract design-capture-guide unity-re-guide clone-build-spec-template; do
  must_exist "$P/skills/clone-app/references/$r.md"
done
```

- [ ] **Step 2: Make the new bash scripts executable**

```bash
chmod +x plugins/clone-app/skills/clone-app/scripts/detect-unity.sh \
         plugins/clone-app/skills/clone-app/scripts/il2cpp-dump.sh \
         plugins/clone-app/skills/clone-app/scripts/unity-assets.sh
```

- [ ] **Step 3: Run the smoke test**

Run: `bash plugins/clone-app/tests/smoke-structure.sh`
Expected: PASS — every `must_exist`/`must_exec` PASS, exit 0.

- [ ] **Step 4: Run the full clone-app suite**

Run: `bash plugins/clone-app/tests/run-all.sh`
Expected: `ALL TESTS PASSED`, exit 0. (run-all auto-globs the new `test-*.sh`/`test-*.py`.)

- [ ] **Step 5: Verify the upstream tree is untouched**

Run: `git status --porcelain plugins/android-reverse-engineering/`
Expected: empty output (nothing printed).

- [ ] **Step 6: Validate JSON manifests still parse**

Run:
```bash
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json')); json.load(open('plugins/clone-app/.claude-plugin/plugin.json'))"
```
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add plugins/clone-app/tests/smoke-structure.sh \
        plugins/clone-app/skills/clone-app/scripts/detect-unity.sh \
        plugins/clone-app/skills/clone-app/scripts/il2cpp-dump.sh \
        plugins/clone-app/skills/clone-app/scripts/unity-assets.sh
git commit -m "test(clone-app): smoke coverage for design + Unity scripts and rubrics"
```

---

## Self-Review

**Spec coverage:**
- Design token capture → Task 1. ✓
- Play screenshots + description → Task 3. ✓
- Unity detection / IL2CPP / Mono / assets → Tasks 2, 4; wired in Task 6. ✓
- design-capture-guide / unity-re-guide / clone-build-spec-template → Task 5. ✓
- re-digest-contract + report-template updates → Task 5. ✓
- SKILL Phase 2/3/6/8 + legal + error table → Task 6. ✓
- Standalone Clone Build Spec feeding writing-plans → Task 6 Phase 8. ✓
- Tests + smoke + upstream-untouched + JSON valid → Tasks 1-7. ✓

**Placeholder scan:** no TBD/TODO; every code step has full content. The two .NET
CLI flag lines in Task 4 are marked as version-dependent (only the tool-missing
path is tested) — acceptable, not a placeholder.

**Type consistency:** `design-tokens.json` schema (Task 1) — keys
`colors/dimens/typography/shapes/theme/icon/layouts`, each `{values,confidence}`
— matches its use in the build-spec template (Task 5) and Phase 8 (Task 6).
`detect-unity.sh` output values `il2cpp|mono|none` (Task 2) match the branch
names in `unity-re-guide.md` and SKILL Phase 2 (Tasks 5, 6). Wrapper exit codes
2/3 consistent between Task 4 scripts and their test.
