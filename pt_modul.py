"""pt_modul.py - Health'in modülleri (2026-10-31; kullanıcı: "Uzak Doğu felsefesi, gerçek uzmanlıklar, modern tıp, bilim, alternatif tıp, her şeyden
yararlanabilir. Ama bunları ben seçmeyeyim; sistem ihtiyacımı anlayıp programımı düzenlesin. Program modüler olabilir, ihtiyaca göre, gidişata göre.")

İlke: kişi yöntem seçmez. Kod, kişinin işaretlerinden (stres, uyku, enerji, nabız değişkenliği, denge testi, iş düzeni, hedefler, sağlık
taraması) en çok 4 modül seçer; her modülün kaynağı (bilim, Uzak Doğu geleneği, doğa...), kanıt düzeyi (dürüstçe) ve kişiye özel nedeni yazılıdır.
Güvenlik kuralları kodda (kalp/tansiyon varsa soğuk su yok). Gidişata göre: her gün işaretler yeniden okunur; bir modülün nedeni ortadan kalkınca
çıkar, yeni bir ihtiyaç doğunca girer; değişiklik nedeniyle Bugün'de görünür ve geri alınabilir. Kişinin çıkardığı modül bir daha önerilmez.
"""
import datetime as dt
import statistics
import time

import pt

MODULLER = {
    "nefes": {"ad": "Nefes çalışması", "kaynak": "Bilim · yoga geleneği (pranayama)", "kanit": "orta", "uygulama": "nefes", "siklik": "her gün", "dk": 5,
              "ne": "Günde 5 dakika yavaş nefes: 4 saniye alın, 6 saniye verin. Ekrandaki halkayı izlemek yeter.",
              "kanit_not": "Dakikada 6 civarı yavaş nefes stres tepkisini yatıştırır, nabız değişkenliğini artırır, tansiyonu biraz düşürür.",
              "desen": [4, 0, 6, 0]},
    "meditasyon": {"ad": "Farkındalık meditasyonu", "kaynak": "Budist gelenek · klinik araştırma", "kanit": "orta", "uygulama": "nefes", "siklik": "haftada 3", "dk": 10,
                   "ne": "Haftada üç gün 10 dakika oturup nefesin girip çıkışını izlemek; akıl dağılınca nazikçe geri dönmek.",
                   "kanit_not": "Sekiz haftalık programlarda kaygı ve stres anlamlı biçimde azalıyor; etki orta büyüklükte.",
                   "desen": [5, 0, 5, 0]},
    "taichi": {"ad": "Tai chi ve qigong", "kaynak": "Uzak Doğu geleneği", "kanit": "güçlü", "uygulama": "video", "siklik": "haftada 2", "dk": 15,
               "ne": "Haftada iki kez 15 dakika yavaş, akışkan hareket; ağırlık bir ayaktan diğerine geçerken denge çalışır.",
               "kanit_not": "Denge ve düşme riskinde en güçlü kanıtı olan yöntemlerden; yaşlılarda düşmeleri belirgin azaltıyor.",
               "video_ara": "tai chi for beginners 15 minute follow along"},
    "isik": {"ad": "Sabah ışığı", "kaynak": "Uyku bilimi", "kanit": "orta", "uygulama": "gorev", "siklik": "her gün", "dk": 10,
             "ne": "Uyandıktan sonraki bir saat içinde 10 dakika dışarıda gün ışığında olmak (bulutlu gün de sayılır).",
             "kanit_not": "Sabah ışığı iç saati ayarlar: akşam uykuya dalmayı kolaylaştırır, gündüz uyanıklığı artırır."},
    "uyku": {"ad": "Uyku düzeni", "kaynak": "Uyku tıbbı", "kanit": "güçlü", "uygulama": "gorev", "siklik": "her gün", "dk": 0,
             "ne": "Her gün aynı saatte yatıp kalkmak; yatmadan 1 saat önce ekran ve ağır yemek yok, yatak odası serin ve karanlık.",
             "kanit_not": "Düzenli uyku saati, uykusuzlukta ilaçsız ilk tedavinin (BDT-U) temel parçası."},
    "orman": {"ad": "Doğa yürüyüşü (shinrin-yoku)", "kaynak": "Japon geleneği · çevre psikolojisi", "kanit": "orta", "uygulama": "gorev",
              "siklik": "haftada 1", "dk": 40,
              "ne": "Haftada bir yürüyüşünüzü parkta ya da ormanda, telefonsuz ve acele etmeden yapın; sesleri ve kokuları fark edin.",
              "kanit_not": "Yeşil alanda vakit stres hormonunu ve nabzı düşürüyor; kolay kardiyo dakikalarına da sayılır."},
    "hara": {"ad": "%80 tokluk (hara hachi bu)", "kaynak": "Okinawa geleneği", "kanit": "sınırlı", "uygulama": "not", "siklik": "her öğün", "dk": 0,
             "ne": "Öğünde tam doymadan, yüzde 80 tokken bırakmak; yavaş yemek ve çatalı ara ara bırakmak.",
             "kanit_not": "Okinawa'nın uzun yaşayanlarının alışkanlığı; yavaş yemek daha az kalori almayla ilişkili. Doğrudan deneysel kanıt sınırlı."},
    "mola": {"ad": "Hareket molası", "kaynak": "İş sağlığı araştırmaları", "kanit": "orta", "uygulama": "gorev", "siklik": "her gün", "dk": 4,
             "ne": "Oturarak geçen her saatin sonunda 2 dakika kalkıp hareket: omuz çevirme, kalça açma, birkaç squat.",
             "kanit_not": "Uzun kesintisiz oturmayı bölmek kan şekeri ve kan basıncı tepkilerini iyileştiriyor."},
    "soguk": {"ad": "Soğuk su", "kaynak": "Geleneksel uygulama · yeni araştırma", "kanit": "sınırlı", "uygulama": "gorev", "siklik": "her gün", "dk": 1,
              "ne": "Duşun son 30 saniyesi soğuk su. Nefesinizi yavaş tutun.",
              "kanit_not": "Uyanıklık ve ruh hali üzerine küçük çalışmalar olumlu; uzun ömre etkisi bilinmiyor. Kalp ya da tansiyon sorununda yapılmaz.",
              "guvenlik": "kalp"},
    "sauna": {"ad": "Sauna", "kaynak": "Fin geleneği · gözlemsel araştırma", "kanit": "orta", "uygulama": "gorev", "siklik": "haftada 2", "dk": 20,
              "ne": "Haftada 2-3 kez 15-20 dakika sauna; bol su için, alkolle birlikte değil.",
              "kanit_not": "Finlandiya'daki büyük izlem çalışmalarında sık saunaya girenlerde kalp-damar ölümleri daha az; neden-sonuç kesin değil.",
              "guvenlik": "kalp"},
}
UYGULAMA_AD = {"nefes": "Rehberli", "video": "Video ile", "gorev": "Günlük görev", "not": "Öğünlerde"}
KAYNAK_AILE = {"nefes": "bilim", "meditasyon": "dogu", "taichi": "dogu", "isik": "bilim", "uyku": "tip", "orman": "doga", "hara": "dogu",
               "mola": "bilim", "soguk": "gelenek", "sauna": "gelenek"}
OLAYLAR = pt.VERI / "modul_olaylar.json"


def _metin(p):
    return " ".join(str(x.get("cevap") or "") + " " + str(x.get("soru") or "") for x in p.get("ek_bilgi") or []).lower() + " " + \
        " ".join(str(n.get("metin") or "") for n in p.get("notlar") or []).lower()


def sinyaller(p=None):
    """Kişinin ihtiyaç işaretleri (kodla, ölçümden). Her biri {anahtar: (değer, açıklama)}."""
    p = p or pt.profil()
    S = {}
    sabah = [d.get("sabah") for d in pt.gunler(14) if d.get("sabah")]
    enerji = [float(s["enerji"]) for s in sabah if isinstance(s.get("enerji"), (int, float))]
    uyku = [float(s["uyku_saat"]) for s in sabah if isinstance(s.get("uyku_saat"), (int, float))]
    st = p.get("stres")
    if st in ("yogun", "orta"):
        S["stres"] = (2 if st == "yogun" else 1, "günlerinizin çoğunun stresli geçtiğini söylediniz" if st == "yogun" else "günlerinizin arada bir yoğun geçtiğini söylediniz")
    if len(enerji) >= 4 and statistics.mean(enerji[:7]) <= 2.6:
        S["enerji"] = (2, f"son sabahlarda enerjiniz ortalama {statistics.mean(enerji[:7]):.1f}/5")
    try:
        import pt_saglik
        h = pt_saglik.hazirlik()
        if h.get("hrv_durum") == "dusuk":
            S["hrv"] = (2, "nabız değişkenliğiniz kendi aralığınızın altında")
    except Exception:  # noqa: BLE001
        pass
    if len(uyku) >= 4 and statistics.mean(uyku[:7]) < 6.8:
        S["uyku"] = (2, f"son günlerde ortalama {statistics.mean(uyku[:7]):.1f} saat uyuyorsunuz")
    elif p.get("uyku_kalite") in ("kotu", "bolunuyor"):
        S["uyku"] = (2 if p["uyku_kalite"] == "kotu" else 1, "uykunuzun " + ("çoğu gece kötü" if p["uyku_kalite"] == "kotu" else "bazen bölündüğünü") + " söylediniz")
    T = {}
    for k in pt.testler().get("kayitlar") or []:
        T.update(k.get("sonuclar") or {})
    yas = p.get("yas") or 0
    if isinstance(T.get("tek_ayak_sn"), (int, float)) and T["tek_ayak_sn"] < 30:
        S["denge"] = (2, f"tek ayak üstünde {T['tek_ayak_sn']:g} saniye durabildiniz")
    elif yas >= 50:
        S["denge"] = (1, f"{yas} yaşından sonra denge yılda bir biraz azalır")
    m = _metin(p)
    if p.get("is_duzeni") == "oturarak" or any(k in m for k in ("masa", "bilgisayar başında", "oturarak", "ofis")):
        S["oturma"] = (2, "gününüzün çoğu oturarak geçiyor")
    if "kilo" in (p.get("hedef_turleri") or []):
        S["kilo"] = (1, "kilo vermek istiyorsunuz")
    if "sauna" in m or "sauna" in (p.get("ekipman") or []):
        S["sauna"] = (1, "saunaya erişiminiz var")
    if {"yuruyus"} & set(p.get("sevdikleri") or []):
        S["doga"] = (1, "yürüyüşü ve doğayı seviyorsunuz")
    if "uzun_omur" in (p.get("hedef_turleri") or []):
        S["uzun"] = (1, "asıl hedefiniz uzun ve sağlıklı yaşamak")
    S["kalp"] = (1 if any(v for k, v in (p.get("tarama") or {}).items() if k in ("kalp", "gogus")) else 0, "")
    return S


def _adaylar(S):
    """(puan, kod, neden) listesi."""
    A = []
    def ekle(kod, puan, *anahtar):
        n = [S[a][1] for a in anahtar if a in S and S[a][1]]
        A.append((puan, kod, (n[0][:1].upper() + n[0][1:] + ".") if n else ""))
    stres = sum(S.get(k, (0,))[0] for k in ("stres", "hrv", "enerji"))
    if stres:
        ekle("nefes", 3 + stres, "hrv", "stres", "enerji")
    if S.get("stres", (0,))[0] >= 2 or (S.get("stres") and S.get("uyku")):
        ekle("meditasyon", 2 + S["stres"][0], "stres")
    if "denge" in S:
        ekle("taichi", 2 + S["denge"][0] + (1 if "uzun" in S else 0), "denge")
    if "uyku" in S:
        ekle("uyku", 3 + S["uyku"][0], "uyku")
        ekle("isik", 1 + S["uyku"][0], "uyku")
    elif "enerji" in S:
        ekle("isik", 3, "enerji")
    if "oturma" in S:
        ekle("mola", 4, "oturma")
    if "doga" in S and stres:
        ekle("orman", 2 + min(stres, 2), "stres", "doga")
    if "kilo" in S:
        ekle("hara", 2, "kilo")
    if "sauna" in S and not S["kalp"][0]:
        ekle("sauna", 2, "sauna")
    if "enerji" in S and not S["kalp"][0] and "uyku" not in S:
        ekle("soguk", 1, "enerji")
    if not A and "uzun" in S:                                 # işaret yokken uzun ömür hedefi: dengeyi erken koru
        A.append((1, "taichi", "Denge yaşla erken bozulur; erken başlamak düşmeleri önlemenin en kolay yolu."))
    return A


def sec(p=None, cikan=None, en_cok=4):
    """Kişiye seçilen modüller: [{kod, ad, kaynak, aile, kanit, kanit_not, ne, siklik, dk, uygulama, neden}]."""
    p = p or pt.profil()
    S = sinyaller(p)
    cikan = set(cikan or [])
    gorulen, out = set(), []
    for puan, kod, neden in sorted(_adaylar(S), key=lambda x: -x[0]):
        if kod in gorulen or kod in cikan:
            continue
        m = MODULLER[kod]
        if m.get("guvenlik") == "kalp" and S["kalp"][0]:
            continue
        gorulen.add(kod)
        out.append({"kod": kod, **{k: v for k, v in m.items() if k not in ("video_ara", "guvenlik")}, "aile": KAYNAK_AILE.get(kod, "bilim"),
                    "neden": neden, "puan": puan})
        if len(out) >= en_cok:
            break
    return out


def _rc():
    import pt_uzun
    return pt_uzun.recete_oku()


def guncelle():
    """Gidişata göre modülleri yeniden seç (günde bir). Değişiklik varsa reçeteye yazar, olay kaydeder. Döner: [{kod, ad, ne, neden}]."""
    import pt_uzun
    rc = pt_uzun.recete_oku()
    if not rc.get("satirlar"):
        return []
    eski = {m["kod"]: m for m in rc.get("moduller") or []}
    yeni = sec(cikan=rc.get("modul_cikan"))
    Y = {m["kod"]: m for m in yeni}
    deg = [{"kod": k, "ad": Y[k]["ad"], "ne": "eklendi", "neden": Y[k]["neden"]} for k in Y if k not in eski]
    deg += [{"kod": k, "ad": eski[k]["ad"], "ne": "cikti", "neden": "Bu ihtiyaç şu an görünmüyor; gerekirse geri gelir."} for k in eski if k not in Y]
    if not deg:
        return []
    rc["moduller"] = yeni
    pt._yaz(pt_uzun.RECETE, rc)
    ol = pt._json(OLAYLAR, {"olaylar": []})
    ol["olaylar"] = ([{"t": int(time.time()), "tarih": pt.bugun().isoformat(), "degisim": deg, "onceki": list(eski.values())}] + ol["olaylar"])[:30]
    pt._yaz(OLAYLAR, ol)
    return deg


def son_olay(gun=3):
    ol = pt._json(OLAYLAR, {"olaylar": []}).get("olaylar") or []
    if not ol:
        return None
    o = ol[0]
    try:
        if (pt.bugun() - dt.date.fromisoformat(o["tarih"])).days > gun or o.get("goruldu") or o.get("geri"):
            return None
    except (KeyError, ValueError):
        return None
    return o


def olay_isaretle(t, geri=False):
    """Son değişikliği gördü ya da geri aldı. Geri alınca eski modüller döner ve eklenen modüller 'çıkan' sayılır (kişinin kararı)."""
    import pt_uzun
    ol = pt._json(OLAYLAR, {"olaylar": []})
    for o in ol["olaylar"]:
        if o.get("t") == t:
            o["goruldu"] = True
            if geri and not o.get("geri"):
                o["geri"] = True
                rc = pt_uzun.recete_oku()
                rc["moduller"] = o.get("onceki") or []
                rc["modul_cikan"] = sorted(set(rc.get("modul_cikan") or []) | {d["kod"] for d in o["degisim"] if d["ne"] == "eklendi"})
                pt._yaz(pt_uzun.RECETE, rc)
    pt._yaz(OLAYLAR, ol)


def cikar(kod, geri=False):
    """Kişi bir modülü istemedi (ya da geri istedi)."""
    import pt_uzun
    rc = pt_uzun.recete_oku()
    c = set(rc.get("modul_cikan") or [])
    if geri:
        c.discard(kod)
    else:
        c.add(kod)
    rc["modul_cikan"] = sorted(c)
    rc["moduller"] = sec(cikan=c)
    pt._yaz(pt_uzun.RECETE, rc)
    return rc["moduller"]


def _bugun_mu(m, t):
    """Modül bugün yapılacaklarda mı? her gün / haftada N (haftanın günlerine yayılır)."""
    s = m.get("siklik") or ""
    if s.startswith("haftada"):
        try:
            n = int(s.split()[1])
        except (IndexError, ValueError):
            n = 1
        gun = dt.date.fromisoformat(t).weekday()
        return gun in {0: (), 1: (5,), 2: (1, 4), 3: (0, 2, 4)}.get(n, (1, 3, 5))
    return s != "her öğün"


def gunun(t=None):
    """Bugünün modülleri: [{...modül, bitti, bugun}]. 'not' türü (öğünlerde) bilgi olarak gelir."""
    t = t or pt.bugun().isoformat()
    rc = _rc()
    yapilan = set(pt.gun(t).get("moduller") or [])
    out = []
    for m in rc.get("moduller") or []:
        out.append({**m, "bitti": m["kod"] in yapilan, "bugun": _bugun_mu(m, t)})
    return out


def isaretle(kod, t=None, geri=False):
    t = pt.tarih_gecerli(t or pt.bugun().isoformat())
    if kod not in MODULLER:
        raise ValueError("bilinmeyen modül")

    def f(d):
        L = set(d.get("moduller") or [])
        (L.discard if geri else L.add)(kod)
        d["moduller"] = sorted(L)
    pt.gun_degistir(t, f)
    return gunun(t)


def video(kod):
    """Modülün rehberli videosu (bir kez aranır, önbellekte): {id, baslik, kanal, sure}."""
    m = MODULLER.get(kod) or {}
    if not m.get("video_ara"):
        return None
    yol = pt.KLASOR / "pt_medya" / "modul_video.json"
    V = pt._json(yol, {})
    if kod in V:
        return V[kod]
    import pt_youtube
    sec_ = None
    for r in pt_youtube._ara(m["video_ara"], 8):
        if 8 * 60 <= r["sure"] <= 30 * 60 and pt_youtube._gomulur(r["id"]):
            sec_ = r
            break
    V[kod] = sec_
    pt._yaz(yol, V)
    return sec_


def metin(moduller):
    """Plan istemine: seçilen modüller ve nedenleri."""
    if not moduller:
        return "Modül yok."
    return "; ".join(f"{m['ad']} ({m['siklik']}, {m['dk']} dk; neden: {m['neden']})" for m in moduller) + \
        ". Bunlar seanslara ek; tai chi seçildiyse hareketlilik ve denge günlerinden birine 15 dakika olarak koy, nefes çalışmasını seans sonuna 2 dakika ekleyebilirsin."
