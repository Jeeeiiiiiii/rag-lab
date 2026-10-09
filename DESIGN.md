---
name: RAG Lab Wire Desk
description: One question filed to three retrieval wires, read live from the lab and laid out as teletype copy on a newsroom wire desk.
colors:
  desk: "#232B25"
  desk-raised: "#2C362F"
  desk-rule: "#44514A"
  chalk: "#ECE7DA"
  chalk-dim: "#AEB7AB"
  paper: "#F2E4A8"
  paper-rule: "#CDBB74"
  ink: "#1C1B19"
  ink-dim: "#5A5032"
  pencil: "#2B58A6"
  pencil-wash: "rgba(43, 88, 166, .14)"
  pencil-desk: "#7FA6E6"
  pencil-desk-lit: "#A9C6F2"
  stamp: "#C3352A"
  stamp-ink: "#F5B7B0"
  stamp-deep: "#A3281F"
  slug-white: "#FFFFFF"
  src-mesh: "#1F6F78"
  src-order: "#8F6210"
  src-pipeline: "#6B4C9A"
  src-finops: "#3B7A37"
  src-signal: "#3D5A80"
  src-onboarding: "#6B6257"
typography:
  display:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, Arial Narrow, sans-serif"
    fontSize: "2.75rem"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0.14em"
  copy:
    fontFamily: "Courier Prime, Courier New, ui-monospace, monospace"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  body:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  label:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.08em"
  slug:
    fontFamily: "Libre Franklin, Franklin Gothic Medium, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.06em"
rounded:
  paper: "1px"
  control: "2px"
  stamp: "3px"
spacing:
  xs: "6px"
  sm: "10px"
  md: "14px"
  gap: "22px"
  page: "28px"
  section: "40px"
  wire-gutter: "56px"
components:
  wire-strip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.copy}"
    rounded: "{rounded.paper}"
    padding: "4px 30px 10px"
  copy-piece:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.copy}"
    padding: "12px 6px 13px"
  copy-piece-lit:
    backgroundColor: "{colors.pencil-wash}"
  rank-first:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    padding: "0 4px"
  source-slug:
    backgroundColor: "{colors.src-mesh}"
    textColor: "{colors.slug-white}"
    typography: "{typography.slug}"
    rounded: "{rounded.paper}"
    padding: "3px 5px 2px"
  assignment-slip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "50px"
  button-file:
    backgroundColor: "{colors.pencil}"
    textColor: "{colors.slug-white}"
    rounded: "{rounded.control}"
    padding: "0 22px"
  button-desk:
    backgroundColor: "{colors.desk-raised}"
    textColor: "{colors.chalk}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  button-desk-quiet:
    backgroundColor: "{colors.desk}"
    textColor: "{colors.chalk}"
    rounded: "{rounded.control}"
    padding: "9px 16px"
  depth-toggle-pressed:
    backgroundColor: "{colors.chalk}"
    textColor: "{colors.desk}"
    width: "42px"
  hold-stamp:
    textColor: "{colors.stamp-deep}"
    typography: "{typography.headline}"
    rounded: "{rounded.stamp}"
    padding: "8px 11px 7px"
  verdict-pass:
    backgroundColor: "{colors.chalk}"
    textColor: "{colors.desk}"
    typography: "{typography.headline}"
    rounded: "{rounded.paper}"
    padding: "5px 8px 4px"
  verdict-fail:
    backgroundColor: "{colors.stamp}"
    textColor: "{colors.slug-white}"
    typography: "{typography.headline}"
    rounded: "{rounded.paper}"
    padding: "5px 8px 4px"
  galley:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.copy}"
    rounded: "{rounded.paper}"
    padding: "16px 20px"
---

# Design System: RAG Lab Wire Desk

## Overview

**Creative North Star: "The Wire Desk"**

A question is a story assignment on a newsroom wire desk. Three wires file at once: DENSE (meaning), BM25 (exact words), and between them THE EDITOR, the hybrid that merges the two by rank. Each wire's take arrives as a canary teletype strip with sprocket feed holes down both margins, lying on a dark green-black desk blotter. The editor works with a blue pencil: pencil lines join the same chunk across wires, ring the right copy, and write the fusion arithmetic under each merged piece. Copy the guard flagged gets a red HOLD FOR LEGAL rubber stamp and its text struck through; copy the editor did not run is marked spiked; every take ends with "— 30 —".

Density is a working desk's: three full columns of copy side by side, every piece carrying rank, source slug, score on its own scale, section and a clamped excerpt. There is one copy size. Rank is carried by weight, case, reversal (the first piece's rank is printed reversed, paper on ink) and rule (dashed rules between pieces, double rules between desk zones), never by a bigger font. Colour is material, not decoration: the desk, the paper, the ink, the pencil and the stamp each are a physical thing on a desk, and the six source slugs are fixed codes like a wire service's.

The world is its own: distinct from order-lab's split-flap departures board (black board, gold flap ink, condensed signage) and from mesh-lab's grey-blue bench instrument. It refuses the category default of a chat box with a sources panel and a metrics table.

**Key Characteristics:**
- Canary paper strips (with sprocket margins) on a dark green-black desk; paper lifts off the desk, desk controls stay flat.
- One type size (15px) for everything except the masthead; rank by weight, case, reversal and rule.
- Courier Prime for all filed copy; Libre Franklin for the desk's own signage and prose.
- Blue pencil is the editor's hand: joins, the right-copy ring, fusion sums, the one filled button.
- Red is reserved for the hold stamp and failure; source colours are fixed per corpus file.
- One motion moment: copy feeds in, then the pencil draws. The resting state is always fully visible.

## Colors

A green-black desk carrying canary paper, black ink and a blue pencil, with stamp red held back for the guard and for failure.

### Primary
- **Canary Copy Paper** (paper): the teletype strips, the assignment slip, the answer galley. Also the one warm accent on the desk itself: "Wire Desk" in the masthead, the editor wire's heading, the "Golden" note key, the running indicator, and changed or gated table rows (gated rows also take a 7% paper wash). **Paper Rule** (paper-rule) is the dashed rule between pieces, the sprocket margin rule, and the slip's label divider.

### Secondary
- **Editor's Blue Pencil** (pencil): the editor's marks on paper. The "Editor ranked it #N" and fusion-sum lines, the right-copy ring, citation labels in the galley, the slip caret and focus ring, the focus outline on paper, text selection, and the "File story" button fill. **Pencil Wash** (pencil-wash) tints every piece of the same chunk when one is hovered or opened.
- **Pencil on the Desk** (pencil-desk): the join lines drawn across the dark desk between strips. A lighter tint than the paper pencil so the line keeps better than 5:1 against the desk, like graphite catching the lamp. A lit join thickens from 2.5 to 4 and lightens to **Lit Pencil** (pencil-desk-lit).

### Tertiary
- **Hold Stamp Red** (stamp): the held piece's strikethrough (at 60% alpha, 1.5px) and the "Gate fails" verdict fill.
- **Stamp Ink on Paper** (stamp-deep): the HOLD FOR LEGAL stamp itself, border, double rule and lettering, 5.9:1 on canary so the 15px stamp text passes.
- **Stamp Ink on the Desk** (stamp-ink): red's legible form on the dark desk: the HELD ledger key, error banners (over a 10% stamp wash with a 55% stamp border), the "API not answering" status, intake and audit failure text.

### Source Slugs
Fixed, one per corpus file, printed as a white code block before the label: **MESH** (src-mesh, mesh-lab), **ORDR** (src-order, order-lab), **PIPE** (src-pipeline, pipeline-lab), **FNOP** (src-finops, finops-agent), **SGNL** (src-signal, signal-desk), **ONBD** (src-onboarding, onboarding-notes). An unknown file falls back to its first four letters on the onboarding grey.

### Neutral
- **Desk Blotter** (desk): the page, the sprocket holes punched through the paper, the pressed depth button's text, the pass verdict's text.
- **Raised Desk** (desk-raised): desk buttons, and hover fill on lessons and unpressed depth buttons.
- **Desk Rule** (desk-rule): every rule and border on the desk: control borders, ledger and table rows, the masthead's and drawers' 3px double rules, scrollbar thumb.
- **Chalk** (chalk): primary text on the desk, bold figures in prose, code on the desk, the pressed depth button and pass verdict fill, the global focus outline.
- **Chalk Dim** (chalk-dim): the lede, wire descriptions, notes, table headers, ledger keys, footers, timings.
- **Ink** (ink): all copy on paper; the reversed first-rank block.
- **Ink Dim** (ink-dim): section lines (italic), placeholders, empty strips, spiked lines, "— 30 —".

### Named Rules
**The Stamp Red Rule.** Red marks only the guard and failure: the HOLD FOR LEGAL stamp, the held strikethrough, the HELD ledger key, the failing gate, and error text. Never a brand colour, a highlight, or a warning that is merely waiting.

**The Two Pencils Rule.** The pencil is one colour in two tints: pencil on paper, pencil-desk on the desk. Never draw a paper-pencil line on the desk; it falls below a readable contrast.

**The Fixed Slug Rule.** Each corpus file keeps its colour and four-letter code everywhere it appears (wires, ledger, intake table). Never reassign or cycle source colours by position.

## Typography

**Display Font:** Libre Franklin (with Franklin Gothic Medium, Arial Narrow, sans-serif), self-hosted variable 400-900
**Body Font:** Libre Franklin, same stack
**Label/Mono Font:** Courier Prime (with Courier New, ui-monospace, monospace), self-hosted 400, 400 italic, 700

**Character:** Courier Prime is the teletype: everything a wire files, the answer galley, the questions and code are typewriter copy. Libre Franklin is the newsroom's signage and the editor's plain voice, gothic and compact. Tabular figures run page-wide so ranks, scores and timings never jitter.

### Hierarchy
- **Display** (800, 2.75rem, 2.2rem at 720px and below, line-height 1): the masthead only, "RAG Lab" in chalk and "Wire Desk" in paper.
- **Headline** (800, 15px, 0.14em, uppercase): wire names, section heads ("What ran", "Attribution", "Intake", "Accuracy audit"), the stamp, verdicts.
- **Copy** (Courier Prime 400, 15px, 1.5): every piece on a strip, the galley, questions in miss lists, hashes. Rank, slug label and score in 700; section line in italic ink-dim; excerpt clamped to four lines until the piece is opened.
- **Body** (400, 15px, 1.5): lede (112ch), notes (64-92ch), status, footers; emphasis in 600 chalk.
- **Label** (700, 15px, 0.08em, uppercase): the slip's ASSIGNMENT label, ledger keys, table headers, the "Golden" note key.
- **Slug** (700, 15px, 0.06em): the four-letter source code in its colour block.

### Named Rules
**The One Copy Size Rule.** Everything below the masthead is 15px. Hierarchy comes from weight (400/600/700/800), case and tracking, reversal (the first rank is paper on ink), italic for the section line, and rules. Never introduce a second text size to rank something.

**The Two Hands Rule.** Filed copy is Courier Prime; the desk's signage, controls and explanations are Libre Franklin. A string the retriever or answerer produced is typewriter; a string the page wrote to explain it is gothic.

## Layout

A single centred column (max 1360px, padding 26px 28px 48px) in fixed order: masthead (title and dateline left, desk status right, closed by a 3px double rule), lede, error banner, the assignment row, known-answer lessons, the golden note, the three wires, the run (answer and attribution), the drawers (intake and audit, opened by a 3px double rule), colophon.

The assignment row is a grid of `1fr auto auto`: the paper slip, the Top 3/5/8 depth toggle, and "File story". The wires are three equal columns with a 56px gutter, the editor in the middle so pencil joins run from DENSE and BM25 inward. The run splits 1.55fr / 1fr; the drawers 1fr / 1.25fr; both with 40px gaps. Zone spacing sits at 20-40px; the working gap is 22px.

At 1100px and below the wires stack into one column (28px gap), the pencil layer is removed, and each piece's own line carries the join instead ("Editor ranked it #N" or "Spiked"); the run and drawers stack. At 720px and below: page padding 20px 16px 36px, the masthead and status stack, the slip takes the full row above the toggle and button, sprocket margins narrow to 14px, the ledger becomes single-column, and low-value table columns (hashes, the misses count) hide because the desktop and the disclosure carry them.

## Elevation & Depth

Paper lifts; the desk is flat. Every paper object (strip, slip, galley) sits on the blotter with a short contact line and a soft drop beneath it. Desk controls, rules, tables and the ledger have no shadow at all. The stamp's double border is drawn with inset shadows and pressed into the paper with multiply blending and an ink-texture filter; the pencil lines carry a graphite displacement filter. Those are textures of the marks, not elevation.

### Shadow Vocabulary
- **Strip on the desk** (`box-shadow: 0 1px 0 rgba(0,0,0,.4), 0 10px 22px -12px rgba(0,0,0,.7)`): teletype strips.
- **Slip on the desk** (`box-shadow: 0 1px 0 rgba(0,0,0,.35), 0 6px 14px -8px rgba(0,0,0,.6)`): the assignment slip; on focus the contact line becomes a 2px pencil ring.
- **Galley** (`box-shadow: 0 10px 22px -12px rgba(0,0,0,.7)`): the answer galley.
- **Stamp double rule** (`box-shadow: inset 0 0 0 2px #F2E4A8, inset 0 0 0 3.5px #A3281F`): inside the stamp's 2.5px border.

### Named Rules
**The Paper Lifts Rule.** Only paper casts a shadow. Anything made of the desk (buttons, toggles, tables, drawers) stays flat and is separated by desk-rule lines.

## Shapes

Paper is cut, not rounded: 1px corners on strips, pieces, slug blocks, the galley and verdicts. Controls are 2px; the banner and stamp 3px. The stamp sits rotated -3deg from its left edge, in the flow so it never covers copy. Strips have sprocket margins: an 18px column each side with a hole punched every 22px (desk-coloured, 3.4px radius) behind a 1px dashed paper-rule. Rules are a vocabulary: dashed between pieces on paper and between misses, solid 1px between desk rows, 3px double between desk zones. The spike is a drawn SVG spindle; the right-copy mark is a hand-drawn pencil ellipse.

## Components

### Wire Strip (signature)
A canary strip with sprocket margins holding one wire's take, ranked 01..k. Each piece is a full-width button: line one is the two-digit rank, the source slug and label (`file#chunk`, never with ".md"), and the score right-aligned on its own scale (dense 3 decimals, BM25 2, editor 4); then the italic section line; then the excerpt. The take closes with "— 30 —" centred in 700 ink-dim, 0.2em tracking. The wire heading (headline type, editor in paper) carries its timing, and a one-line chalk-dim statement of its scale sits under it; a footer says where the right copy was filed.
- **Hover:** 4.5% ink wash on the piece; every piece and pencil join for the same chunk lights (pencil wash, thicker lighter line).
- **Open:** click expands the excerpt fully and keeps that chunk lit.
- **First rank:** the rank number reversed, paper on ink.

### Pencil Marks
Under each piece: on the editor wire, the fusion arithmetic in pencil ("dense #2 + BM25 #1 → 1/62 + 1/61 = 0.0325", figures bold); on the side wires, "Editor ranked it #N" in pencil, or a spike glyph and "Spiked: the editor did not run it" in ink-dim. Relevant copy gets "RIGHT COPY" in pencil uppercase ringed by a hand-drawn ellipse. Joins are curves from strip edge to strip edge, level with each piece's slug line.

### Hold for Legal Stamp
Stamp-red uppercase headline type in a 2.5px border with an inner paper gap and inner rule, rotated -3deg, multiplied into the paper through an ink filter at 90% opacity. The held piece's excerpt is struck through in red. The same chunk shows as a HELD row in the attribution ledger.

### Assignment Slip and Controls
- **Slip:** a paper strip (50px min height) with an uppercase ASSIGNMENT label behind a paper-rule divider and a Courier Prime input; caret in pencil.
- **File story:** the only filled button: pencil fill, white 700 text, 22px side padding, press scale 0.97 over 140ms; "Filing…" at 60% opacity while busy.
- **Depth toggle:** a desk-rule bordered segmented group (Top 3/5/8, each 42px min); pressed is chalk with desk text. Changing it re-files every wire.
- **Desk buttons:** raised-desk fill, 1px desk-rule border, 600 weight, 9px 16px; hover border to chalk-dim, press 0.97. Quiet variant is transparent at 500.
- **Lessons:** transparent bordered chips ("**Exact identifier** · dense loses it") with a raised-desk hover, plus a select of all golden questions.
- **Focus:** global 2px chalk outline at 3px offset; pencil on paper.

### Attribution Ledger
A list with a 9ch key column (uppercase label, chalk-dim; HELD in stamp-ink) and a value of slug plus section note, rows split by desk-rule lines. The "Golden" note above the wires uses the same key/value form with the key in paper.

### Audit and Intake Tables
Uppercase chalk-dim headers, desk-rule rows, right-aligned numerics, Courier Prime hashes. Changed files and the gated row read in paper. The verdict is a headline-type block: "Gate passes" chalk on desk, "Gate fails" white on stamp red, with the arithmetic beside it. Misses and the guard check sit in disclosures.

### Motion
One moment per filing. Copy feeds off the teletype: each piece unclips top to bottom and settles 6px down over 340ms on cubic-bezier(.16, 1, .3, 1), staggered 110ms per wire and 55ms per piece. Then the pencil draws: each join's dash offset runs to zero over 550ms, from 480ms plus 70ms per join, via the Web Animations API with fill backwards and nothing held after the end, so the resting state is the plain, always-visible line. Reduced motion skips both and shows the resting state. State transitions are 120ms background or border changes.

## Do's and Don'ts

### Do:
- **Do** keep every string below the masthead at 15px; rank with weight, case, reversal and rule.
- **Do** set retrieved and answered text in Courier Prime and the page's own explanations in Libre Franklin.
- **Do** show labels as `file#chunk` without ".md", identically on wires, galley and ledger.
- **Do** use pencil-desk (not pencil) for any mark drawn on the dark desk.
- **Do** label every score with its scale and keep each wire's decimals fixed (3, 4, 2).
- **Do** replace pencil joins with each piece's "Editor ranked it #N" / "Spiked" line wherever the wires stack (1100px and below).
- **Do** end motion on the visible resting state; never leave a mark that only appears through animation.

### Don't:
- **Don't** use red for anything except the hold stamp, held strikethrough, HELD key, gate failure and error text.
- **Don't** reassign a source's colour or code, or give a new source a colour already taken.
- **Don't** cast shadows from desk controls, tables or drawers; only paper lifts.
- **Don't** let the stamp overlap copy; it sits in the flow above the struck text.
- **Don't** collapse the three wires into a chat box with a sources panel and a metrics table.
- **Don't** add a second text size to rank or emphasise something.
