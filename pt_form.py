"""pt_form.py - Set sonrası form raporu (2026-10-25). Yandan çekilmiş set videosu → ffmpeg 10 kare/sn → macOS Vision `VNDetectHumanBodyPoseRequest`
(kare başına eklem konumları) → açılar (dirsek, diz, kalça, vücut çizgisi) → tekrar sayımı (histerezisli durum makinesi), derinlik, kilitlenme, tempo,
vücut çizgisi, yorgunlukla bozulma → Claude (sonnet) 1-2 öneri. Araştırma raporu: canlı düzeltme yerine set sonrası rapor; kamera açısı en büyük hata
kaynağı. Video Mac'ten çıkmaz, işlenince silinir; yalnız ölçüler pt/form/<id>.json.
"""
import json
import math
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import pt

KLASOR = pt.VERI / "form"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FPS = 10
# hareket → izlenecek açı, tekrar mı tutuş mu
TUR = {"sinav": ("dirsek", "tekrar"), "egimli_sinav": ("dirsek", "tekrar"), "elmas_sinav": ("dirsek", "tekrar"), "yaslanan_sinav": ("dirsek", "tekrar"),
       "pike_sinav": ("dirsek", "tekrar"), "dips": ("dirsek", "tekrar"), "negatif_dips": ("dirsek", "tekrar"), "barfiks": ("dirsek", "tekrar"),
       "gogse_barfiks": ("dirsek", "tekrar"), "negatif_barfiks": ("dirsek", "tekrar"), "ters_kurek": ("dirsek", "tekrar"), "muscle_up": ("dirsek", "tekrar"),
       "squat": ("diz", "tekrar"), "bulgar_squat": ("diz", "tekrar"), "pistol": ("diz", "tekrar"), "karides_squat": ("diz", "tekrar"),
       "sandalye_kalkis": ("diz", "tekrar"), "kalca_kopru": ("kalca", "tekrar"), "tek_kalca_kopru": ("kalca", "tekrar"), "kb_swing": ("kalca", "tekrar"),
       "plank": ("cizgi", "tutus"), "hollow": ("cizgi", "tutus"), "tuck_hollow": ("cizgi", "tutus"), "lsit": ("kalca", "tutus"), "tuck_lsit": ("kalca", "tutus"),
       "karin_duvar_amut": ("cizgi", "tutus"), "serbest_amut": ("cizgi", "tutus"), "duvar_amut_sinav": ("dirsek", "tekrar"), "yan_plank": ("cizgi", "tutus")}
EKLEMLER = ["omuz", "dirsek", "bilek", "kalca", "diz", "ayak"]


def _vision_noktalar(jpg):
    import Vision
    from Foundation import NSURL
    h = Vision.VNImageRequestHandler.alloc().initWithURL_options_(NSURL.fileURLWithPath_(str(jpg)), None)
    r = Vision.VNDetectHumanBodyPoseRequest.alloc().init()
    ok = h.performRequests_error_([r], None)
    if not (ok[0] if isinstance(ok, tuple) else ok) or not r.results():
        return None
    o = max(r.results(), key=lambda x: x.confidence())
    ad = {"sol": {"omuz": Vision.VNHumanBodyPoseObservationJointNameLeftShoulder, "dirsek": Vision.VNHumanBodyPoseObservationJointNameLeftElbow,
                  "bilek": Vision.VNHumanBodyPoseObservationJointNameLeftWrist, "kalca": Vision.VNHumanBodyPoseObservationJointNameLeftHip,
                  "diz": Vision.VNHumanBodyPoseObservationJointNameLeftKnee, "ayak": Vision.VNHumanBodyPoseObservationJointNameLeftAnkle},
          "sag": {"omuz": Vision.VNHumanBodyPoseObservationJointNameRightShoulder, "dirsek": Vision.VNHumanBodyPoseObservationJointNameRightElbow,
                  "bilek": Vision.VNHumanBodyPoseObservationJointNameRightWrist, "kalca": Vision.VNHumanBodyPoseObservationJointNameRightHip,
                  "diz": Vision.VNHumanBodyPoseObservationJointNameRightKnee, "ayak": Vision.VNHumanBodyPoseObservationJointNameRightAnkle}}
    out = {}
    for taraf, d in ad.items():
        out[taraf] = {}
        for e, j in d.items():
            p = o.recognizedPointForJointName_error_(j, None)
            p = p[0] if isinstance(p, tuple) else p
            if p is not None and p.confidence() > 0.2:
                out[taraf][e] = (p.location().x, p.location().y, p.confidence())
    return out


def _aci(a, b, c):
    """b köşesindeki açı (derece)."""
    v1, v2 = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
    n = math.hypot(*v1) * math.hypot(*v2)
    if not n:
        return None
    return math.degrees(math.acos(max(-1, min(1, (v1[0] * v2[0] + v1[1] * v2[1]) / n))))


def _acilar(nok, oran):
    """Güveni yüksek taraftan açılar. oran = genişlik/yükseklik (Vision 0-1 koordinatları kare değil)."""
    best = None
    for taraf in ("sol", "sag"):
        j = {k: (v[0] * oran, v[1], v[2]) for k, v in (nok.get(taraf) or {}).items()}
        g = sum(v[2] for v in j.values())
        if best is None or g > best[0]:
            best = (g, j)
    if not best:
        return {}
    j = best[1]
    a = {}
    if all(k in j for k in ("omuz", "dirsek", "bilek")):
        a["dirsek"] = _aci(j["omuz"], j["dirsek"], j["bilek"])
    if all(k in j for k in ("kalca", "diz", "ayak")):
        a["diz"] = _aci(j["kalca"], j["diz"], j["ayak"])
    if all(k in j for k in ("omuz", "kalca", "diz")):
        a["kalca"] = _aci(j["omuz"], j["kalca"], j["diz"])
    if all(k in j for k in ("omuz", "kalca", "ayak")):
        a["cizgi"] = _aci(j["omuz"], j["kalca"], j["ayak"])
        # kalça çizginin altında mı üstünde mi (sarkma / kalçayı kaldırma); y yukarı doğru artar
        o, k, ay = j["omuz"], j["kalca"], j["ayak"]
        if ay[0] != o[0]:
            y_cizgi = o[1] + (ay[1] - o[1]) * (k[0] - o[0]) / (ay[0] - o[0])
            a["kalca_sapma"] = k[1] - y_cizgi
    a["guven"] = round(sum(v[2] for v in j.values()) / max(1, len(j)), 2)
    return a


def _tekrarlar(seri):
    """Histerezisli tekrar sayımı: açı aralığının alt %35'ine inip üst %25'ine çıkınca bir tekrar."""
    v = [x for x in seri if x is not None]
    if len(v) < 8:
        return []
    mn, mx = min(v), max(v)
    if mx - mn < 25:
        return []
    alt, ust = mn + 0.35 * (mx - mn), mx - 0.25 * (mx - mn)
    durum, bas, dip_i, L = "ust", 0, None, []
    for i, x in enumerate(seri):
        if x is None:
            continue
        if durum == "ust" and x < alt:
            durum, dip_i = "alt", i
        elif durum == "alt":
            if seri[dip_i] is None or x < seri[dip_i]:
                dip_i = i
            if x > ust:
                L.append({"bas": bas, "dip": dip_i, "bit": i, "en_dusuk": round(seri[dip_i]), "en_yuksek": round(max(y for y in seri[bas:i + 1] if y is not None))})
                durum, bas = "ust", i
    return L


def analiz(video, kod):
    kod = kod if kod in TUR else "sinav"
    aci_ad, tip = TUR[kod]
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([FFMPEG, "-y", "-i", str(video), "-vf", f"fps={FPS},scale=640:-2", "-q:v", "4", f"{td}/k_%04d.jpg"], capture_output=True, timeout=600)
        kareler = sorted(Path(td).glob("k_*.jpg"))[:900]
        if not kareler:
            raise RuntimeError("Video okunamadı.")
        from PIL import Image
        w, h = Image.open(kareler[0]).size
        oran = w / h
        A = []
        for k in kareler:
            n = _vision_noktalar(k)
            A.append(_acilar(n, oran) if n else {})
    seri = [a.get(aci_ad) for a in A]
    gorulen = sum(1 for a in A if a)
    sonuc = {"kod": kod, "ad": pt.KATALOG.get(kod, {}).get("ad", kod), "tip": tip, "aci": aci_ad, "sure_sn": round(len(A) / FPS, 1),
             "gorulen_oran": round(gorulen / max(1, len(A)), 2), "guven": round(sum(a.get("guven", 0) for a in A if a) / max(1, gorulen), 2)}
    cizgi = [a.get("cizgi") for a in A if a.get("cizgi")]
    sapma = [a.get("kalca_sapma") for a in A if a.get("kalca_sapma") is not None]
    if tip == "tekrar":
        L = _tekrarlar(seri)
        sonuc["tekrar"] = len(L)
        if L:
            sonuc["derinlik"] = [r["en_dusuk"] for r in L]
            sonuc["kilit"] = [r["en_yuksek"] for r in L]
            sonuc["inis_sn"] = [round((r["dip"] - r["bas"]) / FPS, 1) for r in L]
            sonuc["kalkis_sn"] = [round((r["bit"] - r["dip"]) / FPS, 1) for r in L]
            yarim = max(1, len(L) // 2)
            sonuc["derinlik_bozulma"] = round(sum(sonuc["derinlik"][yarim:]) / max(1, len(L) - yarim) - sum(sonuc["derinlik"][:yarim]) / yarim) if len(L) >= 4 else None
            if cizgi and aci_ad == "dirsek":
                dip_cizgi = [A[r["dip"]].get("cizgi") for r in L if A[r["dip"]].get("cizgi")]
                sonuc["dipte_vucut_cizgisi"] = round(min(dip_cizgi)) if dip_cizgi else None
    else:
        sonuc["tutus_sn"] = round(sum(1 for a in A if a.get(aci_ad)) / FPS, 1)
        if cizgi:
            sonuc["vucut_cizgisi_ort"] = round(sum(cizgi) / len(cizgi))
            sonuc["vucut_cizgisi_son_ucte"] = round(sum(cizgi[-len(cizgi) // 3:]) / max(1, len(cizgi[-len(cizgi) // 3:])))
    if sapma:
        sonuc["kalca_sapma_ort"] = round(sum(sapma) / len(sapma), 3)
    sonuc["seri"] = [round(x) if x is not None else None for x in seri[::2]][:300]
    return sonuc


ISTEM = """Sen bir antrenör ve fizyoterapistsin. Bir set videosundan bilgisayarla ölçülen değerler aşağıda (yandan çekim, Apple Vision ile eklem tespiti).
Hareket: {ad}. Türkçe, "siz" dili.
ÖLÇÜLER: {olcu}
Açıklama: açılar derece. dirsek ~180 kol düz; diz ~180 bacak düz; "vücut çizgisi" omuz-kalça-ayak açısı, ~170-180 düz; kalca_sapma eksi = kalça çizginin
altında (sarkma), artı = kalça yukarıda. derinlik = her tekrarda en düşük açı (şınavda ~90 ve altı iyi derinlik), kilit = en yüksek açı (~165+ tam açılma).
derinlik_bozulma artı = son tekrarlarda derinlik azaldı (yorgunluk). gorulen_oran/guven düşükse kamera açısı yetersiz demektir.
Kurallar: ölçüde olmayan bir şeyi iddia etme; en çok 2 öneri, her biri tek cümle ve uygulanabilir; iyi olan bir şeyi de söyle. Ölçüm güvenilir değilse
önce telefonun yerleşimini öner (yandan, tüm vücut kadrajda, 2-3 m uzakta, kalça yüksekliğinde).
JSON: {{"ozet": "tek cümle", "iyi": "tek cümle", "oneriler": ["..."], "guvenilir": true|false}}"""


def rapor(video, kod):
    import claude_yaz
    s = analiz(video, kod)
    olcu = {k: v for k, v in s.items() if k != "seri"}
    try:
        c = claude_yaz.sor_json(ISTEM.format(ad=s["ad"], olcu=json.dumps(olcu, ensure_ascii=False)), model_adi="sonnet", zaman_asimi=300)
    except Exception:  # noqa: BLE001
        c = {"ozet": "", "oneriler": [], "guvenilir": s["gorulen_oran"] > 0.6}
    s.update({"ozet": c.get("ozet") or "", "iyi": c.get("iyi") or "", "oneriler": [str(x) for x in c.get("oneriler") or []][:2],
              "guvenilir": bool(c.get("guvenilir", True)), "id": f"f{int(time.time())}", "zaman": int(time.time()), "tarih": pt.bugun().isoformat()})
    pt._yaz(KLASOR / f"{s['id']}.json", s)
    return s


def liste(n=20):
    return [pt._json(p, {}) for p in sorted(KLASOR.glob("f*.json"), reverse=True)[:n]]
