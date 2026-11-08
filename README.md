# OpenCanary
A set of scripts for aggregation, analysis and reporting of build and static analysis results.
Its purpose is to give you a failing CI build if new issues are introduced and to generate a team specific prioritized list of issues to work on.

The purpose of this repo is to provide a set of scripts that can be used to build your own build-canary.
A build-canary is a system that gives you early warning when new problems have been introduced. (so code quality _as you define it_ has regressed). Also a (nightly?) report can be generated to provide you and your team guidance to start improving you code base. The report is a prioritized list (_you define you own team priorities_) of issues to solve.

Branches: `main` is the current version, `classic` (formerly `master`) has the original scripts, see
[conversion_readme.md](conversion_readme.md) for converting a CI pipeline from `classic` to `main`.

The process works in a couple of steps that are executed as post-build steps as part of the CI build.

## Quickstart

New to OpenCanary? [documentation/getting_started.md](documentation/getting_started.md) walks through the first steps,
[documentation/details.md](documentation/details.md) describes every script, its arguments and what it does exactly,
[documentation/rules.md](documentation/rules.md) explains OpenCanary's own rules and how to solve them.

```
cd verification
python3 opencanary.py init        # writes opencanary.toml, point [[input]] at your build log(s)
python3 opencanary.py run         # writes issues.txt (prioritized work list) and report.html
python3 -m unittest               # run the tests
```
`opencanary.py run` needs python 3.11+ (or `pip install tomli`), the individual scripts work with python 3.8+.
Optional tools: `rg` (ripgrep, spelling check in `oc_cpp_issues.py`), `cppcheck`, `clang-format`, `git` and `docopt`, see
[Requirements](documentation/getting_started.md#requirements). On Debian or Ubuntu, install everything with
`sudo apt install python3 ripgrep python3-tomli cppcheck clang-format git python3-docopt`.
On Windows, if `python3` resolves to an older python (check with `python3 --version`), use the `py` launcher instead
(`py opencanary.py run`, `py -m unittest`), it picks the newest installed version.
Every stage can also be used on its own as a filter, `opencanary.py <command>` runs one stage (see `opencanary.py --help`),
for example `cat gcc.log | opencanary.py parse-gcc gcc | opencanary.py prioritize | opencanary.py sort`.

Team specific behavior lives in plain text rule files, first matching line wins (`=` equals, `~` contains, `?` regex):
- `rules/priorities.txt` priority (and category) per rule, **customize this**
- `rules/interest.txt` lines the team is not interested in (3rd party, known noise)
- `rules/customize.txt` component and team per path
- `rules/links.txt` the link of each rule and an optional solution suggestion (an icon after the rule in the report)
- `examples/` has larger example rule sets (CopperSpice, MSVC system headers, toolkit) and a project specific customizer

## Gather
- gcc / clang compiler warnings
- gcc / clang commandline warnings
- msvc warnings
- cppcheck issues
- sanitizer (ubsan, tsan, asan, etc) issues
- clang-tidy
- coverage results
- more?

Parse all warnings/issues into a structured comma-separated format. Actually pipe (|) separated seems to work good, because semicolons (;) and comma (,) are often used in messages and pipe symbols much less. Should a | occur, then its 'escaped' as [[pipe]] instead.

format:
`priority | team | component | fileref | source | rule | category | description | [n]{url}[n]{url}... `

where columns rule -> category -> description are in ordered from fine to coarse
and the lines are ordered in order of priority first and second in order of file(name)
that way issues are clustered per-file as good as possible.

* [0] priority - team assigned priority
* [1] team - name of the team responsible for the file
* [2] component - name of the component the issue is associated to
* [3] fileref - file + linenumber "/path/foo:14" with optional columnnumber "/path/foo:14:35"
* [4] source - the tools that produced the issue (gcc/coverage, cppcheck/opencanary,ubsan,etc.)
* [5] rule - optional tools specific fields (warnings Cxxxx, or POR#xxx")
* [6] category - tool specific (ie. PARSE ERROR, COMPILE ERROR, ISSUE)
* [7] description - the actual message that was reported
* link - tool specific links where [n] refers back to a 0-indexed column (so 0=priority, 1=team etc.), and the named
  link `[solution]{url}`: a page with a solution suggestion for the rule, shown as a small icon after the rule

## category and rule
Its important that the rule is specific enough so advice can be offered on how to handle a particular issue. This is because the rule is what makes links to the Wiki pages unique. Conversely the category must be broad enough to group silimar issues together, but typically only issues with the same priority. However, the latter is not strictly required, specfic rules _can_ have a different priority from their category.

## links
The links are intended to be combined in the report in such a way that when (as an example) the value in 'priority' is clicked, it is linking to the url in [0]{url} etc. This way any tool can add custom links into the report. This is used to create links from the fileref to the source repository (permalinks) so issues can be viewed easily in full context. But also to make the 'rule' clickable, so it links to a wiki page to gather typical solving strategies. The wiki page name is typically generated from the 'rule' name.


## Possible transformations

These steps/stages are suggestions, you can design your own process flow, but this order worked well for me:

- Pre-filter: optional step; remove non-team issues (doing this first prevents unneeded work in following steps)
  - the .opencanaryignore file uses the same fnmatch() syntax that .gitignore uses, currently only oc_cpp_issues.py
    respects these ignore rules.
- Error filter
  - filter out false positives, tooling errors and 3rd party paths (usually a pretty static filter, might be maintained outside the team)
- Interest / Focus on adding value (examples: tr_interest_vc.py, tr_interest_cs.py)
  - filter out what are _not_ errors, but the team should ignore (unmaintained code for example)
  - might seem similar to the previous stage, but the difference is that these are not errors, this is about chosing an focus area.
- Prioritize (see apply_team_priorities.py)
  - assign priorities according to the teams judgement
  - override the priorities to promote rules that have very few issues (to solve low hanging fruit first)
  - **the result of this yields a prioritized work-list for the team**
- Generate report (create_report.py)
  - transform the issue list into a html report for easy access and/or sending emails
- Regression
   - exclude all projects or categories of issues that are not at zero yet
  - **any issues that pass this filter fail the build**

## Script descriptions, in default order of application

All scripts are in `verification/`, `opencanary.py run` applies them in this order:

- Gather: `parse_gcc.py` (gcc and clang), `parse_msvc.py`, `cppcheck.py`, `oc_cpp_issues.py` (raw text search for common C++ problems, respects `.opencanaryignore`)
- `tr_interest.py`, remove what the team is not interested in (`rules/interest.txt`, `--msvc` normalizes paths). Replaces `tr_interest_cs.py`, `tr_interest_vc.py` and `filter_thirdparty.py`.
- `tr_customize.py`, assign 'component' and 'team', make the path presentable and add the permalink (`rules/customize.txt`). Replaces `tr_customize_vc.py`.
- `apply_links.py`, sets the link of the rule and the solution suggestion shown as an icon after the rule (`rules/links.txt`), by default a search for `<source> <rule>`
- `apply_team_priorities.py`, assigns the priority field (`rules/priorities.txt`), **should be customized** based on your preferences
- `apply_low_hanging_fruit.py`, overrides priorities for types of issue that occur 20 times or less (`--threshold N`)
- `sortby.py`, filters duplicates and sorts first by priority and then by filename
- `create_report.py`, transforms the 'structured CSV' to an HTML report, see [Reports](#reports).
- `create_summary.py`, optional, the top 10 issues and the number of issues per rule, team, component and category as an e-mail friendly HTML page, see [Reports](#reports).
- `apply_environment.py`, replaces [[keyword]] placeholders using a `key=value` environment file (`CI_JOB_URL`, `CI_PROJECT_URL`, `CI_COMMIT_SHA`, ..., optional `WIKI_URL_PREFIX`, `PERMALINK_PREFIX` to link to a local checkout instead of `CI_PROJECT_URL/blob/CI_COMMIT_SHA`).
- `tr_regression.py`, example of the regression gate: any line that passes fails the build.

## Reports

Both scripts read the issues (the 'structured CSV', normally `issues.txt`) from stdin and write HTML to stdout,
`-h` or `--help` shows their parameters.

### create_report.py

```
create_report.py [/limit=N] < issues.txt > report.html
```

| Parameter    | Description |
|--------------|-------------|
| `/limit=N`   | Include only the first N issues; the report notes that it is limited. The input is normally sorted by priority, so these are the most important ones. |
| `-h, --help` | Show the usage. |

The report is a single self-contained file (no external scripts or stylesheets) that works offline and as an e-mail
attachment. It needs a current browser (Chrome, Edge, Firefox or Safari). `[[keywords]]` such as `[[branch-id]]` are
filled in by piping the report through `apply_environment.py env.txt`. In the report you can filter on text in any
column, per priority band (the summary cards) and per column value (the funnel button in each column header).

### create_summary.py

```
create_summary.py [--report-url URL] < issues.txt > summary.html
```

| Parameter          | Description |
|--------------------|-------------|
| `--report-url URL` | Add a link to the full report below the branch and committer. The URL can contain `[[keywords]]`, for example `"[[job-url]]/artifacts/file/report.html"` for the report in the artifacts of a GitLab job; the link is left out when a keyword has no value. |
| `-h, --help`       | Show the usage. |

The branch and committer, then the 10 most important issues (lowest priority number first), with a link to the file.
Then a table with a row per combination of rule, team, component and category, with the number of issues, and a total.
The rows of a rule are grouped: its priority, name (with its number of issues) and the description of its first issue
(cut at 100 characters) are shown once for the group. Rules are ordered by number of issues (fewest first) and by name
second, the rows within a rule by number of issues; an empty team, component or category is shown as `(none)`. The
branch, committer and file links are `[[keywords]]`, filled in by piping the summary through `apply_environment.py env.txt`
(a branch or committer without a value is left out). The HTML only
uses tables, attributes and inline styles, so Outlook shows it correctly as the body of an e-mail, for example `send_email.py summary.html report.html` sends it with the full report attached.
`opencanary.py run` writes it when the configuration has `summary = "summary.html"` in `[output]`, and adds the link
when it also has `report_url = "..."`.

## Other tools

- `cmake_completeness.py`, `cmake_to_dot.py`: find sources not referenced by the build (from compile_commands.json), visualize cmake dependencies
- `find_dead_code.py <arrays|functions|defines|variables|sources> [path]`: dead code candidates (words that occur once), and sources no CMakeLists.txt refers to. Replaces the `find_*.sh` scripts.
- `run_clang_format.py` (`CLANG_FORMAT` env var selects the binary), `send_email.py`, `summarize.py`, `list_warnings.py`, `returncode.py`, `pype.py`
- `filter.py` select lines from csv files, `prettydiff.py` diff two csv files with numeric tolerance (needs `pip install docopt`)
