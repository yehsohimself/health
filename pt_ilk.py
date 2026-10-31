"""pt_ilk.py - İlk hafta yolu (2026-10-28; kullanıcı kurulumdan sonra ilk seansta bırakmıştı: her gün 30 dk + 30 dk test).

Yedi sabit adım; Bugün ekranında her gün TEK düğme. Adımlar takvime değil sıraya bağlıdır: kaçırılan gün ceza değildir,
ertesi gün kaldığı yerden sürer. Antrenman adımları pt_hizli ile kişinin basamaklarından kurulur (Claude yok), test
adımları başlangıç testlerini iki parçaya böler (zaten yapılmış testler atlanır). Yedinci adımdan sonra normal haftalık plan.
Durum pt/ilk_hafta.json: {bas, tamam: [{adim, tarih}], birakti}.
"""
import hashlib

import pt

TEST_1 = ["squat_max", "sinav_max", "plank_sn"]
TEST_2 = ["hollow_sn", "derin_squat", "omuz_duvar", "tek_ayak_sn", "oturkalk"]


def _adimlar(p):
    y = p.get("yontemler") or {}
    son = "bjj" if (y.get("bjj_solo") or 0) >= 2 else "flow" if (y.get("flow") or 0) >= 2 else "tum"
    son_ad = {"bjj": "Solo jiu-jitsu", "flow": "Animal flow", "tum": "Tüm vücut"}[son]
    return [
        {"ad": "Tanışma testi", "tur": "test", "testler": TEST_1, "dk": 5,
         "aciklama": "Üç kısa test: squat, şınav, plank. Nereden başlayacağımızı bunlar söyler."},
        {"ad": "İlk antrenman", "tur": "hizli", "odak": "tum", "dk": 10,
         "aciklama": "Tüm vücut, en kolay basamaklar. Nefesiniz hafif hızlansın, yorulmayın."},
        {"ad": "İkinci tanışma testi", "tur": "test", "testler": TEST_2, "dk": 7,
         "aciklama": "Gövde, denge ve hareketlilik testleri. Tek ayak dengesi ve yere oturup kalkma, yaşlanmayı en iyi gösteren iki ölçü."},
        {"ad": "Bacak ve kalça", "tur": "hizli", "odak": "alt", "dk": 10,
         "aciklama": "Squat, köprü ve baldır. Dizler ayak uçlarıyla aynı yönde."},
        {"ad": "Üst vücut", "tur": "hizli", "odak": "ust", "dk": 10,
         "aciklama": "İtme, çekme ve omuz. Her setin sonunda iki tekrar daha yapabilecek gibi bitirin."},
        {"ad": "Hareketlilik", "tur": "hizli", "odak": "mobilite", "dk": 10,
         "aciklama": "Kalça, omurga ve omuz açılımı. Dinlenme günü gibi; zorlamadan."},
        {"ad": "İlk haftanın son antrenmanı", "tur": "hizli", "odak": son, "dk": 15,
         "aciklama": f"{son_ad}, 15 dakika. Bu adımla ilk haftanız biter."},
    ]


def _durum_dosya():
    return pt._json(pt.VERI / "ilk_hafta.json", {"bas": None, "tamam": [], "birakti": False})


def _yaz(d):
    pt._yaz(pt.VERI / "ilk_hafta.json", d)


def durum():
    """Bugün ekranı için: aktif mi, sıradaki adım (seans ya da test listesi), adımların durumu."""
    d = _durum_dosya()
    p = pt.profil()
    A = _adimlar(p)
    tamam = {x["adim"]: x["tarih"] for x in d.get("tamam") or []}
    bugun = pt.bugun().isoformat()
    bitti = len(tamam) >= len(A)
    son_t = max(tamam.values()) if tamam else None
    if d.get("birakti"):
        return {"aktif": False}
    if not d.get("bas") and pt.baslangic_durumu().get("tur") != "alisma":
        return {"aktif": False}                     # zaten alışmış kullanıcıya yol açılmaz
    if bitti:
        yeni = son_t and (pt.bugun() - pt.dt.date.fromisoformat(son_t)).days <= 2
        return {"aktif": False, "bitti": True, "kutla": bool(yeni)}
    eksik = set(pt.test_eksikleri())
    adimlar = []
    for i, a in enumerate(A):
        x = {k: a[k] for k in ("ad", "tur", "dk", "aciklama")}
        if a["tur"] == "test":
            x["testler"] = [t for t in a["testler"] if t in eksik or t not in pt.TEMEL_TESTLER]
            if i not in tamam and not [t for t in a["testler"] if t in eksik]:
                tamam[i] = son_t or bugun          # testleri zaten yapılmış: adım kendiliğinden geçer
                x["atlandi"] = True
        x["durum"] = "tamam" if i in tamam else "sonra"
        adimlar.append(x)
    sira = next((i for i in range(len(A)) if i not in tamam), None)
    if sira is None:
        return {"aktif": False, "bitti": True, "kutla": True}
    adimlar[sira]["durum"] = "simdi"
    simdi = dict(adimlar[sira], no=sira)
    if A[sira]["tur"] == "hizli":
        import pt_hizli
        tohum = int(hashlib.sha1(f"{d.get('bas') or bugun}|{sira}".encode()).hexdigest()[:8], 16)
        s = pt_hizli.olustur(A[sira]["dk"], A[sira]["odak"], "ev", tohum=tohum, p=p)
        s.update({"id": f"ilk{sira}", "ilk_adim": sira, "baslik": A[sira]["ad"]})
        simdi["seans"] = s
    bugun_tamam = any(t == bugun for i, t in tamam.items() if not adimlar[i].get("atlandi"))
    return {"aktif": True, "adim": sira, "toplam": len(A), "adimlar": adimlar, "simdi": simdi, "bugun_tamam": bugun_tamam,
            "bas": d.get("bas")}


def tamamla(adim):
    """Adım bitti (antrenman kaydı `ilk_adim` taşır, test sayfası bitince çağrılır). Her adım bir kez sayılır."""
    with pt._kilit:
        d = _durum_dosya()
        if d.get("birakti"):
            return False
        bitenler = {x["adim"] for x in d.get("tamam") or []}
        if adim in bitenler or not 0 <= adim < 7:
            return False
        d.setdefault("bas", None)
        d["bas"] = d["bas"] or pt.bugun().isoformat()
        d.setdefault("tamam", []).append({"adim": adim, "tarih": pt.bugun().isoformat()})
        _yaz(d)
    return True


def baslat():
    with pt._kilit:
        d = _durum_dosya()
        if not d.get("bas"):
            d["bas"] = pt.bugun().isoformat()
            _yaz(d)


def birak(geri=False):
    with pt._kilit:
        d = _durum_dosya()
        d["birakti"] = not geri
        _yaz(d)
