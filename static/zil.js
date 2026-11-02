/* Bildirim zili (2026-11-02): her ürünün üst çubuğunda; Mac bildirimi kaçırılsa da burada kalır. Veri /api/bildirimler (bildirimler.py).
   Uç yoksa ya da erişim kapalıysa (davetli, tek başına kurulum) zil hiç görünmez. */
(() => {
  const kok = document.documentElement, urunH = kok.dataset.urun === 'capital' ? 'ledger' : (kok.dataset.urun || '');
  const en = () => (kok.lang || '').toLowerCase().startsWith('en');
  const Y = k => (en() ? {b: 'Notifications', u: 'This product', t: 'All', bos: 'Nothing yet. When a recording starts or something is ready, it stays here.', az: 'just now', dk: 'min ago', sa: 'h ago', dun: 'Yesterday'}
    : {b: 'Bildirimler', u: 'Bu ürün', t: 'Tümü', bos: 'Henüz bildirim yok. Bir kayıt başlayınca ya da bir iş bitince burada kalır.', az: 'az önce', dk: 'dk önce', sa: 'sa önce', dun: 'Dün'})[k];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const LOGO = {transcript: 'transcript', note: 'note', ghost: 'ghost', content: 'content', pt: 'pt', ledger: 'ledger', office: 'office'};
  const st = document.createElement('style'); st.textContent = `
.vh-zil{position:relative}.vh-zil svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.vh-zil-s{position:absolute;top:-3px;right:-3px;min-width:16px;height:16px;padding:0 4px;border-radius:9px;background:var(--vurgu,#5b7cf5);color:var(--vurgu-ink,#fff);font:700 10px/16px var(--sans,inherit);text-align:center;font-variant-numeric:tabular-nums;box-shadow:0 0 0 2px var(--bg,#111)}
.vh-zil-s[hidden]{display:none}
.vh-zilp{position:fixed;z-index:95;top:60px;right:16px;width:min(380px,calc(100vw - 24px));max-height:min(70vh,560px);display:flex;flex-direction:column;overflow:hidden;border-radius:18px;border:1px solid var(--hair2,var(--cizgi2,rgba(128,128,128,.25)));background:var(--surface,var(--yuzey,var(--kart,#16161a)));color:var(--ink,inherit);box-shadow:0 24px 60px -18px rgba(0,0,0,.55);animation:vhZilA .18s ease-out}
@keyframes vhZilA{from{opacity:0;transform:translateY(-6px)}}
.vh-zilp header{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid var(--hair,var(--cizgi,rgba(128,128,128,.18)))}
.vh-zilp header b{flex:1;font-size:15px}
.vh-zilp header button{border:0;background:none;color:var(--muted,var(--ink3,#8e8e98));font:inherit;font-size:13px;padding:4px 10px;border-radius:99px;cursor:pointer}
.vh-zilp header button.on{background:var(--surface2,var(--yuzey2,rgba(128,128,128,.15)));color:var(--ink,inherit)}
.vh-zilp ul{list-style:none;margin:0;padding:4px;overflow:auto;flex:1}
.vh-zilp li button{display:grid;grid-template-columns:auto 1fr auto;gap:2px 10px;width:100%;text-align:left;border:0;background:none;color:inherit;font:inherit;padding:10px;border-radius:12px;cursor:pointer}
.vh-zilp li button:hover,.vh-zilp li button:focus-visible{background:var(--surface2,var(--yuzey2,rgba(128,128,128,.12)));outline:none}
.vh-zilp .i{grid-row:1/3;width:22px;height:22px;margin-top:1px;border-radius:6px;display:block}
.vh-zilp .n{grid-row:1/3;width:7px;height:7px;margin:7px 7px 0 8px;border-radius:50%;background:transparent}
.vh-zilp .yeni .n{background:var(--vurgu,#5b7cf5)}
.vh-zilp .a{font-size:14px;font-weight:600;line-height:1.35;min-width:0}
.vh-zilp .z{font-size:12px;color:var(--muted,var(--ink3,#8e8e98));white-space:nowrap;padding-top:1px}
.vh-zilp .m{grid-column:2/4;font-size:13px;line-height:1.4;color:var(--muted,var(--ink3,#8e8e98));display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
.vh-zilp .bos{padding:30px 22px;text-align:center;color:var(--muted,var(--ink3,#8e8e98));font-size:14px;line-height:1.5}
@media (max-width:520px){.vh-zilp{left:12px;right:12px;width:auto}}
@media (prefers-reduced-motion:reduce){.vh-zilp{animation:none}}`; document.head.appendChild(st);

  function zaman(t){ const f = Date.now() / 1000 - t; if (f < 90) return Y('az'); if (f < 3600) return `${Math.round(f / 60)} ${Y('dk')}`;
    const d = new Date(t * 1000), bu = new Date(), s = d.toLocaleTimeString(en() ? 'en-GB' : 'tr-TR', {hour: '2-digit', minute: '2-digit'});
    if (d.toDateString() === bu.toDateString()) return f < 6 * 3600 ? `${Math.round(f / 3600)} ${Y('sa')}` : s;
    const dun = new Date(bu); dun.setDate(bu.getDate() - 1); if (d.toDateString() === dun.toDateString()) return `${Y('dun')} ${s}`;
    return d.toLocaleDateString(en() ? 'en-GB' : 'tr-TR', {day: 'numeric', month: 'short'}); }
  // kayıtlı adres bu Mac'in adresidir; site başka adresten (ev ağı, tünel) açıksa ona çevrilir
  function adres(u){ try{ const a = new URL(u, location.href); if (!/^https?:$/.test(a.protocol)) return ''; if (/^(127\.0\.0\.1|localhost)$/.test(a.hostname) && a.hostname !== location.hostname){
        if (location.protocol === 'https:') return a.pathname + a.search + a.hash; a.hostname = location.hostname; } return a.href; }catch(_){ return ''; } }

  let b, sayac, pan = null, kapsam = urunH;
  async function say(){ if (document.hidden) return; try{ const r = await fetch(`/api/bildirimler?urun=${urunH}&yalniz_sayi=1`); if (!r.ok) return; const j = await r.json();
      sayac.hidden = !j.okunmamis; sayac.textContent = j.okunmamis > 99 ? '99+' : j.okunmamis; }catch(_){} }
  function kapat(){ if (pan){ pan.remove(); pan = null; document.removeEventListener('pointerdown', dis, true); document.removeEventListener('keydown', tus); b.setAttribute('aria-expanded', 'false'); } }
  const dis = e => { if (pan && !pan.contains(e.target) && !b.contains(e.target)) kapat(); };
  const tus = e => { if (e.key === 'Escape') kapat(); };
  async function ciz(){ if (!pan) return; const r = await fetch('/api/bildirimler?urun=' + kapsam).catch(() => null); if (!pan || !r || !r.ok) return; const j = await r.json();
    pan.querySelector('header').innerHTML = `<b>${Y('b')}</b><button type="button" data-k="${urunH}" class="${kapsam ? 'on' : ''}">${Y('u')}</button><button type="button" data-k="" class="${kapsam ? '' : 'on'}">${Y('t')}</button>`;
    pan.querySelector('ul').innerHTML = j.liste.length ? j.liste.map(x => { const L = LOGO[x.urun];
      return `<li class="${x.yeni ? 'yeni' : ''}"><button type="button" data-u="${esc(adres(x.url))}">${!kapsam && L ? `<img class="i" src="/static/logo/${L}.svg" alt="">` : '<span class="n"></span>'}<span class="a">${esc(x.baslik)}</span><span class="z">${esc(zaman(x.t))}</span>${x.metin ? `<span class="m">${esc(x.metin)}</span>` : ''}</button></li>`; }).join('') : `<li class="bos">${Y('bos')}</li>`;
    fetch('/api/bildirimler/okundu', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({urun: kapsam})}).then(() => { if (kapsam) sayac.hidden = true; else say(); }).catch(() => {}); }
  function ac(){ if (pan) return kapat(); kapsam = urunH; pan = document.createElement('div'); pan.className = 'vh-zilp'; pan.setAttribute('role', 'dialog'); pan.setAttribute('aria-label', Y('b'));
    pan.innerHTML = `<header><b>${Y('b')}</b></header><ul></ul>`; const k = b.getBoundingClientRect(); pan.style.top = Math.round(k.bottom + 8) + 'px'; document.body.appendChild(pan); b.setAttribute('aria-expanded', 'true');
    pan.addEventListener('click', e => { const s = e.target.closest('[data-k]'); if (s){ kapsam = s.dataset.k; ciz(); return; }
      const g = e.target.closest('[data-u]'); if (!g || !g.dataset.u) return; const a = new URL(g.dataset.u, location.href); kapat();
      if (a.origin === location.origin){ if (a.pathname === location.pathname && a.hash){ location.hash = a.hash; } else location.href = a.href; } else window.open(a.href, '_blank', 'noopener'); });
    document.addEventListener('pointerdown', dis, true); document.addEventListener('keydown', tus); ciz(); }

  async function kur(){ if (!urunH) return; const r = await fetch(`/api/bildirimler?urun=${urunH}&yalniz_sayi=1`).catch(() => null); if (!r || !r.ok) return;
    const ref = document.querySelector('#ayarBtn') || [...document.querySelectorAll('.navsag > button')].pop(); if (!ref) return;
    b = document.createElement('button'); b.type = 'button'; const es = ref.parentElement.querySelector('button.navbtn, button.nbtn, button.tema, button.yuvarlak') || ref;   // ürünün sade düğmesiyle aynı görünsün (hesap ve vurgulu düğmeler değil)
    b.className = es.className.replace(/\b(vurgu|hidden|acik)\b/g, '') + ' vh-zil'; b.setAttribute('aria-label', Y('b')); b.title = Y('b'); b.setAttribute('aria-haspopup', 'dialog');
    b.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9a6 6 0 0 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9"/><path d="M10 19a2 2 0 0 0 4 0"/></svg><span class="vh-zil-s" hidden></span>';
    ref.before(b); sayac = b.querySelector('.vh-zil-s'); b.addEventListener('click', ac);
    const j = await r.json(); sayac.hidden = !j.okunmamis; sayac.textContent = j.okunmamis > 99 ? '99+' : j.okunmamis;
    setInterval(say, 60000); document.addEventListener('visibilitychange', say); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', kur); else kur();
})();
