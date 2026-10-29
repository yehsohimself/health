"""pt_koc.py - PT'nin koçluk akışı (2026-10-25; kullanıcı: "PT + diyetisyenim varmış gibi hissetmeliyim; bana neler sorar, hayatımı nasıl düzenler,
neler önerir, beni nasıl programlar").

- Günün akışı (`gun_akisi`): kalkıştan yatışa saat saat: sabah kontrolü, pencere, menüdeki öğünler, antrenman (saatli ya da gün düzenine göre),
  su, masa başı molası, takvimdeki toplantılar (gri), akşam görüşmesi, uykuya hazırlık. Her öğenin durumu (bitti / şimdi / sırada / geçti).
- Akşam görüşmesi (`aksam_kaydet`): antrenman, beslenmeye uyum, açlık, enerji → yarının hazırlığı (seans, ilk öğün, menüden çıkarılacaklar) +
  koçun iki cümlesi (sonnet; Claude yoksa kural tabanlı).
- Pazar görüşmesi (`haftalik_sorular`, `haftalik_kaydet`): haftanın verisinden 4-5 seçenekli soru (sonnet) + tartı/bel → cevaplar koç mesajına ve
  gelecek haftanın planına istek olarak girer; bu haftanın alışkanlık hedefi seçilir.
- Programlama blokları (`blok`): 5 haftalık bloklar (4 yüklenme + 1 hafif); ad ve amaç hedeflere göre; plan istemine girer.
- Gün içi tek soru (`ara_soru`): profilde cevabı olmayan, programı değiştirecek sorulardan biri (günde en çok bir).
- Kutlama (`kutlamalar`): kişisel rekor (hareket başına en iyi set); seri ve rozetler pt_oyun.py.
"""
import datetime as dt
import json
import time

import pt

SAAT_DILIM = {"sabah": "07:30", "ogle": "12:30", "aksam": "18:30", "degisir": "18:00"}

# ----------------------------------------------------------------------------- yardımcılar


def _dk(s, varsayilan="08:00"):
    try:
        h, m = str(s or varsayilan).split(":")[:2]
        return int(h) * 60 + int(m)
    except ValueError:
        return _dk(varsayilan)


def _saat(dk):
    dk = max(0, min(24 * 60 - 1, int(dk)))
    return f"{dk // 60:02d}:{dk % 60:02d}"


def gun_duzeni(p=None):
    p = p or pt.profil()
    g = p.get("gun_duzeni") or {}
    return {"kalkis": g.get("kalkis") or "07:00", "yatis": g.get("yatis") or "23:00", "is_bas": g.get("is_bas") or "09:00", "is_bit": g.get("is_bit") or "18:00",
            "is_yeri": g.get("is_yeri") or "", "yogun_gunler": g.get("yogun_gunler") or []}

# ----------------------------------------------------------------------------- programlama blokları
BLOK_ADLARI = ["Temel", "Gelişim", "Yoğunlaşma"]


def blok(kod=None, p=None):
    """Hangi blokta, kaçıncı haftadayız. 5 haftalık döngü: 1-4 yüklenme, 5 hafif + yeniden test."""
    p = p or pt.profil()
    kod = kod or pt.hafta_kodu()
    no = pt._hafta_no(kod)
    blok_no = (no - 1) // 5 + 1
    hafta = (no - 1) % 5 + 1
    ad = BLOK_ADLARI[min(blok_no - 1, len(BLOK_ADLARI) - 1)] if blok_no <= len(BLOK_ADLARI) else BLOK_ADLARI[1 + (blok_no % 2)]
    H = set(p.get("hedef_turleri") or [])
    if blok_no == 1:
        amac = "Hareketleri doğru öğrenmek, düzen kurmak ve başlangıç seviyenizi oturtmak."
    elif "beceri" in H and "kilo" in H:
        amac = "Becerilerde bir üst basamak ve kalori açığında kası korumak."
    elif "beceri" in H:
        amac = "Becerilerde bir üst basamağa geçmek."
    elif "kilo" in H:
        amac = "Kas kaybetmeden yağ vermek; tekrar sayılarını korumak."
    else:
        amac = "Kuvveti ve kondisyonu adım adım artırmak."
    return {"no": blok_no, "ad": ad, "hafta": hafta, "toplam": 5, "hafif": hafta == 5, "amac": amac,
            "metin": f"{ad} blok · {hafta}. hafta / 5" + (" · hafif hafta ve yeniden test" if hafta == 5 else "")}

# ----------------------------------------------------------------------------- günün akışı


def gun_akisi(tarih=None):
    import pt_beslenme
    tarih = tarih or pt.bugun().isoformat()
    p = pt.profil()
    gd = gun_duzeni(p)
    d = pt.gun(tarih)
    gs = pt.gun_seansi(tarih)
    simdi = dt.datetime.now()
    bugun_mu = tarih == pt.bugun().isoformat()
    sdk = simdi.hour * 60 + simdi.minute if bugun_mu else -1
    L = []

    def ekle(dk, tur, baslik, detay="", bitti=False, eylem=None, sure=0):
        L.append({"saat": _saat(dk), "dk": dk, "tur": tur, "baslik": baslik, "detay": detay, "bitti": bool(bitti), "eylem": eylem, "sure": sure})

    kalkis, yatis = _dk(gd["kalkis"]), _dk(gd["yatis"], "23:00")
    if yatis < kalkis:
        yatis += 24 * 60
    ekle(kalkis + 15, "sabah", "Sabah kontrolü", "Dört kısa soru; seansı güne göre ayarlarım.", bitti=bool(d.get("sabah")), eylem="sabah")
    # takvim
    try:
        dolu = (pt.takvim_haftasi(pt.hafta_kodu(dt.date.fromisoformat(tarih))).get(tarih) or {}).get("dolu") or []
    except Exception:  # noqa: BLE001
        dolu = []
    for aralik in dolu:
        a, b = aralik.split("-")
        ekle(_dk(a), "takvim", "Toplantı", aralik.replace("-", "–"), sure=_dk(b) - _dk(a))
    # beslenme
    b = p.get("beslenme") or {}
    pen = pt_beslenme.pencere_durumu(p, tarih)
    menu = {}
    try:
        import pt_yemek
        menu = next((g for g in (pt_yemek.plan(pt.hafta_kodu(dt.date.fromisoformat(tarih))).get("gunler") or []) if g.get("tarih") == tarih), {}) or {}
    except Exception:  # noqa: BLE001
        pass
    yenen = {y.get("ad") for y in d.get("yemekler") or []}
    ogunler = menu.get("ogunler") or []
    if float(b.get("pencere_saat") or 14) < 14:
        ekle(_dk(pen["acilis"]), "pencere", "Yeme penceresi açılıyor", "Orucu proteinli bir öğünle açın.", bitti=bool(d.get("yemekler")))
    if ogunler:
        for i, o in enumerate(ogunler):
            ekle(_dk(o.get("saat"), pen["acilis"]), "ogun", o.get("ad") or "Öğün", f"{o.get('kcal', '')} kcal · {o.get('protein', '')} g protein",
                 bitti=o.get("ad") in yenen, eylem=f"ogun:{i}")
    else:
        n = int(b.get("ogun_sayisi") or 2)
        bas, son = _dk(pen["acilis"]), _dk(pen["kapanis"]) - 30
        for i in range(n):
            ekle(bas + (son - bas) * i // max(1, n - 1), "ogun", f"{i + 1}. öğün", "Menüden ya da kendi öğününüz", bitti=len(d.get("yemekler") or []) > i, eylem="yemek")
    if float(b.get("pencere_saat") or 14) < 14:
        ekle(_dk(pen["kapanis"]), "pencere", "Yeme penceresi kapanıyor", "Son öğün bundan önce bitsin.")
    # antrenman
    for s in gs["seanslar"]:
        if s.get("tur") == "dinlenme":
            continue
        saat = str(s.get("saat") or "")
        if s.get("tur") == "bjj_ders" and (p.get("bjj_ders") or {}).get("saat"):
            saat = p["bjj_ders"]["saat"]
        if not (len(saat) == 5 and saat[2] == ":"):
            dilim = saat or p.get("antrenman_saati") or "sabah"
            saat = {"sabah": _saat(kalkis + 45), "ogle": "12:30", "aksam": _saat(max(_dk(gd["is_bit"]) + 30, 17 * 60 + 30))}.get(dilim, SAAT_DILIM.get(dilim, "18:00"))
        ekle(_dk(saat), "seans", s.get("baslik") or "Antrenman", f"{s.get('sure_dk') or ''} dk", bitti=s.get("bitti"), eylem=f"seans:{s.get('id')}",
             sure=int(s.get("sure_dk") or 30))
    # su ve mola
    hedef_su = pt.su_hedefi(p)
    for i, kesir in enumerate((0.35, 0.65, 0.9)):
        dk = int(kalkis + (yatis - kalkis) * kesir)
        ekle(dk, "su", "Su", f"Bu saate kadar {round(hedef_su * (i + 1) / 3 / 100) / 10:.1f} L".replace(".", ","), bitti=(d.get("su_ml") or 0) >= hedef_su * (i + 1) / 3, eylem="su")
    if any("masa" in str(x.get("cevap", "")).lower() for x in p.get("ek_bilgi") or []) or gd["is_yeri"] in ("ofis", "ev_masa"):
        ekle(_dk(gd["is_bas"]) + 150, "mola", "Hareket molası", "2 dakika", eylem="mola")
        ekle(_dk(gd["is_bas"]) + 360, "mola", "Hareket molası", "2 dakika", eylem="mola")
    # akşam
    ekle(yatis - 120, "aksam", "Akşam görüşmesi", "Bugün nasıl geçti? Yarını hazırlayalım.", bitti=bool(d.get("aksam")), eylem="aksam")
    ekle(yatis - 30, "uyku", "Uykuya hazırlık", "Ekranları bırakın; oda serin ve karanlık.")
    ekle(yatis, "uyku", "Yatış", f"{(yatis - kalkis) / 60:.0f} saatlik uyku için".replace(".", ","))
    L.sort(key=lambda x: (x["dk"], x["tur"] != "takvim"))
    for x in L:
        if x["bitti"]:
            x["durum"] = "bitti"
        elif bugun_mu and x["dk"] + max(30, x["sure"]) < sdk and x["tur"] not in ("takvim", "uyku"):
            x["durum"] = "gecti"
        else:
            x["durum"] = "sirada"
    siradaki = next((x for x in L if x["durum"] == "sirada" and x["tur"] != "takvim" and x["dk"] + max(30, x["sure"]) >= sdk), None)
    if siradaki:
        siradaki["durum"] = "simdi"
    return {"tarih": tarih, "akis": L, "gun_duzeni": gd}

# ----------------------------------------------------------------------------- akşam görüşmesi

AKSAM_ISTEM = """Sen kişinin antrenörü ve diyetisyenisin. Akşam kısa bir değerlendirme yaptı. İKİ cümle yaz: bugünü değerlendir (somut, suçlamadan;
iyi giden bir şeyi söyle) ve yarın için tek bir öneri. Türkçe, "siz" dili, klişe yok.
BUGÜN: {bugun}
YARIN: {yarin}"""


def yarin_hazirligi(tarih=None):
    t = dt.date.fromisoformat(tarih) if tarih else pt.bugun()
    y = (t + dt.timedelta(days=1)).isoformat()
    gs = pt.gun_seansi(y)
    seans = [s for s in gs["seanslar"] if s.get("tur") != "dinlenme"]
    hazirlik = []
    if seans:
        s = seans[0]
        hazirlik.append(f"{s.get('baslik') or 'Antrenman'} ({s.get('sure_dk') or ''} dk): spor kıyafetinizi ve matı hazırlayın.")
    try:
        import pt_yemek
        g = next((g for g in (pt_yemek.plan(pt.hafta_kodu(dt.date.fromisoformat(y))).get("gunler") or []) if g.get("tarih") == y), None)
        if g and g.get("ogunler"):
            o = g["ogunler"][0]
            hazirlik.append(f"İlk öğün {o.get('saat', '')}: {o.get('ad')}.")
            et = [m.get("ad") for m in o.get("malzemeler") or [] if any(k in str(m.get("ad", "")).lower() for k in ("tavuk", "et", "kıyma", "balık", "hindi", "somon"))]
            if et:
                hazirlik.append(f"{et[0].capitalize()} dondurucudaysa bu akşam buzdolabına alın.")
    except Exception:  # noqa: BLE001
        pass
    return {"tarih": y, "seans": [{"baslik": s.get("baslik"), "sure_dk": s.get("sure_dk"), "tur": s.get("tur")} for s in seans], "hazirlik": hazirlik}


def aksam_kaydet(tarih, cevap):
    import claude_yaz
    tarih = tarih or pt.bugun().isoformat()
    a = {k: cevap.get(k) for k in ("antrenman", "beslenme", "aclik", "enerji", "uyku_saat", "not")}
    a["t"] = int(time.time())
    yarin = yarin_hazirligi(tarih)
    d = pt.gun(tarih)
    bugun = {"aksam": a, "seanslar": [{"tur": s.get("tur"), "sure_dk": s.get("sure_dk"), "zorluk": s.get("zorluk")} for s in d["seanslar"]],
             "yemek_sayisi": len(d["yemekler"]), "su_ml": d.get("su_ml"), "sabah": (d.get("sabah") or {}).get("isik")}
    koc = ""
    try:
        if claude_yaz.hazir():
            koc = claude_yaz.sor(AKSAM_ISTEM.format(bugun=json.dumps(bugun, ensure_ascii=False), yarin=json.dumps(yarin, ensure_ascii=False)),
                                 model_adi="sonnet", zaman_asimi=120).strip()[:400]
    except Exception:  # noqa: BLE001
        koc = ""
    if not koc:
        koc = ("Bugünü kaydettiniz; bu tek başına iyi bir alışkanlık." if a.get("antrenman") != "yaptim" else "Bugünkü antrenmanı tamamladınız.") + \
              (f" Yarın: {yarin['seans'][0]['baslik']}." if yarin["seans"] else " Yarın dinlenme günü.")
    a["koc"] = koc
    pt.gun_degistir(tarih, lambda x: x.update(aksam=a))
    return {"aksam": a, "yarin": yarin}

# ----------------------------------------------------------------------------- pazar görüşmesi

HAFTA_ISTEM = """Sen kişinin antrenörü ve diyetisyenisin. Haftalık görüşme yapıyorsunuz. Haftanın verisine bakıp 4 soru sor: her biri tek konu, seçenekli
(3-5 kısa, aynı düzeyde, birbirini dışlayan seçenek). Gözlemine dayansın ("Perşembe yine kaçtı" gibi): kaçırılan günlerin nedeni, zorlanma, açlık,
ağrı, gelecek hafta özel bir durum (seyahat, yoğunluk), sevilen/sevilmeyen hareket ya da öğün. Ayrıca bu hafta için 3 alışkanlık hedefi öner
(ölçülebilir, en çok 8 kelime, ör. "Her öğünde avuç içi kadar protein").
Türkçe, "siz" dili.
VERİ: {veri}
JSON: {{"giris": "haftayı iki cümleyle özetle", "sorular": [{{"soru": "...", "secenekler": ["..."]}}], "aliskanliklar": ["...", "...", "..."]}}"""


def haftalik_sorular(kod=None, yenile=False):
    import claude_yaz
    kod = kod or pt.hafta_kodu()
    yol = pt.MESAJLAR / f"{pt.hafta_gecerli(kod)}.gorusme.json"
    d = pt._json(yol, {})
    if d.get("sorular") and not yenile:
        return d
    v = pt.hafta_verisi(kod)
    try:
        c = claude_yaz.sor_json(HAFTA_ISTEM.format(veri=json.dumps(v, ensure_ascii=False, default=str)[:12000]), model_adi="sonnet", zaman_asimi=300)
    except Exception:  # noqa: BLE001
        c = {}
    sorular = [{"soru": str(s.get("soru"))[:200], "secenekler": [str(x)[:60] for x in s.get("secenekler") or []][:5]} for s in c.get("sorular") or []
               if s.get("soru") and len(s.get("secenekler") or []) >= 2][:5]
    if not sorular:
        sorular = [{"soru": "Bu hafta antrenmanlar nasıl geçti?", "secenekler": ["Planlandığı gibi", "Birkaçını kaçırdım", "Çoğunu kaçırdım"]},
                   {"soru": "Beslenme planına ne kadar uydunuz?", "secenekler": ["Çoğu gün", "Yarı yarıya", "Az"]},
                   {"soru": "Gelecek hafta özel bir durum var mı?", "secenekler": ["Yok", "Seyahat", "İş çok yoğun", "Hastalık/yorgunluk"]}]
    d = {"hafta": kod, "zaman": int(time.time()), "giris": str(c.get("giris") or "")[:400], "sorular": sorular,
         "aliskanliklar": [str(x)[:120] for x in c.get("aliskanliklar") or []][:3] or ["Her öğünde avuç içi kadar protein", "Günde 8 bin adım", "Yatmadan 30 dakika önce ekran yok"]}
    pt._yaz(yol, d)
    return d


def haftalik_kaydet(kod, cevaplar, aliskanlik=None, kilo=None, bel=None):
    """Cevaplar → koç mesajı ve gelecek hafta planının isteği. Döner: plan isteği metni."""
    kod = kod or pt.hafta_kodu()
    yol = pt.MESAJLAR / f"{pt.hafta_gecerli(kod)}.gorusme.json"
    d = pt._json(yol, {})
    d["cevaplar"] = cevaplar
    d["cevap_zaman"] = int(time.time())
    if aliskanlik:
        d["aliskanlik"] = aliskanlik
        sonraki = pt.hafta_kodu(pt.hafta_gunleri(kod)[0] + dt.timedelta(days=7))
        pt.profil_kaydet({"aliskanlik": {"hafta": sonraki, "metin": aliskanlik}})
    pt._yaz(yol, d)
    t = pt.bugun().isoformat()
    ek = {}
    if kilo:
        ek["kilo"] = float(str(kilo).replace(",", "."))
    if bel:
        ek["bel_cm"] = float(str(bel).replace(",", "."))
    if ek:
        pt.gun_degistir(t, lambda x: x.update(ek))
    return " ".join(f"{s.get('soru')} → {cevaplar.get(str(i)) or cevaplar.get(s.get('soru')) or ''}" for i, s in enumerate(d.get("sorular") or [])
                    if cevaplar.get(str(i)) or cevaplar.get(s.get("soru")))

# ----------------------------------------------------------------------------- alışkanlık hedefi


def aliskanlik_bugun(tarih=None):
    p = pt.profil()
    a = p.get("aliskanlik") or {}
    if not a.get("metin"):
        return None
    tarih = tarih or pt.bugun().isoformat()
    gunler = [g.isoformat() for g in pt.hafta_gunleri(pt.hafta_kodu(dt.date.fromisoformat(tarih)))]
    yapilan = [g for g in gunler if (pt._json(pt.gun_yolu(g), {}).get("aliskanlik") or {}).get("tamam")]
    return {"metin": a["metin"], "bugun": tarih in yapilan, "hafta": len(yapilan), "gun": gunler.index(tarih) + 1 if tarih in gunler else 0}

# ----------------------------------------------------------------------------- gün içi tek soru (koç sizi tanımaya devam eder)

ARA_SORULAR = [
    ("antrenman_zamani", "Antrenmanı hangi saatte yapınca daha iyi hissediyorsunuz?", ["Sabah", "Öğle", "Akşam", "Fark etmiyor"]),
    ("stres", "Bu aralar stresiniz ne düzeyde?", ["Düşük", "Orta", "Yüksek"]),
    ("aksam_atistirma", "Akşamları atıştırma isteği oluyor mu?", ["Hiç", "Bazen", "Sık sık"]),
    ("su_aliskanligi", "Gün içinde su içmeyi unutur musunuz?", ["Hayır", "Bazen", "Çoğu zaman"]),
    ("protein_kaynagi", "En sevdiğiniz protein kaynağı hangisi?", ["Tavuk", "Kırmızı et", "Balık", "Yumurta", "Baklagil"]),
    ("hafta_sonu", "Hafta sonları düzeniniz hafta içinden farklı mı?", ["Aynı", "Biraz farklı", "Çok farklı"]),
    ("motivasyon_dusuk", "Motivasyonunuz düştüğünde size en çok ne yardım eder?", ["Kısa bir seans", "Hatırlatma", "İlerlemeyi görmek", "Biriyle konuşmak"]),
    ("uyku_kalitesi", "Uykunuz genelde nasıl?", ["Derin", "Bölünüyor", "Uykuya dalmakta zorlanıyorum"]),
    ("kahve", "Günde kaç fincan kahve içiyorsunuz?", ["Hiç", "1-2", "3 ve üstü"]),
    ("muzik", "Antrenmanda sesli komutları ister misiniz?", ["Evet, hepsini", "Yalnız süreler", "Sessiz olsun"]),
    ("disarida_yeme", "Haftada kaç kez dışarıda yiyorsunuz?", ["Hiç", "1-2", "3-5", "Neredeyse her gün"]),
    ("en_zor", "Programın en zor yanı hangisi?", ["Vakit bulmak", "Beslenme", "Motivasyon", "Ağrı ya da yorgunluk"]),
]


def ara_soru():
    """Bugün sorulacak tek soru (cevaplanmamış ilk soru); günde en çok bir."""
    p = pt.profil()
    cev = p.get("ara_cevaplar") or {}
    bugun = pt.bugun().isoformat()
    if any(v.get("tarih") == bugun for v in cev.values()):
        return None
    for k, s, sec in ARA_SORULAR:
        if k not in cev:
            return {"kod": k, "soru": s, "secenekler": sec}
    return None


def ara_cevap(kod, cevap):
    p = pt.profil()
    soru = next((s for k, s, _ in ARA_SORULAR if k == kod), None)
    if not soru:
        return None
    cev = p.get("ara_cevaplar") or {}
    cev[kod] = {"cevap": str(cevap)[:80], "tarih": pt.bugun().isoformat()}
    ek = [x for x in p.get("ek_bilgi") or [] if x.get("soru") != soru] + [{"soru": soru, "cevap": str(cevap)[:80]}]
    pt.profil_kaydet({"ara_cevaplar": cev, "ek_bilgi": ek})
    return cev[kod]

# ----------------------------------------------------------------------------- kutlama


def kutlamalar(tarih=None):
    """Bugünün kişisel rekorları ve seri dönüm noktaları."""
    tarih = tarih or pt.bugun().isoformat()
    d = pt.gun(tarih)
    out = []
    onceki = {}
    for g in pt.gunler(120)[1:]:
        for s in g.get("seanslar") or []:
            for h in s.get("hareketler") or []:
                v = [float(x.get("deger")) for x in h.get("setler") or [] if x.get("deger") is not None]
                if v:
                    onceki[h["kod"]] = max(v + [onceki.get(h["kod"], 0)])
    kat = pt.katalog()
    for s in d.get("seanslar") or []:
        for h in s.get("hareketler") or []:
            v = [float(x.get("deger")) for x in h.get("setler") or [] if x.get("deger") is not None]
            if v and h.get("kod") in onceki and max(v) > onceki[h["kod"]]:
                olcu = (kat.get(h["kod"]) or {}).get("olcu")
                out.append({"tur": "rekor", "metin": f"Yeni rekor: {(kat.get(h['kod']) or {}).get('ad', h['kod'])} {int(max(v))}{' sn' if olcu == 'sure' else ' tekrar'} (önceki {int(onceki[h['kod']])})"})
    return out                                      # seri eşikleri ve rozetler pt_oyun'da (kutlama ekranı)
