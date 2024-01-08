#!/usr/bin/env python3
"""Parse warnings and error messages from gcc (clang outputs the same format)
"""

import traceback
import sys
import os
from util import *


def is_valid_rule(rule):
    if rule == "":
        return False
    if rule == "rule":
        return False
    if rule == "unused":
        return False
    if rule == "uninitialized":
        return False
    if rule == "cmdline":
        return False
    if rule == "warning":
        return True
    return True


def create_default_link(filename, line):
    url = urljoin("[[permalink-prefix]]", filename)
    if line == 0:
        links = create_link(3, url)
    else:
        links = create_link(3, url + "#L" + line)
    return links


# fileref can include a colomn number (or any other postfixed information)
# eg. file:   /component/inc/foo.h:127:23
#     filename:  /component/inc/foo.h
#     line:      127
def report_issue(file, filename, line, source, rule, category, description):
    links = create_default_link(filename, line)

    if is_valid_rule(rule):
        links += create_link(5, get_feeling_ducky_url(rule))

    team = ""
    component = ""
    if rule == "cmdline":
        component = "compiler"
    report(Priority.UNASSIGNED.value, team, component, file, source, rule, category, description, links)


def split_warning_line(line):
    parts = line.split(": warning:")
    file = get_or_default(parts, 0, "file parse error")
    remainder = get_or_default(parts, 1, "remainder parse error").strip()

    fileparts = file.split(":")
    filename = get_or_default(fileparts, 0, "parse error")
    line = get_or_default(fileparts, 1, "0")

    return file, filename, line, remainder


def parse(line, source):
    rule = "rule-missing"
    category = "warning"
    if "this will be reported only once per input file" in line:
        return
    if "uninitialized" in line:
        rule = "uninitialized"
    if "not used" in line:
        rule = "unused"
    if ": warning" in line:
        file, filename, line, remainder = split_warning_line(line)
        if remainder.startswith("command line"):
            rule = "cmdline"

        rule_parts = remainder.split("[-W")
        if len(rule_parts) > 1:
            description = rule_parts[0].strip()
            rule = rule_parts[-1].rstrip("]")

        report_issue(file, filename, line, source, rule, category, description)


def show_usage():
    eprint("  I got arguments:", sys.argv)
    eprint(r"Usage: type <filename> | " + os.path.basename(__file__) + " <sourcename>")
    eprint(r"  the standard input (captured data from gcc) is transformed to opencanary format")
    eprint(r"  <sourcename> a name that identifies where input came from eg. gcc, clang or a specific build_type)")
    eprint("")


def main():
    if len(sys.argv) < 2:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    source = sys.argv[1]
    for line in sys.stdin:
        parse(line.strip(), source)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise
    except SystemExit:
        raise
    except BrokenPipeError:   # still makes piping into 'head -n' work nicely
        sys.exit(0)
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)
