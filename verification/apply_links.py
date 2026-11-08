#!/usr/bin/env python3
""" set the links of the rule of every issue from a rules file (default: rules/links.txt), see that file for the format

    link:<url>      the link of the rule; without a matching line the rule keeps the link of the parser, or gets
                    https://duckduckgo.com/?q=!ducky+<source>+<rule> when it has none
    solution:<url>  a page with a solution suggestion, shown as an icon after the rule in the report; none by default

    in the url <source> and <rule> are replaced by the (url encoded) source and rule of the issue, <anchor> by the
    anchor GitHub and GitLab give a markdown heading with the rule: lowercase, only letters, digits, '-' and '_'
    (AP#13 becomes ap13, sign-compare stays sign-compare);
    [[keywords]], such as [[wiki-issue-prefix]], are filled in later by apply_environment.py

    Usage: <input> | apply_links.py [--rules FILE]
"""

import argparse
import sys
import urllib.parse
import util
from util import Column


def show_usage():
    print(__doc__, file=sys.stderr)


def fill(template, source, rule):
    return (template.replace("<source>", urllib.parse.quote(source, safe=""))
                    .replace("<rule>", urllib.parse.quote(rule, safe=""))
                    .replace("<anchor>", util.heading_anchor(rule)))


def transform(rules, parts):
    rule, source = parts[Column.RULE], parts[Column.SOURCE]
    if rule == "":
        return parts
    links = util.links_to_dict(parts[Column.LINK])
    rule_column = str(Column.RULE.value)
    link = util.first_match(rules, rule, "link")
    if link is not None:
        links[rule_column] = fill(link, source, rule)
    elif rule_column not in links:
        links[rule_column] = util.get_rule_url(source, rule)
    solution = util.first_match(rules, rule, "solution")
    if solution is not None:
        links[util.SOLUTION_LINK] = fill(solution, source, rule)
    parts[Column.LINK] = util.dict_to_links(links)
    return parts


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", default=util.default_rules_file("links.txt"), help="rules file with the rule and solution links")
    args = parser.parse_args()

    rules = util.load_rules(args.rules)
    for line in util.stdin_rows():
        util.report_list(transform(rules, line))


if __name__ == "__main__":
    util.run_main(main, show_usage)
