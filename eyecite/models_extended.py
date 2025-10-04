import logging
from dataclasses import dataclass

from eyecite.models import CitationBase, FullCitation

logger = logging.getLogger(__name__)


@dataclass
class BaseCitation(CitationBase):
    """A base class for new citation types."""

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(CitationBase.Metadata):
        """Define fields on self.metadata."""

        # Add any common metadata fields for new citation types
        jurisdiction: str | None = None

    def __post_init__(self):
        """Set up groups and metadata."""
        super().__post_init__()
        # Allow accessing metadata fields directly from the citation object
        if not hasattr(self, "metadata") or not isinstance(
            self.metadata, self.Metadata
        ):
            self.metadata = self.Metadata(**getattr(self, "metadata", {}))


@dataclass(eq=False, unsafe_hash=False, repr=False)
class ConstitutionCitation(BaseCitation):
    """A citation to a constitution."""

    jurisdiction: str = "United States"
    article: str | None = None
    section: str | None = None
    clause: str | None = None
    amendment: str | None = None
    part: str | None = None
    paragraph: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        article: str | None = None
        section: str | None = None
        clause: str | None = None
        amendment: str | None = None
        part: str | None = None
        paragraph: str | None = None

    def __hash__(self) -> int:
        """ConstitutionCitation objects are equivalent if they have the same
        jurisdiction, article, and section."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in [
                    "jurisdiction",
                    "article",
                    "section",
                    "clause",
                    "amendment",
                ]
                if k in self.groups
            )
            + (type(self).__name__,)
        )


@dataclass(eq=False, unsafe_hash=False, repr=False)
class RegulationCitation(BaseCitation):
    """A citation to a regulation."""

    jurisdiction: str = "United States"
    reporter: str = ""
    volume: str | None = None
    title: str | None = None
    page: str | None = None
    section: str | None = None
    rule: str | None = None
    chapter: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        reporter: str | None = None
        volume: str | None = None
        title: str | None = None
        page: str | None = None
        section: str | None = None
        rule: str | None = None
        chapter: str | None = None

    def corrected_citation_full(self):
        """Return formatted regulatory citation."""
        parts = []
        if self.title:
            parts.append(f"{self.title}")
        parts.append(self.corrected_citation())
        if self.metadata.parenthetical:
            parts.append(f" ({self.metadata.parenthetical})")
        return "".join(parts)

    def __hash__(self) -> int:
        """RegulationCitation objects are equivalent if they have the same
        jurisdiction, reporter, title, and section."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in [
                    "jurisdiction",
                    "reporter",
                    "title",
                    "section",
                    "rule",
                ]
                if k in self.groups
            )
            + (type(self).__name__,)
        )


@dataclass(eq=False, unsafe_hash=False, repr=False)
class CourtRuleCitation(BaseCitation):
    """A citation to a court rule."""

    jurisdiction: str = "United States"
    rule_num: str = ""
    rule_type: str | None = None
    court: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        rule_num: str | None = None
        rule_type: str | None = None
        court: str | None = None

    def __hash__(self) -> int:
        """CourtRuleCitation objects are equivalent if they have the same
        jurisdiction, rule_num, and court."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in ["jurisdiction", "rule_num", "court"]
                if k in self.groups
            )
            + (type(self).__name__,)
        )


@dataclass(eq=False, unsafe_hash=False, repr=False)
class LegislativeBillCitation(BaseCitation):
    """A citation to an unenacted legislative bill."""

    jurisdiction: str = "United States"
    chamber: str = "House"
    bill_num: str = ""
    congress_num: str | None = None
    session_info: str | None = None
    year: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        chamber: str | None = None
        bill_num: str | None = None
        congress_num: str | None = None
        session_info: str | None = None
        year: str | None = None

    def __hash__(self) -> int:
        """LegislativeBillCitation objects are equivalent if they have the same
        jurisdiction, chamber, and bill_num."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in ["jurisdiction", "chamber", "bill_num"]
                if k in self.groups
            )
            + (type(self).__name__,)
        )


@dataclass(eq=False, unsafe_hash=False, repr=False)
class SessionLawCitation(BaseCitation):
    """A citation to an enacted session law."""

    jurisdiction: str = "United States"
    year: str | None = None
    volume: str | None = None
    page: str | None = None
    chapter_num: str | None = None
    act_num: str | None = None
    law_num: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        year: str | None = None
        volume: str | None = None
        page: str | None = None
        chapter_num: str | None = None
        act_num: str | None = None
        law_num: str | None = None

    def __hash__(self) -> int:
        """SessionLawCitation objects are equivalent if they have the same
        jurisdiction, year, and chapter_num."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in ["jurisdiction", "year", "chapter_num", "act_num"]
                if k in self.groups
            )
            + (type(self).__name__,)
        )


@dataclass(eq=False, unsafe_hash=False, repr=False)
class JournalArticleCitation(FullCitation):
    """A citation to a law journal article."""

    volume: str = ""
    reporter: str = ""  # The journal name
    page: str = ""
    year: str = ""
    pincite: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(FullCitation.Metadata):
        """Define fields on self.metadata."""

        volume: str | None = None
        reporter: str | None = None
        page: str | None = None
        year: str | None = None
        pincite: str | None = None

    def __hash__(self) -> int:
        """JournalArticleCitation objects are equivalent if they have the same
        volume, reporter, page, and year."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in ["volume", "reporter", "page", "year"]
                if k in self.groups
            )
            + (type(self).__name__,)
        )

    def corrected_citation_full(self):
        """Return citation with any variations normalized, including extracted
        metadata if any."""
        parts = [self.corrected_citation()]
        if self.metadata.pincite:
            parts.append(f", {self.metadata.pincite}")
        if self.metadata.year:
            parts.append(f" ({self.metadata.year})")
        if self.metadata.parenthetical:
            parts.append(f" ({self.metadata.parenthetical})")
        return "".join(parts)


@dataclass(eq=False, unsafe_hash=False, repr=False)
class ScientificIdentifierCitation(BaseCitation):
    """A citation to a scientific or academic identifier."""

    id_type: str = ""  # E.g., "DOI", "PMID", "ISBN"
    id_value: str = ""

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        id_type: str | None = None
        id_value: str | None = None

    def __hash__(self) -> int:
        """ScientificIdentifierCitation objects are equivalent if they have the same
        id_type and id_value."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in ["id_type", "id_value"]
                if k in self.groups
            )
            + (type(self).__name__,)
        )

    def corrected_citation_full(self):
        """Return formatted version including metadata."""
        return f"{self.id_type.upper()}: {self.id_value}"


@dataclass(eq=False, unsafe_hash=False, repr=False)
class AttorneyGeneralCitation(BaseCitation):
    """A citation to an Attorney General opinion/advisory opinion."""

    jurisdiction: str = ""
    volume: str | None = None
    page: str | None = None
    opinion_num: str | None = None
    opinion_type: str | None = None  # e.g., "Inf.", "F." for NY
    year: str | None = None

    @dataclass(eq=True, unsafe_hash=True)
    class Metadata(BaseCitation.Metadata):
        """Define fields on self.metadata."""

        volume: str | None = None
        page: str | None = None
        opinion_num: str | None = None
        opinion_type: str | None = None
        year: str | None = None

    def __hash__(self) -> int:
        """AttorneyGeneralCitation objects are equivalent if they have the same
        jurisdiction, opinion_num, and year."""
        return hash(
            tuple(
                self.groups.get(k)
                for k in ["jurisdiction", "opinion_num", "year"]
                if k in self.groups
            )
            + (type(self).__name__,)
        )

    def corrected_citation_full(self):
        """Return formatted AG opinion citation."""
        parts = [f"{self.jurisdiction} Op. Att'y Gen."]
        if self.opinion_type:
            parts.append(f"({self.opinion_type})")
        if self.opinion_num:
            parts.append(f"No. {self.opinion_num}")
        elif self.volume and self.page:
            parts.append(f"{self.volume} Op. Att'y Gen. {self.page}")
        if self.year:
            parts.append(f"({self.year})")
        return " ".join(parts)
