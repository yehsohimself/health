/* Health çevrimdışı çalışanı (2026-10-25). Parkta bağlantı yoksa: sayfa ve son veriler önbellekten, hareket videoları telefonda.
   Yalnızca güvenli adreste (eşleşmiş telefonun https tünel adresi ya da localhost) çalışır. Videolar Safari'nin istediği aralık isteklerine (Range) önbellekten dilimlenerek
   yanıtlanır. API: önce ağ, olmazsa son yanıt. Kayıtlar (POST) sayfadaki kuyrukta bekler, burada tutulmaz. */
const SURUM = 'pt-v3', SAYFA = 'pt-sayfa-' + SURUM, VIDEO = 'pt-video', VERI = 'pt-veri';
const KABUK = ['/static/logo/pt.svg', '/static/pt.webmanifest'];

self.addEventListener('install', e => { e.waitUntil(caches.open(SAYFA).then(c => Promise.all(KABUK.map(u => c.add(u).catch(() => null)))).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(L => Promise.all(L.filter(k => k.startsWith('pt-sayfa-') && k !== SAYFA).map(k => caches.delete(k)))).then(() => self.clients.claim())); });

self.addEventListener('message', e => {
  if (e.data && e.data.tur === 'onbellek') e.waitUntil(caches.open(VIDEO).then(async c => {
    /* anahtar sorgusuz adres: fetch tarafı da öyle arar (2026-10-28: ?t= ile saklanıp sorgusuz arandığı için hiç bulunmuyordu) */
    for (const u of e.data.adresler || []){ if (!u) continue; const x = new URL(u, self.location.origin), anahtar = x.origin + x.pathname;
      if (!(await c.match(anahtar))){ try{ const r = await fetch(x.href); if (r.ok && r.status === 200) await c.put(anahtar, r); }catch(_){ /* çevrimdışı */ } } }
  }));
});

async function dilimle(istek, yanit){
  const aralik = istek.headers.get('range'); if (!aralik) return yanit;
  const b = await yanit.arrayBuffer(), m = /bytes=(\d*)-(\d*)/.exec(aralik); const bas = m && m[1] ? +m[1] : 0, son = m && m[2] ? +m[2] : b.byteLength - 1;
  return new Response(b.slice(bas, son + 1), {status: 206, headers: {'Content-Type': yanit.headers.get('Content-Type') || 'video/mp4',
    'Content-Range': `bytes ${bas}-${son}/${b.byteLength}`, 'Content-Length': String(son - bas + 1), 'Accept-Ranges': 'bytes'}});
}

self.addEventListener('fetch', e => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== 'GET') return;
  if (u.pathname.startsWith('/pt-hareket/') || u.pathname.startsWith('/pt-medya/') || u.pathname.startsWith('/pt-ses/') || u.pathname.startsWith('/pt-kas/')){
    e.respondWith(caches.open(VIDEO).then(async c => { const tam = u.origin + u.pathname; const v = await c.match(tam);
      if (v) return dilimle(r, v.clone());
      try{ return await fetch(r); }catch(_){ return new Response('', {status: 504}); } }));
    return;
  }
  if (u.pathname.startsWith('/api/pt')){
    e.respondWith(fetch(r).then(y => { if (y.ok){ const k = y.clone(); caches.open(VERI).then(c => c.put(r, k)); } return y; })
      .catch(() => caches.open(VERI).then(c => c.match(r)).then(y => y || new Response(JSON.stringify({hata: 'Bağlantı yok'}), {status: 503, headers: {'Content-Type': 'application/json'}}))));
    return;
  }
  if (u.pathname === '/' || u.pathname.startsWith('/static/') || u.hostname === 'cdnjs.cloudflare.com' || u.hostname.endsWith('gstatic.com') || u.hostname === 'fonts.googleapis.com'){
    e.respondWith(fetch(r).then(y => { if (y.ok || y.type === 'opaque'){ const k = y.clone(); caches.open(SAYFA).then(c => c.put(r, k)); } return y; })
      .catch(() => caches.match(r)));
  }
});

/* telefon bildirimleri (pt_push). Tünel adresinde aynı kökü paylaşan Couple bildirimleri de gösterilsin diye başlık/simge veriden. */
self.addEventListener('push', e => {
  let v = {};
  try { v = e.data ? e.data.json() : {}; } catch (er) { v = {baslik: 'Health', metin: e.data ? e.data.text() : ''}; }
  const couple = String(v.etiket || '').startsWith('couple');
  e.waitUntil(self.registration.showNotification(v.baslik || 'Health', {body: v.metin || '', icon: couple ? '/static/couple-ikon-192.png' : '/static/pt-ikon-192.png',
    tag: v.etiket || undefined, data: {url: v.url || '/?u=pt'}}));
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  const hedef = new URL((e.notification.data || {}).url || '/?u=pt', self.location.origin).href;
  e.waitUntil((async () => { const L = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    for (const c of L){ if ('focus' in c){ await c.focus(); if ('navigate' in c) return c.navigate(hedef); return; } }
    return self.clients.openWindow(hedef); })());
});
