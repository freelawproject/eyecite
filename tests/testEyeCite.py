import os
import sys

sys.path.insert(0, ".")

from eyecite.tokenizers_extended import ExtendedCitationTokenizer

# --- CONFIGURATION ---
# Set the path to the folder containing your test documents.
# This can be a relative path (like 'assets') or an absolute path.
ASSET_PATH = "tests/assets"
# ---------------------


def run_tests():
    """
    Scans all .txt files in the specified asset path, runs eyecite to find
    citations, and prints a detailed report for each file.
    """
    # 1. Get the fully configured eyecite tokenizer. This will include all the
    #    new tokenizers you've added if they are integrated correctly.
    tokenizer = ExtendedCitationTokenizer()
    print("🚀 Initialized Eyecite tokenizer. Starting scan...")

    # 2. Check if the asset directory exists
    if not os.path.isdir(ASSET_PATH):
        print(f"❌ ERROR: The directory '{ASSET_PATH}' was not found.")
        print("Please make sure the ASSET_PATH variable is set correctly.")
        return

    # 3. Iterate over each file in the assets directory
    for filename in sorted(os.listdir(ASSET_PATH)):
        if filename.endswith(".txt"):
            filepath = os.path.join(ASSET_PATH, filename)

            print(f"\n📄 **FILE: {filename}**")
            print("-" * 60)

            try:
                with open(filepath, encoding="utf-8") as f:
                    text = f.read()

                # Show a short preview of the file's content for context
                preview = (
                    text[:1000].replace("\n", " ") + "..."
                    if len(text) > 1000
                    else text
                )
                print(f'Preview: "{preview}"\n')

                # 4. Use the tokenizer to find all citations in the text
                citations = list(tokenizer.find_all_citations(text))

                if citations:
                    print(f"🎯 FOUND {len(citations)} CITATIONS:")
                    # Show details for the first 15 citations found
                    for i, citation in enumerate(citations[:25]):
                        # Print the full citation string and its detected type
                        try:
                            citation_text = str(
                                citation
                            )  # Use str representation
                        except Exception:
                            citation_text = f"{type(citation).__name__} object"
                        print(
                            f"  {i + 1:>2}. {citation_text} (Type: {type(citation).__name__})"
                        )

                        # Print the structured metadata that eyecite parsed
                        if hasattr(citation, "metadata") and citation.metadata:
                            # Use vars() for dataclasses/objects, __dict__ is also fine
                            meta_items = [
                                f"{k}={repr(v)}"
                                for k, v in vars(citation.metadata).items()
                                if v is not None
                                and not k.startswith("_")
                                and k != "full_cite"
                            ]
                            if meta_items:
                                # Show the first 5 parsed metadata items
                                print(
                                    f"     └─ Metadata: {', '.join(meta_items[:25])}"
                                )

                    if len(citations) > 15:
                        print(f"     ... and {len(citations) - 15} more.")
                else:
                    print("⚪ No citations found in this file.")

            except Exception as e:
                print(f"❌ ERROR processing {filename}: {e}")

            print()

    print("🎉 __SCAN COMPLETE!__")


if __name__ == "__main__":
    run_tests()
