"""The standalone server opens Health and answers its API."""


def test_ana_sayfa_pt(istemci):
    r = istemci.get("/")
    assert r.status_code == 200 and b'data-urunler="pt"' in r.data


def test_api_ozet_ve_katalog(istemci):
    assert istemci.get("/api/pt").status_code == 200
    k = istemci.get("/api/pt/katalog")
    assert k.status_code == 200 and k.get_json()


def test_mesgul(istemci):
    assert istemci.get("/api/mesgul").get_json()["mesgul"] is False
