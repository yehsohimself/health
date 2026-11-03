/* pt_hazir.js — "Ne yedim, ne içtim?" (2026-11-03; kullanıcı: "Ben yediklerimi seçsem. Bir tabak makarna, bir bardak kahve, bir buçuk kahve. Hazır seçenekler bol bol olsa.
   Orucun devam edip etmemesi de benim kontrolümde olsa."). Değerler BLS 4.0'dan (/api/pt/hazir); yapay zekâ çağrılmaz. Listede olmayan için eski yazma/fotoğraf sayfası. */
(() => {
'use strict';
let veri = null;
const kucuk = s => String(s).toLocaleLowerCase('tr');
const adetYaz = a => { const t = Math.floor(a), y = a - t > .01; return t ? `${t}${y ? '½' : ''}` : '½'; };
const kc = (x, a) => Math.round(x.g * a * (x.yuz.kcal || 0) / 100);
const pr = (x, a) => Math.round(x.g * a * (x.yuz.protein || 0) / 10) / 10;

window.hazirSayfa = async function(){
  const p = sayfa(`<h3>Ne yediniz, ne içtiniz?</h3><div class="satir gri"><span class="donen"></span> Liste geliyor</div>`, {sabit: true});
  try{ veri = veri && Date.now() - veri._t < 60000 ? veri : {...await api('/api/pt/hazir'), _t: Date.now()}; }catch(e){ p.kapat(); toast(e.message); return; }
  if (!(veri.yemekler || []).length){ p.kapat(); yemekSayfa(); return; }
  const Y = {}; veri.yemekler.forEach(x => Y[x.kod] = x);
  const sik = (veri.sik || []).filter(k => Y[k]);
  const GR = (sik.length ? [{kod: 'sik', ad: 'Sık seçtikleriniz'}] : []).concat(veri.gruplar);
  const secim = new Map();
  let grup = GR[0].kod, ara = '', zaman = 0, saat = '', orucElle = null;
  const ku = $('.sayfa', p);
  ku.classList.add('hz');
  ku.innerHTML = `<div class="tutac"></div><button class="kapatx" data-kapat aria-label="Kapat">×</button><h3>Ne yediniz, ne içtiniz?</h3>
    <input class="alan hz-ara" id="hzAra" placeholder="Ara: makarna, kahve, döner…" autocomplete="off">
    <div class="hz-gr" id="hzGr">${GR.map(g => `<button data-g="${g.kod}">${esc(g.ad)}</button>`).join('')}</div>
    <div class="hz-l" id="hzL"></div>
    <button class="metin hz-yok" id="hzYok">Listede yok: yazarak ya da fotoğrafla ekleyin</button>
    <div class="hz-tepsi" id="hzT"></div>`;
  $$('[data-kapat]', ku).forEach(b => b.onclick = () => p.kapat());
  const liste = () => {
    const q = kucuk(ara.trim());
    const L = q ? veri.yemekler.filter(x => kucuk(x.ad).includes(q)) : grup === 'sik' ? sik.map(k => Y[k]) : veri.yemekler.filter(x => x.grup === grup);
    $$('#hzGr button', ku).forEach(b => b.classList.toggle('on', !q && b.dataset.g === grup));
    $('#hzL', ku).innerHTML = L.map(x => { const a = secim.get(x.kod);
      return `<div class="hz-s ${a ? 'on' : ''}" data-k="${x.kod}"><button class="hz-e" data-ekle="${x.kod}"><b>${esc(x.ad)}</b><small>1 ${esc(x.birim)} · ${kc(x, 1)} kcal</small></button>
        ${a ? `<span class="hz-ad"><button data-az="${x.kod}" aria-label="Azalt">−</button><b>${adetYaz(a)} ${esc(x.birim)}</b><button data-cok="${x.kod}" aria-label="Artır">+</button></span>` : '<span class="hz-art">+</span>'}</div>`; }).join('') || `<p class="gri2" style="font-size:14px;margin:14px 0">"${esc(ara)}" listede yok. Aşağıdan yazarak ekleyebilirsiniz.</p>`;
    $$('[data-ekle]', ku).forEach(b => b.onclick = () => { const k = b.dataset.ekle; if (secim.has(k)) secim.delete(k); else secim.set(k, 1); ciz(); });
    $$('[data-cok]', ku).forEach(b => b.onclick = () => { secim.set(b.dataset.cok, secim.get(b.dataset.cok) + .5); ciz(); });
    $$('[data-az]', ku).forEach(b => b.onclick = () => { const k = b.dataset.az, a = secim.get(k) - .5; if (a <= 0) secim.delete(k); else secim.set(k, a); ciz(); });
  };
  const kcalTop = () => [...secim].reduce((t, [k, a]) => t + kc(Y[k], a), 0);
  const bozarMi = () => orucElle !== null ? orucElle : kcalTop() >= (veri.oruc_kcal || 15);
  const tepsi = () => { const T = $('#hzT', ku);
    if (!secim.size){ T.innerHTML = ''; T.hidden = true; return; }
    T.hidden = false;
    const prot = [...secim].reduce((t, [k, a]) => t + pr(Y[k], a), 0);
    T.innerHTML = `<p class="hz-oz">${[...secim].map(([k, a]) => `${adetYaz(a)} ${esc(Y[k].birim)} ${esc(kucuk(Y[k].ad))}`).join(', ')}</p>
      <div class="hz-t"><b>${kcalTop()} kcal</b><span>${Math.round(prot)} g protein</span></div>
      <div class="hz-sat"><span>Ne zaman</span><div class="hz-c">${[[0, 'Şimdi'], [30, '30 dk önce'], [60, '1 sa önce'], [120, '2 sa önce']].map(([d, a]) => `<button data-z="${d}" class="${!saat && zaman === d ? 'on' : ''}">${a}</button>`).join('')}<input type="time" id="hzS" value="${saat}" aria-label="Saat seçin"></div></div>
      <div class="hz-sat"><span>Oruç</span><div class="hz-c"><button data-o="0" class="${bozarMi() ? '' : 'on'}">Sürüyor</button><button data-o="1" class="${bozarMi() ? 'on' : ''}">Bitti</button></div></div>
      <button class="btn ana genis" id="hzEkle">Ekle</button>`;
    $$('[data-z]', T).forEach(b => b.onclick = () => { zaman = +b.dataset.z; saat = ''; tepsi(); });
    $('#hzS', T).onchange = e => { saat = e.target.value; tepsi(); };
    $$('[data-o]', T).forEach(b => b.onclick = () => { orucElle = b.dataset.o === '1'; tepsi(); });
    $('#hzEkle', T).onclick = kaydet;
  };
  const ciz = () => { liste(); tepsi(); };
  const kaydet = async () => {
    let t = Math.floor(Date.now() / 1000) - zaman * 60;
    if (saat){ const [a, b] = saat.split(':').map(Number), d = new Date(); d.setHours(a, b, 0, 0); if (d.getTime() > Date.now() + 60000) d.setDate(d.getDate() - 1); t = Math.floor(d.getTime() / 1000); }
    const kalemler = [...secim].map(([k, a]) => { const x = Y[k]; return {ad: `${adetYaz(a)} ${x.birim} ${kucuk(x.ad)}`, hazir: k, adet: a, birim: x.birim, miktar_g: Math.round(x.g * a), yuz: x.yuz, kaynak: x.kaynak, bls: x.bls}; });
    const bozar = bozarMi(), ad = kalemler.slice(0, 3).map(k => k.ad).join(', ') + (kalemler.length > 3 ? ` +${kalemler.length - 3}` : '');
    const yem = {ad, kalemler, t, secim: true, favori: false, kontrol: false};
    if (orucElle !== null) yem.oruc_bozar = orucElle;
    try{ await gonder('/api/pt/yemek', {tarih: bugunT(), yemek: yem}); veri = null; p.kapat(); toast(bozar ? 'Eklendi. Orucunuz bitti.' : 'Eklendi. Orucunuz sürüyor.'); yukle(); }catch(e){ toast(e.message); }
  };
  $$('#hzGr button', ku).forEach(b => b.onclick = () => { grup = b.dataset.g; ara = ''; $('#hzAra', ku).value = ''; liste(); $('#hzL', ku).scrollTop = 0; });
  $('#hzAra', ku).oninput = e => { ara = e.target.value; liste(); };
  $('#hzYok', ku).onclick = () => { p.kapat(); yemekSayfa(); };
  ciz();
};
})();
