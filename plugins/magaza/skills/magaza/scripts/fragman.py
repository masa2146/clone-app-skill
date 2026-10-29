#!/usr/bin/env python3
"""Store trailer: an animated title card, gameplay segments joined by animated transitions with a
caption per segment in each language, and a closing card. ffmpeg + Pillow.

    fragman.py --plan magaza-plani.json --cikti <dir> [--dil tr-TR,en-US]

Plan block:

    "fragman": {"bolumler": [{"klip": "rec/a.mp4", "bas": 1.0, "son": 6.5}, ...],
                "giris_sn": 2.0, "kapanis_sn": 2.5, "gecis_sn": 0.35,
                "gecisler": ["slideleft", "zoomin", "wipeup", "circleopen"],
                "muzik": "music.mp3", "en": 1080, "boy": 1920, "fps": 30, "kisa_sn": 15}

and per language "fragman": [one caption per segment], "kapanis": closing line (game name, a
feature — never "Play now": Play rejects calls to action in assets).

Writes <dir>/<dil>/fragman-tam.mp4 and fragman-kisa.mp4 (the short one keeps the first
segments that fit kisa_sn) and <dir>/fragman.json with each video's gameplay share and first
gameplay second; `denetle.py video` reads it. Play autoplays muted for 30 s, wants gameplay
within 10 s and at least 80% real gameplay — the cards stay short for that reason.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ortak as o  # noqa: E402

DEFAULTS = {"giris_sn": 2.0, "kapanis_sn": 2.5, "gecis_sn": 0.35, "en": 1080, "boy": 1920, "fps": 30,
            "kisa_sn": 15, "kisa_giris_sn": 1.2, "kisa_kapanis_sn": 1.5, "gecisler": ["slideleft", "zoomin", "wipeup", "circleopen"]}


def timing(G, segs, K, D):
    total = G + sum(segs) + K - (len(segs) + 1) * D
    return total, 1 - (G + K - D) / total, G - D


def cut_short(segs, cfg):
    """First segments (last one trimmed) so the whole video stays within kisa_sn."""
    G, K, D = cfg["giris_sn"], cfg["kapanis_sn"], cfg["gecis_sn"]
    out = []
    for s in segs:
        trial = out + [dict(s)]
        n = len(trial)
        budget = cfg["kisa_sn"] - G - K + (n + 1) * D - sum(x["son"] - x["bas"] for x in out)
        if budget < 1.5:
            break
        trial[-1]["son"] = min(s["son"], s["bas"] + budget)
        out = trial
    return out


def fit_cards(cfg, segs, target=0.82, floor=0.6):
    """Shorten the title and closing cards (never below `floor` s) until gameplay fills `target`."""
    c = dict(cfg)
    lens = [x["son"] - x["bas"] for x in segs]
    while timing(c["giris_sn"], lens, c["kapanis_sn"], c["gecis_sn"])[1] < target and \
            (c["giris_sn"] > floor or c["kapanis_sn"] > floor):
        c["giris_sn"] = max(floor, round(c["giris_sn"] - 0.1, 2))
        c["kapanis_sn"] = max(floor, round(c["kapanis_sn"] - 0.1, 2))
    return c


def card(path, P, font, spaced, w, h, title, line, logo):
    img = o.gradient(w, h, P["koyu"], P["ana"])
    k = w / 1080
    if logo:
        lg = Image.open(logo).convert("RGBA")
        s = min(800 * k / lg.width, 520 * k / lg.height)
        lg = lg.resize((int(lg.width * s), int(lg.height * s)), Image.LANCZOS)
        o.paste_rgba(img, lg, ((w - lg.width) // 2, int(h * 0.30)))
    else:
        o.text_block(img, title, font, (int(60 * k), int(h * 0.30), int(w - 60 * k), int(h * 0.52)),
                     P["acik"], P["koyu"], spaced, int(150 * k), int(20 * k))
    if line:
        o.text_block(img, line, font, (int(80 * k), int(h * 0.58), int(w - 80 * k), int(h * 0.70)),
                     o.readable(P["koyu"], P["vurgu"], P["acik"]), P["koyu"], spaced, int(80 * k), int(16 * k))
    img.save(path)


def caption(path, text, P, font, spaced, w, h):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    k = w / 1080
    if text:
        box = (int(70 * k), int(150 * k), int(w - 70 * k), int(380 * k))
        ImageDraw.Draw(img).rounded_rectangle((box[0] - 20 * k, box[1] - 20 * k, box[2] + 20 * k, box[3] + 20 * k),
                                              int(40 * k), fill=P["koyu"] + (215,))
        o.text_block(img, text, font, box, P["acik"], None, spaced, int(100 * k), int(18 * k))
    img.save(path)


def build(plan, loc, segs, cfg, out, tmp, P):
    t = plan["diller"][loc]
    font = o.font_for(plan, loc)
    spaced = o.lang_info(loc).get("bosluk", True)
    w, h, fps, D = cfg["en"], cfg["boy"], cfg["fps"], cfg["gecis_sn"]
    G, K = cfg["giris_sn"], cfg["kapanis_sn"]
    title = t.get("ad") or plan.get("oyun", "")
    card(os.path.join(tmp, "giris.png"), P, font, spaced, w, h, title, t.get("grafik", ""), plan.get("logo"))
    card(os.path.join(tmp, "kapanis.png"), P, font, spaced, w, h, title, t.get("kapanis", ""), plan.get("logo"))
    caps = t.get("fragman") or []
    args, filt = ["ffmpeg", "-y", "-loglevel", "error"], []
    zoom = "zoompan=z='min(zoom+0.0015,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={w}x{h}:fps={fps}"
    args += ["-i", os.path.join(tmp, "giris.png")]
    filt.append(f"[0:v]{zoom.format(n=int(G * fps), w=w, h=h, fps=fps)},format=yuv420p,setsar=1,settb=AVTB[v0]")
    for i, s in enumerate(segs):
        dur = s["son"] - s["bas"]
        cp = os.path.join(tmp, f"yazi{i}.png")
        caption(cp, caps[i] if i < len(caps) else "", P, font, spaced, w, h)
        args += ["-ss", str(s["bas"]), "-t", str(dur), "-i", s["klip"], "-loop", "1", "-t", str(dur), "-i", cp]
        vi, ci = 1 + 2 * i, 2 + 2 * i
        filt.append(f"[{vi}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1[c{i}]")
        filt.append(f"[{ci}:v]format=rgba,fps={fps},fade=t=in:st=0.15:d=0.3:alpha=1[o{i}]")
        filt.append(f"[c{i}][o{i}]overlay=0:0:shortest=1,format=yuv420p,settb=AVTB[v{i + 1}]")
    oi = 1 + 2 * len(segs)
    args += ["-i", os.path.join(tmp, "kapanis.png")]
    filt.append(f"[{oi}:v]{zoom.format(n=int(K * fps), w=w, h=h, fps=fps)},format=yuv420p,setsar=1,settb=AVTB[v{len(segs) + 1}]")
    durs = [G] + [s["son"] - s["bas"] for s in segs] + [K]
    prev, acc = "v0", durs[0]
    for k in range(1, len(durs)):
        tr = cfg["gecisler"][(k - 1) % len(cfg["gecisler"])]
        off = acc - k * D
        filt.append(f"[{prev}][v{k}]xfade=transition={tr}:duration={D}:offset={off:.3f}[x{k}]")
        prev, acc = f"x{k}", acc + durs[k]
    total, share, first = timing(G, durs[1:-1], K, D)
    if cfg.get("muzik"):
        args += ["-i", cfg["muzik"]]
        filt.append(f"[{oi + 1}:a]atrim=0:{total:.3f},afade=t=out:st={max(0, total - 1):.3f}:d=1[a]")
    else:
        args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        filt.append(f"[{oi + 1}:a]anull[a]")
    args += ["-filter_complex", ";".join(filt), "-map", f"[{prev}]", "-map", "[a]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20", "-r", str(fps),
             "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ERROR: ffmpeg failed for {loc}:\n{r.stderr[-1500:]}")
    return {"dil": loc, "yol": os.path.abspath(out), "sure": round(total, 2),
            "oynanis_orani": round(share, 3), "ilk_oynanis_sn": round(first, 2), "bolum": len(segs)}


def render(plan, out_dir, langs=None):
    cfg = dict(DEFAULTS, **(plan.get("fragman") or {}))
    segs = cfg.get("bolumler") or []
    if not segs:
        sys.exit("ERROR: plan.fragman.bolumler is empty")
    frames = [Image.open(p) for p in plan.get("kareler") or []][:8]
    P = o.palette(plan, frames) if frames or plan.get("palet") else o.palette({"palet": {
        "koyu": "#1b1030", "ana": "#4a2a80", "vurgu": "#ffc23d", "acik": "#fff6e4"}}, [])
    rows = []
    for loc in plan["diller"]:
        if langs and loc not in langs:
            continue
        d = os.path.join(out_dir, loc)
        os.makedirs(d, exist_ok=True)
        # the short cut has shorter cards, or they eat its 80% gameplay share
        short = dict(cfg, giris_sn=cfg["kisa_giris_sn"], kapanis_sn=cfg["kisa_kapanis_sn"])
        short_segs = cut_short(segs, short)
        for kind, ss, c in (("tam", segs, fit_cards(cfg, segs)), ("kisa", short_segs, fit_cards(short, short_segs))):
            with tempfile.TemporaryDirectory() as tmp:
                row = build(plan, loc, ss, c, os.path.join(d, f"fragman-{kind}.mp4"), tmp, P)
            row["tur"] = kind
            rows.append(row)
    meta = {"videolar": rows}
    with open(os.path.join(out_dir, "fragman.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--cikti", required=True)
    ap.add_argument("--dil")
    a = ap.parse_args(argv)
    meta = render(o.load_plan(a.plan), a.cikti, a.dil.split(",") if a.dil else None)
    for v in meta["videolar"]:
        print(f"{v['dil']} {v['tur']}: {v['sure']} sn, oynanış %{100 * v['oynanis_orani']:.0f}, "
              f"ilk oynanış {v['ilk_oynanis_sn']} sn -> {v['yol']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
