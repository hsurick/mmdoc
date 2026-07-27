---
title: mmdoc — Working Notes
date: 2026-06-29
status: background & history — build underway; current plan in OVERVIEW.md (see doc-hierarchy note below)
summary: Notes capturing the problem, how multimodal input actually works at a low level, the design decisions we've settled, and open questions / next steps for mmdoc.
---

# mmdoc — Working Notes

`mmdoc` = **multimodal doc**. A folder-based document format that bundles a Markdown
file with co-located image files, designed so AI agents can read interleaved
text-and-image research documents using existing file-read tools — no harness changes.

There is a fuller external spec by Daniel Hsu (private). These notes are the
project's working understanding, including the low-level mechanics and the
decisions reached.

**Doc hierarchy (who wins on conflict):** `../FORMAT.md` is **normative** for the format;
`CLI.md` for the CLI design; `OVERVIEW.md` owns the plan/build order. NOTES.md is
background and history — where a passage here disagrees with those, they win.

---

## 1. The problem

Research docs contain **text + tables + images** (screenshots, slides, diagrams).
Markdown handles text and simple tables, but **cannot contain images** — only
reference them. AI agents are increasingly the primary readers of research docs, and
the image gap causes several distinct problems:

- **Search blindness.** `grep`/`rg` only matches text, so meaningful content trapped in a
  screenshot or slide is invisible to search.
- **Reasoning blindness.** Reading `![framework](img-001.png)` gives the agent no visual
  understanding unless it takes a separate action to read the image.
- **Token waste & cost.** Handing an agent a `.docx` or a base64-in-Markdown file burns
  huge token counts (see §2) — often for content the model *still can't see*. Storing
  images as files read on demand means you only pay for the image when you actually need it.
- **No home for rich paste (the original pain).** Copying interleaved text+images from
  Google Docs / Notion has nowhere to land: Markdown can't hold the images, and pasting
  into a terminal or agent input strips everything but plain text (see §2). There is no
  format that captures "rich text + its images" from the clipboard.
- **Lossy rich-format ingestion.** Converting a `.docx`/Google Doc to Markdown drops the
  embedded images entirely (see §2, DOCX), so the visual content is lost on the way in.

Concrete origin: a multimodal Google Doc copy-pasted into Claude Code (or into a `.md`)
loses its images — text survives, images vanish or become broken references.

The agent's normal read loop is **search (rg) → read a line range → reason**. The image
gap breaks the reason step and makes visual content invisible to the search step.

### Alternatives the spec considered and rejected

- **Base64 data URIs inline in Markdown** — enormous files, unreadable, useless git diffs
  (and the token trap from §2).
- **Separate asset dirs with ad-hoc naming** — no standard convention, so every project
  invents its own; agents don't know where images live or how they map to the text.
- **Rich formats (DOCX, PDF, HTML)** — not agent-friendly: hard to search, partially read,
  or diff.
- **Notebook formats (`.ipynb`)** — JSON that can inline images, but oriented around code
  execution, awkward for narrative prose.

---

## 2. How multimodal input actually works (the mechanics we nailed down)

This section corrects the original mental model and is the foundation for every design
decision below.

### Content type is declared at the API boundary, never discovered

**Whether something is "an image" to the model is *declared by a label* at the
client→server boundary — it is never *discovered* by the model from the content.**

- Bytes labeled image → go to the vision encoder (the model's "eye").
- Text labeled text → go to the text tokenizer (the model's "reader").
- A base64 image labeled text → is just a very long, useless "word."

### End-to-end trace: screenshot → Claude

1. **Clipboard (macOS pasteboard).** Holds the **raw image bytes** tagged with a type
   like `public.png` (e.g. `89 50 4E 47 …` = the PNG header). **No base64 here.**
   (Copying from Google Docs instead puts *multiple* flavors on the clipboard at once —
   `public.html`, `public.utf8-plain-text`, sometimes `public.tiff`. Markdown editors
   grab the plain-text flavor → images dropped.)
2. **Claude Code app (client).** Reads those bytes, **base64-encodes them** (base64 =
   a way to stuff binary bytes into a JSON text field; it inflates payload ~33% — that's
   *bandwidth, not tokens*), and **labels the block `"type": "image"`**. The base64
   string exists only for this one client→server hop.
3. **Anthropic server (backend).** Reads each content block's `type`:
   - `"type": "text"` → text tokenizer.
   - `"type": "image"` → **base64-decode back into the original PNG bytes**, then run
     through the **vision encoder** (splits the image into patches, each patch → a
     vector). The model **never sees the base64 text** — it's decoded at the door.
4. Image-vectors + text-vectors are concatenated into one sequence the model reads.

**Image token cost is set by resolution, not base64 length:** roughly
`tokens ≈ (width_px × height_px) / 750` for Claude. A 400KB and a 4MB base64 of the
same-resolution image cost the same.

### The clipboard paste problem (the original pain) and how to dodge it

The system clipboard holds the same content in **several flavors at once** — e.g. copying
from Google Docs gives `public.html` (rich, with image refs), embedded image bytes, *and*
`public.utf8-plain-text`. **A terminal (and Claude Code's text input) requests only the
plain-text flavor and ignores the rest** — which is why pasting a Google Doc into the input
box loses the images and formatting ("only some stuff comes through").

You cannot fix this from inside the paste-into-terminal path. The dodge: **don't read the
clipboard through the terminal — read the OS pasteboard directly** from a CLI command/skill
(`osascript` / `NSPasteboard` / `pbpaste -Prefer` on macOS, `xclip`/`wl-paste` on Linux),
which exposes *all* flavors including `public.html` and image bytes. The command extracts
text + images and writes the folder; the terminal's plain-text limitation never applies.
(A terminal keybind like Ghostty's image-paste is the terminal-specific version of the same
idea; the direct-pasteboard command is the portable version.)

**Empirically verified (2026-07-05, real Google Doc with one image copied on this Mac):**
- Pasteboard flavors: `«class HTML»` **2,210,464 bytes** vs plain text **183 bytes** — the
  terminal paste discards 99.99% of the copy. **No standalone image flavor**, so Claude
  Code's Ctrl+V can't see it either.
- The HTML carries the image **inline as a base64 data-URI** (`data:image/png;base64,…`) —
  NOT a remote googleusercontent URL. **No download, no auth, no expiring links**: the bytes
  are already on the machine.
- Full pipeline proven with only existing built pieces: pasteboard HTML → `pandoc -f html
  -t gfm-raw_html` (keeps the data URI) → our `extract_base64_images` → valid mmdoc
  (1.66MB PNG extracted, signature valid, `validate` passes, image readable down the vision
  path). `paste`/`clip` is de-risked: it's plumbing around code that already works.
- Expected artifacts to handle in `paste`: Google's missing alt text (empty `![]` — the
  agent writes alt text itself when it reads the image; `describe` was later dropped) and
  Pandoc's `\` hard-line-break clutter (strip in post).

### Why base64-pasted-as-text is the worst case

If `![x](data:image/png;base64,iVBOR…)` is literal text *in a `.md` file*, then `Read`
returns it as a string → block is `"type": "text"` → the whole base64 goes through the
**text tokenizer** (~170k–230k garbage tokens for a 500KB image) **and the model still
can't see the image.** There is no "recognize and auto-decode" step — the fork already
happened at the label. Worst of both worlds: huge token tax + blindness.

### Why PDF works but DOCX doesn't

Not a fundamental capability gap — it's which pipeline was built, plus one structural
difference:

- **PDF:** the API accepts a `document` block; the server rasterizes **each page to an
  image** *and* extracts the text layer, feeding both. PDFs have **fixed pages**, so
  "render page 3" has one obvious answer.
- **DOCX:** **no DOCX block type** exists — no server pipeline. A DOCX is a **zip of XML**
  (`word/document.xml` = text, `word/media/image1.png` = pictures). Cheap conversion
  grabs the text and **drops the images**. DOCX also **reflows** (no fixed pages), so
  "rasterize each page" isn't even well-defined. Same wall the Google Doc paste hits.

### The multimodal input gap (forward-looking, from the spec)

Models process text and images through **separate encoders that project into one shared
latent space** — by the time the transformer reasons, text tokens and image tokens are
just vectors in the same space. So a "native multimodal document" input type (a container
of interleaved text+images deserialized straight into the model's content-block sequence)
is architecturally feasible, but **no provider offers one for *generation* today** — you
must assemble the interleaving manually via content blocks.

- **Gemini Embedding 2** (Mar 2026) moves this way for *embedding*: interleaved text /
  images / PDFs / audio / video in one request → one shared vector space.
- **Lee et al., "Unified Multimodal Interleaved Document Representation for Retrieval"**
  (arXiv 2410.02729, Oct 2024) — embed documents holistically with interleaved modalities;
  splitting into text-only passages loses cross-modal context.

**Where mmdoc fits:** today the tooling assembles content blocks from the folder; if a
"native multimodal document" input type ever ships, the mmdoc folder is a clean
serialization target for it.

---

## 3. File vs folder, and how the OS tells them apart

### File-vs-folder is a stored type flag, never inferred from the name

- **Filesystem (macOS/Linux):** every entry's **inode** has a type bit
  (`S_IFDIR` = directory, `S_IFREG` = file), set at creation (`mkdir` vs `creat`).
  `ls -l` shows `d` vs `-`. The name/extension is irrelevant — you can have a folder
  named `notes.txt` and a file named `Makefile`.
- **Git/GitHub:** tree entries carry an explicit **mode** — `040000` = directory (tree),
  `100644` = file (blob). GitHub renders folder-vs-file from that mode, never from the
  name's dot.
- **Windows/NTFS:** a `FILE_ATTRIBUTE_DIRECTORY` bit; same idea.

**Extensions are a higher-layer naming convention** apps use to guess *a file's contents
and default handler* — applied *after* the file/folder question is already settled.

### The macOS bundle exception

`.app`, `.pages`, etc. **are** directories, but Finder *draws* them as opaque
single-file bundles. Finder decides this by asking **Launch Services** whether the
extension is a registered *package* type (or whether the folder's bundle bit is set) —
**not** the filesystem, which still says "directory."

We verified on this Mac that `test.mmdoc/` is treated as a **plain browsable folder**:
- `ls -ld` → `drwxr-xr-x` (leading `d` = directory)
- `mdls kMDItemContentType` → `(null)` (nothing claims `.mmdoc` as a package)
- bundle bit → `0`

So an unregistered `.mmdoc` folder is **already navigable in Finder with zero setup**.
(The external spec's claim that it's opaque without registration did **not** hold here.)

### GitHub rendering: no custom renderer needed

Because an `mmdoc` is a **folder of standard files**, GitHub already handles it:
clicking the folder lists its contents; a `README.md` inside **auto-renders** (an
`index.md` does *not* auto-render — only file listing), and **relative image links
(`![alt](img-001.png)`) display inline.** A *single-file* format would have needed every
site to build a custom viewer — which is exactly the trap the folder approach avoids.

**Decision (2026-06-30):** we chose `index.md` as the entry file for canonical-document
semantics, accepting that GitHub shows a file listing first (one extra click) rather than
auto-rendering. Revisit only if free auto-render ever outweighs the naming.

---

## 4. Decisions settled

1. **Folder, not a single file.** The only shape where each image keeps its own
   on-demand trip to the vision encoder *while* text stays greppable and git-diffable.
   Any single-file bundle is either an opaque zip (unsearchable/undiffable) or base64
   text (the token trap).
2. **Solve at write-time, not read-time.** Convert a doc into the folder shape **once**
   when it enters the repo. Benefits every future tool/agent (grep, git, any harness)
   forever. Read-time conversion redoes work every read and helps nobody else.
3. **A skill is the right front door — to *manufacture* the folder, not replace it.**
   A skill runs inside the agent loop *above* the API label boundary, so it **cannot**
   change how images are ingested or make base64 "decode in the model's head." Its only
   power is **filesystem surgery**: explode a doc into loose image files + Markdown.
   Structure: `skill (trigger/instructions) → script (unzip / download / strip base64)
   → folder (the mmdoc output)`.
4. **Name: `mmdoc`** (multimodal doc). A name should advertise the *novel* capability,
   not the substrate (`mddoc` reads as "just markdown" and collides with `.doc`).
   Project dir renamed `/Users/work/mddoc` → `/Users/work/mmdoc`.
5. **The `.mmdoc` extension is optional polish.** Add it only for `**/*.mmdoc` glob /
   tooling identification. Harmless on macOS (plain folder, no registration). A bare
   `foo/` + `README.md` is the most bulletproof, renders everywhere today.

### Decisions locked (2026-06-30)

- **Entry file = `index.md`** (not `README.md`) — canonical-document semantics; accept the
  extra GitHub click (no auto-render) over README's "project doc" connotation.
- **Language = Python** for the CLI — best docx / HTML / image / clipboard libraries.
- **Architecture = a standalone `mmdoc` CLI wrapped by a thin skill** — humans/CI can run it
  directly; the skill just chooses subcommands.
- **Extra tools in scope:** `fetch` (Google Docs API import), `validate`/lint, `export`
  (reverse path). Dropped `pack`/`unpack` for now.
- **Convert-before-read guard (agent skill):** when handed a base64-`.md`, `.docx`, or Google
  Doc, the skill runs `normalize`/`fetch` *first* and reads the resulting mmdoc — never the raw
  bloated source. This makes the base64 token-waste fix airtight (it can't be bypassed).
- **Audience (decided 2026-07-02): a public, open-source standard** — not just a personal tool
  or team convention. Implications: spec rigor and prior art (§8) matter, the name must be
  publishable (PyPI `mmdoc` verified unclaimed 2026-07-02), and the repo eventually needs a
  LICENSE + README. Strategy note from §8: conventions win via working tooling + vendor pull
  (AGENTS.md), and stall without them (llms.txt) — so the CLI/skill quality *is* the adoption
  strategy, not the spec document.
- **Still open:** alt-text/vision model provider (default Claude); `export` default format.
  (Decided since: CLI = Typer, conversion = Pandoc hybrid, `.mmdoc` extension = omit for now —
  see `CLI.md` / `../FORMAT.md`.)

### Format shape (current working assumption)

```
research/
  district-analysis.mmdoc/      ← folder (extension optional)
    index.md                    ← exactly 1 entry file (chose index.md over README.md)
    img-001.png                 ← N images, co-located, relative-path referenced
    img-002.png
  simple-text-doc.md            ← text-only docs stay plain .md
```

**Alt text does double duty** and is critical:
- **Search surface** — `rg "budget allocation"` matches the image-reference line.
- **Semantic summary** — lets an agent reason without loading the image; it only `Read`s
  the actual image file when visual detail matters.

---

## 5. From the spec — historical capture (largely superseded)

We reframed the spec's standalone CLI as **skill-driven** (§4.3), but the spec's command
set was the feature checklist we worked from, so it's preserved here. **Since decided —
where this section disagrees, the newer doc wins:** the command set and architecture are
now specified in `CLI.md`; the `CLAUDE.md` snippet lives normatively in `../FORMAT.md` §9;
the spec's implementation-priority ranking is superseded by the build order in
`OVERVIEW.md`.

### Why the spec rejects a read-time / MCP solution

1. **Harness coupling** — every harness (Claude Code, Codex, Cursor) has its own `ReadFile`
   with permission enforcement, edit-dependency tracking, partial-read support. A parallel
   read path must replicate or bypass all of it, and breaks as the harness evolves.
2. **API-level constraints** — APIs accept interleaved text+image blocks, but encoding
   happens at the boundary; you can't pass a pre-fused multimodal representation. (This is
   the same "label at the boundary" rule from §2.)
3. **Fragility** — read-path fixes need every session configured correctly; a write-path
   fix makes the doc agent-friendly **once**, for every future reader.

### Authoring commands (spec's CLI; for us, candidate skill capabilities)

- **`paste <target>`** — clipboard → folder.
  - *Image* (macOS `pngpaste`/`osascript`, Linux `xclip`) → save as next sequential
    `img-NNN.png`, append `![](…)`, optionally generate alt text via vision model.
  - *Rich-text HTML* (Notion / Google Docs / web) → convert text to Markdown, download/
    extract embedded images, write interleaved references.
  - *Plain text* → append as Markdown.
- **`normalize <source> [target]`** — convert existing forms into a folder.
  - *Base64 Markdown* → extract images to files, replace data URIs with relative paths.
  - *Notion (or similar) `.zip` export* → unzip, identify the Markdown + assets, clean
    vendor-specific formatting, reorganize.
  - *Loose/messy folder* → find Markdown + images, standardize references.
- **`init <name>`** — create an empty folder + entry file with frontmatter template.
- **`describe <target>`** — read each image, generate/update descriptive alt text via a
  vision model.

### Clipboard ingestion — append vs. new, and the terminal limitation (our discussion)

- **Read the pasteboard directly, not via the terminal.** See §2 — the terminal strips to
  plain text, so the command/skill must read the OS pasteboard API to get HTML + image bytes.
- **Append vs. new folder.** Target argument decides it: `mmdoc paste existing.mmdoc/`
  appends to a folder that already exists; a new name creates a fresh one. We want both — we
  often want pasted content folded into an *existing* doc, not split into a second one.
- **Agent-assisted merge.** Pasting rich content into the agent's input can't work (plain-text
  wall). Robust pattern: the command stages the extracted text+images to disk → the agent
  *reads from disk* and applies intelligence at the **merge step** (append / restructure /
  rewrite the existing folder). The agent's understanding happens on staged content.
- **Open feasibility question:** can a terminal keybind (cf. Ghostty Ctrl+V for images)
  reformat/route the clipboard so rich content reaches the right place? Portable fallback is
  the direct-pasteboard command, which doesn't depend on terminal support.
- **Claude Code extensibility facts (verified against docs/issues, 2026-07-02):** Ctrl+V is
  the built-in `chat:imagePaste` action — images only; the HTML clipboard flavor is never
  read (open feature request: claude-code issue #57795). Keybindings can only rebind
  built-in actions (no shell commands/skills/text insertion). Skills and hooks cannot attach
  image blocks to the current prompt. ⇒ An exact rich-paste Ctrl+V clone is Anthropic-only;
  our buildable UX is (a) a `/clip` staging skill (`mmdoc paste --stage` → clip-NNN/, multiple
  clips referenced by name at the right positions in one prompt), and (b) a `UserPromptSubmit`
  hook that detects an `@clipboard` token, stages the pasteboard at submit time, and injects
  the staged path — no paste keystroke at all. Within one clip, text/image interleaving is
  preserved by the format itself.

### Agent integration — operations that work with no harness changes

`search` (rg matches text incl. alt text) · `read text` (`README.md`/`index.md`) ·
`read image` (`Read img-001.png` → goes down the image path) · `partial read` (line ranges)
· `edit` (read-before-edit satisfied by a normal Read). The only "integration" is a project
instruction. Spec's suggested `CLAUDE.md` snippet:

```
Documents in research/*.mmdoc/ are multimodal research documents. The entry file
contains the text with image references. When you encounter an image reference like
![description](img-001.png), the alt text provides a summary. Read the actual image
file from the same directory when you need visual detail.
```

### Implementation priority order (spec's ranking)

1. Format convention + folder structure (define/document the standard).
2. `normalize` — convert existing content; immediate utility.
3. `paste` — clipboard authoring; fastest workflow.
4. `describe` — vision alt-text; upgrades searchability + comprehension.
5. macOS UTI registration — quality-of-life only.

---

## 6. Open questions

- **Build target first:** ingestion path (Google Doc / docx / base64-md → `mmdoc`
  folder — the actual pain) vs. nailing the folder-convention spec first (README vs
  index, alt-text rules, `CLAUDE.md` instructions) so the converter has a fixed target.
- **`README.md` vs `index.md`** as the canonical entry file (README auto-renders on
  GitHub; index reads as "more canonical").
- **CLI language/runtime** for any converter script — Python (best clipboard/image
  ecosystem), Rust (single binary), or Node (aligns with agent tooling).
- **Alt-text generation** — provider-specific default vs provider-agnostic flag.
- **Tables** — keep Markdown tables, or support co-located CSV (`![table: …](data.csv)`)?
- **Nested mmdocs** — allowed or out of scope?
- **Extension or not** — ship bare folders first, add `.mmdoc` later?

---

## 7. Next step

Pick the first build target (Section 6, first bullet). Leaning: the **ingestion skill**
(docx / Google Doc / base64-md → `mmdoc` folder), since that's the concrete pain — with
the folder convention pinned just enough to give it a fixed output target.

*(Superseded: the build is underway — `init`, `normalize` (md/docx), `validate` shipped.
Current plan lives in `OVERVIEW.md` → build order.)*

---

## 8. Prior art & landscape (researched 2026-07-02)

Nothing found that does what mmdoc does — define a **storage convention for multimodal
documents that agents read in place**. But three adjacent categories exist, and each
teaches something.

### Bundle formats (human-app oriented)

- **TextBundle** (textbundle.org, ~2014) — the closest structural cousin. A folder with
  `info.json` (metadata) + `text.md` + an `assets/` subfolder for images; `.textbundle`
  extension (registered as an opaque macOS package) and `.textpack` (zipped variant).
  Adopted by Bear, Ulysses, iA Writer. Built to move rich text *between sandboxed apps*,
  not for agents: the package is opaque (anti-browsing), metadata is JSON in a separate
  file (not greppable beside the text), there's no alt-text discipline, and no ingestion
  tooling. **Why we differ:** YAML frontmatter instead of `info.json` (metadata lives in
  the same greppable file), images at folder root, folder stays transparent, alt text as
  the search surface. **It validates demand** for folder-bundled markdown+assets.
  *Deferred idea:* TextBundle import/export is nearly trivial (move `assets/`, fold
  `info.json` into frontmatter) — cheap interop win someday.

### Agent-facing conventions (adoption lessons, not competitors)

- **AGENTS.md** (agents.md, 2025) — the instructions-file standard for coding agents,
  co-promoted by OpenAI, Google, Anthropic, Cursor, etc., now read by most harnesses.
  Not a document format. Lesson: **dead-simple markdown conventions can win broad
  adoption fast when tooling vendors co-sign.**
- **llms.txt** (llmstxt.org) — AI-readability convention for websites. Stuck at ~0.3%
  adoption, no major vendor has committed, still not formally standardized as of
  mid-2026. Lesson (the cautionary one): **a convention without working tooling or
  vendor pull stalls.** For mmdoc, the CLI + skill are the adoption strategy; the spec
  document alone would die like llms.txt.

### Converters (component-2 competitors — but format allies)

- **MarkItDown** (Microsoft), **Docling** (IBM), **LiteParse** (LlamaIndex),
  unstructured.io — all convert documents into "LLM-ready" Markdown. Docling can even
  save images as referenced files. But every one of them emits its **own ad-hoc output
  layout** — none defines a documented, validate-able convention for where the result
  *lands*. mmdoc is positioned as the **output target** such tools could write into,
  not a rival parser. This also validates the Pandoc-hybrid choice: conversion is a
  commodity; the missing piece is the convention.

### AI-native document representations (added 2026-07-02 — the serious neighbor)

- **DocLang** (doclang-project/doclang, 483★, LF AI & Data Foundation, Apache-2.0, active —
  v0.7.1 Jul 2026) — an **XML-based interchange representation between document parsers and
  LLMs/VLMs**, evidently the standardization of IBM Docling's DocTags vocabulary (`<ched/>`,
  `<fcel/>`, `<location value>`). Preserves structure *plus geometry* (bounding-box
  coordinates from OCR/layout analysis); "designed for LLM/VLM generation," explicitly **not
  for human authoring**. Files are a single `.dclg` XML (images as base64 data-URIs or URLs)
  or a `.dclx` **ZIP archive** (OPC container with `document.xml` + `assets/`).
  **Why it's a different layer, not a competitor:** doclang answers *"how does a parser
  describe a document to a model, losslessly?"* — mmdoc answers *"how does a person store a
  multimodal document so agents can grep/read/edit it in place?"* Its storage choices are
  the exact ones our mechanics analysis (§2, §3) rejects for the read-in-place use case:
  base64-in-text and opaque ZIPs are unsearchable/undiffable and token-hostile when read as
  files. Complementary, and proof the layer distinction is real. *Deferred idea:* a
  doclang→mmdoc importer (`normalize` input) would bridge parser pipelines into our format.
  Also relevant to §2's "multimodal input gap": doclang is an attempt at that serialization
  at the parser→model boundary, not the storage layer.
- **ANDF** (ug2454/ANDF, 1★, v1.0.1 Mar 2026) — "AI Native Document Format": a
  **self-contained single HTML file** with document data in an embedded
  `<script type="application/andf+json">` block, images embedded as assets, plus a Python
  CLI and "AI layer" (markdown export, RAG chunking). Hobby-scale, but instructive: it makes
  precisely the **single-file bet we rejected** — content invisible to grep, git diffs
  useless, images embedded rather than on-demand — and validates that "AI-native document
  format" is a live idea people are reaching for.

### Takeaways from DocLang for mmdoc (2026-07-02)

- **Why their base64 is fine and ours wasn't:** a `.dclg` is only ever opened by a *program*
  that decodes base64 back to bytes before the API boundary (same transport role as base64
  in the client→server JSON hop, §2). The base64 disaster requires a *text-labeled read into
  model context* — which is exactly what agent Read tools do, and why mmdoc must keep images
  as separate files. Same physics, different reader, opposite (correct) designs.
- **Provenance metadata (adopt):** doclang pictures carry origin info; mmdoc should too —
  optional frontmatter fields `source:` / `converted:` / `converter:`, stamped by
  `normalize`/`fetch`. Proposed for ../FORMAT.md.
- **Open-source playbook (validated):** spec-in-repo + reference CLI with `validate` +
  Apache-2.0 (patent grant matters for formats) + tests. Their stars came via Docling's
  existing users → our analog adoption channel is agent-skill users; ship the skill early.
- **`pack`/`unpack` (validated, stays deferred):** they keep a zipped single-file form
  (`.dclx`) alongside the exploded one — shipping vs. working modes. Confirms eventual demand.
- **Scope boundary (named):** geometry/layout belongs to doclang's layer, prose semantics to
  ours. mmdoc never grows bounding boxes; import from doclang instead.

### Name collisions (checked 2026-07-02)

- **PyPI:** `mmdoc` and `mmdoc-cli` both unclaimed (404). Publishable.
- **GitHub:** `ryantm/mmdoc` (31★, "Minimal Markdown Documentation" — a docs-site
  generator) exists, plus an academic **MMDoc\*** cluster (MMDocIR, MMDocRAG,
  MMDocBench — multimodal-document AI research). The academic usage confirms "mmdoc"
  already reads as "multimodal document" to the ML community; collisions are low-profile
  and don't block the name, but search results will be muddy.
