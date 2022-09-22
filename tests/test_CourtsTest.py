from unittest import TestCase
from find import get_citations
from courts_db import courts

citation_strings = list()
for court in courts:
    citation_strings.append(court["citation_string"])

print("First, check whether there are any duplicates.")
print(len(citation_strings))
citation_strings_set = set(citation_strings)
print(len(citation_strings))


print("Then confirm that all values are in dataset. The following are not:")
for key in sample_courts_in_parens.keys:
    if sample_courts_in_parens[key] not in citation_strings:
        print(sample_courts_in_parens[key])

sample_courts_in_parens = {
    "Leday v. State, 983 S.W.2d 713, 718 (Tex. Crim. App. 1998)": "Tex. Crim. App.",
    "Melgar v. State, 236 S.W.3d 302, 308 (Tex. App.—Houston [1st Dist.] 2007, pet. ref’d)": "Tex. App.—Houston [1st Dist.]",
    "Worsdale v. City of Killeen, 578 S.W.3d 57, 69-72 (Tex. 2019)": "Tex.",
    "United States v. Chatman, 584 F.2d 1358 (4th Cir. 1978)": "4th Cir.",
    "Brown v. Wainwright, 665 F.2d 607 (5th Cir.1982)": "5th Cir.",
    "United States v. Ehrlichman, 546 F.2d 910, 929 (D.C. Cir. 1976)": "D.C. Cir.",
    "Commonwealth v. Griffin, 24 A.3d 1037, 1041 (Pa.Super. 2011)": "Pa. Super.",
    "Commonwealth v. Shaffer, 209 A.3d 957, 969 (Pa. 2019)": "Pa.",
    "Sixty-Eight Liquors, Inc. v. Colvin , 118 S.W.3d 171 (Ky. 2003)": "Ky.",
    "Steffan v. Smyzer by and through Rankins , 540 S.W.3d 387, 392 (Ky. App. 2018)": "Ky. App.",
    "Bottling Co. United, Inc. , 2004-0100 (La. 3/2/05), 894 So. 2d 1096.": "La.",
    "Louisiana State Bar Ass’n v. Reis, 513 So. 2d 1173 (La. 1987)": "La.",
    "Reed v. 7631 Burthe Street, LLC , 2017-0476 (La. App. 4 Cir. 12/28/17), 234 So. 3d 1201": "La. App.",
    "Sursely v. Peake, 551 F.3d 1351, 1357 (Fed. Cir. 2009)": "Fed. Cir.",
    "Vieland v. First Fed. Sav. Bank (In re Vieland), 41 B.R. 134, 138 (Bankr. N.D. Ohio 1984)": "Bankr. N.D. Ohio",
    "Bowman v. Bond (In re Bowman), 253 B.R. 233, 237 (8th Cir. BAP 2000)": "8th Cir. BAP",
    "In re Duman, 00.3 I.B.C.R. 137 (Bankr. D. Idaho 2000)": "Bankr. D. Idaho",
    "United States v. H & R Block, Inc., 833 F. Supp. 2d 36, 49 (D.D.C. 2011)": "D.D.C.",
    "Elhady v. Piehota , 303 F. Supp. 3d 453, 462 (E.D. Va. 2017)": "E.D. Va.",
    "See Schneider v. Phila. Gas Works , 223 F. Supp. 3d 308, 316-17 (E.D. Pa. 2016)": "E.D. Pa.",
    "Wisniewski v. Johns-Manville Corp. , 812 F.2d 81, 83 (3d Cir. 1987).": "3d Cir.",
    "Veasey v. Perry, 71 F. Supp. 3d 627, 694 (S.D. Tex. 2014)": "S.D. Tex.",
    "Animal Legal Defense Fund v. Reynolds, 353 F.Supp.3d 812, 820 (S.D. Iowa 2019)": "S.D. Iowa",
    "United States v. Shelton, 336 F. Supp. 3d 940 (S.D.N.Y. 2018)": "S.D.N.Y.",
    "See Pool v. Superior Court, 677 P.2d 261, 271-72 (Ariz. 1984)": "Ariz.",
    "State v. Breit, 930 P.2d 792, 803 (N.M. 1996)": "N.M.",
    "State Kennedy, 666 P.2d 1316, 1326 (Or. 1983)": "Or.",
    "State v. Michael J., 875 A.2d 510, 534-35 (Conn. 2005)": "Conn.",
    "Thomas v. Eighth Judicial District Court, 402 P.3d 619, 626 (Nev. 2017)": "Nev.",
}


class RegexesTest(TestCase):
    def test_parenthetical_court_parser(self):
        """Check that citations return the appropriate court."""

        self.assertEqual(actual, expected)


# other court indicators (SCOTUS, venue nuetral, state reporters)
sample_courts_from_reporter = {
    "T.S. v. State, 2017 Ark. App. 578, 534 S.W.3d 160": "Ark. App.",
    "Brown v. State, 82 Ark. App. 61, 110 S.W.3d 293 (2003)": "Ark. App",
    "Walden v. State, 2014 Ark. 193, 433 S.W.3d 864.": "Ark.",
    "See State v. Singleton, 124 Ohio St.3d 173, 2009-Ohio-6434, 920 N.E.2d 958": "Ohio",
    "State v. Ryan, 172 Ohio App.3d 281, 2007-Ohio-3092, 874 N.E.2d 853, ¶ 10-14 (1st Dist.)": "Oh. Ct. App. 1st Dist.",
    "Vay v. Commonwealth, 67 Va. App. 236, 257 (2017)": "Va. App.",
    "Butcher v. Commonwealth, 298 Va. 392, 397 n.6 (2020)": "Va.",
    "State v. Belton, 150 N.H. 741, 745 (2004)": "N.H.",
}
