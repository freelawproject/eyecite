import argparse
import bz2
import csv
import datetime
import json
import os
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Any

from matplotlib import pyplot as plt  # type: ignore

from eyecite import get_citations

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))


csv.field_size_limit(sys.maxsize)

root = Path(__file__).parent.absolute()

MAX_ROWS_IN_MD = 50


class Benchmark:
    """Benchmark the different eyecite branches"""

    def get_filepath(self, filename):
        return Path.joinpath(root, filename)

    def generate_branch_report(self, branch: str) -> None:
        """Generate Report

        :param branch: Is a branch from main or not
        :return: None
        """
        with bz2.BZ2File(self.get_filepath("bulk-file.csv.bz2")) as zipfile:
            csv_data = csv.DictReader(
                StringIO(zipfile.read().decode()),
                delimiter=",",
            )
        count = 0
        now = datetime.datetime.now()
        data = []
        for row in csv_data:
            text: str = (
                row["xml_harvard"]
                or row["html_lawbox"]
                or row["html_columbia"]
                or row["html_anon_2020"]
                or row["html"]
            )
            params: dict[str, Any] = {
                "clean_steps": ["html", "inline_whitespace"]
            }
            if text:
                # Remove XML encodings from xml_harvard
                text = re.sub(r"^<\?xml.*?\?>", "", text, count=1)
                params["markup_text"] = text or ""
            else:
                params["markup_text"] = row["plain_text"]

            found_citations = get_citations(**params)

            # Get the citation text string from the cite object
            cites = [cite.token.data for cite in found_citations if cite.token]

            count += len(cites)
            output = {
                "id": row["id"],
                "cites": cites,
                "total": count,
                "time": (datetime.datetime.now() - now).total_seconds(),
            }
            data.append(output)
        with open(self.get_filepath(f"{branch}.json"), "w") as f:
            json.dump(data, fp=f, indent=4)

    @staticmethod
    def _md_cell(value: str) -> str:
        """Make a value safe to drop into a single Markdown table cell.

        Some citation tokens contain embedded newlines (e.g.
        ``"163 Ohio\\nSt.3d 242"``). A raw newline inside a table cell ends
        the row -- and a blank line ends the whole table -- so the rendered
        report breaks. Collapse any whitespace run (newlines included) to a
        single space and escape the pipe that would otherwise start a new
        column.
        """
        return re.sub(r"\s+", " ", value).replace("|", r"\|").strip()

    def write_report(self, repo, pr_number):
        """Begin building Report.MD file

        :return: None
        """
        stats = getattr(self, "stats", {})
        gains = stats.get("gains", 0)
        losses = stats.get("losses", 0)
        base_total = stats.get("base_total")
        pr_total = stats.get("pr_total")

        # Column widths (min 6) are computed from the *sanitized* cells, so
        # they reflect what is actually rendered.
        max_gain, max_loss = 6, 6
        with open(self.get_filepath("output.csv")) as inp:
            for row in csv.DictReader(inp):
                max_gain = max(max_gain, len(self._md_cell(row["Gain"])))
                max_loss = max(max_loss, len(self._md_cell(row["Loss"])))

        with open(self.get_filepath("report.md"), "w") as f:
            f.write("# The Eyecite Report :eye:\n\n")
            f.write("\n\nGains and Losses\n")
            f.write("---------\n")
            f.write(f"There were {gains} gains and {losses} losses.\n")
            if base_total is not None and pr_total is not None:
                f.write(
                    f"\nTotal citations found: base **{base_total}**, "
                    f"PR **{pr_total}** "
                    f"(net **{pr_total - base_total:+d}**).\n"
                )
            f.write("\n<details>\n")
            f.write("<summary>Click here to see details.</summary>\n\n")

            total_changes = gains + losses
            if total_changes > MAX_ROWS_IN_MD:
                f.write(
                    f"There were {total_changes} changes so we are only "
                    f"displaying the first {MAX_ROWS_IN_MD}. You can review "
                    f"the\nentire list by downloading the output.csv file "
                    f"linked above.\n\n"
                )
            # Generate Markdown table of outputs, up to MAX_ROWS_IN_MD rows.
            with open(self.get_filepath("output.csv")) as inp:
                header = [
                    "id".center(10),
                    "Gain".center(max_gain),
                    "Loss".center(max_loss),
                ]
                f.write(f"| {' | '.join(header)} |\n")
                blank = ["-" * 10, "-" * max_gain, "-" * max_loss]
                f.write(f"| {' | '.join(blank)} |\n")
                for row_count, row in enumerate(csv.DictReader(inp)):
                    if row_count >= MAX_ROWS_IN_MD:
                        break
                    table = [
                        row["ID"].center(10),
                        self._md_cell(row["Gain"]).center(max_gain),
                        self._md_cell(row["Loss"]).center(max_loss),
                    ]
                    f.write(f"| {' | '.join(table)} |\n")

        with open(self.get_filepath("report.md"), "a+") as f:
            f.write("\n\n</details>\n\n")

        # Add header for time chart for PR comment
        with open(self.get_filepath("report.md"), "a") as f:
            f.write("\n\nTime Chart\n")
            f.write("---------\n")

        with open(self.get_filepath("report.md"), "a") as f:
            # Add Link to Repository Chart image
            link = (
                f"\n![image](https://raw.githubusercontent.com/"
                f"{repo}/artifacts/{pr_number}/results/chart.png)\n"
            )
            f.write(link)

    def append_links(self, base, pr, pr_number, repo):
        """Add links to output in PR document report

        :param base: Baseline branch hash (main / original)
        :param pr: Updated branch hash (the PR)
        :param pr_number: PR # trigger
        :param repo: The repository to upload to
        :return: None
        """
        with open(self.get_filepath("report.md"), "a") as f:
            f.write("\n\nGenerated Files\n---------\n\n")
            f.write(
                f"[Base (main) Output](https://raw.githubusercontent.com/"
                f"{repo}/artifacts/{pr_number}/results/{base}.json)\n"
            )
            f.write(
                f"[PR Output](https://raw.githubusercontent.com/"
                f"{repo}/artifacts/{pr_number}/results/{pr}.json)\n"
            )
            f.write(
                f"[Full Output CSV ](https://raw.githubusercontent.com/"
                f"{repo}/artifacts/{pr_number}/results/output.csv)\n"
            )

    def generate_time_chart(self, base: str, pr: str) -> None:
        """Generate the gains/losses CSV and the speed-comparison chart.

        ``base`` is the baseline branch (main / original); ``pr`` is the
        updated branch. A *gain* is a citation the PR finds that the base
        did not; a *loss* is one the base found that the PR no longer does.

        return: None
        """

        with open(self.get_filepath(f"{base}.json")) as f:
            base_file = json.load(f)

        with open(self.get_filepath(f"{pr}.json")) as b:
            pr_file = json.load(b)

        # Compare documents by id rather than by position. Zipping the two
        # lists assumed both runs emitted rows in the exact same order and
        # count; a single skipped/reordered document would have silently
        # misaligned every later comparison.
        base_by_id = {row["id"]: row["cites"] for row in base_file}
        pr_by_id = {row["id"]: row["cites"] for row in pr_file}
        ordered_ids = list(base_by_id) + [
            i for i in pr_by_id if i not in base_by_id
        ]

        gains, losses = 0, 0
        with open(self.get_filepath("output.csv"), "w") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["ID", "Gain", "Loss"])

            for doc_id in ordered_ids:
                base_cites = set(base_by_id.get(doc_id, []))
                pr_cites = set(pr_by_id.get(doc_id, []))
                if base_cites == pr_cites:
                    continue
                for change in sorted(pr_cites - base_cites):
                    writer.writerow([doc_id, change, ""])
                    gains += 1
                for change in sorted(base_cites - pr_cites):
                    writer.writerow([doc_id, "", change])
                    losses += 1

        # Stash summary stats for write_report().
        self.stats = {
            "gains": gains,
            "losses": losses,
            "base_total": sum(len(c) for c in base_by_id.values()),
            "pr_total": sum(len(c) for c in pr_by_id.values()),
        }

        plt.plot(
            [x["time"] for x in base_file],
            [x["total"] for x in base_file],
            label=f"base/{base}",
        )
        plt.plot(
            [x["time"] for x in pr_file],
            [x["total"] for x in pr_file],
            label=f"pr/{pr}",
        )
        plt.legend(loc="upper left")
        plt.ylabel("# Cites Found ", rotation="vertical")
        plt.xlabel("Seconds")
        plt.title("Comparison of Branches")
        plt.savefig(self.get_filepath("chart.png"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr")
    parser.add_argument("--branches", nargs="+")
    parser.add_argument(
        "--base",
        help=(
            "Hash of the baseline (main) branch, used to orient gains vs. "
            "losses. Must be one of the two --branches values. Defaults to "
            "the first branch, so callers that already pass [base, pr] keep "
            "working."
        ),
    )
    parser.add_argument("--reporters", action="store_true")

    args = parser.parse_args()
    repo = (
        "freelawproject/reporters-db"
        if args.reporters
        else "freelawproject/eyecite"
    )
    benchmark = Benchmark()
    if len(args.branches) == 1:
        benchmark.generate_branch_report(branch=args.branches[0])
    elif len(args.branches) == 2:
        # The second branch is the one checked out during this (second) run,
        # so it is the one whose report we (re)generate here.
        benchmark.generate_branch_report(branch=args.branches[1])
        # Orient the diff explicitly: whichever hash is the baseline is the
        # "base"; the other is the PR. This is needed because the eyecite and
        # reporters-db workflows pass the two branches in opposite order.
        base = args.base if args.base in args.branches else args.branches[0]
        pr = next((b for b in args.branches if b != base), base)
        benchmark.generate_time_chart(base, pr)
        benchmark.write_report(repo=repo, pr_number=args.pr)
        benchmark.append_links(base, pr, args.pr, repo)
