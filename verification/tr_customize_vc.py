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

option_msvc = False
option_display_depth = 0
option_reference_depth = 0
option_prefix_search = ""

windows_separator = "\\"
unix_separator = "/"


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
    if "/modules/" in file:
        return "project"
    return "platform"


def get_substring_end_position(needle, haystack):
    position = haystack.find(needle)
    if position == -1:
        return 0
    return position + len(needle)


# returns the end-position of the 'pattern' or -1 if it is not found
def search_for_pattern(input_string, pattern):
    # Search for the pattern in the input string
    match = re.search(pattern, input_string)

    # If the pattern is found, return the end-position
    if match:
        _start_index, end_index = match.span()
        return end_index

    # If the pattern is not found, return -1
    return -1


# returns file, needs_link
#   file =  path with system prefixes removed
#   needs_link = True if path needs to be linked up to an URL, this is not the case of system headers or third-party paths
def remove_system_paths(file):
    end_position = search_for_pattern(file, r".*Program\sFiles/Microsoft.*/\d+/\w+/")
    if end_position != -1:
        return file[end_position:], False

    # remove drive letter, if any (X:\)
    if re.search(r'\w:\\', file):
        return file[3:], False

    # not a system path
    return file, True


def get_sanitized_build_path(parts):
    file = parts[Column.FILE].replace(windows_separator, unix_separator)  # normalize to unix style
    file, needs_link = remove_system_paths(file)
    return file.lstrip(unix_separator), needs_link


# creates one or more links, by default only one, in the format "[Column.FILE.value]{url}" means it will
# create an URL for the FILE to link to.
def create_default_links(parts):
    global option_reference_depth

    file = parts[Column.FILE]
    parts = file.split(":")
    filename = util.get_or_default(parts, 0, "")
    line_number = util.get_or_default(parts, 1, "0")
    # _column_number = util.get_or_default(parts, 2, 0)  # ignored if present

    if option_reference_depth > 0:
        filename = unix_separator.join(filename.split(unix_separator)[option_reference_depth:])

    url = util.urljoin("[[permalink-prefix]]", filename)

    # check for positive line number
    if str.isdigit(line_number):
        links = util.create_link(Column.FILE.value, url + "#L" + line_number)
    else:
        links = util.create_link(Column.FILE.value, url)
    return links


def create_display_path(parts):
    global option_msvc
    global option_display_depth

    file = parts[Column.FILE]

    if option_display_depth > 0:
        file = unix_separator.join(file.split(unix_separator)[option_display_depth:])
    if option_msvc:
        file = file.replace(unix_separator, windows_separator)  # optionally back to windows style for display
    return file


def links_to_dict(links):
    result = dict(re.findall(r'\[(.*?)\]\{(.*?)\}', links))
    return result


def dict_to_links(links):
    result = ""
    for k, v in links.items():
        result += f"[{k}]({v})"
    return result


def replace_links(new_links, existing_links):
    result = links_to_dict(existing_links)
    for k, v in links_to_dict(new_links).items():
        result[k] = v
    return dict_to_links(result)


def customize(line):
    parts = line.strip().split("|")
    parts[Column.COMPONENT] = define_component(parts)
    parts[Column.TEAM] = define_team(parts)
    parts[Column.FILE], needs_link = get_sanitized_build_path(parts)

    if needs_link:
        new_links = create_default_links(parts)
        parts[Column.LINK] = replace_links(new_links, parts[Column.LINK])

    parts[Column.FILE] = create_display_path(parts)
    util.write_structured_line(parts)


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " [/msvc] [/option=n]")
    eprint("   /msvc                    transform unix paths back to windows path for display")
    eprint("   /depth=n                 set both display_depth and reference_path to n")
    eprint("   /display_depth=n         set display_depth to n, used to show a path in the report that looks nice to the user")
    eprint("   /reference_depth=n       set reference_depth to n, used to align the path with [[permalink-prefix]] to form a working URL")
    eprint("   note: any option may also be given as -option instead of /option, this is useful in environments where / is ambiguous")
    eprint("   will customize structured CSV, according to user-specific rules, see customize()")


def apply_settings(arg):
    global option_msvc
    global option_display_depth
    global option_reference_depth
    global option_prefix_search
    try:
        if arg.startswith("msvc="):
            option_msvc = True
            return
        if arg.startswith("depth="):
            value = int(arg.split("=")[1])
            option_display_depth = value
            option_reference_depth = value
            return
        if arg.startswith("display_depth="):
            value = int(arg.split("=")[1])
            option_display_depth = value
            return
        if arg.startswith("reference_depth="):
            value = int(arg.split("=")[1])
            option_reference_depth = value
            return
    except Exception as e:
        eprint(f"Unknown option: {arg} ({e})")
    eprint(f"Unknown option: {arg}")
    show_usage()
    sys.exit(1)


def main():
    for arg in sys.argv[1:]:
        apply_settings(arg[1:].lower())

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
