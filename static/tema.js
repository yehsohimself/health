/* Görünüm seçimi: Açık | Koyu (2026-11-03). Bütün ürünlerde tek davranış, tek seçim.
   Her ürün ayrı kapıda açıldığı için localStorage paylaşılmaz; çerez kapıdan bağımsızdır, seçim bir yerde yapılınca her üründe geçerli olur.
   <head>'in başında yüklenir ki sayfa yanlış renkte görünüp değişmesin. Kullanım: Tema.bagla(düğme). Değişince window'da 'vh-tema' olayı. */
window.Tema = (() => {
  const VARSAYILAN = 'dark';
  const IKON = {
    light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    dark: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5z"/>',
  };
  const baglilar = new Set();
  const oku = () => { const m = /(?:^|;\s*)vh_tema=(light|dark)/.exec(document.cookie); return m ? m[1] : VARSAYILAN; };
  const al = () => document.documentElement.dataset.theme;
  function ciz(b){ const koyu = al() === 'dark', yazi = koyu ? 'Açık görünüme geç' : 'Koyu görünüme geç';
    // simge gidilecek görünümü gösterir: koyudayken güneş, açıktayken ay
    b.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${koyu ? IKON.light : IKON.dark}</svg>`;
    b.title = yazi; b.setAttribute('aria-label', yazi); }
  function uygula(t){ document.documentElement.dataset.theme = t;
    const m = document.querySelector('meta[name=theme-color]'); if (m) m.content = t === 'light' ? '#f7f7f5' : '#08080a';
    baglilar.forEach(ciz); }
  function ayarla(t){ document.cookie = `vh_tema=${t}; path=/; max-age=31536000; SameSite=Lax`; uygula(t); window.dispatchEvent(new CustomEvent('vh-tema', {detail: t})); }
  const degistir = () => ayarla(al() === 'light' ? 'dark' : 'light');
  function bagla(b){ if (!b) return; baglilar.add(b); ciz(b); b.onclick = degistir; }
  uygula(oku());
  // başka üründe değiştirildiyse bu sekmeye dönünce uyar
  window.addEventListener('focus', () => { const t = oku(); if (t !== al()){ uygula(t); window.dispatchEvent(new CustomEvent('vh-tema', {detail: t})); } });
  return {al, ayarla, degistir, bagla};
})();
