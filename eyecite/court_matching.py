import regex as re
from courts_db import courts


def get_court_by_paren(paren_string: str) -> str | None:
    """Takes the citation string, usually something like "2d Cir", and maps
    that back to the court code.

    Does not work on SCOTUS, since that court lacks parentheticals, and
    needs to be handled after disambiguation has been completed.
    """

    # Remove whitespace and punctuation because citation strings sometimes lack
    # internal spaces, e.g. "Pa.Super." or "SC" (South Carolina)
    court_str = re.sub(r"[^\w]", "", paren_string).lower()

    court_code = None
    if court_str:
        for court in courts:
            s = re.sub(r"[^\w]", "", court["citation_string"]).lower()

            # Check for an exact match first
            if s == court_str:
                return str(court["id"])

            # If no exact match, try to record a startswith match for possible
            # eventual return
            if s.startswith(court_str):
                court_code = court["id"]

        return court_code

    return court_code
