// 넘치는 글을 줄여 맞추고(최소 크기까지), 그래도 넘치면 보고한다. 릴스 영상은 __seekCard(i, t) 로 장마다 시각을 맞춘다.
(() => {
  const report = [];
  document.querySelectorAll('.card').forEach((card, i) => {
    const box = card.querySelector('.content');
    const fits = () => box.scrollHeight <= box.clientHeight + 1 && box.scrollWidth <= box.clientWidth + 1;
    let scale = 1;
    const sized = [...box.querySelectorAll('[data-fit]')].map((el) => [el, parseFloat(getComputedStyle(el).fontSize)]);
    while (!fits() && scale > 0.62) {
      scale -= 0.04;
      for (const [el, base] of sized) el.style.fontSize = `${base * scale}px`;
    }
    if (scale < 0.999) report.push({ slide: i + 1, scale: Math.round(scale * 100) / 100, overflow: !fits() });
    // 한 줄에 한 글자만 남는 꼬리(외톨이) 찾기
    for (const el of box.querySelectorAll('.title, .item, .body')) {
      const range = document.createRange();
      range.selectNodeContents(el);
      const rects = [...range.getClientRects()];
      const last = rects[rects.length - 1];
      if (rects.length > 1 && last && last.width < parseFloat(getComputedStyle(el).fontSize) * 1.6) {
        report.push({ slide: i + 1, orphan: el.textContent.trim().slice(-12) });
      }
    }
  });
  window.__fitReport = report;

  window.__seekCard = (i, t) => {
    const cards = document.querySelectorAll('.card');
    cards.forEach((c, k) => c.classList.toggle('on', k === i));  // 영상: 한 장만 화면에
    for (const a of cards[i].getAnimations({ subtree: true })) { a.pause(); a.currentTime = t * 1000; }
  };
})();
