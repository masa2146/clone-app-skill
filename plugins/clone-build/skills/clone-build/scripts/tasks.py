#!/usr/bin/env python3
"""Docs/TASKS.md — the one task list of a game project — and its detail files. Stdlib only.

    tasks.py next  [--project DIR] [--no-branch]   pick the next open task, mark it running,
                                                   open Docs/tasks/<ID>-<slug>.md, branch <id>-<slug>
    tasks.py set   <ID> <status> [--project DIR]   bekliyor | sürüyor | teslimde | bitti | beklemede
    tasks.py list  [--open] [--project DIR]
    tasks.py add   "<work>" --faz "F8 Ekranlar ve meta" [--kapi G9] [--bitti "..."] [--project DIR]
    tasks.py show  <ID> [--project DIR]
    tasks.py bayat [--project DIR]                 deliveries whose files changed since; exit 1 if any

TASKS.md is written for a person and parsed by this script: one table per phase,
columns ID | İş | Durum | Kapı | Bitti sayılır | Ayrıntı. The "Şu an" block at the
top is regenerated on every change. Details are written when a task starts (not
up front): a phase-3 task planned in week one is planned against a game that no
longer exists by week three.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata

STATUSES = ("bekliyor", "sürüyor", "teslimde", "bitti", "beklemede")
HEADER = "| ID | İş | Durum | Kapı | Bitti sayılır | Ayrıntı |"
SEP = "|---|---|---|---|---|---|"
ROW_RE = re.compile(r"^\| (T\d{3}|P-[\w.-]+) \| (.*?) \| (\w+) \| (.*?) \| (.*?) \| (.*?) \|$")
NOW_START, NOW_END = "<!-- su-an -->", "<!-- /su-an -->"


def slug(text, limit=40):
    t = unicodedata.normalize("NFKD", text.replace("ı", "i").replace("İ", "I"))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:limit].strip("-") or "is"


def tasks_path(project):
    return os.path.join(project, "Docs", "TASKS.md")


def load(project):
    """(lines, tasks) — tasks keep their line index so updates rewrite in place."""
    with open(tasks_path(project)) as f:
        lines = f.read().split("\n")
    tasks, faz = [], None
    for i, line in enumerate(lines):
        if line.startswith("## F") or line.startswith("## P"):
            faz = line[3:].strip()
        m = ROW_RE.match(line)
        if m:
            tasks.append({"line": i, "id": m.group(1), "is": m.group(2), "durum": m.group(3),
                          "kapi": m.group(4), "bitti": m.group(5), "ayrinti": m.group(6), "faz": faz})
    return lines, tasks


def row(t):
    return f"| {t['id']} | {t['is']} | {t['durum']} | {t['kapi']} | {t['bitti']} | {t['ayrinti']} |"


def save(project, lines, tasks):
    for t in tasks:
        lines[t["line"]] = row(t)
    text = "\n".join(lines)
    running = [t for t in tasks if t["durum"] == "sürüyor"]
    waiting = [t for t in tasks if t["durum"] == "teslimde"]
    nxt = next((t for t in tasks if t["durum"] == "bekliyor"), None)
    done = sum(t["durum"] == "bitti" for t in tasks)
    now = [NOW_START, "## Şu an", "",
           f"- **Sürüyor:** " + (", ".join(f"{t['id']} {t['is']}" for t in running) or "—"),
           f"- **Teslimde (onay bekliyor):** " + (", ".join(f"{t['id']} {t['is']}" for t in waiting) or "—"),
           f"- **Sıradaki:** " + (f"{nxt['id']} {nxt['is']}" if nxt else "—"),
           f"- **İlerleme:** {done}/{len(tasks)} bitti", NOW_END]
    if NOW_START in text:
        text = re.sub(re.escape(NOW_START) + r".*?" + re.escape(NOW_END), "\n".join(now), text, flags=re.S)
    with open(tasks_path(project), "w") as f:
        f.write(text)


def find(tasks, tid):
    t = next((t for t in tasks if t["id"].lower() == tid.lower()), None)
    if t is None:
        sys.exit(f"ERROR: no task {tid} in Docs/TASKS.md")
    return t


DETAIL = """---
id: {id}
is: {is_}
faz: {faz}
durum: sürüyor
dal: {branch}
kapi: {kapi}
basladi: {date}
oturum_sayisi: 1
---

# {id} — {is_}

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (if installed) —
> otherwise follow the Plan below step by step and tick each box.

## Özet
Ne yapılacak ve neden, iki cümle. Bitti sayılır: {bitti}

## Plan
**Goal:** {is_}
**Architecture:** (iki üç cümle)
**Tech Stack:** (bu işte dokunulan sistemler)

- [ ] 1. …

## Teknik
Dokunulan dosyalar, komutlar, ölçümler.

## Kontroller
Kapı: {kapi}. Her kontrolün komutu ve sonucu buraya; "geçti" yalnız komutun çıktısıyla yazılır.

## Teslim
`teslim.py {id} <kısa-ad> <dosyalar…>` çıktısındaki tam yollar.

## Sıradaki
Bu işten doğan yeni işler (`tasks.py add` ile TASKS.md'ye de girer).
"""


def cmd_next(a):
    lines, tasks = load(a.project)
    running = [t for t in tasks if t["durum"] == "sürüyor"]
    if running:
        t = running[0]
        print(f"Zaten süren iş var: {t['id']} {t['is']} -> {t['ayrinti'] or 'ayrıntı yok'}")
        return 0
    t = next((t for t in tasks if t["durum"] == "bekliyor"), None)
    if t is None:
        print("Açık iş kalmadı.")
        return 0
    name = f"{t['id']}-{slug(t['is'])}"
    rel = f"Docs/tasks/{name}.md"
    path = os.path.join(a.project, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    branch = name.lower()
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(DETAIL.format(id=t["id"], is_=t["is"], faz=t["faz"], branch=branch, kapi=t["kapi"] or "—",
                                  bitti=t["bitti"], date=datetime.date.today().isoformat()))
    t["durum"], t["ayrinti"] = "sürüyor", rel
    save(a.project, lines, tasks)
    if not a.no_branch and os.path.isdir(os.path.join(a.project, ".git")):
        exists = subprocess.run(["git", "-C", a.project, "rev-parse", "--verify", branch],
                                capture_output=True).returncode == 0
        subprocess.run(["git", "-C", a.project, "switch"] + ([] if exists else ["-c"]) + [branch],
                       capture_output=True)
    print(f"Sıradaki iş: {t['id']} — {t['is']}\nFaz: {t['faz']} · Kapı: {t['kapi'] or '—'}\n"
          f"Bitti sayılır: {t['bitti']}\nAyrıntı dosyası: {os.path.abspath(path)}\nDal: {branch}")
    return 0


def set_status(project, lines, tasks, t, status):
    """Row in TASKS.md and the detail file's front matter move together."""
    t["durum"] = status
    save(project, lines, tasks)
    p = os.path.join(project, t["ayrinti"]) if t["ayrinti"] else ""
    if p and os.path.exists(p):
        with open(p) as f:
            s = f.read()
        with open(p, "w") as f:
            f.write(re.sub(r"^durum: .*$", f"durum: {status}", s, count=1, flags=re.M))


def git(project, *args):
    return subprocess.run(["git", "-C", project, *args], capture_output=True, text=True)


def touched_files(project):
    """Files this branch changed against main/master, committed or not: what a delivery shows."""
    for main in ("main", "master"):
        base = git(project, "merge-base", main, "HEAD")
        if base.returncode == 0:
            break
    else:
        return []
    names = git(project, "diff", "-z", "--name-only", base.stdout.strip()).stdout.split("\0")
    names += git(project, "ls-files", "-z", "--others", "--exclude-standard").stdout.split("\0")
    # the task books change on every status move; they are not what the evidence shows
    return sorted({n for n in names if n and n != "Docs/TASKS.md" and not n.startswith("Docs/tasks/")})


def fingerprint(project, files):
    out = {}
    for f in files:
        p = os.path.join(project, f)
        out[f] = hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.isfile(p) else None
    return out


def stale(project, t):
    """Files that changed since the task was delivered; None when the delivery has no fingerprint."""
    p = os.path.join(project, t["ayrinti"]) if t["ayrinti"] else ""
    if not p or not os.path.exists(p):
        return None
    m = re.search(r"^teslim: (.+)$", open(p).read(), flags=re.M)
    iz = os.path.join(m.group(1).strip(), "iz.json") if m else ""
    if not iz or not os.path.exists(iz):
        return None
    then = json.load(open(iz))
    if not then:     # delivered off git or from main: nothing to compare
        return None
    now = fingerprint(project, then)
    return [f for f in then if then[f] != now[f]]


def cmd_bayat(a):
    _, tasks = load(a.project)
    bad = 0
    for t in (t for t in tasks if t["durum"] == "teslimde"):
        changed = stale(a.project, t)
        if changed is None:
            print(f"{t['id']}: teslimin izi yok, kontrol edilemedi")
        elif changed:
            bad += 1
            print(f"{t['id']}: BAYAT — teslimden sonra {len(changed)} dosya değişti, kanıtı yeniden çek:\n  "
                  + "\n  ".join(changed[:20]))
        else:
            print(f"{t['id']}: güncel")
    return 1 if bad else 0


def cmd_set(a):
    if a.status not in STATUSES:
        sys.exit(f"ERROR: status must be one of {', '.join(STATUSES)}")
    lines, tasks = load(a.project)
    t = find(tasks, a.id)
    set_status(a.project, lines, tasks, t, a.status)
    print(f"{t['id']} -> {a.status}")
    return 0


def cmd_list(a):
    _, tasks = load(a.project)
    for t in tasks:
        if a.open and t["durum"] == "bitti":
            continue
        print(f"{t['id']:8} {t['durum']:10} {t['is']}")
    return 0


def cmd_show(a):
    _, tasks = load(a.project)
    t = find(tasks, a.id)
    for k in ("id", "is", "faz", "durum", "kapi", "bitti", "ayrinti"):
        print(f"{k}: {t[k]}")
    return 0


def cmd_add(a):
    lines, tasks = load(a.project)
    used = [int(t["id"][1:]) for t in tasks if t["id"].startswith("T")]
    new_id = f"T{max(used + [0]) + 1:03d}"
    # last row of the requested phase table; a new phase table goes at the end
    in_faz = [t for t in tasks if (t["faz"] or "").startswith(a.faz.split()[0])]
    entry = f"| {new_id} | {a.work} | bekliyor | {a.kapi} | {a.bitti} |  |"
    if in_faz:
        lines.insert(in_faz[-1]["line"] + 1, entry)
    else:
        lines += ["", f"## {a.faz}", "", HEADER, SEP, entry]
    with open(tasks_path(a.project), "w") as f:
        f.write("\n".join(lines))
    lines, tasks = load(a.project)
    save(a.project, lines, tasks)
    print(f"{new_id} eklendi: {a.work}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("next", "set", "list", "add", "show", "bayat"):
        p = sub.add_parser(name)
        p.add_argument("--project", default=".")
        if name == "next":
            p.add_argument("--no-branch", action="store_true")
        if name in ("set", "show"):
            p.add_argument("id")
        if name == "set":
            p.add_argument("status")
        if name == "list":
            p.add_argument("--open", action="store_true")
        if name == "add":
            p.add_argument("work")
            p.add_argument("--faz", required=True)
            p.add_argument("--kapi", default="—")
            p.add_argument("--bitti", default="(iş başlayınca yazılır)")
    a = ap.parse_args(argv)
    if not os.path.exists(tasks_path(a.project)):
        sys.exit(f"ERROR: {tasks_path(a.project)} not found — run `/clone-build kur` first")
    return {"next": cmd_next, "set": cmd_set, "list": cmd_list, "add": cmd_add, "show": cmd_show, "bayat": cmd_bayat}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
