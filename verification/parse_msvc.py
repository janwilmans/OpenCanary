#!/usr/bin/env python3
"""Parse warnings and error messages from MSVC and transform into a uniform comma-separated format
   see https://github.com/janwilmans/OpenCanary?tab=readme-ov-file#gather
"""

import traceback
import sys
import os
import pathlib
from util import *


def get_priority(rule):
    if "C4100" in rule:
        return 70
    if "C4127" in rule:
        return 15
    if "C4211" in rule:
        return 20
    if "C4239" in rule:
        return 20
    if "C4244" in rule:
        return 40
    if "C4245" in rule:
        return 50
    if "C4310" in rule:
        return 15
    if "C4324" in rule:
        return 20
    if "C4389" in rule:
        return 50
    if "C4456" in rule:
        return 10
    if "C4457" in rule:
        return 10
    if "C4458" in rule:
        return 10
    if "C4499" in rule:
        return 55
    if "C4505" in rule:
        return 60
    if "C4611" in rule:
        return 60
    if "C4505" in rule:
        return 60
    if "C4611" in rule:
        return 20
    if "C4701" in rule:
        return 16
    if "C4706" in rule:
        return 30
    if "C4714" in rule:
        return 17
    if "C4918" in rule:
        return 5
    return Priority.UNSET.value


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


def split_warning_line(line):
    parts = line.split(": warning ")
    filepart = parts[0]
    remaining = parts[1]
    idx = remaining.find(":")
    rule = remaining[:idx]
    description = remaining[idx + 1:].strip()
    component = ""

    lastbrace = filepart.rfind("(")
    filename = get_real_filename(filepart[:lastbrace])
    remaining = filepart[lastbrace:]
    line_number = remaining.lstrip("( ").rstrip(" ,)")   
    fileref = filename + ":" + line_number
    return fileref, filename, line_number, rule, description, component


def split_message_line(line):
    parts = line.split(": message :")
    line = 88
    filepart = parts[0]
    description = parts[1]
    component = ""
    return filepart, line, "", description, component


def report_issue(component, fileref, source, rule, category, description):
    links = create_link(Column.SOURCE.value, get_feeling_ducky_url(rule))
    report(str(get_priority(rule)), "[[team]]", component, fileref, source, rule, category, description, links)


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
        fileref, filename, line, rule, description, component = split_warning_line(line)
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
