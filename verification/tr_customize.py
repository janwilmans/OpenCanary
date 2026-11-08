#!/usr/bin/env python3
"""Remove build paths, customize the 'component' and 'team' fields and add permalinks to the source.
    component:/team: rules are read from a rules file (default rules/customize.txt), the text they are matched
    against is the file path with / separators, see examples/customize_toolkit.txt.

    Usage: <input> | tr_customize.py [--rules FILE] [--msvc] [--depth N] [--display-depth N] [--reference-depth N]
"""

import argparse
import re
import sys
import util
from util import Column

windows_separator = "\\"
unix_separator = "/"

options = None   # set by main()
rules = []       # set by main()


def define_component(parts):
    file = parts[Column.FILE].replace(windows_separator, unix_separator)
    return util.first_match(rules, file, "component") or parts[Column.COMPONENT]


def define_team(parts):
    file = parts[Column.FILE].replace(windows_separator, unix_separator)
    return util.first_match(rules, file, "team") or parts[Column.TEAM]


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

    # remove drive letter, if any (X:/), the path is already normalized to '/'. The remainder is
    # linked, use --reference-depth to remove the build directories in front of the repository path
    if re.match(r'\w:/', file):
        return file[3:], True

    # not a system path
    return file, True


def get_sanitized_build_path(parts):
    file = parts[Column.FILE].replace(windows_separator, unix_separator)  # normalize to unix style
    file, needs_link = remove_system_paths(file)
    return file.lstrip(unix_separator), needs_link


# creates one or more links, by default only one, in the format "[Column.FILE.value]{url}" means it will
# create an URL for the FILE to link to.
def create_default_links(parts):
    file = parts[Column.FILE]
    parts = file.split(":")
    filename = util.get_or_default(parts, 0, "")
    line_number = util.get_or_default(parts, 1, "0")
    # _column_number = util.get_or_default(parts, 2, 0)  # ignored if present

    if options.reference_depth > 0:
        filename = unix_separator.join(filename.split(unix_separator)[options.reference_depth:])

    url = util.urljoin("[[permalink-prefix]]", filename)

    # check for positive line number
    if str.isdigit(line_number):
        links = util.create_link(Column.FILE.value, url + "#L" + line_number)
    else:
        links = util.create_link(Column.FILE.value, url)
    return links


def create_display_path(parts):
    file = parts[Column.FILE]

    if options.display_depth > 0:
        file = unix_separator.join(file.split(unix_separator)[options.display_depth:])
    if options.msvc:
        file = file.replace(unix_separator, windows_separator)  # optionally back to windows style for display
    return file


def replace_links(new_links, existing_links):
    result = util.links_to_dict(existing_links)
    result.update(util.links_to_dict(new_links))
    return util.dict_to_links(result)


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
    print(__doc__, file=sys.stderr)


def main():
    global options, rules
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", default=util.default_rules_file("customize.txt"), help="rules file with component:/team: rules")
    parser.add_argument("--msvc", action="store_true", help="transform unix paths back to windows path for display")
    parser.add_argument("--depth", type=int, help="set both display-depth and reference-depth to n")
    parser.add_argument("--display-depth", type=int, default=0, help="strip n leading path elements from the path shown in the report")
    parser.add_argument("--reference-depth", type=int, default=0, help="strip n leading path elements to align the path with [[permalink-prefix]]")
    options = parser.parse_args(util.legacy_args(sys.argv[1:], ["msvc", "depth", "display-depth", "reference-depth"]))
    if options.depth is not None:
        options.display_depth = options.reference_depth = options.depth
    rules = util.load_rules(options.rules)

    for line in sys.stdin:
        customize(line)


if __name__ == "__main__":
    util.run_main(main, show_usage)
