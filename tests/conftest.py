"""PT test setup: the code is copied into a temporary folder and the server is loaded from pt_sunucu.py; your own pt/ data is never touched."""
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

GERCEK_KOK = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def kok(tmp_path_factory):
    k = tmp_path_factory.mktemp("pt")
    for py in GERCEK_KOK.glob("*.py"):
        shutil.copy(py, k / py.name)
    shutil.copytree(GERCEK_KOK / "static", k / "static")
    for d in ("pt", "kayitlar", "pt_medya"):
        (k / d).mkdir()
    for f in (GERCEK_KOK / "pt_medya").glob("*.json"):
        shutil.copy(f, k / "pt_medya" / f.name)
    (k / "ayarlar.json").write_text(json.dumps({"claude": False}), encoding="utf-8")
    os.environ["VH_TEST"] = "1"
    sys.path.insert(0, str(k))
    for m in [m for m in list(sys.modules) if m in ("gizli", "claude_yaz", "ortak", "pt") or m.startswith("pt_")]:
        del sys.modules[m]
    import gizli                                           # Keychain replaced by a dictionary
    _sahte = {}
    gizli.al = lambda ad: _sahte.get(ad, "")
    gizli.koy = lambda ad, deger: (_sahte.__setitem__(ad, deger) or True)
    import claude_yaz                                      # no Claude program during tests
    claude_yaz.program = lambda: None
    claude_yaz.durum = lambda zorla=False: {"program": False, "giris": False, "kullanim": False}
    return k


@pytest.fixture(scope="session")
def site(kok):
    spec = importlib.util.spec_from_file_location("pt_sunucu", kok / "pt_sunucu.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pt_sunucu"] = mod
    spec.loader.exec_module(mod)
    mod.app.config["TESTING"] = True
    return mod


@pytest.fixture
def istemci(site):
    return site.app.test_client()
