"""pt_hareket.py - PT'nin hareket video kitaplığı (2026-10-25). Videoları kullanıcı kendisi çeker (lisans derdi yok; açık kaynak
uygulamaların çoğu video lisansı yüzünden kapandı).

Yükleme → ffmpeg: ses atılır, uzun kenar 720 px, 30 kare/sn, Apple donanım kodlayıcı (yoksa libx264), faststart, isteğe bağlı kırpma (bas/bit);
kapak karesi; 3 kareyle Claude hareketi tanır (katalogdaki koda eşler ya da yeni hareket önerir). Dosyalar pt/hareketler/<kod>/.
"""
import datetime as dt
import json
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pt

FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"


def sure(yol):
    try:
        r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(yol)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return 0.0


def islem(kaynak, hedef_mp4, bas=None, bit=None):
    """Döngüde oynayacak hafif kopya: sessiz, ≤720 px, 30 kare/sn."""
    kes = []
    if bas:
        kes += ["-ss", f"{float(bas):.2f}"]
    if bit:
        kes += ["-to", f"{float(bit):.2f}"]
    vf = "scale='if(gt(iw,ih),min(720,iw),-2)':'if(gt(iw,ih),-2,min(720,ih))',fps=30,format=yuv420p"
    for kodlayici in (["-c:v", "h264_videotoolbox", "-b:v", "2200k"], ["-c:v", "libx264", "-crf", "26", "-preset", "veryfast"]):
        r = subprocess.run([FFMPEG, "-y", *kes, "-i", str(kaynak), "-an", "-vf", vf, *kodlayici, "-movflags", "+faststart", str(hedef_mp4)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode == 0 and Path(hedef_mp4).exists() and Path(hedef_mp4).stat().st_size > 1000:
            return True
    raise RuntimeError("Video işlenemedi: " + (r.stderr or "")[-300:])


def kareler(mp4, klasor, n=3):
    s = sure(mp4) or 3
    L = []
    for i in range(n):
        o = Path(klasor) / f"k{i}.jpg"
        subprocess.run([FFMPEG, "-y", "-ss", f"{s * (i + 1) / (n + 1):.2f}", "-i", str(mp4), "-frames:v", "1", "-vf", "scale=480:-2", str(o)],
                       capture_output=True, timeout=60)
        if o.exists():
            L.append(o)
    return L


TANI_ISTEM = """Bu kareler bir kişinin kendi çektiği bir egzersiz videosundan (kalistenik, solo BJJ drill, animal flow ya da mobilite).
Hareketi tanı. Önce aşağıdaki katalogda karşılığı var mı bak; varsa o kodu ver. Yoksa yeni hareket öner (kod: küçük harf_alt_çizgi, Türkçe ad).
{ipucu}
KATALOG: {katalog}
JSON: {{"kod": "...", "katalogda": true|false, "ad": "Türkçe ad", "tur": "kalistenik|bjj|flow|mobilite|isinma", "olcu": "tekrar|sure",
"ekipman": "yok|bar|paralel|halka|kettlebell|bant|mat|duvar", "bolge": ["omuz", ...], "aciklama": "tek cümle nasıl yapılır",
"ipuclari": ["en çok 3 kısa form ipucu"], "guven": 0-1}}"""


def tani(kare_yollari, ipucu=""):
    import claude_yaz
    kat = ", ".join(f"{k}={v['ad']}" for k, v in pt.KATALOG.items())
    c = claude_yaz.json_coz(claude_yaz.sor_gorsel(TANI_ISTEM.format(katalog=kat, ipucu=f"Kullanıcının notu: {ipucu}" if ipucu else ""),
                                                   [str(x) for x in kare_yollari], model_adi="sonnet", zaman_asimi=300))
    return c or {}


def _kod_temizle(s):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    return re.sub(r"[^a-z0-9_]+", "_", str(s or "").translate(tr).lower()).strip("_")[:40] or f"hareket_{int(time.time())}"


def ekle(kaynak, kod=None, ipucu="", bas=None, bit=None, pozisyon=None):
    """Videoyu işler, tanır, kaydeder. kod verilirse (ör. 'Bu hareketin videosu yok · Video ekle') doğrudan o harekete bağlanır."""
    with tempfile.TemporaryDirectory() as td:
        gecici = Path(td) / "v.mp4"
        islem(kaynak, gecici, bas, bit)
        bilgi = {}
        if kod and kod in pt.KATALOG:
            h = pt.KATALOG[kod]
            bilgi = {"kod": kod, "katalogda": True, "ad": h["ad"]}
        else:
            try:
                bilgi = tani(kareler(gecici, td), ipucu)
            except Exception as e:  # noqa: BLE001
                bilgi = {"hata": str(e)[:200]}
            if kod:
                bilgi["kod"] = kod
        kod = _kod_temizle(bilgi.get("kod") or ipucu or "hareket")
        hed = pt.HAREKETLER / kod
        hed.mkdir(parents=True, exist_ok=True)
        shutil.move(str(gecici), hed / "video.mp4")
        subprocess.run([FFMPEG, "-y", "-ss", f"{min(1.0, sure(hed / 'video.mp4') / 2):.2f}", "-i", str(hed / "video.mp4"), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(hed / "kapak.jpg")], capture_output=True, timeout=60)
    eski = pt._json(hed / "bilgi.json", {})
    b = {**eski, **{k: v for k, v in bilgi.items() if k in ("ad", "tur", "olcu", "ekipman", "bolge", "aciklama", "ipuclari", "guven", "katalogda")},
         "kod": kod, "sure": round(sure(hed / "video.mp4"), 1), "eklenme": eski.get("eklenme") or int(time.time()), "guncelleme": int(time.time())}
    if pozisyon in pt.BJJ_POZISYONLAR:                           # jiu-jitsu haritasına teknik videosu
        b.update({"pozisyon": pozisyon, "tur": "bjj_teknik"})
    if kod in pt.KATALOG:                                       # katalog hareketinin adı/zinciri korunur
        b.update({"ad": b.get("ad") or pt.KATALOG[kod]["ad"], "katalogda": True})
    pt._yaz(hed / "bilgi.json", b)
    return b


def _kod(kod):
    if not re.fullmatch(r"[a-z0-9_]{1,60}", str(kod or "")):
        raise ValueError("Geçersiz hareket.")
    return kod


def duzenle(kod, ek):
    p = pt.HAREKETLER / _kod(kod) / "bilgi.json"
    if not p.exists():
        return None
    b = pt._json(p, {})
    for a in ("ad", "aciklama", "ipuclari", "tur", "olcu", "ekipman", "bolge"):
        if a in ek:
            b[a] = ek[a]
    b["guncelleme"] = int(time.time())
    pt._yaz(p, b)
    return b


def sil(kod):
    k = pt.HAREKETLER / _kod(kod)
    if not k.is_dir():
        return False
    cop = pt.KLASOR / ".cop" / f"pt_hareket__{kod}_{int(time.time())}"
    cop.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(k), cop)
    return True


def eksik_videolar():
    """Önümüzdeki günlerin planında geçen ama videosu olmayan hareketler (bu ve gelecek hafta; sık geçenler önce)."""
    from collections import Counter
    kat = pt.katalog()
    say = Counter()
    bu = pt.hafta_kodu()
    gunler = (pt.program(bu).get("gunler") or []) + (pt.program(pt.hafta_kodu(pt.hafta_gunleri(bu)[0] + dt.timedelta(days=7))).get("gunler") or [])
    for g in [g for g in gunler if g.get("tarih", "") >= pt.bugun().isoformat()]:
        for b in g.get("bolumler") or []:
            for h in b.get("hareketler") or []:
                if h.get("kod") in kat and not kat[h["kod"]].get("video"):
                    say[h["kod"]] += 3 if b.get("ad") in ("Ana bölüm", "Drill", "Akış") else 1      # ana hareketler ısınmadan önce
    return [{"kod": k, "ad": kat[k]["ad"], "kez": n} for k, n in say.most_common()]


if __name__ == "__main__":
    import sys
    print(json.dumps(ekle(sys.argv[1], *(sys.argv[2:3] or [None])), ensure_ascii=False, indent=1))
