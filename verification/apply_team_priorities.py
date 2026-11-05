#!/usr/bin/env python3
""" assign team specific priorities and/or categories to the issues
    the priorities are defined in a rules file (default: rules/priorities.txt), see that file for the format.
"""

import argparse
import sys
import util
from util import Column, Priority


def show_usage():
    print(__doc__, file=sys.stderr)


def get_priority(rules, rule):
    value = util.first_match(rules, rule)
    return Priority.UNASSIGNED.value if value is None else int(value)


def get_category(rules, line):
    value = util.first_match(rules, line[Column.RULE], "category")
    return line[Column.CATEGORY] if value is None else value


def transform(rules, line):
    line[Column.PRIO] = str(get_priority(rules, line[Column.RULE]))
    line[Column.CATEGORY] = get_category(rules, line)
    return line


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", default=util.default_rules_file("priorities.txt"), help="rules file with the team priorities")
    args = parser.parse_args()

    rules = util.load_rules(args.rules)
    for line in util.stdin_rows():
        util.report_list(transform(rules, line))


if __name__ == "__main__":
    util.run_main(main, show_usage)
