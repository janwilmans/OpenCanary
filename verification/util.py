#!/usr/bin/env python3
import sys, os, re
from enum import IntEnum

# global variable used to query env.txt that is read at main()
envfile = {}


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


def normpath(pathstr):
    # os.path.normpath cant be used here, as it would convert the / back to \ on windows.
    return pathstr.replace("\\", r"/").rstrip("/")


def replace_no_case(instr, old, new):
    regex = re.compile(re.escape(old), re.IGNORECASE)
    return regex.sub(new, instr)


# returns project directory _without_ trailing /
def get_project_dir():
    return normpath(get_from_envfile('CI_PROJECT_DIR'))


# returns projects GIT url _without_ trailing /
def get_git_url():
    return normpath(get_from_envfile('CI_PROJECT_URL'))


# returns projects JOB url _without_ trailing /
def get_job_url():
    return normpath(get_from_envfile('CI_JOB_URL'))


def get_user_email():
    return get_from_envfile('GITLAB_USER_EMAIL')


def get_report_id():
    return get_from_envfile('CI_COMMIT_TITLE')

def get_subject_postfix():
    return get_from_envfile('CI_COMMIT_TITLE')


def remove_project_path(pathstr):
    return replace_no_case(pathstr, get_project_dir(), "")


def remove_build_path(pathstr):
    parent = os.path.dirname(get_project_dir())
    return replace_no_case(pathstr, parent, "")


def report(priority, team, component, filename, source, rule, category, description, link):
    s = "|"  # csv separator
    sprint(
        s.join([str(priority), team, component, filename, source, rule, category, description, link]))


class KeyNotInEnvironmentFile:
    pass


def get_from_envfile(key):
    return envfile.get(key, KeyNotInEnvironmentFile)


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


# _Issue_XXX_NN will be concatenated for issues specific pages
# _Issues will be concatenated for the overview page
wiki_url_prefix = "https://wiki.kindtechnologies.nl/wiki/index.php?title=OpenCanary"


def getWikiUrl(issueId):
    return wiki_url_prefix + "_Issue_" + issueId


def getWikiMainUrl():
    return wiki_url_prefix + "_Issues"


def getFeelingDuckyUrl(term):
    return r"https://duckduckgo.com/?q=!ducky+msdn+" + term


def get_or_default(list, index, default):
    if index < len(list):
        return list[index]
    return default
