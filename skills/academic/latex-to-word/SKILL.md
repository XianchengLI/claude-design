---
name: latex-to-word
description: >-
  Convert a LaTeX manuscript to submission-ready Microsoft Word (.docx) for
  journals that require Word (JMIR, Elsevier, Wiley, PLOS, etc.). Uses pandoc
  for text/tables/maths/citations, renders TikZ figures separately, and
  visually QAs the result via LibreOffice. Use whenever the user asks to
  convert .tex to Word/docx, "latex to word", pandoc docx export, prepare a
  Word manuscript for submission, or fix formatting that breaks in the Word
  conversion (dropped tables, citation/cross-ref numbering, TikZ figures,
  superscript boxes, separate appendix files).
---

# LaTeX → Word (submission-ready DOCX)

Goal: a clean, editable Word manuscript whose **content** (text, tables with
their numbers, equations, resolved citations) is faithful, with figures handled
as the separate files journals want anyway. Aim for "structurally correct +
lightly styled, then a short manual polish in Word" — not pixel-perfect from
pandoc.

## Core strategy: separate concerns

| Content | Handling |
|---|---|
| Prose / headings / lists / inline & display maths | pandoc (maths → native Word OMML) |
| Citations + reference list | pandoc `--citeproc` + journal **CSL** (never by hand) |
| Tables (incl. `threeparttable`, `multicolumn`, `booktabs`) | **KEEP** — pandoc converts them to native Word tables with data + notes intact |
| `tabulary` tables | convert to `tabular` first (pandoc **silently drops** `tabulary`) |
| Figures (`\includegraphics`) | strip to a numbered placeholder; the PNG/PDF is uploaded separately |
| TikZ / pgfplots figures | compile to standalone PDF, rasterise to PNG, upload separately |
| Main vs appendices | convert to **separate** .docx files (journals submit supplements separately) |

The preprocess step keeps tables and strips only figures; do not strip tables —
re-keying tables of statistics into Word risks transcription errors.

## Tooling (check first; install only what's missing)

- **pandoc** ≥ 3 — required. `pandoc --version`
- **LaTeX + Ghostscript** — only if there are TikZ/pgfplots figures, or for
  visual QA. MiKTeX (Windows, per-user, `winget install MiKTeX.MiKTeX`) bundles
  Ghostscript as `mgs.exe`; TeX Live / TinyTeX also work. Enable auto package
  install: `initexmf --set-config-value="[MPM]AutoInstall=1"`.
- **LibreOffice** — for visual QA only (`winget install
  TheDocumentFoundation.LibreOffice`, machine scope). Provides `soffice` for
  docx → PDF.
- Read tool renders PDFs via `pdftoppm`; if absent, rasterise PDF→PNG with
  Ghostscript and Read the PNGs.

## Procedure

1. **Copy the scripts** in `scripts/` into the project's export dir (e.g.
   `docx_export/`). Edit the CONFIG block in `preprocess.py` (main file,
   appendix files) and `convert.sh` (bib path, CSL name, stems).

2. **Fetch the journal CSL** (citation-style-language repo), e.g. JMIR:
   ```
   curl -fsSL "https://raw.githubusercontent.com/citation-style-language/styles/master/journal-of-medical-internet-research.csl" -o jmir.csl
   ```
   Browse https://github.com/citation-style-language/styles for other journals.

3. **Starter reference.docx** (base Word styles; user fine-tunes in Word):
   ```
   pandoc -o reference.docx --print-default-data-file reference.docx
   ```

4. **Preprocess + convert** (produces separate docx):
   ```
   python preprocess.py && bash convert.sh
   ```

5. **Render TikZ figures** to standalone files (one per `tikzpicture`). Wrap the
   exact `tikzpicture` (with its `\usetikzlibrary{...}`, often `positioning`) in:
   ```latex
   \documentclass[border=4pt]{standalone}
   \usepackage{tikz,amsmath}\usetikzlibrary{positioning}
   \begin{document}
   ... tikzpicture ...
   \end{document}
   ```
   Then compile + rasterise (MiKTeX paths shown):
   ```
   pdflatex -interaction=nonstopmode figX.tex
   mgs -dBATCH -dNOPAUSE -sDEVICE=png16m -r600 -dTextAlphaBits=4 \
       -dGraphicsAlphaBits=4 -o figX.png figX.pdf
   ```
   Keep both the PDF (vector, ideal for submission) and a 600-dpi PNG.

6. **QA — structural** (zero leaks + expected table/eqn counts):
   ```
   python qa_docx.py .
   ```

7. **QA — visual** (catch layout/box issues only rendering reveals):
   ```
   soffice -env:UserInstallation=file:///C:/tmp/lo_profile --headless \
           --convert-to pdf --outdir pdf_preview article_main.docx
   mgs -dBATCH -dNOPAUSE -sDEVICE=png16m -r150 -o "pg-%03d.png" pdf_preview/article_main.pdf
   ```
   Read the page PNGs (focus on table-heavy pages, former-`tabulary` tables,
   footnote markers). The `-env:UserInstallation` flag gives soffice a private
   profile — without it a leftover lock makes `--convert-to` silently produce
   no PDF. If a run produces no PDF, kill `soffice`/`soffice.bin` and retry with
   the flag.

## Gotchas (each is handled by `preprocess.py`; verify in visual QA)

| Symptom in Word | Cause | Fix |
|---|---|---|
| A whole table missing | `tabulary` — pandoc drops it silently | `tabulary` → `tabular` (`convert_tabulary`) |
| Small □ box before a superscript | `$^a$` empty-base math superscript renders as empty-base equation | `$^a$` → `\textsuperscript{a}` (`convert_superscript_markers`) |
| Wrong table/figure numbers in text (e.g. "Table 6" for an appendix table) | pandoc auto-numbers `\ref` by appearance | resolve `\ref` to static "Table N"/"Table SN" via auto-built label map |
| Caption has no number | pandoc doesn't number captions | prepend "Table N. " to each caption (`number_table_captions`) |
| Appendix content bleeds into main docx | `\input{appendix}` followed | strip `\appendix` + `\input{...Appendix..}` |
| `\cite` left as raw text / no reference list | natbib + `\bibliography` confuses citeproc | strip bib directives; use `--citeproc --bibliography --csl` |
| Reference list has no "References" heading | citeproc emits the list but no heading | replace `\bibliography{..}` with `\section*{References}` (`strip_directives`) — citeproc appends the list right under it |
| No manuscript title, or title not styled | custom `\title`/`\maketitle` defs; pandoc's body-title extraction is flaky | `extract_title_block` pulls title to `main_meta.yaml` → `--metadata-file` (Word "Title" style); authors re-inserted as a body paragraph |
| Empty `()` where a URL should be | custom two-arg `\URL{url}{text}` macro pandoc drops | `\URL{u}{t}` → `\href{u}{t}` (`convert_url_macro`) → Word hyperlink |
| TikZ figure absent / garbled | pandoc cannot render TikZ | render to standalone PDF/PNG, insert as image |

## Hand-off: what the user does in Word (cannot be automated without Word)

- Apply table styles; touch up column widths on wide/complex tables.
- Insert figure files at the `[Figure N. ... insert figure file here]` markers,
  or upload each separately per journal rules. (Assemble them into one folder
  named by figure number, with a README mapping each to its placeholder.)
- Eyeball equations, special characters, and the now-static cross-references.
  (Title, author block, and the "References" heading are emitted automatically —
  confirm they look right.)
- Author names/affiliations usually go through the journal's submission system,
  not the Word title page.

Always state honestly that automated QA is structural; final visual fidelity is
confirmed when the user opens the file in Word (or via the LibreOffice PDF QA).