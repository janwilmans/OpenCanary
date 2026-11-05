#!/usr/bin/env python3
""" re-prioritize rules that have only a few issues (default: 20 or less) to the low-hanging-fruit priority
    so the team can solve those first.

    Usage: <input> | apply_low_hanging_fruit.py [--threshold N]
"""

import argparse
import sys
from collections import Counter
import util
from util import Column, Priority


def show_usage():
    print(__doc__, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--threshold", type=int, default=20, help="rules with at most this many issues are low hanging fruit")
    args = parser.parse_args()

    lines = list(util.stdin_rows())
    counts = Counter(parts[Column.RULE] for parts in lines)
    for line in lines:
        if counts[line[Column.RULE]] <= args.threshold:
            line[Column.PRIO] = str(Priority.LOW_HANGING.value)
            line[Column.DESCRIPTION] = "[LOW] " + line[Column.DESCRIPTION]
        util.report_list(line)


if __name__ == "__main__":
    util.run_main(main, show_usage)
