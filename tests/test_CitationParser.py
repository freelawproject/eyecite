"""
Demonstrates the fix for eyecite#146: law-citation section numbers with
letter suffixes (e.g. "18 U.S.C. § 1028A") are now recognized, including
real compound forms like "300gg-91", while guarded against fabricating
section numbers out of adjacent prose in space-stripped text.

Run with:
    python3 test.py
"""

from eyecite import get_citations
from eyecite.models import FullLawCitation


POSITIVE_CASES = [
    # (text, expected section value)
    ("18 U.S.C. § 1028A", "1028A"),               # the reported bug (#146)
    ("18 U.S.C. § 1028", "1028"),                 # plain section, unaffected
    ("42 U.S.C. § 300gg-91", "300gg-91"),         # real compound section (ACA)
    ("12 U.S.C. § 1749bbb-10c", "1749bbb-10c"),   # triple-letter compound
    ("42 U.S.C. § 1396a", "1396a"),               # common single-letter suffix (Medicaid)
]

NEGATIVE_CASES = [
    # text that must NOT produce a (wrong) citation
    "42 U.S.C. §1983and the equal protection clause",
    "18 U.S.C. §1030is a computer fraud statute",
    "18 U.S.C. §1983or the due process clause",
]


def law_section(text):
    """Return the section value of the first FullLawCitation found, or None."""
    law_cites = [c for c in get_citations(text) if isinstance(c, FullLawCitation)]
    return law_cites[0].groups.get("section") if law_cites else None


def run():
    failures = []

    print("=== Positive cases (should extract the correct section) ===")
    for text, expected in POSITIVE_CASES:
        got = law_section(text)
        ok = got == expected
        failures.append((text, expected, got)) if not ok else None
        print(f"[{'PASS' if ok else 'FAIL'}] {text!r:45} -> {got!r} (expected {expected!r})")

    print("\n=== Negative cases (should NOT fabricate a citation) ===")
    for text in NEGATIVE_CASES:
        got = law_section(text)
        ok = got is None
        failures.append((text, None, got)) if not ok else None
        print(f"[{'PASS' if ok else 'FAIL'}] {text!r:45} -> {got!r}")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for text, expected, got in failures:
            print(f"  {text!r}: expected {expected!r}, got {got!r}")
        raise SystemExit(1)
    print(f"All {len(POSITIVE_CASES) + len(NEGATIVE_CASES)} cases passed.")


if __name__ == "__main__":
    run()
    