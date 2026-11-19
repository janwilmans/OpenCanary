#!/usr/bin/env python3
""" remove issues that are reported more than once by different sources, such as the same warning from gcc and clang,
    or from the issues files of several CI jobs; the source is not compared, and neither are the links, which are made
    from the source. The first issue is kept, with its source and links; order is kept.

    Usage: <input> | deduplicate.py
"""

import argparse
import sys
import util
from util import Column


def show_usage():
    print(__doc__, file=sys.stderr)


def key(parts):
    return tuple(value for column, value in enumerate(parts) if column not in (Column.SOURCE, Column.LINK))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.parse_args()

    seen = set()
    for parts in util.stdin_rows():
        if key(parts) not in seen:
            seen.add(key(parts))
            util.report_list(parts)


if __name__ == "__main__":
    util.run_main(main, show_usage)
