# Converting a CI pipeline from `classic` to `main`

The `classic` branch is the original version of the scripts, until November 2026, but is no longer developed.

`main` is a cleanup of `classic`: the scripts that had team or project specific settings hardcoded now read them from
rule files or options, and a few scripts were merged. The issue format is unchanged (on `classic` the README listed
category before rule, the code already used rule as column 5 and category as column 6), so existing `issues.txt` files
and scripts that read them keep working.

## 1. Rename the scripts in the pipeline

| on `classic` | on `main` |
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

## 2. Move local edits out of the scripts

If you edited scripts on `classic` to fit your project, those edits now go into rule files, options or the environment
file, so the scripts can be updated without merge conflicts:

- the if-chain in `apply_team_priorities.py`: `rules/priorities.txt`, or your own file with `--rules FILE`
- the threshold in `apply_low_hanging_fruit.py`: `--threshold N` (default 20, unchanged)
- `wiki_url_prefix` in `apply_environment.py`: `WIKI_URL=...` (the url of the wiki button) in the environment file;
  a wiki page per rule is a `solution:` line in `rules/links.txt`
- the cppcheck path in `cppcheck.py`: the `CPPCHECK` environment variable (default: `cppcheck` on the PATH)
- the binary in `run_clang_format.py`: the `CLANG_FORMAT` environment variable

## 3. Expect these differences in the output

- MSVC priorities: on `classic`, `parse_msvc.py` assigned priorities and `apply_team_priorities.py` then overwrote all
  of them with 8 (unassigned), except C4701. On `main`, `parse_msvc.py` assigns 8 and `apply_team_priorities.py` applies
  the MSVC table from `rules/priorities.txt`. A pipeline that runs `apply_team_priorities.py` now gets the MSVC
  priorities (for example C4100 70, C4244 40). A pipeline that skipped it gets 8 for everything, so add the stage.
  Either way the order of `issues.txt` changes, so update any baseline you compare against.
- In the MSVC report the documentation link is on the rule column instead of the source column.
- `cppcheck.py` leaves team and component empty instead of `tin` and `tincomp`, use `tr_customize.py` to fill them.
- `sortby.py` no longer crashes on Windows paths with a drive letter (`C:\...`).
- gcc and clang pipelines produce the same output as on `classic`.

## 4. Optionally replace the pipe with `opencanary.py run`

A typical `classic` pipeline:

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
