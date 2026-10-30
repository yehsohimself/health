"""pt_hedef.py - Kısa, orta ve uzun vadeli hedefler (2026-10-30; kullanıcı: "kısa orta uzun vadeli hedefler belirleyelim birlikte").

Gerçek bir antrenör ilk görüşmenin sonunda üç hedef koyar: 4 hafta (alışkanlık ve ilk ölçülebilir kazanım), 12 hafta (bir blok sonunda görünür
fark), 1 yıl (asıl neden). PT de öyle: ADAYLARI KOD üretir (profil, testler, basamaklar ve kilo trendinden ölçülebilir hedefler; model uyduramaz),
Claude her vade için birini seçip kişinin diline çevirir (yoksa kurallar seçer), kişi onaylar ya da değiştirir. İlerleme her zaman KODLA ölçülür:
kilo trendi, bel, test kayıtları, zincir basamağı, seans sayısı, seri. Hedefler haftalık plan istemine ve ara kontrole girer.

Kayıt: pt/hedefler.json {hedefler: [{id, vade, metin, neden, olcu: {tur, kod?, hedef, baslangic}, bas, son, durum, kaynak}], oneri: {...}}.
"""
import datetime as dt
import hashlib
import json
import time

import pt

HEDEFLER = pt.VERI / "hedefler.json"
VADELER = [("kisa", "Kısa vade", 28, "4 hafta"), ("orta", "Orta vade", 84, "3 ay"), ("uzun", "Uzun vade", 365, "1 yıl")]
VADE_GUN = {k: g for k, _, g, _ in VADELER}
VADE_AD = {k: a for k, a, _, _ in VADELER}
VADE_SURE = {k: s for k, _, _, s in VADELER}
TEST_AD = {k: a for k, a, *_ in pt.TESTLER}
TEST_OLCU = {k: o for k, _, o, *_ in pt.TESTLER}

ONERI_ISTEM = """Sen PT'sin: kişisel antrenör + diyetisyen. Kişiyle ilk görüşmenin sonunda üç hedef belirliyorsunuz: kısa (4 hafta), orta (3 ay),
uzun (1 yıl). Aşağıda KODUN ÖLÇEBİLDİĞİ aday hedefler var; YALNIZCA bu adaylardan seç (numarayla). Her vade için bir ana hedef ve bir seçenek.
Seçerken: kısa vade alışkanlık ve ilk somut kazanım (kaçırılmayacak kadar gerçekçi), orta vade bir blok sonunda görünür fark, uzun vade kişinin
asıl nedeni. Üç vade için üç FARKLI ölçü türü seç (ör. kısa: seri ya da seans sayısı, orta: basamak ya da test, uzun: beceri ya da hedef kilo);
aynı ölçüyü iki vadede kullanma. Kişinin hedef türlerine ve motivasyonuna uy; sağlık notlarına saygı göster. "metin" kişinin dilinde, somut, en çok 12 kelime,
sayı içersin (adayın sayısını değiştirme). "neden" tek cümle, "siz" dili, klişe yok.
KİŞİ: {profil}
ADAYLAR:
{adaylar}
JSON: {{"hedefler": [{{"vade": "kisa|orta|uzun", "aday": 3, "metin": "...", "neden": "..."}}], "secenekler": [{{"vade": "...", "aday": 5, "metin": "...", "neden": "..."}}]}}"""


def _oku():
    return pt._json(HEDEFLER, {"hedefler": [], "oneri": {}})


def _yaz(d):
    pt._yaz(HEDEFLER, d)


def _imza(p):
    return hashlib.sha1(json.dumps({k: p.get(k) for k in ("hedef_turleri", "beceri_hedefleri", "hedef_kilo_kg", "kilo_kg", "gunler", "gunluk_dk")},
                                   sort_keys=True, default=str).encode()).hexdigest()[:10]


def _son_test():
    """Her testin en son değeri."""
    out = {}
    for k in pt.testler().get("kayitlar") or []:
        for ad, v in (k.get("sonuclar") or {}).items():
            if isinstance(v, (int, float)):
                out[ad] = (k.get("tarih"), float(v))
    return out


def _kilo(p):
    tr = [t for _, _, t in __import__("pt_beslenme").trend(21) if t]
    return float(tr[-1]) if tr else (float(p["kilo_kg"]) if p.get("kilo_kg") else None)


def _son_bel():
    for d in pt.gunler(60):
        if d.get("bel_cm"):
            return float(d["bel_cm"])
    return None


def adaylar(p=None):
    """Kodun ölçebildiği hedef adayları. Her aday: {vade, metin, olcu: {tur, kod, hedef, baslangic, birim}, simdi}."""
    p = p or pt.profil()
    kat = pt.katalog()
    H = set(p.get("hedef_turleri") or [])
    out = []

    def ekle(vade, metin, tur, hedef, baslangic, kod=None, birim="", yon="artis"):
        out.append({"vade": vade, "metin": metin, "olcu": {"tur": tur, "kod": kod, "hedef": hedef, "baslangic": baslangic, "birim": birim, "yon": yon}})

    kilo = _kilo(p)
    hk = p.get("hedef_kilo_kg")
    if "kilo" in H and kilo and hk and float(hk) < kilo - 0.5:
        hiz = min(0.7, float((p.get("beslenme") or {}).get("kilo_hizi") or 0.5))
        haftalik = kilo * hiz / 100
        k4 = round(max(float(hk), kilo - haftalik * 4), 1)
        k12 = round(max(float(hk), kilo - haftalik * 12), 1)
        ekle("kisa", f"4 haftada {k4} kg'a inmek", "kilo", k4, round(kilo, 1), birim="kg", yon="azalis")
        if k12 < k4:
            ekle("orta", f"3 ayda {k12} kg'a inmek", "kilo", k12, round(kilo, 1), birim="kg", yon="azalis")
        ekle("uzun", f"Hedef kilo {float(hk):g} kg", "kilo", float(hk), round(kilo, 1), birim="kg", yon="azalis")
    bel = _son_bel()
    if bel and ("kilo" in H or "saglik" in H):
        ekle("kisa", f"Bel çevresini {bel - 2:g} cm'ye indirmek", "bel", bel - 2, bel, birim="cm", yon="azalis")
        ekle("orta", f"Bel çevresini {bel - 5:g} cm'ye indirmek", "bel", bel - 5, bel, birim="cm", yon="azalis")
    # düzen: seans ve seri (herkes için)
    gun_sayisi = max(2, min(6, len(p.get("gunler") or []) or 3))
    ekle("kisa", f"4 haftada {max(8, round(gun_sayisi * 4 * .7))} antrenman", "seans", max(8, round(gun_sayisi * 4 * .7)), 0, birim="antrenman")
    ekle("kisa", "14 gün kesintisiz seri", "seri", 14, 0, birim="gün")
    ekle("orta", f"3 ayda {max(24, round(gun_sayisi * 12 * .7))} antrenman", "seans", max(24, round(gun_sayisi * 12 * .7)), 0, birim="antrenman")
    ekle("orta", "30 gün kesintisiz seri", "seri", 30, 0, birim="gün")
    ekle("uzun", "Bir yılda 150 antrenman", "seans", 150, 0, birim="antrenman")
    # testler: son değerden ölçülebilir artış
    T = _son_test()
    ARTIS = {"sinav_max": (3, 8, 15), "squat_max": (5, 10, 20), "barfiks_max": (1, 3, 6), "dips_max": (2, 4, 8), "plank_sn": (20, 45, 90), "hollow_sn": (10, 25, 45),
             "asilma_sn": (10, 25, 45)}
    for kod, (a4, a12, a52) in ARTIS.items():
        if kod in T and (("kas" in H) or ("beceri" in H) or ("kondisyon" in H) or ("saglik" in H)):
            tarih, v = T[kod]
            birim = "sn" if TEST_OLCU.get(kod) == "sure" else "tekrar"
            ad = TEST_AD.get(kod, kod).replace("En fazla ", "")
            ad = ad[:1].upper() + ad[1:]
            ekle("kisa", f"{ad}: {v:g} → {v + a4:g} {birim}", "test", v + a4, v, kod=kod, birim=birim)
            ekle("orta", f"{ad}: {v:g} → {v + a12:g} {birim}", "test", v + a12, v, kod=kod, birim=birim)
            ekle("uzun", f"{ad}: {v:g} → {v + a52:g} {birim}", "test", v + a52, v, kod=kod, birim=birim)
    # beceri zincirleri: sonraki basamak (orta), beceri (uzun)
    try:
        for b in pt.beceriler():
            for z in b.get("zincirler") or []:
                if z.get("sonraki"):
                    ekle("orta", f"{z['sonraki']['ad']} basamağına geçmek", "basamak", z["sonraki"]["kod"], z["simdi"]["kod"], kod=z["sonraki"]["kod"])
            if b["kod"] in kat and not b.get("tamam"):
                ad = b["ad"] if b["ad"][:2] in ("L-",) else b["ad"].lower()
                ekle("uzun", f"İlk {ad}", "basamak", b["kod"], None, kod=b["kod"])
                out[-1]["olcu"]["beceri"] = True
                out[-1]["yakinlik"] = b.get("ilerleme") or 0
    except Exception:  # noqa: BLE001
        pass
    out.sort(key=lambda a: -(a.get("yakinlik") or 0) if a["olcu"].get("beceri") else 0)   # en yakın beceri önce (gerçekçi uzun vade)
    tekil, gorulen = [], set()
    for a in out:                                                               # aynı zincir iki beceride geçince aynı basamak iki kez çıkmasın
        anahtar = (a["vade"], a["olcu"]["tur"], a["olcu"].get("kod"), a["olcu"].get("hedef"))
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        tekil.append(a)
    for i, a in enumerate(tekil):
        a["no"] = i + 1
    return tekil


def _profil_kisa(p):
    return json.dumps({k: p.get(k) for k in ("hedef_turleri", "hedefler", "beceri_hedefleri", "motivasyon", "deneyim", "sinirlar", "sakatliklar", "notlar",
                                             "kilo_kg", "hedef_kilo_kg", "gunler", "gunluk_dk")}, ensure_ascii=False)


def _kural_secimi(A, p):
    """Claude yoksa: her vade için en anlamlı aday."""
    H = set(p.get("hedef_turleri") or [])
    secim, secenek, kullanilan = [], [], set()
    # Kısa vade düzen (seans/seri) ya da kilo; orta vade görünür fark (test/basamak); uzun vade asıl neden (beceri/hedef kilo). Üç vade aynı ölçü olmasın.
    ONCELIK = {"kisa": (["kilo", "seans", "seri", "test", "bel"] if "kilo" in H else ["seans", "test", "seri", "kilo", "bel"]),
               "orta": ["basamak", "test", "kilo", "seans", "bel", "seri"], "uzun": ["beceri", "kilo", "test", "seans"]}
    NEDEN = {"kisa": "Dört haftada tutturulabilir, ilk somut kazanım.", "orta": "Bir blok sonunda görünür fark.", "uzun": "Asıl nedeniniz; her şey buna doğru."}
    tur = lambda a: "beceri" if a["olcu"].get("beceri") else a["olcu"]["tur"]  # noqa: E731
    for vade, *_ in VADELER:
        L = [a for a in A if a["vade"] == vade]
        if not L:
            continue
        onc = ONCELIK[vade]
        L.sort(key=lambda a: (tur(a) in kullanilan, onc.index(tur(a)) if tur(a) in onc else 99))
        secim.append({"vade": vade, "aday": L[0]["no"], "metin": L[0]["metin"], "neden": NEDEN[vade]})
        kullanilan.add(tur(L[0]))
        for a in L[1:3]:
            secenek.append({"vade": vade, "aday": a["no"], "metin": a["metin"], "neden": ""})
    return {"hedefler": secim, "secenekler": secenek}


def oner(yenile=False):
    """Üç vade için öneri (Claude seçer, kod ölçer). Sonuç önbellekte; profil değişince ya da yenile ile yeniden."""
    import claude_yaz
    p = pt.profil()
    d = _oku()
    o = d.get("oneri") or {}
    imza = _imza(p)
    if o.get("hedefler") and o.get("imza") == imza and not yenile:
        return o
    A = adaylar(p)
    if not A:
        return {"hedefler": [], "secenekler": [], "zaman": int(time.time()), "imza": imza}
    c = {}
    try:
        if claude_yaz.hazir():
            metin = "\n".join(f"{a['no']}. [{VADE_AD[a['vade']]}] {a['metin']} (ölçü: {a['olcu']['tur']})" for a in A)
            c = claude_yaz.sor_json(ONERI_ISTEM.format(profil=_profil_kisa(p), adaylar=metin), model_adi="sonnet", zaman_asimi=240)
    except Exception:  # noqa: BLE001
        c = {}
    by_no = {a["no"]: a for a in A}

    def temiz(L, tek=True):
        out, gorulen = [], set()
        for x in L or []:
            try:
                a = by_no[int(x.get("aday"))]
            except (TypeError, ValueError, KeyError):
                continue
            vade = x.get("vade") if x.get("vade") in VADE_GUN else a["vade"]
            if tek and vade in gorulen:
                continue
            gorulen.add(vade)
            out.append({"vade": vade, "aday": a["no"], "metin": str(x.get("metin") or a["metin"])[:120], "neden": str(x.get("neden") or "")[:220],
                        "olcu": a["olcu"]})
        return out
    sec = temiz(c.get("hedefler"))
    if len(sec) < min(3, len({a["vade"] for a in A})):
        k = _kural_secimi(A, p)
        var = {x["vade"] for x in sec}
        sec += [dict(x, olcu=by_no[x["aday"]]["olcu"]) for x in k["hedefler"] if x["vade"] not in var]
        secenek = temiz(c.get("secenekler"), tek=False) or [dict(x, olcu=by_no[x["aday"]]["olcu"]) for x in k["secenekler"]]
    else:
        secenek = temiz(c.get("secenekler"), tek=False)
    secili = {x["aday"] for x in sec}
    secenek = [x for x in secenek if x["aday"] not in secili][:6]
    o = {"hedefler": sorted(sec, key=lambda x: list(VADE_GUN).index(x["vade"])), "secenekler": secenek, "zaman": int(time.time()), "imza": imza,
         "adaylar": A}
    with pt._kilit:
        d = _oku()
        d["oneri"] = o
        _yaz(d)
    return o


def _hid():
    return f"h{time.time_ns() // 1000}"


def kaydet(secilenler):
    """Kişinin onayladığı hedefleri etkinleştirir. Her öğe: {vade, metin, olcu?, neden?}; olcu yoksa serbest (elle işaretlenir).
    Aynı vadede eski etkin hedef 'degisti' olur."""
    bugun = pt.bugun()
    with pt._kilit:
        d = _oku()
        for s in secilenler or []:
            vade = s.get("vade") if s.get("vade") in VADE_GUN else "orta"
            metin = str(s.get("metin") or "").strip()[:120]
            if not metin:
                continue
            olcu = s.get("olcu") if isinstance(s.get("olcu"), dict) and s["olcu"].get("tur") else {"tur": "serbest"}
            olcu = {k: olcu.get(k) for k in ("tur", "kod", "hedef", "baslangic", "birim", "yon")}
            if olcu["tur"] in ("seans", "seri", "dk"):
                olcu["baslangic"] = 0
            elif olcu["tur"] == "kilo" and olcu.get("baslangic") is None:
                olcu["baslangic"] = _kilo(pt.profil())
            for h in d["hedefler"]:
                if h.get("vade") == vade and h.get("durum") == "aktif":
                    h["durum"] = "degisti"
                    h["bitis"] = bugun.isoformat()
            d["hedefler"].append({"id": _hid(), "vade": vade, "metin": metin, "neden": str(s.get("neden") or "")[:220], "olcu": olcu,
                                  "bas": bugun.isoformat(), "son": (bugun + dt.timedelta(days=VADE_GUN[vade])).isoformat(), "durum": "aktif",
                                  "kaynak": "kendi" if s.get("kendi") else "pt"})
        d["onaylandi"] = int(time.time())
        _yaz(d)
    return aktif()


def degistir(hid, metin=None, durum=None):
    with pt._kilit:
        d = _oku()
        h = next((x for x in d["hedefler"] if x.get("id") == hid), None)
        if not h:
            return None
        if metin is not None:
            h["metin"] = str(metin).strip()[:120] or h["metin"]
        if durum in ("aktif", "tamam", "birakti"):
            h["durum"] = durum
            if durum == "tamam":
                h["tamam_tarih"] = pt.bugun().isoformat()
        _yaz(d)
    return h


def _simdi(h):
    """Hedefin bugünkü ölçümü (kodla)."""
    o = h.get("olcu") or {}
    t = o.get("tur")
    bas = h.get("bas") or pt.bugun().isoformat()
    if t == "kilo":
        return _kilo(pt.profil())
    if t == "bel":
        return _son_bel()
    if t == "test":
        T = _son_test()
        return T[o["kod"]][1] if o.get("kod") in T else o.get("baslangic")
    if t == "seans":
        return sum(1 for d in pt.gunler(400) if d.get("tarih", "") >= bas for s in d.get("seanslar") or [] if s.get("bitti"))
    if t == "dk":
        return sum(int(s.get("sure_dk") or 0) for d in pt.gunler(400) if d.get("tarih", "") >= bas for s in d.get("seanslar") or [] if s.get("bitti"))
    if t == "seri":
        try:
            import pt_oyun
            h = pt_oyun.hesap()
            G = [g for g in h["gunler"] if g["tarih"] >= bas]
            en = cur = 0
            for g in G:
                cur = cur + 1 if g["durum"] in ("tamam", "onarildi", "korundu") else 0
                en = max(en, cur)
            return max(en, h.get("seri") or 0)              # hedef konulduğunda süren seri de sayılır (15 günlük seri "0" görünüyordu)
        except Exception:  # noqa: BLE001
            return 0
    if t == "basamak":
        kat = pt.katalog()
        hedef_h = kat.get(o.get("kod")) or {}
        if not hedef_h:
            return None
        ak = pt.aktif_basamak(hedef_h.get("zincir"), kat)
        return (kat.get(ak) or {}).get("basamak", 0)
    return None


def ilerleme(h):
    o = h.get("olcu") or {}
    t = o.get("tur")
    bugun = pt.bugun()
    try:
        kalan = (dt.date.fromisoformat(h.get("son")) - bugun).days
        gecen = (bugun - dt.date.fromisoformat(h.get("bas"))).days
    except (TypeError, ValueError):
        kalan, gecen = 0, 0
    toplam = max(1, kalan + gecen)
    zaman_orani = min(1.0, max(0.0, gecen / toplam))
    out = {**h, "kalan_gun": kalan, "zaman_orani": round(zaman_orani, 3)}
    if h.get("durum") == "tamam":
        return {**out, "oran": 1.0, "durum_metni": "Tamamlandı", "yolda": "tamam"}
    if t == "serbest":
        return {**out, "oran": None, "simdi": None, "durum_metni": "Siz işaretlersiniz", "yolda": "elle"}
    simdi = _simdi(h)
    hedef, bas = o.get("hedef"), o.get("baslangic")
    oran = None
    if t == "basamak":
        kat = pt.katalog()
        hb = (kat.get(o.get("kod")) or {}).get("basamak") or 0
        bb = (kat.get(bas) or {}).get("basamak") if bas else None
        if simdi is not None and hb:
            if bb is None:
                bb = 0
            oran = 1.0 if simdi >= hb else max(0.0, (simdi - bb) / max(1, hb - bb))
        simdi_m = (kat.get(pt.aktif_basamak((kat.get(o.get("kod")) or {}).get("zincir"), kat)) or {}).get("ad")
    elif simdi is not None and hedef is not None:
        try:
            if o.get("yon") == "azalis":
                oran = 1.0 if simdi <= hedef else max(0.0, (float(bas) - simdi) / max(.01, float(bas) - float(hedef))) if bas is not None else 0.0
            else:
                oran = 1.0 if simdi >= hedef else max(0.0, (simdi - float(bas or 0)) / max(.01, float(hedef) - float(bas or 0)))
        except (TypeError, ValueError):
            oran = None
        simdi_m = f"{round(simdi, 1):g} {o.get('birim') or ''}".strip()
    else:
        simdi_m = None
    if oran is not None and oran >= 1.0:
        yolda, metin = "tamam", "Hedefe ulaştınız"
    elif oran is None:
        yolda, metin = "bilinmiyor", "Henüz ölçüm yok"
    elif kalan < 0:
        yolda, metin = "gecti", "Süre doldu"
    elif oran + 0.15 >= zaman_orani:
        yolda, metin = "yolunda", "Yolunda"
    else:
        yolda, metin = "geride", "Biraz geride"
    return {**out, "oran": round(oran, 3) if oran is not None else None, "simdi": simdi, "simdi_metni": simdi_m, "durum_metni": metin, "yolda": yolda}


def aktif():
    d = _oku()
    L = [ilerleme(h) for h in d.get("hedefler") or [] if h.get("durum") == "aktif"]
    L.sort(key=lambda x: list(VADE_GUN).index(x["vade"]))
    return L


def hepsi():
    d = _oku()
    return [ilerleme(h) for h in d.get("hedefler") or []]


def kendiliginden_tamamla():
    """Ölçüm hedefe ulaştıysa tamam yaz (kutlama için olay döner)."""
    olaylar = []
    with pt._kilit:
        d = _oku()
        for h in d.get("hedefler") or []:
            if h.get("durum") != "aktif":
                continue
            i = ilerleme(h)
            if i.get("yolda") == "tamam":
                h["durum"] = "tamam"
                h["tamam_tarih"] = pt.bugun().isoformat()
                olaylar.append({"id": f"hedef:{h['id']}", "tur": "hedef", "metin": h["metin"], "vade": h["vade"]})
        if olaylar:
            _yaz(d)
    return olaylar


def ozet():
    d = _oku()
    L = aktif()
    o = d.get("oneri") or {}
    return {"aktif": L, "var": bool(L), "onaylandi": d.get("onaylandi"), "oneri_var": bool(o.get("hedefler")),
            "bekleyen_oneri": bool(o.get("hedefler")) and not L}


def istem_metni():
    """Plan ve koç istemleri için tek paragraf."""
    L = aktif()
    if not L:
        return "henüz belirlenmedi"
    return "; ".join(f"{VADE_AD[h['vade']]} ({h['kalan_gun']} gün kaldı): {h['metin']}" + (f" [şu an {h['simdi_metni']}, {h['durum_metni'].lower()}]" if h.get("simdi_metni") else "")
                     for h in L)


if __name__ == "__main__":
    print(json.dumps({"adaylar": adaylar(), "aktif": aktif()}, ensure_ascii=False, indent=1, default=str))
