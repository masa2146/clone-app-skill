#!/usr/bin/env python3
"""Lay out a game project on day one — `/clone-build kur`. Stdlib only.

    scaffold-project.py <project-dir> --game "<Name>" --package com.x.y
        [--source clone|original] [--work <clone-app work dir>]
        [--teslim-root ~/GameWork] [--unity <Unity binary>] [--no-git]

Writes CLAUDE.md, Docs/TASKS.md (the lifecycle filtered by source, plus the
build plan's tasks when --work has one), Docs/tasks/, Docs/KARARLAR.md,
Docs/project.json, a Unity .gitignore, and the dated delivery folder outside the
repo. A clone also gets clone-app's Unity kit (import, UI rebuild, verify) and,
with --work, the extraction's bootstrap docs. Never overwrites a file that
exists: a resumed project keeps what it has.
"""
import argparse
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "..", "templates")
sys.path.insert(0, HERE)
import tasks  # noqa: E402

GATES = """Kapılar: G0 başlangıç (kararlar yazılı, düzen kurulu, telefonda boş sahne) · G1 çıkarım
doğrulama (check-extraction yeşil) · G2 yön (sadakat, sanat, araç, lisans kararları) · G3 görünüm
kilidi · G4 varlık çözümü (çizmeden önce arandı) · G5 kural kaynağı · G6 ölçü aleti kalibrasyonu ·
G7 tarama (bütün seviyeler) · G8 seviye hakemi · G9 görsel teslim (karşılaştırma, tam yollar) ·
G10 regresyon testi · G12 cihaz QA · G13 yayın (paket taraması, lisanslar). G11 birleştirme ve
G14 oturum sonu her işte koşar."""

GITIGNORE = """# Unity
/[Ll]ibrary/
/[Tt]emp/
/[Oo]bj/
/[Bb]uild/
/[Bb]uilds/
/[Ll]ogs/
/[Uu]ser[Ss]ettings/
/[Mm]emoryCaptures/
/[Rr]ecordings/
*.csproj
*.sln
*.pidb
*.userprefs
*.apk
*.aab
*.unitypackage
.vs/
.idea/
.DS_Store
# runs, captures and deliveries never enter git
*.log
mono_crash*
captures/
compare/
video_clip/
*.mp4
TestResults*.xml
__pycache__/
"""

# a clone's imported reference art is rebuilt from the extraction by ImportExtracted /
# ImportUI; committed once, it stays in the history and the repo can never be pushed
CLONE_IGNORE = """# extracted reference, rebuilt by CloneKit — never in git
/Assets/Extracted/
/Assets/Extracted.meta
/Assets/ExtractedUI/
/Assets/ExtractedUI.meta
"""

UNITY_DEFAULT = "/Applications/Unity/Hub/Editor/*/Unity.app/Contents/MacOS/Unity"


def write_new(path, text):
    """Write unless the file exists; returns True when written."""
    if os.path.exists(path):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    return True


def cell(s):
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def lifecycle_rows(source):
    keep = {"*", "K"} if source == "clone" else {"*", "Ö"}
    with open(os.path.join(TEMPLATES, "lifecycle.tsv")) as f:
        return [r for r in csv.DictReader(f, delimiter="\t") if r["kaynak"] in keep]


def plan_rows(work):
    """Tasks from clone-build's build-plan.json, as P-<id> rows of their own phase."""
    for p in (os.path.join(work, "deliverables", "build-plan.json"),
              os.path.join(work, "..", "deliverables", "build-plan.json")):
        if os.path.exists(p):
            with open(p) as f:
                return [t for t in json.load(f).get("tasks", []) if t.get("status") != "done"]
    return []


def tasks_md(game, source, work):
    out = [f"# {game} — İşler", "",
           "Tek iş listesi. Elle değil `tasks.py` ile güncellenir (`/task sonraki`, `/task bitir <ID>`);",
           "ayrıntı dosyası iş başlarken `Docs/tasks/` altına yazılır.", "",
           tasks.NOW_START, tasks.NOW_END, "", GATES]
    faz = None
    for r in lifecycle_rows(source):
        if r["faz"] != faz:
            faz = r["faz"]
            out += ["", f"## {faz}", "", tasks.HEADER, tasks.SEP]
        # T004 is this scaffold itself: done the moment the list exists
        status = "bitti" if r["id"] == "T004" else "bekliyor"
        out.append(f"| {r['id']} | {cell(r['is'])} | {status} | {cell(r['kapi'])} | {cell(r['bitti_sayilir'])} |  |")
    plan = plan_rows(work) if work else []
    if plan:
        out += ["", "## P Yapım planı (build-plan.json)", "", tasks.HEADER, tasks.SEP]
        for t in plan:
            gate = (t.get("gate") or {}).get("kind", "—")
            out.append(f"| P-{cell(t['id'])} | {cell(t.get('title'))} | bekliyor | {gate} | "
                       f"{cell(t.get('done_when') or t.get('acceptance') or 'gate RESULT: PASS')} |  |")
    return "\n".join(out) + "\n"


def find_clone_app():
    """clone-app's scripts dir: sibling plugin in a checkout, else the newest cached install."""
    sib = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "clone-app", "skills", "clone-app", "scripts"))
    if os.path.isdir(sib):
        return sib
    cached = sorted(glob.glob(os.path.expanduser(
        "~/.claude/plugins/cache/*/clone-app/*/skills/clone-app/scripts")), key=os.path.getmtime)
    return cached[-1] if cached else None


def copy_new(src, dst, done):
    if os.path.exists(src) and not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
        done.append(dst)


def install_clone_kit(project, done):
    ca = find_clone_app()
    if not ca:
        print("WARN: clone-app plugin not found — Unity kit not copied", file=sys.stderr)
        return
    t = os.path.join(ca, "templates")
    have = {os.path.basename(p) for p in glob.glob(os.path.join(project, "Assets", "**", "*.cs"), recursive=True)}
    # runtime component: must sit outside an Editor folder or prefabs lose it
    kit = [(n, ("Editor", "CloneKit")) for n in ("ImportExtracted.cs", "ImportUI.cs", "VerifyImport.cs", "RenderLayout.cs")]
    for name, sub in kit + [("ExtractedNode.cs", ("CloneKit",))]:
        if name in have:  # a second copy anywhere under Assets is a duplicate class: CS0101
            mine = glob.glob(os.path.join(project, "Assets", "**", name), recursive=True)[0]
            with open(mine, "rb") as f, open(os.path.join(t, name), "rb") as g:
                same = f.read() == g.read()
            print(f"WARN: {name} already in Assets — kept the project's copy"
                  + ("" if same else f"; it differs from clone-app's current kit, replace it with {os.path.join(t, name)} to get its fixes"),
                  file=sys.stderr)
            continue
        copy_new(os.path.join(t, name), os.path.join(project, "Assets", *sub, name), done)
    copy_new(os.path.join(ca, "unity-batch.sh"), os.path.join(project, "tools", "unity-batch.sh"), done)


def install_bootstrap(project, work, done):
    ex = os.path.join(work, "extracted") if os.path.isdir(os.path.join(work, "extracted")) else work
    root = os.path.dirname(ex) if os.path.basename(ex) == "extracted" else work
    copy_new(os.path.join(root, "deliverables", "bootstrap", "CLAUDE.md"), os.path.join(project, "Docs", "KAYNAK.md"), done)
    copy_new(os.path.join(ex, "asset-guide"), os.path.join(project, "Docs", "assets"), done)
    copy_new(os.path.join(ex, "REFERENCE-SOURCES.md"), os.path.join(project, "Docs", "REFERENCE-SOURCES.md"), done)
    copy_new(os.path.join(root, "deliverables", "clone-build-spec.md"), os.path.join(project, "Docs", "clone-build-spec.md"), done)
    copy_new(os.path.join(root, "deliverables", "reconstruction"), os.path.join(project, "Docs", "reconstruction"), done)


def unity_binary(unity):
    if unity != "auto":
        return unity
    found = sorted(glob.glob(UNITY_DEFAULT))
    if not found:
        sys.exit("ERROR: no Unity editor found; pass --unity <binary>")
    return found[-1]


def compile_check(project, unity):
    """Open the project once: the kit compiles and its .meta files exist before the first commit."""
    log = os.path.join(tempfile.gettempdir(), f"compile-check-{os.getpid()}.log")
    subprocess.run([unity, "-batchmode", "-quit", "-projectPath", project, "-logFile", log])
    with open(log, errors="replace") as f:
        errors = sorted({l.strip() for l in f if "error CS" in l})
    if errors:
        sys.exit("ERROR: the project does not compile:\n" + "\n".join(errors[:10]) + f"\nlog: {log}")


def create_unity(project, unity):
    if os.path.isdir(os.path.join(project, "Assets")) and os.path.exists(os.path.join(project, "ProjectSettings")):
        return
    # the log stays out of the project folder: -createProject wants it empty
    log = os.path.join(tempfile.gettempdir(), f"create-project-{os.getpid()}.log")
    r = subprocess.run([unity, "-batchmode", "-quit", "-createProject", project, "-logFile", log])
    if r.returncode != 0:
        sys.exit(f"ERROR: Unity -createProject failed, see {log}")
    # a fresh -createProject has no uGUI; every UI script (and TMP) needs it
    mf = os.path.join(project, "Packages", "manifest.json")
    with open(mf) as f:
        m = json.load(f)
    m.setdefault("dependencies", {}).setdefault("com.unity.ugui", "2.0.0")
    with open(mf, "w") as f:
        json.dump(m, f, indent=2)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("project")
    ap.add_argument("--game", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--source", choices=("clone", "original"), default="clone")
    ap.add_argument("--work", help="clone-app working dir (or its extracted/)")
    ap.add_argument("--teslim-root", default="~/GameWork")
    ap.add_argument("--unity", nargs="?", const="auto", help="create the Unity project (binary path or auto)")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)

    project = os.path.abspath(os.path.expanduser(a.project))
    os.makedirs(project, exist_ok=True)
    unity = unity_binary(a.unity) if a.unity else None
    if unity:
        create_unity(project, unity)
    gslug = tasks.slug(a.game, 60)
    teslim_dir = os.path.join(os.path.abspath(os.path.expanduser(a.teslim_root)), gslug, "teslim")
    work = os.path.abspath(os.path.expanduser(a.work)) if a.work else None
    done = []

    if a.source == "clone":
        install_clone_kit(project, done)
        if work:
            install_bootstrap(project, work, done)
    kaynak = os.path.exists(os.path.join(project, "Docs", "KAYNAK.md"))
    clone_block = ""
    if a.source == "clone":
        clone_block = ("\n## Klon kuralları\n\n"
                       f"- Kaynak oyunun çıkarımı: `{work or '<clone-app work dir>'}` — salt okunur, depoya kopyalanmaz.\n"
                       "- Bir şeyi çizmeden önce çıkarımda ara (`Docs/assets/ASSET-INDEX.tsv`). Kimlik `<dosya>:<path_id>`'dir;\n"
                       "  ada göre birleştirme yapılmaz, aynı adlı iki nesne olabilir.\n"
                       "- Unity kiti `Assets/Editor/CloneKit/`: ImportExtracted (3D), ImportUI (ekranlar), VerifyImport\n"
                       "  (Python beklentisiyle karşılaştırma). Unity'yi `tools/unity-batch.sh` ile çalıştır.\n"
                       "- `Assets/Extracted/` ve `Assets/ExtractedUI/` kitle çıkarımdan yeniden kurulur, git'e girmez\n"
                       "  (`.gitignore`'da). Bir kez commit'lenen çıkarılmış dosya geçmişte kalır, depo bir daha gönderilemez.\n"
                       "- Bilinen tuzaklar: clone-app SKILL.md \"Known traps\".\n"
                       "- Çıkarılmış dosya mağaza paketine ve GitHub'a girmez; yayından önce paket taraması 0 göstermeli.\n"
                       + ("\n@Docs/KAYNAK.md\n" if kaynak else ""))
    source_line = ("Var olan bir oyundan yola çıkan klon; mekanik birebir, sanat ve ses bizim."
                   if a.source == "clone" else "Özgün oyun.")
    compare = ("- Görsel ya da mekanik her değişiklik karşılaştırmayla teslim edilir: sol BİZİM, sağ REFERANS,\n"
               "  aynı bölüm, aynı an." if a.source == "clone" else
               "- Görsel ya da mekanik her değişiklik önce/sonra çekimiyle teslim edilir.")
    with open(os.path.join(TEMPLATES, "CLAUDE.md.tmpl")) as f:
        claude = f.read().format(game=a.game, package=a.package, source_line=source_line,
                                 teslim_dir=teslim_dir, compare_line=compare, clone_block=clone_block)

    files = {
        "CLAUDE.md": claude,
        "Docs/TASKS.md": tasks_md(a.game, a.source, work),
        "Docs/KARARLAR.md": f"# {a.game} — Kararlar\n\nNumaralı, tarihli; değişen karar silinmez, üstü çizilip yenisi yazılır.\n\n"
                            "| # | Tarih | Karar | Gerekçe |\n|---|---|---|---|\n",
        "Docs/project.json": json.dumps({"game": a.game, "slug": gslug, "package": a.package, "source": a.source,
                                         "work": work, "teslim_dir": teslim_dir}, ensure_ascii=False, indent=2) + "\n",
        "Docs/tasks/.gitkeep": "",
    }
    for rel, text in files.items():
        if write_new(os.path.join(project, rel), text):
            done.append(os.path.join(project, rel))
    gi = os.path.join(project, ".gitignore")
    have = open(gi).read().splitlines() if os.path.exists(gi) else []
    wanted = GITIGNORE + (CLONE_IGNORE if a.source == "clone" else "")
    missing = [l for l in wanted.splitlines() if l and l not in have]
    if missing:
        with open(gi, "a") as f:
            f.write(("\n" if have else "") + "\n".join(missing) + "\n")
        done.append(gi)
    if write_new(os.path.join(teslim_dir, "TESLIMLER.md"), f"# {a.game} — Teslimler\n\nEn yeni üstte.\n\n"):
        done.append(os.path.join(teslim_dir, "TESLIMLER.md"))
    lines, ts = tasks.load(project)
    tasks.save(project, lines, ts)
    if unity:
        compile_check(project, unity)

    if not a.no_git and not os.path.isdir(os.path.join(project, ".git")):
        subprocess.run(["git", "init", "-q", "-b", "main", project], check=True)
        subprocess.run(["git", "-C", project, "add", "-A"], check=True)
        subprocess.run(["git", "-C", project, "commit", "-q", "-m", f"chore: {a.game} project scaffold"], check=True)

    print(f"Kuruldu: {project}\nİş sayısı: {len(ts)}\nTeslim klasörü: {teslim_dir}")
    for p in done:
        print(f"  + {p}")
    print("Sıradaki adım: /task sonraki")
    return 0


if __name__ == "__main__":
    sys.exit(main())
