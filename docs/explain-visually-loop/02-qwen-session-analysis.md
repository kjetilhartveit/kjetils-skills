# 02 · Where the Qwen run spent its time and tokens

Run: Qwen 3.8 27B FP8 on the GX10 (OpenCode), prompt "move from eslint + prettier to oxlint/oxfmt or Biome …
Explain visually" in fantasy-snooker. **4 h 25 min** wall clock. Opus baseline: ~11 min, 3 chapters.

Re-run the numbers with:

```bash
python docs/explain-visually-loop/tools/analyse_session.py docs/explain-visually-loop/inputs/session-9712ffae-....md --events --calls
```

**Assumptions.** Tokens ≈ characters / 3.6 (prose mixed with code and JSON; JSON-escaped tool inputs are decoded
first). *Generated* = thinking + assistant text + tool-call inputs (decode-bound: 15 tok/s on the GX10).
*Consumed* = tool outputs (prefill; cheap per token, but it fills the context). The export has no per-message
timestamps, but OpenCode session ids encode their creation time, which gives three anchors (session start, five
subagents at +61.5 min, one subagent at +167.3 min). Subagent sessions are not in the export: only their prompt
and their final summary are. Screenshots read as images are not counted (≈1–2k vision tokens each, 28 reads).

## 1. Overview

The decode model holds: in the first 61.5 min the main thread generated ≈51k tokens, which is 57 min at 15 tok/s.
**Generation speed is the bottleneck, so generated tokens ≈ minutes.**

| Wall clock | Lines | What happened | Main generated | Decode min |
|---|---|---|---|---|
| 0 – 61.5 min | 1–5142 | skills, repo, measurements, web research, brief, overview, subagent prompts | 51k | 57 |
| 61.5 – 167.3 | 5142–6203 | 5 chapter subagents in parallel (≈85–90 min, hidden), then fact-check and patches | 15k | 16 |
| 167.3 – 265 | 6203–11429 | decision subagent (hidden), assemble, **screenshot/fix loop on one mobile bug** | 62k | 69 |

Main-thread generated tokens by phase (127,948 total = 142 min at 15 tok/s):

| Phase | Generated tok | % | min @15 | of which thinking | Consumed tok |
|---|---|---|---|---|---|
| Load skills + read kit/contract | 2.9k | 2.3 | 3.2 | 2.7k | 9.7k |
| Repo exploration + measurements (real oxlint/oxfmt/Biome runs, POC) | 11.2k | 8.8 | 12.5 | 9.8k | 11.4k |
| Web research (4 searches, 2 fetches, 9 hand-written fetch scripts) | 22.0k | 17.2 | 24.5 | 17.9k | 28.0k |
| Brief (one 23 KB write + edits) | 8.9k | 6.9 | 9.9 | 2.5k | 0 |
| Overview + before/after template | 4.7k | 3.7 | 5.2 | 2.7k | 0 |
| Subagent prompts (6) + reading their summaries | 10.9k | 8.6 | 12.2 | 1.9k | 4.6k |
| Fact-check + patch chapters (count drift 14→15) | 5.4k | 4.2 | 6.0 | 2.8k | 6.2k |
| Assemble (4 runs) | 1.4k | 1.1 | 1.6 | 0.9k | 0.2k |
| **Verify / screenshot / fix loop** | **60.5k** | **47.3** | **67.2** | **48.8k** | **40.5k** |

By kind: thinking **90.0k (70 %)**, tool inputs 34.4k (27 %), visible text 3.5k (3 %). Consumed: 100.6k.

Hidden work: the five chapter subagents ran ≈85–90 min wall clock (each also ran its own Playwright screenshots,
see L5153–5172). The final page has **134 KB of chapter HTML (~37k tokens) in 6 chapters**, against Opus's
**33 KB (~9k tokens) in 3 chapters**: Qwen wrote about 4× as much page.

Other facts: subagents were used (6, `agent: general`). One context compaction happened at L7162 (≈ +170 min),
mid-fix-loop. Tool calls: 40 shell, 37 read, 28 edit, 12 write, 9 execute, 6 subagent, 5 skill, 4 websearch,
2 webfetch. Most-edited files: `frag-deps.html` 14 edits (fact patches), `frag-story.html` 5 edits (mobile fix),
plus 10 throwaway Playwright scripts (`shot.js`, `diag.js` … `diag8.js`, `verify-final.js`, ≈7k tokens).
The page was never published (OpenCode has no artifact tool); it ended as `/tmp/opencode/oxc-explainer/index.html`.

## 2. Thinking vs output: the 10 biggest sinks

| # | Sink | Gen tok | min | Example |
|---|---|---|---|---|
| 1 | **Pixel-debugging the story chapter's mobile pin** (L6317–11429) | ~55k | ~61 | L9748, one 7.5k-token thought: "Wait, but in diag2 the stick's rect was reported as top:50 … So the screenshot and the probe disagree." |
| 2 | **Fact recaps in thinking** (the same fact list restated 8–10×) | ~25k | ~28 | L919 "Now I have a full picture…", L3328/L4210 "Confirmed:", L4374 "**Facts list (verified):**", L4515 "Final data:", L4659, L4925, L5039 |
| 3 | Web research thinking + bespoke fetch scripts | 22k | 24.5 | 9 `execute` scripts that fetch and strip HTML (L2706–4479); L2714 `TypeError: for...of requires an iterable` → rewrite and retry |
| 4 | Subagent work (hidden) | ≈37k page tokens + their thinking/checks | ≈85–90 wall | 6 chapters; story subagent hand-built a mobile pin that overrode the kit (`position: sticky` against the kit's `position: static`) |
| 5 | Ad-hoc Playwright tooling | ~13k (scripts 7k + setup) | ~14 | L6317 `require(".../node_modules/playwright-core")` fails → 5 calls to locate the pnpm path and the chromium binary (L6361–6484); then diag.js … diag8.js |
| 6 | Re-reading kit internals and digesting them | ~8k gen, 37k consumed | ~9 | kit.css read 2× (14.6k), kit.js (9.2k); L8505 4.4k-token thought "Key findings from kit.css: `.ev-stick { position: sticky; top: max(calc(…` |
| 7 | Subagent prompts restating the brief | 8.9k | 9.9 | L5142–5288: 1.3–1.8k tokens each, "DO THIS IN ORDER: 1. Read …brief.md" followed by chapter content that is already in the brief |
| 8 | Brief written in one go | 6.3k | 7.0 | L4909: a 23 KB brief (Opus wrote ~82 lines) |
| 9 | Count drift and patching | 5.4k | 6.0 | L5329 "the brief says '14 packages' but package.json has 15"; 14 edits to frag-deps, edits to complex/code/overview/brief |
| 10 | Chasing a false bug (Playwright artefact) | inside #1, ~15k | ~17 | L10093 "`visualViewport: { offsetTop: 197 }` … This is the smoking gun": smooth scroll + `isMobile` emulation, not a page bug |

Deliberation markers ("Wait", "Hmm", "Actually", "Let me reconsider") appear **54× before assembly and 211× after**:
the fix loop is mostly the model arguing with screenshots.

## 3. Failure modes specific to the weaker/slower model

Haiku may hide these (it thinks less and decodes ~10× faster); the GX10 pays for every one of them.

1. **Visual reasoning by hand.** It reads PNGs and reconstructs pixel positions in prose ("y=0-8: sliced '65 s' …
   y=430-640: step 4 card"), then disagrees with its own DOM probes. Each round costs 2–7k thinking tokens.
2. **Writes tools instead of using them.** 10 throwaway Playwright scripts, 9 fetch scripts, with environment
   discovery each time (pnpm store path, headless shell binary).
3. **Thinking as a notebook.** Facts are recapped in thinking rather than written once to a file; at 15 tok/s a
   2.5k-token recap is ~3 min, and it happened ~10 times.
4. **Over-scoping.** "When relevant" was read as "always": 6 chapters plus overview, ~4× Opus's page size.
   Fact-gathering was also deep (custom-rule POC under oxlint, migration runs); that was valuable and Opus did
   the same, so the problem is the recaps around it, not the measurements.
5. **Hand-counted numbers drift** across brief, prompts and fragments (14 vs 15 packages, 12 vs 13 removals).
6. **Overrides the kit when told to "override per skill".** The story fragment re-implemented mobile pinning,
   producing a 492 px panel on an 844 px phone with steps hidden behind it.
7. **Context compaction mid-task.** After L7162 it resumed from a summary, re-read frag-story.html (6.7k),
   kit.css (7.3k) and kit.js (9.2k) and re-derived the layout from scratch.
8. **Small coding slips with expensive retries** (Promise.allSettled destructuring, wrong module path): each retry
   costs a full think-write-run cycle.
9. **Weak stopping rule.** "Look at the page once … Don't iterate on polish" did not stop it: it ran 3 more verify
   rounds after the fix (vf-*.png, diag8, full-page error scan at L11376).

## 4. Biggest potential gains (ranked)

Minutes are main-thread decode time at 15 tok/s unless noted as wall clock.

| # | Change | Saves (est.) | Cause in the skills today |
|---|---|---|---|
| 1 | **Kit component for phone pinning** (e.g. `ev-side ev-side--pin` with a capped panel height, steps' `scroll-margin-top` set from it, compact-panel hooks), and forbid fragments from overriding `.ev-stick` positioning | most of the 60k-token fix loop: **~45–55k tok, ~50–60 min** | `explain-with-storytelling/SKILL.md` "On phones, pin the graphic at the top …"; `FRAGMENT-CONTRACT.md` L98 "Stacks below 900px (override the stacking per skill, e.g. pin the graphic at the top on phones)" makes every agent hand-roll it |
| 2 | **Deterministic check tool in the kit** (promote `tools/shoot.py`: phone/desktop × dark/light, forces each `ev-step` without smooth scroll, reports overflow, panel/step overlap, console errors as JSON). The skill says: run it once, fix only listed errors, at most one re-run, no image-by-image pixel reasoning | ~13k tok of script writing + the false-bug chase ~15k: **~25k tok, ~28 min** (overlaps with #1) | `explain-with-storytelling` "Check with screenshots at several scroll positions (Playwright, or a page that forces each step)"; `explain-visually` §5 "Look at the page once (screenshot …)" gives no tool and no stopping rule |
| 3 | **Fewer, smaller chapters.** Default to Overview + Story + one before/after + Decision (≤4); per-chapter budget (e.g. ≤5 steps, ≤4k tokens HTML); before/after chapters as **JSON data rendered by a kit template** instead of hand-written HTML | subagent wall time ≈85 → ~35–45 min: **~40–50 min wall**; plus fewer patches | `explain-visually` §3 six-chapter table with "when relevant"; §4 "Build the three before/after chapters together from one template plus data" (it wrote a markdown template, not data) |
| 4 | **Facts ledger instead of recaps.** Append facts with source to `facts.md` as they're found ("write it down, don't restate it in thinking"); key numbers in a small `facts.json` computed by a command (e.g. counting devDeps), referenced by chapters | ~12–15k tok of recaps + 5k of patches: **~17k tok, ~19 min** | `explain-visually` §1/§2: gather everything, then write the brief afterwards, so facts live in thinking until L4909 |
| 5 | **Budgeted research + a fetch helper.** "At most 3 searches and 3 fetches; stop when every chapter's claims have a source." Ship `fetch_text.py URL` (HTML → trimmed text) so no bespoke fetch scripts | ~10k tok, **~11 min** | `explain-visually` §1 "Gather enough relevant information to back every statement" has no budget |
| 6 | **Short, templated subagent prompts.** Skill provides the prompt: "Read brief.md §NAME, load explain-with-X, write frag-NAME.html, run assemble.py --standalone, no screenshots." Content stays in the brief | ~6k tok, **~7 min**; subagents skip their own Playwright runs (part of #3's wall time) | `explain-visually` §4 "each given the brief, its explain-with-* skill, the kit path …" invites long custom prompts; storytelling skill's screenshot line makes each subagent verify itself |
| 7 | **Never read `kit.css` / `kit.js`.** The contract's cheat sheet is the API; add the few facts agents went looking for (sticky offsets, `--ev-sticky-top`, phone behaviour). Coordinator doesn't load chapter skills itself | ~8k tok gen (~9 min), ~40k consumed → less likely to hit compaction (and its re-reads) | `explainer-kit/SKILL.md` "Files" table lists kit.css/kit.js without saying "don't read"; agents read them to debug layout |
| 8 | **Smaller brief.** Cap at ~1 page: answer, key numbers (from facts.json), per-chapter bullets with source ids | ~3–4k tok, **~4 min** | `explain-visually` §2 doesn't size the brief |

Rough total if 1–7 land: main thread ~128k → ~35–45k generated tokens (~40–50 min) and subagent wall time
roughly halved, so **~4.4 h → ~1.5 h** on the GX10 without dropping the measured facts or the decision chapter.

## 5. Caveats

- Thinking vs. visible text is split on the export's 3-blank-line gaps; it's approximate but visible text is only
  3 % either way.
- Phases are assigned per tool call; thinking is attributed to the phase of the tool output it digests.
- Subagent token counts are invisible; their cost is inferred from wall-clock anchors and the final page size.
