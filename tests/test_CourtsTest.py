from unittest import TestCase

from eyecite import get_citations


class RegexesTest(TestCase):
    def test_parenthetical_court_parser(self):
        """Check that citations return the appropriate court."""
        samples = {
            "Leday v. State, 983 S.W.2d 713, 718 (Tex. Crim. App. 1998)": "texcrimapp",
            "Worsdale v. City of Killeen, 578 S.W.3d 57, 69-72 (Tex. 2019)": "tex",
            "United States v. Chatman, 584 F.2d 1358 (4th Cir. 1978)": "ca4",
            "Brown v. Wainwright, 665 F.2d 607 (5th Cir. 1982)": "ca5",
            "United States v. Ehrlichman, 546 F.2d 910, 929 (D.C. Cir. 1976)": "cadc",
            "Commonwealth v. Griffin, 24 A.3d 1037, 1041 (Pa. Super. Ct. 2011)": "pasuperct",
            "Commonwealth v. Shaffer, 209 A.3d 957, 969 (Pa. 2019)": "pa",
            "Sixty-Eight Liquors, Inc. v. Colvin , 118 S.W.3d 171 (Ky. 2003)": "ky",
            "Steffan v. Smyzer by and through Rankins , 540 S.W.3d 387, 392 (Ky. Ct. App. 2018)": "kyctapp",
            "Louisiana State Bar Ass\u2019n v. Reis, 513 So. 2d 1173 (La. 1987)": "la",
            "Sursely v. Peake, 551 F.3d 1351, 1357 (Fed. Cir. 2009)": "cafc",
            "Vieland v. First Fed. Sav. Bank (In re Vieland), 41 B.R. 134, 138 (Bankr. N.D. Ohio 1984)": "ohnb",
            "Bowman v. Bond (In re Bowman), 253 B.R. 233, 237 (8th Cir. BAP 2000)": "bap8",
            "United States v. H & R Block, Inc., 833 F. Supp. 2d 36, 49 (D.D.C. 2011)": "dcd",
            "Elhady v. Piehota , 303 F. Supp. 3d 453, 462 (E.D. Va. 2017)": "vaed",
            "See Schneider v. Phila. Gas Works, 223 F. Supp. 3d 308, 316-17 (E.D. Pa. 2016)": "paed",
            "Wisniewski v. Johns-Manville Corp., 812 F.2d 81, 83 (3rd Cir. 1987).": "ca3",
            "Veasey v. Perry, 71 F. Supp. 3d 627, 694 (S.D. Tex. 2014)": "txsd",
            "Animal Legal Defense Fund v. Reynolds, 353 F.Supp.3d 812, 820 (S.D. Iowa 2019)": "iasd",
            "United States v. Shelton, 336 F. Supp. 3d 940 (S.D.N.Y. 2018)": "nysd",
            "See Pool v. Superior Court, 677 P.2d 261, 271-72 (Ariz. 1984)": "ariz",
            "State v. Breit, 930 P.2d 792, 803 (N.M. 1996)": "nm",
            "State Kennedy, 666 P.2d 1316, 1326 (Or. 1983)": "or",
            "State v. Michael J., 875 A.2d 510, 534-35 (Conn. 2005)": "conn",
            "Commonwealth v. Muniz, 164 A.3d 1189 (Pa. 2017)": "pa",
            "Commonwealth v. Shaffer, 209 A.3d 957, 969 (Pa. Jan. 1, 2019)": "pa",
            "Sixty-Eight Liquors, Inc. v. Colvin, 118 S.W.3d 171 (Ky. Aug. 2, 2003)": "ky",
            "Wisniewski v. Johns-Manville Corp., 812 F.2d 81, 83 (3rd Cir. June 30, 1987).": "ca3",
            "Wallace v. Cellco P'ship, No. CV 14-8052-DSF (AS), 2015 WL 13908106, at *7 (C.D. Cal. Feb. 9, 2015)": "cacd",
        }
        for key in samples:
            eyecite_result = get_citations(key)
            self.assertEqual(eyecite_result[0].metadata.court, samples[key])
