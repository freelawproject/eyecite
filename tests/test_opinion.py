import sys

sys.path.insert(0, ".")
from eyecite.tokenizers_extended import AttorneyGeneralOpinionsTokenizer

# Test specifically on opinion_AL.txt
with open("tests/assets/opinion_AL.txt", encoding="utf-8") as f:
    text = f.read()

print("Testing Attorney General opinion citation detection...")
print("=" * 60)

# Check if the file was read properly
print(f"File content length: {len(text)} characters")
print(f"First 200 characters: '{text[:200]}...'")
print()

tokenizer = AttorneyGeneralOpinionsTokenizer()
citations = list(tokenizer.find_all_citations(text))

print(f"🤔 Found {len(citations)} Attorney General opinion citations:")
print()

if citations:
    for i, cite in enumerate(citations):
        print(f"  {i + 1}. {cite}")

    print("\n✅ SUCCESS! AG opinions are being detected!")
else:
    print("❌ No AG opinion citations found in the test file.")
    print("\nLet me check if the file contains AG opinion patterns...")

    # Check for AG opinion patterns in the text
    ag_patterns = [
        "AGO",
        "Attorney General",
        "No. 20",
        "N.C. Op. Att'y Gen.",
        "Ala. Op. Att'y Gen.",
    ]
    found_patterns = []
    for pattern in ag_patterns:
        if pattern.lower() in text.lower():
            found_patterns.append(pattern)
            print(f"✅ Found pattern: {pattern}")

    if not found_patterns:
        print("❌ No AG opinion patterns found in the text.")
        print("The AG opinion tokenizer may need adjustment.")

    print("\nNow testing the regex directly...")
    # Test the regex directly
    from eyecite.tokenizers_extended import ATTORNEY_GENERAL_REGEX

    regex_matches = ATTORNEY_GENERAL_REGEX.findall(text)
    print(
        f"Direct regex found: {len(regex_matches)} matches: {regex_matches[:3]}..."
    )
