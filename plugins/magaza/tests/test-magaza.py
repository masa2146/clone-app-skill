#!/usr/bin/env python3
"""gorsel / denetle / fragman / sayfa / rakip on synthetic frames and clips, with planted errors."""
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, "..", "skills", "magaza", "scripts")
sys.path.insert(0, S)
from PIL import Image, ImageDraw  # noqa: E402
import ortak  # noqa: E402

CJK = ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
       "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc"]
LATIN = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/Library/Fonts/Arial.ttf"]


def first(paths):
    return next((p for p in paths if os.path.exists(p)), None)


def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(S, script), *args], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    fails = []
    def check(name, cond):
        print(f"{'PASS' if cond else 'FAIL'}: {name}")
        if not cond: fails.append(name)

    cjk, latin = first(CJK), first(LATIN)
    if not latin or not shutil.which("ffmpeg"):
        print("SKIP: needs a system TTF and ffmpeg")
        return 0
    tmp = tempfile.mkdtemp()
    for i in range(3):
        im = Image.new("RGB", (540, 1200), (30 + 60 * i, 140, 220 - 50 * i))
        d = ImageDraw.Draw(im)
        for k in range(12):
            d.rectangle((20 + 40 * k, 200 + 70 * k, 90 + 40 * k, 260 + 70 * k), fill=(250, 90 + 10 * k, 40))
        im.save(os.path.join(tmp, f"k{i}.png"))
    langs = {"tr-TR": {"ad": "Deneme Kule", "kisa": "Nişan al, fırlat ve kuleyi hamlelerin bitmeden yık.",
                       "uzun": "Her bölümde bir kule seni bekliyor. Topu doğru yere at, parçaların düşüşünü izle.",
                       "basliklar": ["Nişan al ve fırlat", "Kuleyi devir", "Zincirleme patlama"],
                       "grafik": "Tek atış, tek kule", "fragman": ["Nişan al", "Yık"], "kapanis": "Kuleler bekliyor"}}
    if cjk:
        langs["ja-JP"] = {"ad": "デネメ", "kisa": "狙って投げて、手数が尽きる前にタワーを崩そう。",
                          "uzun": "どのステージにもタワーが待っている。", "basliklar": ["狙って投げる", "タワーを崩す", "連鎖する爆発"],
                          "grafik": "一撃でタワーを崩せ", "fragman": ["狙う", "崩す"], "kapanis": "タワーが待っている"}
    for i in range(2):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        f"testsrc2=size=270x600:rate=30:duration=5", os.path.join(tmp, f"c{i}.mp4")], check=True)
    plan = {"oyun": "Deneme Kule", "font": cjk or latin, "kareler": [f"k{i}.png" for i in range(3)], "diller": langs,
            "fragman": {"bolumler": [{"klip": "c0.mp4", "bas": 0, "son": 4.5}, {"klip": "c1.mp4", "bas": 0.5, "son": 5}],
                        "en": 270, "boy": 480, "giris_sn": 1.2, "kapanis_sn": 1.5, "kisa_sn": 8}}
    pp = os.path.join(tmp, "plan.json")
    json.dump(plan, open(pp, "w"), ensure_ascii=False)
    out = os.path.join(tmp, "out")

    code, msg = run("gorsel.py", "--plan", pp, "--cikti", out)
    check("gorsel exits 0", code == 0)
    man = json.load(open(os.path.join(out, "manifest.json")))
    check("3 styles × languages × (3 shots + 1 graphic)", len(man["goruntuler"]) == 3 * len(langs) * 4)
    sizes = {Image.open(r["yol"]).size for r in man["goruntuler"] if r["tur"] == "telefon"}
    check("every phone shot is 1080x1920", sizes == {(1080, 1920)})
    check("feature graphic is 1024x500 RGB",
          all(Image.open(r["yol"]).size == (1024, 500) and Image.open(r["yol"]).mode == "RGB"
              for r in man["goruntuler"] if r["tur"] == "grafik"))
    check("styles differ (same frame, different pixels)",
          len({Image.open(os.path.join(out, "tr-TR", s, "telefon-01.png")).tobytes()[:200000] for s in ("serit", "panorama", "odak")}) == 3)
    code, msg = run("denetle.py", "gorsel", os.path.join(out, "manifest.json"))
    check("clean images pass", code == 0)
    bad = dict(man)
    p = os.path.join(tmp, "kotu.png")
    Image.new("RGBA", (1080, 2400), (0, 0, 0, 255)).save(p)
    bad["goruntuler"] = man["goruntuler"] + [{"dil": "tr-TR", "stil": "serit", "tur": "telefon", "sira": 9, "yol": p,
                                              "metin_orani": 0.3}]
    json.dump(bad, open(os.path.join(tmp, "kotu.json"), "w"))
    code, msg = run("denetle.py", "gorsel", os.path.join(tmp, "kotu.json"))
    check("planted 1080x2400 RGBA with 30% text is caught",
          code == 1 and "alfa" in msg and "iki katını" in msg and "%30" in msg)

    code, msg = run("denetle.py", "metin", "--plan", pp)
    check("clean texts pass", code == 0)
    dirty = json.loads(json.dumps(plan))
    t = dirty["diller"]["tr-TR"]
    t["kisa"] = "Ücretsiz kule oyunu, şimdi indir!"
    t["ad"] = "DENEME KULE OYUNU EN IYI SURUM 2026"
    t["uzun"] = "kule " * 30 + "\nkule, top, atış, yık, oyun, bulmaca, eğlence"
    t["basliklar"][2] = "Her gün yeni görev"
    rk = {"uygulamalar": [{"paket": "com.example.rival", "diller": {"tr-TR": {"baslik": "Rakip",
          "aciklama": "Her bölümde bir kule seni bekliyor ve topu doğru yere at"}}}]}
    t["uzun"] += "\nHer bölümde bir kule seni bekliyor ve topu doğru yere at."
    json.dump(dirty, open(os.path.join(tmp, "kirli.json"), "w"), ensure_ascii=False)
    json.dump(rk, open(os.path.join(tmp, "rakip.json"), "w"), ensure_ascii=False)
    code, msg = run("denetle.py", "metin", "--plan", os.path.join(tmp, "kirli.json"), "--rakip", os.path.join(tmp, "rakip.json"))
    for what, needle in [("banned word 'ücretsiz'", "ücretsiz"), ("CTA 'şimdi indir'", "şimdi indir"),
                         ("'yeni' on a screenshot", "başlık 3"), ("name over 30", "sınır 30"), ("all caps name", "büyük harf"),
                         ("keyword stuffing", "doldurma"), ("comma keyword block", "sözcük listesi"),
                         ("phrase copied from a competitor", "rakipten kopya")]:
        check(f"metin catches {what}", needle in msg)
    check("metin exits 1 on errors", code == 1)

    if cjk and cjk != latin:
        lp = json.loads(json.dumps(plan))
        lp["font"] = latin
        json.dump(lp, open(os.path.join(tmp, "latin.json"), "w"), ensure_ascii=False)
        code, msg = run("denetle.py", "glif", "--plan", os.path.join(tmp, "latin.json"))
        check("glif catches Japanese captions in a Latin-only font", code == 1 and "ja-JP" in msg and "eksik harf" in msg)
    code, msg = run("denetle.py", "glif", "--plan", pp)
    check("glif passes with a font that has every glyph", code == 0)

    fo = os.path.join(tmp, "fout")
    code, msg = run("fragman.py", "--plan", pp, "--cikti", fo, "--dil", "tr-TR")
    check("fragman exits 0", code == 0)
    meta = json.load(open(os.path.join(fo, "fragman.json")))
    dur = lambda p: float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                                   "-of", "csv=p=0", p]).decode())
    full = next(v for v in meta["videolar"] if v["tur"] == "tam")
    short = next(v for v in meta["videolar"] if v["tur"] == "kisa")
    check("full cut length matches its timing", abs(dur(full["yol"]) - full["sure"]) < 0.25)
    check("short cut stays within kisa_sn", dur(short["yol"]) <= 8.2)
    code, msg = run("denetle.py", "video", os.path.join(fo, "fragman.json"))
    check("trailer passes the gameplay rules", code == 0)
    long = {"videolar": [dict(full, oynanis_orani=0.6, ilk_oynanis_sn=12)]}
    json.dump(long, open(os.path.join(tmp, "uzun.json"), "w"))
    code, msg = run("denetle.py", "video", os.path.join(tmp, "uzun.json"))
    check("video catches 60% gameplay and a 12 s intro", code == 1 and "%60" in msg and "10 saniye" in msg)

    page = os.path.join(out, "index.html")
    code, msg = run("sayfa.py", os.path.join(out, "manifest.json"), "--fragman", os.path.join(fo, "fragman.json"),
                    "--plan", pp, "--cikti", page)
    h = open(page).read()
    check("review page shows every image and the trailer", code == 0 and h.count("<img") >= len(man["goruntuler"]) and "<video" in h)
    check("review page uses relative paths", tmp not in h)

    hd = os.path.join(tmp, "html")
    os.makedirs(hd)
    for pkg, desc in (("com.example.a", "Smash the tower with one shot. Physics puzzle fun."),
                      ("com.example.b", "Topple every tower in this physics puzzle.")):
        ld = {"@type": "SoftwareApplication", "name": pkg[-1].upper() + " Tower", "description": desc,
              "screenshot": [{"url": "https://x/1"}, {"url": "https://x/2"}]}
        open(os.path.join(hd, f"{pkg}.en-US.html"), "w").write(
            f'<script type="application/ld+json">{json.dumps(ld)}</script>')
    code, msg = run("rakip.py", "com.example.a", "com.example.b", "--diller", "en-US", "--cikti",
                    os.path.join(tmp, "rk"), "--html-dir", hd)
    md = open(os.path.join(tmp, "rk", "rakip.md")).read() if code == 0 else ""
    check("rakip table built offline", code == 0 and "| com.example.a |" in md)
    check("rakip lists words both competitors use", "physics (2)" in md and "puzzle (2)" in md)

    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    if cjk:
        lines = ortak._balanced(d, "一撃でタワーを崩せ", ortak._font(cjk, 60), 300, False)
        check("no Japanese line starts with ー", all(l[0] not in ortak.NO_LINE_START for l in lines[1:]) and len(lines) > 1)
    P = ortak.palette({}, [Image.open(os.path.join(tmp, "k0.png"))])
    check("derived palette: caption colour reads on the background", ortak.contrast(P["acik"], P["koyu"]) >= 4.5)
    check("derived background is not pure black", sum(P["koyu"]) > 15)

    print(f"\n{len(fails)} failed" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
