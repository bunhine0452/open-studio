// 시각 t(초)로 화면 전체를 맞춘다. CSS 애니메이션은 멈춘 채 currentTime 만 옮기고,
// 숫자 세기·코드 타이핑·낱말 자막처럼 글자가 바뀌는 것만 여기서 그린다. 같은 t 면 언제나 같은 화면.
(() => {
  const D = window.__DATA;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const easeOut = (x) => 1 - Math.pow(1 - clamp(x), 3);
  const fmt = (n, comma) => (comma ? n.toLocaleString('en-US') : String(n));
  const cap = document.querySelector('.cap');
  let shown = -1;

  const vids = [...document.querySelectorAll('img.vid')];
  window.__seek = (t) => {
    for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; }
    const waits = [];
    for (const v of vids) {  // 카드 속 영상: 나타난 뒤부터 흐른다 (보이는 동안만 갈아 끼운다)
      const d = v.dataset;
      if (t < Number(d.t0) - 1 || t > Number(d.t1)) continue;
      const k = Math.max(0, Math.min(Number(d.n) - 1, Math.round((t - Number(d.t0) + Number(d.off)) * 30))) + 1;
      const src = d.dir + String(k).padStart(5, '0') + '.jpg';
      if (v.getAttribute('src') !== src) { v.setAttribute('src', src); waits.push(v.decode().catch(() => {})); }
    }

    for (const c of D.counts) {
      const el = document.getElementById(c.id);
      const n = Math.round(c.to * easeOut((t - c.t0) / c.dur));
      el.textContent = c.prefix + fmt(t < c.t0 ? 0 : n, c.comma) + c.suffix;
    }
    for (const ty of D.types) {
      const el = document.getElementById(ty.id);
      const k = t < ty.t0 ? 0 : Math.max(1, Math.round(ty.text.length * clamp((t - ty.t0) / ty.dur)));
      el.textContent = ty.text.slice(0, k);
    }

    const i = D.caps.findIndex((c) => t >= c.t0 && t < c.t1);
    if (i !== shown) {
      shown = i;
      cap.innerHTML = i < 0 ? '' : '<div class="box">' + D.caps[i].w.map((w) =>
        `<span class="w${w.hl ? ' hl' : ''}">${w.x}</span>`).join('') + '</div>';
    }
    if (i >= 0) {
      const c = D.caps[i];
      const p = easeOut((t - c.t0) / 0.18);
      const box = cap.firstChild;
      box.style.opacity = p;
      box.style.transform = `translateY(${(1 - p) * 14}px)`;
      const spans = box.children;
      let now = -1;
      c.w.forEach((w, k) => { if (t >= w.s - 0.04) now = k; });
      c.w.forEach((w, k) => {
        spans[k].classList.toggle('on', k <= now);
        spans[k].classList.toggle('now', k === now);
      });
    }
    return Promise.all(waits);
  };
})();
