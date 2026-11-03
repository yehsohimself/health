"""Sade kahve orucu bozmaz, karar kişide; hazır seçim saatli kaydedilir (uydurma veri, sanal klasör)."""
import datetime as dt
import json
import time

import pytest


@pytest.fixture
def pb(kok, tmp_path, monkeypatch):
    import pt
    import pt_beslenme
    v = tmp_path / "pt"
    for ad, yol in (("VERI", v), ("GUNLUK", v / "gunluk"), ("PROGRAM", v / "program"), ("MESAJLAR", v / "mesajlar"), ("HAREKETLER", v / "hareketler")):
        monkeypatch.setattr(pt, ad, yol)
        yol.mkdir(parents=True, exist_ok=True)
    return pt_beslenme


KAHVE = {"ad": "Kahve", "kalemler": [{"ad": "Kahve", "kcal": 5, "miktar_g": 240}]}
YEMEK = {"ad": "Makarna", "kalemler": [{"ad": "Makarna", "kcal": 430, "miktar_g": 250}]}


def test_sade_kahve_orucu_bozmaz(pb):
    assert pb.oruc_bozar(KAHVE) is False
    assert pb.oruc_bozar(YEMEK) is True
    assert pb.oruc_bozar({**KAHVE, "oruc_bozar": True}) is True          # kişi karar verdiyse o
    assert pb.oruc_bozar({**YEMEK, "oruc_bozar": False}) is False
    assert pb.oruc_bozar({"ad": "Yazılı öğün"}) is True                  # içeriği bilinmeyen kayıt


def test_yalniz_bozanlar_sayilir(pb):
    d = {"yemekler": [{**KAHVE, "t": 100}, {**YEMEK, "t": 200}, {**KAHVE, "t": 300}]}
    assert pb.yeme_anlari(d) == [200]


def test_kahveden_sonra_oruc_suruyor(pb):
    import pt
    import pt_gidisat
    bugun = pt.bugun().isoformat()
    dun = (pt.bugun() - dt.timedelta(days=1)).isoformat()
    bas = int(time.time()) - 15 * 3600
    pb.yemek_kaydet(dun, {**YEMEK, "t": bas})
    y = pb.yemek_kaydet(bugun, {**KAHVE, "t": int(time.time()) - 60})
    s = pt_gidisat.suren_oruc()
    assert s["durum"] == "oruc" and s["bas_t"] == bas
    pb.yemek_oruc(bugun, y["id"], True)                                   # "orucu bozdu" derse biter
    assert pt_gidisat.suren_oruc()["durum"] == "yeme"
    pb.yemek_oruc(bugun, y["id"], False)
    assert pt_gidisat.suren_oruc()["durum"] == "oruc"


def test_secim_saati_ve_gunu(pb):
    import pt
    t = int(time.time()) - 86400
    y = pb.yemek_kaydet(pt.bugun().isoformat(), {**YEMEK, "secim": True, "t": t})
    assert "secim" not in y and y["t"] == t
    assert [x["id"] for x in pt.gun(dt.datetime.fromtimestamp(t).date().isoformat())["yemekler"]] == [y["id"]]
    ileri = pb.yemek_kaydet(pt.bugun().isoformat(), {**YEMEK, "secim": True, "t": int(time.time()) + 9999})
    assert ileri["t"] <= time.time() + 1


def test_sik_secilenler(pb, monkeypatch):
    import pt
    (pt.VERI / "hazir.json").write_text(json.dumps({"gruplar": [{"kod": "a", "ad": "A"}], "yemekler": [{"kod": "k", "ad": "K"}]}))
    monkeypatch.setattr(pb, "HAZIR", pt.VERI / "hazir.json")
    pb.yemek_kaydet(pt.bugun().isoformat(), {"ad": "K", "kalemler": [{"ad": "K", "hazir": "k", "adet": 1.5, "kcal": 1}]})
    r = pb.hazir_liste()
    assert r["sik"] == ["k"] and r["son_adet"] == {"k": 1.5}
