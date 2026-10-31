"""PT uzun ömür katmanı (2026-10-31): reçete (programın bileşimini kod kurar), haftalık doz, göstergeler, uzun ömür hedefleri."""
import datetime as dt
import json

import pytest

BUGUN = dt.date(2026, 10, 30)          # cuma


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    import pt_hedef
    import pt_kontrol
    import pt_oyun
    import pt_uzun
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt_oyun, "OYUN", v / "oyun.json")
    monkeypatch.setattr(pt_hedef, "HEDEFLER", v / "hedefler.json")
    monkeypatch.setattr(pt_kontrol, "DEGERLENDIRME", v / "degerlendirme.json")
    monkeypatch.setattr(pt_uzun, "RECETE", v / "recete.json")
    monkeypatch.setenv("VH_CLAUDE_YOK", "1")
    pt_oyun._onbellek.clear()
    pt.profil_kaydet({"ad": "Test", "kilo_kg": 84, "boy_cm": 178, "dogum_tarihi": "1986-05-02", "hedef_turleri": ["uzun_omur", "kas"],
                      "sevdikleri": ["jiujitsu", "yuruyus", "ev"], "bjj_ders": {"gunler": [1, 3], "saat": "19:00", "sure_dk": 90},
                      "gunler": [0, 2, 4, 5], "gunluk_dk": 45, "kuruldu": True, "ekipman": ["bar", "mat"]})
    return pt


def _gun(pt, tarih, **alan):
    d = {"tarih": tarih, "seanslar": [], "yemekler": [], "agri": [], "bjj": [], **alan}
    (pt.GUNLUK / f"{tarih}.json").write_text(json.dumps(d), encoding="utf-8")


def test_recete_ihtiyactan_kurulur(ptv):
    import pt_uzun
    r = pt_uzun.recete()
    kod = {x["kod"]: x for x in r["satirlar"]}
    assert kod["bjj_ders"]["haftada"] == 2 and kod["bjj_ders"]["sabit"]        # dersler sabit, sayılmaz
    assert kod["kalistenik"]["haftada"] >= 2                                   # uzun ömür: en az iki güç
    assert "kardiyo" in kod and "bisiklet" not in kod                          # bisikleti yok: yürüyüş
    assert r["toplam"] <= r["gun"]
    assert all(x["neden"] for x in r["satirlar"])
    assert r["ozet"].startswith("Haftada 6 gün")


def test_recete_sayilar_ve_uyari(ptv):
    import pt_uzun
    r = pt_uzun.recete(sayilar={"kalistenik": 1, "kardiyo": 0, "mobilite": 1}, kardiyo_tur="kosu")
    assert any("ikinin altında" in u for u in r["uyarilar"])
    assert any("Kardiyo günü yok" in u for u in r["uyarilar"])
    assert r["dozlar"]["guc"] == 2                                             # hedef düşmez, uyarı verilir


def test_recete_kaydet_profili_gunceller(ptv):
    import pt_uzun
    k = pt_uzun.recete_kaydet({"kalistenik": 2, "kardiyo": 2, "flow": 1}, "kosu")
    p = ptv.profil()
    assert p["yontemler"]["kardiyo"] == 2 and p["yontemler"]["flow"] == 1
    assert p["kardiyo_tur"] == "kosu" and k["onay"]
    assert "Kolay koşu" in pt_uzun.recete_metni()


def test_doz_seanslardan_sayilir(ptv):
    import pt_uzun
    pazartesi = BUGUN - dt.timedelta(days=BUGUN.weekday())
    _gun(ptv, pazartesi.isoformat(), seanslar=[{"bitti": True, "tur": "kalistenik", "sure_dk": 30,
                                                "bolumler": [{"hareketler": [{"kod": "tek_ayak_denge"}]}]}])
    _gun(ptv, (pazartesi + dt.timedelta(days=1)).isoformat(), seanslar=[{"bitti": True, "tur": "kardiyo", "sure_dk": 40,
                                                                       "kardiyo": {"tur": "yuruyus", "yogunluk": "kolay"}}],
         ek_gorev=["yuruyus"])
    _gun(ptv, (pazartesi + dt.timedelta(days=2)).isoformat(), seanslar=[{"bitti": True, "tur": "bjj_ders", "sure_dk": 90}], ek_gorev=["denge"])
    y = pt_uzun.hafta_olcumu()
    assert y["guc"] == 1 and y["kolay_dk"] == 60 and y["yogun"] == 1 and y["denge"] == 2


def test_oturkalk_testi_puana_cevrilir(ptv):
    import pt_uzun
    ptv.test_kaydet({"oturkalk": "Bir destek", "tek_ayak_sn": 22}, BUGUN.isoformat())
    G = {g["kod"]: g for g in pt_uzun.gostergeler()}
    assert G["oturkalk"]["deger"] == 9 and G["oturkalk"]["durum"] == "iyi"
    assert G["denge"]["deger"] == 22 and G["denge"]["durum"] == "orta"


def test_uzun_omur_hedef_adaylari(ptv):
    import pt_hedef
    ptv.test_kaydet({"tek_ayak_sn": 15, "oturkalk": "İki destek"}, BUGUN.isoformat())
    A = pt_hedef.adaylar()
    turler = {(a["vade"], a["olcu"]["tur"], a["olcu"].get("kod")) for a in A}
    assert ("kisa", "doz", None) in turler and ("uzun", "doz", None) in turler
    assert ("kisa", "test", "tek_ayak_sn") in turler and ("orta", "test", "oturkalk_puan") in turler
    secim = pt_hedef._kural_secimi(A, ptv.profil())["hedefler"]
    assert secim[0]["vade"] == "kisa" and "doz" in secim[0]["metin"]


def test_degerlendirme_ekip_ve_uzun_omur(ptv):
    import pt_kontrol
    d = pt_kontrol.degerlendirme(yenile=True)
    assert d["yazan"] == "kural"
    assert len(d["ekip"]) >= 6 and d["uzun_omur"]["ozet"]
    assert "jiu-jitsu" in d["antrenman"]["yaklasim"].lower()
