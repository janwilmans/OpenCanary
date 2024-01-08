#!/usr/bin/env python3
"""Remove build paths, customize 'component' field
"""

import traceback
import sys
import os
import re
import util
from util import Column
from util import eprint

msvc = False


def define_component(parts):
    file = parts[Column.FILE].replace("\\", r"/")
    if "lib/toolkit" in file:
        return "toolkit"
    if "/sensing" in file:
        return "sensing"
    if "/tooling/" in file:
        return "tooling"
    if "/keylok" in file:
        return "device"
    if "/vqt" in file:
        return "UI"
    if "/taskcommunication" in file:
        return "IPC"
    if "/viceventlog" in file:
        return "logging"
    if "/logviewer" in file:
        return "logviewer"
    if "/lib/shmemlib" in file:
        return "IPC"
    return ""


def define_team(parts):
    file = parts[Column.FILE].replace("\\", r"/")
    if "/lib/" in file:
        return "platform"
    if "/infrastructure/" in file:
        return "platform"
    if "/window.cc" in file:
        return "project"
    if "/kernel" in file:
        return "project"
    return "platform"


def get_substring_end_position(needle, haystack):
    position = haystack.find(needle)
    if position == -1:
        return 0
    return position + len(needle)


def remove_pattern(input_string, pattern):
    # Search for the pattern in the input string
    match = re.search(pattern, input_string)

    # If the pattern is found, return the end-position
    if match:
        _start_index, end_index = match.span()
        return end_index
    else:
        # If the pattern is not found, return -1
        return -1

# notice [[marker]] is prefixed to indicate the path needs to be fixed
# by create_default_link()
def remove_build_path(parts):
    file = parts[Column.FILE]
    uniform_filepath = file.replace("\\", r"/")

    end_position = remove_pattern(uniform_filepath, r".*Program\sFiles/Microsoft.*/\d+/\w+/")
    if end_position != -1:
        return file[end_position:]

    end_position = remove_pattern(uniform_filepath, r"/vcenter[^/]*/")
    if end_position != -1:
        return "[[marker]]" + file[end_position:]

    # remove X:\
    if re.search(r'\w:\\', file):
        return file[3:]

    return file


def create_default_link(parts):
    file = parts[Column.FILE]
    parts = file.split(":")
    filename = util.get_or_default(parts, 0, "")
    line_number = util.get_or_default(parts, 1, "0")
    #_colomn_number = util.get_or_default(parts, 2, 0)  # ignored if present

    url = util.urljoin("[[permalink-prefix]]", filename.replace("\\", "/"))
    links = util.create_link(3, url)

    # check for positive line number
    if str.isdigit(line_number):
        links = util.create_link(3, url + "#L" + line_number)
    return links


def customize(line):
    global msvc
    parts = line.strip().split("|")
    parts[Column.COMPONENT] = define_component(parts)
    parts[Column.TEAM] = define_team(parts)

    if msvc:
        parts[Column.FILE] = remove_build_path(parts).replace("/", "\\")
    else:
        parts[Column.FILE] = remove_build_path(parts)

    file = parts[Column.FILE]
    if file.startswith("[[marker]]"):
        length = len("[[marker]]")
        parts[Column.FILE] = file[length:]
        parts[Column.LINK] = parts[Column.LINK] + create_default_link(parts)
    util.write_structured_line(parts)


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " [/msvc]")
    eprint("   /msvc transform unix paths generated by lexers/parsers also to windows style paths")
    eprint("   will customize structured CSV, according to user-specific rulesm, see customize()")


def main():
    global msvc
    if len(sys.argv) > 1:
        msvc = True

    for line in sys.stdin:
        customize(line)


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
