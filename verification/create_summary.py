#!/usr/bin/env python3
""" create a short html summary of the issues: the number of issues per category and team, with totals
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


def plural(value, one, many=None):
    return f"{value} {one if value == 1 else many or one + 's'}"


def ordered(totals):
    """the names by number of issues, most first, then by name"""
    return sorted(totals, key=lambda name: (-totals[name], name.lower(), name))


def count(issues):
    """per (category, team) the number of issues, and the totals per category and per team"""
    cells, categories, teams = {}, {}, {}
    for parts in issues:
        category = html.unescape(parts[Column.CATEGORY]).strip() or NO_NAME
        team = html.unescape(parts[Column.TEAM]).strip() or NO_NAME
        cells[category, team] = cells.get((category, team), 0) + 1
        categories[category] = categories.get(category, 0) + 1
        teams[team] = teams.get(team, 0) + 1
    return cells, categories, teams


def cell(tag, text, align="left", bold=False, background=None):
    style = f"{BORDER} padding: 4px 10px; {FONT}" + (" font-weight: bold;" if bold else "")
    bgcolor = f' bgcolor="{background}"' if background else ""
    return f'<{tag} align="{align}"{bgcolor} style="{style}">{text}</{tag}>'


def number(value, bold=False, background=None):
    return cell("td", str(value) if value else "", "right", bold, background)


def create_summary(issues):
    cells, categories, teams = count(issues)
    team_names = ordered(teams)
    total = len(issues)

    result = ['<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8"/>\n<title>OpenCanary summary</title>\n</head>\n']
    result.append(f'<body style="margin: 0; padding: 16px; {FONT}">\n')
    result.append(f'<p style="margin: 0 0 4px; {FONT} font-size: 18px; font-weight: bold;">Software Quality Summary</p>\n')
    result.append(f'<p style="margin: 0 0 12px; {FONT} color: #667085;">{plural(total, "issue")} in '
                  f'{plural(len(categories), "category", "categories")} for {plural(len(teams), "team")}</p>\n')
    if total == 0:
        return "".join(result) + "</body>\n</html>\n"

    result.append('<table cellpadding="0" cellspacing="0" border="0" style="border-collapse: collapse;">\n<tr>')
    result.append(cell("th", "Category", bold=True, background=HEADER_BACKGROUND))
    result.append(cell("th", "Total", "right", True, HEADER_BACKGROUND))
    result.extend(cell("th", html.escape(team), "right", True, HEADER_BACKGROUND) for team in team_names)
    result.append('</tr>\n')
    for category in ordered(categories):
        result.append('<tr>' + cell("td", html.escape(category)) + number(categories[category], True, TOTAL_BACKGROUND))
        result.extend(number(cells.get((category, team), 0)) for team in team_names)
        result.append('</tr>\n')
    result.append('<tr>' + cell("td", "Total", bold=True, background=TOTAL_BACKGROUND) + number(total, True, TOTAL_BACKGROUND))
    result.extend(number(teams[team], True, TOTAL_BACKGROUND) for team in team_names)
    result.append('</tr>\n</table>\n</body>\n</html>\n')
    return "".join(result)


def show_usage():
    eprint("Usage: " + os.path.basename(__file__) + " < issues.txt > summary.html")
    eprint("   create an html summary of the number of issues per category and team, with totals,")
    eprint("   from opencanary-formatted issues on stdin, written to stdout")
    eprint("   categories and teams are ordered by number of issues first and by name second")
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
