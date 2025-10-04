#!/usr/bin/env python3
"""Simple test to verify that our extended citation types work."""

import os
import sys

# Add the eyecite directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "eyecite"))

try:
    # Test basic imports
    from eyecite.tokenizers_extended import (
        JournalArticleTokenizer,
        StateConstitutionTokenizer,
    )

    print("✅ Imports successful!")

    # Test basic functionality
    tokenizer = JournalArticleTokenizer()
    test_text = "125 Yale L.J. 250 (2015)"

    citations = list(tokenizer.find_all_citations(test_text))

    if len(citations) == 1:
        citation = citations[0]
        print(f"✅ Journal citation found: {citation.matched_text()}")
        print(f"   Volume: {citation.volume}, Reporter: {citation.reporter}")
        print("✅ Test passed!")
    else:
        print("❌ Test failed - expected 1 citation, got", len(citations))
        sys.exit(1)

    # Test constitution tokenizer
    const_tokenizer = StateConstitutionTokenizer()
    const_text = "U.S. CONST. art. I, § 9, cl. 2"
    const_citations = list(const_tokenizer.find_all_citations(const_text))

    if len(const_citations) == 1:
        const_cite = const_citations[0]
        print(f"✅ Constitution citation found: {const_cite.matched_text()}")
        print(
            f"   Jurisdiction: {const_cite.jurisdiction}, Article: {const_cite.article}"
        )
        print("✅ Constitution test passed!")
    else:
        print(
            "❌ Constitution test failed - expected 1 citation, got",
            len(const_citations),
        )
        sys.exit(1)

    print("\n🎉 All integration tests passed!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)
