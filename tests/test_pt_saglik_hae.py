"""Health Auto Export'un AutoSync .hae dosyaları (uydurma veri; sıkıştırılmamış LZFSE bloğu)."""
import json
import os
import struct
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="libcompression yalnız macOS'ta")


@pytest.fixture
def pt_saglik(kok, tmp_path, monkeypatch):
    """Sanal kökten; gerçek pt/ klasörü testlerde asla yüklenmesin (modülü dosya başında içe aktarma)."""
    import pt
    import pt_saglik as m
    monkeypatch.setattr(pt, "VERI", tmp_path / "pt")
    monkeypatch.setattr(m, "KLASOR", tmp_path / "pt" / "saglik")
    monkeypatch.setattr(m, "AYAR", tmp_path / "pt" / "ayar.json")
    return m


def _hae(d):
    b = json.dumps(d).encode()
    return b"bvx-" + struct.pack("<I", len(b)) + b + b"bvx$"


def test_hae_coz_ve_bozuk(pt_saglik):
    assert pt_saglik.hae_coz(_hae({"metric": "x", "data": []}))["metric"] == "x"
    assert pt_saglik.hae_coz(b"bozuk") is None


def test_deger_hesabi(pt_saglik):
    adim = {"data": [{"qty": 1.4, "start": 1}, {"qty": 2.2, "start": 2}]}
    assert pt_saglik.hae_deger("step_count", adim) == ("adim", 4)
    assert pt_saglik.hae_deger("resting_heart_rate", {"data": [{"qty": 50}, {"qty": 60}]}) == ("nabiz", 55.0)
    assert pt_saglik.hae_deger("weight_body_mass", {"data": [{"qty": 80, "start": 1, "unit": "kg"}, {"qty": 79.5, "start": 2, "unit": "kg"}]}) == ("kilo", 79.5)
    assert pt_saglik.hae_deger("step_count", {"data": []}) is None


def test_tarama_gun_yazar_gorulen_atlar_yarim_dosyayi_yeniden_dener(pt_saglik, tmp_path):
    kl = tmp_path / "HealthMetrics" / "step_count"
    kl.mkdir(parents=True)
    (kl / "20261102.hae").write_bytes(_hae({"data": [{"qty": 100, "start": 1}, {"qty": 23, "start": 2}]}))
    (kl / "20261103.hae").write_bytes(b"yarim")
    gorulen = {}
    sinir = time.time() - 86400
    assert pt_saglik._hae_tara(tmp_path, gorulen, sinir) == {"2026-11-02": {"adim": 123}}
    assert str(kl / "20261103.hae") not in gorulen                # yarım dosya görüldü sayılmaz
    assert pt_saglik._hae_tara(tmp_path, gorulen, sinir) == {}    # değişmeyen dosya yeniden okunmaz
    (kl / "20261102.hae").write_bytes(_hae({"data": [{"qty": 500, "start": 1}]}))
    os.utime(kl / "20261102.hae", (time.time() + 5, time.time() + 5))
    assert pt_saglik._hae_tara(tmp_path, gorulen, sinir) == {"2026-11-02": {"adim": 500}}   # gün dosyası büyüyünce üstüne yazar


def test_adim_eksik_sayimi(pt_saglik):
    assert pt_saglik.adim_bilgi(8997, {"adim_eksik": 0.125}) == {"sayilan": 8997, "tahmin": 10300, "duzeltildi": True, "oran": 0.125}
    assert pt_saglik.adim_bilgi(8997, {}) == {"sayilan": 8997, "tahmin": 8997, "duzeltildi": False}   # ayar yoksa dokunulmaz
    assert pt_saglik.adim_bilgi(None, {}) is None
    assert pt_saglik.adim_bilgi(0, {"adim_eksik": 0.125}) is None
    assert pt_saglik.adim_bilgi(1000, {"adim_eksik": 0.9})["duzeltildi"] is False                     # saçma oran yok sayılır


def test_hae1_parcali_bicim(pt_saglik):
    def parca(d):
        b = _hae(d)
        return len(b).to_bytes(4, "big") + b
    ham = b"HAE1" + parca({"metric": "x", "data": []}) + parca({"metric": "x", "data": [{"qty": 1}]}) + parca({"metric": "x", "data": [{"qty": 2}]})
    assert [x["qty"] for x in pt_saglik.hae_coz(ham)["data"]] == [1, 2]
    assert pt_saglik.hae_coz(b"HAE1" + parca({"data": []})[:-3]) is None      # yarım dosya


def test_yuruyus_bulma(pt_saglik):
    import datetime as dt
    bas = dt.datetime(2026, 11, 2, 8, 50).timestamp()
    ornek = [(bas + i * 60, bas + i * 60 + 55, 70) for i in range(30)]           # 30 dk sürekli yürüyüş
    aks = dt.datetime(2026, 11, 2, 13, 0).timestamp()
    ornek += [(aks + i * 60, aks + i * 60 + 55, 70) for i in range(20)]          # gün ortası
    ev = dt.datetime(2026, 11, 2, 21, 0).timestamp()
    ornek += [(ev + i * 300, ev + i * 300 + 30, 10) for i in range(8)]           # evin içi: az adım
    W = pt_saglik.yuruyus_bul(ornek, 'Köpek gezdirme')
    assert [(w["ad"], w["dk"], w["adim"]) for w in W] == [("Köpek gezdirme", 30, 2100), ("Yürüyüş", 20, 1400)]


def test_kendi_kaydi_ile_tekrar_olmaz(pt_saglik, monkeypatch):
    import datetime as dt
    import json as j
    import pt
    t = "2026-11-02"
    monkeypatch.setattr(pt, "GUNLUK", pt.VERI / "gunluk")
    pt.GUNLUK.mkdir(parents=True, exist_ok=True)
    pt_saglik.KLASOR.mkdir(parents=True, exist_ok=True)
    W = [{"bas": 1, "bit": 2, "dk": 30, "adim": 2000, "ad": "Köpek gezdirme", "dilim": "sabah"}, {"bas": 3, "bit": 4, "dk": 50, "adim": 3000, "ad": "Köpek gezdirme", "dilim": "aksam"}]
    (pt_saglik.KLASOR / f"{t}.json").write_text(j.dumps({"tarih": t, "yuruyusler": W}))
    (pt.GUNLUK / f"{t}.json").write_text(j.dumps({"tarih": t, "seanslar": [{"bitti": True, "baslik": "Köpek gezisi", "bitis_t": dt.datetime(2026, 11, 2, 9, 36).timestamp()}]}))
    assert [w["dilim"] for w in pt_saglik.yuruyusler(t)] == ["aksam"]
