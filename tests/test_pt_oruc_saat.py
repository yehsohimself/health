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
