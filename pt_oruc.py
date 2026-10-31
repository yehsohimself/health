"""Oruç sırasında vücutta neler oluyor (2026-10-31; kullanıcı: "sıradaki yemeğime kaç saat kaldığını, şu an otofaji mi, hangi fazda
olduğumu söylesin; şu an vücudunda şunlar oluyor gibi bilgilendirsin; spor yaptığımı belirtirsem onunla birleştirsin").

Fazlar son yemekten geçen saate göre. Saatler kişiden kişiye değişir; yaklaşık ve dürüst yazılır. Otofaji tek bir saatte açılan düğme
değildir: insanlarda başlama saati ölçülemedi, hayvan çalışmalarında uzun açlıkta belirgin artar. Antrenman glikojeni erken tükettiği için
oruç saatine "kayma" eklenir (yalnız orucun içinde biten seanslar)."""
import datetime as dt
import time

import pt

FAZLAR = [
    {"bas": 0, "kod": "sindirim", "ad": "Sindirim",
     "simdi": ["Kan şekeri ve insülin yemekten sonra yükseldi; vücut yediğini kullanıyor.",
               "Fazlası karaciğer ve kaslara şeker (glikojen), geri kalanı yağ olarak depolanıyor."]},
    {"bas": 4, "kod": "emilim_sonrasi", "ad": "Emilim sonrası",
     "simdi": ["İnsülin düşüyor; kan şekerini karaciğerdeki depo (glikojen) dengede tutuyor.",
               "Yağ depolarından yağ asitleri yavaş yavaş kana karışmaya başlıyor."]},
    {"bas": 12, "kod": "yaga_gecis", "ad": "Yağa geçiş",
     "simdi": ["Karaciğerdeki şeker deposu azaldı; vücut enerjinin giderek daha büyük kısmını yağdan alıyor.",
               "Karaciğer keton üretmeye başladı; kandaki düzeyleri hâlâ düşük.",
               "Açlık hissi dalga dalga gelir: alışık olduğunuz öğün saatlerinde artar, sonra geçer."]},
    {"bas": 16, "kod": "hafif_ketoz", "ad": "Hafif ketoz",
     "simdi": ["Ketonlar belirgin biçimde artıyor; beyin enerjisinin bir kısmını onlardan alıyor.",
               "Büyüme hormonu yükselir; kas kaybını sınırlamaya yardım ettiği düşünülüyor.",
               "Su ve tuz (sodyum) kaybı artar: baş ağrısı ya da halsizlikte su ve bir tutam tuz iyi gelir."]},
    {"bas": 24, "kod": "uzun_oruc", "ad": "Uzun oruç",
     "simdi": ["Karaciğerin şeker deposu büyük ölçüde bitti; ketonlar yükseliyor.",
               "Vücut proteinden de şeker üretmeye başlar; uzadıkça kas korunması zorlaşır.",
               "Uzun oruçlar doktorla planlanmalı; ilaç kullanıyorsanız özellikle."]},
    {"bas": 48, "kod": "cok_uzun", "ad": "Çok uzun oruç",
     "simdi": ["48 saati geçen oruçlar tıbbi gözetim ister. Baş dönmesi, çarpıntı ya da bayılma hissinde orucu açın."]},
]

OTOFAJI = [  # (eşik saat, metin)
    (0, "Belirgin değil. Otofaji hücrelerde her zaman az miktarda sürer; tokken baskılanır."),
    (16, "Artmaya başlamış olabilir. İnsanlarda başlama saati ölçülemedi; bu tahmin hayvan çalışmalarına dayanıyor."),
    (24, "Büyük olasılıkla artıyor. Hayvan çalışmalarında 24-48 saatlik açlıkta belirgin; insanlarda kanıt sınırlı."),
]

KAYMA = {"kolay": 0.04, "orta": 0.06, "aralik": 0.08}   # dakika başına glikojen eşdeğeri oruç saati


def faz(sa):
    f = FAZLAR[0]
    for x in FAZLAR:
        if sa >= x["bas"]:
            f = x
    return f


def otofaji(sa):
    m = OTOFAJI[0][1]
    for e, t in OTOFAJI:
        if sa >= e:
            m = t
    return m


def _yogunluk(s):
    k = s.get("kardiyo") or s.get("bisiklet") or {}
    if k.get("yogunluk") in KAYMA:
        return k["yogunluk"]
    z = float(s.get("zorluk") or 6)
    return "aralik" if z >= 7 else "orta" if z >= 5 else "kolay"


def sporlar(bas_t, simdi=None):
    """Orucun içinde biten seanslar. Saati bilinmeyen seans, orucun başladığı günden sonraysa ya da aynı gün ve oruç sabahtan başladıysa sayılır."""
    simdi = simdi or time.time()
    bas = dt.datetime.fromtimestamp(bas_t)
    L = []
    g = bas.date()
    while g <= dt.date.fromtimestamp(simdi):
        for s in pt.gun(g.isoformat()).get("seanslar") or []:
            if not s.get("bitti"):
                continue
            t = s.get("bitis_t")
            if t:
                if not (bas_t <= t <= simdi):
                    continue
            elif g == bas.date() and bas.hour >= 12:      # akşam başlayan orucun gününde saati bilinmeyen seans büyük olasılıkla önceydi
                continue
            dk = int(pt.sayi(s.get("sure_dk"), 0, 600, 0) or 0)
            if dk < 10:
                continue
            L.append({"ad": s.get("baslik") or s.get("tur") or "Antrenman", "dk": dk, "yogunluk": _yogunluk(s), "t": t,
                      "guc": s.get("tur") in ("guc", "kalistenik", "test") or bool(s.get("hareketler"))})
        g += dt.timedelta(days=1)
    return L


def durum(pen, simdi=None):
    """pencere_durumu çıktısından oruç durumu. Yeme penceresi açıkken None."""
    simdi = simdi or time.time()
    if not pen or pen.get("durum") == "acik" or not pen.get("oruc_bas_t"):
        return None
    bas = pen["oruc_bas_t"]
    sp = sporlar(bas, simdi)
    kayma = round(min(4.0, sum(x["dk"] * KAYMA[x["yogunluk"]] for x in sp)), 1)
    sonraki = pen.get("acilis_t") if pen.get("durum") == "once" else pen.get("sonraki_acilis_t")
    kilo = pt.sayi(pt.profil().get("kilo_kg"), 30, 300)
    return {"bas_t": int(bas), "kayma_sa": kayma, "spor": sp, "sonraki_t": sonraki, "hedef_sa": pen.get("hedef_oruc"),
            "protein_g": int(round(kilo * 0.4 / 5) * 5) if kilo else None, **istemci()}


def anlat(o, simdi=None):
    """Sohbet ve bildirim için tek paragraf (sunucu tarafı)."""
    if not o:
        return "Yeme saatleri açık; oruç yok."
    simdi = simdi or time.time()
    sa = (simdi - o["bas_t"]) / 3600
    etkin = sa + o["kayma_sa"]
    f = faz(etkin)
    s = f"Son yemekten {sa:.1f} saat geçti; faz: {f['ad']}"
    if o["kayma_sa"]:
        s += f" (antrenman yüzünden yaklaşık {o['kayma_sa']} saat ileride sayılıyor)"
    s += f". Otofaji: {otofaji(etkin)}"
    if o.get("sonraki_t"):
        k = max(0, o["sonraki_t"] - simdi) / 3600
        s += f" Sıradaki yemek {k:.1f} saat sonra ({dt.datetime.fromtimestamp(o['sonraki_t']):%H:%M})."
    if o["spor"]:
        s += " Oruçta yapılan: " + ", ".join(f"{x['ad']} {x['dk']} dk" for x in o["spor"]) + "."
    return s


def istemci():
    """Arayüzün dakika dakika hesaplaması için sabit tablolar."""
    return {"fazlar": FAZLAR, "otofaji": [{"bas": e, "metin": t} for e, t in OTOFAJI]}
