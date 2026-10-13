# Scripts and tab mode (explainer kit)

Only for fragments with their own script (section clips, slides, video, code walkthrough) and for tabbed pages.
Read `FRAGMENT-CONTRACT.md` first; this adds to it. Example of a scripted fragment:

```html
<section class="ev-tab-content" data-tab="clips" data-label="Clips" data-hint="short animations">
  <style> [data-tab="clips"] .clips-ring { … } </style>
  … content built from kit components …
  <script>
  (function () {
    "use strict";
    EV.onShow("clips", function (panel, info) {
      if (!info.first) return;            // build once
      EV.clip(panel.querySelector("#clips-backoff-clip"), { duration: 12, setup: …, draw: … });
    });
  })();
  </script>
</section>
```

## Script

- Inline scripts are wrapped in an IIFE `(function () { … })();`. **(checked)** No globals; query inside your
  own section (`panel.querySelector`), not `document.querySelector` (warning).
- `EV` exists before your script runs (kit.js is in `<head>`). Build things in **`EV.onShow(NAME, fn)`**:
  `fn(panel, {first})` runs whenever the tab becomes visible (and immediately in standalone pages).
  Hidden tabs are `display:none`, so measuring (`getBBox`, `getTotalLength`, scroll positions,
  IntersectionObserver setup) must happen there. Use `info.first` to build once; re-measure on every show.
- `EV.onHide(NAME, fn)` or `panel.addEventListener("ev:tabhide", …)` to pause your own animations.
  Players made with `EV.clip` pause on hide by themselves.
- Raw events, if you prefer: `ev:tabshow` / `ev:tabhide` CustomEvents on the section, `detail: {tab, first}`.
- External scripts only from `https://cdnjs.cloudflare.com/`, `https://cdn.jsdelivr.net/npm/`,
  `https://unpkg.com/`, pinned to an exact `x.y.z`. **(checked)** The same `src` in two fragments is loaded once.
- Respect `prefers-reduced-motion` (EV.clip does: no autoplay, end frame shown).

## Extra components

| need | markup |
|---|---|
| animated clip | `<figure class="ev-clip" id="NAME-x" aria-label="…">` + `EV.clip(el, {duration, width, height, setup(svg), draw(t, svg), caption})`; helpers in `EV.svg` (`el`, `text`, `win`, `easeIO`, `easeOut`, `setClass`, `setText`) |
| own scroll steps | `EV.steps(panel.querySelectorAll(".ev-step"), function (i, el) { … })` marks the current step and calls back in both scroll directions (code walkthrough). Not an `IntersectionObserver` |

## Tab mode

```
python assemble.py --title "Refresh tick backoff" --overview overview.html \
  --tab clips=frag-clips.html --tab story=frag-story.html --tab code=frag-code.html --out index.html
python assemble.py --title "Backoff in 90 seconds" --standalone frag-video.html [--overview ov.html] --out index.html
```

Options: `--default TAB` (default `clips`), `--theme violet|ocean|amber|aurora` (first-load theme; the viewer's
own pick is remembered). Deep links: `#clips`, `#story`, `#code`, or any element id (`#code-chain` opens the
Code tab and scrolls there). Arrow keys / Home / End move between tabs.

