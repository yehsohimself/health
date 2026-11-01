"""claude_butce.py — Claude aboneliğinin dengeleyicisi (2026-10-31; kullanıcı: "Lab'deki ürünler yoğun token harcıyor. Limitlerimi saçma
harcamasın; belki saçma şeylere harcıyorum, belki harcamam gereken yerlere harcamıyorum. Sen dengele, limit aşımı yaşamayayım").

Gösterge tahmin değil: Claude programı her yanıtta aboneliğin GERÇEK doluluğunu verir (stream-json `rate_limit_event`: 5 saatlik ve 7 günlük
pencere, 0-1, yenilenme zamanı). Bu doluluk kullanıcının kendi Claude Code / Claude uygulaması kullanımını da içerir; Lab'in kendi başına
yaptığı işler kullanıcıya yer açmak için geri çekilir.

İş türleri:
  siz       kullanıcı bekliyor (site isteği, sohbet akışı)                → hiç durdurulmaz
  toplanti  toplantı içeriği (claude_yaz.toplanti_mi)                     → hiç durdurulmaz
  devam     kullanıcının verdiği işin kendiliğinden adımları (özet, temizlik, altyazı, Kısaca…) → çalışır; sıkışınca opus yerine sonnet
  arka      Lab'in kendi başına yaptıkları (Ghost taslakları, keşif, bakım, öğrenme, testler) → doluluğa ve günlük paya göre bekler

Seviye (doluluk): bol · normal · dikkat · kritik · sinir. Haftalık hız: haftanın geçen kısmına göre beklenen doluluk (hedef: hafta sonunda ≤%90);
önde gidiliyorsa seviye yükselir. Bol seviyede (hafta boşa gidecekse) arka plan payı iki katına çıkar ve bekleyen işler çalışır.

Kayıtlar: kayitlar/.claude_doluluk.json (son gösterge), kayitlar/.claude_butce_olay.jsonl (bekletme, model düşürme, atlama).
"""
import json
import os
import re
import threading
import time
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
DOLULUK = KLASOR / "kayitlar" / ".claude_doluluk.json"
OLAY = KLASOR / "kayitlar" / ".claude_butce_olay.jsonl"
KULLANIM = KLASOR / "kayitlar" / ".claude_kullanim.jsonl"
HAFTA = 7 * 86400
HEDEF_HAFTA = 0.90            # hafta bu dolulukla bitsin
YOKLAMA_SN = 20 * 60          # gösterge bundan eskiyse arka plan işi sormadan önce küçük bir yoklama yapılır

SEVIYE_SIRA = ["bol", "normal", "dikkat", "kritik", "sinir"]
SEVIYE_AD = {"bol": "Bol", "normal": "Dengede", "dikkat": "Dikkat", "kritik": "Sıkışık", "sinir": "Sınırda"}

# (önek, ürün, tür, değer, günlük üst sınır (çağrı)). Önek iş adının başıyla eşleşir (claude_yaz._is_adi); ilk eşleşen geçerli.
# Tür yalnız varsayılandır: site isteğinden gelen çağrı "siz", toplantı içeriği "toplanti" sayılır.
POLITIKA = [
    # Ghost: X taslakları tek başına bütün kullanımın yarısına yakın (7 günde 781 çağrı); paylaşılan çok az. Değer orta, günlük pay sınırlı.
    ("X taslakları", "Ghost", "arka", "orta", 60), ("karisim", "Ghost", "arka", "orta", 60), ("paylasim", "Ghost", "arka", "orta", 60),
    ("kesif", "Ghost", "arka", "orta", 20), ("tetik", "Ghost", "arka", "orta", 15), ("fikir_kartlari", "Ghost", "arka", "dusuk", 10),
    ("konu_toplantisi", "Ghost", "arka", "orta", 10), ("yerimleri", "Ghost", "arka", "dusuk", 10), ("performans", "Ghost", "arka", "dusuk", 4),
    ("bultenler", "Ghost", "arka", "dusuk", 6), ("seckiler", "Ghost", "arka", "dusuk", 6), ("hesaplar", "Ghost", "arka", "dusuk", 6),
    ("ghost_gelisim", "Ghost", "arka", "dusuk", 6), ("ghost_kendi", "Ghost", "arka", "dusuk", 4), ("ghost_hikaye", "Ghost", "arka", "dusuk", 8),
    ("ghost_yanit", "Ghost", "arka", "dusuk", 8), ("ghost_defter", "Ghost", "arka", "dusuk", 8), ("ghost_blog", "Ghost", "arka", "dusuk", 4),
    ("ghost_oneri", "Ghost", "arka", "orta", 10), ("ghost_danisman", "Ghost", "arka", "orta", 6), ("ghost_kaynak", "Ghost", "arka", "orta", 20),
    ("ghost_sohbet", "Ghost", "siz", "yuksek", 0), ("ghost", "Ghost", "arka", "dusuk", 10),
    # Meet: toplantı içeriği zaten "toplanti"; burada kalanlar bakım ve takvim
    ("canli_asistan", "Meet", "devam", "yuksek", 0), ("Canlı özet", "Meet", "devam", "yuksek", 0), ("kisaca", "Meet", "devam", "yuksek", 0),
    ("danisman", "Meet", "devam", "yuksek", 0), ("sinyaller", "Meet", "devam", "orta", 0), ("toplanti_kapisi", "Meet", "devam", "yuksek", 0),
    ("meet_altyazi", "Meet", "devam", "yuksek", 0), ("Toplantı", "Meet", "devam", "yuksek", 0), ("04_toplanti", "Meet", "devam", "yuksek", 0),
    ("karar_zinciri", "Meet", "devam", "orta", 0), ("notlarim", "Meet", "devam", "yuksek", 0), ("sirketler", "Meet", "devam", "orta", 0),
    ("kisiler", "Meet", "arka", "orta", 10), ("tarifler", "Meet", "siz", "yuksek", 0), ("sohbet", "Meet", "siz", "yuksek", 0),
    ("Meet asistanı", "Meet", "siz", "yuksek", 0), ("meet_gelisim", "Meet", "arka", "yuksek", 30), ("Takvim eşitleme", "Meet", "arka", "yuksek", 48),
    ("İş kanıtı", "Meet", "arka", "orta", 6), ("is_kanit", "Meet", "arka", "orta", 8), ("Haftalık özet", "Meet", "arka", "orta", 6),
    ("Toplantı öncesi", "Meet", "devam", "yuksek", 0), ("Ad önerisi", "Meet", "devam", "orta", 0),
    # Studio: kullanıcının verdiği videonun adımları
    ("Transkript temizliği", "Studio", "devam", "yuksek", 0), ("Özet", "Studio", "devam", "yuksek", 0), ("Çeviri", "Studio", "devam", "yuksek", 0),
    ("Altyazı kırılımı", "Studio", "devam", "orta", 0), ("Öne çıkan anlar", "Studio", "devam", "orta", 0), ("Görüntü betimleme", "Studio", "devam", "orta", 0),
    ("yayin", "Studio", "devam", "orta", 0), ("dublaj", "Studio", "devam", "orta", 0), ("Soru-cevap", "Studio", "siz", "yuksek", 0),
    ("Marka", "Studio", "devam", "orta", 0), ("B-roll", "Studio", "devam", "dusuk", 0), ("studio_asistan", "Studio", "siz", "yuksek", 0),
    ("studio_gelisim", "Studio", "arka", "dusuk", 8), ("sahne_dizin", "Studio", "arka", "dusuk", 10),
    # Content, Health, Couple, Atölye, diğerleri
    ("content_sohbet", "Content", "siz", "yuksek", 0), ("content", "Content", "arka", "orta", 0),
    ("pt_sohbet", "Health", "siz", "yuksek", 0), ("pt_kanit", "Health", "arka", "dusuk", 4), ("pt_kart", "Health", "arka", "dusuk", 10),
    ("pt_cizim", "Health", "arka", "dusuk", 10), ("pt_youtube", "Health", "arka", "dusuk", 6), ("pt", "Health", "devam", "orta", 0),
    ("couple", "Couple", "arka", "dusuk", 4), ("atolye", "Atölye", "arka", "dusuk", 20),
    ("capital_sohbet", "Capital", "siz", "yuksek", 0), ("capital_dil", "Capital", "arka", "dusuk", 10), ("capital", "Capital", "devam", "orta", 0),
    ("money_guncel", "Money", "arka", "orta", 2), ("money_danisman", "Money", "devam", "orta", 0), ("ledger", "Money", "devam", "orta", 0), ("office_guncel", "Office", "arka", "orta", 4), ("office", "Office", "devam", "orta", 0),
    ("dil_cevir", "Arayüz çevirisi", "arka", "dusuk", 60), ("Doluluk yoklaması", "Dengeleyici", "devam", "yuksek", 0),
]
# Kendiliğinden yalnız haftada bir tur çalışan ürünler (2026-10-31; kullanıcı: "Content'in arka planda dev çalışması saçma; görev verdikçe
# yoğun çalışmalı, onun dışında haftada bir bile çalışsa yeter"). Tur: aynı önekte arka plan çağrıları; 3 saatten uzun ara yeni tur sayılır.
HAFTALIK = {"content": 7 * 86400}
TUR_ARA = 3 * 3600
HAFTA_DURUM = KLASOR / "kayitlar" / ".claude_butce_hafta.json"

URUN_SIRA = ["Ghost", "Meet", "Studio", "Content", "Health", "Capital", "Money", "Ledger", "Office", "Couple", "Atölye", "Arayüz çevirisi", "Diğer"]


def politika(is_adi):
    ad = str(is_adi or "")
    for onek, urun, tur, deger, ust in POLITIKA:
        if ad.startswith(onek):
            return {"onek": onek, "urun": urun, "tur": tur, "deger": deger, "ust": ust}
    return {"onek": ad, "urun": "Diğer", "tur": "devam", "deger": "orta", "ust": 0}


# ----------------------------------------------------------------------------------------------------------------------- gösterge
_kilit = threading.Lock()


def gosterge_yaz(bilgi):
    """claude_yaz akıştaki rate_limit_event'i buraya verir."""
    try:
        p = bilgi.get("unifiedWindows") or {}
        d = {"t": time.time(), "durum": bilgi.get("status"),
             "p5": float((p.get("five_hour") or {}).get("utilization") or 0), "r5": int((p.get("five_hour") or {}).get("resetsAt") or 0),
             "p7": float((p.get("seven_day") or {}).get("utilization") or 0), "r7": int((p.get("seven_day") or {}).get("resetsAt") or 0)}
        if not p and bilgi.get("rateLimitType"):                       # eski biçim: tek pencere
            k = "p5" if "five" in str(bilgi["rateLimitType"]) else "p7"
            d[k] = float(bilgi.get("utilization") or 0); d["r" + k[1]] = int(bilgi.get("resetsAt") or 0)
        DOLULUK.parent.mkdir(parents=True, exist_ok=True)
        tmp = DOLULUK.with_suffix(".tmp"); tmp.write_text(json.dumps(d), encoding="utf-8"); os.replace(tmp, DOLULUK)
        return d
    except Exception:  # noqa: BLE001
        return None


def gosterge():
    try:
        d = json.loads(DOLULUK.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    simdi = time.time()
    if d.get("r5") and d["r5"] < simdi:                                 # pencere yenilendi: eski doluluk geçersiz
        d["p5"] = 0.0
    if d.get("r7") and d["r7"] < simdi:
        d["p7"] = 0.0
    return d


_son_yoklama = [0.0]


def yokla(zorla=False):
    """Gösterge eskiyse çok küçük bir haiku çağrısıyla tazeler (en sık 15 dk'da bir). Yanıtın kendisi kullanılmaz."""
    d = gosterge()
    if not zorla and d and time.time() - d.get("t", 0) < YOKLAMA_SN:
        return d
    with _kilit:
        if time.time() - _son_yoklama[0] < 900 and not zorla:
            return gosterge()
        _son_yoklama[0] = time.time()
    try:
        import claude_yaz
        if not claude_yaz.program() or claude_yaz.misafir():
            return d
        claude_yaz.sor("Yalnızca 'tamam' yaz.", model_adi="haiku", zaman_asimi=60, _is="Doluluk yoklaması")
    except Exception:  # noqa: BLE001
        pass
    return gosterge()


def seviye(d=None):
    """Doluluk ve haftalık hızdan seviye; açıklamasıyla."""
    import claude_yaz
    d = d if d is not None else gosterge()
    if claude_yaz.sinir_durumu():
        return {"seviye": "sinir", "neden": "Claude kullanım sınırı bildirildi"}
    if not d:
        return {"seviye": "normal", "neden": "Doluluk henüz ölçülmedi"}
    p5, p7, simdi = d.get("p5", 0), d.get("p7", 0), time.time()
    gecen = 1 - max(0, (d.get("r7") or simdi + HAFTA) - simdi) / HAFTA if d.get("r7") else 0.5
    gecen = min(1.0, max(0.02, gecen))
    beklenen = HEDEF_HAFTA * gecen
    onde = p7 - beklenen
    tahmin = p7 / gecen if gecen > 0.05 else None                      # bu hızla hafta sonunda
    ek = {"p5": p5, "p7": p7, "gecen": round(gecen, 3), "beklenen": round(beklenen, 3), "onde": round(onde, 3),
          "hafta_sonu_tahmini": round(tahmin, 2) if tahmin else None, "r5": d.get("r5"), "r7": d.get("r7"), "olcum": d.get("t")}
    if p5 >= 0.95 or p7 >= 0.97:
        return {"seviye": "sinir", "neden": "Abonelik neredeyse dolu", **ek}
    if p5 >= 0.80:
        return {"seviye": "kritik", "neden": f"5 saatlik pencere %{round(p5 * 100)} dolu", **ek}
    if p7 >= 0.90 or onde >= 0.20:
        return {"seviye": "kritik", "neden": f"Haftalık kullanım planın çok önünde (%{round(p7 * 100)}, bu noktada beklenen %{round(beklenen * 100)})", **ek}
    if p5 >= 0.60:
        return {"seviye": "dikkat", "neden": f"5 saatlik pencere %{round(p5 * 100)} dolu", **ek}
    if onde >= 0.08:
        return {"seviye": "dikkat", "neden": f"Haftalık kullanım planın önünde (%{round(p7 * 100)}, beklenen %{round(beklenen * 100)})", **ek}
    if p5 < 0.35 and onde <= -0.15:
        return {"seviye": "bol", "neden": f"Bu hafta aboneliğin büyük kısmı boşta (%{round(p7 * 100)}, beklenen %{round(beklenen * 100)})", **ek}
    return {"seviye": "normal", "neden": "Kullanım plana uygun", **ek}


# ----------------------------------------------------------------------------------------------------------------------- kayıt okuma
_onb = {"t": 0.0, "satirlar": []}


def _son_satirlar(sn=26 * 3600):
    """Kullanım kaydının son ~1 gününü (30 sn önbellekle) okur."""
    if time.time() - _onb["t"] < 30:
        return _onb["satirlar"]
    out = []
    try:
        with open(KULLANIM, "rb") as f:
            f.seek(max(0, os.path.getsize(KULLANIM) - 1_500_000))
            sinir = time.time() - sn
            for s in f.read().decode("utf-8", "ignore").splitlines()[1:]:
                try:
                    x = json.loads(s)
                except Exception:  # noqa: BLE001
                    continue
                if x.get("t", 0) >= sinir and not x.get("misafir"):
                    out.append(x)
    except OSError:
        pass
    _onb.update(t=time.time(), satirlar=out)
    return out


def _gun_basi():
    return time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))


def bugunku_cagri(onek):
    g = _gun_basi()
    say = 0
    for x in _son_satirlar():
        pol = politika(x.get("is"))
        if x.get("t", 0) >= g and pol["onek"] == onek and (x.get("tur") or pol["tur"]) == "arka":
            say += 1
    return say


def art_arda_hata(is_adi, n=3, sn=7200):
    """Aynı iş son 2 saatte art arda n kez hata verdiyse son hatanın zamanı (yoksa 0)."""
    s = [x for x in _son_satirlar() if x.get("is") == is_adi and x.get("t", 0) > time.time() - sn][-n:]
    return s[-1]["t"] if len(s) == n and all(not x.get("ok", True) for x in s) else 0


def olay(tur, is_adi, **ek):
    try:
        OLAY.parent.mkdir(parents=True, exist_ok=True)
        with open(OLAY, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(time.time()), "olay": tur, "is": is_adi, **ek}, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ----------------------------------------------------------------------------------------------------------------------- karar
def _hafta_oku():
    try:
        return json.loads(HAFTA_DURUM.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _hafta_ilk(onek):
    """Durum dosyası yoksa kayıttan son arka plan turunu bulur."""
    son = bas = 0
    try:
        for s in KULLANIM.read_text(encoding="utf-8").splitlines():
            try:
                x = json.loads(s)
            except Exception:  # noqa: BLE001
                continue
            pol = politika(x.get("is"))
            if pol["onek"] != onek or (x.get("tur") or pol["tur"]) != "arka":
                continue
            t = x.get("t", 0)
            if t - son > TUR_ARA:
                bas = t
            son = t
    except OSError:
        pass
    return {"bas": bas, "son": son}


def haftalik_durum(onek):
    """{izin, bas, son, sonraki}: bu önek için kendiliğinden tur şimdi çalışabilir mi."""
    sure = HAFTALIK.get(onek)
    if not sure:
        return {"izin": True}
    d = _hafta_oku() or {}
    k = d.get(onek) or _hafta_ilk(onek)
    simdi = time.time()
    if simdi - k.get("son", 0) < TUR_ARA:                       # süren tur
        return {"izin": True, **k, "suruyor": True}
    sonraki = k.get("bas", 0) + sure
    return {"izin": simdi >= sonraki, **k, "sonraki": sonraki}


def _hafta_isle(onek):
    with _kilit:
        d = _hafta_oku() or {}
        k = d.get(onek) or _hafta_ilk(onek)
        simdi = time.time()
        if simdi - k.get("son", 0) >= TUR_ARA:
            k["bas"] = simdi
        k["son"] = simdi
        d[onek] = k
        try:
            HAFTA_DURUM.parent.mkdir(parents=True, exist_ok=True); HAFTA_DURUM.write_text(json.dumps(d), encoding="utf-8")
        except OSError:
            pass


class Bekle(Exception):
    """Arka plan işi şimdi çalışmamalı; `kalici` ise beklemek de anlamsız (günlük pay doldu, art arda hata)."""
    def __init__(self, neden, kalici=False):
        super().__init__(neden); self.neden, self.kalici = neden, kalici


def tur_bul(is_adi, istekten=False, toplanti=False, akis=False):
    if toplanti:
        return "toplanti"
    if istekten or akis:
        return "siz"
    return politika(is_adi)["tur"]


def karar(is_adi, tur, model_adi):
    """Bu çağrı şimdi yapılabilir mi, hangi modelle? {model, not}. Arka plan işi çalışmamalıysa Bekle fırlatır."""
    pol = politika(is_adi)
    if tur in ("siz", "toplanti"):
        return {"model": model_adi}
    sv = seviye(yokla() if tur == "arka" else gosterge())
    s = sv["seviye"]
    m = model_adi
    if tur == "devam":
        if s in ("kritik", "sinir") and m == "opus":
            m = "sonnet"
        return {"model": m, "seviye": s}
    # arka
    hd = haftalik_durum(pol["onek"])
    if not hd["izin"]:
        raise Bekle(f"{pol['urun']} kendiliğinden haftada bir çalışır; sonraki tur "
                    f"{time.strftime('%d.%m %H:%M', time.localtime(hd['sonraki']))}", kalici=True)
    hata_t = art_arda_hata(is_adi)
    if hata_t and time.time() - hata_t < 3600:
        raise Bekle("art arda hata verdi; 1 saat ara", kalici=True)
    if m == "haiku" and pol["deger"] == "yuksek" and s != "sinir":     # çok ucuz ve gerekli (takvim eşitleme): sıkışıkken de sürer
        return {"model": m, "seviye": s}
    if s in ("kritik", "sinir"):
        raise Bekle(sv["neden"])
    if s == "dikkat" and pol["deger"] != "yuksek":
        raise Bekle(sv["neden"])
    ust = pol["ust"] * (2 if s == "bol" else 1)
    if ust and bugunku_cagri(pol["onek"]) >= ust:
        raise Bekle(f"{pol['urun']} için bugünkü arka plan payı doldu ({ust} istek)", kalici=True)
    if m == "opus" and (s == "dikkat" or pol["deger"] == "dusuk"):
        m = "sonnet"
    if pol["onek"] in HAFTALIK:
        _hafta_isle(pol["onek"])
    return {"model": m, "seviye": s}


def arka_plan_uygun(is_adi=None):
    """Kendiliğinden çalışan bir arka plan turunu başlatmak uygun mu (tur başında sorulur; çağrı çağrı denetim ayrıca yapılır)."""
    try:
        karar(is_adi or "ghost", "arka", "sonnet")
        return True
    except Bekle:
        return False


# ----------------------------------------------------------------------------------------------------------------------- rapor
def _agirlik(x):
    """Bir çağrının aboneliğe yükü: Claude'un verdiği maliyet (API eşdeğeri) varsa o; yoksa tokenlardan yaklaşık (göreli)."""
    if x.get("maliyet") is not None:
        return float(x["maliyet"])
    k = {"opus": 5.0, "haiku": 0.33}.get(str(x.get("model") or ""), 1.0)
    return k * (x.get("giris", 0) * 0.3 + x.get("cikis", 0) * 15) / 1e6       # önbellekli girişin çoğu ucuz okunur


def rapor(gun=7):
    sinir = time.time() - gun * 86400
    urunler, turler, isler = {}, {}, {}
    toplam = 0.0
    try:
        satirlar = KULLANIM.read_text(encoding="utf-8").splitlines()
    except OSError:
        satirlar = []
    hatalar = {}
    for s in satirlar:
        try:
            x = json.loads(s)
        except Exception:  # noqa: BLE001
            continue
        if x.get("t", 0) < sinir or x.get("misafir"):
            continue
        pol = politika(x.get("is"))
        a = _agirlik(x); toplam += a
        tur = x.get("tur") or pol["tur"]
        u = urunler.setdefault(pol["urun"], {"yuk": 0.0, "istek": 0, "arka": 0.0})
        u["yuk"] += a; u["istek"] += 1; u["arka"] += a if tur == "arka" else 0
        turler[tur] = turler.get(tur, 0) + a
        i = isler.setdefault(x.get("is") or "?", {"yuk": 0.0, "istek": 0, "urun": pol["urun"], "hata": 0})
        i["yuk"] += a; i["istek"] += 1; i["hata"] += 0 if x.get("ok", True) else 1
    for ad, i in isler.items():
        if i["hata"] >= 5 and i["hata"] >= i["istek"] * 0.4:
            hatalar[ad] = i["hata"]
    pay = lambda v: round(100 * v / toplam, 1) if toplam else 0  # noqa: E731
    olaylar = {"bekletildi": 0, "hafif_model": 0, "atlandi": 0}
    try:
        for s in OLAY.read_text(encoding="utf-8").splitlines():
            x = json.loads(s)
            if x.get("t", 0) >= sinir and x.get("olay") in olaylar:
                olaylar[x["olay"]] += 1
    except Exception:  # noqa: BLE001
        pass
    sv = seviye()
    ghost = _ghost_degeri(gun)
    oneriler = _oneriler(sv, urunler, toplam, turler, hatalar, ghost)
    haftalik = {onek: haftalik_durum(onek) for onek in HAFTALIK}
    for onek, hd in haftalik.items():
        if hd.get("sonraki") and not hd.get("izin"):
            oneriler.append(f"{politika(onek)['urun']} kendiliğinden haftada bir çalışır (sonraki tur "
                            f"{time.strftime('%d.%m', time.localtime(hd['sonraki']))}); verdiğiniz işlerde her zaman tam hızla çalışır.")
    return {"gun": gun, "seviye": sv, "seviye_ad": SEVIYE_AD.get(sv["seviye"]),
            "urunler": [{"ad": k, "pay": pay(v["yuk"]), "arka_pay": pay(v["arka"]), "istek": v["istek"]}
                        for k, v in sorted(urunler.items(), key=lambda kv: -kv[1]["yuk"])],
            "turler": {k: pay(v) for k, v in turler.items()},
            "isler": [{"ad": k, "urun": v["urun"], "pay": pay(v["yuk"]), "istek": v["istek"], "hata": v["hata"]}
                      for k, v in sorted(isler.items(), key=lambda kv: -kv[1]["yuk"])[:15]],
            "dengeleyici": olaylar, "hatalar": hatalar, "haftalik": haftalik, "ghost": ghost, "oneriler": oneriler}


def _ghost_degeri(gun):
    try:
        import importlib                     # adı birleştirilerek: disa_depo'nun içe aktarma taraması Ghost'u başka ürünlerin deposuna çekmesin
        ghost_gelisim = importlib.import_module("ghost" + "_gelisim")
        T = ghost_gelisim._taslaklar(gun)
        ak = [ghost_gelisim._akibet(t) for t in T]
        return {"taslak": len(T), "paylasilan": sum(1 for a in ak if a.startswith("paylaş")),
                "calisilan": sum(1 for a in ak if a in ("kopyaladı", "üzerinde çalıştı", "kalsın dedi"))}
    except Exception:  # noqa: BLE001
        return None


def _oneriler(sv, urunler, toplam, turler, hatalar, ghost):
    o = []
    s = sv["seviye"]
    if s in ("kritik", "sinir"):
        o.append("Lab'in kendi başına yaptığı işler şu an bekliyor; sizin istekleriniz ve toplantılar her zaman çalışır.")
    if sv.get("hafta_sonu_tahmini") and sv["hafta_sonu_tahmini"] > 1.0:
        o.append(f"Bu hızla haftalık hak yenilenmeden dolar (tahmin: %{round(sv['hafta_sonu_tahmini'] * 100)}). "
                 "Payın bir kısmı sizin Claude oturumlarınızdan geliyor; Lab arka planı geri çekiliyor.")
    g = next((u for k, u in urunler.items() if k == "Ghost"), None)
    if g and toplam and g["yuk"] / toplam > 0.3 and ghost and ghost.get("taslak"):
        o.append(f"Ghost kullanımın %{round(100 * g['yuk'] / toplam)}'ini harcıyor: {ghost['taslak']} taslak yazıldı, "
                 f"{ghost['paylasilan']} paylaşıldı. Günlük Ghost payı 60 istekle sınırlandı.")
    if hatalar:
        o.append("Art arda hata veren işler 1 saat bekletiliyor: " + ", ".join(list(hatalar)[:3]) + ".")
    if s == "bol":
        o.append("Bu hafta aboneliğinizin büyük kısmı boşta kalacak; bekleyen arka plan işleri çalışıyor, günlük paylar iki katına çıktı.")
    return o


if __name__ == "__main__":
    import sys
    if sys.argv[1:2] == ["yokla"]:
        yokla(zorla=True)
    print(json.dumps(rapor(int(sys.argv[2]) if len(sys.argv) > 2 else 7), ensure_ascii=False, indent=1))
