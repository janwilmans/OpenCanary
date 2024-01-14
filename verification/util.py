#!/usr/bin/env python3

import sys
import os
import re
import html
import gitignore_parser
from enum import IntEnum
from datetime import datetime

# global variable used to query env.txt that is read at main()
envfile = {}


class Priority(IntEnum):
    LOW_HANGING = 7
    UNASSIGNED = 8
    UNSET = 11


class Column(IntEnum):
    PRIO = 0
    TEAM = 1
    COMPONENT = 2
    FILE = 3
    SOURCE = 4
    RULE = 5
    CATEGORY = 6
    DESCRIPTION = 7
    LINK = 8


def on_ci_server():
    return "CI_SERVER" in os.environ


def is_scheduled_build():
    if "CI_PIPELINE_SOURCE" in os.environ:
        return "schedule" in os.environ["CI_PIPELINE_SOURCE"]
    return False


def is_part_of_project(name):
    if "CI_PROJECT_PATH" in os.environ:
        return name.lower() in os.environ["CI_PROJECT_PATH"].lower()
    return False


def normpath(pathstr):
    # os.path.normpath cant be used here, as it would convert the / back to \ on windows.
    return pathstr.replace("\\", r"/").rstrip("/")


def replace_no_case(instr, old, new):
    regex = re.compile(re.escape(old), re.IGNORECASE)
    return regex.sub(new, instr)


def replace_pipe(parts):
    result = []
    for part in parts:
        result += [part.replace("|", "[[pipe]]")]
    return result


def join_report_line(parts):
    s = "|"  # csv separator
    return s.join(replace_pipe(parts))


def report(priority, team, component, filename, source, rule, category, description, link):
    sprint(join_report_line([str(priority), team, component, filename, source, rule, category, html.escape(description), link]))


def report_list(list_value):
    sprint(join_report_line(list_value))


def string_sql_escaping_word(word):
    result = word
    if word.startswith('b"'):
        result = word[1:]
    if word.startswith("b'"):
        result = word[1:]
    return result.strip('"').strip("'")


def string_sql_escaping(line):
    result = []
    for word in line:
        result += [string_sql_escaping_word(word)]
    return result


def read_structured_line(line):
    result = string_sql_escaping(line.strip().split("|"))
    check_structured_line_parts(result)
    return result


def check_structured_line_parts(parts):
    if len(parts) != len(Column):
        eprint(f"assertion failed: broken structured CSV, line has {len(parts)}/{len(Column)} parts:\n {parts}")


def write_structured_line(parts):
    check_structured_line_parts(parts)
    sys.stdout.write("|".join(parts))
    sys.stdout.write("\n")


class KeyNotInEnvironmentFile:
    pass


def get_from_envfile(key):
    return envfile.get(key, "[[" + key + " not found by get_from_envfile()]]")


def get_from_envfile_or(key, default_value):
    return envfile.get(key, default_value)


def read_lines_from_file(filename):
    with open(filename, encoding="utf-8") as file:
        contents = file.read()
        return contents.splitlines()


def read_envfile(filename):
    global envfile
    lines = read_lines_from_file(filename)
    for line in lines:
        index = line.find("=")
        if index > 0:
            k = line[:index]
            envfile[k] = line[index + 1:]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def sprint(*args, **kwargs):
    try:
        print(*args, file=sys.stdout, **kwargs)
    except OSError as exc:
        if exc.errno == 22: # broken pipe causes 'Invalid Argument' on windows
            sys.stderr.close()  # dirty hack to prevent reporting any errors
            sys.exit(1)


# returns the position of the nth occurrence of substring in string
# return -1 if there is no nth occurrence or if n=0 is specified
def find_nth(string, substring, n):
    if n == 0:
        return -1
    if n == 1:
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)


def get_feeling_ducky_url(term):
    return r"https://duckduckgo.com/?q=!ducky+msdn+" + term


def get_or_default(list_value, index, default):
    if index < len(list_value):
        return list_value[index]
    return default


# assuption: pieces are already '/' separated
# note: duplicated '/'s are removed
def urljoin(*args):
    trailing_slash = '/' if args[-1].endswith('/') else ''
    return "/".join(map(lambda x: str(x).strip('/'), args)) + trailing_slash


def create_link(index, url):
    return "[" + str(index) + "]{" + url + "}"


def get_timestamp():
    now = datetime.now()
    return now.strftime("%H:%M:%S.%f")[:12]


def get_cpp_files_from_directory(path):
    rootpath = os.path.abspath(path)
    headers = []
    cpps = []

    for root, _dirs, files in gitignore_parser.walk(rootpath, filenames=['.opencanaryignore']):
        for file in files:
            filename = os.path.abspath(os.path.join(root, file))
            if file.endswith(".h") or file.endswith(".hpp"):
                headers += [filename]
            if file.endswith(".cpp") or file.endswith(".cc"):
                cpps += [filename]
    return headers, cpps


def get_include_file(line):
    match = re.search(r'#include ["<](.*?)[">]', line)
    if match:
        return match.group(1)
    return ""


def get_abspath_from_include_line(file, line):
    include_file = get_include_file(line)
    if include_file == "":
        return ""
    dirname = os.path.dirname(file)
    absname = os.path.join(dirname, include_file)
    if os.path.isfile(absname):
        return os.path.normpath(absname)
    return ""


def get_recursive_files_include_tree(files, visited = set()):
    result = []
    result.extend(files)
    for file in files:
        file = os.path.normpath(file)
        if file in visited:
            continue
        visited.add(file)
        lines = read_lines_from_file(file)
        for line in lines:
            if line.startswith("#include"):
                newfile = get_abspath_from_include_line(file, line)
                if newfile != "":
                    result.extend(get_recursive_files_include_tree([newfile], visited))
    return result
