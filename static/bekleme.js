/* Asistanlar yanıt beklerken ortak görünüm (2026-11-02; BoardUI'nin Agent Thinking ve Composer Loader fikirlerinden, kendi dilimizle yeniden yazıldı).
   Üç nokta yerine: dalgalanan nokta ızgarası + parlayan durum yazısı + geçen süre; yazma kutusunun kenarında ürün renginde dönen ışık.
   Kullanım: Bekleme.basla('studio', yazmaKutusu)  ->  yanıt balonunda Bekleme.html('studio', ['Bakıyorum', 'Düşünüyorum', 'Toparlıyorum'])  ->  Bekleme.bitir('studio').
   Yazılar 0, 8, 20 ve 40. saniyede değişir; bu kadar uzun süren beklemede son yazı dürüstçe "hâlâ çalışıyorum" olur. Yeniden çizim süreyi ve dalgayı sıfırlamaz. */
window.Bekleme = (() => {
  const CSS = `
.vh-bk{display:inline-flex;align-items:center;gap:9px;max-width:100%;vertical-align:middle;line-height:1.35;font-size:14px;white-space:normal}
.vh-bk-n{flex:none;display:grid;grid-template-columns:repeat(3,4.5px);gap:2.5px}
.vh-bk-n i{display:block;width:4.5px;height:4.5px;border-radius:50%;background:color-mix(in srgb,var(--vurgu,currentColor) 72%,var(--ink,#fff));opacity:.2;animation:vhBkD 1.32s ease-in-out infinite;animation-delay:calc(var(--d,0)*110ms + var(--f,0ms))}
.vh-bk-n i:nth-child(2),.vh-bk-n i:nth-child(4){--d:1}.vh-bk-n i:nth-child(3),.vh-bk-n i:nth-child(5),.vh-bk-n i:nth-child(7){--d:2}.vh-bk-n i:nth-child(6),.vh-bk-n i:nth-child(8){--d:3}.vh-bk-n i:nth-child(9){--d:4}
.vh-bk-y{min-width:0;color:transparent;background:linear-gradient(90deg,var(--muted,var(--ink3,#8e8e98)) 30%,var(--ink,#fff) 50%,var(--muted,var(--ink3,#8e8e98)) 70%);background-size:240% 100%;-webkit-background-clip:text;background-clip:text;animation:vhBkP 2.6s linear infinite;animation-delay:var(--f,0ms)}
.vh-bk-s{flex:none;color:var(--muted,var(--ink3,#8e8e98));font-size:12.5px;font-variant-numeric:tabular-nums;opacity:.8}
.vh-bk-s:empty{display:none}
.vh-isik{position:absolute;inset:0;z-index:1;display:block;overflow:hidden;pointer-events:none;opacity:0;transition:opacity .45s ease}
.vh-isik.acik{opacity:1}
.vh-isik svg{display:block;width:100%;height:100%;overflow:visible}
.vh-isik rect{fill:none;stroke-linecap:round;animation:vhBkI 3.8s linear infinite}
#asMesaj,#mMesajlar,#gsAkis,#shAkis,#sakis,#sAkis,#mesajlar,#sb,#sbMesajlar{-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 var(--vh-sol,0px));mask-image:linear-gradient(to bottom,transparent 0,#000 var(--vh-sol,0px))}
.vh-satirlar{list-style:none;margin:0;padding:0;display:flex;flex-direction:column}
.vh-satir{position:relative;padding:0 0 12px 22px;font-size:14px;line-height:1.4;color:var(--muted,var(--ink3,#8e8e98))}
.vh-satir:last-child{padding-bottom:0}
.vh-satir::before{content:"";position:absolute;left:3px;top:6px;width:7px;height:7px;border-radius:50%;background:var(--muted,var(--ink3,#8e8e98));opacity:.55}
.vh-satir:not(:last-child)::after{content:"";position:absolute;left:6px;top:17px;bottom:-1px;border-left:1px solid var(--hair2,var(--cizgi2,rgba(128,128,128,.3)));transform-origin:top}
.vh-satir.son{color:var(--ink,inherit)}.vh-satir.son::before{background:var(--vurgu,currentColor);opacity:1;box-shadow:0 0 0 4px color-mix(in srgb,var(--vurgu,#5b7cf5) 22%,transparent);animation:vhBkN 1.6s ease-in-out infinite}
.vh-satir.yeni{animation:vhBkG .42s cubic-bezier(.22,1,.36,1) both}.vh-satir.yeni::after{animation:vhBkC .5s cubic-bezier(.22,1,.36,1) both}
@keyframes vhBkG{from{opacity:0;transform:translateY(4px);filter:blur(5px)}}
@keyframes vhBkC{from{transform:scaleY(0)}}
@keyframes vhBkN{50%{box-shadow:0 0 0 7px color-mix(in srgb,var(--vurgu,#5b7cf5) 8%,transparent)}}
@keyframes vhBkD{0%,62%,100%{opacity:.2;transform:scale(.82)}24%{opacity:1;transform:scale(1.08)}}
@keyframes vhBkP{from{background-position:120% 0}to{background-position:-120% 0}}
@keyframes vhBkI{from{stroke-dashoffset:0}to{stroke-dashoffset:-100}}
@media (prefers-reduced-motion:reduce){.vh-bk-n i{animation:none;opacity:.55;transform:none}.vh-bk-y{animation:none;color:var(--muted,var(--ink3,#8e8e98));background:none}
  .vh-isik rect{animation:none;stroke-dasharray:none}.vh-isik .vh-i1,.vh-isik .vh-i2{display:none}.vh-isik .vh-i3{stroke-width:2;opacity:.7}.vh-satir,.vh-satir::before,.vh-satir::after{animation:none!important}}`;
  const st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);

  const ESIK = [0, 8, 20, 40];
  const en = () => (document.documentElement.lang || '').toLowerCase().startsWith('en');
  const UZUN = () => en() ? 'This is taking a while; still working' : 'Biraz uzun sürdü; hâlâ çalışıyorum';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const BAS = {}, ISIK = {}; let say = 0, T = 0;

  function sure(ms){ const n = Math.floor(ms / 1000); if (n < 3) return '';
    const d = Math.floor(n / 60), s = n % 60;
    return en() ? (d ? `${d}m ${s}s` : `${s}s`) : (d ? `${d} dk ${s} sn` : `${s} sn`); }
  // dört yazıdan az verildiyse 40. saniyede "uzun sürdü" cümlesi gelir; aradaki eşiklerde son verilen yazı kalır
  function yazi(ms, L){ const n = ms / 1000; if (L.length < ESIK.length && n >= 40) return UZUN();
    return L[Math.min(ESIK.filter(e => n >= e).length, L.length) - 1] || ''; }

  function tik(){ const G = document.querySelectorAll('.vh-bk'); if (!G.length){ clearInterval(T); T = 0; return; }
    G.forEach(el => { const ms = Date.now() - Number(el.dataset.bas);
      const s = el.querySelector('.vh-bk-s'), yeni = sure(ms); if (s && s.dataset.d !== yeni){ s.dataset.d = yeni; s.textContent = yeni; }
      let L = []; try{ L = JSON.parse(el.dataset.e || '[]'); }catch(_){}
      const y = el.querySelector('.vh-bk-y'), m = yazi(ms, L); if (y && y.dataset.d !== m){ y.dataset.d = m; y.textContent = m; } }); }

  function html(k, E){ const L = [].concat(E), bas = BAS[k] || (BAS[k] = Date.now()), ms = Date.now() - bas, m = yazi(ms, L), s = sure(ms);
    if (!T) T = setInterval(tik, 500);
    return `<span class="vh-bk" role="status" data-bas="${bas}" data-e="${esc(JSON.stringify(L))}" style="--f:-${ms % 15840}ms"><span class="vh-bk-n" aria-hidden="true">${'<i></i>'.repeat(9)}</span><span class="vh-bk-y" data-d="${esc(m)}">${esc(m)}</span><span class="vh-bk-s" aria-hidden="true" data-d="${esc(s)}">${esc(s)}</span></span>`; }

  function isikKur(k, el){ if (!el || ISIK[k]) return;
    const alan = /^(TEXTAREA|INPUT)$/.test(el.tagName), kap = alan ? el.parentElement : el, cs = getComputedStyle(el);
    if (getComputedStyle(kap).position === 'static') kap.style.position = 'relative';
    const r = parseFloat(cs.borderTopLeftRadius) || 12, kn = parseFloat(cs.borderTopWidth) || 0, n = ++say, ic = `<defs><linearGradient id="vhG${n}"><stop offset="0" style="stop-color:var(--vurgu,#5b7cf5)"/><stop offset=".5" style="stop-color:color-mix(in srgb,var(--vurgu,#5b7cf5) 55%,#fff)"/><stop offset="1" style="stop-color:var(--vurgu,#5b7cf5)"/></linearGradient>
      <filter id="vhB${n}" x="-20%" y="-80%" width="140%" height="260%"><feGaussianBlur stdDeviation="9"/></filter><filter id="vhC${n}" x="-20%" y="-80%" width="140%" height="260%"><feGaussianBlur stdDeviation="2.6"/></filter></defs>`;
    // tepe keskin çizgide; yumuşak katmanlar kısa olduğu için onun gerisinden gelir. SVG süzgeci: iPhone CSS süzgecini SVG parçasında yok sayıyor.
    const dik = (s, g, d, ek) => `<rect class="${s}" width="100%" height="100%" rx="${r}" pathLength="100" stroke="url(#vhG${n})" stroke-width="${g}" stroke-dasharray="${d} ${100 - d}" ${ek}/>`;
    const s = document.createElement('span'); s.className = 'vh-isik'; s.setAttribute('aria-hidden', 'true'); s.style.borderRadius = r + 'px';
    s.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg">${ic}${dik('vh-i1', 26, 25, `filter="url(#vhB${n})" opacity=".3"`)}${dik('vh-i2', 7, 29, `filter="url(#vhC${n})" opacity=".75"`)}${dik('vh-i3', 3, 32, '')}</svg>`;
    const yer = () => { if (alan){ s.style.inset = 'auto'; s.style.left = el.offsetLeft + 'px'; s.style.top = el.offsetTop + 'px'; s.style.width = el.offsetWidth + 'px'; s.style.height = el.offsetHeight + 'px'; } else s.style.inset = `-${kn}px`; };
    yer(); kap.appendChild(s); void s.offsetWidth; s.classList.add('acik');
    const g = alan && window.ResizeObserver ? new ResizeObserver(yer) : null; if (g) g.observe(el);
    ISIK[k] = {s, g}; }

  function basla(k, el){ BAS[k] = Date.now(); isikKur(k, el); }
  function bitir(k){ delete BAS[k]; const i = ISIK[k]; if (!i) return; delete ISIK[k]; if (i.g) i.g.disconnect(); i.s.classList.remove('acik'); setTimeout(() => i.s.remove(), 500); }

  // sohbet yukarı kayınca yazı başlığın altında keskin kesilmesin: solma kaydırma miktarıyla büyür, en üstte hiç yoktur
  const SOL = '#asMesaj,#mMesajlar,#gsAkis,#shAkis,#sakis,#sAkis,#mesajlar,#sb,#sbMesajlar';
  document.addEventListener('scroll', e => { const k = e.target; if (k && k.matches && k.matches(SOL)) k.style.setProperty('--vh-sol', Math.min(k.scrollTop, 30) + 'px'); }, true);

  // akan iş kaydı: yalnız yeni gelen satır belirir, yanındaki çizgi kendini çizer; son satır süren iştir
  const GORULEN = {};
  function satirlar(k, L, surer = true){ const once = GORULEN[k] || 0; GORULEN[k] = L.length;
    return `<ol class="vh-satirlar">${L.map((m, i) => `<li class="vh-satir${i >= once ? ' yeni' : ''}${surer && i === L.length - 1 ? ' son' : ''}">${m && m.u && /^https?:/.test(m.u) ? `<a href="${esc(m.u)}" target="_blank" rel="noopener" style="color:inherit">${esc(m.m)}</a>` : esc(m && m.m || m)}</li>`).join('')}</ol>`; }

  // yuvarlanan sayı: data-yuvarla="anahtar" taşıyan öğe, değeri önceki görülenden farklıysa oraya kısa hareketle gelir; yazının biçimi korunur
  const SAYI = /-?\d[\d.,]*/;
  function coz(s){ const m = SAYI.exec(s); if (!m) return null; const h = m[0], o = /[.,](\d{1,2})$/.exec(h), g = o ? h.slice(0, -o[0].length) : h, bin = (/[.,]/.exec(g) || [''])[0];
    const b = o ? o[1].length : 0; return {h, d: b, ond: o ? o[0][0] : '', bin, n: Number(h.replace(/[^\d-]/g, ''))}; }
  function yaz(c, n){ const e = n < 0 ? '-' : '', y = String(Math.abs(n)).padStart(c.d + 1, '0'), t = c.d ? y.slice(0, -c.d) : y, o = c.d ? c.ond + y.slice(-c.d) : '';
    return e + (c.bin ? t.replace(/\B(?=(\d{3})+(?!\d))/g, c.bin) : t) + o; }
  function yuvarla(el){ const a = 'vhSayi_' + el.dataset.yuvarla, son = el.textContent, c = coz(son); if (!c) return; let eski = null;
    try{ eski = localStorage.getItem(a); if (eski !== String(c.n)) localStorage.setItem(a, c.n); }catch(_){}
    if (eski === null || eski === String(c.n) || matchMedia('(prefers-reduced-motion:reduce)').matches) return;
    const once = Number(eski), t0 = performance.now(), SURE = 700;
    const adim = () => { if (!el.isConnected) return; const p = Math.min(1, (performance.now() - t0) / SURE), v = 1 - Math.pow(1 - p, 3);
      if (p >= 1){ el.textContent = son; return; } el.textContent = son.replace(c.h, yaz(c, Math.round(once + (c.n - once) * v))); setTimeout(adim, 33); };
    adim(); }
  const tara = k => { if (k.nodeType !== 1) return; if (k.dataset && k.dataset.yuvarla) yuvarla(k); if (k.querySelectorAll) k.querySelectorAll('[data-yuvarla]').forEach(yuvarla); };
  new MutationObserver(L => L.forEach(m => m.addedNodes.forEach(tara))).observe(document.documentElement, {childList: true, subtree: true});

  return {basla, bitir, html, satirlar};
})();
