"""pt_hizli.py - hızlı antrenman (2026-10-27; Nike Training Club'ın "süre + odak + ekipman seç, başla" deneyimi).

Claude YOK: seans kodla, saniyesinde kurulur ve oynatıcının biçimini (bolumler: set | tur | tabata | sure) kullanır.
Kişiye göre: zincir hareketleri o zincirdeki ŞU ANKİ basamağınızdan, hedef set/tekrar ilerleme kurallarından gelir; ekipmanınıza ve bulunduğunuz
yere (ev/park/yolda) göre seçilir; ağrı kuralı bozulan bölgeler (pt.koru_bolgeler) korunur. Odak "önerilen" ise son günlerde en az yüklenen
kas grubuna gider (pt_kitaplik.kas_durumu). Süre, oynatıcının adım hesabıyla aynı tahminle hedefe oturtulur.
"""
import random

import pt
import pt_kart

# odak: (ad, açıklama, zincirler, ısınma, soğuma)
ODAK = {
    "tum": ("Tüm vücut", "İtme, çekme, bacak ve gövde.", ["itme", "cekme", "bacak", "govde", "kalca", "dips", "plank"],
            ["jumping_jack", "kedi_inek", "dunya_esneme", "bilek_hazirlik"], ["dunya_esneme", "kanepe_esneme"]),
    "ust": ("Üst vücut", "Göğüs, sırt, omuz ve kollar.", ["itme", "cekme", "dips", "amut_itme", "plank", "front_lever"],
            ["bilek_hazirlik", "omuz_cevirme", "kedi_inek", "jumping_jack"], ["gogus_donus", "kedi_inek"]),
    "alt": ("Bacak ve kalça", "Squat, köprü ve baldır.", ["bacak", "kalca", "baldir", "kalca_kb", "govde"],
            ["jumping_jack", "dunya_esneme", "derin_squat_tutus", "kalca_9090"], ["kanepe_esneme", "kalca_9090"]),
    "govde": ("Karın ve gövde", "Hollow, plank ve asılı gövde.", ["govde", "plank", "asili_govde", "lsit"],
              ["kedi_inek", "dunya_esneme", "jumping_jack"], ["kedi_inek", "gogus_donus"]),
    "kondisyon": ("Kondisyon", "Tabata: 20 saniye çalış, 10 saniye dinlen.", None, ["jumping_jack", "dunya_esneme"], ["derin_squat_tutus", "kanepe_esneme"]),
    "flow": ("Animal flow", "Tutuşlar, geçişler ve akış.", None, ["bilek_hazirlik", "kedi_inek"], ["dunya_esneme"]),
    "bjj": ("Solo BJJ", "Kaçışlar, kalkışlar, guard ve gölge güreşi.", None, ["boyun_hazirlik", "kedi_inek", "kalca_9090"], ["kalca_9090"]),
    "mobilite": ("Hareketlilik", "Kalça, omurga ve omuz açılımı.", None, [], []),
}
SURELER = [5, 10, 15, 20, 30, 45]
KONDISYON = ["jumping_jack", "sprawl", "@bacak", "@itme", "beast", "teknik_kalkis", "ip_atlama", "golge_gures", "@kalca"]
ODAK_KASLARI = {"ust": {"gogus", "on_omuz", "yan_omuz", "arka_omuz", "triceps", "biceps", "ust_sirt", "kanat", "on_kol"},
                "alt": {"kalca", "on_bacak", "arka_bacak", "ic_bacak", "baldir"},
                "govde": {"karin", "yan_karin", "bel"}}


def _var_olan(p, nerede):
    if nerede in ("yolda", "otel"):
        return set()
    v = set(p.get("ekipman") or [])
    if nerede == "park":
        v |= {"bar", "paralel"}
    return v


def _uygun(kod, kat, var_olan, koru, izin=None):
    """Ekipmana ve korunan bölgelere uygun hali. `izin`: odağın zincirleri; ekipmansız karşılık başka bir bölgeye kayıyorsa (üst vücutta
    barfiks yerine kalça köprüsü gibi) hareket alınmaz."""
    h = kat.get(kod)
    if not h:
        return None
    k2 = pt.ekipmansiz_karsilik(kod, var_olan, kat)
    if izin is not None and k2 != kod and (kat.get(k2) or {}).get("zincir") not in izin:
        return None
    h = kat.get(k2) or h
    if h["ekipman"] not in ("yok", "mat", "duvar") and h["ekipman"] not in var_olan:
        return None
    while set(h.get("bolge") or []) & set(koru):
        alt = pt.zincir_komsu(h["kod"], -1, kat)
        if not alt:
            return None
        h = kat[alt]
    return h["kod"]


def _isinma_sec(L, kat, var_olan, koru, n):
    out = []
    for k in L:
        u = _uygun(k, kat, var_olan, koru)
        if u and u not in out:
            out.append(u)
    return out[:n]


def adim_sure(seans, kat):
    """pt.html adimlar() ile aynı süre tahmini (saniye)."""
    top = 0
    bol = seans.get("bolumler") or []
    for n, b in enumerate(bol):
        bic, hs = b.get("bicim") or "set", b.get("hareketler") or []
        if bic in ("tur", "tabata", "emom"):
            tur = b.get("tur_sayisi") or 3
            cs = b.get("calisma_sn") or (20 if bic == "tabata" else 40)
            ds = b.get("dinlenme_sn", 10 if bic == "tabata" else 20)
            top += tur * sum(h.get("sure_sn") or cs for h in hs) + max(0, tur * len(hs) - 1) * ds
        elif bic in ("sure", "akis"):
            top += sum((h.get("sure_sn") or (h.get("tekrar") or 8) * 4) for h in hs) + max(0, len(hs) - 1) * 8
        else:
            for i, h in enumerate(hs):
                k = kat.get(h["kod"]) or {}
                s = h.get("set") or 3
                ust = int(str(h.get("tekrar") or "8").split("-")[-1] or 8)
                calis = h.get("sure_sn") or (ust if k.get("olcu") == "sure" else ust * 3.2 + 6)
                dinlen = h.get("dinlenme_sn") or 90
                top += s * calis + (s - 1) * dinlen + (0 if i == len(hs) - 1 else min(90, dinlen))
        if n < len(bol) - 1:
            top += 20
    return top


def onerilen_odak():
    """Son günlerde en az yüklenen kas grubu. Döner: (odak, neden)."""
    import pt_kitaplik
    D = {x["kas"]: x for x in pt_kitaplik.kas_durumu(7)}
    puan = {}
    for o, kaslar in ODAK_KASLARI.items():
        L = [D[k] for k in kaslar if k in D]
        puan[o] = sum(x["taze"] for x in L) / len(L) - sum(x["set"] for x in L) / (len(L) * 40)
    yorgun = [o for o, kaslar in ODAK_KASLARI.items() if any((D.get(k) or {}).get("taze", 1) < .5 for k in kaslar)]
    if not any(x["son"] for x in D.values()):
        return "tum", "Henüz kayıt yok: tüm vücutla başlayalım."
    en = max(puan, key=puan.get)
    if all(v > .95 for v in puan.values()):
        return "tum", "Bütün kaslarınız dinlenmiş: tüm vücut."
    ad = {"ust": "üst vücut", "alt": "bacak ve kalça", "govde": "gövde"}
    neden = f"{ad[en].capitalize()} en dinlenmiş bölgeniz"
    if yorgun:
        neden += f"; {', '.join(ad[o] for o in yorgun if o != en)} son 48 saatte çalıştı" if [o for o in yorgun if o != en] else ""
    return en, neden + "."


def olustur(sure_dk=20, odak="onerilen", nerede="ev", tohum=None, kod=None, p=None, vurgu=None):
    """Hızlı antrenman seansı. `kod` verilirse tek harekete odaklı seans ("Bunu şimdi yap"). `vurgu`: öne alınan, bir set fazla çalışılan zincirler
    (hazır programlar)."""
    p = p or pt.profil()
    kat = pt.katalog()
    sure_dk = min(SURELER, key=lambda x: abs(x - int(sure_dk or 20)))
    rnd = random.Random(tohum)
    var_olan = _var_olan(p, nerede)
    koru = pt.koru_bolgeler()
    neden = ""
    if kod:
        return _tek(kod, kat, var_olan, koru, p)
    if odak == "onerilen" or odak not in ODAK:
        odak, neden = onerilen_odak()
    ad, aciklama, zincirler, isinma, soguma = ODAK[odak]
    hedef_sn = sure_dk * 60
    bolumler = []
    if sure_dk >= 10 and isinma:
        isn = _isinma_sec(rnd.sample(isinma, len(isinma)), kat, var_olan, koru, 2 if sure_dk <= 15 else 3)
        if isn:
            bolumler.append({"ad": "Isınma", "bicim": "sure", "hareketler": [{"kod": k, "sure_sn": 30 if sure_dk <= 15 else 45} for k in isn]})
    sog = []
    if sure_dk >= 20 and soguma:
        sog = _isinma_sec(soguma, kat, var_olan, koru, 2)

    def toplam(ana):
        return adim_sure({"bolumler": bolumler + [ana] + ([{"bicim": "sure", "hareketler": [{"kod": x, "sure_sn": 45} for x in sog]}] if sog else [])}, kat)

    vurgu = [z for z in vurgu or [] if z]
    if zincirler and vurgu:
        zincirler = vurgu + [z for z in zincirler if z not in vurgu]
    if zincirler:                                                            # güç odakları
        hs = []
        for z in zincirler:
            u = _uygun(pt.aktif_basamak(z, kat), kat, var_olan, koru, set(zincirler))
            if u and u not in hs and kat[u].get("zincir") not in {kat[x].get("zincir") for x in hs}:
                hs.append(u)
        n_bas = max(2, sum(1 for k in hs if kat[k].get("zincir") in vurgu))
        hs = hs[:n_bas] + rnd.sample(hs[n_bas:], len(hs[n_bas:]))
        if sure_dk <= 15:                                                    # kısa: devre (tur)
            ana = {"ad": "Ana bölüm", "bicim": "tur", "tur_sayisi": 3, "calisma_sn": 40, "dinlenme_sn": 20, "hareketler": [{"kod": k} for k in hs[:3 if sure_dk <= 10 else 4]]}
        else:
            ana = {"ad": "Ana bölüm", "bicim": "set", "hareketler": []}
            for k in hs:
                hd = pt.hedef(k, kat)
                ana["hareketler"].append({"kod": k, "set": hd["set"], "tekrar": f"{hd['alt']}-{hd['ust']}",
                                          "dinlenme_sn": 75 if kat[k].get("zincir") in ("itme", "cekme", "dips", "bacak") else 50})
                if hd["olcu"] == "sure":
                    ana["hareketler"][-1]["sure_sn"] = hd["ust"]
                if len(ana["hareketler"]) > 1 and toplam(ana) > hedef_sn * 1.08:
                    ana["hareketler"].pop()
                    break
            for h_ in ana["hareketler"]:                                     # programın vurguladığı zincir: bir set fazla
                if kat[h_["kod"]].get("zincir") in vurgu and h_["set"] < 5:
                    h_["set"] += 1
            n = 0                                                            # süre kaldıysa set ekle (en çok 5)
            while toplam(ana) < hedef_sn * .9 and n < 20:
                h_ = ana["hareketler"][n % len(ana["hareketler"])]
                if h_["set"] < 5:
                    h_["set"] += 1
                    if toplam(ana) > hedef_sn * 1.05:
                        h_["set"] -= 1
                        break
                n += 1
    else:
        tur_ = {"kondisyon": None, "flow": "flow", "bjj": "bjj", "mobilite": "mobilite"}[odak]
        if odak == "kondisyon":
            L = []
            for k in KONDISYON:
                k = pt.aktif_basamak(k[1:], kat) if k.startswith("@") else k
                u = _uygun(k, kat, var_olan, koru)
                if u and u not in L:
                    L.append(u)
            L = L[:2] + rnd.sample(L[2:], len(L[2:]))
            ana = {"ad": "Ana bölüm", "bicim": "tabata", "tur_sayisi": 4, "calisma_sn": 20, "dinlenme_sn": 10, "hareketler": L[:2]}
            ana["hareketler"] = [{"kod": k} for k in L[:2]]
            bloklar = [ana]
            i = 2
            while adim_sure({"bolumler": bolumler + bloklar}, kat) + 260 <= hedef_sn - (90 if sog else 0) and len(bloklar) < 9:
                cift = (L * 2)[i:i + 2]
                bloklar.append({"ad": f"Blok {len(bloklar) + 1}", "bicim": "tabata", "tur_sayisi": 4, "calisma_sn": 20, "dinlenme_sn": 10,
                                "hareketler": [{"kod": k} for k in cift]})
                i += 2
            bloklar[0]["ad"] = "Blok 1" if len(bloklar) > 1 else "Ana bölüm"
            bolumler += bloklar
            ana = None
        else:
            L = [x["kod"] for x in sorted(kat.values(), key=lambda x: x.get("basamak") or 0) if x.get("tur") == tur_]
            L = [u for u in dict.fromkeys(_uygun(k, kat, var_olan, koru) for k in L) if u]
            L = rnd.sample(L, len(L))
            cs = 45 if odak != "mobilite" else 60
            ana = {"ad": "Ana bölüm", "bicim": "tur" if odak != "mobilite" else "sure", "tur_sayisi": 1, "calisma_sn": cs, "dinlenme_sn": 15,
                   "hareketler": [{"kod": k, "sure_sn": cs} if odak == "mobilite" else {"kod": k} for k in L[:4 if odak != "mobilite" else 8]]}
            if odak != "mobilite":
                while adim_sure({"bolumler": bolumler + [{**ana, "tur_sayisi": ana["tur_sayisi"] + 1}]}, kat) <= hedef_sn - (90 if sog else 0):
                    ana["tur_sayisi"] += 1
                    if ana["tur_sayisi"] >= 12:
                        break
            else:
                while len(ana["hareketler"]) > 2 and adim_sure({"bolumler": bolumler + [ana]}, kat) > hedef_sn:
                    ana["hareketler"].pop()
                n = len(ana["hareketler"])                                   # uzun seansta her harekete daha çok süre (en çok 150 sn)
                sn = max(45, min(180, int((hedef_sn - (n - 1) * 8) / n)))
                for h_ in ana["hareketler"]:
                    h_["sure_sn"] = sn
    if zincirler and ana.get("bicim") == "tur":
        while adim_sure({"bolumler": bolumler + [{**ana, "tur_sayisi": ana["tur_sayisi"] + 1}]}, kat) <= hedef_sn - (90 if sog else 0) and ana["tur_sayisi"] < 6:
            ana["tur_sayisi"] += 1
        while ana["tur_sayisi"] > 2 and adim_sure({"bolumler": bolumler + [ana]}, kat) > hedef_sn + 60:
            ana["tur_sayisi"] -= 1
    if ana:
        bolumler.append(ana)
    if sog:
        bolumler.append({"ad": "Soğuma", "bicim": "sure", "hareketler": [{"kod": k, "sure_sn": 45} for k in sog]})
    s = {"tur": "mobilite" if odak == "mobilite" else "flow" if odak == "flow" else "bjj_solo" if odak == "bjj" else "kalistenik",
         "baslik": ad, "hedef_dk": sure_dk, "hizli": True, "odak": odak, "nerede": nerede, "bolumler": bolumler, "aciklama": aciklama,
         "neden": neden}
    return _son(s, kat, koru)


def _tek(kod, kat, var_olan, koru, p):
    if kod not in kat:
        raise ValueError("Böyle bir hareket yok.")
    h = kat[kod]
    hd = pt.hedef(kod, kat)
    isinma = {"kalistenik": ["jumping_jack", "kedi_inek", "bilek_hazirlik"], "bjj": ["kedi_inek", "kalca_9090"], "flow": ["bilek_hazirlik", "kedi_inek"]}.get(h["tur"], [])
    isn = _isinma_sec(isinma, kat, var_olan, koru, 2)
    bol = [{"ad": "Isınma", "bicim": "sure", "hareketler": [{"kod": k, "sure_sn": 40} for k in isn if k != kod]}] if isn and h["tur"] not in ("mobilite", "isinma") else []
    if h["tur"] in ("mobilite", "isinma"):
        bol.append({"ad": "Ana bölüm", "bicim": "sure", "hareketler": [{"kod": kod, "sure_sn": 60}]})
    elif h["tur"] in ("bjj", "flow"):
        bol.append({"ad": "Ana bölüm", "bicim": "tur", "tur_sayisi": 4, "calisma_sn": 40, "dinlenme_sn": 20, "hareketler": [{"kod": kod}]})
    else:
        x = {"kod": kod, "set": hd["set"], "tekrar": f"{hd['alt']}-{hd['ust']}", "dinlenme_sn": 90}
        if hd["olcu"] == "sure":
            x["sure_sn"] = hd["ust"]
        bol.append({"ad": "Ana bölüm", "bicim": "set", "hareketler": [x]})
    uyari = []
    if set(h.get("bolge") or []) & set(koru):
        uyari.append(f"{', '.join(pt.BOLGELER.get(b, b) for b in set(h['bolge']) & set(koru))} şu an korunuyor; ağrı olursa bırakın.")
    s = {"tur": h["tur"] if h["tur"] in pt.YONTEMLER else "kalistenik", "baslik": h["ad"], "hizli": True, "tek": kod, "bolumler": bol,
         "aciklama": f"Isınma ve {hd['set']} set {h['ad'].lower()}." if h["tur"] == "kalistenik" else "", "uyarlama": uyari}
    return _son(s, kat, koru)


def _son(s, kat, koru):
    K = pt_kart.kartlar()
    kas = {}
    for b in s["bolumler"]:
        if b.get("ad") in ("Isınma", "Soğuma"):
            continue
        for h in b.get("hareketler") or []:
            for m in ((K.get(h["kod"]) or {}).get("kaslar") or {}).get("birincil") or []:
                kas[m] = kas.get(m, 0) + 1
    s["sure_dk"] = max(1, round(adim_sure(s, kat) / 60))
    s["kaslar"] = [m for m, _ in sorted(kas.items(), key=lambda x: -x[1])][:5]
    ek = sorted({kat[h["kod"]]["ekipman"] for b in s["bolumler"] for h in b.get("hareketler") or [] if h["kod"] in kat} - {"yok"})
    s["ekipman"] = [pt.EKIPMANLAR.get(e, "Duvar" if e == "duvar" else e) for e in ek]
    s["id"] = "hizli"
    if koru and not s.get("tek"):
        s.setdefault("uyarlama", []).append(f"{', '.join(pt.BOLGELER.get(b, b) for b in koru)} korunuyor: o bölgeyi yükleyen hareketler bir basamak kolay.")
    return s


def secenekler():
    return {"sureler": SURELER, "odaklar": [{"kod": k, "ad": v[0], "aciklama": v[1]} for k, v in ODAK.items()],
            "onerilen": dict(zip(("odak", "neden"), onerilen_odak()))}
