"""
Validate BibTeX file: check required fields, DOI resolution, duplicates, formatting.

Usage:
    python validate_bibtex.py <bib_file> [--check-dois] [--fix-output <output.bib>]

Examples:
    python validate_bibtex.py article.bib
    python validate_bibtex.py article.bib --check-dois
    python validate_bibtex.py article.bib --check-dois --fix-output fixed.bib
"""

import re
import sys
import json
import argparse
from pathlib import Path
from collections import Counter

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# Required fields per entry type (BibTeX standard)
REQUIRED_FIELDS = {
    "article": ["author", "title", "journal", "year"],
    "inproceedings": ["author", "title", "booktitle", "year"],
    "book": ["author", "title", "publisher", "year"],
    "incollection": ["author", "title", "booktitle", "publisher", "year"],
    "phdthesis": ["author", "title", "school", "year"],
    "mastersthesis": ["author", "title", "school", "year"],
    "techreport": ["author", "title", "institution", "year"],
    "misc": ["author", "title", "year"],
}

# Recommended fields (warnings, not errors)
RECOMMENDED_FIELDS = {
    "article": ["volume", "pages", "doi"],
    "inproceedings": ["pages", "doi"],
    "book": ["isbn"],
}


def parse_bibtex(text):
    """Parse BibTeX file into list of entries."""
    entries = []
    # Match @type{key, ... }
    pattern = re.compile(
        r"@(\w+)\s*\{([^,]+),\s*(.*?)\n\}",
        re.DOTALL
    )

    for match in pattern.finditer(text):
        entry_type = match.group(1).lower()
        key = match.group(2).strip()
        body = match.group(3)

        fields = {}
        # Parse fields by finding "field = " patterns and extracting balanced braces
        for fm in re.finditer(r"(\w+)\s*=\s*", body):
            field_name = fm.group(1).lower()
            rest = body[fm.end():]

            if rest.startswith("{"):
                # Extract balanced braces content
                depth = 0
                end = 0
                for j, ch in enumerate(rest):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            end = j
                            break
                value = rest[1:end]  # strip outer braces
            elif rest.startswith('"'):
                # Quoted value
                close = rest.index('"', 1)
                value = rest[1:close]
            else:
                # Bare number or value
                m = re.match(r"(\d+)", rest)
                value = m.group(1) if m else ""

            fields[field_name] = value.strip()

        entries.append({
            "type": entry_type,
            "key": key,
            "fields": fields,
            "raw": match.group(0),
        })

    return entries


def check_required_fields(entries):
    """Check required fields for each entry type."""
    issues = []
    for entry in entries:
        etype = entry["type"]
        key = entry["key"]
        required = REQUIRED_FIELDS.get(etype, [])

        for field in required:
            if field not in entry["fields"] or not entry["fields"][field]:
                issues.append({
                    "key": key,
                    "severity": "ERROR",
                    "type": "missing_required_field",
                    "message": f"Missing required field: {field}",
                })

        recommended = RECOMMENDED_FIELDS.get(etype, [])
        for field in recommended:
            if field not in entry["fields"] or not entry["fields"][field]:
                issues.append({
                    "key": key,
                    "severity": "WARNING",
                    "type": "missing_recommended_field",
                    "message": f"Missing recommended field: {field}",
                })

    return issues


def check_duplicates(entries):
    """Detect duplicate entries by DOI, title similarity, or key."""
    issues = []

    # Check duplicate keys
    keys = [e["key"] for e in entries]
    key_counts = Counter(keys)
    for key, count in key_counts.items():
        if count > 1:
            issues.append({
                "key": key,
                "severity": "ERROR",
                "type": "duplicate_key",
                "message": f"Duplicate citation key (appears {count} times)",
            })

    # Check duplicate DOIs
    doi_map = {}
    for entry in entries:
        doi = entry["fields"].get("doi", "").lower().strip()
        if doi:
            if doi in doi_map:
                issues.append({
                    "key": entry["key"],
                    "severity": "ERROR",
                    "type": "duplicate_doi",
                    "message": f"Duplicate DOI with '{doi_map[doi]}': {doi}",
                })
            else:
                doi_map[doi] = entry["key"]

    # Check similar titles
    titles = {}
    for entry in entries:
        title = entry["fields"].get("title", "")
        normalized = re.sub(r"[^a-z0-9\s]", "", title.lower()).strip()
        normalized = re.sub(r"\s+", " ", normalized)
        if len(normalized) > 20:
            for existing_norm, existing_key in titles.items():
                if existing_key == entry["key"]:
                    continue
                # Simple similarity: check if 80%+ words overlap
                words_a = set(normalized.split())
                words_b = set(existing_norm.split())
                if len(words_a) > 3 and len(words_b) > 3:
                    overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
                    if overlap > 0.8:
                        issues.append({
                            "key": entry["key"],
                            "severity": "WARNING",
                            "type": "similar_title",
                            "message": f"Similar title to '{existing_key}' (overlap: {overlap:.0%})",
                        })
            titles[normalized] = entry["key"]

    return issues


def check_formatting(entries):
    """Check common formatting issues."""
    issues = []

    for entry in entries:
        key = entry["key"]
        fields = entry["fields"]

        # Year validation
        year = fields.get("year", "")
        if year:
            if not re.match(r"^\d{4}$", year):
                issues.append({
                    "key": key,
                    "severity": "ERROR",
                    "type": "invalid_year",
                    "message": f"Invalid year format: '{year}'",
                })
            elif int(year) < 1900 or int(year) > 2030:
                issues.append({
                    "key": key,
                    "severity": "WARNING",
                    "type": "unusual_year",
                    "message": f"Unusual year: {year}",
                })

        # Pages format: should use -- not -
        pages = fields.get("pages", "")
        if pages and re.search(r"(?<!\-)\-(?!\-)", pages):
            issues.append({
                "key": key,
                "severity": "WARNING",
                "type": "page_dash",
                "message": f"Pages use single dash '{pages}', should use '--'",
            })

        # DOI format check
        doi = fields.get("doi", "")
        if doi:
            if doi.startswith("http"):
                issues.append({
                    "key": key,
                    "severity": "WARNING",
                    "type": "doi_format",
                    "message": f"DOI should not start with http: '{doi[:50]}'",
                })

        # Empty author check
        author = fields.get("author", "")
        if author and len(author) < 3:
            issues.append({
                "key": key,
                "severity": "WARNING",
                "type": "short_author",
                "message": f"Suspiciously short author field: '{author}'",
            })

        # Title capitalization: check for unprotected acronyms
        title = fields.get("title", "")
        acronyms = re.findall(r"\b[A-Z]{2,}\b", title)
        for acr in acronyms:
            # Check if protected with braces
            if f"{{{acr}}}" not in title and f"{{" not in title:
                issues.append({
                    "key": key,
                    "severity": "WARNING",
                    "type": "unprotected_acronym",
                    "message": f"Acronym '{acr}' may need brace protection: {{{acr}}}",
                })

    return issues


def _normalize_title(s):
    s = re.sub(r"[{}]", "", s or "")
    return re.sub(r"[^a-z0-9\s]", " ", s.lower()).strip()


def crossref_record_mismatch(fields, message):
    """Detect 'DOI resolves but points to a different paper' (张冠李戴).

    Returns a description string, or None when the record plausibly matches.
    Comparison is deliberately loose (title word overlap + first-author family
    name) so formatting differences don't raise false alarms.
    """
    problems = []
    bib_title = _normalize_title(fields.get("title", ""))
    cr_titles = message.get("title") or []
    cr_title = _normalize_title(cr_titles[0]) if cr_titles else ""
    if bib_title and cr_title:
        bib_words = set(bib_title.split())
        cr_words = set(cr_title.split())
        # Containment (not Jaccard): CrossRef often stores only the main title
        # without the subtitle, which must not count as a mismatch.
        overlap = len(bib_words & cr_words) / max(min(len(bib_words), len(cr_words)), 1)
        if overlap < 0.5:
            problems.append(
                f"title mismatch (overlap {overlap:.0%}): CrossRef has '{cr_titles[0][:80]}'"
            )
    bib_author = fields.get("author", "")
    cr_authors = message.get("author") or []
    if bib_author and cr_authors:
        first_family = (cr_authors[0].get("family") or "").lower()
        first_bib_author = bib_author.split(" and ")[0].lower()
        if first_family and first_family not in first_bib_author:
            problems.append(
                f"first-author mismatch: CrossRef has '{cr_authors[0].get('family')}'"
            )
    return "; ".join(problems) or None


def check_dois_resolve(entries, timeout=10):
    """Verify DOIs resolve via CrossRef AND point to the right paper."""
    if not HAS_REQUESTS:
        print("WARNING: 'requests' not installed. Skipping DOI resolution check.")
        print("  Install with: pip install requests")
        return []

    issues = []
    dois = [(e["key"], e["fields"], e["fields"]["doi"]) for e in entries if e["fields"].get("doi")]
    total = len(dois)

    print(f"\nChecking {total} DOIs...")

    for i, (key, fields, doi) in enumerate(dois, 1):
        # Normalize DOI
        clean_doi = doi.strip()
        if clean_doi.startswith("http"):
            clean_doi = re.sub(r"https?://doi\.org/", "", clean_doi)

        # Use CrossRef API (more reliable than doi.org which has anti-bot measures)
        url = f"https://api.crossref.org/works/{clean_doi}"
        headers = {
            "User-Agent": "validate_bibtex/1.0 (mailto:research@example.com)",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 404:
                issues.append({
                    "key": key,
                    "severity": "ERROR",
                    "type": "doi_not_found",
                    "message": f"DOI not found in CrossRef: {clean_doi}",
                })
            elif resp.status_code >= 400:
                issues.append({
                    "key": key,
                    "severity": "WARNING",
                    "type": "doi_check_failed",
                    "message": f"CrossRef returned HTTP {resp.status_code} for: {clean_doi}",
                })
            elif resp.status_code == 200:
                try:
                    mismatch = crossref_record_mismatch(fields, resp.json().get("message", {}))
                except ValueError:
                    mismatch = None
                if mismatch:
                    issues.append({
                        "key": key,
                        "severity": "ERROR",
                        "type": "doi_mismatch",
                        "message": f"DOI resolves but record differs ({mismatch}): {clean_doi}",
                    })
            status = "OK" if resp.status_code == 200 else resp.status_code
            print(f"  [{i}/{total}] {key}: {status}       ", end="\r")
        except requests.exceptions.Timeout:
            issues.append({
                "key": key,
                "severity": "WARNING",
                "type": "doi_timeout",
                "message": f"DOI resolution timed out: {clean_doi}",
            })
        except requests.exceptions.RequestException as e:
            issues.append({
                "key": key,
                "severity": "WARNING",
                "type": "doi_error",
                "message": f"DOI check failed: {clean_doi} ({e})",
            })

    print(f"  DOI check complete: {total} checked.       ")
    return issues


def check_note_doi_consistency(entries):
    """Check that doi field and note field are consistent (our vancouver.bst workaround)."""
    issues = []
    for entry in entries:
        key = entry["key"]
        doi = entry["fields"].get("doi", "")
        note = entry["fields"].get("note", "")

        if doi and not note:
            issues.append({
                "key": key,
                "severity": "INFO",
                "type": "missing_note_doi",
                "message": f"Has doi field but no note workaround (vancouver.bst ignores doi field)",
            })
        elif doi and note:
            # Check if DOI in note matches doi field
            note_doi = re.search(r"10\.\d{4,}/[^\s\}]+", note)
            if note_doi:
                note_doi_str = note_doi.group(0).rstrip("}")
                doi_clean = doi.strip().rstrip("}")
                if note_doi_str != doi_clean:
                    issues.append({
                        "key": key,
                        "severity": "WARNING",
                        "type": "doi_note_mismatch",
                        "message": f"DOI mismatch: field='{doi_clean}' vs note='{note_doi_str}'",
                    })

    return issues


def print_report(entries, all_issues):
    """Print formatted validation report."""
    errors = [i for i in all_issues if i["severity"] == "ERROR"]
    warnings = [i for i in all_issues if i["severity"] == "WARNING"]
    infos = [i for i in all_issues if i["severity"] == "INFO"]

    print("\n" + "=" * 60)
    print("BIBTEX VALIDATION REPORT")
    print("=" * 60)

    # Summary
    entry_types = Counter(e["type"] for e in entries)
    print(f"\nEntries: {len(entries)}")
    for etype, count in sorted(entry_types.items(), key=lambda x: -x[1]):
        print(f"  @{etype}: {count}")

    entries_with_doi = sum(1 for e in entries if e["fields"].get("doi"))
    print(f"\nDOI coverage: {entries_with_doi}/{len(entries)} ({entries_with_doi/len(entries)*100:.0f}%)")

    print(f"\nIssues: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")

    if errors:
        print(f"\n{'ERRORS':=^60}")
        for issue in errors:
            print(f"  [{issue['key']}] {issue['message']}")

    if warnings:
        print(f"\n{'WARNINGS':=^60}")
        for issue in warnings:
            print(f"  [{issue['key']}] {issue['message']}")

    if infos:
        print(f"\n{'INFO':=^60}")
        for issue in infos:
            print(f"  [{issue['key']}] {issue['message']}")

    if not all_issues:
        print("\n  No issues found!")

    print("\n" + "=" * 60)
    return len(errors)


def main():
    parser = argparse.ArgumentParser(description="Validate BibTeX file")
    parser.add_argument("bib_file", help="Path to BibTeX file")
    parser.add_argument("--check-dois", action="store_true",
                        help="Verify DOIs resolve (requires internet)")
    parser.add_argument("--json", action="store_true",
                        help="Output report as JSON")
    parser.add_argument("--fix-output", metavar="FILE",
                        help="Write auto-fixed BibTeX to file (page dashes only)")
    args = parser.parse_args()

    bib_path = Path(args.bib_file)
    if not bib_path.exists():
        print(f"ERROR: File not found: {bib_path}")
        sys.exit(1)

    text = bib_path.read_text(encoding="utf-8")
    entries = parse_bibtex(text)

    if not entries:
        print(f"ERROR: No BibTeX entries found in {bib_path}")
        sys.exit(1)

    print(f"Parsed {len(entries)} entries from {bib_path.name}")

    # Run all checks
    all_issues = []
    all_issues.extend(check_required_fields(entries))
    all_issues.extend(check_duplicates(entries))
    all_issues.extend(check_formatting(entries))
    all_issues.extend(check_note_doi_consistency(entries))

    if args.check_dois:
        all_issues.extend(check_dois_resolve(entries))

    if args.json:
        report = {
            "file": str(bib_path),
            "total_entries": len(entries),
            "issues": all_issues,
            "summary": {
                "errors": len([i for i in all_issues if i["severity"] == "ERROR"]),
                "warnings": len([i for i in all_issues if i["severity"] == "WARNING"]),
                "info": len([i for i in all_issues if i["severity"] == "INFO"]),
            }
        }
        print(json.dumps(report, indent=2))
    else:
        error_count = print_report(entries, all_issues)

    # Auto-fix: page dashes
    if args.fix_output:
        fixed = text
        # Fix single dashes in pages
        fixed = re.sub(
            r"(pages\s*=\s*\{[^}]*?)(?<!\-)(\-)(?!\-)([^}]*?\})",
            lambda m: m.group(0).replace("-", "--") if "--" not in m.group(0) else m.group(0),
            fixed
        )
        Path(args.fix_output).write_text(fixed, encoding="utf-8")
        print(f"\nFixed output written to: {args.fix_output}")

    sys.exit(1 if any(i["severity"] == "ERROR" for i in all_issues) else 0)


if __name__ == "__main__":
    main()
