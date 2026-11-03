"""Health gidişat: seriler, oruç süresi, gün dökümü (2026-11-02). Yalnız sanal klasörde."""
import datetime as dt
import time

import pytest


@pytest.fixture
def g(kok, tmp_path, monkeypatch):
    import pt
    import pt_gidisat
    import pt_saglik
    v = tmp_path / "pt"
    monkeypatch.setattr(pt_saglik, "KLASOR", v / "saglik")
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    pt_gidisat._ON.clear()
    monkeypatch.setattr(pt_gidisat, "_pencere_sa", lambda p=None: 6.0)
    monkeypatch.setattr(pt, "profil", lambda: {"beslenme": {"pencere_saat": 6}})
    return pt_gidisat


def _t(gun_once, saat, dakika=0):
    g = dt.date.today() - dt.timedelta(days=gun_once)
    return g.isoformat(), int(dt.datetime.combine(g, dt.time(saat, dakika)).timestamp())


def _yaz(tarih, **alan):
    import pt
    pt.gun_degistir(tarih, lambda d: d.update(alan))


def test_oruc_biten_gune_yazilir_ve_tolerans(g):
    d2, a2 = _t(2, 18)
    d1, b1 = _t(1, 11, 42)                                      # 17 sa 42 dk: hedef 18, tolerans içinde
    _yaz(d2, oruc_kapandi=a2)
    _yaz(d1, oruc_acildi=b1, oruc_kapandi=b1 + 3 * 3600)
    s = g.gun_satiri(d1)
    assert s["oruc_sa"] == 17.7 and s["oruc_tamam"] and not s["oruc_tahmini"]
    assert g.oruc_gunu(d2) is None                              # öncesi yok: uydurulmaz


def test_kisa_oruc_seriyi_bozar_ve_gosterilir(g):
    d3, a3 = _t(3, 20)
    d2, b2 = _t(2, 12)                                          # 16 sa: hedefin altında
    _yaz(d3, oruc_kapandi=a3)
    _yaz(d2, oruc_acildi=b2, oruc_kapandi=b2 + 6 * 3600)
    s = g.gun_satiri(d2)
    assert s["oruc_sa"] == 16.0 and not s["oruc_tamam"]
    d1, b1 = _t(1, 12, 30)                                      # 18,5 sa: tuttu
    _yaz(d1, oruc_acildi=b1)
    assert g.ozet()["oruc"]["seri"] == 1


def test_son_yemek_isaretlenmemisse_tahmin(g):
    d2, a2 = _t(2, 12)
    d1, b1 = _t(1, 12)
    _yaz(d2, oruc_acildi=a2)                                    # kapanış yok: 12 + 6 sa = 18.00 sayılır
    _yaz(d1, oruc_acildi=b1)
    o = g.oruc_gunu(d1)
    assert o["saat"] == 18.0 and o["tahmini"]


def test_hareket_serisi_bugun_bozmaz_bosluk_bozar(g):
    for n in (3, 2, 1):
        _yaz(_t(n, 12)[0], seanslar=[{"bitti": True, "sure_dk": 10, "tur": "spor"}])
    _yaz(_t(5, 12)[0], seanslar=[{"bitti": True, "sure_dk": 10, "tur": "spor"}])
    H = g.ozet()["hareket"]
    assert H["seri"] == 3 and H["en_uzun"] == 3                 # bugün henüz yapılmadı: seri sürüyor
    _yaz(_t(0, 12)[0], seanslar=[{"bitti": False, "sure_dk": 10, "tur": "spor"}])
    assert g.ozet()["hareket"]["seri"] == 3                     # bitmemiş seans sayılmaz
    _yaz(_t(0, 12)[0], seanslar=[{"bitti": True, "sure_dk": 10, "tur": "dinlenme"}])
    assert not g.hareket_gunu(_t(0, 12)[0])["var"]


def test_takvim_bes_hafta_pazartesiden_gelecek_isaretli(g):
    T = g.takvim()
    assert len(T["gunler"]) == 35
    assert dt.date.fromisoformat(T["gunler"][0]["tarih"]).weekday() == 0
    bugun = dt.date.today().isoformat()
    assert all(x.get("gelecek") == (x["tarih"] > bugun) or (not x.get("gelecek") and x["tarih"] <= bugun) for x in T["gunler"])
    assert T["sonraki"] is False


def test_takvim_ilk_kayittan_once_bos_hafta_gostermez(g):
    _yaz(_t(1, 12)[0], su_ml=500)
    T = g.takvim()
    assert len(T["gunler"]) in (7, 14) and T["onceki"] is False
    assert dt.date.fromisoformat(T["gunler"][0]["tarih"]).weekday() == 0


def test_gun_dokumu_ve_gecersiz_tarih(g):
    d, a = _t(1, 12)
    _yaz(d, oruc_acildi=a, oruc_kapandi=a + 3600, su_ml=1500, sabah={"uyku_saat": 7, "enerji": 4, "isik": "yesil"},
         seanslar=[{"bitti": True, "baslik": "Günlük liste", "sure_dk": 18, "zorluk": 6, "hareketler": [{"kod": "sinav", "setler": [{"deger": 10}, {"deger": 10}]}]},
                   {"bitti": False, "baslik": "Yapılmadı", "sure_dk": 30}])
    r = g.gun_ozet(d)
    assert [s["baslik"] for s in r["seanslar"]] == ["Günlük liste"]
    assert r["seanslar"][0]["hareketler"] == [{"ad": "Şınav", "setler": "2 × 10"}]
    assert r["su_ml"] == 1500 and r["sabah"]["uyku_saat"] == 7 and r["yeme"]["bit_t"] == a + 3600
    with pytest.raises(ValueError):
        g.gun_ozet("../profil")


def test_suren_oruc(g):
    d, a = _t(1, 18)
    _yaz(d, oruc_kapandi=a)
    s = g.suren_oruc()
    assert s["durum"] == "oruc" and s["saat"] == round((time.time() - a) / 3600, 1)
