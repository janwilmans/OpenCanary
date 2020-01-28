#!/usr/bin/env python3
"""Parse warnings and error messages from MSVC
"""

import traceback, sys, os
from util import *

def isValidRule(rule):
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
        return False
    return True


def create_default_link(filename, line):
    if "/ui_" in filename:
        return ""
    url = urljoin("[[permalink-prefix]]", filename)
    if line == 0:
        links = create_link(3, url)
    else:
        links = create_link(3, url + "#L" + line)
    return links


# fileref can include a colomn number (or any other postfixed information)
# eg. fileref:   /component/inc/foo.h:127:23
#     filename:  /component/inc/foo.h
#     line:      127
def report_issue(fileref, filename, line, rule, description, source, category):
    links = create_default_link(filename, line)

    if isValidRule(rule):
        links += create_link(5, get_feeling_ducky_url(rule))

    if "/ui_" in filename:
        fileref = fileref + " (generated)"

    team = ""
    component = ""
    if (rule == "cmdline"):
        component = "compiler"

    # Priority.Unassigned
    report(3, team, component, fileref, source, rule, category, description, links)


def split_warning_line(line, depth):
    sep = "/"   # using os.sep won't work if post-processing gcc output is done on window, so dont use it
    parts = line.split(": warning:")
    fileref = get_or_default(parts, 0, "fileref parse error")
    fileref = sep.join(fileref.split(sep)[depth:])

    description = get_or_default(parts, 1, "description parse error").strip()
    fileparts = fileref.split(":")
    filename = get_or_default(fileparts, 0, "parse error")
    line = get_or_default(fileparts, 1, "0")
    return fileref, filename, line, description


def parse(line, source, depth):
    rule = "rule-missing"
    category = "warning"
    if "this will be reported only once per input file" in line:
        return
    if "uninitialized" in line:
        rule = "uninitialized"
    if "not used" in line:
        rule = "unused"

    if ": warning" in line:
        fileref, filename, line, description = split_warning_line(line, depth)
        if description.startswith("command line"):
            rule = "cmdline"

        rule_parts = description.split("[-W")
        if len(rule_parts) > 1:
            description = rule_parts[0]
            rule = rule_parts[-1].rstrip("]")

        report_issue(fileref, filename, line, rule, description, source, category)


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint(r"Usage: type <filename> | " + os.path.basename(__file__) + " <sourcename> [/depth=N]")
    eprint(r"  the standard input (captured data from gcc) is transformed to opencanary format")
    eprint(r"  <sourcename> can be any name the identifies where input came from (gcc/clang/other)")
    eprint(r"  /depth=N can be used the specify how deep the build-directory is nested")
    eprint(r"           for example if warnings are output like ../../foo/lib/f.c usung /depth=2 would strip")
    eprint(r"           off the first two levels making the filename output as 'foo/lib/f.c'")
    eprint("")


def main():

    depth = 0
    if len(sys.argv) == 3 and "/depth=" in sys.argv[2].lower():
        depth = int(sys.argv[2].split("=")[1])

    if len(sys.argv) < 2 or (len(sys.argv) == 3 and depth == 0):
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    source = sys.argv[1]

    for raw in sys.stdin:
        line = raw.strip()
        parse(line, source, depth)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)
