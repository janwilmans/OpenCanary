# OpenCanary in detail

This page describes every script in `verification/`: its arguments and exactly what it does to its input. For a
first setup, read [getting_started.md](getting_started.md) first.

- [The issue format](#the-issue-format)
- [Rule files](#rule-files)
- [opencanary.py, the entry point](#opencanarypy)
- Gather: [parse_gcc.py](#parse_gccpy), [parse_msvc.py](#parse_msvcpy), [oc_cpp_issues.py](#oc_cpp_issuespy), [cppcheck.py](#cppcheckpy)
- Transform: [tr_interest.py](#tr_interestpy), [tr_customize.py](#tr_customizepy),
  [apply_team_priorities.py](#apply_team_prioritiespy), [apply_low_hanging_fruit.py](#apply_low_hanging_fruitpy),
  [sortby.py](#sortbypy)
- Output: [create_report.py](#create_reportpy), [create_summary.py](#create_summarypy),
  [apply_environment.py](#apply_environmentpy), [tr_regression.py](#tr_regressionpy)
- [Other tools](#other-tools)
- [Known limitations](#known-limitations)

## Conventions shared by all scripts

- Stages read from stdin and write to stdout; messages go to stderr. A stage can be run directly
  (`python3 sortby.py < in.txt`) or through `opencanary.py <command>`.
- On an unexpected error a script prints the Python traceback and its usage to stderr and exits with code 1.
  A broken pipe (for example piping into `head`) exits quietly.
- Scripts that use `argparse` (`tr_interest.py`, `tr_customize.py`, `apply_team_priorities.py`,
  `apply_low_hanging_fruit.py`, `filter.py`) also accept `-h`/`--help`; `create_report.py` and `create_summary.py`
  accept `-h`/`--help` as well.

## The issue format

Every stage between the parsers and the report passes *issues*: one issue per line, nine fields separated by `|`.

```
priority|team|component|fileref|source|rule|category|description|links
8|||src/w.cc:9:11|gcc|sign-compare|warning|comparison of integer expressions of different signedness|[3]{[[permalink-prefix]]/src/w.cc#L9}[5]{https://duckduckgo.com/?q=!ducky+gcc+sign-compare}
```

| # | Field | Meaning | Written by | Changed by |
|---|-------|---------|------------|------------|
| 0 | priority | Integer, lower is more important. | parsers | `apply_team_priorities.py`, `apply_low_hanging_fruit.py` |
| 1 | team | Team responsible for the file. | parsers (empty) | `tr_customize.py` |
| 2 | component | Component the file belongs to. | parsers (empty, `compiler` for command line warnings) | `tr_customize.py` |
| 3 | fileref | `file[:line[:column]]` | parsers | `tr_customize.py` (path clean-up) |
| 4 | source | Tool or build that reported it, free text. | parsers | |
| 5 | rule | The tool's name for the check, e.g. `C4701`, `sign-compare`, `AP#13`. | parsers | |
| 6 | category | Broad group, e.g. `warning`, `redflag`, `ub`. | parsers | `apply_team_priorities.py` |
| 7 | description | The message, HTML-escaped (`&`, `<`, `>`, `"`, `'`). | parsers | `apply_low_hanging_fruit.py` (`[LOW] ` prefix) |
| 8 | links | `[n]{url}` repeated; `n` is the field the link belongs to. `[solution]{url}` is a page with a solution suggestion for the rule, the report shows it as a small icon after the rule. | parsers | `tr_customize.py` (`[3]`) |

Details:

- A `|` inside a field is written as `[[pipe]]` by the scripts that write issues with the shared helper
  (the parsers, `apply_team_priorities.py`, `apply_low_hanging_fruit.py`).
- When a stage reads a line it strips surrounding whitespace, splits on `|` and strips a leading `b` plus surrounding
  quotes from each field. A line that does not have nine fields is reported on stderr
  (`assertion failed: broken structured CSV`) but is still processed.
- In the report the `[3]` link makes the file clickable and `[5]` makes the rule clickable; any field can carry a link.
- Special priorities: `7` low hanging fruit, `8` unassigned (no priority rule matched), `11` not set yet
  (`oc_cpp_issues.py`), `10` and `1` (`cppcheck.py`).
- Placeholders in double brackets are filled in later by `apply_environment.py`, see
  [apply_environment.py](#apply_environmentpy) for the list.

## Rule files

`tr_interest.py`, `tr_customize.py` and `apply_team_priorities.py` take their team specific behavior from rule files.
The defaults are in `verification/rules/`, larger examples in `verification/examples/`.

```text
# comment
<value> <matcher> [<matcher>...]   # comment
```

- Everything after ` #` (a space followed by `#`) is a comment, as is a line that starts with `#`. Empty lines are
  ignored.
- The line is split like a shell command line (Python `shlex`): use quotes for a matcher that contains spaces.
  A backslash outside quotes is an escape character, so write Windows paths in single quotes (`'~src\net\'`), or match
  on `/` and let `--msvc` normalize the paths first.
- The first word is the *value*, the rest are *matchers*; each matcher starts with:

  | Matcher | Matches when the text |
  |---------|-----------------------|
  | `=text` | equals `text` exactly |
  | `~text` | contains `text` |
  | `?regex` | contains a match of the Python regular expression `regex` (case-sensitive, prefix `(?i)` to ignore case) |

- A rule matches when **all** its matchers match. Rules are tried from top to bottom and the **first** matching rule
  wins.
- A value of the form `key:name` (for example `component:network`) belongs to that key; one file can hold rules for
  several keys. Rules without a `:` in their value are the file's main rules.
- A line that is not `<value>` followed by at least one valid matcher stops the script with
  `rule line N is invalid: ...`.

| File | Used by | Text matched | Values |
|------|---------|--------------|--------|
| `rules/interest.txt` | `tr_interest.py` | the whole issue line, including its line ending | `drop` removes the line; any other value (for example `keep`) keeps it, so a `keep` rule above a `drop` rule is an exception |
| `rules/customize.txt` | `tr_customize.py` | the fileref with `/` separators | `component:<name>`, `team:<name>` |
| `rules/priorities.txt` | `apply_team_priorities.py` | the rule field | `<priority>` (an integer), `category:<name>` |

Because the interest text includes the line ending, use `~` or `?` there; `=` never matches a whole line.

## opencanary.py

```
opencanary.py init                       write a starter opencanary.toml in the current directory
opencanary.py run [-c opencanary.toml]   run the whole pipeline from the configuration
opencanary.py <command> [args...]        run one stage, stdin/stdout like the script itself
opencanary.py -h | --help                show the usage
```

| Command | Script | | Command | Script |
|---------|--------|-|---------|--------|
| `parse-gcc` | `parse_gcc.py` | | `low-hanging` | `apply_low_hanging_fruit.py` |
| `parse-msvc` | `parse_msvc.py` | | `sort` | `sortby.py` |
| `cpp-issues` | `oc_cpp_issues.py` | | `report` | `create_report.py` |
| `cppcheck` | `cppcheck.py` | | `summary` | `create_summary.py` |
| `interest` | `tr_interest.py` | | `environment` | `apply_environment.py` |
| `customize` | `tr_customize.py` | | `regression` | `tr_regression.py` |
| `prioritize` | `apply_team_priorities.py` | | | |

`opencanary.py <command>` passes the remaining arguments to the script and returns its exit code. When a command that
reads stdin is started from a terminal without redirected input it does not wait, it prints how to redirect and exits
with code 1. `cpp-issues` and `cppcheck` do not read stdin.

`init` refuses to overwrite an existing `opencanary.toml`.

### Configuration

All relative paths are relative to the directory of the configuration file.

| Table | Key | Default | Meaning |
|-------|-----|---------|---------|
| `[[input]]` (one or more) | `format` | required | `gcc`, `msvc` or `cpp-issues`; anything else stops the run |
| | `path` | required | the log file (`gcc`, `msvc`) or the directory to scan (`cpp-issues`) |
| | `source` | the format | value for the source field (passed to the parser) |
| `[rules]` | `interest` | `verification/rules/interest.txt` | rules for `tr_interest.py` |
| | `customize` | `verification/rules/customize.txt` | rules for `tr_customize.py` |
| | `priorities` | `verification/rules/priorities.txt` | rules for `apply_team_priorities.py` |
| | `low_hanging_threshold` | `20` | `--threshold` of `apply_low_hanging_fruit.py` |
| `[customize]` | `msvc` | `false` | `--msvc` for both `tr_interest.py` and `tr_customize.py` |
| | `display_depth` | `0` | `--display-depth` of `tr_customize.py` |
| | `reference_depth` | `0` | `--reference-depth` of `tr_customize.py` |
| `[output]` | `issues` | `issues.txt` | the work list |
| | `report` | `report.html` | the HTML report |
| | `environment` | none | environment file; when set the report is passed through `apply_environment.py` |
| | `summary` | none | when set, the e-mail summary is written to this file |

A configuration without `[[input]]` stops with `no [[input]] defined in the configuration`. Reading the configuration
needs Python 3.11+ or the `tomli` package.

### What `run` does

1. For every `[[input]]`, in order, collect the issues:
   `parse_gcc.py <source> < path`, `parse_msvc.py <source> < path` or `oc_cpp_issues.py <path>`.
   The results are concatenated.
2. `tr_interest.py [--rules <interest>] [--msvc]`
3. `tr_customize.py [--rules <customize>] [--display-depth=N] [--reference-depth=N] [--msvc]`
4. `apply_team_priorities.py [--rules <priorities>]`
5. `apply_low_hanging_fruit.py [--threshold N]`
6. `sortby.py`, the result is written to the `issues` file.
7. `create_report.py`, then `apply_environment.py <environment>` when configured; written to the `report` file.
8. When `summary` is configured: `create_summary.py` on the issues, then `apply_environment.py <environment>` when
   configured; written to the `summary` file.

Each step prints its stderr messages. If a step exits with a non-zero code, `run` stops with
`opencanary: stage '<script>' failed with exit code N`. `run` does not run `tr_regression.py`; run it as a separate
CI step.

---

## Gather

### parse_gcc.py

```
parse_gcc.py <sourcename> < build.log
```

| Argument | Description |
|----------|-------------|
| `<sourcename>` | Required. Written to the source field, for example `gcc`, `clang` or a build type. Further arguments are ignored. |

Reads a gcc or clang build log (clang and clang-tidy use the same format) and writes one issue per warning.

- Only lines that contain `: warning` are used; errors and notes are ignored. Lines containing
  `this will be reported only once per input file` are skipped.
- The line is split at `: warning:`: the part before it is the fileref (`file:line:column`), the part after it the
  message.
- **rule**: the text inside the last `[...]` of the message, without a leading `-W`: `[-Wsign-compare]` gives
  `sign-compare`, `[misc-const-correctness]` gives `misc-const-correctness`, `[-Wformat=]` gives `format=`.
  Without brackets the rule is `cmdline` when the message starts with `command line`, `unused` when the line contains
  `not used`, `uninitialized` when it contains `uninitialized`, and `rule-missing` otherwise.
- **description**: the message up to the last `[`, HTML-escaped.
- **priority** `8`, **team** empty, **component** `compiler` for `cmdline` warnings and empty otherwise,
  **category** `warning`.
- **links**: `[3]{[[permalink-prefix]]/<file>#L<line>}` and, unless the rule is `rule-missing`, `unused`,
  `uninitialized` or `cmdline`, `[5]{https://duckduckgo.com/?q=!ducky+<source>+<rule>}`.

```
in:   w.cc:9:11: warning: comparison of integer expressions of different signedness: 'int' and 'unsigned int' [-Wsign-compare]
out:  8|||w.cc:9:11|gcc|sign-compare|warning|comparison of integer expressions of different signedness: &#x27;int&#x27; and &#x27;unsigned int&#x27; |[3]{[[permalink-prefix]]/w.cc#L9}[5]{https://duckduckgo.com/?q=!ducky+gcc+sign-compare}
```

### parse_msvc.py

```
parse_msvc.py <sourcename> < build.log
```

| Argument | Description |
|----------|-------------|
| `<sourcename>` | Required. Written to the source field. Further arguments are ignored. |

Reads an MSVC (cl.exe, MASM, link) build log and writes one issue per warning.

- Lines containing `: message`, and the known false message `class template optional is only available with C++17 or
  later.`, are skipped. Lines containing `: error` are printed to stderr as `-- error found:` and not reported.
- **Warnings** (`<file>(<line>[,<column>]): warning <rule>: <description>`): the line is split at the first
  `: warning `. The rule is the text up to the next `:`, the description the rest. The fileref becomes
  `file:line[:column]` (or just `file` without a location, as in `MASM : warning A4018: ...`).
  On a CI server (the `CI_SERVER` environment variable is set) an existing file name is replaced by its real path, with
  its real capitalization and `/` separators; a file that does not exist is reported on stderr as
  `--- Could not resolve:` (except `.obj` and `.lib` files).
  **category** `warning`, **component** empty.
- **Command line warnings** (`cl : Command line warning D9002 : ignoring unknown option '/foo'`): fileref is the text
  up to and including `Command line warning`, the rule (`D9002`) and description follow, **component** `compiler`,
  **category** `cmdline`.
- **priority** `8`, **team** empty, description HTML-escaped.
- **links**: only `[5]{https://duckduckgo.com/?q=!ducky+<source>+<rule>}`; the file link is added by `tr_customize.py`.

```
in:   C:\project\lib\toolkit\slot.h(75): warning C4251: 'Slot::m_name': class 'std::string' needs to have dll-interface
out:  8|||C:\project\lib\toolkit\slot.h:75|msvc|C4251|warning|&#x27;Slot::m_name&#x27;: class &#x27;std::string&#x27; needs to have dll-interface|[5]{https://duckduckgo.com/?q=!ducky+msvc+C4251}
```

### oc_cpp_issues.py

```
oc_cpp_issues.py <path>
```

| Argument | Description |
|----------|-------------|
| `<path>` | Required. Directory that is searched recursively. Exactly one argument. |

Searches C++ sources and Visual Studio projects for common problems with plain text checks (no compiler involved).
Files and directories listed in a `.opencanaryignore` file (`.gitignore` syntax) are skipped.

Every line of every header (`.h`, `.hpp`) and source file (`.cpp`, `.cc`) is checked:

The descriptions below are shortened; the reported text starts with `Anti-pattern: ` or `prevent UB: `.

| Rule | Reported when the line | Category | Description, in short |
|------|------------------------|----------|-----------------------|
| `MO#1` | contains `/make_unique` | modernize | For C++14 and later use #include &lt;memory&gt; (no prefix) |
| `MO#2` | contains `make_unique` but not `std::make_unique` (and not `MO#1`) | modernize | For C++14 and later use std::make_unique (no prefix) |
| `AP#3` | contains `reinterpret_cast<` | casting | do not reinterpret_cast |
| `AP#4` | matches `[^a-z]volatile[^a-z].*;` | redflag | do not use volatile |
| `MO#5` | matches `\sNULL\s` | modernize | do not use NULL, use 0 or nullptr instead |
| `AP#6` | matches the Dutch words `deze`, `niet`, `naam`, `als`, `...ectie`, `voet` (ignoring case) | readability | do not use non-english words |
| `AP#7` | matches `#if\s+<digit>` | readability | do not keep historical code in ifdefs |
| `AP#8` | matches `(<word> *)`, a C-style pointer cast | modernize | dont use c-style casts |
| `AP#9` | matches `#define _<name>` | ub | names starting with an underscore are reserved |
| `AP#10` | defines a `min` or `max` macro (`#define.*(min\|max).*\(.*:`, ignoring case) | modernize | use std::min and std::max |
| `AP#11` | matches `extern` followed by something other than `"` | redflag | do not use extern |
| `AP#13` | matches `delete <name>;` | redflag | do not use delete |
| `AP#14` | contains `extern volatile` | redflag | extern volatile ?! |
| `AP#15` | matches `(char *)"`, casting away the constness of a string literal | ub | do not cast away constness of string literals |
| `AP#16` | contains `const_cast<` | readability | do not cast away constness |
| `AP#17` | starts with `using namespace` (headers only) | redflag | Using namespace found in header file (no prefix) |
| `AP#18` | matches `(while\|if\|switch) (... = ...)`, an assignment in a condition | assign_in_condition | do not assign inside conditions |
| `AP#19` | contains one of the misspelled words in `wrong_word_list` (such as `recieve`, `seperate`, `wich`) as a whole word; needs ripgrep, see below | spelling | Misspelled word '<word>' found |

Every Visual Studio project (a file whose name ends with `proj`) is checked per `ItemDefinitionGroup`:

| Rule | Reported when | Category |
|------|---------------|----------|
| `UD#4` | `ClCompile/TreatWarningAsError` is missing or not `true` | redflag |
| `UD#5` | `ClCompile/WarningLevel` is missing or does not end with `4` | redflag |
| `PARSE` | the project, header or source could not be read (for example not UTF-8) | parse |

Fields: **priority** `11` (to be set by `apply_team_priorities.py`, the default `rules/priorities.txt` lists all these
rules), **team** and **component** empty, **fileref** `<absolute path>:<line>` (`:0` for project checks),
**source** `opencanary`, **links** `[3]{[[permalink-prefix]]/<absolute path with />#L<line>}`. Because the path is
absolute, use `reference_depth` (`tr_customize.py --reference-depth`) to make the links match the repository.

The spelling check (`AP#19`) runs `rg` (ripgrep) once in `<path>` and reports only matches in the headers and sources
that the other checks read, so `.opencanaryignore` applies to it too. Without ripgrep on the `PATH` it is skipped with a
message on stderr. The default `rules/priorities.txt` gives it priority 90.

### cppcheck.py

```
cppcheck.py <env.txt> <path> <basepath>
cppcheck.py <env.txt> cdb <basepath>
```

| Argument | Description |
|----------|-------------|
| `<env.txt>` | Environment file (`KEY=value` lines), read but currently not used for the output. |
| `<path>` | Directory that cppcheck analyses recursively. |
| `cdb` | Instead of a directory: use the compile database `build_cppcheck/compile_commands.json` in the current directory, and `./suppressions.xml` when it exists. |
| `<basepath>` | Its length is removed from the start of every reported file name, so paths are relative to it. |

Runs cppcheck (the `CPPCHECK` environment variable, else `cppcheck` on the `PATH`, else
`C:\Program Files\Cppcheck\cppcheck.exe`) with `-q -D TEST -D TEST_F --enable=all
--template={file}:{line}:{severity}:{message}` and converts every reported line:

- cppcheck's stdout is passed to stderr; its stderr lines are parsed as `file:line:severity:message`. Lines with fewer
  than four fields are printed to stderr as `err:`; messages `Redundant code` and `Consider using std` are skipped.
- **priority** `10`, or `1` for line 0; **team** and **component** empty; **fileref** `file:line`;
  **source** `cppcheck`; **rule** the literal text `rule`; **category** the cppcheck severity; **description** the
  message.
- **links** `[3]` to `[[permalink-prefix]]` plus the file name from its second `/` on, and `[5]` to a search for
  the rule.
- When cppcheck exits with a non-zero code an extra issue is reported: rule `exec`, category `ci`, description
  `cppcheck exited with exitcode N`.

---

## Transform

### tr_interest.py

```
tr_interest.py [--rules FILE] [--msvc] < issues
```

| Option | Default | Description |
|--------|---------|-------------|
| `--rules FILE` | `rules/interest.txt` | interest rule file |
| `--msvc` (also `/msvc`, `-msvc`) | off | replace every `\` with `/` in the line before matching; the output keeps the `/` |
| `-h`, `--help` | | show the usage |

For every input line: with `--msvc` replace `\` by `/`; find the first rule (without a `key:` value) whose matchers all
match the whole line; when its value is `drop` the line is removed, otherwise it is written unchanged. Lines are not
parsed, so this also works on raw log lines.

The default rules drop lines containing `_autogen`, `|use of old-style|` and `external/`.

### tr_customize.py

```
tr_customize.py [--rules FILE] [--msvc] [--depth N] [--display-depth N] [--reference-depth N] < issues
```

| Option | Default | Description |
|--------|---------|-------------|
| `--rules FILE` | `rules/customize.txt` | `component:` and `team:` rules |
| `--msvc` | off | show the paths with `\` in the output |
| `--display-depth N` | `0` | remove the first N path elements from the path that is shown |
| `--reference-depth N` | `0` | remove the first N path elements from the path used in the file link |
| `--depth N` | | set both depths to N |
| `-h`, `--help` | | show the usage |

The old spellings `/msvc`, `-display_depth=2`, `-reference_depth=2` and `-depth=2` are accepted too.

For every issue, in this order:

1. **component**: the first `component:<name>` rule that matches the fileref (with `/` separators) sets it to
   `<name>`; when none matches the component is left as it was (for example `compiler`).
2. **team**: the first `team:<name>` rule that matches sets it; when none matches the team is left as it was.
3. **fileref clean-up**: `\` becomes `/`. A path into a Visual Studio installation (matching
   `.*Program Files/Microsoft.*/<digits>/<word>/`) is cut after that part and gets no file link. Otherwise a drive
   letter (`C:/`) is removed. A leading `/` is removed.
4. **file link** (not for Visual Studio paths): the path without `:line:column`, minus the first `reference_depth`
   elements, becomes `[3]{[[permalink-prefix]]/<path>#L<line>}` (without `#L` when there is no line number). It
   replaces an existing `[3]` link; other links are kept.
5. **display**: the first `display_depth` path elements are removed from the fileref, and with `--msvc` `/` becomes
   `\`.

```
in:   8|||C:\project\lib\toolkit\slot.h:75|msvc|C4251|warning|...|[5]{...}
      tr_customize.py --msvc --display-depth 1
out:  8|||lib\toolkit\slot.h:75|msvc|C4251|warning|...|[5]{...}[3]{[[permalink-prefix]]/project/lib/toolkit/slot.h#L75}
```

`verification/examples/tr_customize_copperspice.py` is an example of a project specific customizer.

### apply_team_priorities.py

```
apply_team_priorities.py [--rules FILE] < issues
```

| Option | Default | Description |
|--------|---------|-------------|
| `--rules FILE` | `rules/priorities.txt` | priority and `category:` rules |
| `-h`, `--help` | | show the usage |

For every issue, matched against the **rule** field:

- **priority**: the value of the first matching rule without a `key:`; `8` when no rule matches. The priority set by a
  parser is always replaced.
- **category**: the first matching `category:<name>` rule sets it to `<name>`; otherwise it is left as it was.

Guideline used in the default file: below 10 solve immediately, 11–50 likely a bug, 51–75 the wrong approach, 76–99
style. The report's priority bands follow these numbers.

### apply_low_hanging_fruit.py

```
apply_low_hanging_fruit.py [--threshold N] < issues
```

| Option | Default | Description |
|--------|---------|-------------|
| `--threshold N` | `20` | rules with at most N issues are low hanging fruit |
| `-h`, `--help` | | show the usage |

Reads all issues and counts them per rule (over the whole input). For every issue of a rule with at most N issues the
priority becomes `7` and the description gets the prefix `[LOW] `. This also applies to rules that had a more
important priority (for example `5` becomes `7`). Order is kept.

### sortby.py

```
sortby.py < issues
```

No arguments; any argument prints the usage and exits with code 1.

1. Removes duplicates: lines that are identical after removing surrounding whitespace are kept once (the same warning
   from several builds or from a header included in many files).
2. Sorts by priority (as an integer), then file name, then line number, then column number (both as integers,
   `0` when missing). A Windows drive letter in the file name is handled.

The priority must be an integer, otherwise the script stops with a traceback.

---

## Output

### create_report.py

```
create_report.py [/limit=N] < issues.txt > report.html
```

| Option | Description |
|--------|-------------|
| `/limit=N` | Include only the first N issues (the most important ones, as the input is sorted); the report notes that it is limited. |
| `-h`, `--help` | Show the usage. |

Any other argument prints the usage and exits with code 1.

Writes one self-contained HTML file: no external scripts, stylesheets, fonts or images, so it works offline and as an
e-mail attachment. It is well-formed XML.

- Every issue becomes a record `[band, priority, team, component, file, source, rule, category, description,
  {field: link}]`. HTML escapes in the fields are decoded; the page shows them as plain text. A malformed links field
  stops the script with `REPORT ERROR`.
- **Priority bands**: *Fix now* (priority ≤ 10), *Likely bug* (11–50), *Wrong approach* (51–75), *Style* (76 and
  higher, and non-numeric priorities). The summary cards show the count per band.
- The records are stored as gzip compressed, base64 encoded JSON blocks of 4000 issues; the browser unpacks them with
  `DecompressionStream` and renders only the rows in view, so reports with tens of thousands of issues stay fast.
  This needs a current Chrome, Edge, Firefox or Safari.
- `[[keywords]]` in the page (header and links) are left for `apply_environment.py`. Because that script cannot see
  inside the compressed data, the page carries the keyword values in a hidden element and fills them into the issues
  while unpacking: `[[permalink-prefix]]`, `[[wiki-issue-prefix]]`, `[[wiki-url]]`, `[[job-url]]`, `[[branch-id]]`,
  `[[user-name]]`, `[[commit-message]]`.
- Header items (branch, author, last commit, CI job and wiki buttons) without a value, or still containing `[[`, are
  hidden.
- A link becomes clickable on the field it belongs to; `javascript:` links are not.

In the browser:

| Feature | How |
|---------|-----|
| Filter by priority band | click one or more summary cards |
| Filter on text in any column | the search box (all words must occur), `/` focuses it, `Esc` clears it |
| Filter by column value | the funnel button in a column header: a checklist of the values with their counts (given the other filters), searchable, *Select all* / *Select none*; at most 500 values are listed at a time |
| Clear all filters | **Reset**, or the *Issues* card |
| Sort | click a column name, again to reverse; natural order (`C4100` before `C4244`, `2` before `10`), ties keep the input order |
| Full text | click a row, or `Enter`/`Space` on a focused row |

### create_summary.py

```
create_summary.py < issues.txt > summary.html
```

| Option | Description |
|--------|-------------|
| `-h`, `--help` | Show the usage. |

Any other argument prints the usage and exits with code 1.

Writes a short HTML page meant as the body of an e-mail. It only uses tables, HTML attributes and inline styles,
because Outlook renders HTML with Word and ignores classes, flexbox and scripts.

- `Branch: [[branch-id]]` and `Committer: [[user-name]]`, filled in by `apply_environment.py` (see its table below:
  the branch or tag name, and `GITLAB_USER_NAME`, the user who started the pipeline). A line whose value is missing
  is left out.
- One line of text: `<n> issues for <n> rules in <n> categories for <n> teams`.
- **Top 10 issues**: the 10 most important issues, lowest priority number first; issues with the same priority keep
  their input order (by file, as `sortby.py` writes them). Columns: priority, file (a link to the `[3]` file link of
  the issue when it has one), rule, team and description (cut like below). The links still contain
  `[[permalink-prefix]]`; pipe the summary through `apply_environment.py` to fill it in, as `opencanary.py run` does.
- **Issues per rule**: a table with a row per combination of rule, team, component and category, with the number of
  issues.
- The rows of one rule are grouped. The rule's **priority** (all distinct priorities, comma separated, if there are
  several), its **name** (with its total when it has more than one row) and the **description** of its first issue
  (the most important one, as the input is sorted) are shown once, in cells that span the group. The description is
  cut at the last space before 100 characters and ends with `…`.
- Rules are ordered by number of issues (fewest first), then by name (ignoring case). Rows within a rule by number of
  issues (fewest first), then team, component and category.
- An empty team, component or category is shown as `(none)`.
- The last row is the total number of issues. With no input only the text line is written.

### apply_environment.py

```
apply_environment.py <env.txt> < input > output
```

| Argument | Description |
|----------|-------------|
| `<env.txt>` | Required, the only argument. A text file with `KEY=value` lines; the line is split at the first `=`, lines without `=` are ignored. |

Replaces the placeholders in every input line (any text, normally the report):

| Placeholder | Replaced by |
|-------------|-------------|
| `[[permalink-prefix]]` | `PERMALINK_PREFIX` (with `\` as `/`, without trailing `/`) when present, else `CI_PROJECT_URL/blob/CI_COMMIT_SHA` |
| `[[job-url]]` | `CI_JOB_URL` (with `/`, without trailing `/`) |
| `[[branch-id]]` | `CI_COMMIT_REF_NAME` (the branch or tag), else `CI_BUILD_REF_NAME` (its name before GitLab 9.0), else `CI_COMMIT_SHA (commit_id)` |
| `[[user-name]]` | `GITLAB_USER_NAME`; `Scheduled build` when the `CI_PIPELINE_SOURCE` environment variable of the process contains `schedule` |
| `[[commit-message]]` | `CI_COMMIT_TITLE` |
| `[[wiki-url]]` | `WIKI_URL_PREFIX` + `_Issues` |
| `[[wiki-issue-prefix]]` | `WIKI_URL_PREFIX` + `_Issue_` |

`WIKI_URL_PREFIX` defaults to `https://wiki.company.nl/wiki/index.php?title=OpenCanary`. A missing key for job URL,
user name, commit message or permalink is written as `[[<KEY> not found by get_from_envfile()]]`, which makes the
report hide that header item. A line that contains `data-optional=""` is removed entirely when one of its
placeholders gets an empty or missing value, so pages without scripts (the summary) do not show such an item either;
the report and the summary write each optional item on its own line. `[[pipe]]` is not replaced.

### tr_regression.py

```
tr_regression.py < issues.txt
```

No arguments. An example of a regression gate, meant to be copied and edited: it removes every line that contains one
of the accepted texts listed in `filter_stdin()` (rules that still have issues today, such as `sign-compare` or
`rule-missing`). When lines remain they are new issues: they are written to stdout, `N new issue(s) where introduced!`
is written to stderr and the exit code is `1`, which fails the CI job. Otherwise the exit code is `0`.

---

## Other tools

### summarize.py

```
summarize.py [-v | -s] < issues.txt
```

| Option | Description |
|--------|-------------|
| (none) | Per rule: `<rule>: <count>`, padded to 50 characters, then `[<component>]: <description of its first issue, cut at 100 characters>`. Ordered by count (fewest first), then rule. Ends with `In total N issues.` |
| `-v` | As above, plus `@ <fileref>` of the first issue of each rule. |
| `-s` | Print only the description of every issue, one per line. |

Issues with rule `rule-missing` are counted but not listed (a warning goes to stderr).

### list_warnings.py

```
list_warnings.py < issues.txt
```

Prints the compiler options that would silence every rule in the input: `-Wno-<rule>` for gcc/clang and
`/wd<number>` for MSVC rules (rules of five characters starting with `C`, such as `C4100`). `rule-missing` is skipped.

### filter.py

```
filter.py -i FILE [-i FILE ...] [options]
```

| Option | Description |
|--------|-------------|
| `-i`, `--input FILE` | Required, repeatable: the files to read. |
| `-s`, `--separator C` | Field separator, default `\|`. |
| `-c`, `--column N` | Match only against field N, counting from 0. `-c 0` is treated as not set and matches the whole line, so the first field cannot be selected. |
| `-ic`, `--ignorecase` | Match case-insensitively. |
| `-if`, `--includefilter TEXT` | Repeatable: keep only lines containing one of these texts. |
| `-xf`, `--excludefilter TEXT` | Repeatable: remove lines containing one of these texts; wins over `--includefilter`. |
| `-fm`, `--fullmatch` | Accepted, but has no effect. |
| `-o`, `--outputfile FILE` | Write the lines to FILE instead of the console. |

Ends with `N  lines.` on stdout.

### find_dead_code.py

```
find_dead_code.py <arrays|functions|defines|variables|sources> [path]
```

Searches `path` (default `.`, respecting `.opencanaryignore`) for dead code candidates: words that occur only once in
all `.h`, `.c` and `.cc` files, in the context of the mode.

| Mode | Prints |
|------|--------|
| `arrays` | lines declaring an array `name[` whose name occurs once |
| `functions` | lines with `name(` whose name occurs once |
| `defines` | `#define NAME` where NAME occurs once |
| `variables` | `name;` or `name =` where name occurs once |
| `sources` | source files whose name does not occur in any `CMakeLists.txt` line that mentions `.c`, `.cc` or `.h` |

### cmake_completeness.py

```
cmake_completeness.py <compile_commands.json>
```

Run from the source root. Collects the files in the compile database plus everything they include, recursively
(`#include "..."` and `#include <...>` lines whose file exists relative to the including file), and prints the `.cpp`/`.cc` files under the current directory that are
not part of that set (`_autogen` files excluded), after listing both sets.

### cmake_to_dot.py

```
cat */CMakeLists.txt | cmake_to_dot.py > deps.dot
```

No arguments. Reads CMake text and writes a Graphviz digraph with an edge for every `target_link_libraries`
dependency (`PRIVATE`/`PUBLIC` skipped, `${PROJECT_NAME}` and `add_library(... ALIAS ...)` names resolved).

### run_clang_format.py

```
run_clang_format.py [/f] [file ...]
```

| Argument | Description |
|----------|-------------|
| `file ...` | Files to check; without files all `.h`, `.hpp`, `.cpp` and `.cc` files under the current directory, respecting `.gitignore` and `.clang-format-ignore`. |
| `/f` | Format the files in place instead of checking. |

Generated files are skipped (path contains `CompilerIdCXX`, or one of the first 50 lines is a comment saying
`generated include file` or `file is autogenerated`). Checks with `clang-format --dry-run -Werror`; exit code `1` when
a file is not formatted. The binary is the `CLANG_FORMAT` environment variable, default `clang-format-11`.

### send_email.py

```
send_email.py <bodyfile> [attachment ...] [-s <subject>]
```

| Argument | Description |
|----------|-------------|
| `<bodyfile>` | Mail body; a file ending in `.html` is sent as HTML, otherwise as text. |
| `attachment ...` | Files to attach. |
| `-s <subject>` | Subject, default `Software Quality Report`. |

A template: the SMTP server, sender and login are variables at the top of the script, and the recipients are chosen in
`send_report()`: recent git authors (2 weeks) that are in a fixed list, another address for scheduled builds or a
specific project, and an admin address when not running on CI.

### pype.py

```
pype.py <logfile> [filter-msvc-warnings] [add-msvc-summary] [filter-gcc-warnings] [add-gcc-summary] [build_summary] [test_summary] -- <command ...>
```

Runs the command through the shell, writes its combined stdout and stderr to `<logfile>`, and streams it to stderr at
the same time (unbuffered, for live CI logs). `filter-*-warnings` hides warning and note lines from the stream,
`add-*-summary` repeats all `: error ` lines at the end. Exits with the command's exit code and prints the elapsed time.

`build_summary` and `test_summary` append to `summary.log` in the current directory, so a CI job can show the
failures at the end (for example `cat summary.log` in `after_script`), also when several commands are run with pype:

| Option          | Appends to `summary.log` |
|-----------------|--------------------------|
| `build_summary` | lines with `FAILED:`, `Failed`, `error:` or `Killed` |
| `test_summary`  | gtest/ctest failures (`[  FAILED  ]`, `***Failed`, `: Failure`), and at the end all unique AddressSanitizer, UndefinedBehaviorSanitizer and ThreadSanitizer lines, their counts, and the sanitizer lines that refer to a source file |

### returncode.py

```
returncode.py [N]
```

Exits with code N (default 0), for example to ignore the exit code of a tool in a CI script.

### prettydiff.py

```
prettydiff.py <file1> <file2> [--num=COLUMN,DELTA ...] [--sep=SEP]
```

Prints lines of `file2` that are not in `file1` with `+ `, and lines of `file1` not in `file2` with `- `. Lines are
compared per field (separator `--sep`, default `|`; the last field is not compared). `--num=COLUMN,DELTA` makes a
field numeric: values that differ by at most DELTA (default 1) are equal. Needs `pip install docopt`.

---

## Known limitations

- `parse_gcc.py` takes the file name for the link up to the first `:`, so a Windows path with a drive letter gets a
  wrong `[3]` link; `tr_customize.py` replaces that link with a correct one.
