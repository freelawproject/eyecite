#!/usr/bin/env python3
"""Demo script showing the extended EyeCite functionality."""

import os
import sys

# Add the eyecite directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eyecite"))

try:
    # Import the extended functionality
    from eyecite import get_citations
    from eyecite.models_extended import (
        ConstitutionCitation,
        JournalArticleCitation,
        LegislativeBillCitation,
        ScientificIdentifierCitation,
        SessionLawCitation,
    )

    print("✅ Successfully imported extended EyeCite functionality!")
    print()

    # Test text with multiple citation types
    test_text = """
    This opinion relies on both constitutional law and modern scholarship.

    First, U.S. CONST. art. I, § 9, cl. 2 prohibits bills of attainder.
    Georgia CONST. art. I, § 1, para. I also applies.
    U.S. CONST. amend. XIV, § 1 guarantees equal protection.

    The legislature authorized H.R. 25, 118th Cong. to address this issue.
    The enactment became Pub. L. No. 94-579, § 102, 90 Stat. 2743.

    Recent scholarship includes 125 Yale L.J. 250 (2015) and 68 Am. J. Comp. L. 1 (2020).

    The key identifier is DOI: 10.1038/171737a0.
    Patent No. U.S. Patent No. 8,888,888 is relevant too.
    """

    print("🧪 Testing extended citation parsing with sample text:")
    print("=" * 60)
    print(test_text.strip())
    print("=" * 60)
    print()

    # Find citations using the standard method (will include extended types)
    citations = get_citations(test_text)

    print(f"📊 Found {len(citations)} citations total:")
    print()

    # Categorize citations
    constitution_cites = [
        c for c in citations if isinstance(c, ConstitutionCitation)
    ]
    bill_cites = [
        c for c in citations if isinstance(c, LegislativeBillCitation)
    ]
    law_cites = [c for c in citations if isinstance(c, SessionLawCitation)]
    journal_cites = [
        c for c in citations if isinstance(c, JournalArticleCitation)
    ]
    science_cites = [
        c for c in citations if isinstance(c, ScientificIdentifierCitation)
    ]
    other_cites = [
        c
        for c in citations
        if not isinstance(
            c,
            ConstitutionCitation
            | LegislativeBillCitation
            | SessionLawCitation
            | JournalArticleCitation
            | ScientificIdentifierCitation,
        )
    ]

    print("📜 Constitution Citations:")
    for cite in constitution_cites:
        print(f"    - {cite.matched_text()}")
        if hasattr(cite, "jurisdiction"):
            print(f"      Jurisdiction: {cite.jurisdiction}")
        if hasattr(cite, "article") and cite.article:
            print(f"      Article: {cite.article}")
        if hasattr(cite, "section") and cite.section:
            print(f"      Section: {cite.section}")
        if hasattr(cite, "amendment") and cite.amendment:
            print(f"      Amendment: {cite.amendment}")
        print()

    print("🏛️ Legislative Bill Citations:")
    for cite in bill_cites:
        print(f"    - {cite.matched_text()}")
        print(f"      Chamber: {cite.chamber}, Bill: {cite.bill_num}")
        print()

    print("📋 Session Law Citations:")
    for cite in law_cites:
        print(f"    - {cite.matched_text()}")
        if cite.law_num:
            print(f"      Law Number: {cite.law_num}")
        print()

    print("📚 Journal Article Citations:")
    for cite in journal_cites:
        print(f"    - {cite.matched_text()}")
        print(f"      Reporter: {cite.reporter}, Volume: {cite.volume}")
        print()

    print("🔬 Scientific Identifiers:")
    for cite in science_cites:
        print(f"    - {cite.matched_text()}")
        print(f"      Type: {cite.id_type}, Value: {cite.id_value}")
        print()

    print("💼 Other Citations (case law, etc.):")
    for cite in other_cites:
        print(f"    - {cite.matched_text()} ({type(cite).__name__})")
        print()

    print("🎉 Integration Complete!")
    print("The extended EyeCite functionality is working properly.")

except ImportError as e:
    print(f"❌ Import error: {e}")
    print(
        "Please make sure eyecite is properly installed or the Python path is set correctly."
    )
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
