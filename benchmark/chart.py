import argparse
import ast
import csv
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

csv.field_size_limit(sys.maxsize)


class Report(object):
    def __init__(self):
        """"""
        self.root = Path(__file__).parent.absolute()
        self.branch1 = None
        self.branch2 = None

    def compare_dataframes(self) -> None:
        """Compare generated data frames between branches

        Generates (mostly) the markdown report for the PR comment

        Returns: None
        """
        gains = []
        losses = []
        dfA = pd.read_csv(
            Path.joinpath(self.root, "outputs", f"data-{self.branch1}.csv")
        )
        dfB = pd.read_csv(
            Path.joinpath(self.root, "outputs", f"data-{self.branch2}.csv")
        )

        head_count = min([len(dfA), len(dfB)])

        dfA = dfA.head(head_count)
        dfB = dfB.head(head_count)

        # Remove columns to enable comparisons
        del dfA["Time"]
        del dfB["Time"]
        del dfA["Total"]
        del dfB["Total"]

        comparison = dfA.compare(dfB)

        with open("outputs/output.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "GAIN", "LOSS", "OPINION_ID", "--"])
            for row in comparison.iterrows():
                non_overlap = set(ast.literal_eval(row[1][0])) ^ set(
                    ast.literal_eval(row[1][1])
                )
                if len(list(non_overlap)) == 0:
                    continue
                for item in list(non_overlap):
                    if item in list(ast.literal_eval(row[1][0])):
                        gains.append(item)
                        row_to_add = [row[0], item, "", dfA.iat[row[0], 0]]
                    else:
                        losses.append(item)
                        row_to_add = [row[0], "", item, dfA.iat[row[0], 0]]
                    writer.writerow(row_to_add)

        # Generate our report based on the provided information.
        with open("outputs/report.md", "w") as f:
            f.write("# The Eyecite Report :eye:\n")
            f.write("")
            f.write(
                f"There were {len(gains)} gains and {len(losses)} losses.\n"
            )
            f.write(
                "You can verify any losses by using the cluster id generated\n"
            )
            f.write("# Output\n")
            f.write("---------\n\n")
            f.write(
                "The following chart illustrates the gains and losses "
                "(if any) from the current pr.\n"
            )

        # Add markdown report file outputs
        df = pd.read_csv("outputs/output.csv")
        with open("outputs/report.md", "a") as md:
            df.to_markdown(buf=md)

        # Remove NAN from file to make it look cleaner
        with open("outputs/report.md", "r+") as f:
            file = f.read()
            file = re.sub("nan", "   ", file)
            f.seek(0)
            f.write(file)
            f.truncate()

        # Add header for time chart for PR comment
        with open("outputs/report.md", "a") as f:
            f.write(
                "\n\n# Speed Comparison\n### Main Branch vs. Current Branch\n"
            )

    def generate_time_chart(self):
        """Generate time chart showing speed across branches

        return: None
        """
        dfA = pd.read_csv(
            Path.joinpath(self.root, "outputs", f"data-{self.branch1}.csv")
        )
        dfB = pd.read_csv(
            Path.joinpath(self.root, "outputs", f"data-{self.branch2}.csv")
        )

        dfA.columns = dfA.columns.str.replace("Total", f"Total {self.branch1}")
        dfB.columns = dfB.columns.str.replace("Total", f"Total {self.branch2}")
        df = pd.merge_asof(dfA, dfB, on="Time")

        df.plot(x="Time", y=[f"Total {self.branch1}", f"Total {self.branch2}"])
        plt.savefig("outputs/time-comparison.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A tool to generate reports.")
    parser.add_argument("--branch1")
    parser.add_argument("--branch2")

    args = parser.parse_args()
    report = Report()
    report.branch1 = args.branch1
    report.branch2 = args.branch2

    # Process the report
    report.compare_dataframes()
    # Generate time chart
    report.generate_time_chart()
