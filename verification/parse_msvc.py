#!/usr/bin/env python3
"""Parse warnings and error messages from MSVC and transform into a uniform comma-separated format
   see https://github.com/janwilmans/OpenCanary?tab=readme-ov-file#gather
"""

import util
import sys
import os
import pathlib
from util import *


def could_not_resolve(filename):
    lower_filename = filename.lower()
    if lower_filename.endswith(".obj"):
        return
    if lower_filename.endswith(".lib"):
        return
    eprint("--- Could not resolve:", filename, "(can be ignored when running without source files present)")


# this gets the filename as it is actually stored on the filesystem, with correct capitalization
def get_real_filename(filename):
    if not on_ci_server():
        return filename
    fs_filename = filename
    if os.path.isfile(filename):
        fs_filename = str(pathlib.Path(filename).resolve())
    else:
        could_not_resolve(filename)
    return fs_filename.replace('\\', '/')


# splits a line in two parts, if the separator is not found the second part is empty
def split_two(line, separator):
    parts = line.split(separator, 1)
    if len(parts) == 2:
        return parts[0], parts[1].strip(" )")
    return line, ""

# msvc messages look like:
# C:\project\...\slot.h(75): warning C4251: description....
# MASM messages look like:
# MASM : warning A4018:invalid command-line option : /utf-8
#
def split_warning_line(line):
    filepart, remainder = split_two(line, ": warning ")
    rule, description = split_two(remainder, ":")

    filename, location = split_two(filepart, "(")
    filename = get_real_filename(filename)

    line_number, column_number = split_two(location, ",")

    fileref = filename
    if line_number != "":
        fileref = f"{filename}:{line_number}"
    else:
        line_number = "0"
    if column_number != "":
        fileref = f"{filename}:{line_number}:{column_number}"
    return fileref, filename, line_number, rule, description


def split_message_line(line):
    parts = line.split(": message :")
    line = 88
    filepart = parts[0]
    description = parts[1]
    component = ""
    return filepart, line, "", description, component


def report_issue(component, fileref, source, rule, category, description):
    links = create_link(Column.RULE.value, get_feeling_ducky_url(rule))
    report(Priority.UNASSIGNED.value, "", component, fileref, source, rule, category, description, links)


def parse_msvc(line, source):
    if line.startswith(" "):  # strip out notes
        return
    if ": message" in line:
        # message lines sometimes seem to contain ": warning", this seem to be caused by compilers writing interleaved to stdout ??
        return
    if "class template optional is only available with C++17 or later." in line:
        # workaround bug where this warning is falsely reported on an unrelated line
        return

    line = line.strip()

    if ": error" in line:
        eprint("-- error found:" + line)
    if ": warning" in line:
        fileref, filename, line, rule, description = split_warning_line(line)
        component = ""
        report_issue(component, fileref, source, rule, "warning", description)
        return
    # if ": message" in line:
    #    filename, line, rule, description, component = split_message_line(line)
    #    reportIssue(filename, line, rule, description, component, "message")
    #    return

    # cl : Command line warning D9002 : ignoring unknown option '/foobar'
    cmdline_marker = "Command line warning"
    if cmdline_marker in line:
        i = line.find(cmdline_marker) + len(cmdline_marker)
        filename = line[:i].strip()
        s = line[i:].split(":")

        fileref = filename
        line = 0
        rule = s[0].strip()
        description = s[1].strip()
        component = "compiler"
        category = "cmdline"

        report_issue(component, fileref, source, rule, category, description)
        return


def show_usage():
    eprint("  I got arguments:", sys.argv)
    eprint(r"Usage: type <filename> | " + os.path.basename(__file__) + " <sourcename>")
    eprint(r"  the standard input (captured data from msvc) is transformed to opencanary format")
    eprint(r"  <sourcename> a name that identifies where input came from eg. a specific build_type)")
    eprint("")


def main():
    if len(sys.argv) < 2:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    source = sys.argv[1]
    for line in sys.stdin:
        parse_msvc(line.strip(), source)


if __name__ == "__main__":
    util.run_main(main, show_usage)
