r"""Pre-process LaTeX for clean pandoc -> DOCX conversion (journal submission).

Strategy (see SKILL.md): KEEP tables (pandoc converts even threeparttable /
multicolumn / booktabs into native Word tables), STRIP figures to numbered
placeholders (figures are submitted as separate files), and resolve every
cross-reference to static "Table N" / "Figure SN" text so numbering does not
drift.

It also fixes the gotchas that silently corrupt the DOCX:
  * `tabulary` -> `tabular`   (pandoc DROPS tabulary tables without warning)
  * `$^a$` empty-base math superscripts -> \textsuperscript{a}
    (otherwise Word renders an empty-base equation as a placeholder box)
  * strip `\appendix` + `\input{appendix}` so the main file converts alone.

Edit the CONFIG block, then run:  python preprocess.py
Outputs: <stem>_stripped.tex for the main file and every appendix file.
"""
import re
from pathlib import Path

# ---------------------------------------------------------------- CONFIG ----
ROOT = Path(__file__).resolve().parent          # adjust if tex lives elsewhere
MAIN_FILE = ROOT / "article.tex"
APPENDIX_FILES = [ROOT / f"MultimediaAppendix{i}.tex" for i in range(1, 9)]
OUT_DIR = ROOT / "docx_export"
# ----------------------------------------------------------------------------

CAP_RE = re.compile(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", re.DOTALL)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
ENV_RE = re.compile(
    r"\\begin\{(figure\*?|table\*?)\}(?:\[[^\]]*\])?.*?\\end\{\1\}", re.DOTALL
)


def build_label_map(main: Path, appendices: list[Path]) -> dict:
    """Scan files in document order; assign Table N / Figure N to the main file
    and Table SN / Figure SN to the appendices, keyed by each float's \\label."""
    mapping, counts = {}, {"main_t": 0, "main_f": 0, "app_t": 0, "app_f": 0}

    def scan(path: Path, appendix: bool):
        if not path.exists():
            return
        for m in ENV_RE.finditer(path.read_text(encoding="utf-8")):
            block, env = m.group(0), m.group(1)
            lm = LABEL_RE.search(block)
            if not lm:
                continue
            is_fig = env.startswith("figure")
            if appendix:
                key = "app_f" if is_fig else "app_t"
                counts[key] += 1
                kind = "Figure" if is_fig else "Table"
                mapping[lm.group(1)] = f"{kind} S{counts[key]}"
            else:
                key = "main_f" if is_fig else "main_t"
                counts[key] += 1
                kind = "Figure" if is_fig else "Table"
                mapping[lm.group(1)] = f"{kind} {counts[key]}"

    scan(main, appendix=False)
    for a in appendices:
        scan(a, appendix=True)
    return mapping


def clean_caption(cap: str, label_map: dict) -> str:
    cap = re.sub(r"\\(textbf|emph|textit)\{([^}]*)\}", r"\2", cap)
    cap = LABEL_RE.sub("", cap)
    cap = re.sub(r"\\ref\{([^}]*)\}", lambda m: label_map.get(m.group(1), "(ref)"), cap)
    return re.sub(r"\s+", " ", cap).strip()


def convert_superscript_markers(text: str) -> str:
    # $^a$ / $^{*}$ / $^{1}$ -> \textsuperscript{...}. Leaves $R^2$, $x^2$ alone
    # because the pattern needs '$' immediately followed by '^'.
    return re.sub(r"\$\^\{?([A-Za-z0-9*]+)\}?\$", r"\\textsuperscript{\1}", text)


def convert_tabulary(text: str) -> str:
    def repl(m):
        spec = m.group(1)
        for a, b in (("L", "l"), ("C", "c"), ("R", "r"), ("J", "l")):
            spec = spec.replace(a, b)
        return "\\begin{tabular}{" + spec + "}"

    text = re.sub(r"\\begin\{tabulary\}\{[^}]*\}\{([^}]*)\}", repl, text)
    return text.replace("\\end{tabulary}", "\\end{tabular}")


def strip_figures(text: str, label_map: dict) -> str:
    pat = re.compile(r"\\begin\{(figure\*?)\}(?:\[[^\]]*\])?.*?\\end\{\1\}", re.DOTALL)

    def repl(m):
        block = m.group(0)
        lm = LABEL_RE.search(block)
        ref = label_map.get(lm.group(1) if lm else "", "Figure")
        cm = CAP_RE.search(block)
        cap = clean_caption(cm.group(1), label_map) if cm else ""
        body = f"{ref}. {cap} -- insert figure file here" if cap else f"{ref} omitted"
        return f"\n\n\\noindent\\textit{{[{body}]}}\n\n"

    return pat.sub(repl, text)


def number_table_captions(text: str, label_map: dict) -> str:
    pat = re.compile(r"\\begin\{table\*?\}(?:\[[^\]]*\])?.*?\\end\{table\*?\}", re.DOTALL)

    def repl(m):
        block = m.group(0)
        lm = LABEL_RE.search(block)
        num = label_map.get(lm.group(1) if lm else "")
        if not num:
            return block

        def cap_repl(cm):
            cap = cm.group(1)
            return cm.group(0) if cap.lstrip().startswith(num) else "\\caption{" + f"{num}. " + cap + "}"

        return CAP_RE.sub(cap_repl, block, count=1)

    return pat.sub(repl, text)


def resolve_refs(text: str, label_map: dict) -> str:
    def repl(m):
        return label_map.get(m.group(1), f"[{m.group(1)}]")

    text = re.sub(r"(?:Table|Figure)~?\\ref\{([^}]+)\}", repl, text)
    return re.sub(r"\\ref\{([^}]+)\}", repl, text)


def strip_directives(text: str) -> str:
    text = re.sub(r"\\usepackage(\[[^\]]*\])?\{natbib\}\s*", "", text)
    text = re.sub(r"\\bibliographystyle\{[^}]+\}\s*", "", text)
    # Replace \bibliography{...} with a "References" heading so the citeproc list
    # (appended at the end of the document) sits under a real section heading.
    text = re.sub(r"\\bibliography\{[^}]+\}\s*", "\n\\\\section*{References}\n", text)
    text = re.sub(r"\\input\{[^}]*Appendix\d+\}\s*", "", text)
    text = re.sub(r"\\appendix\s*", "", text)
    return text


def inline_url_footnote(text: str) -> str:
    return re.sub(r"\\footnote\{\\URL\{[^}]*\}\{([^}]+)\}\}", r" (\1)", text)


def convert_url_macro(text: str) -> str:
    # Custom \URL{url}{display} -> \href{url}{display} (pandoc renders \href as a
    # Word hyperlink; it silently drops the unknown two-arg \URL, leaving "()").
    return re.sub(r"\\URL\{([^}]*)\}\{([^}]*)\}", r"\\href{\1}{\2}", text)


def _braced_arg(text: str, cmd: str):
    """Return (full_match, inner) for \\cmd{...} with balanced braces, or None."""
    m = re.search(r"\\" + cmd + r"\s*\{", text)
    if not m:
        return None
    i, depth = m.end(), 1
    while i < len(text) and depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return text[m.start():i], text[m.end():i - 1]


def extract_title_block(text: str):
    """For the main file: pull \\title / \\author out of the body, drop
    \\maketitle, and return (body_without_title, title_text, author_block).
    Title goes to pandoc metadata (Word "Title" style); the author block is
    re-inserted as a normal paragraph just under the title."""
    title_text, author_block = "", ""
    t = _braced_arg(text, "title")
    if t:
        full, inner = t
        title_text = re.sub(r"\s+", " ", inner).strip()
        text = text.replace(full, "", 1)
    a = _braced_arg(text, "author")
    if a:
        full, inner = a
        author_block = inner.strip()
        text = text.replace(full, "", 1)
    text = re.sub(r"\\maketitle\s*", "", text)
    return text, title_text, author_block


def process(path: Path, label_map: dict, out: Path, is_main: bool = False) -> None:
    text = path.read_text(encoding="utf-8")
    text = convert_superscript_markers(text)
    text = convert_tabulary(text)
    text = strip_figures(text, label_map)
    text = number_table_captions(text, label_map)
    text = strip_directives(text)
    text = inline_url_footnote(text)
    text = convert_url_macro(text)
    text = resolve_refs(text, label_map)
    if is_main:
        text, title_text, author_block = extract_title_block(text)
        # Re-insert authors as a body paragraph right after \begin{document}
        # (plain string splice -- author_block has backslashes re.sub would mangle).
        if author_block:
            marker = "\\begin{document}"
            idx = text.find(marker)
            if idx != -1:
                cut = idx + len(marker)
                text = text[:cut] + "\n\n" + author_block + "\n\n" + text[cut:]
        # Title -> pandoc metadata (renders with Word "Title" style).
        (OUT_DIR / "main_meta.yaml").write_text(
            f"---\ntitle: |\n  {title_text}\n---\n", encoding="utf-8")
    out.write_text(text, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    label_map = build_label_map(MAIN_FILE, APPENDIX_FILES)
    process(MAIN_FILE, label_map, OUT_DIR / f"{MAIN_FILE.stem}_stripped.tex", is_main=True)
    for a in APPENDIX_FILES:
        if a.exists():
            process(a, label_map, OUT_DIR / f"{a.stem}_stripped.tex")
    print(f"Label map ({len(label_map)} floats): {label_map}")
    print(f"Wrote stripped .tex to {OUT_DIR}")


if __name__ == "__main__":
    main()