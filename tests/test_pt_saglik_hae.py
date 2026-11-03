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
