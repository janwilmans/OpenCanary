#!/usr/bin/env python3
"""Parse warnings and error messages from MSVC
"""

import traceback, sys, os, pathlib
from util import *

def create_default_link(filename, line):
    project_relative_filename = remove_project_path(filename)
    if project_relative_filename.lower().startswith("c:/"):
        return ""

    url = urljoin("[[permalink-prefix]]", project_relative_filename)
    links = create_link(3, url)

    # check for positive line number
    if str.isdigit(line):
        links = create_link(3, url + "#L" + str(line))
    return links


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
    # prime number 3 means: no specific priority assigned
    return 3

def report_issue(fileref, filename, line, rule, description, component, category):
    links = create_default_link(filename, line)
    if not rule == "":
        links += create_link(5, get_feeling_ducky_url(rule))

    links += create_link(6, "[[wiki-issue-prefix]]" + rule.replace("#", "_"))

    fileref = remove_build_path(fileref)
    description = remove_build_path(description)
    report(get_priority(rule), "tin", component, fileref, "msvc", rule, category, description, links)


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
    description = remaining[idx + 2:]
    component = ""

    lastbrace = filepart.rfind("(")
    filename = get_real_filename(filepart[:lastbrace])
    remaining = filepart[lastbrace:]
    parts = remaining.rstrip().rstrip(")")
    line = parts.split(",")[0][1:]
    fileref = filename + ":" + line
    return fileref, filename, line, rule, description, component


def split_message_line(line):
    parts = line.split(": message :")
    line = 88
    filepart = parts[0]
    description = parts[1]
    component = ""
    return filepart, line, "", description, component


def parse_msvc(line):
    if line.startswith(" "): # strip out notes
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
        report_issue(fileref, filename, line, rule, description, component, "warning")
        return
    # if ": message" in line:
    #    filename, line, rule, description, component = split_message_line(line)
    #    reportIssue(filename, line, rule, description, component, "message")
    #    return

    # cl : Command line warning D9002 : ignoring unknown option '/foobar'
    cmdlineMarker = "Command line warning"
    if cmdlineMarker in line:
        i = line.find(cmdlineMarker) + len(cmdlineMarker)
        filename = line[:i].strip()
        s = line[i:].split(":")
        report_issue(filename, filename, 0, s[0].strip(), s[1].strip(), "compiler", "cmdline")
        return

def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint(r"Usage: type <filename> | " + os.path.basename(__file__) + " <env.txt> [<inputfile>]")
    eprint(r"  <env.txt> file containing CI environment variables")
    eprint(r"  <inputfile> if the second argument is omitted stdin is used")


def main():
    # only used for debugging
    if len(sys.argv) < 2:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    read_envfile(sys.argv[1])

    # only used for debugging
    if len(sys.argv) > 2:
        sys.stdin = open(sys.argv[2], 'r')

    for line in sys.stdin:
        parse_msvc(line)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)
