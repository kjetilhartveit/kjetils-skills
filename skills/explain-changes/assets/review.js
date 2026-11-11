
(() => {
  const store = (() => { try { return window.localStorage; } catch { return null; } })();
  const pageKey = 'rv:' + document.title + ':';
  // Folding a file from its bottom would leave the reader far below it, so bring its header back into view.
  const fold = (file, scroll = true) => {
    file.open = false;
    if (scroll && file.getBoundingClientRect().top < 0) file.scrollIntoView({ block: 'start' });
  };
  document.querySelectorAll('.rv-file').forEach((file) => {
    const boxes = [...file.querySelectorAll('.rv-viewed input')];
    if (!boxes.length) return;
    const key = pageKey + boxes[0].dataset.key;
    const listed = document.querySelectorAll(`.rv-files a[href="#${file.id}"], .rv-nav a[href="#${file.id}"]`);
    const apply = (viewed, scroll = true) => {
      boxes.forEach((box) => { box.checked = viewed; });
      file.classList.toggle('rv-done', viewed);
      listed.forEach((link) => link.closest('li').classList.toggle('rv-listed-done', viewed));
      if (viewed) fold(file, scroll);
    };
    let stored = false;
    try { stored = store?.getItem(key) === '1'; } catch {}
    if (stored) apply(true, false);
    boxes.forEach((box) => box.addEventListener('change', () => {
      try { store?.setItem(key, box.checked ? '1' : '0'); } catch {}
      apply(box.checked);
    }));
    file.querySelector('.rv-fold')?.addEventListener('click', () => fold(file));
  });
  const modeKey = 'rv:diff-view';
  const setMode = (mode) => {
    document.documentElement.dataset.diff = mode;
    document.querySelectorAll('.rv-seg button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.mode === mode)));
  };
  try { setMode(store?.getItem(modeKey) === 'lines' ? 'lines' : 'inline'); } catch { setMode('inline'); }
  document.querySelectorAll('.rv-seg button').forEach((b) => b.addEventListener('click', () => {
    setMode(b.dataset.mode);
    try { store?.setItem(modeKey, b.dataset.mode); } catch {}
  }));
  const setAll = (open) => document.querySelectorAll('.rv-file').forEach((file) => { file.open = open; });
  document.getElementById('rv-expand').addEventListener('click', () => setAll(true));
  document.getElementById('rv-collapse').addEventListener('click', () => setAll(false));
  const fitNotes = () => document.querySelectorAll('.rv-scroll').forEach((box) => {
    if (box.clientWidth) box.style.setProperty('--rv-visible', box.clientWidth + 'px');
  });
  fitNotes();
  const wrapKey = 'rv:wrap';
  const wrapButton = document.getElementById('rv-wrap');
  const setWrap = (on) => {
    document.documentElement.dataset.wrap = on ? 'on' : 'off';
    wrapButton.setAttribute('aria-pressed', String(on));
    fitNotes();
  };
  try { setWrap(store?.getItem(wrapKey) !== 'off'); } catch { setWrap(true); }
  wrapButton.addEventListener('click', () => {
    const on = wrapButton.getAttribute('aria-pressed') !== 'true';
    setWrap(on);
    try { store?.setItem(wrapKey, on ? 'on' : 'off'); } catch {}
  });
  window.addEventListener('resize', fitNotes);
  document.querySelectorAll('.rv-file').forEach((file) => file.addEventListener('toggle', fitNotes));
  document.querySelectorAll('.rv-files a, .rv-toc-file').forEach((link) => link.addEventListener('click', () => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) target.open = true;
  }));
})();
