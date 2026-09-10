#!/usr/bin/env bash
# Convert stripped LaTeX to SEPARATE DOCX files: main manuscript + each
# appendix (journals submit appendices/supplements as independent files).
# Run preprocess.py first. Run this from the directory holding the *_stripped.tex.
#
# Prereqs: pandoc (>=3), the .bib, a journal CSL. Optional: reference.docx (base styles).
set -euo pipefail
cd "$(dirname "$0")"

# ----------------------------------------------------------------- CONFIG ---
BIB="../article.bib"            # path to BibTeX file
CSL="jmir.csl"                  # journal CSL (see SKILL.md for fetch command)
MAIN_STEM="article"             # -> article_stripped.tex -> article_main.docx
APPENDIX_STEMS=(MultimediaAppendix1 MultimediaAppendix2 MultimediaAppendix3 \
                MultimediaAppendix4 MultimediaAppendix5 MultimediaAppendix6 \
                MultimediaAppendix7 MultimediaAppendix8)
# ----------------------------------------------------------------------------

ARGS=(--citeproc --bibliography="$BIB" --csl="$CSL")
[ -f reference.docx ] && ARGS+=(--reference-doc=reference.docx)

# Main gets the generated title metadata (Word "Title" style).
MAIN_ARGS=("${ARGS[@]}")
[ -f main_meta.yaml ] && MAIN_ARGS+=(--metadata-file=main_meta.yaml)
pandoc "${MAIN_STEM}_stripped.tex" -o "${MAIN_STEM}_main.docx" "${MAIN_ARGS[@]}"
for s in "${APPENDIX_STEMS[@]}"; do
  [ -f "${s}_stripped.tex" ] && pandoc "${s}_stripped.tex" -o "${s}.docx" "${ARGS[@]}"
done

echo "Wrote ${MAIN_STEM}_main.docx + appendix docx files."