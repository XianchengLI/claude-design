"""Structural QA for converted .docx files (run from the output directory).

Reports, per docx: native-table count, OMML equation count, and any genuine
LaTeX leakage (a backslash-command surviving in body text). Zero leaks +
expected table counts = the conversion carried content faithfully.

NOTE: do NOT QA by `pandoc docx -t plain | grep '\\cmd'` -- the plain writer
re-emits math as LaTeX, producing false leaks. Read the XML text runs instead.

Usage: python qa_docx.py [dir]   (default: current directory)
"""
import re, sys, zipfile, glob, os, collections

DOCX_DIR = sys.argv[1] if len(sys.argv) > 1 else "."
WT = re.compile(r"<w:t[^>]*>(.*?)</w:t>", re.S)
LEAK = re.compile(r"\\[a-zA-Z]+")   # a real LaTeX command sitting in body text

for path in sorted(glob.glob(os.path.join(DOCX_DIR, "*.docx"))):
    name = os.path.basename(path)
    if name == "reference.docx":
        continue
    try:
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        print(f"{name:30s} ERROR: {e}")
        continue
    text = " ".join(WT.findall(xml))
    leaks = collections.Counter(LEAK.findall(text))
    n_tbl = xml.count("<w:tbl>")
    n_math = xml.count("<m:oMath>")
    box = sum(1 for ch in text if 0x2400 <= ord(ch) <= 0x2426 or ord(ch) in (0x25A1, 0x2751))
    leakstr = ", ".join(f"{k}({v})" for k, v in leaks.most_common(10)) if leaks else "NONE"
    flag = "" if not leaks and box == 0 else "  <-- CHECK"
    print(f"{name:30s} tables={n_tbl:<3d} eqns={n_math:<4d} boxchars={box:<3d} leaks: {leakstr}{flag}")