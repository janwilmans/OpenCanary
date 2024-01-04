#!/usr/bin/env python3
""" sort and summarize the number of issues per rule and totals
"""

import traceback, sys, os
from util import *

verbose = False

def read():
    results = []
    for line in sys.stdin:
        results += [readIssuesParts(line)]
    return results

issue_descriptions = {}

def unescape(text):
    text = text.replace("&#x27;", "'")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    return text

def add_description(rule, parts):
    global issue_descriptions
    if rule in issue_descriptions:
        return
    
    issue_descriptions[rule] = "[" + parts[Column.Component] + "]: " + unescape(parts[Column.Description][:100])
    
    if verbose:
        issue_descriptions[rule] = issue_descriptions[rule] +  "\t@ " + parts[Column.File]
        
    #issue_descriptions[rule] = "[" + parts[Column.Component] + "]: " + parts[Column.Link]

def countRules(lines):
    results = {}
    for parts in lines:
        checkStructuredLineParts(parts)
        rule = parts[Column.Rule]
        add_description(rule, parts)
        if rule in results:
            results[rule] = results[rule] + 1
        else:
            results[rule] = 1
    return results


def get_description(rule):
    global issue_descriptions
    return issue_descriptions.get(rule, "")


def show_usage():
    eprint("Usage: <input> | " + os.path.basename(__file__) + [-v])
    eprint("  -v verbose mode: also print the file/location of the first occurance of an issue")


def main():
    global verbose
    if len(sys.argv) > 2:
        eprint("error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)
        
    if len(sys.argv) == 2:
        verbose = True        

    print("Summary of all issues:")
    lines = read()
    result = []
    check_len = 0
    for rule, count in sorted(countRules(lines).items(), key=lambda item: (item[1], item[0])):
        check_len += count
        if rule == "rule-missing":
            continue
        print("{}: {}\t\t{}".format(rule, count, get_description(rule)))
        
    if check_len != len(lines):
        print("error in script: {}/{} issues accounted for.".format(len(lines), check_len))
    print("In total {} issues.".format(check_len))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        show_usage()
        sys.exit(1)
