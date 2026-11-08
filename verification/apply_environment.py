#!/usr/bin/env python3
""" apply environment specific transformations
    * add links to git repo 
    * insert job/user information
    see 'def transform(line)', the [[keys]] are replaced using the provided environment file
"""

import sys
import os
import util
from util import eprint

# returns projects JOB url _without_ trailing /
def get_job_url():
    return util.normpath(util.get_from_envfile('CI_JOB_URL'))


def get_user_email():
    return util.get_from_envfile('GITLAB_USER_EMAIL')


def get_user_name():
    if util.is_scheduled_build():
        return "Scheduled build"
    return util.get_from_envfile('GITLAB_USER_NAME')


def get_commit_message():
    return util.get_from_envfile('CI_COMMIT_TITLE')


# CI_COMMIT_REF_NAME is the branch or tag name, CI_BUILD_REF_NAME its name before GitLab 9.0
def get_branch_id():
    for key in ('CI_COMMIT_REF_NAME', 'CI_BUILD_REF_NAME'):
        branch_id = util.get_from_envfile_or(key, '')
        if branch_id != "":
            return branch_id
    commit_id = util.get_from_envfile_or('CI_COMMIT_SHA', '')
    return commit_id + " (commit_id)" if commit_id != "" else ""


def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint("Usage: <input> | " + os.path.basename(__file__) + " <env.txt>")
    eprint("   where <env.txt> is a mandatory ascii files with key=value pairs")
    eprint("   " + __doc__)


# _Issue_XXX_NN will be concatenated for issues specific pages
# _Issues will be concatenated for the overview page
# configure with WIKI_URL_PREFIX=... in the environment file
DEFAULT_WIKI_URL_PREFIX = "https://wiki.company.nl/wiki/index.php?title=OpenCanary"


def get_wiki_url_prefix():
    return util.get_from_envfile_or("WIKI_URL_PREFIX", DEFAULT_WIKI_URL_PREFIX)


def get_wiki_issue_prefix():
    return get_wiki_url_prefix() + "_Issue_"


def get_wiki_main_url():
    return get_wiki_url_prefix() + "_Issues"


# returns projects GIT url _without_ trailing /
# PERMALINK_PREFIX=... in the environment file overrides it, for example file:///C:/project/repo to link to a local checkout
def get_permalink_prefix():
    if "PERMALINK_PREFIX" in util.envfile:
        return util.normpath(util.envfile["PERMALINK_PREFIX"])
    return util.urljoin(util.normpath(util.get_from_envfile('CI_PROJECT_URL')), "blob", util.get_from_envfile('CI_COMMIT_SHA'))


OPTIONAL_MARKER = 'data-optional=""'


def is_missing(value):
    return value == "" or "not found by get_from_envfile()" in value


def transform(line):
    """replaces the [[keys]]; a line with data-optional="" (one element per line) is removed entirely when one of its
    [[keys]] has no value, so html without scripts, such as an e-mail, does not show an empty or 'not found' item"""
    values = {
        "[[wiki-issue-prefix]]": get_wiki_issue_prefix,
        "[[wiki-url]]": get_wiki_main_url,
        "[[job-url]]": get_job_url,
        "[[branch-id]]": get_branch_id,
        "[[user-name]]": get_user_name,
        "[[commit-message]]": get_commit_message,
        "[[permalink-prefix]]": get_permalink_prefix,
    }
    optional = OPTIONAL_MARKER in line
    for key, get_value in values.items():
        if key in line:
            value = get_value()
            if optional and is_missing(value):
                return ""
            line = line.replace(key, value)
    return line


def main():
    if len(sys.argv) != 2:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    util.read_envfile(sys.argv[1])
    for line in sys.stdin:
        sys.stdout.write(transform(line))


if __name__ == "__main__":
    util.run_main(main, show_usage)
