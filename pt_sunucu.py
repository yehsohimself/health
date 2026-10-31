"""pt_sunucu.py - Health'i tek başına çalıştırır (2026-10-29; ayrı depo `yehsohimself/health` için). Video Hub'ın ortak sunucusu yoksa bunu kullanın:

    .venv/bin/python pt_sunucu.py            http://127.0.0.1:8771

Yalnız bu Mac'ten erişilir (127.0.0.1). Uçlar pt_site.kaydet(app) ile aynı; sayfa static/pt.html. Ortak sunucuda (site.py) bu dosya kullanılmaz.
"""
import os
import sys
from pathlib import Path

from flask import Flask, make_response

KLASOR = Path(__file__).resolve().parent
sys.path.insert(0, str(KLASOR))

import pt_site  # noqa: E402

app = Flask(__name__, static_folder=str(KLASOR / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024


@app.get("/")
def ana():
    html = (KLASOR / "static" / "pt.html").read_text(encoding="utf-8")
    html = html.replace("<html", '<html data-urun="pt" data-urunler="pt"', 1)
    r = make_response(html)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/api/mesgul")
def mesgul():
    n = pt_site.mesgul()
    return {"mesgul": bool(n), "nedenler": n}


@app.before_request
def _kaynak_kapisi():
    """Başka bir sitenin tarayıcı üzerinden bu sunucuya yazmasını engeller (ortak sunucudaki 00_baslangic._kaynak_kapisi'nin eşi)."""
    from flask import request
    host = (request.host or "").split(":")[0]
    if host not in ("127.0.0.1", "localhost", "::1", "[::1]"):
        return {"hata": "Bu adres kabul edilmiyor."}, 403
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        koken = request.headers.get("Origin")
        if request.headers.get("Sec-Fetch-Site") == "cross-site" or (koken and koken.split("://")[-1].split(":")[0] not in ("127.0.0.1", "localhost")):
            return {"hata": "Başka bir siteden gelen istek."}, 403


@app.errorhandler(Exception)
def _hata(e):
    from flask import request
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    if not request.path.startswith("/api/"):
        raise e
    if isinstance(e, (ValueError, TypeError, KeyError)):
        return {"hata": str(e)[:300] or "Geçersiz istek."}, 400
    import traceback
    traceback.print_exc()
    return {"hata": "Beklenmeyen bir hata oldu."}, 500


@app.after_request
def _guvenlik(r):
    r.headers.setdefault("X-Content-Type-Options", "nosniff")
    r.headers.setdefault("Referrer-Policy", "same-origin")
    return r


pt_site.kaydet(app)

if __name__ == "__main__":
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else int(os.environ.get("PT_PORT", "8771"))
    print(f"Health: http://127.0.0.1:{port}", flush=True)
    app.run(host="127.0.0.1", port=port, threaded=True)
