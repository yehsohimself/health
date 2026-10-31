"""Health: yemeye başlama ve son yemek saati seçilebilir (2026-10-31)."""
import time

import pytest


@pytest.fixture
def ptv(kok, tmp_path, monkeypatch):
    import pt
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    return pt


def test_saat_secimi_ve_sinirlar(ptv):
    import datetime as dt
    import pt_beslenme
    simdi = int(time.time())
    bugun = dt.date.today().isoformat()
    pt_beslenme.oruc_isaretle(bugun, "ac", t=simdi - 3600)
    assert ptv.gun(bugun)["oruc_acildi"] == simdi - 3600
    with pytest.raises(ValueError):                              # bitiş başlangıçtan önce olamaz
        pt_beslenme.oruc_isaretle(bugun, "kapat", t=simdi - 7200)
    pt_beslenme.oruc_isaretle(bugun, "kapat", t=simdi - 60)
    pd = pt_beslenme.pencere_durumu(tarih=bugun)
    assert pd["kapattim"] and pd["kapandi_t"] == simdi - 60 and pd["acildi_t"] == simdi - 3600
    pt_beslenme.oruc_isaretle(bugun, "ac", t=simdi - 5400)       # başlangıcı geriye düzeltmek kapanışı silmez
    assert ptv.gun(bugun)["oruc_kapandi"] == simdi - 60
    with pytest.raises(ValueError):
        pt_beslenme.oruc_isaretle(bugun, "ac", t=simdi + 3600)
    with pytest.raises(ValueError):
        pt_beslenme.oruc_isaretle(bugun, "ac", t=simdi - 5 * 86400)
    dun = int((dt.datetime.combine(dt.date.today(), dt.time()) - dt.timedelta(hours=2)).timestamp())
    if dun > simdi - 3 * 86400:
        g = pt_beslenme.oruc_isaretle(bugun, "kapat", t=dun)     # dün gece: dünün kaydına yazılır
        assert g == (dt.date.today() - dt.timedelta(days=1)).isoformat()
    pt_beslenme.oruc_isaretle(bugun, "kapat", geri=True)
    assert "oruc_kapandi" not in ptv.gun(bugun)


def test_oruc_fazi_ve_spor(ptv):
    import datetime as dt
    import pt_beslenme
    import pt_oruc
    simdi = int(time.time())
    bugun = dt.date.today().isoformat()
    ptv.profil_kaydet({"ad": "T", "kilo_kg": 80, "kuruldu": True, "beslenme": {"pencere_bas": "11:00", "pencere_saat": 6}})
    pt_beslenme.oruc_isaretle(bugun, "ac", t=simdi - 7 * 3600)
    pt_beslenme.oruc_isaretle(bugun, "kapat", t=simdi - 14 * 60)
    pen = pt_beslenme.pencere_durumu(tarih=bugun)
    o = pen["oruc"]
    assert o and o["bas_t"] == simdi - 14 * 60 and o["sonraki_t"] > simdi and o["protein_g"] == 30
    assert pt_oruc.faz(13)["kod"] == "yaga_gecis" and pt_oruc.faz(17)["kod"] == "hafif_ketoz"
    assert "ölçülemedi" in pt_oruc.otofaji(18)
    ptv.seans_kaydet(bugun, {"id": "s1", "tur": "spor", "baslik": "Futbol", "sure_dk": 60, "zorluk": 8})
    o = pt_beslenme.pencere_durumu(tarih=bugun)["oruc"]
    assert o["spor"][0]["ad"] == "Futbol" and o["kayma_sa"] == 4.0
    assert "Futbol 60 dk" in pt_oruc.anlat(o)
