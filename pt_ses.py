"""pt_ses.py - Health koçunun sesi: önceden üretilmiş doğal Türkçe ses parçaları (2026-10-25; kullanıcı: "Türkçe ses aşırı robotik, çok kötü").

Tarayıcının/telefonun yerleşik sesi yerine bu Mac'teki sinir ağı ses modeli (Chatterbox Multilingual, MLX; Studio'nun dublajıyla aynı model,
.venv-mlxtts) ile cümle parçaları önceden seslendirilir. Ses: modelin varsayılan sesi (`conds.pt` → pt_medya/_ses_model/conds.safetensors);
başka bir ses örneği (`pt_medya/_ses_ornek.wav`, rızası alınmış kişi) konursa onunla. Sayfa konuşmayı parçalara böler (hareket adı, hedef,
adımlar, "Sırada …", "Son on saniye"…); her parça bir kez üretilir ve pt_medya/_ses/<anahtar>.m4a olarak saklanır. Eksik parçalar
bekleyen.json kuyruğuna girer; site arka planda üretir (parça başına ~5 sn). Elle: `python pt_ses.py katalog` (bütün hareketlerin parçaları).
"""
import fcntl
import hashlib
import os
import json
import shutil
import subprocess
import threading
import time
import unicodedata

import pt
import pt_kart

MEDYA = pt_kart.MEDYA
KLASOR = MEDYA / "_ses"
MODEL = MEDYA / "_ses_model"
ORNEK = MEDYA / "_ses_ornek.wav"
BEKLEYEN = KLASOR / "bekleyen.json"
MLX_PY = pt.KLASOR / ".venv-mlxtts" / "bin" / "python"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
_kilit = threading.Lock()
SIRA = ["", "Birinci", "İkinci", "Üçüncü", "Dördüncü", "Beşinci", "Altıncı", "Yedinci", "Sekizinci", "Dokuzuncu", "Onuncu"]
SABIT = ["Dinlenme.", "On saniye.", "Son on saniye.", "Bitti. Elinize sağlık.", "Hadi başlıyoruz."] + \
        [f"{SIRA[i]} set." for i in range(1, 11)] + [f"{SIRA[i]} tur." for i in range(1, 11)]


def _norm(t):
    return " ".join(unicodedata.normalize("NFC", str(t)).split())


def anahtar(t):
    return hashlib.sha1(_norm(t).encode("utf-8")).hexdigest()[:16]


def hazir():
    """{metin: anahtar} yerine yalnız hazır anahtarlar (sayfa metnin anahtarını kendisi hesaplamaz; sunucu eşler)."""
    d = pt._json(KLASOR / "dizin.json", {})
    return {m: k for m, k in d.items() if (KLASOR / f"{k}.m4a").exists()}


def iste(metinler):
    """Eksik parçaları kuyruğa ekler. Döner: kuyruğa eklenen sayı."""
    h = hazir()
    with _kilit:
        b = pt._json(BEKLEYEN, [])
        yeni = [m for m in dict.fromkeys(_norm(x) for x in metinler if str(x).strip()) if m not in h and m not in b and len(m) <= 400]
        if yeni:
            KLASOR.mkdir(parents=True, exist_ok=True)
            pt._yaz(BEKLEYEN, b + yeni)
    return len(yeni)


def bekleyen():
    return len(pt._json(BEKLEYEN, []))


KOD = r'''
import json, sys, wave, numpy as np
import mlx.core as mx
from mlx_audio.tts.utils import load_model
istek = json.load(open(sys.argv[1], encoding="utf-8"))
model = load_model(istek["model"])
cond = model.prepare_conditionals(istek["ornek"], model.sample_rate, exaggeration=0.6) if istek.get("ornek") else None
for p in istek["parcalar"]:
    try:
        beklenen = max(0.8, len(p["metin"]) / 14.0)
        for sic in (0.7, 0.5):
            kw = dict(text=p["metin"], lang_code="tr", exaggeration=0.6, cfg_weight=0.5, temperature=sic, repetition_penalty=1.2,
                      max_new_tokens=min(1000, int(beklenen * 25 * 2.4) + 60), verbose=False)
            if cond is not None:
                kw["conds"] = cond
            s = list(model.generate(**kw))
            ses = np.concatenate([np.asarray(r.audio).reshape(-1) for r in s]) if s else None
            if ses is not None and beklenen * 0.4 <= len(ses) / model.sample_rate <= beklenen * 2.4:
                break
        a = np.clip(np.asarray(ses, dtype=np.float32).reshape(-1), -1, 1)
        with wave.open(p["cikti"], "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(model.sample_rate); w.writeframes((a * 32767).astype(np.int16).tobytes())
        mx.clear_cache()
        print("ok", p["k"], flush=True)
    except Exception as e:
        print("hata", p["k"], str(e)[:120], flush=True)
'''


def calistir(en_cok=60, log=print):
    """Kuyruktan en çok `en_cok` parçayı seslendirir. Döner: üretilen sayı."""
    with _kilit:
        b = pt._json(BEKLEYEN, [])
    if not b:
        return 0
    if not (MODEL / "conds.safetensors").exists() and not ORNEK.exists():
        log("ses modeli hazır değil (pt_medya/_ses_model)")
        return 0
    is_ = KLASOR / f".is_{os.getpid()}_{threading.get_ident()}"
    shutil.rmtree(is_, ignore_errors=True)
    is_.mkdir(parents=True)
    parca = b[:en_cok]
    istek = {"model": str(MODEL), "ornek": str(ORNEK) if ORNEK.exists() else None,
             "parcalar": [{"k": anahtar(m), "metin": m, "cikti": str(is_ / f"{anahtar(m)}.wav")} for m in parca]}
    (is_ / "istek.json").write_text(json.dumps(istek, ensure_ascii=False), encoding="utf-8")
    (is_ / "kod.py").write_text(KOD, encoding="utf-8")
    try:
        subprocess.run([str(MLX_PY), "-I", str(is_ / "kod.py"), str(is_ / "istek.json")], capture_output=True, text=True, timeout=60 * 60)
    except subprocess.TimeoutExpired:
        log("ses üretimi zaman aşımına uğradı")
    yapilan, yeni = 0, {}
    for m in parca:
        k = anahtar(m)
        wav = is_ / f"{k}.wav"
        if wav.exists():
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(wav), "-af", "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                            "silenceremove=start_periods=1:start_threshold=-45dB,areverse", "-c:a", "aac", "-b:a", "64k", str(KLASOR / f"{k}.m4a")],
                           capture_output=True, timeout=60)
            if (KLASOR / f"{k}.m4a").exists():
                yeni[m] = k
                yapilan += 1
    with _kilit, open(KLASOR / ".kilit", "w") as kf:
        fcntl.flock(kf, fcntl.LOCK_EX)                    # site ve elle çalışan üretim aynı anda yazmasın
        d = pt._json(KLASOR / "dizin.json", {})
        d.update(yeni)
        pt._yaz(KLASOR / "dizin.json", d)
        kalan = [m for m in pt._json(BEKLEYEN, []) if m not in parca]
        pt._yaz(BEKLEYEN, kalan)
    shutil.rmtree(is_, ignore_errors=True)
    log(f"ses: {yapilan}/{len(parca)} parça hazır, kuyrukta {len(kalan)}")
    return yapilan


def cumleler(metin, en_uzun=220):
    """Uzun metni seslendirilebilir cümlelere böler (çok uzun cümle virgülden)."""
    import re
    out = []
    for c in re.split(r"(?<=[.!?…])\s+|\n+", metin):
        c = c.strip(" -•*#\t")
        while len(c) > en_uzun:
            i = c.rfind(",", 0, en_uzun)
            i = i if i > 40 else c.rfind(" ", 0, en_uzun)
            out.append(c[:i + 1].strip())
            c = c[i + 1:].strip()
        if len(c) > 1:
            out.append(c if c[-1] in ".!?…:" else c + ".")
    return out


def uzun_metin(metin, hedef, log=print):
    """Uzun bir metni (haftalık koç mesajı) cümle cümle seslendirip tek m4a yapar. Döner: hedef ya da None."""
    C = cumleler(metin)
    if not C:
        return None
    iste(C)
    for _ in range(60):
        h = hazir()
        if all(_norm(c) in h for c in C):
            break
        if not calistir(log=log):
            time.sleep(5)
    h = hazir()
    dosyalar = [KLASOR / f"{h[_norm(c)]}.m4a" for c in C if _norm(c) in h]
    if not dosyalar:
        return None
    liste = KLASOR / f".liste_{os.getpid()}_{threading.get_ident()}.txt"
    sus = KLASOR / "_sus.m4a"
    if not sus.exists():
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "0.35", "-c:a", "aac", "-b:a", "64k", str(sus)],
                       capture_output=True, timeout=60)
    liste.write_text("".join(f"file '{f}'\nfile '{sus}'\n" for f in dosyalar), encoding="utf-8")
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(liste), "-c:a", "aac", "-b:a", "80k", str(hedef)],
                   capture_output=True, timeout=600)
    liste.unlink(missing_ok=True)
    return hedef if hedef.exists() else None


def katalog_metinleri():
    """Bütün hareketlerin sabit parçaları: ad, "Sırada …", adımlar + ortak cümleler."""
    K = pt_kart.kartlar()
    out = list(SABIT)
    for kod, h in pt.katalog().items():
        out += [f"{h['ad']}.", f"Sırada {h['ad']}."] + list((K.get(kod) or {}).get("adimlar") or [])
    return out


def hepsini(log=print):
    iste(katalog_metinleri())
    while bekleyen():
        if not calistir(log=log):
            break


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["katalog"]:
        hepsini()
    else:
        iste(sys.argv[1:])
        print(calistir())
