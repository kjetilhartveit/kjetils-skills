#!/usr/bin/env python3
"""Assemble an explain-visually page from the kit and fragments.

Tabbed:
  python assemble.py --title "Refresh tick backoff" --overview overview.html \
      --tab clips=frag-clips.html --tab story=frag-story.html --tab code=frag-code.html \
      --out index.html [--default clips] [--theme violet]
Standalone (one fragment, no tab bar; --overview optional):
  python assemble.py --title "Backoff in 90 seconds" --standalone frag-video.html --out index.html
Page (one scrollable document: overview, then every section under a part heading; --toc adds a
sticky chapter list built from the part headings and every element with id + data-toc="Label"):
  python assemble.py --page --toc --title "Backoff explainer" --overview overview.html       --section story=frag-story.html --section code=frag-code.html --out index.html

Inlines kit.css + kit.js, inserts the fragments, and validates the fragment contract
(FRAGMENT-CONTRACT.md). Any error aborts without writing; warnings are printed.
Standard library only.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

KIT_DIR = Path(__file__).resolve().parent
ALLOWED_SCRIPT_HOSTS = (
    "https://cdnjs.cloudflare.com/",
    "https://cdn.jsdelivr.net/npm/",
    "https://unpkg.com/",
)
THEMES = ("violet", "ocean", "amber", "aurora")
KNOWN_LABELS = {"clips": "Clips", "story": "Story", "code": "Code", "video": "Video", "slides": "Slides"}
TAB_ICONS = {
    "clips": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><rect x="1.8" y="3" width="12.4" height="10" rx="2.2"/><path d="M6.8 6v4l3.4-2z" fill="currentColor"/></svg>',
    "story": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><path d="M2.5 3.5h11M2.5 6.5h11M2.5 9.5h7M2.5 12.5h9"/></svg>',
    "code": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5.5 4 2 8l3.5 4M10.5 4 14 8l-3.5 4"/></svg>',
    "video": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><circle cx="8" cy="8" r="6.2"/><path d="M6.7 5.6v4.8l3.8-2.4z" fill="currentColor"/></svg>',
    "slides": '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><rect x="1.8" y="2.5" width="12.4" height="8.5" rx="1.6"/><path d="M8 11v2.5M5.5 13.5h5"/></svg>',
}
TAB_NAME = re.compile(r"^[a-z][a-z0-9]*$")
FORBIDDEN_TAGS = {"html", "head", "body", "title", "meta", "link", "base", "iframe", "object", "embed"}


class Problems:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    def warn(self, where: str, msg: str) -> None:
        self.warnings.append(f"{where}: {msg}")


class Scan(HTMLParser):
    """Collects ids, classes, top-level elements, <style>/<script> bodies and tags."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.top: list[tuple[str, dict]] = []
        self.ids: list[tuple[str, int]] = []
        self.classes: set[str] = set()
        self.tags: set[str] = set()
        self.styles: list[str] = []
        self.scripts: list[tuple[dict, str]] = []
        self._in: str | None = None
        self._buf: list[str] = []
        self._attrs: dict = {}
        self.top_text = ""

    VOID = {"area", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "path",
            "circle", "rect", "line", "polyline", "polygon", "ellipse", "use", "stop"}

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self.tags.add(tag)
        if self.depth == 0:
            self.top.append((tag, a))
        if "id" in a:
            self.ids.append((a["id"], self.getpos()[0]))
        for c in a.get("class", "").split():
            self.classes.add(c)
        if tag in ("style", "script"):
            self._in, self._buf, self._attrs = tag, [], a
        if tag not in self.VOID:
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        self.tags.add(tag)
        if "id" in a:
            self.ids.append((a["id"], self.getpos()[0]))
        for c in a.get("class", "").split():
            self.classes.add(c)

    def handle_endtag(self, tag):
        if tag == self._in:
            body = "".join(self._buf)
            if tag == "style":
                self.styles.append(body)
            else:
                self.scripts.append((self._attrs, body))
            self._in = None
        if tag not in self.VOID:
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if self._in:
            self._buf.append(data)
        elif self.depth == 0:
            self.top_text += data


def strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def css_rules(css: str):
    """Yield (prelude, body) pairs at one nesting level."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            if css[i:].strip():
                yield css[i:].strip(), None
            return
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        yield prelude, css[j + 1:k - 1]
        i = k


def check_css(css: str, scope_re: re.Pattern, scope_txt: str, kf_prefix: str, where: str, p: Problems,
              kit_classes: set[str]) -> None:
    for prelude, body in css_rules(strip_css_comments(css)):
        if not prelude:
            continue
        if body is None:
            p.err(where, f"stray CSS outside a rule: {prelude[:60]!r}")
            continue
        if prelude.startswith("@"):
            at = prelude.split()[0].lower()
            if at in ("@media", "@supports", "@container", "@layer"):
                check_css(body, scope_re, scope_txt, kf_prefix, where, p, kit_classes)
            elif at in ("@keyframes", "@-webkit-keyframes"):
                name = prelude.split(None, 1)[1].strip() if " " in prelude else ""
                if not name.startswith(kf_prefix):
                    p.err(where, f"@keyframes {name!r} must be prefixed {kf_prefix!r} (keyframe names are global)")
            elif at in ("@import", "@font-face", "@property", "@page"):
                p.err(where, f"{at} is not allowed in a fragment (global effect)")
            else:
                p.warn(where, f"unchecked at-rule {at}")
            continue
        for sel in split_selectors(prelude):
            if not scope_re.match(sel):
                p.err(where, f"selector {sel!r} is not scoped under {scope_txt}")
            for c in re.findall(r"\.(ev-[\w-]+)", sel):
                if "." + c == scope_txt:
                    continue
                if c not in kit_classes:
                    p.err(where, f"selector uses .{c}: the ev- prefix is reserved for the kit; name your own classes <tab>-...")
                else:
                    p.warn(where, f"selector restyles kit class .{c}; prefer kit tokens/modifiers over overrides")


def split_selectors(prelude: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in prelude:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def check_scripts(scripts, where: str, p: Problems, seen_src: dict) -> list[str]:
    """Returns srcs that are duplicates of an earlier fragment's (to be removed)."""
    dupes = []
    for attrs, body in scripts:
        src = attrs.get("src")
        if src:
            if not src.startswith(ALLOWED_SCRIPT_HOSTS):
                p.err(where, f"script src {src!r} is not on the CDN allowlist {ALLOWED_SCRIPT_HOSTS}")
            elif not re.search(r"[@/]\d+\.\d+\.\d+", src):
                p.err(where, f"script src {src!r} must pin an exact version (x.y.z)")
            if src in seen_src:
                dupes.append(src)
                p.warn(where, f"script {src} already loaded by {seen_src[src]}; the duplicate tag is dropped")
            else:
                seen_src[src] = where
            continue
        if attrs.get("type") not in (None, "", "text/javascript", "module"):
            continue  # data blocks (e.g. application/json) are fine
        code = re.sub(r"^\s*(//[^\n]*\n|/\*.*?\*/)*", "", body, flags=re.S).strip()
        if code and not re.match(r"^[;!]?\s*\(\s*(function\b|\(\s*\)\s*=>|async\b)", code):
            p.err(where, "inline <script> must be wrapped in an IIFE: (function () { ... })();")
        if re.search(r"\bdocument\.querySelector(All)?\(\s*['\"][.\w]", code):
            p.warn(where, "document.querySelector(…) found; query inside your own section (panel.querySelector) instead")
        if re.search(r"\bwindow\.\w+\s*=(?!=)", code):
            p.warn(where, "assigns a window.* global; keep state inside the IIFE")
    return dupes


def read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        sys.exit(f"assemble.py: cannot read {path}: {e}")


def kit_class_names(css: str) -> set[str]:
    return set(re.findall(r"\.(ev-[\w-]+)", css))


def validate_fragment(name: str, path: str, src: str, p: Problems, kit_classes: set[str], seen_src: dict):
    where = Path(path).name
    sc = Scan()
    sc.feed(src)
    sc.close()
    sections = [(t, a) for t, a in sc.top if t != "!--"]
    if len(sections) != 1 or sections[0][0] != "section":
        p.err(where, f"must contain exactly one top-level <section>, found {[t for t, _ in sections]}")
        return sc, {}
    tag, attrs = sections[0]
    if "ev-tab-content" not in attrs.get("class", "").split():
        p.err(where, 'top-level <section> needs class="ev-tab-content"')
    if attrs.get("data-tab") != name:
        p.err(where, f'data-tab="{attrs.get("data-tab")}" does not match --tab name {name!r}')
    if "id" in attrs:
        p.err(where, "the top-level section must not have an id (the assembler sets it)")
    if sc.top_text.strip():
        p.err(where, f"text outside the <section>: {sc.top_text.strip()[:60]!r}")
    for t in sorted(sc.tags & FORBIDDEN_TAGS):
        p.err(where, f"<{t}> is not allowed in a fragment")
    for i, line in sc.ids:
        if not i.startswith(name + "-"):
            p.err(where, f"line {line}: id {i!r} must be prefixed {name + '-'!r}")
    for c in sorted(sc.classes):
        if c.startswith("ev-") and c not in kit_classes:
            p.warn(where, f"class {c!r} is not defined in kit.css (typo?)")
    scope = re.compile(r"""^\[data-tab=(["']?)%s\1\]""" % re.escape(name))
    for css in sc.styles:
        check_css(css, scope, f'[data-tab="{name}"]', name + "-", where, p, kit_classes)
    dupes = check_scripts(sc.scripts, where, p, seen_src)
    return sc, {"attrs": attrs, "dupes": dupes}


def validate_overview(path: str, src: str, p: Problems, kit_classes: set[str], seen_src: dict):
    where = Path(path).name
    sc = Scan()
    sc.feed(src)
    sc.close()
    tops = [t for t, _ in sc.top]
    if tops != ["header"] or "ev-overview" not in sc.top[0][1].get("class", "").split():
        p.err(where, f'overview must be exactly one <header class="ev-overview">, found {tops}')
    for t in sorted(sc.tags & FORBIDDEN_TAGS):
        p.err(where, f"<{t}> is not allowed in the overview")
    for i, line in sc.ids:
        if not i.startswith("ov-"):
            p.err(where, f"line {line}: id {i!r} must be prefixed 'ov-'")
    if "h1" not in sc.tags:
        p.warn(where, "overview has no <h1 class=\"ev-headline\">")
    if "figure" not in sc.tags:
        p.warn(where, "overview has no hero <figure class=\"ev-hero\">")
    for c in sorted(sc.classes):
        if c.startswith("ev-") and c not in kit_classes:
            p.warn(where, f"class {c!r} is not defined in kit.css (typo?)")
    for css in sc.styles:
        check_css(css, re.compile(r"^\.ev-overview\b"), ".ev-overview", "ov-", where, p, kit_classes | {"ev-overview"})
    check_scripts(sc.scripts, where, p, seen_src)
    return sc


def drop_dupe_scripts(src: str, dupes: list[str]) -> str:
    for s in dupes:
        src = re.sub(r'<script[^>]*\bsrc=["\']%s["\'][^>]*>\s*</script>' % re.escape(s), "", src, count=1)
    return src


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--title", required=True, help="page name, 2-4 words")
    ap.add_argument("--overview", help="overview fragment (<header class=\"ev-overview\">)")
    ap.add_argument("--tab", action="append", default=[], metavar="NAME=FILE", help="tab fragment, in display order")
    ap.add_argument("--standalone", metavar="FILE", help="single fragment page without a tab bar")
    ap.add_argument("--page", action="store_true", help="one scrollable page; give sections with --section")
    ap.add_argument("--section", action="append", default=[], metavar="NAME=FILE", help="page-mode fragment, in display order")
    ap.add_argument("--toc", action="store_true", help="page mode: sticky chapter list on the left (top bar when narrow)")
    ap.add_argument("--default", help="tab selected on load (default: clips if present, else the first)")
    ap.add_argument("--theme", choices=THEMES, help="theme on first load (viewer's own choice still wins)")
    ap.add_argument("--kit-dir", default=str(KIT_DIR), help="folder with kit.css, kit.js, shell.html")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if a.page:
        if a.tab or a.standalone or not a.section:
            ap.error("--page takes one or more --section NAME=FILE (no --tab / --standalone)")
        a.tab = a.section
    elif a.section or a.toc:
        ap.error("--section and --toc need --page")
    elif bool(a.tab) == bool(a.standalone):
        ap.error("give either one or more --tab NAME=FILE, or --standalone FILE")

    kit = Path(a.kit_dir)
    kit_css, kit_js, shell = (kit / "kit.css").read_text("utf-8"), (kit / "kit.js").read_text("utf-8"), (kit / "shell.html").read_text("utf-8")
    kit_classes = kit_class_names(kit_css) | set(re.findall(r"""["' ](ev-[a-z][\w-]*)""", kit_js))
    p = Problems()
    seen_src: dict = {}
    all_ids: dict[str, str] = {}

    def collect_ids(sc: Scan, where: str):
        for i, line in sc.ids:
            if i in all_ids:
                p.err(where, f"line {line}: duplicate id {i!r} (also in {all_ids[i]})")
            else:
                all_ids[i] = f"{where}:{line}"

    overview_html = ""
    if a.overview:
        overview_html = read(a.overview)
        collect_ids(validate_overview(a.overview, overview_html, p, kit_classes, seen_src), Path(a.overview).name)

    tabs: list[tuple[str, str, str, dict]] = []
    specs = [("", a.standalone)] if a.standalone else []
    for spec in a.tab:
        if "=" not in spec:
            ap.error(f"--tab/--section expects NAME=FILE, got {spec!r}")
        specs.append(tuple(spec.split("=", 1)))
    names_seen = set()
    for name, path in specs:
        src = read(path)
        if a.standalone:
            m = re.search(r"""data-tab=["']([a-z][a-z0-9]*)["']""", src)
            name = m.group(1) if m else ""
        if not TAB_NAME.match(name):
            p.err(Path(path).name, f"tab name {name!r} must be lowercase letters/digits")
            continue
        if name in names_seen:
            p.err(Path(path).name, f"tab {name!r} given twice")
        names_seen.add(name)
        sc, info = validate_fragment(name, path, src, p, kit_classes, seen_src)
        collect_ids(sc, Path(path).name)
        tabs.append((name, path, drop_dupe_scripts(src, info.get("dupes", [])), info.get("attrs", {})))
    toc_subs: dict[str, list[tuple[str, str]]] = {}
    for name, path, src, _ in tabs:
        toc_subs[name] = []
        for m in re.finditer(r"<[a-zA-Z][^>]*\bdata-toc=[^>]*>", src):
            t = m.group(0)
            i, lbl = re.search(r'\sid="([^"]+)"', t), re.search(r'\bdata-toc="([^"]*)"', t)
            if not i or not lbl or not lbl.group(1).strip():
                p.err(Path(path).name, f"data-toc needs an id and a non-empty label: {t[:80]!r}")
            else:
                toc_subs[name].append((i.group(1), html.unescape(lbl.group(1))))
    if "overview" in all_ids:
        p.err(all_ids["overview"], "id 'overview' is reserved for page mode")
    for i in all_ids:
        if i in names_seen:
            p.err(all_ids[i], f"id {i!r} equals a tab name and would break #{i} deep links")

    for w in p.warnings:
        print("warning:", w, file=sys.stderr)
    if p.errors:
        for e in p.errors:
            print("ERROR:", e, file=sys.stderr)
        print(f"assemble.py: {len(p.errors)} error(s); nothing written.", file=sys.stderr)
        return 1

    title = html.escape(a.title)
    page_body = None
    if a.page:
        NL = "\n"
        parts: list[str] = []
        toc_items: list[str] = []
        if a.overview:
            toc_items.append('<li><a class="ev-toc-part" href="#overview"><span class="ev-toc-n">1</span>'
                             '<span class="ev-toc-t">Overview</span></a></li>')
        for k, (name, _, src, attrs) in enumerate(tabs, start=2 if a.overview else 1):
            label = attrs.get("data-label") or KNOWN_LABELS.get(name, name.capitalize())
            ptitle, plede, hint = attrs.get("data-part-title") or label, attrs.get("data-part-lede"), attrs.get("data-hint")
            head = (f'<header class="ev-part-head" id="{name}">'
                    f'<p class="ev-eyebrow"><span class="ev-n">{k}</span>{html.escape(label)}'
                    + (f' · {html.escape(hint)}' if hint else "") + "</p>"
                    + f'<h2 class="ev-part-title" id="{name}-part-title">{html.escape(ptitle)}</h2>'
                    + (f'<p class="ev-part-lede">{html.escape(plede)}</p>' if plede else "") + "</header>")
            parts.append(head + NL + re.sub(r"<section\b", f'<section aria-labelledby="{name}-part-title"',
                                            src.strip(), count=1))
            subs = "".join(f'<li><a href="#{i}"><span class="ev-toc-t">{html.escape(l)}</span></a></li>'
                           for i, l in toc_subs[name])
            toc_items.append(f'<li><a class="ev-toc-part" href="#{name}"><span class="ev-toc-n">{k}</span>'
                             f'<span class="ev-toc-t">{html.escape(label)}</span></a>'
                             + (f'<ol class="ev-toc-sub">{subs}</ol>' if subs else "") + "</li>")
        nav = ""
        if a.toc:
            first = "Overview" if a.overview else html.escape(tabs[0][3].get("data-label") or tabs[0][0].capitalize())
            nav = ('<nav class="ev-toc" aria-label="Chapters">' + NL
                   + '  <button class="ev-toc-bar" type="button" aria-expanded="false" aria-controls="ev-toc-list">'
                   + f'<span class="ev-toc-now"><span class="ev-toc-n">1</span><span class="ev-toc-lbl">{first}</span></span>'
                   + '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
                   + 'stroke-linejoin="round" aria-hidden="true"><path d="m6 3.5 4.5 4.5L6 12.5"/></svg></button>' + NL
                   + '  <div class="ev-toc-list" id="ev-toc-list"><p class="ev-toc-title">Chapters</p>' + NL
                   + '    <ol>' + (NL + "      ").join(toc_items) + "</ol>" + NL + "  </div>" + NL + "</nav>" + NL)
        topbar = re.search(r'<div class="ev-topbar">.*?</div>\s*</div>', shell, flags=re.S).group(0)
        page_body = (f'<div class="ev-doc{" ev-doc--toc" if a.toc else ""}">' + NL + nav
                     + '<div class="ev-doc-main">' + NL
                     + f'<div class="ev-page" id="overview">{NL}  {topbar}{NL}<!--EV:OVERVIEW-->{NL}</div>{NL}'
                     + '<main class="ev-panels ev-pages">' + NL + NL.join(parts) + NL
                     + "</main>" + NL + "</div>" + NL + "</div>")
        body = ""
    elif a.standalone:
        name, _, src, _ = tabs[0]
        body = f'<main class="ev-panels ev-standalone">\n{src.strip()}\n</main>'
    else:
        default = a.default or ("clips" if "clips" in names_seen else tabs[0][0])
        if default not in names_seen:
            ap.error(f"--default {default!r} is not one of the tabs")
        buttons, sections = [], []
        for name, _, src, attrs in tabs:
            label = html.escape(attrs.get("data-label") or KNOWN_LABELS.get(name, name.capitalize()))
            hint = attrs.get("data-hint")
            sel = name == default
            buttons.append(
                f'<button class="ev-tab" type="button" role="tab" id="tab-{name}" data-tab="{name}" '
                f'aria-controls="{name}" aria-selected="{str(sel).lower()}" tabindex="{0 if sel else -1}">'
                f'{TAB_ICONS.get(name, "")}<span>{label}</span>'
                + (f'<span class="ev-tab-hint">{html.escape(hint)}</span>' if hint else "")
                + "</button>"
            )
            # Give the section its panel identity: id=<name> (hash target), role, labelledby.
            src = re.sub(
                r"<section\b", f'<section id="{name}" role="tabpanel" aria-labelledby="tab-{name}" tabindex="-1"'
                + ("" if sel else " hidden"), src.strip(), count=1)
            sections.append(src)
        body = (
            '<nav class="ev-tabbar" aria-label="Views">\n'
            f'  <div class="ev-tablist" role="tablist" data-default="{default}">\n    '
            + "\n    ".join(buttons)
            + "\n  </div>\n</nav>\n"
            '<main class="ev-panels">\n' + "\n".join(sections) + "\n</main>"
        )

    out = re.sub(r"\n?<!--\s*\n\s*Template for assemble\.py.*?-->\s*", "\n", shell, flags=re.S)
    if page_body is not None:
        out = re.sub(r"<body>.*</body>", lambda m: "<body>\n" + page_body + "\n</body>", out, count=1, flags=re.S)
    out = out.replace("<!--EV:HTML-ATTRS-->", f' data-ev-theme="{a.theme}"' if a.theme else "")
    out = out.replace("<!--EV:TITLE-->", title)
    out = out.replace("<!--EV:KIT-CSS-->", "<style>\n" + kit_css + "\n</style>")
    out = out.replace("<!--EV:KIT-JS-->", "<script>\n" + kit_js.replace("</script", "<\\/script") + "\n</script>")
    out = out.replace("<!--EV:OVERVIEW-->", overview_html.strip())
    out = out.replace("<!--EV:TABS-->", body)
    Path(a.out).write_text(out, encoding="utf-8")
    print(f"assemble.py: wrote {a.out} ({len(out.encode('utf-8')) // 1024} KB, "
          f"{'standalone ' + tabs[0][0] if a.standalone else ('page: ' if a.page else 'tabs: ') + ', '.join(t[0] for t in tabs)}"
          f"{', ' + str(len(p.warnings)) + ' warning(s)' if p.warnings else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
