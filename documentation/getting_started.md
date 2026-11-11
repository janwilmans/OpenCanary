# Getting started with OpenCanary

OpenCanary turns the warnings in your build logs into a prioritized work list for your team, an HTML report to
browse it, an optional e-mail summary, and optionally a check that fails the CI build when new issues appear.

This page takes you from nothing to a working report in about six steps. Every script and option is described in full
in [details.md](details.md).

## What you get

| Output | What it is |
|--------|------------|
| `issues.txt` | The work list: one issue per line, most important first. Plain text, easy to diff and to use in scripts. |
| `report.html` | One self-contained HTML file to browse the issues: filter, sort and click through to the source. Works offline and as an e-mail attachment. |
| `summary.html` | Optional: the 10 most important issues and a short table per rule, team, component and category, made to be the body of an e-mail (also in Outlook). |
| exit code | Optional: `tr_regression.py` fails the build when issues appear that you have not accepted yet. |

## Requirements

- Python 3.11 or newer for `opencanary.py run` (or Python 3.8+ with `pip install tomli`). The individual scripts work
  with Python 3.8+.
- On Windows: if `python3 --version` shows an older Python than you have installed, use the `py` launcher instead,
  `py opencanary.py run`, it picks the newest installed version.
- A current browser (Chrome, Edge, Firefox or Safari) to open the report.

Some scripts use other tools; without them only that part is skipped or unavailable:

| Tool | Needed by | Without it |
|------|-----------|------------|
| `rg` ([ripgrep](https://github.com/BurntSushi/ripgrep)) | `oc_cpp_issues.py`, the spelling check (`misspelled-word`) | the spelling check is skipped, with a message on stderr |
| `tomli` (python package) | `opencanary.py run` on Python older than 3.11 | `opencanary.py run` stops; the individual scripts still work |
| `cppcheck` | `cppcheck.py` | no cppcheck issues |
| `clang-format` | `run_clang_format.py` (`CLANG_FORMAT` selects the binary, default `clang-format-11`) | the script cannot check formatting |
| `git` | `send_email.py`, to find the recent authors | `send_email.py` fails |
| `docopt` (python package) | `prettydiff.py` | the script cannot run |

On Debian or Ubuntu, install all of them with:

```
sudo apt install python3 ripgrep python3-tomli cppcheck clang-format git python3-docopt
```

On other systems use the package manager (for example `winget`, `choco` or `brew`) or `pip install tomli docopt` for
the python packages.

The examples below use `python3`; all scripts are in the `verification/` directory of this repository.

## Step 1: capture a build log

OpenCanary reads the warnings from the compiler output, so first save that output to a file. Do a full rebuild:
a compiler only reports the warnings of the files it actually compiles.

```sh
# gcc / clang with make or ninja
cmake --build build --clean-first 2>&1 | tee build/gcc.log

# MSVC (from a developer command prompt)
cmake --build build --clean-first > build\msvc.log 2>&1
```

Supported inputs:

| Format | Produced by | Notes |
|--------|-------------|-------|
| `gcc` | gcc and clang (including clang-tidy style `[check-name]` warnings) | lines with `: warning:` |
| `msvc` | cl.exe, MASM, `Command line warning Dxxxx` | lines with `: warning ` |
| `cpp-issues` | OpenCanary's own text search for common C++ problems | scans a source directory instead of a log |

`cppcheck.py` is available as a separate stage, see [details.md](details.md#cppcheckpy).

## Step 2: create a configuration

```sh
cd /path/to/your/project
python3 /path/to/OpenCanary/verification/opencanary.py init
```

This writes `opencanary.toml` in the current directory. Point the `[[input]]` table at your log; add one `[[input]]`
table per log:

```toml
[[input]]
format = "gcc"          # gcc | msvc | cpp-issues
source = "gcc"          # free text, shown in the 'source' column
path = "build/gcc.log"  # relative to this file
```

Everything else is optional and can stay as it is for now.

## Step 3: run it

```sh
python3 /path/to/OpenCanary/verification/opencanary.py run
```

```
opencanary: 1270 issues written to /path/to/your/project/issues.txt
opencanary: report written to /path/to/your/project/report.html
```

Open `report.html` in a browser. You will see:

- **Summary cards** per priority band (*Fix now* priority 10 and lower, *Likely bug* 11–50, *Wrong approach*
  51–75, *Style* 76 and higher). Click one or more to show only those issues.
- **A search box** that matches text in any column, for example `hides local` or `C4701 core`. Press `/` to jump to it.
- **A funnel button** in each column header: a checklist of that column's values with their counts, untick values to
  hide them.
- **Reset** clears all filters. Click a column name to sort; click a row to see its full text.

Every issue starts with priority 99 ("unassigned") unless a rule in `rules/priorities.txt` matches it, and rules
with only a few issues are moved to priority 7 ("low hanging fruit", the description gets a `[LOW]` prefix) so they can
be cleared first. Unassigned issues land in *Style* and low hanging fruit in *Fix now* until you tune the priorities
in step 5.

## Step 4: make the links work

File names in the report link to your source code, and the report header shows the branch, the author and a link to
the CI job. These values come from an *environment file*: a text file with `KEY=value` lines. Add it to the
configuration:

```toml
[output]
environment = "env.txt"
```

**On your own machine**, link to a local checkout:

```text
PERMALINK_PREFIX=file:///C:/project/your-project
```

**On CI** (GitLab variable names), link to the exact commit in your repository:

```text
CI_PROJECT_URL=https://gitlab.example.com/group/project
CI_COMMIT_SHA=0123456789abcdef
CI_JOB_URL=https://gitlab.example.com/group/project/-/jobs/42
CI_COMMIT_TITLE=Fix the frobnicator
CI_COMMIT_REF_NAME=main
GITLAB_USER_NAME=Jane Doe
```

The file links are built as `<prefix>/<path in the log>#L<line>`. If the paths in your log are absolute, remove the
leading directories that are not part of the repository with `reference_depth`:

```toml
[customize]
reference_depth = 2    # C:\builds\project\src\x.cc -> drive removed -> builds/project/src/x.cc -> src/x.cc
display_depth = 2      # the same, for the path shown in the report
msvc = true            # show the paths with \ in the report
```

Leave out keys you do not have; the header items that have no value are hidden.

## Step 5: make it yours

Team specific behavior lives in three plain text rule files in `verification/rules/`. Copy them next to your
configuration and point to the copies, so updating OpenCanary does not overwrite them:

```toml
[rules]
interest = "rules/interest.txt"
customize = "rules/customize.txt"
priorities = "rules/priorities.txt"
low_hanging_threshold = 20
```

Each line is `<value> <matcher>...`, the first line whose matchers all match wins. A matcher is `=text` (equals),
`~text` (contains) or `?regex`. Quote matchers with spaces, `#` starts a comment.

1. **Remove noise** with `interest.txt`, matched against the whole issue line:
   ```text
   keep ~third_party/our_fork/    # exception: we maintain this one
   drop ~third_party/
   drop ~_autogen
   drop "~|C4996|"                # the rule column of an MSVC warning
   ```
2. **Assign components and teams** with `customize.txt`, matched against the file path (with `/`):
   ```text
   component:network ~src/net/
   component:ui      ~src/gui/
   team:platform     ~src/net/
   team:apps         ~src/gui/
   ```
3. **Set priorities** with `priorities.txt`, matched against the rule (the warning name, such as `C4701` or
   `sign-compare`). Lower is more important:
   ```text
   5   =C4701                  # potentially uninitialized variable
   45  ~sign-compare
   90  ~unused-parameter
   category:ub =array-bounds   # also changes the category column
   ```

Run `opencanary.py run` again after each change and check the report. A good first goal is a *Fix now* band that holds
only issues the team agrees should be fixed now.

## Step 6: run it on CI

Run OpenCanary after the build, keep the outputs as artifacts, and optionally mail the summary. A GitLab example:

```yaml
opencanary:
  stage: report
  needs: [build]
  script:
    - |
      for v in CI_PROJECT_URL CI_COMMIT_SHA CI_COMMIT_REF_NAME CI_JOB_URL CI_COMMIT_TITLE GITLAB_USER_NAME; do
        echo "$v=${!v}"
      done > env.txt
    - python3 OpenCanary/verification/opencanary.py run -c opencanary.toml
  artifacts:
    when: always
    paths: [issues.txt, report.html, summary.html]
```

Write only the variables you need to `env.txt`: the CI environment also contains tokens.

**Metrics**: add `metrics = "metrics.txt"` to `[output]` for the number of issues per rule, team and priority in the
[OpenMetrics](https://openmetrics.io) format, to follow them over time in a monitoring system such as Prometheus.

**E-mail summary**: add `summary = "summary.html"` to `[output]`, then send it with the report attached. `send_email.py`
is a starting point: set the mail server at the top of the script and the recipients in `send_report()` first:

```sh
python3 OpenCanary/verification/send_email.py summary.html report.html -s "Software Quality Report"
```

**Fail the build on new issues**: copy `verification/tr_regression.py` and list the rules you still accept (the issues
that exist today). Any issue that passes the filter fails the job:

```sh
python3 OpenCanary/verification/tr_regression.py < issues.txt
```

Remove a rule from the list once its issues are fixed, and it can never come back unnoticed.

## Try the example first

The repository has a complete example: an MSVC `/W4` build of CopperSpice.

```sh
cd examples
unzip log.w4.all.zip                 # gives log.w4.all.txt
python3 ../verification/opencanary.py run -c opencanary.toml
```

It shows MSVC paths, rule sets for interest and components (`verification/examples/`), and an environment file
that links to a local checkout.

## Running single stages

Every stage is also a filter that reads issues from stdin and writes to stdout, so you can inspect or replace any step:

```sh
python3 opencanary.py parse-gcc gcc < build.log | python3 opencanary.py prioritize | python3 opencanary.py sort
python3 opencanary.py report < issues.txt > report.html
python3 summarize.py < issues.txt          # issues per rule as text
```

See [details.md](details.md) for every script, its arguments and exactly what it does to each line.
