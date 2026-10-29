"""pt_kart.py - Hareket kartları (2026-10-25; kullanıcı: "bir hareket öneriyorsun ama yalnız yazılı olursa anlamam").

Her katalog hareketi için (Claude, sonnet, 12'lik gruplar): Türkçe "nasıl yapılır" 3 adım, 2 sık hata, nerede hissedilir, çalışan kaslar (şema bölgeleri),
nefes, ve görsel üretimi için İngilizce poz tarifi (başlangıç, bitiş, hareket, kamera, tutuş mu). Kişisel veri değil: pt_medya/kartlar.json (git dışı,
gece yedeğinde). Görseller pt_gorsel.py.
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pt

MEDYA = pt.KLASOR / "pt_medya"
KARTLAR = MEDYA / "kartlar.json"
KASLAR = ["gogus", "on_omuz", "yan_omuz", "arka_omuz", "triceps", "biceps", "on_kol", "karin", "yan_karin", "ust_sirt", "kanat", "bel", "kalca",
          "on_bacak", "arka_bacak", "ic_bacak", "baldir", "boyun"]
KAS_AD = {"gogus": "Göğüs", "on_omuz": "Ön omuz", "yan_omuz": "Yan omuz", "arka_omuz": "Arka omuz", "triceps": "Arka kol", "biceps": "Ön kol (biceps)",
          "on_kol": "Önkol ve kavrama", "karin": "Karın", "yan_karin": "Yan karın", "ust_sirt": "Üst sırt", "kanat": "Sırt kanatları", "bel": "Bel",
          "kalca": "Kalça", "on_bacak": "Ön bacak", "arka_bacak": "Arka bacak", "ic_bacak": "İç bacak", "baldir": "Baldır", "boyun": "Boyun"}
_kilit = threading.Lock()

ISTEM = """Sen deneyimli bir antrenör ve fizyoterapistsin. Aşağıdaki hareketlerin her biri için bir hareket kartı yaz. Türkçe metinler kısa, net, "siz"
dili; uydurma yok. Görsel tarifler İNGİLİZCE ve bir yapay zekâ görsel modeline verilecek: tek kişi, yandan ya da önden tam boy, ekipman açıkça.

HAREKETLER (kod: ad · tür · açıklama · ekipman):
{liste}

Her hareket için:
- "adimlar": tam 3 kısa adım (her biri ≤ 14 kelime): başlangıç, hareket, bitiş/dönüş.
- "hatalar": 2 sık hata (≤ 10 kelime), "sik_hata_neden" yok.
- "hisset": tek cümle, nerede hissedilmeli.
- "nefes": tek kısa cümle.
- "kaslar": birincil 1-3, ikincil 0-3; YALNIZ şu kodlardan: {kaslar}
- "gorsel": {{"bas": "starting position, precise body description", "bit": "end position", "hareket": "short motion description from start to end",
  "kamera": "side|front|three-quarter|top", "tutus": true|false (static hold like plank), "ekipman_en": "equipment visible or none"}}

JSON: {{"kartlar": {{"kod": {{"adimlar": [...], "hatalar": [...], "hisset": "...", "nefes": "...", "kaslar": {{"birincil": [...], "ikincil": [...]}}, "gorsel": {{...}}}}}}}}"""


def kartlar():
    return pt._json(KARTLAR, {})


def _grup(kodlar):
    import claude_yaz
    E = {"yok": "none", "bar": "pull-up bar", "paralel": "parallel bars", "halka": "gymnastic rings", "kettlebell": "kettlebell", "bant": "resistance band",
         "mat": "exercise mat", "duvar": "wall", "ip": "jump rope"}
    liste = "\n".join(f"{k}: {pt.KATALOG[k]['ad']} · {pt.KATALOG[k]['tur']} · {pt.KATALOG[k]['aciklama']} · {E.get(pt.KATALOG[k]['ekipman'], pt.KATALOG[k]['ekipman'])}" for k in kodlar)
    c = claude_yaz.sor_json(ISTEM.format(liste=liste, kaslar=", ".join(KASLAR)), model_adi="sonnet", zaman_asimi=600)
    out = {}
    for k, v in (c.get("kartlar") or {}).items():
        if k not in pt.KATALOG or not isinstance(v, dict):
            continue
        kas = v.get("kaslar") or {}
        out[k] = {"adimlar": [str(x)[:120] for x in (v.get("adimlar") or [])][:3], "hatalar": [str(x)[:100] for x in (v.get("hatalar") or [])][:2],
                  "hisset": str(v.get("hisset") or "")[:160], "nefes": str(v.get("nefes") or "")[:120],
                  "kaslar": {"birincil": [x for x in kas.get("birincil") or [] if x in KASLAR][:3], "ikincil": [x for x in kas.get("ikincil") or [] if x in KASLAR][:3]},
                  "gorsel": {a: (v.get("gorsel") or {}).get(a) for a in ("bas", "bit", "hareket", "kamera", "tutus", "ekipman_en")}, "zaman": int(time.time())}
    return out


def uret(kodlar=None, yenile=False):
    """Eksik kartları üretir (ya da verilenleri). Döner: kart sayısı."""
    K = kartlar()
    kodlar = [k for k in (kodlar or list(pt.KATALOG)) if k in pt.KATALOG and (yenile or k not in K)]
    gruplar = [kodlar[i:i + 12] for i in range(0, len(kodlar), 12)]
    with ThreadPoolExecutor(3) as ex:
        for sonuc in ex.map(_grup, gruplar):
            with _kilit:
                K = kartlar()
                K.update(sonuc)
                pt._yaz(KARTLAR, K)
    return len(kartlar())


if __name__ == "__main__":
    import sys
    print(uret(sys.argv[1:] or None))
