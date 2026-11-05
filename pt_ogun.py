"""pt_ogun.py - Tek ve iki öğünlük hazır düzen, bir yemeğin hedefe göre değerlendirmesi (2026-11-05; kullanıcı: "tek öğün yiyeceksem ne yemeliyim, iki öğün yiyeceksem kahvaltıda ne, ikinci öğünde ne; seçenek olarak ikisini de işle").

Yapay zekâ çağrılmaz. Yemekler ve besin değerleri hazır listeden (pt_medya/hazir_yemek.json, BLS 4.0); porsiyon kişinin protein hedefine göre yarım adımla ayarlanır.
Seçim profilde beslenme.ogun_sayisi (1 = tek); haftalık menü de buna uyar."""
import datetime as dt

import pt
import pt_beslenme

TAVUK, SOMON = "izgara_tavuk_gogsu", "izgara_somon"
LOR, YULAF, ZY_SEBZE = "yagsiz_lor_quark", "yulaf_ezmesi_kuru", "zeytinyagli_sebze_yemegi"
# (yemek kodu, adet); protein yemeği None: adedi hedefe göre hesaplanır
_AKSAM = [("mercimek_corbasi", 1), (None, 1), ("bulgur_pilavi", 1), (ZY_SEBZE, 1), ("mevsim_salata", 1)]
DUZENLER = {
    "iki": {"ad": "İki öğün", "neden": "Proteine iki kez yetişilir, tabak büyümez. Önerdiğim düzen bu.",
            "ogunler": [
                {"ad": "Kahvaltı", "secenekler": [
                    {"ad": "Yulaflı", "kalemler": [(LOR, 1), (YULAF, 1), ("elma", 1), ("ceviz", .5), ("haslanmis_yumurta", 2)]},
                    {"ad": "Tuzlu", "kalemler": [("menemen", 1), (LOR, .5), ("yogurt", 1), ("tam_bugday_ekmegi", 2), ("domates_salatalik", 1)]}]},
                {"ad": "İkinci öğün", "secenekler": [
                    {"ad": "Tavuklu", "protein": TAVUK, "kalemler": _AKSAM},
                    {"ad": "Balıklı", "protein": SOMON, "kalemler": _AKSAM}]}]},
    "tek": {"ad": "Tek öğün", "neden": "Tabak büyük olur. Hepsini bitiremezseniz yoğurt ve cevizi bir saat sonra yiyin.",
            "ogunler": [
                {"ad": "Tek öğün", "secenekler": [
                    {"ad": "Tavuklu", "protein": TAVUK, "kalemler": [*_AKSAM, (LOR, 1), ("elma", 1), ("ceviz", 1)]},
                    {"ad": "Balıklı", "protein": SOMON, "kalemler": [*_AKSAM, (LOR, 1), ("elma", 1), ("ceviz", 1)]}]}]},
}


def _kucuk(s):
    return str(s).replace("I", "ı").replace("İ", "i").lower()


def _adet_yaz(a):
    return {.5: "Yarım", 1.5: "1,5", 2.5: "2,5"}.get(a) or f"{a:g}"


def _yemekler():
    return {y["kod"]: y for y in pt_beslenme.hazir_liste().get("yemekler") or []}


def _kalem(Y, kod, adet):
    x = Y.get(kod)
    if not x:
        return None
    return pt_beslenme.kalem_hesapla({"ad": f"{_adet_yaz(adet)} {x['birim']} {_kucuk(x['ad'])}", "hazir": kod, "adet": adet, "birim": x["birim"],
                                      "miktar_g": round(x["g"] * adet), "yuz": x["yuz"], "kaynak": x.get("kaynak"), "bls": x.get("bls")})


def _protein_adet(Y, kod, gerek):
    """Eksik proteini kapatan porsiyon: yarım adımla, 1 ile 2,5 arası."""
    x = Y.get(kod)
    tek = (x["g"] * x["yuz"]["protein"] / 100) if x else 0
    return min(2.5, max(1.0, round(gerek / tek * 2) / 2)) if tek else 1


def _sec_kalemler(Y, s, gerek):
    once = [(k, a) for k, a in s["kalemler"] if k]
    hazir = sum((_kalem(Y, k, a) or {}).get("protein") or 0 for k, a in once)
    L = []
    for k, a in s["kalemler"]:
        kod, adet = (k, a) if k else (s["protein"], _protein_adet(Y, s["protein"], gerek - hazir))
        m = _kalem(Y, kod, adet)
        if m:
            L.append(m)
    return L


def _toplam(L):
    return pt_beslenme.gun_toplam({"yemekler": [{"kalemler": L}]})


def secili(p=None):
    p = p or pt.profil()
    return "tek" if int((p.get("beslenme") or {}).get("ogun_sayisi") or 2) == 1 else "iki"


def _saatler(p, kod):
    b = p.get("beslenme") or {}
    bas = pt_beslenme._dk(b.get("pencere_bas"))
    sure = float(b.get("pencere_saat") or 6) * 60
    if sure >= 14 * 60:
        return ["14:30"] if kod == "tek" else ["11:00", "17:00"]
    yaz = lambda d: f"{int(d // 60) % 24:02d}:{int(d % 60):02d}"
    return [yaz(bas + sure / 2)] if kod == "tek" else [yaz(bas), yaz(bas + sure - 60)]


def duzenler(p=None):
    """Her düzen: öğünler, seçenekler, kalemler, toplam. Sayılar hesaplanır, uydurulmaz."""
    p = p or pt.profil()
    Y = _yemekler()
    h = pt_beslenme.hedefler(p)
    pr = h.get("protein") or 120
    alt = (h.get("protein_aralik") or [pr])[0]
    S = {}
    for kod, d in DUZENLER.items():
        saat = _saatler(p, kod)
        hedef = alt if kod == "tek" else pr
        ogunler = []
        # kahvaltının proteini ikinci öğünden düşülür; tek öğünde gerekli olanın tamamı bu tabakta
        once = 0
        for i, o in enumerate(d["ogunler"]):
            sec = []
            for s in o["secenekler"]:
                L = _sec_kalemler(Y, s, hedef - once)
                sec.append({"ad": s["ad"], "kalemler": [m["ad"] for m in L], **_toplam(L)})
            ogunler.append({"ad": o["ad"], "saat": saat[i], "secenekler": sec})
            once += max(x.get("protein") or 0 for x in sec) if i == 0 and len(d["ogunler"]) > 1 else 0
        top = {a: sum(o["secenekler"][0].get(a) or 0 for o in ogunler) for a in ("kcal", "protein", "lif", "doymus")}
        S[kod] = {"kod": kod, "ad": d["ad"], "neden": d["neden"], "ogunler": ogunler, "toplam": {a: round(v) for a, v in top.items()}}
    return {"secili": secili(p), "duzenler": S, "hedef": {a: h.get(a) for a in ("kcal", "protein", "lif", "doymus_ust", "kolesterol")}}


def sec(kod):
    if kod not in DUZENLER:
        raise ValueError("Bilinmeyen düzen.")
    pt.profil_kaydet({"beslenme": {"ogun_sayisi": 1 if kod == "tek" else 2}})
    return duzenler()


def yedim(kod, i, s, tarih=None):
    """Düzendeki öğünü, ekranda görünen porsiyonlarla kaydeder."""
    d = DUZENLER[kod]
    o = d["ogunler"][int(i)]
    sc = o["secenekler"][int(s)]
    h = pt_beslenme.hedefler()
    pr = h.get("protein") or 120
    if kod == "tek":
        gerek = (h.get("protein_aralik") or [pr])[0]
    else:
        ilk = duzenler()["duzenler"][kod]["ogunler"][0]["secenekler"]
        gerek = pr - (max(x.get("protein") or 0 for x in ilk) if int(i) else 0)
    L = _sec_kalemler(_yemekler(), sc, gerek)
    return pt_beslenme.yemek_kaydet(tarih or pt.bugun().isoformat(), {"ad": f"{o['ad']} ({_kucuk(sc['ad'])})", "kalemler": L, "favori": False, "kontrol": False})


def _nasil_tek(T, h, kod):
    pay = 1 if kod == "tek" else .5
    H = {"kcal": (h.get("kcal") or 0) * pay, "protein": (h.get("protein") or 0) * pay, "lif": (h.get("lif") or 0) * pay, "doymus": (h.get("doymus_ust") or 0) * pay}
    satir = [{"ad": "Kalori", "deger": round(T["kcal"]), "hedef": round(H["kcal"]), "birim": "kcal"}, {"ad": "Protein", "deger": round(T["protein"]), "hedef": round(H["protein"]), "birim": "g"},
             {"ad": "Lif", "deger": round(T.get("lif") or 0), "hedef": round(H["lif"]), "birim": "g"}, {"ad": "Doymuş yağ", "deger": round(T.get("doymus") or 0), "hedef": round(H["doymus"]), "birim": "g", "ust": True}]
    oran = lambda a: (T.get(a) or 0) / H[a] if H[a] else 1
    notlar = []
    if oran("protein") < .8 and H["protein"]:
        eksik = round(H["protein"] - T["protein"])
        tavuk = max(50, round(eksik / .30 / 50) * 50)
        notlar.append(f"Protein {eksik} g eksik. Yanına yaklaşık {tavuk} g pişmiş tavuk ya da balık eklemek kapatır.")
    if oran("kcal") < .7 and H["kcal"]:
        notlar.append("Kalori az. Tek gün sorun değil; her gün böyle olursa açık fazla büyür, enerji düşer ve kas kaybı artar.")
    elif oran("kcal") > 1.15 and H["kcal"]:
        notlar.append("Kalori bu öğün için fazla.")
    if oran("doymus") > 1 and H["doymus"]:
        notlar.append("Doymuş yağ yüksek" + ("; kolesterolünüz için krema ve tereyağını azaltın." if h.get("kolesterol") else "."))
    if oran("lif") >= 1 and H["lif"]:
        notlar.append("Lif iyi.")
    baslik = ("Protein ve kalori az" if oran("protein") < .8 and oran("kcal") < .7 else "Protein az" if oran("protein") < .8 else "Kalori az" if oran("kcal") < .7
              else "Kalori fazla" if oran("kcal") > 1.15 else "Bu öğün için dengeli")
    return {"baslik": baslik, "satirlar": satir, "notlar": notlar}


def nasil(y, p=None):
    """Tek yemek, iki düzene göre ne kadar yetiyor (kodla). Kısa karar + eksik için somut ekleme."""
    p = p or pt.profil()
    h = pt_beslenme.hedefler(p)
    T = pt_beslenme.gun_toplam({"yemekler": [y]})
    return {"secili": secili(p), "tek": _nasil_tek(T, h, "tek"), "iki": _nasil_tek(T, h, "iki")}


def baglam_metni(p=None):
    """Sohbet için: hedef, seçili düzen ve iki düzenin içeriği."""
    p = p or pt.profil()
    v = duzenler(p)
    h = v["hedef"]
    s = [f"Günlük hedef {h.get('kcal')} kcal, {h.get('protein')} g protein, en az {h.get('lif')} g lif, en çok {h.get('doymus_ust')} g doymuş yağ." + (" Kolesterolü yüksek." if h.get("kolesterol") else ""),
         f"Seçili düzen: {DUZENLER[v['secili']]['ad']}."]
    for d in v["duzenler"].values():
        s.append(f"{d['ad']} ({d['toplam']['kcal']} kcal, {d['toplam']['protein']} g protein): " + " | ".join(
            f"{o['ad']} {o['saat']}: " + " YA DA ".join(", ".join(x["kalemler"]) for x in o["secenekler"]) for o in d["ogunler"]))
    return " ".join(s)


def son_yemekler(gun=3):
    bugun = pt.bugun()
    L = []
    for i in range(gun, -1, -1):
        t = (bugun - dt.timedelta(days=i)).isoformat()
        for y in pt.gun(t).get("yemekler") or []:
            T = pt_beslenme.gun_toplam({"yemekler": [y]})
            L.append({"id": y.get("id"), "tarih": t, "saat": dt.datetime.fromtimestamp(y["t"]).strftime("%H:%M") if y.get("t") else "", "ad": y.get("ad"), "kcal": round(T["kcal"]), "protein": round(T["protein"])})
    return L
