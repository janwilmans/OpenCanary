#!/usr/bin/env python3
""" apply environment specific transformations
    * add links to git repo 
    * insert job/user information
    see 'def transform(line)', the [[keys]] are replaced using the provided environment file
"""

import traceback, sys, os
from util import *

def show_usage():
    if len(sys.argv) > 1:
        eprint("  I got:", sys.argv)
        eprint("")
    eprint("Usage: <input> | " + os.path.basename(__file__) + " <env.txt>")
    eprint("   where <env.txt> is a mandatory ascii files with key=value pairs")
    eprint("   " + __doc__)


# _Issue_XXX_NN will be concatenated for issues specific pages
# _Issues will be concatenated for the overview page
wiki_url_prefix = "https://wiki.company.nl/wiki/index.php?title=OpenCanary"

def get_wiki_issue_prefix():
    return wiki_url_prefix + "_Issue_"


def get_wiki_main_url():
    return wiki_url_prefix + "_Issues"


# returns projects GIT url _without_ trailing /
def get_permalink_prefix():
    return urljoin(normpath(get_from_envfile('CI_PROJECT_URL')), "blob", get_from_envfile('CI_COMMIT_SHA'))


def transform(line):

    line = line.replace("[[wiki-issue-prefix]]", get_wiki_issue_prefix())
    line = line.replace("[[wiki-url]]", get_wiki_main_url())
    line = line.replace("[[job-url]]", get_job_url())
    line = line.replace("[[branch-id]]", get_branch_id())
    line = line.replace("[[user-name]]", get_user_name())
    line = line.replace("[[commit-message]]", get_commit_message())
    line = line.replace("[[permalink-prefix]]", get_permalink_prefix())
    return line


def main():
    if len(sys.argv) != 2:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    read_envfile(sys.argv[1])
    for line in sys.stdin:
        sys.stdout.write(transform(line))


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)
