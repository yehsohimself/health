"""pt_uzun.py - Uzun ve sağlıklı ömür katmanı (2026-10-31; kullanıcı: "Bir longevity uzmanlığı da katmak lazım. Benim esasen finaldeki amacım uzun
ve sağlıklı bir ömür. Jiu-jitsu gibi bir sürü uzmanlığı da bünyeye katmalı, her ne gerekiyorsa. Ama bana bunları sormamalı, ben bunlardan anlamam.
Ben ihtiyacı ve şartlarımı tanımlayacağım, o bana 'o zaman sana şöyle bir program yazıyorum' diyecek.")

Üç parça, hepsi KODDA (Claude yalnızca açıklar):
1. GÖSTERGELER (`gostergeler`): uzun ömürle en çok ilişkilendirilen, evde ölçülebilen işaretler: kardiyo kapasitesi (VO2max; Apple Sağlık'tan ya da
   sabah nabzından tahmin), yere oturup kalkma testi, tek ayak denge, barda asılı kalma (kavrama), şınav ve squat (kas gücü), bel/boy oranı, sabah
   nabzı, uyku. Her biri iyi / orta / geliştirilecek, ne anlama geldiği ve nasıl iyileştiği sade dille. Teşhis değil.
2. HAFTALIK DOZ (`dozlar`, `hafta_olcumu`, `plan_dozu`): güç (haftada en az 2), kolay kardiyo dakikası (konuşabilecek tempoda; alışırken 60-90, sonra
   150), haftada bir yoğun çalışma (nefes nefese; jiu-jitsu dersi sayılır), denge (haftada 3 gün kısa), hareketlilik, uyku. Planın ve yapılanın
   bu dozu ne kadar karşıladığı ölçülür.
3. REÇETE (`recete`): kişinin ihtiyacından ve şartlarından (hedefler, sevdikleri, günleri, dakikası, ekipmanı, dersleri, ağrıları) haftalık disiplin
   karışımı. Kişi disiplin seçmez; Health "size şöyle bir program yazıyorum" der, her satırın nedenini söyler, kişi sayıları değiştirebilir. Onaylanan
   reçete profilin `yontemler`'ine ve plan istemine gider. Kayıt pt/recete.json.
"""
import datetime as dt
import math
import time

import pt

RECETE = pt.VERI / "recete.json"

# Kişinin "sevdikleri" (kurulumda ihtiyaç dilinde sorulur; disiplin adı sorulmaz)
SEVDIKLERI = {"jiujitsu": "Jiu-jitsu ya da dövüş sporu", "bisiklet": "Bisiklete binmek", "yuruyus": "Yürüyüş, doğa", "kosu": "Koşu",
              "ev": "Evde ya da parkta vücut ağırlığıyla", "flow": "Yere yakın akış hareketleri", "esneme": "Esneme, yoga"}

KARDIYO_TUR = {"yuruyus": "Tempolu yürüyüş", "kosu": "Kolay koşu", "merdiven": "Merdiven", "yuzme": "Yüzme"}

# Yere oturup kalkma testi (Araújo; 0-10, her destek bir puan düşürür): test sayfasında seçenek, kayıtta puan
OTURKALK = {"Hiç destek yok": 10, "Bir destek": 9, "İki destek": 8, "Üç-dört destek": 6.5, "Beş ve fazla": 4}

UZMANLAR = [
    ("antrenor", "Antrenör", "Güç ve beceri: hangi hareket, kaç set, nasıl ilerler."),
    ("kardiyo", "Dayanıklılık koçu", "Kalp ve kondisyon: kolay tempo dakikaları ve haftalık yoğun çalışma."),
    ("diyetisyen", "Diyetisyen", "Kalori, protein, lif ve yeme düzeni."),
    ("fizyoterapist", "Fizyoterapist", "Ağrılar, eklemler, hareketlilik ve denge."),
    ("uyku", "Uyku ve toparlanma koçu", "Uyku, yorgunluk ve hafif haftalar."),
    ("uzun_omur", "Uzun ömür uzmanı", "Yıllar sonra da güçlü, dengeli ve bağımsız olmanız için ölçüler."),
    ("zihin", "Zihin-beden uzmanı", "Nefes, meditasyon, tai chi: stres, uyku ve denge için; kanıtı olduğu kadarıyla."),
    ("davranis", "Alışkanlık koçu", "Düzeni sürdürmek: küçük, her gün yapılabilir adımlar."),
]


def _yas(p):
    try:
        return int(p.get("yas") or 0) or None
    except (TypeError, ValueError):
        return None


def _son_testler():
    out = {}
    for k in pt.testler().get("kayitlar") or []:
        for ad, v in (k.get("sonuclar") or {}).items():
            if v not in (None, ""):
                out[ad] = (k.get("tarih"), v)
    return out


def _saglik_son(alan, gun=60):
    try:
        import pt_saglik
    except Exception:  # noqa: BLE001
        return None
    b = pt.bugun()
    for i in range(gun):
        t = (b - dt.timedelta(days=i)).isoformat()
        v = (pt_saglik.gun(t) or {}).get(alan)
        if v:
            return t, float(v)
    return None


def _saglik_ortanca(alan, gun=14):
    try:
        import pt_saglik
    except Exception:  # noqa: BLE001
        return None
    b = pt.bugun()
    L = sorted(float(x) for x in ((pt_saglik.gun((b - dt.timedelta(days=i)).isoformat()) or {}).get(alan) for i in range(gun)) if x)
    return L[len(L) // 2] if L else None


def _durum(v, iyi, orta, azalan=False):
    if v is None:
        return "yok"
    if azalan:
        return "iyi" if v <= iyi else "orta" if v <= orta else "gelistir"
    return "iyi" if v >= iyi else "orta" if v >= orta else "gelistir"


def _vo2_esik(yas, kadin):
    """Yaşa göre kaba eşikler (ml/kg/dk; kabaca 'iyi' ve 'ortalama' sınırları). Tahminidir; sıralama için."""
    yas = yas or 35
    iyi, orta = (45, 38) if yas < 30 else (43, 36) if yas < 40 else (41, 34) if yas < 50 else (38, 31) if yas < 60 else (35, 28)
    return (iyi - 6, orta - 6) if kadin else (iyi, orta)


def gostergeler(p=None):
    """Uzun ömür göstergeleri, kodla. Her biri: {kod, ad, deger, birim, durum, kaynak, neden, nasil, test}."""
    p = p or pt.profil()
    yas, kadin = _yas(p), p.get("cinsiyet") == "kadin"
    T = _son_testler()
    sayi = lambda k: float(T[k][1]) if k in T and isinstance(T[k][1], (int, float)) else None  # noqa: E731
    G = []

    # 1. Kardiyo kapasitesi
    vo2, kaynak = None, ""
    s = _saglik_son("vo2max", 120)
    if s:
        vo2, kaynak = round(s[1], 1), "Apple Sağlık"
    else:
        nab = _saglik_ortanca("nabiz", 14) or sayi("dinlenme_nabzi")
        if nab and 35 <= nab <= 110:
            hrmax = 208 - 0.7 * (yas or 35)
            vo2, kaynak = round(15.3 * hrmax / nab, 1), "sabah nabzından tahmin"
    iyi, orta = _vo2_esik(yas, kadin)
    G.append({"kod": "vo2", "ad": "Kardiyo kapasitesi", "deger": vo2, "birim": "VO2max", "durum": _durum(vo2, iyi, orta), "kaynak": kaynak,
              "neden": "Uzun ömürle en güçlü ilişkisi olan ölçülerden biri: kalbin ve kasların ne kadar oksijen kullanabildiği.",
              "nasil": "Haftada 2-3 kez konuşabileceğiniz tempoda uzun kardiyo, bir kez nefes nefese aralıklar.",
              "test": "dinlenme_nabzi" if vo2 is None else None, "hedef": f"{iyi}+"})
    # 2. Yere oturup kalkma
    ok = sayi("oturkalk_puan")
    G.append({"kod": "oturkalk", "ad": "Yere oturup kalkma", "deger": ok, "birim": "/10", "durum": _durum(ok, 8, 6),
              "kaynak": "test" if ok is not None else "",
              "neden": "Güç, esneklik ve dengenin birlikte ölçüsü; yaş ilerledikçe bağımsız yaşamın iyi bir habercisi.",
              "nasil": "Squat, kalça hareketliliği ve haftada bir kez bu hareketin kendisini çalışmak.", "test": "oturkalk", "hedef": "8+"})
    # 3. Tek ayak denge
    ta = sayi("tek_ayak_sn")
    G.append({"kod": "denge", "ad": "Tek ayak denge", "deger": ta, "birim": "sn", "durum": _durum(ta, 30 if (yas or 35) < 60 else 20, 10),
              "kaynak": "test" if ta is not None else "",
              "neden": "Denge yaşla erken bozulur ve düşme riskinin en önemli nedenlerinden biridir.",
              "nasil": "Seansların sonuna 1-2 dakika tek ayak çalışması; haftada üç gün yeter.", "test": "tek_ayak_sn", "hedef": "30 sn"})
    # 4. Kavrama (barda asılı kalma)
    asl = sayi("asilma_sn")
    i_, o_ = (60, 30) if not kadin else (45, 20)
    G.append({"kod": "kavrama", "ad": "Kavrama gücü", "deger": asl, "birim": "sn asılı", "durum": _durum(asl, i_, o_), "kaynak": "test" if asl is not None else "",
              "neden": "Kavrama gücü genel kas gücünün ve uzun ömrün basit bir göstergesi.",
              "nasil": "Barda asılı kalma ve barfiks basamakları.", "test": "asilma_sn" if "bar" in (p.get("ekipman") or []) else None, "hedef": f"{i_} sn"})
    # 5. Kas gücü (üst ve alt)
    sv, sq = sayi("sinav_max"), sayi("squat_max")
    gu = None
    if sv is not None or sq is not None:
        puan = []
        if sv is not None:
            puan.append(2 if sv >= (10 if kadin else 20) else 1 if sv >= (3 if kadin else 10) else 0)
        if sq is not None:
            puan.append(2 if sq >= 30 else 1 if sq >= 15 else 0)
        gu = sum(puan) / len(puan)
    G.append({"kod": "guc", "ad": "Kas gücü", "deger": " · ".join(x for x in [f"{sv:g} şınav" if sv is not None else "", f"{sq:g} squat" if sq is not None else ""] if x) or None,
              "birim": "", "durum": "yok" if gu is None else ("iyi" if gu >= 1.5 else "orta" if gu >= 0.75 else "gelistir"), "kaynak": "test" if gu is not None else "",
              "neden": "Kas kütlesi otuzlardan sonra her on yılda azalır; güç antrenmanı bunu durduran en etkili şey.",
              "nasil": "Haftada en az iki güç antrenmanı, basamak basamak.", "test": "sinav_max,squat_max" if gu is None else None, "hedef": ""})
    # 6. Bel/boy oranı
    bel = None
    for d in pt.gunler(90):
        if d.get("bel_cm"):
            bel = float(d["bel_cm"])
            break
    bel = bel or sayi("bel_cm")
    oran = round(bel / float(p["boy_cm"]), 2) if bel and p.get("boy_cm") else None
    G.append({"kod": "bel", "ad": "Bel/boy oranı", "deger": oran, "birim": "", "durum": _durum(oran, 0.5, 0.6, azalan=True),
              "kaynak": "ölçüm" if oran else "",
              "neden": "Karın çevresindeki yağ, kilodan daha iyi bir metabolik risk göstergesi. Bel, boyun yarısının altında olsun.",
              "nasil": "Hafif kalori açığı, yeterli protein, düzenli hareket.", "test": "bel_cm" if oran is None else None,
              "hedef": f"{round(float(p['boy_cm']) / 2)} cm bel" if p.get("boy_cm") else "0,5"})
    # 7. Sabah nabzı
    nab = _saglik_ortanca("nabiz", 14) or sayi("dinlenme_nabzi")
    G.append({"kod": "nabiz", "ad": "Sabah nabzı", "deger": round(nab) if nab else None, "birim": "atım/dk", "durum": _durum(nab, 60, 72, azalan=True),
              "kaynak": "Apple Sağlık" if _saglik_ortanca("nabiz", 14) else ("test" if nab else ""),
              "neden": "Kondisyon arttıkça dinlenme nabzı düşer; kişiden kişiye değişir, en anlamlısı kendi eğiliminiz.",
              "nasil": "Kolay kardiyo dakikaları ve iyi uyku.", "test": "dinlenme_nabzi" if not nab else None, "hedef": "60 altı"})
    # 8. Uyku
    uy = [float((d.get("sabah") or {}).get("uyku_saat")) for d in pt.gunler(14) if (d.get("sabah") or {}).get("uyku_saat")]
    uyku = round(sum(uy) / len(uy), 1) if uy else (_saglik_ortanca("uyku_saat", 14) or None)
    G.append({"kod": "uyku", "ad": "Uyku", "deger": uyku, "birim": "saat", "durum": _durum(uyku, 7, 6), "kaynak": "sabah kontrolü" if uy else ("Apple Sağlık" if uyku else ""),
              "neden": "Toparlanma, iştah, ruh hali ve uzun vadede kalp sağlığı uykuya bağlı.",
              "nasil": "Her gün aynı saatte yatıp kalkmak; yatmadan önce ekran yok.", "test": None, "hedef": "7-9 sa"})
    return G


# ----------------------------------------------------------------------------- haftalık doz

def _kolay_hedef(p, bas=None):
    bas = bas or pt.baslangic_durumu()
    if bas.get("tur") in ("alisma", "donus"):
        return 60
    if p.get("deneyim") == "yeni":
        return 90
    return 150


def dozlar(p=None, rc=None):
    """Haftalık hedef doz: onaylı reçeteden, yoksa kişiye önerilecek reçeteden."""
    p = p or pt.profil()
    rc = rc or recete_oku()
    if not rc.get("dozlar"):
        rc = recete(p)
    d = dict(rc.get("dozlar") or {})
    if pt.baslangic_durumu().get("tur") in ("alisma", "donus"):     # alışırken hedef küçük kalır (reçete sonradan onaylansa da)
        d["kolay_dk"] = min(d.get("kolay_dk") or 60, 60)
        d["yogun"] = 0
    return {"guc": d.get("guc") or 2, "kolay_dk": d.get("kolay_dk") or 60, "yogun": d.get("yogun", 1), "denge": d.get("denge") or 3,
            "hareketlilik": d.get("hareketlilik") or 1, "uyku": 7.0}


def _seans_dozu(s):
    """Bir seansın doza katkısı."""
    tur = s.get("tur")
    dk = float(s.get("sure_dk") or 0)
    out = {"guc": 0, "kolay_dk": 0, "yogun": 0, "denge": 0, "hareketlilik": 0}
    if tur == "kalistenik" and dk >= 10:
        out["guc"] = 1
    kar = s.get("bisiklet") or s.get("kardiyo") or {}
    if tur in ("bisiklet", "kardiyo", "yuruyus", "kosu") or kar:
        yog = kar.get("yogunluk") or ("orta" if tur == "kosu" and dk < 30 else "kolay")
        k = float((dk or kar.get("sure_dk") or 0) if tur in ("bisiklet", "kardiyo", "yuruyus", "kosu") else (kar.get("sure_dk") or 0))
        if yog in ("aralik", "tempo", "orta"):
            out["yogun"] = 1
            out["kolay_dk"] += k * 0.5               # aralıklı seansın ısınma ve araları kolay tempoda geçer
        else:
            out["kolay_dk"] += k
    if tur == "bjj_ders" and dk >= 30:
        out["yogun"] = 1
    if tur in ("mobilite", "flow"):
        out["hareketlilik"] = 1
    kodlar = {h.get("kod") for b in s.get("bolumler") or [] for h in b.get("hareketler") or []} | {h.get("kod") for h in s.get("hareketler") or []}
    if kodlar & {"tek_ayak_denge", "yere_otur_kalk"}:
        out["denge"] = 1
    return out


def _topla(seanslar):
    t = {"guc": 0, "kolay_dk": 0, "yogun": 0, "denge": 0, "hareketlilik": 0}
    denge_gun = set()
    for tarih, s in seanslar:
        d = _seans_dozu(s)
        for k in ("guc", "kolay_dk", "yogun", "hareketlilik"):
            t[k] += d[k]
        if d["denge"]:
            denge_gun.add(tarih)
    t["denge"] = len(denge_gun)
    t["kolay_dk"] = int(round(t["kolay_dk"]))
    t["yogun"] = min(t["yogun"], 3)
    return t


def hafta_olcumu(kod=None):
    """Bu hafta (Pzt-Paz) YAPILAN: bitmiş seanslar + işaretlenmiş yürüyüş görevleri + uyku ortalaması."""
    kod = kod or pt.hafta_kodu()
    L = []
    uyku = []
    adim = []
    for g in pt.hafta_gunleri(kod):
        if g > pt.bugun():
            continue
        d = pt.gun(g.isoformat())
        for s in d.get("seanslar") or []:
            if s.get("bitti"):
                L.append((g.isoformat(), s))
        ek = set(d.get("ek_gorev") or [])
        if "yuruyus" in ek:
            L.append((g.isoformat(), {"tur": "yuruyus", "sure_dk": 20}))
        if ek & {"denge", "oturkalk"}:
            L.append((g.isoformat(), {"tur": "gorev", "hareketler": [{"kod": "tek_ayak_denge"}]}))
        u = (d.get("sabah") or {}).get("uyku_saat")
        if u:
            uyku.append(float(u))
        try:
            import pt_saglik
            a = (pt_saglik.gun(g.isoformat()) or {}).get("adim")
            if a:
                adim.append(float(a))
        except Exception:  # noqa: BLE001
            pass
    t = _topla(L)
    t["uyku"] = round(sum(uyku) / len(uyku), 1) if uyku else None
    t["adim"] = int(sum(adim) / len(adim)) if adim else None
    return t


def plan_dozu(pl=None):
    """Bu haftanın PLANI dozu ne kadar karşılıyor."""
    pl = pl if pl is not None else pt.program()
    return _topla([(g.get("tarih"), g) for g in pl.get("gunler") or [] if g.get("tur") != "dinlenme"])


def doz_ozeti(kod=None):
    p = pt.profil()
    hedef = dozlar(p)
    yap = hafta_olcumu(kod)
    pln = plan_dozu(pt.program(kod))
    AD = {"guc": ("Güç", "antrenman"), "kolay_dk": ("Kolay kardiyo", "dk"), "yogun": ("Nefes nefese", "kez"), "denge": ("Denge", "gün"),
          "hareketlilik": ("Hareketlilik", "seans")}
    satir = []
    for k, (ad, birim) in AD.items():
        if not hedef.get(k):
            continue
        satir.append({"kod": k, "ad": ad, "birim": birim, "hedef": hedef[k], "yapilan": yap.get(k) or 0, "plan": pln.get(k) or 0,
                      "oran": round(min(1.0, (yap.get(k) or 0) / hedef[k]), 2)})
    tamam = all(s["yapilan"] >= s["hedef"] for s in satir)
    return {"satirlar": satir, "tamam": tamam, "uyku": yap.get("uyku"), "uyku_hedef": hedef["uyku"], "adim": yap.get("adim")}


def doz_haftalari(bas):
    """`bas` tarihinden bu yana dozun tamamlandığı (güç + kolay kardiyo) hafta sayısı; bu hafta bitmemişse sayılmaz, tamamsa sayılır."""
    p = pt.profil()
    hedef = dozlar(p)
    try:
        b = dt.date.fromisoformat(bas)
    except (TypeError, ValueError):
        b = pt.bugun()
    n = 0
    g = b - dt.timedelta(days=b.weekday())
    while g <= pt.bugun():
        kod = pt.hafta_kodu(g)
        y = hafta_olcumu(kod)
        if y["guc"] >= hedef["guc"] and y["kolay_dk"] >= hedef["kolay_dk"]:
            n += 1
        g += dt.timedelta(days=7)
    return n


# ----------------------------------------------------------------------------- reçete

ROL_NEDEN = {
    "guc": "Kas ve kemik yaşla en çok kaybettiğimiz şey; haftada en az iki güç antrenmanı bunu korur. Vücut ağırlığıyla, basamak basamak ilerler.",
    "kolay": "Konuşabileceğiniz tempoda; kalbin ve damarların temeli. Haftalık toplam {dk} dakika hedefi buradan ve günlük yürüyüşlerden dolar.",
    "yogun": "Haftada bir kez nefes nefese: kardiyo kapasitesi uzun ömrün en güçlü göstergelerinden.",
    "bjj_ders": "Sevdiğiniz şey; yoğun kondisyonu da karşılar. Haftanın geri kalanı derslere göre dizilir: dersten önceki gün ağır bacak ve kavrama yok.",
    "bjj_solo": "Derslerde zorlandığınız pozisyonların evde 20 dakikalık drilleri.",
    "hareketlilik": "Eklemler ve denge; sakatlığı ve düşme riskini azaltır. Güç seanslarının sonuna da iki dakika denge eklenir.",
    "flow": "Yere yakın akış: hareketlilik, koordinasyon ve gövde gücü bir arada; sevdiğiniz için hareketlilik günü bu olur.",
}


def _kardiyo_tasiyici(p, sev):
    if "bisiklet" in sev or "bisiklet" in (p.get("ekipman") or []):
        return "bisiklet"
    return "kardiyo"


def recete(p=None, sayilar=None, kardiyo_tur=None):
    """Kişinin ihtiyacı ve şartlarından haftalık karışım. `sayilar` verilirse (kişi değiştirdi) o sayılarla satırlar ve uyarılar yeniden kurulur."""
    p = p or pt.profil()
    sev = set(p.get("sevdikleri") or [])
    if not sev:                                      # eski profiller: seçtiği yöntemlerden
        y = p.get("yontemler") or {}
        sev = {k for k, v in {"ev": y.get("kalistenik"), "bisiklet": y.get("bisiklet"), "flow": y.get("flow"), "esneme": y.get("mobilite"),
                              "jiujitsu": y.get("bjj_solo") or ((p.get("bjj_ders") or {}).get("gunler"))}.items() if v}
    H = set(p.get("hedef_turleri") or [])
    ders = sorted(set((p.get("bjj_ders") or {}).get("gunler") or []))
    gunler = sorted(set(p.get("gunler") or []) | set(ders)) or [0, 2, 4]
    n = min(len(gunler), 7)
    bos = max(0, n - len(ders))
    if n == 7:
        bos = max(0, bos - 1)                       # haftada en az bir gün tam dinlenme
    dk = int(p.get("gunluk_dk") or 30)
    bas = pt.baslangic_durumu()
    alisma = bas.get("tur") in ("alisma", "donus")
    kolay_hedef = _kolay_hedef(p, bas)
    tas = _kardiyo_tasiyici(p, sev)
    ktur = kardiyo_tur if kardiyo_tur in KARDIYO_TUR else ("kosu" if ("kosu" in sev and "yuruyus" not in sev) else "yuruyus")

    if sayilar is None:
        s = {"kalistenik": 0, tas: 0, "bjj_solo": 0, "flow": 0, "mobilite": 0}
        kalan = bos
        s["kalistenik"] = min(2, kalan)          # üçüncü güç günü, kardiyo ve hareketlilikten sonra (kas/beceri hedefinde)
        kalan -= s["kalistenik"]
        k_seans = min(3, max(1, math.ceil(kolay_hedef * 0.7 / max(20, min(dk, 60)))))   # kalan %30'u günlük yürüyüşten
        s[tas] = min(k_seans, kalan)
        kalan -= s[tas]
        if kalan > 0 and "jiujitsu" in sev and not ders:
            s["bjj_solo"] = 1
            kalan -= 1
        if kalan > 0:
            s["flow" if "flow" in sev else "mobilite"] = 1
            kalan -= 1
        if kalan > 0 and "jiujitsu" in sev and ders and not s["bjj_solo"]:
            s["bjj_solo"] = 1
            kalan -= 1
        if kalan > 0 and {"kas", "beceri"} & H and s["kalistenik"] < 4:
            s["kalistenik"] += 1
            kalan -= 1
        if kalan > 0 and "kondisyon" in H and s[tas] < 4:
            s[tas] += 1
            kalan -= 1
    else:
        s = {k: max(0, min(7, int(v or 0))) for k, v in sayilar.items() if k in ("kalistenik", "bisiklet", "kardiyo", "bjj_solo", "flow", "mobilite")}
        tas = "bisiklet" if s.get("bisiklet") else ("kardiyo" if s.get("kardiyo") else tas)

    kardiyo_dk = min(max(dk, 30), 60) if tas == "bisiklet" else min(max(dk, 25), 50)
    yogun_ders = len(ders) > 0
    satirlar = []
    if ders:
        satirlar.append({"kod": "bjj_ders", "ad": "Jiu-jitsu dersi", "haftada": len(ders), "dk": int((p.get("bjj_ders") or {}).get("sure_dk") or 90), "rol": "Ders · yoğun",
                         "neden": ROL_NEDEN["bjj_ders"], "sabit": True})
    if s.get("kalistenik"):
        satirlar.append({"kod": "kalistenik", "ad": "Güç antrenmanı", "haftada": s["kalistenik"], "dk": dk, "rol": "Güç", "neden": ROL_NEDEN["guc"]})
    for k in ("bisiklet", "kardiyo"):
        if s.get(k):
            ad = "Bisiklet" if k == "bisiklet" else KARDIYO_TUR[ktur]
            ned = ROL_NEDEN["kolay"].format(dk=kolay_hedef)
            if not yogun_ders and not alisma:
                ned += " Bunlardan biri aralıklı olur: " + ROL_NEDEN["yogun"].split(": ")[1]
            satirlar.append({"kod": k, "ad": ad, "haftada": s[k], "dk": kardiyo_dk, "rol": "Kolay kardiyo" + ("" if yogun_ders or alisma else " · bir gün aralıklı"),
                             "neden": ned, "kardiyo_tur": ktur if k == "kardiyo" else None})
    if s.get("bjj_solo"):
        satirlar.append({"kod": "bjj_solo", "ad": "Jiu-jitsu drill (evde)", "haftada": s["bjj_solo"], "dk": min(dk, 25), "rol": "Beceri", "neden": ROL_NEDEN["bjj_solo"]})
    if s.get("flow"):
        satirlar.append({"kod": "flow", "ad": "Akış hareketleri", "haftada": s["flow"], "dk": min(dk, 30), "rol": "Hareketlilik", "neden": ROL_NEDEN["flow"]})
    if s.get("mobilite"):
        satirlar.append({"kod": "mobilite", "ad": "Hareketlilik ve denge", "haftada": s["mobilite"], "dk": 20, "rol": "Hareketlilik", "neden": ROL_NEDEN["hareketlilik"]})

    toplam = sum(x["haftada"] for x in satirlar)
    kardiyo_toplam = sum(x["haftada"] * x["dk"] for x in satirlar if x["kod"] in ("bisiklet", "kardiyo"))
    eklemeler = ["Her güç antrenmanının sonunda 2 dakika tek ayak denge; haftada üç gün yeter.",
                 "Haftada bir kez yere oturup kalkma alıştırması: yaş ilerledikçe en çok işe yarayan hareketlerden."]
    if kardiyo_toplam < kolay_hedef:
        eklemeler.insert(0, f"Antrenman olmayan günlerde 20-30 dakika yürüyüş: kalan {kolay_hedef - kardiyo_toplam} dakika buradan dolar (günlük görev olarak gelir).")
    uyari = []
    if s.get("kalistenik", 0) < 2:
        uyari.append("Güç antrenmanı haftada ikinin altında: kas kaybını durdurmak için en az iki öneririm.")
    if not s.get("bisiklet") and not s.get("kardiyo"):
        uyari.append("Kardiyo günü yok: kalp ve kondisyon için günlük yürüyüşleri mutlaka yapalım.")
    if toplam > n:
        uyari.append(f"Haftada {n} gününüz var, program {toplam} antrenman: bazı günler iki kısa seans olur ya da sayıları azaltın.")
    if alisma:
        uyari.append("İlk haftalarda seanslar kısa (10-20 dk); alıştıkça buradaki sürelere çıkarız.")
    ag = [x for x in p.get("sakatliklar") or [] if x]
    if ag:
        uyari.append("Ağrılarınız: " + "; ".join(ag[:3]) + ". Bu bölgeleri yükleyen hareketler kolay basamaktan başlar.")
    yontemler = {"kalistenik": s.get("kalistenik", 0), "bisiklet": s.get("bisiklet", 0), "kardiyo": s.get("kardiyo", 0), "bjj_solo": s.get("bjj_solo", 0),
                 "flow": s.get("flow", 0), "mobilite": s.get("mobilite", 0)}
    return {"satirlar": satirlar, "eklemeler": eklemeler, "uyarilar": uyari, "yontemler": yontemler, "gun": n, "toplam": toplam,
            "kardiyo_tur": ktur, "dozlar": {"guc": max(2, s.get("kalistenik", 0)), "kolay_dk": kolay_hedef, "yogun": 0 if alisma else 1, "denge": 3,
                                            "hareketlilik": max(1, s.get("flow", 0) + s.get("mobilite", 0))},
            "ozet": _ozet_cumlesi(satirlar, n), "moduller": _moduller(p)}


def _moduller(p):
    try:
        import pt_modul
        return pt_modul.sec(p, recete_oku().get("modul_cikan"))
    except Exception:  # noqa: BLE001
        return []


def _ozet_cumlesi(satirlar, n):
    SAYIM = {"flow": "akış seansı", "mobilite": "hareketlilik ve denge seansı", "bjj_solo": "evde jiu-jitsu drill'i", "bisiklet": "bisiklet turu"}
    parca = [f"{x['haftada']} {SAYIM.get(x['kod']) or x['ad'].lower()}" for x in satirlar]
    return f"Haftada {n} gün: " + ", ".join(parca) + "." if parca else ""


def recete_oku():
    return pt._json(RECETE, {})


def recete_kaydet(sayilar=None, kardiyo_tur=None):
    """Kişi onayladı: reçete kaydedilir, profilin yöntemleri buna göre güncellenir."""
    p = pt.profil()
    r = recete(p, sayilar, kardiyo_tur)
    kayit = {**r, "zaman": int(time.time()), "onay": True, "modul_cikan": recete_oku().get("modul_cikan") or []}
    pt._yaz(RECETE, kayit)
    y = {**(p.get("yontemler") or {}), **r["yontemler"]}
    ek = {"yontemler": y, "kardiyo_tur": r["kardiyo_tur"]}
    pt.profil_kaydet(ek)
    return kayit


def recete_metni():
    """Plan istemine: onaylanan reçete ve doz kuralları."""
    r = recete_oku()
    if not r.get("satirlar"):
        return "Reçete yok; profildeki yöntemlere göre yaz. Yine de haftada en az 2 güç antrenmanı ve kolay kardiyo olsun."
    d = r.get("dozlar") or {}
    satir = "; ".join(f"{x['ad']} haftada {x['haftada']} × {x['dk']} dk ({x['rol']})" for x in r["satirlar"])
    kardiyo = KARDIYO_TUR.get(r.get("kardiyo_tur") or "yuruyus", "Tempolu yürüyüş")
    return (f"{satir}. Kardiyo günü bisiklet değilse tur 'kardiyo' ({kardiyo}). UZUN ÖMÜR DOZU: güç en az {d.get('guc', 2)} seans; kolay kardiyo "
            f"toplam en az {d.get('kolay_dk', 150)} dk (konuşabilecek tempo); " + ("haftada 1 yoğun çalışma (aralıklı kardiyo ya da BJJ dersi); " if d.get("yogun") else "")
            + "güç seanslarının Kapanış bölümüne tek_ayak_denge (2×30 sn her ayak); haftada bir seansa yere_otur_kalk (2×5). MODÜLLER: "
            + __import__("pt_modul").metin(r.get("moduller") or []))


def uzman_notlari(p=None, g=None):
    """Claude yoksa: her uzmanın tek cümlesi, göstergelerden."""
    p = p or pt.profil()
    g = g or gostergeler(p)
    by = {x["kod"]: x for x in g}
    eksik = [x["ad"].lower() for x in g if x["durum"] == "yok" and x.get("test")]
    zayif = [x["ad"].lower() for x in g if x["durum"] == "gelistir"]
    return [
        {"uzman": "Antrenör", "not": "Haftada en az iki güç antrenmanı; her hareket ölçerek bir üst basamağa geçer."},
        {"uzman": "Dayanıklılık koçu", "not": "Kardiyonun çoğu konuşabileceğiniz tempoda; haftada bir kez nefes nefese."},
        {"uzman": "Diyetisyen", "not": "Protein her öğünde, lif her gün; kalori hedefiniz tartıya göre kendini düzeltir."},
        {"uzman": "Fizyoterapist", "not": ("Ağrıyan bölgeler kolay basamaktan başlar. " if p.get("sakatliklar") else "") + "Haftada üç gün iki dakikalık denge yeter."},
        {"uzman": "Uyku ve toparlanma koçu", "not": f"Uyku ortalamanız {by['uyku']['deger']} saat; hedef 7-9." if by["uyku"]["deger"] else "Sabah kontrolünde uykunuzu yazın; programı ona göre ayarlarım."},
        {"uzman": "Uzun ömür uzmanı", "not": ("Önce şu ölçüleri alalım: " + ", ".join(eksik[:3]) + ". ") if eksik else
         ("Geliştireceğimiz: " + ", ".join(zayif[:3]) + ". " if zayif else "Göstergeleriniz iyi; korumak hedef. ") + "Yılda bir kez tansiyon, kan şekeri ve kolesterolü doktorunuza ölçtürün."},
        *([{"uzman": "Zihin-beden uzmanı", "not": "Programınıza ekledim: " + ", ".join(m["ad"].lower() for m in _moduller(p)[:3]) + "; nedenleri programda yazılı."}]
           if _moduller(p) else []),
        {"uzman": "Alışkanlık koçu", "not": "Kısa da olsa her gün bir şey: seri, eksik günleri değil devam etmeyi sayar."},
    ]


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "recete":
        print(json.dumps(recete(), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "doz":
        print(json.dumps(doz_ozeti(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(gostergeler(), ensure_ascii=False, indent=1, default=str))
