import re

from eyecite.models import TokenExtractor
from eyecite.models_extended import (
    AttorneyGeneralCitation,
    ConstitutionCitation,
    CourtRuleCitation,
    JournalArticleCitation,
    LegislativeBillCitation,
    RegulationCitation,
    ScientificIdentifierCitation,
    SessionLawCitation,
)

# Federal Constitution Patterns
FEDERAL_CONSTITUTION_REGEX = re.compile(
    r"U\.S\.\sCONST\.\s(?P<article>[IVXLCDM]+),\s§\s(?P<section>\d+)(?:,\scl\.\s(?P<clause>\d+))?",
    re.IGNORECASE,
)
FEDERAL_CONSTITUTION_AMENDMENT_REGEX = re.compile(
    r"U\.S\.\sCONST\.\samend\.\s(?P<amendment>[IVXLCDM]+)(?:,\s§\s(?P<section>\d+))?",
    re.IGNORECASE,
)

# State Constitutions Regex (Combined pattern from documentation)
STATE_CONSTITUTIONS_REGEX = re.compile(
    r"(?:"
    # Georgia: Ga. CONST. art. I, § 1, para. I.
    r"(?P<state_abbr_ga>Ga\.)\sCONST\.\sart\.\s(?P<article_ga>[\w\d]+),\s§\s(?P<section_ga>[\w\d]+),\spara\.\s(?P<paragraph_ga>[\w\d]+)|"
    # Maine: Me. CONST. art. IV, pt. 3, § 1
    r"(?P<state_abbr_me>Me\.)\sCONST\.\sart\.\s(?P<article_me>[\w\d]+),\spt\.\s(?P<part_me>[\d\w]+),\s§\s(?P<section_me>[\d\w]+)|"
    # Massachusetts: Mass. CONST. pt. 1, art. 12
    r"(?P<state_abbr_mass>Mass\.)\sCONST\.\spt\.\s(?P<part_mass>\d+),\sart\.\s(?P<article_mass>[\d\w]+)|"
    # New Hampshire: N.H. CONST. pt. 1, art. 2
    r"(?P<state_abbr_nh>N\.H\.)\sCONST\.\spt\.\s(?P<part_nh>\d+),\sart\.\s(?P<article_nh>[\d\w]+)|"
    # Standard pattern for most states: VA. CONST. art. IV, § 14
    r"(?P<state_abbr>(?:[A-Z]\.){2,}|[A-Z][a-z]+\.)\sCONST\.\sart\.\s(?P<article_std>[\w\d]+)(?:,\s§\s(?P<section_std>[\d\w]+))?"
    r")",
    re.IGNORECASE,
)

# Federal Legislature Patterns
FEDERAL_BILLS_REGEX = re.compile(
    r"(?P<hr>H\.R\.\s(?P<bill_num_hr>\d+))|(?P<sen>S\.\s(?P<bill_num_sen>\d+)),\s(?P<congress_num>\d+)th\sCong\.",
    re.IGNORECASE,
)
FEDERAL_SESSION_LAW_REGEX = re.compile(
    r"Pub\.\sL\.\sNo\.\s(?P<law_num>[\d-]+),\s(?:§\s(?P<section_num>[\d\w-]+),)?\s(?P<volume_num>\d+)\sStat\.\s(?P<page_num>[\d,\s]+)",
    re.IGNORECASE,
)

# Journal Article Pattern
JOURNAL_ARTICLE_REGEX = re.compile(
    r"(?P<volume>\d+)\s+(?P<reporter>[\w\s.&;']+?)\s+(?P<page>\d+)(?:,\s+(?P<pincite>[\d-]+))?\s+\((?P<year>\d{4})\)",
    re.IGNORECASE,
)

# Scientific Identifier Patterns
IDENTIFIER_REGEX_MAP = {
    "DOI": re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Z0-9]+)\b"),
    "PMID": re.compile(r"\bPMID:\s*(\d+)\b"),
    "ISBN": re.compile(
        r"ISBN(?:-13)?:\s*?(97[89](?:-|\s)?\d(?:-|\s)?\d{3}(?:-|\s)?\d{5}(?:-|\s)?\d)"
    ),
    "arXiv": re.compile(r"arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)"),
    "NCT": re.compile(r"\b(NCT\d{8})\b"),
    "Patent": re.compile(r"U\.S\.\s(?:Patent|Pat\.\sApp\.)\sNo\.\s([\d,/-]+)"),
    "CAS": re.compile(r"CAS\s(?:No\.?|Number)\s(\d{2,7}-\d{2}-\d)"),
    "ORCID": re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b"),
}

# Administrative Regulations Patterns (50 state combined)
ADMINISTRATIVE_REGULATIONS_REGEX = re.compile(
    r"(?:"
    r"REGS\.?\sConn\.\sState\sAgencies\s§\s(?P<section_reg_conn>[\d\w-]+)|"
    r"N\.C\.\sAdmin\.\sCode\stit\.(?P<title_nc>\d+)\s*\.\s*(?P<rule_nc>[\d.-]+)|"
    r"N\.D\.\sAdmin\.\sCode\s§\s(?P<section_nd>[\d.-]+)|"
    r"N\.J\.\sAdmin\.\sCode\s§\s(?P<section_nj>[\d:-]+)|"
    r"N\.M\.\sAdmin\.\sCode\s§\s(?P<section_nm>[\d.]+)|"
    r"(?P<title_va>\d+)\sVa\.\sAdmin\.\sCode\s(?P<section_va>[\d.-]+)"
    r")",
    re.IGNORECASE,
)

# Court Rules Patterns (50 state combined - simplified version)
COURT_RULES_REGEX = re.compile(
    r"(?:"
    r"B\.?\s*R\.\sE\.\s(?P<rule_fed_evid>\d+)|"
    r"F\.?\s*R\.\sC\.?\sP\.\s(?P<rule_fed_civ>\d+)|"
    r"F\.?\s*R\.\sC\.?\sR\.\sP\.\s(?P<rule_fed_crim>\d+)|"
    r"N\.C\.\sR\.\sCiv\.\sP\.\s(?P<rule_nc_civ>[\d.-]+)|"
    r"N\.C\.\sGen\.\sStat\.\s§\s(?P<stat_nc>[\d-]+)|"
    r"(?P<state_abbr_court>(?:[A-Z]\.){2,}|[A-Z][a-z]+\.)\sR\.\s(?P<court_type>[\w\s]+)\sR\.\s(?P<rule_num>[\d.-]+)"
    r")",
    re.IGNORECASE,
)

# Scattered Citations Pattern (§§ ranges)
SCATTERED_CITATIONS_REGEX = re.compile(
    r"(?P<full_cite>"
    r"N\.C\.\sGen\.\sStat\.\s(?:§{1,2}\s(?P<section_scattered>[\d\s,\-]+))"
    r")",
    re.IGNORECASE,
)


class StateConstitutionTokenizer:
    """Tokenizer for all U.S. state constitutions."""

    def __init__(self, *args, **kwargs):
        self.regex = STATE_CONSTITUTIONS_REGEX
        self.extractors = [
            TokenExtractor(
                FEDERAL_CONSTITUTION_REGEX,
                self._create_constitution_token,
                {"citation_type": "federal"},
            ),
            TokenExtractor(
                FEDERAL_CONSTITUTION_AMENDMENT_REGEX,
                self._create_constitution_token,
                {"citation_type": "federal_amendment"},
            ),
            TokenExtractor(
                STATE_CONSTITUTIONS_REGEX,
                self._create_constitution_token,
                {"citation_type": "state"},
            ),
        ]

    def _create_constitution_token(self, match, extra, offset=0):
        """Create ConstitutionCitation from match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)

        # Determine jurisdiction and extract proper citation data
        groups = match.groupdict()
        citation_type = extra.get("citation_type", "")

        if citation_type == "federal" or citation_type == "federal_amendment":
            jurisdiction = "United States"
        else:
            # State constitution - check specific state patterns first
            if groups.get("state_abbr_ga"):
                jurisdiction = "Georgia"
            elif groups.get("state_abbr_me"):
                jurisdiction = "Maine"
            elif groups.get("state_abbr_mass"):
                jurisdiction = "Massachusetts"
            elif groups.get("state_abbr_nh"):
                jurisdiction = "New Hampshire"
            else:
                # Standard state pattern - extract from state_abbr_std
                state_abbr = groups.get("state_abbr", "")
                jurisdiction = self._abbr_to_jurisdiction(state_abbr)

        # Extract article/section/amendment from the correct group names
        article = None
        section = None
        amendment = None
        metadata_extra = {}

        if citation_type == "federal":
            article = groups.get("article")
            section = groups.get("section")
        elif citation_type == "federal_amendment":
            amendment = groups.get("amendment")
        else:  # state constitution
            # Check for specific state patterns first
            if groups.get("article_ga"):
                article = groups.get("article_ga")
                section = groups.get("section_ga")
                # Also set paragraph if present
                if groups.get("paragraph_ga"):
                    metadata_extra = {"paragraph": groups.get("paragraph_ga")}
            elif groups.get("article_me"):
                article = groups.get("article_me")
                # Also set part if present
                if groups.get("part_me"):
                    metadata_extra = {"part": groups.get("part_me")}
            elif groups.get("part_mass") and groups.get("article_mass"):
                # Massachusetts format is different
                metadata_extra = {
                    "part": groups.get("part_mass"),
                    "article": groups.get("article_mass"),
                }
            elif groups.get("part_nh") and groups.get("article_nh"):
                # New Hampshire format is different
                metadata_extra = {
                    "part": groups.get("part_nh"),
                    "article": groups.get("article_nh"),
                }
            elif groups.get("article_std"):
                article = groups.get("article_std")
                section = groups.get("section_std")

        # Create metadata dict for constructor
        metadata = {
            "jurisdiction": jurisdiction,
            "article": article,
            "section": section,
            "amendment": amendment,
        }

        # Add extra metadata if any was set
        metadata.update(metadata_extra)

        token = Token(data, start + offset, end + offset, groups)
        citation = ConstitutionCitation(
            token=token,
            index=0,  # Temporary index, will be set by tokenizer
            jurisdiction=jurisdiction,
            metadata=metadata,
        )
        return citation

    def _abbr_to_jurisdiction(self, abbr):
        """Convert state abbreviation to full jurisdiction name."""
        state_map = {
            "Ala.": "Alabama",
            "Cal.": "California",
            "Va.": "Virginia",
            "N.Y.": "New York",
            "Tex.": "Texas",
            "Ga.": "Georgia",
            "Me.": "Maine",
            "Mass.": "Massachusetts",
            "N.H.": "New Hampshire",
            "N.C.": "North Carolina",
            "S.C.": "South Carolina",
            "Ky.": "Kentucky",
            "Tenn.": "Tennessee",
            "Fla.": "Florida",
            "Mich.": "Michigan",
            "Ohio": "Ohio",
        }
        return state_map.get(abbr.strip(), abbr.strip())

    def find_all_citations(self, text: str):
        """Find all constitution citations in text."""
        yield from self._find_citations(text)

    def _find_citations(self, text):
        """Helper method to find citations."""
        citations = []

        # Check federal constitution first
        for match in FEDERAL_CONSTITUTION_REGEX.finditer(text):
            citation = self._create_constitution_token(
                match, {"citation_type": "federal"}
            )
            citations.append(citation)

        for match in FEDERAL_CONSTITUTION_AMENDMENT_REGEX.finditer(text):
            citation = self._create_constitution_token(
                match, {"citation_type": "federal_amendment"}
            )
            citations.append(citation)

        # Check state constitutions
        for match in STATE_CONSTITUTIONS_REGEX.finditer(text):
            citation = self._create_constitution_token(
                match, {"citation_type": "state"}
            )
            citations.append(citation)

        return citations

    def tokenize(self, text: str):
        """Tokenize the entire text for constitution citations."""

        citations = list(self.find_all_citations(text))
        # For now, return empty citation_tokens since we're not fully implementing
        # the full tokenizer interface yet
        return [], [(i, citation) for i, citation in enumerate(citations)]


class JournalArticleTokenizer:
    """Tokenizer for law journal articles."""

    def __init__(self, *args, **kwargs):
        self.regex = JOURNAL_ARTICLE_REGEX
        self.extractors = [
            TokenExtractor(JOURNAL_ARTICLE_REGEX, self._create_journal_token)
        ]

    def _create_journal_token(self, match, extra, offset=0):
        """Create JournalArticleCitation from match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        groups = match.groupdict()

        volume = groups.get("volume")
        reporter = groups.get("reporter", "").strip()
        page = groups.get("page")
        year = groups.get("year")
        pincite = groups.get("pincite")

        metadata = {
            "volume": volume,
            "reporter": reporter,
            "page": page,
            "year": year,
            "pincite": pincite,
        }

        token = Token(data, start + offset, end + offset, groups)
        citation = JournalArticleCitation(
            token=token,
            index=0,  # Temporary index, will be set by tokenizer
            volume=volume,
            reporter=reporter,
            page=page,
            year=year,
            pincite=pincite,
            metadata=metadata,
        )
        return citation

    def find_all_citations(self, text: str):
        """Find all journal article citations in text."""
        for match in JOURNAL_ARTICLE_REGEX.finditer(text):
            citation = self._create_journal_token(match, {})
            yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for journal citations."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


class FederalLegislationTokenizer:
    """Tokenizer for federal bills and session laws."""

    def __init__(self, *args, **kwargs):
        self.extractors = [
            TokenExtractor(FEDERAL_BILLS_REGEX, self._create_bill_token),
            TokenExtractor(
                FEDERAL_SESSION_LAW_REGEX, self._create_session_law_token
            ),
        ]

    def _create_bill_token(self, match, extra, offset=0):
        """Create LegislativeBillCitation from bill match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        groups = match.groupdict()

        # Determine chamber and bill number
        if groups.get("hr"):
            chamber = "House"
            bill_num = groups.get("bill_num_hr")
        else:
            chamber = "Senate"
            bill_num = groups.get("bill_num_sen")

        congress_num = groups.get("congress_num")

        metadata = {
            "chamber": chamber,
            "bill_num": bill_num,
            "congress_num": congress_num,
        }

        token = Token(data, start + offset, end + offset, groups)
        citation = LegislativeBillCitation(
            token=token,
            index=0,  # Temporary index, will be set by tokenizer
            jurisdiction="United States",
            chamber=chamber,
            bill_num=bill_num,
            congress_num=congress_num,
            metadata=metadata,
        )
        return citation

    def _create_session_law_token(self, match, extra, offset=0):
        """Create SessionLawCitation from session law match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        groups = match.groupdict()

        jurisdiction = "United States"
        year = None  # Would need to be extracted from context
        volume = groups.get("volume_num")
        page = groups.get("page_num")
        law_num = groups.get("law_num")

        metadata = {"volume": volume, "page": page, "law_num": law_num}

        token = Token(data, start + offset, end + offset, groups)
        citation = SessionLawCitation(
            token=token,
            jurisdiction=jurisdiction,
            year=year,
            volume=volume,
            page=page,
            law_num=law_num,
            metadata=metadata,
        )
        return citation

    def find_all_citations(self, text: str):
        """Find all federal legislation citations in text."""
        # Bills
        for match in FEDERAL_BILLS_REGEX.finditer(text):
            citation = self._create_bill_token(match, {})
            yield citation

        # Session laws
        for match in FEDERAL_SESSION_LAW_REGEX.finditer(text):
            citation = self._create_session_law_token(match, {})
            yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for federal legislation."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


class ScientificIdentifierTokenizer:
    """Tokenizer for various scientific and academic identifiers."""

    def __init__(self, *args, **kwargs):
        self.extractors = [
            TokenExtractor(
                regex, self._create_identifier_token, {"id_type": id_type}
            )
            for id_type, regex in IDENTIFIER_REGEX_MAP.items()
        ]

    def _create_identifier_token(self, match, extra, offset=0):
        """Create ScientificIdentifierCitation from match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        id_type = extra["id_type"]
        id_value = match.group(1)

        groups = {"id_type": id_type, "id_value": id_value}
        metadata = groups.copy()

        token = Token(data, start + offset, end + offset, groups)
        citation = ScientificIdentifierCitation(
            token=token, id_type=id_type, id_value=id_value, metadata=metadata
        )
        return citation

    def find_all_citations(self, text: str):
        """Find all scientific identifier citations in text."""
        for id_type, regex in IDENTIFIER_REGEX_MAP.items():
            for match in regex.finditer(text):
                citation = self._create_identifier_token(
                    match, {"id_type": id_type}
                )
                yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for scientific identifiers."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


class AdministrativeRegulationsTokenizer:
    """Tokenizer for administrative regulations from various U.S. states."""

    def __init__(self, *args, **kwargs):
        self.extractors = [
            TokenExtractor(
                ADMINISTRATIVE_REGULATIONS_REGEX, self._create_regulation_token
            )
        ]

    def _create_regulation_token(self, match, extra, offset=0):
        """Create RegulationCitation from regulation match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        groups = match.groupdict()

        # Determine jurisdiction and regulation details
        if groups.get("section_reg_conn"):
            jurisdiction = "Connecticut"
            section = groups["section_reg_conn"]
            title = None
        elif groups.get("title_nc") and groups.get("rule_nc"):
            jurisdiction = "North Carolina"
            title = groups["title_nc"]
            section = groups["rule_nc"]
        elif groups.get("section_nd"):
            jurisdiction = "North Dakota"
            title = None
            section = groups["section_nd"]
        elif groups.get("section_nj"):
            jurisdiction = "New Jersey"
            title = None
            section = groups["section_nj"]
        elif groups.get("section_nm"):
            jurisdiction = "New Mexico"
            title = None
            section = groups["section_nm"]
        elif groups.get("title_va") and groups.get("section_va"):
            jurisdiction = "Virginia"
            title = groups["title_va"]
            section = groups["section_va"]
        else:
            jurisdiction = "United States"
            title = None
            section = None

        metadata = {"title": title, "section": section}

        token = Token(data, start + offset, end + offset, groups)
        citation = RegulationCitation(
            token=token,
            jurisdiction=jurisdiction,
            title=title,
            section=section,
            metadata=metadata,
        )
        return citation

    def find_all_citations(self, text: str):
        """Find all administrative regulation citations in text."""
        for match in ADMINISTRATIVE_REGULATIONS_REGEX.finditer(text):
            citation = self._create_regulation_token(match, {})
            yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for administrative regulations."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


class CourtRulesTokenizer:
    """Tokenizer for court rules from various U.S. jurisdictions."""

    def __init__(self, *args, **kwargs):
        self.extractors = [
            TokenExtractor(COURT_RULES_REGEX, self._create_court_rule_token)
        ]

    def _create_court_rule_token(self, match, extra, offset=0):
        """Create CourtRuleCitation from court rule match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        groups = match.groupdict()

        # Determine jurisdiction and rule details
        if groups.get("rule_fed_evid"):
            jurisdiction = "United States"
            rule_num = groups["rule_fed_evid"]
            rule_type = "Evidence"
            court = "Federal"
        elif groups.get("rule_fed_civ"):
            jurisdiction = "United States"
            rule_num = groups["rule_fed_civ"]
            rule_type = "Civil Procedure"
            court = "Federal"
        elif groups.get("rule_fed_crim"):
            jurisdiction = "United States"
            rule_num = groups["rule_fed_crim"]
            rule_type = "Criminal Procedure"
            court = "Federal"
        elif groups.get("rule_nc_civ"):
            jurisdiction = "North Carolina"
            rule_num = groups["rule_nc_civ"]
            rule_type = "Civil Procedure"
            court = "Superior Court"
        elif groups.get("stat_nc"):
            jurisdiction = "North Carolina"
            rule_num = groups["stat_nc"]
            rule_type = "Statute"
            court = "General Statutes"
        else:
            jurisdiction = groups.get("state_abbr_court", "United States")
            rule_num = groups.get("rule_num")
            court_type = groups.get("court_type", "")
            rule_type = court_type
            court = court_type

        metadata = {
            "rule_num": rule_num,
            "rule_type": rule_type,
            "court": court,
        }

        token = Token(data, start + offset, end + offset, groups)
        citation = CourtRuleCitation(
            token=token,
            jurisdiction=jurisdiction,
            rule_num=rule_num,
            rule_type=rule_type,
            court=court,
            metadata=metadata,
        )
        return citation

    def find_all_citations(self, text: str):
        """Find all court rule citations in text."""
        for match in COURT_RULES_REGEX.finditer(text):
            citation = self._create_court_rule_token(match, {})
            yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for court rules."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


class ScatteredCitationsTokenizer:
    """Tokenizer for scattered citations with §§ ranges."""

    def __init__(self, *args, **kwargs):
        self.extractors = [
            TokenExtractor(
                SCATTERED_CITATIONS_REGEX, self._create_scattered_token
            )
        ]

    def _create_scattered_token(self, match, extra, offset=0):
        """Create SessionLawCitation from scattered citation match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)
        groups = match.groupdict()

        # This is a North Carolina scattered citation
        jurisdiction = "North Carolina"
        section = groups.get("section_scattered")

        # Check if it's a range (contains multiple sections)
        # For ranges, we'll keep the original format - no need to split since we just want to validate
        if not (section and any(char in section for char in [",", "-", " "])):
            section = section

        metadata = {"section": section, "full_cite": data}

        token = Token(data, start + offset, end + offset, groups)
        citation = SessionLawCitation(
            token=token,
            jurisdiction=jurisdiction,
            chapter_num=section,  # Using chapter_num to store the section info
            metadata=metadata,
        )
        return citation

    def find_all_citations(self, text: str):
        """Find all scattered citation ranges in text."""
        for match in SCATTERED_CITATIONS_REGEX.finditer(text):
            citation = self._create_scattered_token(match, {})
            yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for scattered citations."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


# Attorney General Opinions Patterns (50 state combined from documentation)
ATTORNEY_GENERAL_REGEX = re.compile(
    r"(?:"
    + r"|".join(
        [
            r"(\d+)\sAla\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Alabama: volume page (year)
            r"AGO\s(\d{4})\-(\d+)",  # Alabama AGO format: AGO 2018-046
            r"(\d{4})\sAlaska\sOp\.\sAtt'y\sGen\.\s([\d\w-]+)",  # Alaska: year opinion_num
            r"Ariz\.\sOp\.\sAtt'y\sGen\.\s([\d\w-]+)",  # Arizona: opinion_num (year)
            r"Ark\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Arkansas: opinion_num (year)
            r"(\d+)\sCal\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # California: volume page (year)
            r"Colo\.\sOp\.\sAtt'y\sGen\.\s([\d\w-]+)",  # Colorado: opinion_num (year)
            r"(\d+)\sConn\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Connecticut: volume page (year)
            r"(\d+)\sDel\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Delaware: volume page (year)
            r"Fla\.\sOp\.\sAtt'y\sGen\.\s([\d\w-]+)",  # Florida: opinion_num (year)
            r"Ga\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Georgia: opinion_num (year)
            r"Haw\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Hawaii: opinion_num (year)
            r"Idaho\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Idaho: opinion_num (year)
            r"Ill\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Illinois: opinion_num (year)
            r"Ind\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Indiana: opinion_num (year)
            r"Iowa\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Iowa: page (year)
            r"Kan\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Kansas: opinion_num (year)
            r"Ky\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Kentucky: opinion_num (year)
            r"La\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Louisiana: opinion_num (year)
            r"Me\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Maine: page (year)
            r"(\d+)\sMd\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Maryland: volume page (year)
            r"Mass\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Massachusetts: page (year)
            r"Mich\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Michigan: opinion_num (year)
            r"Minn\.\sOp\.\sAtt'y\sGen\.\s([\d\w-]+)",  # Minnesota: opinion_num (year)
            r"Miss\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Mississippi: page (year)
            r"Mo\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Missouri: opinion_num (year)
            r"(\d+)\sMont\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Montana: volume page (year)
            r"Neb\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Nebraska: opinion_num (year)
            r"Nev\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Nevada: opinion_num (year)
            r"N\.H\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # New Hampshire: page (year)
            r"N\.J\.\sOp\.\sAtt'y\sGen\.\s([\d-]+)",  # New Jersey: opinion_num (year)
            r"N\.M\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # New Mexico: opinion_num (year)
            r"N\.Y\.\sOp\.\sAtt'y\sGen\.\s\((Inf|F)\.\)\sNo\.\s([\d-]+)",  # New York: opinion_type opinion_num (year)
            r"(\d+)\sN\.C\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # North Carolina: volume page (year)
            r"N\.D\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # North Dakota: page (year)
            r"Ohio\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Ohio: opinion_num (year)
            r"Okla\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Oklahoma: opinion_num (year)
            r"(\d+)\sOr\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Oregon: volume page (year)
            r"Pa\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Pennsylvania: opinion_num (year)
            r"R\.I\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Rhode Island: page (year)
            r"S\.C\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # South Carolina: page (year)
            r"S\.D\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # South Dakota: opinion_num (year)
            r"Tenn\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d]+)",  # Tennessee: opinion_num (year)
            r"Tex\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d\w-]+)",  # Texas: opinion_num (year)
            r"Utah\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Utah: opinion_num (year)
            r"Vt\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Vermont: opinion_num (year)
            r"Va\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Virginia: page (year)
            r"Wash\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Washington: opinion_num (year)
            r"W\.\sVa\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # West Virginia: page (year)
            r"Wis\.\sOp\.\sAtt'y\sGen\.\s(\d+)",  # Wisconsin: page (year)
            r"Wyo\.\sOp\.\sAtt'y\sGen\.\sNo\.\s([\d-]+)",  # Wyoming: opinion_num (year)
        ]
    )
    + r")",
    re.IGNORECASE,
)


class AttorneyGeneralOpinionsTokenizer:
    """Tokenizer for Attorney General advisory opinions from all 50 states."""

    def __init__(self, *args, **kwargs):
        self.extractors = [
            TokenExtractor(
                ATTORNEY_GENERAL_REGEX, self._create_ag_opinion_token
            )
        ]

    def _create_ag_opinion_token(self, match, extra, offset=0):
        """Create AttorneyGeneralCitation from AG opinion match."""
        from eyecite.models import Token

        start, end = match.span()
        data = match.group(0)

        # Parse the match groups to determine state and citation details
        groups = match.groups()
        state_abbr = self._extract_state_from_match(data)

        # Extract volume/page or opinion number based on state pattern
        jurisdiction = self._abbr_to_jurisdiction(state_abbr)
        volume = None
        page = None
        opinion_num = None
        opinion_type = None
        year = None

        # The regex captures groups differently based on state format
        if len(groups) >= 2:
            first_group = groups[0]
            second_group = groups[1]

            if first_group and len(first_group) == 4:  # Year format
                year = first_group
                if second_group:
                    if second_group.isdigit():
                        page = second_group
                    else:
                        opinion_num = second_group
            elif first_group and first_group.isdigit():  # Volume format
                volume = first_group
                if second_group and second_group.isdigit():
                    page = second_group
                else:
                    opinion_num = second_group

        # For states with opinion numbers (No. format)
        if "No." in data:
            opinion_num = self._extract_opinion_num(data)

        # For NY-style opinions with type
        if "(Inf.)" in data or "(F.)" in data:
            if "(Inf.)" in data:
                opinion_type = "Inf."
            elif "(F.)" in data:
                opinion_type = "F."

        metadata = {
            "volume": volume,
            "page": page,
            "opinion_num": opinion_num,
            "opinion_type": opinion_type,
            "year": year,
        }

        groups_dict = {"jurisdiction": jurisdiction, "data": data}
        token = Token(data, start + offset, end + offset, groups_dict)
        citation = AttorneyGeneralCitation(
            token=token,
            index=0,  # Required parameter from CitationBase
            jurisdiction=jurisdiction,
            volume=volume,
            page=page,
            opinion_num=opinion_num,
            opinion_type=opinion_type,
            year=year,
            metadata=metadata,
        )
        return citation

    def _extract_state_from_match(self, text: str) -> str:
        """Extract state abbreviation from AG opinion text."""
        state_indicators = {
            "Ala. Op. Att'y Gen.": "Ala.",
            "Alaska Op. Att'y Gen.": "Alaska",
            "Ariz. Op. Att'y Gen.": "Ariz.",
            "Ark. Op. Att'y Gen.": "Ark.",
            "Cal. Op. Att'y Gen.": "Cal.",
            "Colo. Op. Att'y Gen.": "Colo.",
            "Conn. Op. Att'y Gen.": "Conn.",
            "Del. Op. Att'y Gen.": "Del.",
            "D.C. Op. Att'y Gen.": "D.C.",
            "Fla. Op. Att'y Gen.": "Fla.",
            "Ga. Op. Att'y Gen.": "Ga.",
            "Haw. Op. Att'y Gen.": "Haw.",
            "Idaho Op. Att'y Gen.": "Idaho",
            "Ill. Op. Att'y Gen.": "Ill.",
            "Ind. Op. Att'y Gen.": "Ind.",
            "Iowa Op. Att'y Gen.": "Iowa",
            "Kan. Op. Att'y Gen.": "Kan.",
            "Ky. Op. Att'y Gen.": "Ky.",
            "La. Op. Att'y Gen.": "La.",
            "Me. Op. Att'y Gen.": "Me.",
            "Md. Op. Att'y Gen.": "Md.",
            "Mass. Op. Att'y Gen.": "Mass.",
            "Mich. Op. Att'y Gen.": "Mich.",
            "Minn. Op. Att'y Gen.": "Minn.",
            "Miss. Op. Att'y Gen.": "Miss.",
            "Mo. Op. Att'y Gen.": "Mo.",
            "Mont. Op. Att'y Gen.": "Mont.",
            "Neb. Op. Att'y Gen.": "Neb.",
            "Nev. Op. Att'y Gen.": "Nev.",
            "N.H. Op. Att'y Gen.": "N.H.",
            "N.J. Op. Att'y Gen.": "N.J.",
            "N.M. Op. Att'y Gen.": "N.M.",
            "N.Y. Op. Att'y Gen.": "N.Y.",
            "N.C. Op. Att'y Gen.": "N.C.",
            "N.D. Op. Att'y Gen.": "N.D.",
            "Ohio Op. Att'y Gen.": "Ohio",
            "Okla. Op. Att'y Gen.": "Okla.",
            "Or. Op. Att'y Gen.": "Or.",
            "Pa. Op. Att'y Gen.": "Pa.",
            "R.I. Op. Att'y Gen.": "R.I.",
            "S.C. Op. Att'y Gen.": "S.C.",
            "S.D. Op. Att'y Gen.": "S.D.",
            "Tenn. Op. Att'y Gen.": "Tenn.",
            "Tex. Op. Att'y Gen.": "Tex.",
            "Utah Op. Att'y Gen.": "Utah",
            "Vt. Op. Att'y Gen.": "Vt.",
            "Va. Op. Att'y Gen.": "Va.",
            "Wash. Op. Att'y Gen.": "Wash.",
            "W. Va. Op. Att'y Gen.": "W. Va.",
            "Wis. Op. Att'y Gen.": "Wis.",
            "Wyo. Op. Att'y Gen.": "Wyo.",
        }

        for pattern, abbr in state_indicators.items():
            if pattern.lower() in text.lower():
                return abbr

        return "Unknown"  # Fallback

    def _abbr_to_jurisdiction(self, abbr: str) -> str:
        """Convert state abbreviation to full jurisdiction name."""
        state_map = {
            "Ala.": "Alabama",
            "Alaska": "Alaska",
            "Ariz.": "Arizona",
            "Ark.": "Arkansas",
            "Cal.": "California",
            "Colo.": "Colorado",
            "Conn.": "Connecticut",
            "Del.": "Delaware",
            "D.C.": "District of Columbia",
            "Fla.": "Florida",
            "Ga.": "Georgia",
            "Haw.": "Hawaii",
            "Idaho": "Idaho",
            "Ill.": "Illinois",
            "Ind.": "Indiana",
            "Iowa": "Iowa",
            "Kan.": "Kansas",
            "Ky.": "Kentucky",
            "La.": "Louisiana",
            "Me.": "Maine",
            "Md.": "Maryland",
            "Mass.": "Massachusetts",
            "Mich.": "Michigan",
            "Minn.": "Minnesota",
            "Miss.": "Mississippi",
            "Mo.": "Missouri",
            "Mont.": "Montana",
            "Neb.": "Nebraska",
            "Nev.": "Nevada",
            "N.H.": "New Hampshire",
            "N.J.": "New Jersey",
            "N.M.": "New Mexico",
            "N.Y.": "New York",
            "N.C.": "North Carolina",
            "N.D.": "North Dakota",
            "Ohio": "Ohio",
            "Okla.": "Oklahoma",
            "Or.": "Oregon",
            "Pa.": "Pennsylvania",
            "R.I.": "Rhode Island",
            "S.C.": "South Carolina",
            "S.D.": "South Dakota",
            "Tenn.": "Tennessee",
            "Tex.": "Texas",
            "Utah": "Utah",
            "Vt.": "Vermont",
            "Va.": "Virginia",
            "Wash.": "Washington",
            "W. Va.": "West Virginia",
            "Wis.": "Wisconsin",
            "Wyo.": "Wyoming",
        }
        return state_map.get(abbr, abbr)

    def _extract_opinion_num(self, text: str) -> str:
        """Extract opinion number from AG opinion text."""
        import re

        match = re.search(r"No\.\s*([\d-]+)", text)
        if match:
            return match.group(1)
        return None

    def find_all_citations(self, text: str):
        """Find all Attorney General opinion citations in text."""
        for match in ATTORNEY_GENERAL_REGEX.finditer(text):
            citation = self._create_ag_opinion_token(match, {})
            yield citation

    def tokenize(self, text: str):
        """Tokenize the entire text for AG opinions."""
        citations = list(self.find_all_citations(text))
        return [], [(i, citation) for i, citation in enumerate(citations)]


# Update the ExtendedCitationTokenizer to include AG opinions
class ExtendedCitationTokenizer:
    """A tokenizer that combines all extended citation types with the base tokenizer."""

    def __init__(self):
        # Import base tokenizer
        from eyecite.tokenizers import AhocorasickTokenizer

        # Create base tokenizer and get its extractors
        self.base_tokenizer = AhocorasickTokenizer()
        base_extractors = list(self.base_tokenizer.extractors)

        # Create extended extractors
        extended_extractors = []

        # Add constitution extractors
        const_tokenizer = StateConstitutionTokenizer()
        extended_extractors.extend(const_tokenizer.extractors)

        # Add journal extractors
        journal_tokenizer = JournalArticleTokenizer()
        extended_extractors.extend(journal_tokenizer.extractors)

        # Add federal legislation extractors
        fed_leg_tokenizer = FederalLegislationTokenizer()
        extended_extractors.extend(fed_leg_tokenizer.extractors)

        # Add scientific identifier extractors
        sci_tokenizer = ScientificIdentifierTokenizer()
        extended_extractors.extend(sci_tokenizer.extractors)

        # Add administrative regulation extractors
        reg_tokenizer = AdministrativeRegulationsTokenizer()
        extended_extractors.extend(reg_tokenizer.extractors)

        # Add court rules extractors
        court_tokenizer = CourtRulesTokenizer()
        extended_extractors.extend(court_tokenizer.extractors)

        # Add scattered citations extractors
        scattered_tokenizer = ScatteredCitationsTokenizer()
        extended_extractors.extend(scattered_tokenizer.extractors)

        # Add AG opinions extractors
        ag_tokenizer = AttorneyGeneralOpinionsTokenizer()
        extended_extractors.extend(ag_tokenizer.extractors)

        # Combine all extractors
        self.all_extractors = base_extractors + extended_extractors

        # Create a tokenizer with all extractors
        self.combined_tokenizer = AhocorasickTokenizer.__new__(
            AhocorasickTokenizer
        )
        self.combined_tokenizer.extractors = self.all_extractors
        self.combined_tokenizer.__post_init__()

    def tokenize(self, text: str):
        """Tokenize text using combined extractors."""
        return self.combined_tokenizer.tokenize(text)

    def find_all_citations(self, text: str):
        """Find all citations (both base and extended) in text."""
        # Use the standard get_citations function which will use the full combined tokenizer
        # Temporarily replace the default tokenizer
        import eyecite.tokenizers
        from eyecite.find import get_citations

        original_default = eyecite.tokenizers.default_tokenizer
        eyecite.tokenizers.default_tokenizer = self.combined_tokenizer

        try:
            citations = get_citations(text)
        finally:
            # Restore original tokenizer
            eyecite.tokenizers.default_tokenizer = original_default

        return citations


# Create default extended tokenizer instance
default_extended_tokenizer = ExtendedCitationTokenizer()
