#!/usr/bin/env python3
""" write the number of issues in the OpenMetrics text format (https://openmetrics.io), for a CI or monitoring system
    such as Prometheus or GitLab metrics reports, to follow the number of issues over time

    one gauge, opencanary_issues, with a sample per source, rule, category, team, component and priority:
      opencanary_issues{source="gcc",rule="sign-compare",category="warning",team="core",component="net",priority="50"} 3
    sum it in the monitoring system for a total, per team or per rule

    Usage: <input> | create_metrics.py
"""

import argparse
import html
import sys
from collections import Counter
import util
from util import Column

LABELS = [("source", Column.SOURCE), ("rule", Column.RULE), ("category", Column.CATEGORY), ("team", Column.TEAM),
          ("component", Column.COMPONENT), ("priority", Column.PRIO)]


def show_usage():
    print(__doc__, file=sys.stderr)


def escape(value):
    """a label value in OpenMetrics: backslash, double quote and newline are escaped"""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def create_metrics(rows):
    counts = Counter(tuple(html.unescape(parts[column]).strip() for _name, column in LABELS)
                     for parts in rows if len(parts) > max(column for _name, column in LABELS))
    lines = ["# TYPE opencanary_issues gauge",
             "# HELP opencanary_issues Number of issues reported by OpenCanary."]
    for values, count in sorted(counts.items()):
        labels = ",".join(f'{name}="{escape(value)}"' for (name, _column), value in zip(LABELS, values))
        lines.append(f"opencanary_issues{{{labels}}} {count}")
    lines.append("# EOF")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()
    sys.stdout.write(create_metrics(util.stdin_rows()))


if __name__ == "__main__":
    util.run_main(main, show_usage)
