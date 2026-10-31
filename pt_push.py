"""pt_push.py - Health'in telefon bildirimleri (2026-10-25; couple_push.py'nin eşi, ayrı anahtar "pt_vapid" ve abone listesi pt/push_aboneler.json).

Ana ekrana eklenmiş Health (iOS 16.4+ web uygulaması, https: eşleşmiş tünel adresi) Web Push ile bildirim alır; izin kullanıcının dokunuşuyla istenir.
Bildirimler pt_site arka plan döngüsünden: sabah kontrolü (antrenman saatinden önce), yeme penceresinin kapanmasına 30 dk, antrenman saati,
pazar akşamı haftalık mesaj. Günde aynı türden en çok bir (pt/push_gonderilen.json).
"""
import base64
import json
import threading
import time

import pt

ABONE = pt.VERI / "push_aboneler.json"
def _iletisim():
    """VAPID `sub`: ayarlar.json `push_iletisim` (https adresi ya da mailto:); yoksa ilk e-posta (kullanıcı e-postasının push sağlayıcısına gitmesini istemezse ayara adres yazar)."""
    import ortak
    a = ortak.ayar(); e = ortak.kimlik()["epostalar"]
    return a.get("push_iletisim") or (("mailto:" + e[0]) if e else "https://example.com")
_kilit = threading.Lock()


def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _vapid():
    """Anahtar yoksa üretir ve Anahtar Zinciri'ne yazar. Döner (Vapid01, açık anahtar base64url)."""
    import gizli
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01
    ham = gizli.al("pt_vapid")
    if ham:
        v = Vapid01.from_raw(ham.strip().encode())
    else:
        v = Vapid01()
        v.generate_keys()
        ham = _b64(v.private_key.private_numbers().private_value.to_bytes(32, "big"))
        if not gizli.koy("pt_vapid", ham):
            raise RuntimeError("Bildirim anahtarı Anahtar Zinciri'ne yazılamadı.")
    acik = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return v, _b64(acik)


def acik_anahtar():
    return _vapid()[1]


def aboneler():
    return pt._json(ABONE, [])


def _yaz(L):
    pt.VERI.mkdir(parents=True, exist_ok=True)
    ABONE.write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")


def abone_ol(sub, cihaz=""):
    if not isinstance(sub, dict) or not str(sub.get("endpoint") or "").startswith("https://") or not (sub.get("keys") or {}).get("p256dh"):
        raise ValueError("Geçersiz abonelik.")
    with _kilit:
        L = [x for x in aboneler() if x["sub"]["endpoint"] != sub["endpoint"]]
        L.append({"sub": {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]}},
                  "cihaz": cihaz[:120], "zaman": time.time()})
        _yaz(L)
    return len(L)


def abonelik_sil(endpoint):
    with _kilit:
        L = [x for x in aboneler() if x["sub"]["endpoint"] != endpoint]
        _yaz(L)
    return len(L)


def gonder(baslik, metin, url="/?u=pt", etiket=""):
    """Bütün abone cihazlara; arka planda, hata akışı durdurmaz. Döner gönderilen sayısı (eşzamanlı çağrıda 0 olabilir)."""
    L = aboneler()
    if not L:
        return 0

    def kos():
        from pywebpush import WebPushException, webpush
        try:
            v, _ = _vapid()
        except Exception as e:  # noqa: BLE001
            print(f"Health bildirimi: anahtar yok ({e})", flush=True)
            return
        veri = json.dumps({"baslik": baslik[:120], "metin": metin[:300], "url": url or "/", "etiket": etiket or ""}, ensure_ascii=False)
        olu = []
        for x in L:
            try:
                webpush(subscription_info=x["sub"], data=veri, vapid_private_key=v, vapid_claims={"sub": _iletisim()}, ttl=12 * 3600, timeout=15)
            except WebPushException as e:
                kod = getattr(e.response, "status_code", 0) if getattr(e, "response", None) is not None else 0
                if kod in (404, 410):
                    olu.append(x["sub"]["endpoint"])
                else:
                    print(f"Health bildirimi gönderilemedi ({kod}): {str(e)[:160]}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"Health bildirimi gönderilemedi: {str(e)[:160]}", flush=True)
        for ep in olu:
            abonelik_sil(ep)
    threading.Thread(target=kos, daemon=True).start()
    return len(L)
