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
    gi = open(os.path.join(proj, ".gitignore")).read()
    check(".gitignore keeps captures, logs and extracted art out", "captures/" in gi and "/Assets/Extracted/" in gi)
    tdir = json.load(open(os.path.join(proj, "Docs", "project.json")))["teslim_dir"]
    check("delivery folder outside the repo", tdir.startswith(teslim_root) and os.path.exists(os.path.join(tdir, "TESLIMLER.md")))

    old = os.path.join(tmp, "Eski")
    os.makedirs(os.path.join(old, "Assets", "Editor"))
    open(os.path.join(old, "Assets", "Editor", "ImportExtracted.cs"), "w").write("// project's own copy\n")
    code, out = run("scaffold-project.py", old, "--game", "Eski", "--package", "com.a.c", "--teslim-root", teslim_root, "--no-git")
    check("kit already in the project is not copied twice",
          not os.path.exists(os.path.join(old, "Assets", "Editor", "CloneKit", "ImportExtracted.cs"))
          and os.path.exists(os.path.join(old, "Assets", "Editor", "CloneKit", "ImportUI.cs")))
    check("an outdated project copy is reported", "differs from clone-app's current kit" in out)

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

    code, out = run("tasks.py", "bayat", "--project", proj)
    check("bayat without git: says it cannot check, does not block", code == 0 and "izi yok" in out)

    code, out = run("tasks.py", "set", "T001", "bitti", "--project", proj)
    code, out = run("tasks.py", "add", "Yeni iş", "--faz", "F0 Kararlar", "--project", proj)
    md = open(os.path.join(proj, "Docs", "TASKS.md")).read()
    lines = md.splitlines()
    i_new = next(i for i, l in enumerate(lines) if "| Yeni iş |" in l)
    check("add lands inside its phase table", lines[i_new - 1].startswith("| T00") and "## F1" in "\n".join(lines[i_new:]))
    code, out = run("tasks.py", "next", "--project", proj)
    check("next moves on to T002", "T002" in out)
    check("bad status refused", run("tasks.py", "set", "T002", "yarim", "--project", proj)[0] != 0)

    # stale delivery: the code changes after the evidence was made
    g = lambda *c: subprocess.run(["git", "-C", proj, *c], capture_output=True, text=True)
    g("init", "-q", "-b", "main"); g("add", "-A")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    run("tasks.py", "set", "T002", "bitti", "--project", proj)
    code, out = run("tasks.py", "next", "--project", proj)
    t3 = next(l.split()[0] for l in run("tasks.py", "list", "--open", "--project", proj)[1].splitlines() if "sürüyor" in l)
    src = os.path.join(proj, "Assets", "Ekran.cs")
    os.makedirs(os.path.dirname(src), exist_ok=True)
    open(src, "w").write("v1")
    run("teslim.py", t3, "ekran", ev, "--project", proj)
    code, out = run("tasks.py", "bayat", "--project", proj)
    check("fresh delivery is güncel", code == 0 and f"{t3}: güncel" in out)
    open(src, "w").write("v2")
    code, out = run("tasks.py", "bayat", "--project", proj)
    check("changed file after delivery -> BAYAT, exit 1, names the file",
          code == 1 and "BAYAT" in out and "Assets/Ekran.cs" in out)
    open(src, "w").write("v1")
    check("reverting the change makes it güncel again", run("tasks.py", "bayat", "--project", proj)[0] == 0)

    # parallel task in its own worktree; the task book stays in the main checkout
    g("switch", "-q", "main")
    os.makedirs(os.path.join(proj, "Library"), exist_ok=True)
    open(os.path.join(proj, "Library", "cache.bin"), "w").write("x")
    run("tasks.py", "next", "--no-branch", "--project", proj)
    code, out = run("tasks.py", "next", "--project", proj)
    check("plain next still refuses a second running task, points to --worktree", "--worktree" in out)
    code, out = run("tasks.py", "next", "--worktree", "--project", proj)
    wt = next((l.split(": ", 1)[1] for l in out.splitlines() if l.startswith("Çalışma klasörü: ")), "")
    t4 = out.split("Sıradaki iş: ")[1].split(" ")[0] if "Sıradaki iş: " in out else ""
    check("next --worktree opens ../<repo>-<branch> beside the project",
          code == 0 and os.path.isdir(wt) and os.path.dirname(wt) == os.path.realpath(tmp) or os.path.dirname(wt) == tmp)
    if sys.platform == "darwin":
        check("Library cloned into the worktree", os.path.exists(os.path.join(wt, "Library", "cache.bin")))
    w = lambda *c: subprocess.run(["git", "-C", wt, *c], capture_output=True, text=True)
    code, out = run("tasks.py", "list", "--open", "--project", wt)
    check("run from the worktree, the book is the main checkout's; the worktree stays clean",
          out.count("sürüyor") == 2 and w("status", "--porcelain").stdout == "")
    wsrc = os.path.join(wt, "Assets", "Yeni.cs")
    os.makedirs(os.path.dirname(wsrc), exist_ok=True)
    open(wsrc, "w").write("v1")
    run("teslim.py", t4, "paralel", ev, "--project", wt)
    check("delivery fingerprints the worktree's code", f"{t4}: güncel" in run("tasks.py", "bayat", "--project", proj)[1])
    open(wsrc, "w").write("v2")
    check("a change in the worktree makes it BAYAT", f"{t4}: BAYAT" in run("tasks.py", "bayat", "--project", proj)[1])
    w("add", "-A"); w("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "work")
    branch = w("branch", "--show-current").stdout.strip()
    code, out = run("tasks.py", "temizle", "--project", proj)
    check("unmerged worktree is not offered for deletion", "silinebilir" not in out)
    m = g("-c", "user.name=t", "-c", "user.email=t@t", "merge", "--no-ff", "-qm", "merge", branch)
    check("worktree branch merges into a main whose book is dirty (branch never touched it)", m.returncode == 0)
    code, out = run("tasks.py", "temizle", "--yes", "--project", proj)
    check("merged but not bitti in the book: kept", "KALIYOR" in out and os.path.isdir(wt))
    sub = os.path.join(wt, "Assets")
    check("tasks.py works from a subfolder of a worktree", run("tasks.py", "list", "--project", sub)[0] == 0)
    run("tasks.py", "set", t4, "bitti", "--project", proj)
    code, out = run("tasks.py", "next", "--worktree", "--project", proj)
    fresh = next((l.split(": ", 1)[1] for l in out.splitlines() if l.startswith("Çalışma klasörü: ")), "")
    code, out = run("tasks.py", "temizle", "--project", proj)
    check("merged + bitti worktree is offered, not deleted without --yes", "silinebilir" in out and os.path.isdir(wt))
    open(os.path.join(wt, "yarim.txt"), "w").write("unsaved")
    code, out = run("tasks.py", "temizle", "--yes", "--project", proj)
    check("a merged worktree with unsaved work is kept", "KALIYOR" in out and os.path.isdir(wt))
    check("a fresh worktree with no commits (git calls it merged) is never deleted", os.path.isdir(fresh))
    os.remove(os.path.join(wt, "yarim.txt"))
    code, out = run("tasks.py", "temizle", "--yes", "--project", proj)
    check("temizle --yes removes it and reports df before/after", not os.path.isdir(wt) and "Boş yer:" in out)
    check("...and still leaves the fresh one", os.path.isdir(fresh))
    check("disk under threshold exits 1", run("tasks.py", "disk", "--min-gb", "1e9", "--project", proj)[0] == 1)
    check("disk over threshold exits 0", run("tasks.py", "disk", "--min-gb", "0", "--project", proj)[0] == 0)

    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
