#!/usr/bin/env python3
"""scaffold-project.py -> tasks.py next/set/add -> teslim.py, on a temp project."""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "skills", "clone-build", "scripts")


def run(script, *args, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(S, script), *args], capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout + r.stderr


def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    tmp = tempfile.mkdtemp()
    work = os.path.join(tmp, "work")
    os.makedirs(os.path.join(work, "deliverables", "bootstrap"))
    os.makedirs(os.path.join(work, "extracted", "asset-guide"))
    open(os.path.join(work, "deliverables", "bootstrap", "CLAUDE.md"), "w").write("# bootstrap\n")
    open(os.path.join(work, "extracted", "asset-guide", "ASSET-INDEX.tsv"), "w").write("name\n")
    json.dump({"tasks": [{"id": "screen-menu", "title": "Build scene: Menu | main", "gate": {"kind": "visual-diff"},
                          "status": "pending"},
                         {"id": "old", "title": "done one", "status": "done"}]},
              open(os.path.join(work, "deliverables", "build-plan.json"), "w"))
    proj = os.path.join(tmp, "Oyun")
    teslim_root = os.path.join(tmp, "GW")

    code, out = run("scaffold-project.py", proj, "--game", "Deneme Oyun", "--package", "com.a.b",
                    "--work", work, "--teslim-root", teslim_root, "--no-git")
    check("scaffold exits 0", code == 0)
    md = open(os.path.join(proj, "Docs", "TASKS.md")).read()
    check("clone keeps K rows, drops Ö rows", "| T001 |" in md and "| T007 |" in md and "| T015 |" not in md)
    check("build plan rows added, done ones skipped", "| P-screen-menu |" in md and "P-old" not in md)
    ids = [l.split("\t")[0] for l in open(os.path.join(S, "..", "templates", "lifecycle.tsv")).read().splitlines()[1:] if l]
    check("lifecycle ids are unique", len(ids) == len(set(ids)))
    check("T004 (the scaffold itself) starts done", "| T004 | `/clone-build kur` | bitti |" in md)
    check("pipe in a title cannot break the table", "Menu / main" in md)
    claude = open(os.path.join(proj, "CLAUDE.md")).read()
    check("CLAUDE.md starts sessions with /task sonraki", "/task sonraki" in claude and "@Docs/KAYNAK.md" in claude)
    check("bootstrap copied", os.path.exists(os.path.join(proj, "Docs", "KAYNAK.md"))
          and os.path.exists(os.path.join(proj, "Docs", "assets", "ASSET-INDEX.tsv")))
    check("Unity kit copied, runtime part outside Editor",
          os.path.exists(os.path.join(proj, "Assets", "Editor", "CloneKit", "ImportExtracted.cs"))
          and os.path.exists(os.path.join(proj, "Assets", "CloneKit", "ExtractedNode.cs")))
    check(".gitignore keeps captures and logs out", "captures/" in open(os.path.join(proj, ".gitignore")).read())
    tdir = json.load(open(os.path.join(proj, "Docs", "project.json")))["teslim_dir"]
    check("delivery folder outside the repo", tdir.startswith(teslim_root) and os.path.exists(os.path.join(tdir, "TESLIMLER.md")))

    open(os.path.join(proj, "CLAUDE.md"), "a").write("own line\n")
    run("scaffold-project.py", proj, "--game", "Deneme Oyun", "--package", "com.a.b", "--no-git")
    check("re-run never overwrites", "own line" in open(os.path.join(proj, "CLAUDE.md")).read())

    code, out = run("tasks.py", "next", "--project", proj)
    check("next picks T001", code == 0 and "T001" in out)
    detail = [f for f in os.listdir(os.path.join(proj, "Docs", "tasks")) if f.startswith("T001")]
    check("detail file written", len(detail) == 1)
    code, out = run("tasks.py", "next", "--project", proj)
    check("next with a running task shows it, picks nothing new", "Zaten süren" in out)
    md = open(os.path.join(proj, "Docs", "TASKS.md")).read()
    check("Şu an block names the running task", "**Sürüyor:** T001" in md)

    ev = os.path.join(tmp, "Ekran Görüntüsü 1.PNG")
    open(ev, "w").write("x")
    code, out = run("teslim.py", "T001", "ilk teslim", ev, "--not", "deneme", "--project", proj)
    check("teslim exits 0", code == 0)
    check("evidence copied with an ascii name", "01_ekran-goruntusu-1.png" in out)
    check("index has the entry", "T001" in open(os.path.join(tdir, "TESLIMLER.md")).read())
    d = open(os.path.join(proj, "Docs", "tasks", detail[0])).read()
    check("task file has the paths and status teslimde", "01_ekran-goruntusu-1.png" in d and "durum: teslimde" in d)

    code, out = run("tasks.py", "set", "T001", "bitti", "--project", proj)
    code, out = run("tasks.py", "add", "Yeni iş", "--faz", "F0 Kararlar", "--project", proj)
    md = open(os.path.join(proj, "Docs", "TASKS.md")).read()
    lines = md.splitlines()
    i_new = next(i for i, l in enumerate(lines) if "| Yeni iş |" in l)
    check("add lands inside its phase table", lines[i_new - 1].startswith("| T00") and "## F1" in "\n".join(lines[i_new:]))
    code, out = run("tasks.py", "next", "--project", proj)
    check("next moves on to T002", "T002" in out)
    check("bad status refused", run("tasks.py", "set", "T002", "yarim", "--project", proj)[0] != 0)

    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
