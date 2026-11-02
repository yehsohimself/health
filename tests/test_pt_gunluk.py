"""Günlük sabit liste + sürpriz: plan kodla kurulur, ısınma/yürüyüş/test/alet giremez (2026-11-02)."""
import datetime as dt

import pytest

BUGUN = dt.date(2026, 11, 4)                       # Çarşamba


@pytest.fixture
def g(kok, tmp_path, monkeypatch):
    import pt
    import pt_gunluk
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    (v / "program" / "gecmis").mkdir()
    monkeypatch.setattr(pt, "bugun", lambda: BUGUN)
    monkeypatch.setattr(pt, "yorgunluk_durumu", lambda: {"durum": "iyi"})
    pt.profil_kaydet({"ad": "Deneme", "gunluk_dk": 30, "ekipman": ["mat"]})
    pt.test_kaydet({"squat_max": 50, "sinav_max": 10, "plank_sn": 30}) if hasattr(pt, "test_kaydet") else None
    pt_gunluk.kur(yuruyus_dk=90)
    return pt, pt_gunluk


def _kodlar(gun):
    return [h["kod"] for b in gun["bolumler"] for h in b["hareketler"]]


def test_her_gun_ayni_liste_ve_tek_surpriz(g):
    pt, G = g
    pl = pt.program(pt.hafta_kodu())
    assert len(pl["gunler"]) == 7
    kat = pt.katalog()
    surprizler = []
    for gun in pl["gunler"]:
        assert gun["tur"] == "kalistenik" and gun["sure_dk"] <= 30
        bol = {b["ad"]: b for b in gun["bolumler"]}
        assert set(bol) == {"Günlük liste", "Sürpriz"}
        assert len(bol["Günlük liste"]["hareketler"]) == len(G.VARSAYILAN)
        assert len(bol["Sürpriz"]["hareketler"]) == 1
        surprizler.append(bol["Sürpriz"]["hareketler"][0]["kod"])
        for k in _kodlar(gun):
            assert kat[k]["ekipman"] in ("yok", "mat", "duvar"), k
            assert kat[k]["tur"] != "isinma", k
            assert k not in ("kedi_inek", "bilek_hazirlik", "gogus_donus", "dunya_esneme", "kalca_9090", "kanepe_esneme"), k
    assert len(set(surprizler)) == 7
    assert G.gunun_surprizi("2026-11-04")[0] == G.gunun_surprizi("2026-11-04")[0]


def test_surpriz_adaylari_gecerli_ve_ay_boyu_tekrarsiz(g):
    pt, G = g
    kat = pt.katalog()
    sira = G.surpriz_sirasi(kat=kat)
    assert len(sira) >= 25 and len({k for k, _ in sira}) == len(sira)
    for (k, gr), (_, gr2) in zip(sira, sira[1:]):
        assert k in kat and G.aletsiz(k, kat)
    assert sum(1 for a, b in zip(sira, sira[1:]) if a[1] == b[1]) <= 2


def test_adetler_dalgalanir_ve_testten_gelir(g):
    pt, G = g
    gunler = pt.program(pt.hafta_kodu())["gunler"]
    def squat(i):
        return next(h for h in gunler[i]["bolumler"][0]["hareketler"] if h["kod"] == "squat")
    assert int(squat(1)["tekrar"]) < int(squat(0)["tekrar"]) < int(squat(2)["tekrar"])      # hafif < orta < zorlu
    assert squat(2)["set"] == 3 and squat(1)["set"] == 2
    assert len({h["kod"] for gun in gunler for h in gun["bolumler"][0]["hareketler"]} & {"sinav", "genis_sinav", "ayak_yuksek_sinav"}) >= 2


def test_test_istenmez_ve_plan_uret_claude_cagirmaz(g, monkeypatch):
    pt, G = g
    assert pt.test_gerekli() is False
    import claude_yaz
    monkeypatch.setattr(claude_yaz, "sor_json", lambda *a, **k: pytest.fail("Claude çağrılmamalı"))
    pl = pt.program_uret(None, "yürüyüş ve ısınma ekle")
    assert all(g_["tur"] == "kalistenik" for g_ in pl["gunler"])
    assert all(b["ad"] != "Isınma" for b in pt.asgari_seans()["bolumler"])


def test_kirmizi_gun_hareket_yok(g):
    pt, G = g
    gun = G.gun_kur("2026-11-04")
    assert pt.seansi_uyarla(gun, "kirmizi")["tur"] == "dinlenme"


def test_hedef_iki_basaridan_sonra_artar_ve_geri_alinir(g):
    pt, G = g
    bas = G.seviye("squat")
    gun = pt.program(pt.hafta_kodu())["gunler"][2]
    sq = next(h for h in gun["bolumler"][0]["hareketler"] if h["kod"] == "squat")
    kayit = {"tarih": gun["tarih"], "plan_id": gun["id"], "zorluk": 6, "hareketler": [{"kod": "squat", "setler": [{"deger": int(sq["tekrar"])}] * sq["set"]}]}
    assert pt.seans_sonrasi_ilerleme(kayit) == []
    d = pt.seans_sonrasi_ilerleme(kayit)
    assert d and G.seviye("squat") > bas
    assert pt.degisiklik_geri_al(d[0]["id"]) and G.seviye("squat") == bas


def test_liste_sohbetten_degisir_alet_giremez(g):
    pt, G = g
    G.liste_degistir({"cikar": ["superman"], "ekle": ["yan_plank", "barfiks", "kedi_inek"], "surpriz_cikar": ["sprawl"], "seviye": {"plank": 40}})
    a = G.ayar()
    assert "superman" not in a["sabit"] and "yan_plank" in a["sabit"]
    assert "barfiks" not in a["sabit"] and "kedi_inek" not in a["sabit"]
    assert "sprawl" not in [k for k, _ in G.surpriz_sirasi()]
    assert G.seviye("plank") == 40


def test_yuruyus_doza_sayilir_plana_girmez(g):
    pt, G = g
    import pt_uzun
    assert pt_uzun.hafta_olcumu()["kolay_dk"] == 180                 # pazartesi + salı
    assert pt_uzun.plan_dozu()["kolay_dk"] >= 150
