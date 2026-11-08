#!/usr/bin/env python3
""" Remove issues the team is not interested in (3rd party code, known noise).
    Lines matching a 'drop' rule in the rules file are removed, see rules/interest.txt for the format.

    Usage: <input> | tr_interest.py [--rules FILE] [--msvc]
      --rules FILE  rules file, default rules/interest.txt
      --msvc        normalize paths, replacing \\ with / before the rules are applied
"""

import argparse
import sys
import util


def show_usage():
    print(__doc__, file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", default=util.default_rules_file("interest.txt"), help="rules file, 'drop' rules remove the line")
    parser.add_argument("--msvc", action="store_true", help="replace \\ with / in the output")
    args = parser.parse_args(util.legacy_args(sys.argv[1:], ["msvc"]))

    rules = util.load_rules(args.rules)
    for line in sys.stdin:
        if args.msvc:
            line = line.replace("\\", "/")
        if util.first_match(rules, line) != "drop":
            sys.stdout.write(line)


if __name__ == "__main__":
    util.run_main(main, show_usage)
