"""pt_beslenme.py - PT'nin diyetisyen tarafı (2026-10-25).

- Hedefler: Mifflin-St Jeor + etkinlik çarpanı ile başlangıç harcaması; haftalık kilo hızı (varsayılan vücut ağırlığının %0,7'si, en çok %1)
  açığa çevrilir. Protein ISSN 2026 aralığı: kilo başına 1,6-2,2 g (fazla kiloluysa HEDEF kiloya göre); varsayılan 2,0 g/kg.
- Kendini düzelten hedef (MacroFactor deseni): trend kilo = üstel ortalama (eksik günler doldurulur); harcama = kaydedilen ortalama yemek −
  trend değişiminin enerji karşılığı (7700 kcal/kg). 14 günde en az 8 kayıtlı gün varsa tahmin 0,25 ağırlıkla güncellenir. Kırmızı sayı yok,
  ceza yok: her hafta bağımsız, hedefin neden değiştiği yazılır.
- 18/6: pencere ilk yemek kaydıyla açılır (ayrı başlat/durdur yok); oruç "aşama" etiketleri gösterilmez (dayanağı doğrulanmadı).
- Yemek kaydı: fotoğraf + cümle (ya da yalnız biri) → Claude düzeltilebilir tabak çıkarır; her sayının kaynağı yazılır; yağ sorusu (fotoğraf
  testlerinde en büyük açık kaçırılan yağ, öğün başına ~30 g).
"""
import datetime as dt
import json
import time
import uuid
from pathlib import Path

import pt

DOSYA = pt.VERI / "beslenme.json"
FAVORI = pt.VERI / "favoriler.json"
KCAL_KG = 7700


def durum_dosyasi():
    return pt._json(DOSYA, {"harcama": None, "harcama_gecmis": [], "hedef_gecmis": []})


def _yaz(d):
    pt._yaz(DOSYA, d)


def bmr(p):
    kilo, boy, yas = p.get("kilo_kg"), p.get("boy_cm"), p.get("yas")
    if not (kilo and boy and yas):
        return None
    return 10 * float(kilo) + 6.25 * float(boy) - 5 * float(yas) + (5 if p.get("cinsiyet") != "kadin" else -161)


def yapilan_dk_haftalik(gun=14):
    """Son `gun` günde GERÇEKTEN bitirilen seansların haftalık ortalama dakikası (planlanan değil)."""
    son, top = pt.bugun(), 0
    for i in range(gun):
        d = pt._json(pt.gun_yolu((son - dt.timedelta(days=i)).isoformat()), {})
        top += sum(int(s.get("sure_dk") or 0) for s in d.get("seanslar") or [] if s.get("bitti"))
    return top * 7 / gun


def etkinlik_carpani(p):
    """Gerçekten yapılan antrenman dakikasına göre (2026-10-28: planlanan dakika sayılıyordu; hiç antrenman yapılmadan harcama
    şişiyor, kalori hedefi gereğinden düşük çıkıyordu). Masa başı çalışan için taban 1,25."""
    dk = yapilan_dk_haftalik()
    masa = "masa" in json.dumps(p.get("ek_bilgi") or [], ensure_ascii=False).lower()
    taban = 1.25 if masa else 1.3
    return round(taban + min(0.4, dk / 1000), 3)


def trend(gun_sayisi=60):
    """Kilo trendi: üstel ortalama (alfa 0,1), eksik günler önceki trendle doldurulur. [(tarih, ham|None, trend)]"""
    son = pt.bugun()
    L, tr = [], None
    for i in range(gun_sayisi - 1, -1, -1):
        g = (son - dt.timedelta(days=i)).isoformat()
        d = pt._json(pt.gun_yolu(g), {})
        k = d.get("kilo")
        if k:
            tr = float(k) if tr is None else tr + 0.1 * (float(k) - tr)
        L.append((g, k, round(tr, 2) if tr is not None else None))
    return L


def gun_toplam(d):
    t = {"kcal": 0.0, "protein": 0.0, "yag": 0.0, "karb": 0.0, "lif": 0.0, "doymus": 0.0}
    for y in d.get("yemekler") or []:
        for k in y.get("kalemler") or []:
            for a in t:
                try:
                    t[a] += float(k.get(a) or 0)
                except (TypeError, ValueError):
                    pass
    return {a: round(v) for a, v in t.items()}


def harcama_guncelle():
    """Son 14 günün kaydedilen yemeği ve trend değişiminden harcama tahmini; eski tahminle harmanlanır."""
    d = durum_dosyasi()
    p = pt.profil()
    ilk = (bmr(p) or 0) * etkinlik_carpani(p)
    eski = d.get("harcama") or ilk or None
    tr = trend(28)
    son14 = tr[-14:]
    kayitli = []
    for g, _, _ in son14:
        gd = pt._json(pt.gun_yolu(g), {})
        if gd.get("yemekler") and not gd.get("eksik_kayit"):
            kayitli.append(gun_toplam(gd)["kcal"])
    gozlem = None
    trs = [t for _, _, t in son14 if t is not None]
    if len(kayitli) >= 8 and len(trs) >= 2:
        degisim_kg_gun = (trs[-1] - trs[0]) / max(1, len(son14) - 1)
        gozlem = sum(kayitli) / len(kayitli) - degisim_kg_gun * KCAL_KG
    yeni = ilk or eski            # gözlem yokken saklı değer değil, güncel tahmin (eski değer planlanan dakikayla şişmiş olabilir)
    if gozlem and eski:
        yeni = 0.75 * eski + 0.25 * gozlem
    elif gozlem:
        yeni = gozlem
    if yeni:
        d["harcama"] = round(yeni)
        d["harcama_gecmis"] = (d.get("harcama_gecmis") or [])[-60:] + [{"tarih": pt.bugun().isoformat(), "deger": round(yeni),
                                                                         "gozlem": round(gozlem) if gozlem else None, "kayitli_gun": len(kayitli)}]
        _yaz(d)
    return d.get("harcama"), gozlem, len(kayitli)


def hedefler(p=None):
    p = p or pt.profil()
    d = durum_dosyasi()
    son = (d.get("harcama_gecmis") or [{}])[-1]
    tahmin = (bmr(p) or 0) * etkinlik_carpani(p)
    harcama = (d.get("harcama") if son.get("gozlem") else tahmin) or d.get("harcama") or None   # gerçek veriyle düzelmediyse güncel tahmin
    kilo = p.get("kilo_kg")
    tr = [t for _, _, t in trend(14) if t]
    if tr:
        kilo = tr[-1]
    hiz = min(0.7, float((p.get("beslenme") or {}).get("kilo_hizi") or 0.5))   # haftada vücut ağırlığının en çok %0,7'si (kas kaybı ve yorgunluk)
    hedef_kilo = p.get("hedef_kilo_kg")
    kayip = bool(hedef_kilo and kilo and float(hedef_kilo) < float(kilo) - 0.3)
    acik = round(float(kilo) * hiz / 100 * KCAL_KG / 7) if kayip and kilo else 0
    taban_kcal = max(1500 if p.get("cinsiyet") != "kadin" else 1200, round((bmr(p) or 0) * 1.1))   # dinlenme metabolizmasının altına inilmez
    kcal = round(max(taban_kcal, harcama - acik)) if harcama else None
    # protein: fazla kiloluysa hedef kiloya göre (ISSN 2026)
    boy = p.get("boy_cm")
    taban = float(hedef_kilo or kilo or 0)
    if boy and kilo and not hedef_kilo:
        bmi = float(kilo) / (float(boy) / 100) ** 2
        if bmi > 27:
            taban = 25 * (float(boy) / 100) ** 2
    protein = round(taban * 2.0) if taban else None
    pencere = pencere_durumu(p)
    ogun = int((p.get("beslenme") or {}).get("ogun_sayisi") or 2)
    metin = " ".join(p.get("sinirlar") or []) + " " + json.dumps(p.get("saglik_degerleri") or {}, ensure_ascii=False)
    kol = "kolesterol" in metin.lower() or "ldl" in metin.lower()
    lif = max(25, round((kcal or 2000) / 1000 * 14))                           # 14 g / 1000 kcal (ABD beslenme kılavuzu), en az 25 g
    doymus = round((kcal or 2000) * (0.07 if kol else 0.10) / 9)               # kolesterol yüksekse enerjinin <%7'si (AHA), değilse <%10
    return {"kcal": kcal, "protein": protein, "lif": lif, "doymus_ust": doymus, "kolesterol": kol, "protein_aralik": [round(taban * 1.6), round(taban * 2.2)] if taban else None,
            "harcama": round(harcama) if harcama else None, "acik": acik, "kilo_trend": kilo, "kayip": kayip,
            "ogun_protein": round(protein / max(2, ogun)) if protein else None, "pencere": pencere,
            "neden": _hedef_nedeni(d, acik, hiz, harcama, kilo)}


def _hedef_nedeni(d, acik, hiz, harcama, kilo=None):
    g = (d.get("harcama_gecmis") or [])[-2:]
    if not harcama:
        return "Boy, kilo ve yaşınızı girdiğinizde hedef hesaplanır."
    if len(g) == 2 and g[0]["deger"] != g[1]["deger"] and g[1].get("kayitli_gun", 0) >= 8:   # kayıt yokken fark yöntemden gelir, kayıttan değil
        fark = g[1]["deger"] - g[0]["deger"]
        return (f"Son iki haftanın kayıtları ve kilo gidişiniz harcamanızı {abs(fark)} kcal {'yüksek' if fark > 0 else 'düşük'} gösterdi; hedef buna göre "
                f"{'arttı' if fark > 0 else 'azaldı'}.")
    sayi = lambda n: f"{round(n):,}".replace(",", ".")
    erken = "" if g and g[-1].get("kayitli_gun", 0) >= 8 else " Yemek ve kilo kaydettikçe hedef size göre ayarlanır."
    if acik and kilo:
        kg = str(round(float(kilo) * hiz / 100, 1)).replace(".", ",")
        return f"Haftada yaklaşık {kg} kg vermek için. Günlük harcamanız ~{sayi(harcama)} kcal.{erken}"
    return f"Kilonuzu korumaya göre. Günlük harcamanız ~{sayi(harcama)} kcal.{erken}"


def _dk(s):
    h, m = (str(s or "12:00") + ":0").split(":")[:2]
    return int(h) * 60 + int(m)


def pencere_durumu(p=None, tarih=None):
    """18/6: pencere planlanan saatte ya da ilk yemekte açılır; ilk yemek erken olursa o andan sayılır."""
    p = p or pt.profil()
    b = p.get("beslenme") or {}
    saat = float(b.get("pencere_saat") or 6)
    tarih = tarih or pt.bugun().isoformat()
    d = pt.gun(tarih)
    bas_dk = _dk(d.get("pencere_bas") or b.get("pencere_bas"))
    ilk = min([y.get("t") for y in d.get("yemekler") or [] if y.get("t")] or [None]) if d.get("yemekler") else None
    gun0 = dt.datetime.combine(dt.date.fromisoformat(tarih), dt.time())
    acilis = gun0 + dt.timedelta(minutes=bas_dk)
    if ilk:
        ilk_t = dt.datetime.fromtimestamp(ilk)
        if ilk_t < acilis:
            acilis = ilk_t
    if d.get("oruc_acildi"):                                    # "Orucu açtım" dokunuşu: pencere o andan sayılır
        acilis = dt.datetime.fromtimestamp(d["oruc_acildi"])
        if ilk:
            acilis = min(acilis, dt.datetime.fromtimestamp(ilk))
    kapanis = acilis + dt.timedelta(hours=saat)
    kapattim = bool(d.get("oruc_kapandi"))
    if kapattim:                                                # "Son yemeğimi yedim": pencere o anda kapanır
        kapanis = dt.datetime.fromtimestamp(d["oruc_kapandi"])
    simdi = dt.datetime.now()
    durum = "once" if simdi < acilis and not kapattim else "acik" if simdi < kapanis and not kapattim else "kapandi"
    oruc_bas = _oruc_basi(tarih)
    return {"acilis": acilis.strftime("%H:%M"), "kapanis": kapanis.strftime("%H:%M"), "acilis_t": int(acilis.timestamp()),
            "kapanis_t": int(kapanis.timestamp()), "durum": durum, "saat": saat, "kaydirildi": bool(d.get("pencere_bas")),
            "acildi": bool(d.get("oruc_acildi")), "kapattim": kapattim,
            "oruc_bas_t": int(oruc_bas) if oruc_bas else None, "hedef_oruc": 24 - saat}


def _oruc_basi(tarih):
    """Süren orucun başladığı an: bugün kapatıldıysa o an; yoksa (bugün henüz yenmediyse) dünün kapanışı ya da son yemeği."""
    d = pt.gun(tarih)
    if d.get("oruc_kapandi"):
        return d["oruc_kapandi"]
    if d.get("yemekler") or d.get("oruc_acildi"):
        return None
    dun = pt.gun((dt.date.fromisoformat(tarih) - dt.timedelta(days=1)).isoformat())
    return dun.get("oruc_kapandi") or max([y.get("t") or 0 for y in dun.get("yemekler") or []] or [0]) or None


def oruc_isaretle(tarih, ne, geri=False):
    """Tek dokunuş: ne = 'ac' (orucu şimdi açtım) | 'kapat' (son yemeğimi yedim). geri=True işareti kaldırır."""
    alan = {"ac": "oruc_acildi", "kapat": "oruc_kapandi"}[ne]

    def f(d):
        if geri:
            d.pop(alan, None)
        else:
            d[alan] = int(time.time())
            if ne == "ac":
                d.pop("oruc_kapandi", None)
    pt.gun_degistir(tarih, f)


def dunku_yemekler(tarih):
    """Önceki günün öğünleri (fotoğrafsız, sade): 'Dünkü gibi' listesi."""
    dun = (dt.date.fromisoformat(tarih) - dt.timedelta(days=1)).isoformat()
    L = []
    for y in pt.gun(dun).get("yemekler") or []:
        if not y.get("kalemler"):
            continue
        t = gun_toplam({"yemekler": [y]})
        L.append({"id": y["id"], "ad": y.get("ad") or ", ".join(k.get("ad", "") for k in y["kalemler"][:3]),
                  "ogun": y.get("ogun"), "kcal": t.get("kcal"), "protein": t.get("protein"), "kalem": len(y["kalemler"])})
    return {"tarih": dun, "liste": L}


def yemek_kopyala(tarih, kaynak, idler=None):
    """Kaynak günün öğünlerini (ya da yalnız `idler`) bugüne aynen ekler; yeni kimlik ve şimdiki zamanla."""
    L = [y for y in pt.gun(kaynak).get("yemekler") or [] if y.get("kalemler") and (not idler or y.get("id") in idler)]
    yeni = []
    for i, y in enumerate(L):
        k = {a: y[a] for a in ("ad", "ogun", "kalemler", "not") if a in y}
        k.update(id=f"y{int(time.time() * 1000)}{i}{uuid.uuid4().hex[:4]}", t=int(time.time()) + i, kopya=kaynak)   # aynı milisaniyede iki kopya birbirini ezmesin
        yeni.append(yemek_kaydet(tarih, k))
    return yeni


def pencere_onerisi(tarih=None):
    """Akşam BJJ dersi ya da geç antrenman pencere dışında kalıyorsa kaydırma önerisi."""
    p = pt.profil()
    gs = pt.gun_seansi(tarih)
    pd = pencere_durumu(p, tarih)
    aksam = [s for s in gs["seanslar"] if s.get("saat") == "aksam" or s.get("tur") == "bjj_ders"]
    if not aksam or pd["kaydirildi"]:
        return None
    bjj_saat = (p.get("bjj_ders") or {}).get("saat") or "19:00"
    kapanis_dk = _dk(pd["kapanis"])
    seans_dk = _dk(bjj_saat) if any(s.get("tur") == "bjj_ders" for s in aksam) else 19 * 60
    if seans_dk + 90 <= kapanis_dk:
        return None
    yeni_bas = max(_dk(pd["acilis"]), seans_dk + 120 - int(pd["saat"] * 60))
    return {"yeni": f"{yeni_bas // 60:02d}:{yeni_bas % 60:02d}",
            "neden": f"Bugün akşam {'BJJ dersi' if any(s.get('tur') == 'bjj_ders' for s in aksam) else 'antrenman'} var; antrenmandan sonra proteinli bir öğün pencereye sığsın."}


def pencere_kaydir(tarih, bas):
    pt.gun_degistir(tarih, lambda d: d.update(pencere_bas=bas))

# ----------------------------------------------------------------------------- yemek kaydı

YEMEK_ISTEM = """Sen bir diyetisyensin. Kullanıcının yediği öğünü {kaynak} tahmin et. Türk ev yemeklerini ve Almanya'daki market ürünlerini iyi bilirsin
(porsiyon: 1 kepçe çorba ~250 g, 1 dilim ekmek ~30 g, 1 tabak pilav ~180 g, 1 yemek kaşığı yağ ~10 g). Kullanıcı bir kalemin gramını ya da adedini söylediyse o kalemde AYNEN onu kullan (cömertlik kuralı yalnız söylenmeyen miktarlar için).
{foto_notu}
KULLANICININ YAZDIĞI: {metin}
GIDA HASSASİYETLERİ: {hassasiyet}
KULLANICININ SIK YEDİĞİ ÖĞÜNLER: {sik}
KULLANICININ GEÇMİŞ DÜZELTMELERİ (tahminlerini buna göre ayarla): {duzeltme}

Nasıl tahmin edeceksin:
1. Önce tabaktaki her yiyeceği ayır ve GRAMINI tahmin et (tabak ~26 cm, çatal ~19 cm, avuç, kaşık gibi ölçeklere bak). Ölçümlerde görsel modeller
   gramı ortalama %15-30 DÜŞÜK tahmin ediyor; özellikle büyük porsiyonlarda, et ve pilavda cömert ol.
2. Besin değerlerini Alman besin tablosundan (BLS 4.0) ben alacağım. Her kalem için "ara": BLS adlandırma tarzında 1-2 Almanca arama ifadesi ve 1
   İngilizce (ör. ["Reis gekocht", "Rice boiled"], ["Hähnchenbrustfilet gebraten", "Chicken breast fillet fried"], ["Joghurt mind. 3,5 % Fett",
   "Yogurt 3.5 % fat"], ["Linsensuppe", "Lentil soup"]); pişmişse pişirme sözcüğünü yaz (gekocht, gebraten, gegrillt, frittiert, gebacken).
   Tabloda olmayabilecek Türk yemeklerinde (börek, simit, mantı, karnıyarık, mercimek köftesi, dolma...) "tarif" de ver: yemeğin 100 gramındaki
   ana malzemeler ve gramları [{{"ad", "g", "ara": [...]}}] (toplam ~100 g; malzemeler PİŞMİŞ yemeğin 100 gramına denk: fırında/tencerede buharlaşan suyu yazma, un ve yağ oranı ona göre; yağı unutma).
   Yedek olarak 100 g değerlerini de yaz (yuz: kcal, protein, yag, karb, lif, doymus); yalnız tabloda karşılık bulunmazsa kullanılır.
3. Fotoğraflar yağı genelde eksik gösterir: kızartma, tereyağı, zeytinyağı, sos görünmüyorsa ama yemeğin doğası gereği varsa ayrı kalem yaz.
- "soru": sonucu en çok değiştirecek TEK kısa soru (ör. "Pilava tereyağı kondu mu?"); belirsizlik yoksa boş. "secenekler": o sorunun 2-4 kısa cevabı.
- "eslesen": öğün sık yediklerinden biriyle aynıysa onun adı, değilse boş.
- "hassasiyet_uyari": hassasiyet listesindeki bir malzeme varsa kısa uyarı, yoksa boş.
- "guven": dusuk|orta|yuksek.
JSON: {{"ad": "öğünün kısa adı", "kalemler": [{{"ad", "miktar_g", "ara": [], "tarif": [], "yuz": {{"kcal", "protein", "yag", "karb", "lif", "doymus"}}}}],
"soru": "", "secenekler": [],
"eslesen": "", "hassasiyet_uyari": "", "guven": "orta"}}"""

DUZELTME = pt.VERI / "yemek_duzeltme.json"

ESLE_ISTEM = """Her yiyecek için Alman besin tablosundaki (BLS 4.0) adaylardan EN UYGUN olanın kodunu seç. Aynı yiyecek ve aynı hazırlanış olmalı (pişmiş/çiğ,
kızartma/haşlama, yağ oranı, tatlandırılmış mı); en yakını açıkça başka bir şeyse (başka yiyecek, başka hazırlanış, tatlı/tuzlu farkı) boş bırak, uydurma.
Kullanıcının sözüne ve fotoğraftaki tarife göre en olası olanı seç; emin değilsen genel (kısa adlı) kalemi seç.
{liste}
JSON: {{"secim": {{"<id>": "<kod ya da boş>"}}}}"""


def _bls_esle(kalemler):
    """Modelin kalemlerini BLS kodlarına bağlar. Döner: {id: bls değeri}; id = "i" (kalem) ya da "i.j" (tarif malzemesi).
    Adaylar koddan (sözcük araması), seçim Claude'dan (yalnız adaylar arasından; listede olmayan kod atılır)."""
    import claude_yaz
    import pt_bls
    if not pt_bls.hazir():
        return {}
    yuvalar = {}
    for i, k in enumerate(kalemler):
        yuvalar[str(i)] = (k.get("ad"), k.get("ara") or [k.get("ad") or ""])
        for j, m in enumerate(k.get("tarif") or []):
            if isinstance(m, dict):
                yuvalar[f"{i}.{j}"] = (m.get("ad"), m.get("ara") or [m.get("ad") or ""])
    aday, satir = {}, []
    for yid, (ad, aralar) in yuvalar.items():
        L, gor = [], set()
        for q in aralar[:3]:
            for x in pt_bls.ara(str(q), 8):
                if x["kod"] not in gor:
                    gor.add(x["kod"])
                    L.append(x)
        aday[yid] = {x["kod"]: x for x in L[:14]}
        if L:
            satir.append(f"[{yid}] {ad}: " + " | ".join(f"{x['kod']} {x['de']} ({x['en']}, {x['yuz']['kcal']:g} kcal)" for x in L[:14]))
    if not satir:
        return {}
    try:
        c = claude_yaz.sor_json(ESLE_ISTEM.format(liste="\n".join(satir)), model_adi="sonnet", zaman_asimi=120) or {}
    except Exception:
        return {}
    out = {}
    for yid, kod in (c.get("secim") or {}).items():
        kod = str(kod or "").strip()
        if kod and kod in aday.get(str(yid), {}):
            out[str(yid)] = aday[str(yid)][kod]
    return out


def _bls_uygula(k, i, secim):
    """Kalemin 100 g değerleri BLS'den: doğrudan karşılık, yoksa tariften (malzemelerin gram ağırlıklı toplamı). Döner: True BLS kullanıldıysa."""
    import pt_bls
    x = secim.get(str(i))
    if x:
        k["yuz"] = {a: round(float(x["yuz"][a]), 2) for a in pt_bls.ALANLAR}
        k.update(kaynak=f"BLS: {x['de']}", bls=x["kod"])
        return True
    tarif = [m for m in (k.get("tarif_ham") or []) if isinstance(m, dict)]
    eslesen = [(float(m.get("g") or 0), secim[f"{i}.{j}"]) for j, m in enumerate(k.get("tarif_ham") or []) if isinstance(m, dict) and f"{i}.{j}" in secim]
    toplam = sum(float(m.get("g") or 0) for m in tarif)
    if eslesen and toplam > 0 and sum(g for g, _ in eslesen) >= 0.8 * toplam:
        yuz = {a: round(sum(g * float(x["yuz"][a]) for g, x in eslesen) / toplam, 2) for a in pt_bls.ALANLAR}
        k["yuz"] = yuz
        k.update(kaynak="BLS: tariften (" + ", ".join(x["de"].split(",")[0] for _, x in eslesen[:4]) + ")", bls="tarif")
        return True
    return False


def _atwater(y):
    """100 g değerlerinin tutarlılığı: kcal, 4p+4k+9y'den %20'den fazla saparsa makrolardan hesaplanan kullanılır."""
    hesap = 4 * y["protein"] + 4 * y["karb"] + 9 * y["yag"]
    if hesap > 0 and (not y["kcal"] or abs(y["kcal"] - hesap) / hesap > 0.2):
        y["kcal"] = round(hesap, 1)
    return y


def kalem_hesapla(k):
    """Kalemin toplam değerleri = gram × 100 g değerleri. `yuz` yoksa kalemin kendi toplamları kalır."""
    yuz = k.get("yuz")
    if not yuz:
        return k
    g = pt.sayi(k.get("miktar_g"), 0, 5000, 0)
    for a in ("kcal", "protein", "yag", "karb", "lif", "doymus"):
        if a in yuz:
            k[a] = round(g * pt.sayi(yuz.get(a), 0, 900, 0) / 100, 1)
    return k


def _duzeltme_notu():
    """Son düzeltmelerden kısa not: hangi yiyeceklerde gram tahmini sistematik olarak kaçıyor, kullanıcı sık hangi kalemi ekliyor."""
    from collections import defaultdict
    L = pt._json(DUZELTME, {"liste": []})["liste"][-40:]
    oran, eklenen = defaultdict(list), defaultdict(int)
    for d in L:
        for x in d.get("degisen") or []:
            if x.get("tahmin") and x.get("son"):
                oran[x["ad"].lower()].append(x["son"] / x["tahmin"])
        for a in d.get("eklenen") or []:
            eklenen[a.lower()] += 1
    out = [f"{ad}: gerçek porsiyon tahminin ~{sum(r) / len(r):.1f} katı" for ad, r in oran.items() if len(r) >= 2 and abs(sum(r) / len(r) - 1) >= 0.15]
    tum = [r for rs in oran.values() for r in rs]
    if len(tum) >= 4 and abs(sum(tum) / len(tum) - 1) >= 0.15:
        out.append(f"genel olarak porsiyonları tahminin ~{sum(tum) / len(tum):.1f} katı")
    out += [f"sık eklediği kalem: {a}" for a, n in eklenen.items() if n >= 2]
    return "; ".join(out[:8]) or "yok"


def duzeltme_kaydet(tahmin, son):
    """Kullanıcının tahmini kaydetmeden önce değiştirdikleri: gram oranları ve eklenen kalemler (sonraki tahminlere girer)."""
    if not tahmin:
        return
    T = {(k.get("ad") or "").strip().lower(): k for k in tahmin.get("kalemler") or []}
    S = {(k.get("ad") or "").strip().lower(): k for k in son.get("kalemler") or []}
    degisen = [{"ad": a, "tahmin": float(T[a].get("miktar_g") or 0), "son": float(S[a].get("miktar_g") or 0)} for a in T
               if a in S and float(T[a].get("miktar_g") or 0) > 0 and abs(float(S[a].get("miktar_g") or 0) - float(T[a].get("miktar_g") or 0)) >= 5]
    eklenen = [S[a].get("ad") for a in S if a and a not in T]
    silinen = [T[a].get("ad") for a in T if a and a not in S]
    if not (degisen or eklenen or silinen):
        return
    with pt._kilit:
        d = pt._json(DUZELTME, {"liste": []})
        d["liste"] = (d["liste"] + [{"t": int(time.time()), "ad": son.get("ad"), "degisen": degisen, "eklenen": eklenen, "silinen": silinen}])[-120:]
        pt._yaz(DUZELTME, d)


def yemek_coz(metin="", resim=None, resimler=None, cevap=None):
    """Fotoğraf(lar) ve/veya cümle → kalemler. Model gram ve 100 g değerlerini verir, toplamları kod hesaplar.
    `cevap` = {"soru", "cevap"}: önceki tahminin sorusuna verilen cevap (yeniden tahmin)."""
    import claude_yaz
    resimler = list(resimler or ([resim] if resim else []))
    p = pt.profil()
    kaynak = "fotoğraftan ve yazdıklarından" if resimler and metin else "fotoğraftan" if resimler else "yazdıklarından"
    foto_notu = ""
    if len(resimler) > 1:
        foto_notu = (f"{len(resimler)} fotoğraf var: aynı öğünün farklı açıları olabilir (gramı ikisine birlikte bakarak tahmin et) ya da biri yemekten "
                     "SONRA tabakta kalanı gösteriyor olabilir; öyleyse kalanı düş, yalnız yeneni yaz.\n")
    if cevap and cevap.get("cevap"):
        metin = (metin + "\n" if metin else "") + f"(Soruya cevap: {cevap.get('soru', '')} → {cevap['cevap']})"
    sik = ", ".join(x["ad"] for x in son_ogunler(10)) or "yok"
    istem = YEMEK_ISTEM.format(kaynak=kaynak, foto_notu=foto_notu, metin=metin or "(yok)", sik=sik, duzeltme=_duzeltme_notu(),
                               hassasiyet=", ".join((p.get("beslenme") or {}).get("hassasiyetler") or []) or "yok")
    if resimler:
        c = claude_yaz.json_coz(claude_yaz.sor_gorsel(istem + "\nYanıtın YALNIZCA JSON olsun.", resimler, model_adi="sonnet", zaman_asimi=300))
    else:
        c = claude_yaz.sor_json(istem, model_adi="sonnet", zaman_asimi=300)
    if not c:
        raise claude_yaz.ClaudeHata("Tahmin okunamadı")
    ham = [k for k in c.get("kalemler") or [] if isinstance(k, dict)]
    secim = _bls_esle(ham)
    kal = []
    for i, k in enumerate(ham):
        try:
            x = {"ad": str(k.get("ad") or "")[:60], "miktar_g": round(float(k.get("miktar_g") or 0)), "tarif_ham": k.get("tarif") or []}
            if not _bls_uygula(x, i, secim):
                yuz = k.get("yuz") or {}
                if yuz:
                    x["yuz"] = _atwater({a: round(float(yuz.get(a) or 0), 1) for a in ("kcal", "protein", "yag", "karb", "lif", "doymus")})
                else:
                    x.update({a: round(float(k.get(a) or 0), 1) for a in ("kcal", "protein", "yag", "karb")})
                x["kaynak"] = "Claude tahmini"
            x.pop("tarif_ham", None)
            kal.append(kalem_hesapla(x))
        except (TypeError, ValueError, AttributeError):
            continue
    sec = [str(s)[:40] for s in (c.get("secenekler") or []) if str(s).strip()][:4]
    esl = str(c.get("eslesen") or "").strip()
    esl_ogun = next((x for x in son_ogunler(10) if x["ad"].lower() == esl.lower()), None) if esl else None
    return {"ad": str(c.get("ad") or metin or "Öğün")[:80], "kalemler": kal, "soru": str(c.get("soru") or "")[:160], "secenekler": sec if c.get("soru") else [],
            "eslesen": esl_ogun, "hassasiyet_uyari": str(c.get("hassasiyet_uyari") or "")[:200], "guven": c.get("guven") or "orta"}


FOTO = pt.VERI / "yemek_foto"


def foto_kaydet(yid, kaynak):
    """Öğün fotoğrafının küçük kopyası (640 px) günlükte gösterilir."""
    import subprocess
    FOTO.mkdir(parents=True, exist_ok=True)
    hedef = FOTO / f"{yid}.jpg"
    subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "640", str(kaynak), "--out", str(hedef)], capture_output=True, timeout=60)
    return hedef.exists()


def disaridan_kaydet(resimler, metin="", tarih=None):
    """Telefonun Paylaş menüsünden gelen fotoğraf: tahmin edilir ve 'kontrol bekliyor' işaretiyle hemen kaydedilir."""
    y = yemek_coz(metin, resimler=resimler)
    y["id"] = f"y{int(time.time() * 1000)}{uuid.uuid4().hex[:4]}"
    if resimler and foto_kaydet(y["id"], resimler[0]):
        y["foto"] = True
    y["kontrol"] = True
    y["tahmin"] = {"ad": y["ad"], "kalemler": [dict(k) for k in y["kalemler"]]}
    tarih = tarih or pt.bugun().isoformat()
    return yemek_kaydet(tarih, {k: v for k, v in y.items() if k not in ("secenekler", "eslesen", "hassasiyet_uyari")})


def yemek_kaydet(tarih, y):
    y = dict(y)
    y.setdefault("id", f"y{int(time.time() * 1000)}{uuid.uuid4().hex[:4]}")
    y.setdefault("t", int(time.time()))
    def temiz(k):
        k = dict(k)
        for a, ust in (("miktar_g", 5000), ("kcal", 5000), ("protein", 500), ("yag", 500), ("karb", 1000), ("lif", 200), ("doymus", 300)):
            if a in k:
                k[a] = pt.sayi(k[a], 0, ust, 0)
        return kalem_hesapla(k)
    y["kalemler"] = [temiz(k) for k in y.get("kalemler") or [] if isinstance(k, dict) and k.get("ad")]
    if y.get("tahmin") and not y.get("kontrol"):                    # kullanıcı tahmini kontrol edip kaydetti: düzeltmesinden öğren
        duzeltme_kaydet(y.pop("tahmin"), y)

    def ekle(d):
        d["yemekler"] = [x for x in d["yemekler"] if x.get("id") != y["id"]] + [y]
        d["yemekler"].sort(key=lambda x: x.get("t") or 0)
    pt.gun_degistir(tarih, ekle)
    if y.get("favori"):
        favori_ekle(y)
    return y


def yemek_sil(tarih, yid):
    (FOTO / f"{yid}.jpg").unlink(missing_ok=True)
    pt.gun_degistir(tarih, lambda d: d.update(yemekler=[x for x in d["yemekler"] if x.get("id") != yid]))


def favoriler():
    return pt._json(FAVORI, {"liste": []})["liste"]


def favori_ekle(y):
    with pt._kilit:
        f = pt._json(FAVORI, {"liste": []})
        ad = y.get("ad") or "Öğün"
        f["liste"] = [x for x in f["liste"] if x.get("ad") != ad] + [{"ad": ad, "kalemler": y.get("kalemler") or [], "t": int(time.time())}]
        pt._yaz(FAVORI, f)


def son_ogunler(n=8):
    """'Her zamanki' için: son 21 günde en sık ve en son yenen öğünler + favoriler."""
    from collections import Counter
    sayi, son = Counter(), {}
    for g in pt.gunler(21):
        for y in g.get("yemekler") or []:
            ad = y.get("ad")
            if ad:
                sayi[ad] += 1
                son.setdefault(ad, y)
    L = [{"ad": ad, "kalemler": son[ad].get("kalemler") or [], "sayi": n_} for ad, n_ in sayi.most_common(n)]
    for f in favoriler():
        if f["ad"] not in {x["ad"] for x in L}:
            L.append({**f, "favori": True})
    return L[:n + 4]

# ----------------------------------------------------------------------------- günlük öneri

ONERI_ISTEM = """Sen bir diyetisyensin. Bugün için {ogun} öğünlük, {pencere} penceresine sığan bir yemek önerisi yaz. Türkçe, kısa.
Hedef: yaklaşık {kcal} kcal, en az {protein} g protein (öğün başına en az {ogun_protein} g). Şimdiye kadar yenen: {yenen}.
Antrenman: {antrenman}. Mutfak: {mutfak}. Hassasiyetler (KESİNLİKLE kullanma): {hassasiyet}. Sevmedikleri (kullanma): {sevmedik}.
{market}. Orucu proteinle açtır. Antrenman pencere içindeyse antrenmandan sonraki öğün en proteinli olsun.
JSON: {{"ogunler": [{{"saat": "13:00", "ad", "malzemeler": ["150 g tavuk göğsü", ...], "kcal", "protein", "not"}}], "ipucu": "tek cümle"}}"""


DIYET_AD = {"vejetaryen": "vejetaryen (et ve balık yok)", "vegan": "vegan (hiç hayvansal ürün yok)", "pesketaryen": "pesketaryen (et yok, balık var)",
            "domuzsuz": "domuz eti yok"}


def gunluk_oneri(tarih=None):
    import claude_yaz
    p = pt.profil()
    h = hedefler(p)
    d = pt.gun(tarih)
    yen = gun_toplam(d)
    gs = pt.gun_seansi(tarih)
    c = claude_yaz.sor_json(ONERI_ISTEM.format(market=pt.market_notu(p),
        ogun=(p.get("beslenme") or {}).get("ogun_sayisi") or 2, pencere=f"{h['pencere']['acilis']}-{h['pencere']['kapanis']}",
        kcal=(h["kcal"] or 2000) - yen["kcal"], protein=max(0, (h["protein"] or 140) - yen["protein"]), ogun_protein=h["ogun_protein"] or 40,
        yenen=f"{yen['kcal']} kcal, {yen['protein']} g protein" if yen["kcal"] else "henüz bir şey yok",
        antrenman=", ".join(f"{s.get('baslik')} ({s.get('saat') or 'saat yok'})" for s in gs["seanslar"] if s.get("tur") != "dinlenme") or "dinlenme günü",
        mutfak=", ".join(x for x in [(p.get("beslenme") or {}).get("mutfak") or "Türk ev yemekleri", DIYET_AD.get(p.get("diyet") or "", "")] if x),
        hassasiyet=", ".join((p.get("beslenme") or {}).get("hassasiyetler") or []) or "yok",
        sevmedik=", ".join((p.get("beslenme") or {}).get("sevmedikleri") or []) or "yok"), model_adi="sonnet", zaman_asimi=300)
    hass = [x.lower() for x in (p.get("beslenme") or {}).get("hassasiyetler") or []]
    for o in c.get("ogunler") or []:                       # hassasiyet kesin hariç: kodla ikinci kontrol
        o["uyari"] = [m for m in o.get("malzemeler") or [] if any(x and x in str(m).lower() for x in hass)]
    sonuc = {"tarih": d["tarih"], "zaman": int(time.time()), **c}
    pt.gun_degistir(d["tarih"], lambda x: x.update(yemek_onerisi=sonuc))
    return sonuc

# ----------------------------------------------------------------------------- haftalık özet


def hafta_ozeti(gun_listesi):
    h = hedefler()
    toplamlar, pencereye, protein_tutan, kayitli = [], 0, 0, 0
    for g in gun_listesi:
        d = pt._json(pt.gun_yolu(g.isoformat()), {})
        if not d.get("yemekler"):
            continue
        kayitli += 1
        t = gun_toplam(d)
        toplamlar.append(t)
        if h["protein"] and t["protein"] >= h["protein"] * 0.9:
            protein_tutan += 1
        pd = pencere_durumu(tarih=g.isoformat())
        if all(pd["acilis_t"] - 600 <= (y.get("t") or 0) <= pd["kapanis_t"] + 600 for y in d["yemekler"]):
            pencereye += 1
    tr = [x for x in trend(21) if x[2] is not None]
    hafta_degisim = round(tr[-1][2] - tr[-8][2], 2) if len(tr) >= 8 else None
    return {"kayitli_gun": kayitli, "ort_kcal": round(sum(t["kcal"] for t in toplamlar) / len(toplamlar)) if toplamlar else None,
            "ort_protein": round(sum(t["protein"] for t in toplamlar) / len(toplamlar)) if toplamlar else None,
            "protein_hedefi_tutan_gun": protein_tutan, "pencereye_uyan_gun": pencereye, "hedef": {k: h[k] for k in ("kcal", "protein")},
            "trend_kilo": tr[-1][2] if tr else None, "trend_hafta_degisim_kg": hafta_degisim, "hedef_neden": h["neden"]}
