#!/usr/bin/env python3
""" create a short html summary of the issues: the number of issues per rule, team, component and category
    the html is meant as the body of an e-mail, so it only uses tables, html attributes and inline styles,
    which is what Outlook (it renders html with Word) supports
"""

import html
import os
import sys
import traceback
import util
from util import Column
from util import eprint

FONT = "font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #1d2330;"
BORDER = "border: 1px solid #d0d5dd;"
HEADER_BACKGROUND = "#f1f3f6"
TOTAL_BACKGROUND = "#e8efff"
NO_NAME = "(none)"
DESCRIPTION_LIMIT = 100   # characters of the description shown per rule


def plural(value, one, many=None):
    return f"{value} {one if value == 1 else many or one + 's'}"


def name(parts, column):
    return html.unescape(parts[column]).strip() or NO_NAME


def sort_key(value, count):
    """fewest issues first, then by name"""
    return (count, value.lower(), value)


def priority_order(priority):
    return (0, int(priority), "") if priority.isdigit() else (1, 0, priority)


def group(issues):
    """per rule the number of issues of each (team, component, category) combination, as an ordered list of
    (rule, priorities, total, [(team, component, category, count), ...])
    priorities are assigned per rule, so a rule normally has one; if it has more they are all listed"""
    rules = {}
    priorities = {}
    descriptions = {}
    for parts in issues:
        rule = name(parts, Column.RULE)
        combinations = rules.setdefault(rule, {})
        key = (name(parts, Column.TEAM), name(parts, Column.COMPONENT), name(parts, Column.CATEGORY))
        combinations[key] = combinations.get(key, 0) + 1
        priorities.setdefault(rule, set()).add(parts[Column.PRIO].strip())
        descriptions.setdefault(rule, shorten(html.unescape(parts[Column.DESCRIPTION]).strip()))
    result = []
    for rule, combinations in rules.items():
        rows = sorted(combinations.items(), key=lambda item: (item[1], [part.lower() for part in item[0]], item[0]))
        rule_priorities = ", ".join(sorted(priorities[rule], key=priority_order))
        result.append((rule, rule_priorities, descriptions[rule], sum(combinations.values()), [key + (count,) for key, count in rows]))
    return sorted(result, key=lambda item: sort_key(item[0], item[3]))


def shorten(text, limit=DESCRIPTION_LIMIT):
    """cut at the last whitespace before the limit, so the table stays readable in an e-mail"""
    if len(text) <= limit:
        return text
    cut = text.rfind(" ", 0, limit)
    return text[:cut if cut > 0 else limit].rstrip() + "…"


def cell(tag, text, align="left", bold=False, background=None, rowspan=1):
    style = f"{BORDER} padding: 4px 10px; {FONT}" + (" font-weight: bold;" if bold else "")
    bgcolor = f' bgcolor="{background}"' if background else ""
    span = f' rowspan="{rowspan}"' if rowspan > 1 else ""
    return f'<{tag} align="{align}" valign="top"{bgcolor}{span} style="{style}">{text}</{tag}>'


def rule_cell(rule, total, rows):
    text = html.escape(rule)
    if rows > 1:
        text += f'<br/><span style="{FONT} font-size: 12px; color: #667085;">{plural(total, "issue")}</span>'
    return cell("td", text, bold=True, rowspan=rows)


def create_summary(issues):
    rules = group(issues)
    total = len(issues)
    teams = {name(parts, Column.TEAM) for parts in issues}
    categories = {name(parts, Column.CATEGORY) for parts in issues}

    result = ['<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8"/>\n<title>OpenCanary summary</title>\n</head>\n']
    result.append(f'<body style="margin: 0; padding: 16px; {FONT}">\n')
    result.append(f'<p style="margin: 0 0 4px; {FONT} font-size: 18px; font-weight: bold;">Software Quality Summary</p>\n')
    result.append(f'<p style="margin: 0 0 12px; {FONT} color: #667085;">{plural(total, "issue")} for '
                  f'{plural(len(rules), "rule")} in {plural(len(categories), "category", "categories")} '
                  f'for {plural(len(teams), "team")}</p>\n')
    if total == 0:
        return "".join(result) + "</body>\n</html>\n"

    result.append('<table cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse;">\n<tr>')
    result.append(cell("th", "Prio", "right", True, HEADER_BACKGROUND))
    for heading in ("Rule", "Description", "Team", "Component", "Category"):
        result.append(cell("th", heading, bold=True, background=HEADER_BACKGROUND))
    result.append(cell("th", "Issues", "right", True, HEADER_BACKGROUND) + '</tr>\n')
    for rule, priorities, description, rule_total, rows in rules:
        for index, (team, component, category, count) in enumerate(rows):
            result.append('<tr>')
            if index == 0:
                result.append(cell("td", html.escape(priorities), "right", rowspan=len(rows)) + rule_cell(rule, rule_total, len(rows)))
                result.append(cell("td", html.escape(description), rowspan=len(rows)))
            result.extend(cell("td", html.escape(value)) for value in (team, component, category))
            result.append(cell("td", str(count), "right") + '</tr>\n')
    result.append('<tr>' + cell("td", "", background=TOTAL_BACKGROUND) + cell("td", "Total", bold=True, background=TOTAL_BACKGROUND))
    result.append(cell("td", "", background=TOTAL_BACKGROUND) * 4)
    result.append(cell("td", str(total), "right", True, TOTAL_BACKGROUND) + '</tr>\n</table>\n</body>\n</html>\n')
    return "".join(result)


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " < issues.txt > summary.html")
    eprint("   create an html summary of the number of issues per rule (with its priority and the description of its")
    eprint("   first issue, cut at " + str(DESCRIPTION_LIMIT) + " characters), team, component and category,")
    eprint("   from opencanary-formatted issues on stdin, written to stdout")
    eprint("   the rows of a rule are grouped, rules are ordered by number of issues (fewest first) and by name second")
    eprint("   the html only uses tables and inline styles, so it works as an Outlook e-mail body (see send_email.py)")
    eprint("")
    eprint("   -h, --help   show this help")
    eprint("")
    eprint("   input, one issue per line: priority|team|component|file|source|rule|category|description|link-info")
    eprint("")


def main():
    if sys.argv[1:] in (["-h"], ["--help"]):
        show_usage()
        sys.exit(0)

    if len(sys.argv) != 1:
        eprint(os.path.basename(__file__) + " commandline error: invalid argument(s)\n")
        show_usage()
        sys.exit(1)

    issues = [util.read_structured_line(line) for line in sys.stdin if line.strip()]
    sys.stdout.write(create_summary(issues))


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
