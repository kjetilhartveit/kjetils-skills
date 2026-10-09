/* explain-visually kit.js: themes, tabs or page mode (+ chapter list), code blocks, clip player. Dependency-free.
   Loaded in <head> (inlined by assemble.py). Defines window.EV; wires the page on DOMContentLoaded.
   Public API:
     EV.onShow(tab, fn(panel, info))   run fn whenever tab `tab` becomes visible (info.first on 1st show)
     EV.onHide(tab, fn(panel))         run fn when it is hidden
     EV.clip(el, opts) -> player       animated SVG clip with play/pause/replay/scrub
     EV.code(el)                       enhance one <figure class="ev-code"> (auto-run for all on load)
     EV.highlight(src) -> html         TS/JS token highlighting of one string
     EV.svg                            helpers: el, text, clamp, win, easeIO, easeOut
     EV.select(tab)                    switch tab from script
     EV.stickyTop() -> px              height of the sticky bar at the top (tab bar / chapter bar), 0 if none;
                                       also kept in the CSS variable --ev-sticky-top on <html>
   Events dispatched on each .ev-tab-content: "ev:tabshow" / "ev:tabhide" (detail: {tab, first}). */
(function () {
  "use strict";
  var root = document.documentElement;
  var EV = window.EV = window.EV || {};

  /* ------------------------------------------------------------------ themes */
  var THEMES = [
    { id: "violet", name: "Violet", dark: true, light: true, sw: ["#09090b", "#8d7dff"],
      font: "family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600" },
    { id: "ocean", name: "Ocean", dark: true, light: true, sw: ["#071422", "#2fb8d6"],
      font: "family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600" },
    { id: "amber", name: "Amber", dark: true, light: true, sw: ["#121212", "#e0a030"],
      font: "family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600" },
    { id: "aurora", name: "Aurora", dark: true, light: false, sw: ["#0a0e17", "#2dd4bf"],
      font: "family=Sora:wght@400;500;600;700&family=Fira+Code:wght@400;500;600" }
  ];
  var byId = {};
  THEMES.forEach(function (t) { byId[t.id] = t; });
  function load(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function save(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) {} }

  var authored = root.getAttribute("data-ev-theme");
  var theme = byId[load("ev-theme")] ? load("ev-theme") : byId[authored] ? authored : "violet";
  var modeChoice = load("ev-mode"); // "dark" | "light" | null (= follow host / system)
  var mqLight = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;

  function resolveMode() {
    var t = byId[theme];
    if (!t.light) return "dark";
    if (!t.dark) return "light";
    if (modeChoice === "dark" || modeChoice === "light") return modeChoice;
    var host = root.getAttribute("data-theme");
    if (host === "dark" || host === "light") return host;
    return mqLight && mqLight.matches ? "light" : "dark";
  }
  var fontsLoaded = { violet: true }; // the shell links Geist
  function ensureFonts(t) {
    if (fontsLoaded[t.id]) return;
    fontsLoaded[t.id] = true;
    var l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?" + t.font + "&display=swap";
    document.head.appendChild(l);
  }
  function applyTheme() {
    root.setAttribute("data-ev-theme", theme);
    root.setAttribute("data-ev-mode", resolveMode());
    ensureFonts(byId[theme]);
    renderSwitchers();
  }
  applyTheme(); // synchronous, before first paint
  if (mqLight && mqLight.addEventListener) mqLight.addEventListener("change", function () { if (!modeChoice) applyTheme(); });
  if (window.MutationObserver) new MutationObserver(function () { if (!modeChoice) applyTheme(); })
    .observe(root, { attributes: true, attributeFilter: ["data-theme"] });

  var SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  var MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/></svg>';

  function buildSwitcher(host) {
    host.classList.add("ev-themes");
    host.setAttribute("role", "group");
    host.setAttribute("aria-label", "Theme");
    var g = document.createElement("div");
    g.className = "ev-themes-group";
    THEMES.forEach(function (t) {
      var b = document.createElement("button");
      b.type = "button";
      b.setAttribute("data-ev-theme-id", t.id);
      b.title = t.name + (t.light ? "" : " (dark only)");
      b.innerHTML = '<span class="ev-sw" style="background:' + t.sw[0] + '"><i style="background:' + t.sw[1] + '"></i></span><span class="ev-nm">' + t.name + "</span>";
      b.addEventListener("click", function () { theme = t.id; save("ev-theme", t.id); applyTheme(); });
      g.appendChild(b);
    });
    var m = document.createElement("button");
    m.type = "button";
    m.className = "ev-mode";
    m.addEventListener("click", function () {
      modeChoice = resolveMode() === "dark" ? "light" : "dark";
      save("ev-mode", modeChoice);
      applyTheme();
    });
    host.innerHTML = "";
    host.appendChild(g);
    host.appendChild(m);
  }
  function renderSwitchers() {
    var mode = root.getAttribute("data-ev-mode"), t = byId[theme];
    document.querySelectorAll(".ev-themes").forEach(function (host) {
      host.querySelectorAll("[data-ev-theme-id]").forEach(function (b) {
        b.setAttribute("aria-pressed", String(b.getAttribute("data-ev-theme-id") === theme));
      });
      var m = host.querySelector(".ev-mode");
      if (!m) return;
      var both = t.dark && t.light;
      m.disabled = !both;
      m.innerHTML = mode === "dark" ? SUN : MOON;
      m.setAttribute("aria-label", both ? (mode === "dark" ? "Switch to light mode" : "Switch to dark mode") : t.name + " has a dark mode only");
      m.title = m.getAttribute("aria-label");
    });
  }

  /* -------------------------------------------------------------------- tabs */
  var panels = {}, tabs = {}, order = [], current = null, shownOnce = {};

  function fire(panel, type, first) {
    panel.dispatchEvent(new CustomEvent(type, { detail: { tab: panel.getAttribute("data-tab"), first: !!first } }));
  }
  function show(name, opts) {
    opts = opts || {};
    if (!panels[name]) return;
    if (current === name) return;
    var prev = current;
    current = name;
    order.forEach(function (n) {
      var on = n === name;
      if (tabs[n]) { tabs[n].setAttribute("aria-selected", String(on)); tabs[n].tabIndex = on ? 0 : -1; }
      panels[n].hidden = !on;
    });
    if (prev) fire(panels[prev], "ev:tabhide");
    var first = !shownOnce[name];
    shownOnce[name] = true;
    fire(panels[name], "ev:tabshow", first);
    if (opts.focus && tabs[name]) tabs[name].focus();
    if (opts.hash) { try { history.replaceState(null, "", "#" + name); } catch (e) {} }
    if (opts.scroll) {
      var bar = document.querySelector(".ev-tabbar");
      // If the reader is deep in the previous tab (bar is stuck), jump to the top of the new one.
      if (bar && bar.getBoundingClientRect().top <= 1) {
        window.scrollTo({ top: panels[name].parentNode.getBoundingClientRect().top + window.scrollY - bar.offsetHeight, behavior: "auto" });
      }
    }
  }
  EV.select = function (name) { show(name, { hash: true, scroll: true }); };

  function fromHash() {
    var h = decodeURIComponent((location.hash || "").slice(1));
    if (!h) return false;
    if (panels[h]) { show(h); return true; }
    var el = document.getElementById(h);
    var p = el && el.closest(".ev-tab-content");
    if (p && panels[p.getAttribute("data-tab")]) {
      show(p.getAttribute("data-tab"));
      requestAnimationFrame(function () { el.scrollIntoView({ block: "start" }); });
      return true;
    }
    return false;
  }

  function initTabs() {
    document.querySelectorAll(".ev-tab-content[data-tab]").forEach(function (p) {
      var n = p.getAttribute("data-tab");
      panels[n] = p;
      order.push(n);
    });
    var list = document.querySelector(".ev-tablist");
    if (!list) { // standalone: every fragment is visible at once
      order.forEach(function (n) { current = n; shownOnce[n] = true; fire(panels[n], "ev:tabshow", true); });
      fromHashStandalone();
      return;
    }
    list.querySelectorAll('[role="tab"]').forEach(function (t) {
      var n = t.getAttribute("data-tab");
      tabs[n] = t;
      t.addEventListener("click", function () { show(n, { hash: true, scroll: true }); });
    });
    list.addEventListener("keydown", function (e) {
      var names = order.filter(function (n) { return tabs[n]; });
      var i = names.indexOf(current), j = -1;
      if (e.key === "ArrowRight") j = (i + 1) % names.length;
      else if (e.key === "ArrowLeft") j = (i - 1 + names.length) % names.length;
      else if (e.key === "Home") j = 0;
      else if (e.key === "End") j = names.length - 1;
      if (j < 0) return;
      e.preventDefault();
      show(names[j], { focus: true, hash: true });
    });
    order.forEach(function (n) { panels[n].hidden = true; });
    if (!fromHash()) {
      var def = list.getAttribute("data-default");
      show(panels[def] ? def : order[0]);
    }
    window.addEventListener("hashchange", fromHash);
  }
  function fromHashStandalone() {
    var h = (location.hash || "").slice(1), el = h && document.getElementById(h);
    if (el) requestAnimationFrame(function () { el.scrollIntoView({ block: "start" }); });
  }

  /* ------------------------------------------- page mode: chapter list */
  /* Height of whatever is stuck to the top of the viewport (tab bar, or the collapsed chapter bar
     on narrow screens). Fragments with sticky graphics offset themselves by this. */
  EV.stickyTop = function () {
    var bar = document.querySelector(".ev-tabbar") || document.querySelector(".ev-toc-bar");
    if (!bar || getComputedStyle(bar).display === "none") return 0;
    return Math.round(bar.getBoundingClientRect().height);
  };
  function initToc() {
    var toc = document.querySelector(".ev-toc");
    if (!toc) return;
    var bar = toc.querySelector(".ev-toc-bar");
    var nowN = toc.querySelector(".ev-toc-now .ev-toc-n"), nowL = toc.querySelector(".ev-toc-now .ev-toc-lbl");
    var links = Array.prototype.slice.call(toc.querySelectorAll(".ev-toc-list a"));
    var items = links.map(function (a) {
      var part = a.closest(".ev-toc-sub") ? a.closest(".ev-toc-sub").parentNode.querySelector(".ev-toc-part") : a;
      return { a: a, part: part, el: document.getElementById(a.getAttribute("href").slice(1)) };
    }).filter(function (it) { return it.el; });
    var cur = -1, queued = false;
    function label(a) { return a.querySelector(".ev-toc-t").textContent; }
    function setActive(i) {
      if (i === cur) return;
      cur = i;
      var it = items[i];
      links.forEach(function (l) { l.classList.remove("is-active", "is-in"); l.removeAttribute("aria-current"); });
      it.a.classList.add("is-active");
      it.a.setAttribute("aria-current", "location");
      if (it.part !== it.a) it.part.classList.add("is-in");
      if (nowN) nowN.textContent = it.part.querySelector(".ev-toc-n").textContent;
      if (nowL) nowL.textContent = label(it.part) + (it.part !== it.a ? " · " + label(it.a) : "");
    }
    function onScroll() {
      queued = false;
      var top = EV.stickyTop(), line = top + (window.innerHeight - top) * 0.45, active = 0;
      items.forEach(function (it, i) { if (it.el.getBoundingClientRect().top <= line) active = i; });
      if ((window.innerHeight + window.scrollY) >= document.documentElement.scrollHeight - 2) active = items.length - 1;
      setActive(active);
    }
    function queue() { if (!queued) { queued = true; requestAnimationFrame(onScroll); } }
    function close() { toc.classList.remove("is-open"); if (bar) bar.setAttribute("aria-expanded", "false"); }
    if (bar) bar.addEventListener("click", function () {
      var open = toc.classList.toggle("is-open");
      bar.setAttribute("aria-expanded", String(open));
    });
    links.forEach(function (a) { a.addEventListener("click", close); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && toc.classList.contains("is-open")) { close(); bar.focus(); } });
    window.addEventListener("scroll", queue, { passive: true });
    window.addEventListener("resize", queue);
    onScroll();
  }

  /* onShow / onHide: safe to call before or after the first show */
  EV.onShow = function (name, fn) {
    function attach() {
      var p = panels[name] || document.querySelector('.ev-tab-content[data-tab="' + name + '"]');
      if (!p) return;
      p.addEventListener("ev:tabshow", function (e) { fn(p, e.detail); });
      if (shownOnce[name] && !p.hidden) fn(p, { tab: name, first: true });
    }
    if (ready) attach(); else pending.push(attach);
  };
  EV.onHide = function (name, fn) {
    var go = function () {
      var p = document.querySelector('.ev-tab-content[data-tab="' + name + '"]');
      if (p) p.addEventListener("ev:tabhide", function () { fn(p); });
    };
    if (ready) go(); else pending.push(go);
  };
  var ready = false, pending = [];

  /* ---------------------------------------------------------- svg helpers */
  var NS = "http://www.w3.org/2000/svg";
  function svgEl(parent, tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    if (attrs) for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function clamp(v, a, b) { a = a == null ? 0 : a; b = b == null ? 1 : b; return v < a ? a : v > b ? b : v; }
  EV.svg = {
    el: svgEl,
    text: function (p, x, y, s, cls, extra) {
      var a = { x: x, y: y };
      if (cls) a["class"] = cls;
      if (extra) for (var k in extra) a[k] = extra[k];
      return svgEl(p, "text", a, s);
    },
    clamp: clamp,
    win: function (t, a, b) { return clamp((t - a) / (b - a)); },        // 0..1 progress of t through [a,b]
    easeIO: function (p) { return p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2; },
    easeOut: function (p) { return 1 - Math.pow(1 - p, 3); },
    setClass: function (e, c) { if (e.getAttribute("class") !== c) e.setAttribute("class", c); },
    setText: function (e, s) { s = String(s); if (e.textContent !== s) e.textContent = s; }
  };

  /* ------------------------------------------------------------ clip player */
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var ICON_PLAY = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9.5-5.5z"/></svg>';
  var ICON_PAUSE = '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="2.5" width="3" height="11" rx="1"/><rect x="9.5" y="2.5" width="3" height="11" rx="1"/></svg>';
  var ICON_REPLAY = '<svg viewBox="0 0 16 16" aria-hidden="true" class="ev-rp"><path d="M2.5 8a5.5 5.5 0 1 0 1.7-4"/><path d="M2.5 2.5v3.5H6"/></svg>';
  function fmt(s) { s = Math.floor(s); var m = Math.floor(s / 60); s -= m * 60; return m + ":" + (s < 10 ? "0" : "") + s; }
  var players = [], rafOn = false, last = 0, io = null;

  /* opts: { duration (s), width=440, height=270, label, loop=true, caption,
             setup(svg) called once to build static shapes, draw(t, svg) called per frame } */
  EV.clip = function (el, opts) {
    if (!el || el.__evClip) return el && el.__evClip;
    el.classList.add("ev-clip");
    var w = opts.width || 440, h = opts.height || 270, dur = opts.duration;
    var screen = document.createElement("div");
    screen.className = "ev-clip-screen";
    var svg = svgEl(null, "svg", { viewBox: "0 0 " + w + " " + h, role: "img", "aria-label": opts.label || el.getAttribute("aria-label") || "Animation" });
    screen.appendChild(svg);
    var bar = document.createElement("div");
    bar.className = "ev-clip-bar";
    bar.innerHTML = '<button class="ev-clip-btn" type="button" data-pp></button>' +
      '<button class="ev-clip-btn" type="button" data-rp aria-label="Replay">' + ICON_REPLAY + "</button>" +
      '<div class="ev-clip-track" role="slider" tabindex="0" aria-label="Clip position" aria-valuemin="0" aria-valuemax="' + dur + '"><div class="ev-clip-rail"><div class="ev-clip-fill"></div></div></div>' +
      '<span class="ev-clip-time"></span>';
    el.innerHTML = "";
    el.appendChild(screen);
    el.appendChild(bar);
    if (opts.caption) {
      var cap = document.createElement("figcaption");
      cap.className = "ev-clip-cap";
      cap.textContent = opts.caption;
      el.appendChild(cap);
    }
    if (opts.setup) opts.setup(svg);
    var P = {
      el: el, svg: svg, dur: dur, t: dur, playing: false, started: false, userPaused: reduce, visible: false,
      loop: opts.loop !== false, draw: opts.draw,
      pp: bar.querySelector("[data-pp]"), fill: bar.querySelector(".ev-clip-fill"),
      time: bar.querySelector(".ev-clip-time"), track: bar.querySelector(".ev-clip-track")
    };
    P.render = function () {
      P.draw(P.t, svg);
      P.fill.style.width = (P.t / dur * 100) + "%";
      P.time.textContent = fmt(P.t) + " / " + fmt(dur);
      P.track.setAttribute("aria-valuenow", P.t.toFixed(1));
    };
    P.ui = function () {
      P.pp.innerHTML = P.playing ? ICON_PAUSE : ICON_PLAY;
      P.pp.setAttribute("aria-label", P.playing ? "Pause" : "Play");
    };
    P.play = function () {
      if (!P.started || P.t >= dur) { P.t = 0; P.started = true; }
      P.playing = true; P.ui(); kick();
    };
    P.pause = function () { P.playing = false; P.ui(); };
    P.seek = function (t) { P.t = clamp(t, 0, dur); P.started = true; P.render(); };
    P.toggle = function () {
      if (P.playing) { P.pause(); P.userPaused = true; } else { P.userPaused = false; P.play(); }
    };
    P.render(); // poster = end frame
    P.ui();
    P.pp.addEventListener("click", P.toggle);
    screen.addEventListener("click", P.toggle);
    bar.querySelector("[data-rp]").addEventListener("click", function () { P.t = 0; P.started = true; P.userPaused = false; P.play(); });
    function seekEv(ev) { var r = P.track.getBoundingClientRect(); P.seek((ev.clientX - r.left) / r.width * dur); }
    P.track.addEventListener("pointerdown", function (ev) {
      P.track.setPointerCapture(ev.pointerId); seekEv(ev);
      function mv(e) { seekEv(e); }
      function up() { P.track.removeEventListener("pointermove", mv); P.track.removeEventListener("pointerup", up); }
      P.track.addEventListener("pointermove", mv); P.track.addEventListener("pointerup", up);
    });
    P.track.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") { P.seek(P.t + (ev.key === "ArrowRight" ? 1 : -1)); ev.preventDefault(); }
    });
    var panel = el.closest(".ev-tab-content");
    if (panel) panel.addEventListener("ev:tabhide", function () { if (P.playing) P.pause(); });
    players.push(P);
    if (io) io.observe(el);
    el.__evClip = P;
    return P;
  };
  function frame(ts) {
    var dt = last ? Math.min(.1, (ts - last) / 1000) : 0, any = false;
    last = ts;
    players.forEach(function (P) {
      if (!P.playing) return;
      any = true;
      P.t += dt;
      if (P.t >= P.dur) {
        if (reduce || !P.loop) { P.t = P.dur; P.pause(); } else P.t = 0;
      }
      P.render();
    });
    if (any) requestAnimationFrame(frame); else { rafOn = false; last = 0; }
  }
  function kick() { if (!rafOn) { rafOn = true; last = 0; requestAnimationFrame(frame); } }
  if ("IntersectionObserver" in window) {
    io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var P = en.target.__evClip;
        if (!P) return;
        P.visible = en.isIntersecting && en.intersectionRatio >= .5;
        if (P.visible && !P.userPaused && !P.playing) P.play();
        else if (!P.visible && P.playing) P.pause();
      });
    }, { threshold: [0, .5, 1] });
  }
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) players.forEach(function (P) { if (P.playing) P.pause(); });
  });

  /* ------------------------------------------------------- code highlighting */
  var KW = "const|let|var|function|return|if|else|for|while|of|in|new|await|async|export|import|from|as|type|interface|extends|implements|class|typeof|keyof|true|false|null|undefined|this|throw|try|catch|finally|switch|case|default|break|continue|do|yield|enum|declare|satisfies|void|readonly|public|private|protected|static";
  var TOKEN = new RegExp(
    "(\\/\\/.*$)" +                                   // 1 line comment
    "|(\\/\\*.*?(?:\\*\\/|$))" +                      // 2 block comment (single line part)
    "|(\"(?:[^\"\\\\]|\\\\.)*\"|'(?:[^'\\\\]|\\\\.)*'|`(?:[^`\\\\]|\\\\.)*`)" + // 3 strings
    "|\\b(" + KW + ")\\b" +                           // 4 keywords
    "|\\b(\\d[\\d_]*(?:\\.\\d+)?)\\b" +               // 5 numbers
    "|\\b([A-Z][A-Za-z0-9_]*)\\b" +                   // 6 types / classes
    "|([A-Za-z_$][\\w$]*)(?=\\s*\\()", "g");          // 7 calls
  var CLS = [null, "com", "com", "str", "kw", "num", "type", "fn"];
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function hlLine(line, state) {
    var out = "", i = 0, m;
    if (state.inBlock) {
      var end = line.indexOf("*/");
      if (end < 0) return '<span class="ev-tk-com">' + esc(line) + "</span>";
      out = '<span class="ev-tk-com">' + esc(line.slice(0, end + 2)) + "</span>";
      i = end + 2; state.inBlock = false;
    }
    TOKEN.lastIndex = i;
    while ((m = TOKEN.exec(line))) {
      if (m[0] === "") { TOKEN.lastIndex++; continue; }
      out += esc(line.slice(i, m.index));
      var k = 1; while (!m[k]) k++;
      out += '<span class="ev-tk-' + CLS[k] + '">' + esc(m[0]) + "</span>";
      if (k === 2 && !/\*\/$/.test(m[0])) state.inBlock = true;
      i = TOKEN.lastIndex;
    }
    return out + esc(line.slice(i));
  }
  EV.highlight = function (src) {
    var st = { inBlock: false };
    return src.split("\n").map(function (l) { return hlLine(l, st); }).join("\n");
  };

  function ranges(spec) { // "3-6, 9" -> {3:1,4:1,5:1,6:1,9:1}
    var set = {};
    (spec || "").split(",").forEach(function (part) {
      var m = /^\s*(\d+)\s*(?:-\s*(\d+))?\s*$/.exec(part);
      if (!m) return;
      for (var n = +m[1], e = m[2] ? +m[2] : n; n <= e; n++) set[n] = 1;
    });
    return set;
  }
  /* <figure class="ev-code" data-file="path/to/file.ts" data-start="1" data-add="3-6" data-del="2"
       data-hl="9" data-focus data-marks="4:1, 9:2" data-groups="3-6:New early return; 8-9:Unchanged"
       data-tag="Proposed"><pre><code>…escaped source…</code></pre>
       <ol class="ev-code-notes"><li>note for marker 1</li>…</ol></figure>
     Line numbers in all attributes are DISPLAYED numbers (data-start based). */
  EV.code = function (fig) {
    if (fig.__evCode) return;
    fig.__evCode = true;
    var code = fig.querySelector("pre > code") || fig.querySelector("pre");
    if (!code) return;
    var src = code.textContent.replace(/^\n+|\s+$/g, "");
    var start = parseInt(fig.getAttribute("data-start") || "1", 10);
    var add = ranges(fig.getAttribute("data-add")), del = ranges(fig.getAttribute("data-del")), hl = ranges(fig.getAttribute("data-hl"));
    var marks = {};
    (fig.getAttribute("data-marks") || "").split(",").forEach(function (p) {
      var m = /^\s*(\d+)\s*:\s*(\w+)\s*$/.exec(p);
      if (m) (marks[+m[1]] = marks[+m[1]] || []).push(m[2]);
    });
    var groups = {};
    (fig.getAttribute("data-groups") || "").split(";").forEach(function (p) {
      var m = /^\s*(\d+)(?:\s*-\s*(\d+))?\s*:\s*(.+?)\s*$/.exec(p);
      if (m) groups[+m[1]] = { label: m[3], end: m[2] ? +m[2] : +m[1] };
    });
    var lines = EV.highlight(src).split("\n"), nAdd = 0, nDel = 0, html = "";
    lines.forEach(function (l, i) {
      var n = start + i, cls = "ev-ln", g = " ";
      if (groups[n]) {
        var isNew = true;
        for (var k = n; k <= groups[n].end; k++) if (!add[k]) isNew = false;
        html += '<span class="ev-ln-group' + (isNew ? " is-new" : "") + '">' + esc(groups[n].label) + "</span>";
      }
      if (add[n]) { cls += " is-add"; g = "+"; nAdd++; }
      else if (del[n]) { cls += " is-del"; g = "−"; nDel++; }
      if (hl[n]) cls += " is-hl";
      var mk = (marks[n] || []).map(function (x) { return '<span class="ev-mark" aria-label="note ' + x + '">' + x + "</span>"; }).join("");
      html += '<span class="' + cls + '"><span class="ev-ln-n">' + n + '</span><span class="ev-ln-g" aria-hidden="true">' + g + '</span><span class="ev-ln-c">' + (l || " ") + mk + "</span></span>";
    });
    var pre = code.closest("pre") || code;
    var newPre = document.createElement("pre");
    newPre.innerHTML = "<code>" + html + "</code>";
    var scroll = document.createElement("div");
    scroll.className = "ev-code-scroll";
    scroll.appendChild(newPre);
    pre.parentNode.replaceChild(scroll, pre);
    if (fig.hasAttribute("data-focus")) fig.classList.add("is-focus");
    var file = fig.getAttribute("data-file"), tag = fig.getAttribute("data-tag");
    if (file || tag || nAdd || nDel) {
      var head = document.createElement("div");
      head.className = "ev-code-head";
      var h = "";
      if (file) {
        var cut = file.lastIndexOf("/");
        h += '<span class="ev-code-file" data-kind="file"><span><span class="ev-dir">' + esc(file.slice(0, cut + 1)) + '</span><span class="ev-base">' + esc(file.slice(cut + 1)) + "</span></span></span>";
      }
      h += '<span class="ev-code-tag">';
      if (nAdd || nDel) h += '<span class="ev-code-stat"><span class="ev-add">+' + nAdd + '</span> <span class="ev-del">−' + nDel + "</span></span>";
      if (tag) h += '<span class="ev-chip ev-chip--neutral">' + esc(tag) + "</span>";
      h += "</span>";
      head.innerHTML = h;
      fig.insertBefore(head, fig.firstChild);
    }
  };

  /* --------------------------------------------------------------- boot */
  function boot() {
    document.querySelectorAll("[data-ev-themes]").forEach(buildSwitcher);
    renderSwitchers();
    document.querySelectorAll("figure.ev-code").forEach(EV.code);
    ready = true;
    pending.splice(0).forEach(function (f) { f(); });
    initTabs();
    initToc();
    syncStickyTop();
    window.addEventListener("resize", syncStickyTop);
    document.querySelectorAll(".ev-side").forEach(initSide);
  }
  /* Mirrors EV.stickyTop() into CSS so sticky panels (.ev-stick) can sit below the top bar without script. */
  function syncStickyTop() { root.style.setProperty("--ev-sticky-top", EV.stickyTop() + "px"); }

  /* ev-side: tell CSS the panel's height (for the centred sticky top) and centre the panel on the first text
     box at rest, by pushing down whichever column starts higher. Re-runs whenever either side changes size
     (also when a hidden tab is shown). */
  function initSide(side) {
    var stick = side.querySelector(":scope > .ev-stick");
    var text = Array.prototype.filter.call(side.children, function (c) { return c !== stick; })[0];
    if (!stick || !text || !window.ResizeObserver) return;
    var anchor = text.querySelector("[data-ev-anchor]") || text.firstElementChild || text;
    function align() {
      var h = stick.offsetHeight;
      if (!h) return;                       // hidden tab
      stick.style.setProperty("--ev-stick-h", h + "px");
      var stacked = getComputedStyle(stick).position !== "sticky";
      var a = anchor.getBoundingClientRect(), t = text.getBoundingClientRect();
      var diff = stacked ? 0 : Math.round(a.top - t.top + a.height / 2 - h / 2);
      stick.style.setProperty("--ev-side-shift", Math.max(0, diff) + "px");
      text.style.setProperty("--ev-side-shift", Math.max(0, -diff) + "px");
    }
    var ro = new ResizeObserver(align);
    [stick, text, anchor].forEach(function (el) { ro.observe(el); });
    window.addEventListener("resize", align);
    align();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
