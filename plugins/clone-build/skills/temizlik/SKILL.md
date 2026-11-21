---
name: temizlik
description: Sweep the leftovers agent sessions leave behind in game/app projects built with clone-build — finished git worktrees and their Unity Library copies, merged local branches, old logs and test XMLs, superseded AAB/xcarchive builds, raw AI image/3D outputs already picked, stale session scratchpads, .utmp — after a task is merged, or as a weekly sweep. Lists first, deletes only on the user's "evet". Türkçe: gereksiz dosyaları sil, temizlik, disk doldu, yer aç, eski worktree, eski build, birleşmiş dallar, artıkları sil.
trigger: temizlik|gereksiz dosyaları sil|disk doldu|yer aç|eski worktree|eski build|artıkları sil|clean up leftovers|free disk space
---

# Temizlik

Oturumların çalışırken bıraktığı, işi bitmiş dosyaları bulur; önce kuru liste verir, kullanıcı "evet" demeden
hiçbir şey silmez. Kapsam: kullanıcının proje kökü (çoğu `~/PythonWorks` gibi tek klasör; ilk çalışmada sor ve
hafızaya yaz) altındaki git depoları, onların worktree'leri (çoğu kardeş klasör: `../<depo>-<dal>`), projelerin
teslim kökleri ve `/private/tmp/claude-$(id -u)/*` oturum klasörleri.

clone-build projelerinde iki hazır parça işi kolaylaştırır: `tasks.py temizle` birleşmiş görev worktree'lerini
siler, `tasks.py disk` boş yer eşiğini söyler. Bu skill onların kapsamadığı artıkları da toplar.

## Ayar

```
GUN=7          # bu kadar gündür dokunulmamış şey aday olur
CANLI_SAAT=24  # son bu kadar saatte değişmiş dosyası olan klasöre dokunulmaz
```

## Ne zaman

1. **İş bitince** (`/task bitir` sonrası): yalnız o işin worktree'si, dalı, logları ve ham AI çıktıları. `GUN`
   beklenmez; `CANLI_SAAT` ve korunanlar yine geçerli. Şu an içinde çalıştığın worktree'yi silme.
2. **Haftada bir:** bütün projeler, bütün aday türleri, `GUN` kuralıyla. Oturum açılışında `tasks.py disk` eşiğin
   altındaysa da önerilir.

## Asla silinmeyecekler

- **Commitlenmemiş değişikliği olan worktree** (`git -C <wt> status --porcelain` boş değil) ve **main'e birleşmemiş
  commit'i olan worktree ya da dal** (`git -C <depo> branch --no-merged main`).
- **Canlı oturumun klasörü:** son `CANLI_SAAT` saatte değişmiş dosyası olan klasör
  (`find <yol> -type f -mmin -$((CANLI_SAAT*60)) -print -quit`). `ListAgents` ile canlı oturumlara bak; onların
  klasörüne, dalına, scratchpad'ine dokunma. Main'deki commitlenmemiş değişiklik başka bir oturumundur.
- **İmza anahtarları ve gizli dosyalar:** her `*.keystore`, `*.jks`, `*.p12`, `*.mobileprovision`, imza klasörü,
  `google-services.json`, `.env`, kasa/yedek klasörü (yeri kullanıcının hafızasında).
- **Kaynak oyunun çıkarımı ve referansları:** clone-app `$WORK` (`extracted/`, `deliverables/`), `reference/`,
  `.apk`/`.xapk` kaynak paketleri. Paket tarama aracı (T110) çıkarımı okur; silinirse yayın taraması çalışmaz.
- **Bir aracın okuduğu her yol.** Silmeden önce adını projede ara:
  `grep -rl '<klasör adı>' tools Docs .claude Assets/Editor CLAUDE.md`. İsabet varsa aday değildir.
- **Korumalı dallar ve etiketler:** sadık kopya (T016) ve `reference-transaction` kancasının koruduğu her ref.
- **Git dışı ama tek kopya olanlar:** projenin CLAUDE.md'sinde ve KARARLAR'ında "git dışı", "silinmez",
  "korunur" diye geçen her şey; teslim kökü (`<teslim-root>/<oyun>/teslim/` silinmez); seçilmiş Gemini/Tripo
  çıktıları (`Art/` altında ya da KARARLAR'da yolu yazılı olanlar); izlenmeyen yeni dosyalar (`??`).
- **Ana deponun kendi `Library/` klasörü.** Yalnız silinecek worktree'nin içindeki `Library/` adaydır.
- **Mağazada yayındaki ve incelemedeki sürümün paketi** (AAB ve `.xcarchive`; arşiv çökme sembollerini taşır).
  Hangisi olduğunu projenin durum belgesi söyler; tahmin etme.

Projeye özel korunanlar: o projenin CLAUDE.md'sindeki "Temizlikte korunanlar" bölümü. Yoksa önce CLAUDE.md'yi ve
KARARLAR'ı oku, bulduklarını kullanıcıya gösterip o bölüme ekle.

## Aday türleri

Her aday için: proje, yol, boyut, en yeni dosyasının tarihi, neden aday, neden güvenli.

| Tür | Nasıl bulunur | Güvenli sayılma şartı |
|---|---|---|
| Worktree (+ içindeki `Library/`) | `git -C <depo> worktree list` | temiz, dalı main'e birleşmiş, en yeni dosyası `GUN`'den eski |
| Yerel dal | `git -C <depo> branch --merged main` | worktree'ye bağlı değil, son commit'i `GUN`'den eski |
| Android paketi | `Builds/*.aab`, `*.apk` (sürümlü adlar) | yayındaki ve incelemedeki sürümden eski; sonuncu tutulur |
| iOS arşivi | `Builds/*.xcarchive` (`Info.plist` → sürüm/yapı) | daha yeni yapı yayında ya da incelemede |
| Test sonucu, log, çökme dökümü | kökteki `*.xml`, `mono_crash.*.json`, `Logs/*.log`, `Logs/*.xml` | git-ignored ve `GUN`'den eski |
| Kare dizisi, ara çekim | `captures/`, `compare/` altındaki PNG dizileri | mp4'ü üretilmiş ya da teslime girmiş; bir araç okumuyor |
| Ham AI çıktısı | `raw-ai/`, `sprites-generated/work/`, indirilmiş GLB'ler | seçim KARARLAR'da, seçilen dosya `Art/`'a alınmış; reddedilen denemeler |
| `.utmp/`, Burst/IL2CPP ara klasörü | derleme ara klasörleri | `GUN`'den eski |
| Oturum scratchpad'i | `/private/tmp/claude-$(id -u)/<proje-anahtarı>/*` | canlı oturumun değil, en yeni dosyası `GUN`'den eski |

**Boyut tuzağı:** worktree'ye `Library/` çoğu zaman `cp -cR` (APFS klonu) ile kopyalanır; `du` tam boyutu gösterir
ama silinince o kadar yer açılmaz. "En fazla şu kadar" de; açılan gerçek yeri önce ve sonra `df -h ~` ile ölç.

## Çalışma biçimi

1. **Kuru liste.** Adayları topla, korunanlara karşı tek tek kontrol et. Ayrıntılı listeyi scratchpad'e yaz;
   kullanıcıya dosya listesi dökme, günlük dille özet ver: kaç aday, en fazla ne kadar yer açılır, en büyük üçü
   hangi işin artığı. Örnek: "İki oyunun eski sürüm kopyaları ve bir eski iOS arşivi silinirse en fazla 6 GB
   açılır; işleri main'de, kopyalara iki haftadır dokunulmamış."
2. **Onay.** Kullanıcı "evet" demeden hiçbir şey silinmez; bir kısmını seçebilir, yalnız seçileni sil. Onay o
   listeye aittir; sonradan bulunan aday yeniden sorulur.
3. **Silme:**
   - Worktree: `git -C <depo> worktree remove <yol>`; kirli ya da izlenmeyen dosya diye reddederse dur, sor.
     `--force` ve `rm -rf` ile worktree silme yok. Ardından `git worktree prune`; dal birleşmişse `git branch -d`.
   - Dal: `git branch -d <dal>`. **Asla `-D`.** Reddederse dal birleşmemiştir, aday değildir.
   - Dosya/klasör: `rm` / `rm -r` yalnız onaylanan tam yola.
4. **Sonra:** açılan yeri `df -h ~` ile ölç, tek cümleyle bildir. Başka projenin worktree'sini ya da dalını
   sildiysen o projenin canlı oturumuna bir satır haber ver.

## Yapma

- Okumadığın bir temizlik aracında `--help` deneme (bazı sürümler `--help` ile gerçek temizliği başlatıyor).
- Commit atma, dal değiştirme; temizlik başka oturumun işine karışmaz.
- "Büyük ve eski" diye aday çıkarma; her adayın "neden güvenli" sorusuna somut cevabı olmalı.
