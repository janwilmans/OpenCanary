#!/usr/bin/env python3
""" sort and summarize the number of issues per rule and totals
"""

import traceback
import sys
import os
from util import *

verbose = False


def read():
    results = []
    for line in sys.stdin:
        results += [read_issues_parts(line)]
    return results


issue_descriptions = {}


def unescape(text):
    text = text.replace("&#x27;", "'")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    return text


def limit_string_at_whitespace(input_string, max_length=100):
    if len(input_string) <= max_length:
        return input_string

    # Find the last whitespace within the specified max length
    last_whitespace = input_string.rfind(' ', 0, max_length)

    # If no whitespace is found, cut off at max length
    if last_whitespace == -1:
        return input_string[:max_length]

    return input_string[:last_whitespace]


def add_description(rule, parts):
    if rule in issue_descriptions:
        return

    issue_descriptions[rule] = "[" + parts[Column.COMPONENT] + "]: " + limit_string_at_whitespace(unescape(parts[Column.DESCRIPTION]))

    if verbose:
        issue_descriptions[rule] = issue_descriptions[rule] + "\t@ " + parts[Column.FILE]

    # issue_descriptions[rule] = "[" + parts[Column.Component] + "]: " + parts[Column.Link]


def count_rules(lines):
    results = {}
    for parts in lines:
        check_structured_line_parts(parts)
        rule = parts[Column.RULE]
        add_description(rule, parts)
        if rule in results:
            results[rule] = results[rule] + 1
        else:
            results[rule] = 1
    return results


def get_description(rule):
    return issue_descriptions.get(rule, "")


def show_usage():
    eprint("Usage: <input> | " + os.path.basename(__file__) + [-v])
    eprint("  -v verbose mode: also print the file/location of the first occurance of an issue")


def main():
    global verbose
    if len(sys.argv) > 2:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    if len(sys.argv) == 2:
        verbose = True

    print("Summary of all issues:")
    lines = read()
    check_len = 0
    for rule, count in sorted(count_rules(lines).items(), key=lambda item: (item[1], item[0])):
        check_len += count
        if rule == "rule-missing":
            eprint("-- warning: ignored issue with rule-missing!")
            continue
        warning = "{}: {}".format(rule, count)
        print("{:50}: {}".format(warning, get_description(rule)))

    if check_len != len(lines):
        print("error in script: {}/{} issues accounted for.".format(len(lines), check_len))
    print(f"In total {check_len} issues.")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)
