import argparse
import bz2
import csv
import datetime
import sys
from io import StringIO
from pathlib import Path

from eyecite import get_citations

csv.field_size_limit(sys.maxsize)


class Benchmark(object):
    """Benchmark the different eyecite branches"""

    def __init__(self):
        self.root = Path(__file__).parent.absolute()
        self.now = datetime.datetime.now()
        self.times = []
        self.totals = []
        self.list_of_ids = []
        self.opinions = []
        self.count = 0
        self.fields = []

    def fetch_citations(self, row) -> None:
        """Fetch citations from rows opinion data

        return: None
        """
        row_id = row[0]
        row = dict(zip(self.fields, row))
        non_empty_rows = [
            row[field] for field in self.fields if type(row[field]) == str
        ]
        if len(non_empty_rows) == 0:
            return None

        self.list_of_ids.append(row_id)
        found_cites = []
        for op in non_empty_rows:
            found_citations = get_citations(op)
            cites = [cite.token.data for cite in found_citations if cite.token]
            found_cites.extend(cites)

        self.opinions.append(found_cites)
        self.count += len(found_cites)
        self.totals.append(self.count)
        self.times.append((datetime.datetime.now() - self.now).total_seconds())

    def generate_branch_report(self, branch: str) -> None:
        """Generate Branch v Main Report

        return: None
        """
        zipfile = bz2.BZ2File(
            Path.joinpath(self.root, "..", "one-percent.csv.bz2")
        )
        csv_data = csv.reader(StringIO(zipfile.read().decode()), delimiter=",")
        self.fields = next(csv_data)
        for row in csv_data:
            self.fetch_citations(row)
        rows = zip(self.list_of_ids, self.times, self.totals, self.opinions)
        with open(f"../outputs/data-{branch}.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow(["OpinionID", "Time", "Total", "Opinions"])
            writer.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A test program.")
    parser.add_argument("--main", action="store_true")
    parser.add_argument("--branch")
    args = parser.parse_args()

    benchmark = Benchmark()
    benchmark.generate_branch_report(branch=args.branch)
