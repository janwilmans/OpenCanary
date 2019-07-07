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
    url = urljoin(get_git_url(), "/blob/master", remove_project_path(filename).replace("../", ""))
    if line == 0:
        links = create_link(3, url)
    else:
        links = create_link(3, url + "#L" + line)
    return links

# fileref can include a colomn number (or any other postfixed information)
# eg. fileref:   /component/inc/foo.h:127:23
#     filename:  /component/inc/foo.h
#     line:      127
def report_issue(fileref, filename, line, rule, description, component, category):
    links = create_default_link(filename, line)

    if isValidRule(rule):
        links += create_link(5, getFeelingDuckyUrl(rule))

    if "/ui_" in filename:
        fileref = fileref + " (generated)"

    fileref = remove_build_path(fileref)
    description = remove_build_path(description)
    report(10, "tin", component, fileref, "gcc/clang", rule, category, description, links)


def split_warning_line(line):
    parts = line.split(": warning:")
    fileref = get_or_default(parts, 0, "fileref parse error")
    description = get_or_default(parts, 1, "description parse error").strip()
    component = ""
    fileparts = fileref.split(":")
    filename = get_or_default(fileparts, 0, "parse error")
    line = get_or_default(fileparts, 1, "0")
    return fileref, filename, line, description, component


def parse(line):
    rule = "warning"
    category = "warning"
    if "this will be reported only once per input file" in line:
        return
    if "uninitialized" in line:
        rule = "uninitialized"
    if "not used" in line:
        rule = "unused"

    if ": warning" in line:
        fileref, filename, line, description, component = split_warning_line(line)
        if description.startswith("command line"):
            rule = "cmdline"
            component = "compiler"
        report_issue(fileref, filename, line, rule, description, component, category)


def show_usage():
    eprint(r"Usage: type <filename> | " + os.path.basename(__file__) + " <env.txt> [<inputfile>]")
    eprint(r"  <env.txt> file containing CI environment variables")
    eprint(r"  <inputfile> if the second argument is omitted stdin is used")


def main():
    # only used for debugging
    if len(sys.argv) < 2:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    read_envfile(sys.argv[1])

    # only used for debugging
    if len(sys.argv) > 2:
        sys.stdin = open(sys.argv[2], 'r')

    for raw in sys.stdin:
        line = raw.strip()
        parse(line)


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
