#!/usr/bin/env python3

import sys, os, re, html
from enum import IntEnum
from datetime import datetime

# global variable used to query env.txt that is read at main()
envfile = {}

class Priority(IntEnum):
    Unassigned = 3

class Column(IntEnum):
    Prio = 0
    Team = 1
    Component = 2
    File = 3
    Source = 4
    Rule = 5
    Category = 6
    Description = 7
    Link = 8


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


# returns project directory _without_ trailing /
def get_project_dir():
    return normpath(get_from_envfile('CI_PROJECT_DIR'))


# returns projects JOB url _without_ trailing /
def get_job_url():
    return normpath(get_from_envfile('CI_JOB_URL'))


def get_user_email():
    return get_from_envfile('GITLAB_USER_EMAIL')


def get_user_name():
    if is_scheduled_build():
        return "Scheduled build"
    return get_from_envfile('GITLAB_USER_NAME')


def get_commit_message():
    return get_from_envfile('CI_COMMIT_TITLE')


def get_branch_id():
    return get_from_envfile('CI_BUILD_REF_NAME')    # remove get_from_envfile and move it into apply_environment.py


def remove_project_path(pathstr):
    return replace_no_case(pathstr, get_project_dir(), "")


def remove_build_path(pathstr):                     # remove this and strip out file-prefix in apply_environment.py
    parent = os.path.dirname(get_project_dir())
    return replace_no_case(pathstr, parent, "")


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


def reportList(list):
    sprint(join_report_line(list))


def stripSqlEscapingWord(word):
    result = word
    if word.startswith('b"'):
        result = word[1:]
    if word.startswith("b'"):
        result = word[1:]
    return result.strip('"').strip("'")


def stripSqlEscaping(line):
    result = []
    for word in line:
        result += [stripSqlEscapingWord(word)]
    return result


def readIssuesParts(line):
    result = stripSqlEscaping(line.strip().split("|"))
    checkStructuredLineParts(result)
    return result


def checkStructuredLineParts(parts):
    if len(parts) != len(Column):
        eprint("assertion failed: broken structured CSV, line has {}/{} parts:\n {}".format(len(parts), len(Column), parts))
    

def writeStructuredLine(parts):
    checkStructuredLineParts(parts)
    sys.stdout.write("|".join(parts))
    sys.stdout.write("\n")

class KeyNotInEnvironmentFile:
    pass


def get_from_envfile(key):
    return envfile.get(key, KeyNotInEnvironmentFile)


def get_from_envfile_or(key, default_value):
    return envfile.get(key, default_value)


def read_envfile(filename):
    global envfile
    lines = open(filename, "r").read().splitlines()
    for line in lines:
        index = line.find("=")
        if index > 0:
            k = line[:index]
            envfile[k] = line[index + 1:]


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)


# returns the position of the nth occurrence of substring in string
# return -1 if there is no nth occurrence or if n=0 is specified
def find_nth(string, substring, n):
    if (n == 0):
        return -1
    if (n == 1):
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)


def get_feeling_ducky_url(term):
    return r"https://duckduckgo.com/?q=!ducky+msdn+" + term


def get_or_default(list, index, default):
    if index < len(list):
        return list[index]
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
