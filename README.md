# OpenCanary
A set of scripts for aggregation, analysis and reporting of build and static analysis results.
Its purpose is to give you a failing CI build if new issues are introduced and to generate a team specific prioritized list of issues to work on.

The purpose of this repo is to provide a set of scripts that can be used to build your own build-canary.
A build-canary is a system that gives you early warning when new problems have been introduced. (so code quality _as you define it_ has regressed). Also a (nightly?) report can be generated to provide you and your team guidance to start improving you code base. The report is a prioritized list (_you define you own team priorities_) of issues to solve.

The process works in a couple of steps that are executed as post-build steps as part of the CI build.

## Quickstart

```
cd verification
python3 opencanary.py init        # writes opencanary.toml, point [[input]] at your build log(s)
python3 opencanary.py run         # writes issues.txt (prioritized work list) and report.html
python3 -m unittest               # run the tests
```
`opencanary.py run` needs python 3.11+ (or `pip install tomli`), the individual scripts work with python 3.8+.
Every stage can also be used on its own as a filter, `opencanary.py <command>` runs one stage (see `opencanary.py --help`),
for example `cat gcc.log | opencanary.py parse-gcc gcc | opencanary.py prioritize | opencanary.py sort`.

Team specific behavior lives in plain text rule files, first matching line wins (`=` equals, `~` contains, `?` regex):
- `rules/priorities.txt` priority (and category) per rule, **customize this**
- `rules/interest.txt` lines the team is not interested in (3rd party, known noise)
- `rules/customize.txt` component and team per path
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
* link - tool specific links where [n] refers back to a 0-indexed column (so 0=priority, 1=team etc.)

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
- `apply_team_priorities.py`, assigns the priority field (`rules/priorities.txt`), **should be customized** based on your preferences
- `apply_low_hanging_fruit.py`, overrides priorities for types of issue that occur 20 times or less (`--threshold N`)
- `sortby.py`, filters duplicates and sorts first by priority and then by filename
- `create_report.py`, transforms the 'structured CSV' to an HTML report.
- `apply_environment.py`, replaces [[keyword]] placeholders using a `key=value` environment file (`CI_JOB_URL`, `CI_PROJECT_URL`, `CI_COMMIT_SHA`, ..., optional `WIKI_URL_PREFIX`).
- `tr_regression.py`, example of the regression gate: any line that passes fails the build.

Other tools:
- `cmake_completeness.py`, `cmake_to_dot.py`: find sources not referenced by the build (from compile_commands.json), visualize cmake dependencies
- `find_dead_code.py <arrays|functions|defines|variables|sources> [path]`: dead code candidates (words that occur once), and sources no CMakeLists.txt refers to. Replaces the `find_*.sh` scripts.
- `run_clang_format.py` (`CLANG_FORMAT` env var selects the binary), `send_email.py`, `summarize.py`, `list_warnings.py`, `returncode.py`, `pype.py`
- `filter.py` select lines from csv files, `prettydiff.py` diff two csv files with numeric tolerance (needs `pip install docopt`)

## Converting a CI pipeline from `master` to `main`

`main` is a cleanup of `master`: the scripts that had team or project specific settings hardcoded now read them from
rule files or options, and a few scripts were merged. The issue format is unchanged (on `master` the README listed
category before rule, the code already used rule as column 5 and category as column 6), so existing `issues.txt` files
and scripts that read them keep working.

### 1. Rename the scripts in the pipeline

| on `master` | on `main` |
|---|---|
| `tr_interest_vc.py` | `tr_interest.py`, the default `rules/interest.txt` contains the same rules (`_autogen`, `\|use of old-style\|`) |
| `filter_thirdparty.py` | `tr_interest.py`, `rules/interest.txt` also drops `external/` |
| `filter_thirdparty.py /msvc` | `tr_interest.py --msvc` and add the lines of `examples/interest_msvc_system.txt` to your interest rules |
| `tr_interest_cs.py [/msvc]` | `tr_interest.py --rules examples/interest_copperspice.txt [--msvc]` |
| `tr_customize_vc.py [/msvc] [/depth=n]` | `tr_customize.py --rules examples/customize_toolkit.txt`, the old options are still accepted (`--msvc`, `--depth=n`, `--display-depth=n`, `--reference-depth=n` are the new spelling) |
| `tr_customize_cs.py` | `examples/tr_customize_copperspice.py` |
| `find_unique_*.sh`, `find_sources_unreferenced_by_cmake.sh` | `find_dead_code.py <arrays\|functions\|defines\|variables\|sources> [path]` |
| `prettydiff.py` (repository root) | `verification/prettydiff.py` |
| `sample_usage.bat` | `opencanary.py run` |

`tr_interest.py` takes one `--rules` file, so when the old pipeline ran more than one interest filter, put all `drop`
lines in one file. Without `--rules`, `tr_customize.py` uses `rules/customize.txt`, which has no rules and leaves the
component and team columns empty; the components and teams that were hardcoded in `tr_customize_vc.py` are in
`examples/customize_toolkit.txt`.

### 2. Move local edits out of the scripts

If you edited scripts on `master` to fit your project, those edits now go into rule files, options or the environment
file, so the scripts can be updated without merge conflicts:

- the if-chain in `apply_team_priorities.py`: `rules/priorities.txt`, or your own file with `--rules FILE`
- the threshold in `apply_low_hanging_fruit.py`: `--threshold N` (default 20, unchanged)
- `wiki_url_prefix` in `apply_environment.py`: `WIKI_URL_PREFIX=...` in the environment file
- the cppcheck path in `cppcheck.py`: the `CPPCHECK` environment variable (default: `cppcheck` on the PATH)
- the binary in `run_clang_format.py`: the `CLANG_FORMAT` environment variable

### 3. Expect these differences in the output

- MSVC priorities: on `master`, `parse_msvc.py` assigned priorities and `apply_team_priorities.py` then overwrote all
  of them with 8 (unassigned), except C4701. On `main`, `parse_msvc.py` assigns 8 and `apply_team_priorities.py` applies
  the MSVC table from `rules/priorities.txt`. A pipeline that runs `apply_team_priorities.py` now gets the MSVC
  priorities (for example C4100 70, C4244 40). A pipeline that skipped it gets 8 for everything, so add the stage.
  Either way the order of `issues.txt` changes, so update any baseline you compare against.
- In the MSVC report the documentation link is on the rule column instead of the source column.
- `cppcheck.py` leaves team and component empty instead of `tin` and `tincomp`, use `tr_customize.py` to fill them.
- `sortby.py` no longer crashes on Windows paths with a drive letter (`C:\...`).
- gcc and clang pipelines produce the same output as on `master`.

### 4. Optionally replace the pipe with `opencanary.py run`

A typical `master` pipeline:

```
cat build.log | parse_msvc.py msvc | tr_interest_vc.py | filter_thirdparty.py /msvc | tr_customize_vc.py /msvc \
  | apply_team_priorities.py | apply_low_hanging_fruit.py | sortby.py > issues.txt
cat issues.txt | create_report.py | apply_environment.py env.txt > report.html
```

becomes the same pipe with the new names (step 1), or an `opencanary.toml` (create one with `opencanary.py init`):

```
[[input]]
format = "msvc"
path = "build.log"

[rules]
interest = "ci/interest.txt"       # your drop rules, including those of examples/interest_msvc_system.txt
customize = "ci/customize.txt"     # your component:/team: rules
priorities = "ci/priorities.txt"   # optional, default verification/rules/priorities.txt

[customize]
msvc = true

[output]
issues = "issues.txt"
report = "report.html"
environment = "env.txt"
```

and the CI step is `python3 verification/opencanary.py run -c opencanary.toml`. This needs python 3.11 or newer (or
`pip install tomli`). The individual scripts work with python 3.8 or newer. `tr_regression.py`, `summarize.py` and
`send_email.py` are not part of `opencanary.py run`; call them on `issues.txt` as before.
