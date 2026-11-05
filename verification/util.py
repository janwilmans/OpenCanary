#!/usr/bin/env python3

import sys
import os
import re
import html
import shlex
import traceback
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


def legacy_args(args, known):
    """accept the old style options /msvc, -display_depth=2 as --msvc, --display-depth=2, only for the option names
    in 'known' so values such as /absolute/paths are left alone"""
    result = []
    for arg in args:
        name, sep, value = arg.lstrip("/-").partition("=")
        name = name.lower().replace("_", "-")
        if arg[:1] in "/-" and arg[:2] != "--" and name in known:
            arg = "--" + name + sep + value
        result.append(arg)
    return result


def stdin_rows():
    """yields every line of stdin as a list of columns"""
    for line in sys.stdin:
        yield read_structured_line(line)


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


# ---- rule files -----------------------------------------------------------------------------------------------------
# A rule file is a plain text list of "<value> <matcher> [<matcher>...]" lines, evaluated top to bottom, the first rule
# whose matchers all match wins. Matchers: =text (equals), ~text (contains), ?regex (re.search). Use quotes for text with spaces, # starts a
# comment. A value of the form key:value (eg. component:CsCore) lets one file hold several kinds of rules.

class Rule:
    def __init__(self, value, matchers):
        self.value = value
        self.matchers = matchers

    def matches(self, text):
        for matcher in self.matchers:
            if matcher[0] == "=" and text != matcher[1:]:
                return False
            if matcher[0] == "~" and matcher[1:] not in text:
                return False
            if matcher[0] == "?" and not re.search(matcher[1:], text):
                return False
        return True


def parse_rules(lines):
    rules = []
    for number, line in enumerate(lines, 1):
        line = line.split(" #")[0].strip()
        if line == "" or line.startswith("#"):
            continue
        parts = shlex.split(line)
        if len(parts) < 2 or any(m[0] not in "=~?" for m in parts[1:]):
            raise ValueError(f"rule line {number} is invalid: {line!r}, expected '<value> =text|~text|?regex ...'")
        rules.append(Rule(parts[0], parts[1:]))
    return rules


def load_rules(filename):
    return parse_rules(read_lines_from_file(filename))


def first_match(rules, text, key=None):
    """returns the value of the first matching rule, or None. With key, only rules with value 'key:...' are
    considered and the 'key:' prefix is removed from the result."""
    prefix = "" if key is None else key + ":"
    for rule in rules:
        if rule.value.startswith(prefix) and (key is not None or ":" not in rule.value) and rule.matches(text):
            return rule.value[len(prefix):]
    return None


def default_rules_file(name):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules", name)


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def run_main(main, show_usage):
    """common entry point wrapper for all scripts: quiet on ctrl-c / broken pipe, usage + traceback on errors"""
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BrokenPipeError:   # still makes piping into 'head -n' work nicely
        sys.stderr.close()
        sys.exit(0)
    except Exception:  # pylint: disable=broad-except
        eprint(traceback.format_exc())
        show_usage()
        sys.exit(1)


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


def get_cpp_files_from_directory(path, ignore_files=('.opencanaryignore',)):
    rootpath = os.path.abspath(path)
    headers = []
    cpps = []

    for root, _dirs, files in gitignore_parser.walk(rootpath, filenames=list(ignore_files)):
        for file in files:
            filename = os.path.abspath(os.path.join(root, file))
            extension = os.path.splitext(file)[1].lower()
            if extension in (".h", ".hpp"):
                headers += [filename]
            if extension in (".cpp", ".cc"):
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


def get_recursive_files_include_tree(files, visited):
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
