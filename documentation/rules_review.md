# Review of the oc_cpp_issues.py rules

A review of the text-search rules in `verification/oc_cpp_issues.py` (November 2026): which ones are wrong, which ones
duplicate a compiler warning, and which rules could be added. For each rule, why it is reported and how to solve it is
in [rules.md](rules.md).

Method: `oc_cpp_issues.py --mark-comments` was run on a production code base of 3,326 files and 726k lines, and a sample
of the issues of each rule was read. Suspect patterns were also tried on single test lines. The issue counts below come
from that run.

## Confirmed bugs

| Rule | Problem | Evidence / fix |
|------|---------|----------------|
| `extern`, `volatile-variable`, `manual-delete` | `($\|[^\w])` needs a character before the keyword, so a line that starts with it is never reported | `extern int g;` and `volatile int f;` are missed, the same lines indented are reported. Use `\b` |
| `manual-delete` | misses `delete[] p;`, `delete this->p;` and `delete a.b;` | tested |
| `null-macro` | `\sNULL\s` needs whitespace on both sides: `f(NULL)`, `p = NULL;` and `== NULL)` are missed; the only hit in code was inside a string | use `\bNULL\b` |
| `self-include` | compares only the file name: a header `inifile/configuration.h` that includes `"configuration/configuration.h"` (another file) is reported; all 10 hits were false | resolve the include relative to the header and compare paths |
| `duplicate-include` | ignores `#if` / `#else` branches: `#include <regex>` once in each branch is reported | only report when the earlier include is in the same or an enclosing branch |
| `assign-in-condition` | reports the C++17 `if (init; cond)`: `if (auto x = f(); x != 0)`, most of the 129 hits | exclude conditions that contain `;` |
| `c-style-pointer-cast` | reports unnamed parameters (`void f(QTimerEvent *)`) and Qt `SLOT(...)` signatures; misses `(const char*)x`, `(unsigned char *)x` and `(Foo::Bar*)x` | require an expression after the `)`, allow qualifiers and `::` |
| `min-max-macro` | any macro with MIN or MAX in its name and a `(` and `:`, such as `#define MAX_LEN (b ? 10 : 20)`, and even `#define CLAMP(x) std::min(...)` | use `#define\s+(min\|max)\s*\(` |
| `unqualified-make-unique` | every name that contains `make_unique` matches: `make_unique_id()` | use `\bmake_unique\s*<` |
| `todo` | all hits in code were a variable named `todo` (`while (todo != 0)`) | only search comments |
| `redundant-semicolon`, `null-macro` | match inside string literals: `"a;;b"`, `"attach a NULL data pointer"` | see [structural improvements](#structural-improvements), point 1 |
| `using-namespace-in-header` | `^using namespace` misses an indented `using namespace` inside a namespace block, which leaks just the same | allow leading whitespace |
| `constant-if-directive` | misses `# if 0` and `#if (0)` | allow `#\s*if\s*\(?\s*\d` |
| `undef-macro` | all 9 hits were local helper macros that are `#undef`'d after use, which is good practice | only report the `#undef` of a macro that the file did not define itself, such as `Bool` |
| `short-macro-name` | 2 of the 3 hits were such local, `#undef`'d helper macros | the same exemption |
| `extern-volatile` | an `extern volatile` line is reported three times: `extern`, `volatile-variable` and `extern-volatile` | report only `extern-volatile` for it |

## Structural improvements

1. **Match a rule only where it belongs.** Rules about code should not match inside comments or string literals.
   `todo`, `non-english-word` and `misspelled-word` should search only comments, and the remaining rules the whole
   line. `without_comments()` already does half of this, and blanking string contents as well is a small addition.
   This removes most false positives at the source, so the `comments` category of `--mark-comments` becomes a
   fallback instead of a filter that the report depends on.
2. **Keep all rules in one table.** Half of the rules are in `LINE_RULES` and half in a chain of `if` statements, each
   with its own regex habits. One table makes every rule testable the same way, and makes bugs like the ones above
   less likely.
3. **Make categories and descriptions consistent.** `assign-in-condition` has the category `assign_in_condition`,
   which is its own name, not a category (`bug` or `readability` fits). The descriptions start with `Anti-pattern:`,
   `prevent UB:` or nothing, and one has a typo ("dont").
4. **Speed.** The line checks take about 23 seconds for 726k lines. Cheap pre-checks, such as skipping the `#`
   rules on lines without a `#`, would remove most of that time.

## Rules that compilers already report

Before keeping the text version of these rules, check whether the compiler warning is enabled in the builds that
OpenCanary collects; the compiler is more precise.

| Rule | Compiler warning |
|------|------------------|
| `catch-by-value` | GCC `-Wcatch-value` (in `-Wall`) |
| `address-null-check` | GCC `-Waddress`, clang `-Wtautological-undefined-compare` |
| `memset-zero-size` | `-Wmemset-transposed-args` |
| `assign-to-self` | clang `-Wself-assign` |
| `assign-in-condition` | `-Wparentheses` reports `if (x = y)` |
| `deprecated-uncaught-exception` | `-Wdeprecated-declarations` |
| `redundant-semicolon` | clang `-Wextra-semi-stmt` |
| `reserved-macro-name` | clang `-Wreserved-macro-identifier` |

Once the C++17 false positives are fixed, `assign-in-condition` mostly reports `if ((x = f()))`, where the double
parentheses are the usual way to say that the assignment is intended. The rule can be removed.

## Rules to add

None of these are reported by GCC, clang or MSVC (unless noted). Roughly in order of value:

| Rule | Pattern (sketch) | Why |
|------|------------------|-----|
| `unnamed-lock` | `\b(lock_guard\|unique_lock\|scoped_lock\|QMutexLocker)\s*(<[^>]*>)?\s*[({][^;]*[)}]\s*;` without a variable name | the lock is released at the end of the statement, a real concurrency bug |
| `suppressed-warning` | `#pragma warning\s*\(\s*disable`, `#pragma (GCC\|clang) diagnostic ignored` | hides warnings from the tool that collects them; shows what is hidden next to what is reported |
| `empty-catch` | `catch\s*\([^)]*\)\s*\{\s*\}` | the exception is silently swallowed |
| `assert-side-effect` | `\bassert\s*\(.*([^=!<>]=[^=]\|\+\+\|--)` | the side effect disappears in a release build |
| `unsafe-c-string` | `\b(strcpy\|strcat\|sprintf\|vsprintf\|gets)\s*\(` | buffer overflows; only MSVC warns (C4996) |
| `atoi-family` | `\b(atoi\|atol\|atof)\s*\(` | errors cannot be detected, use `std::from_chars` |
| `new-in-smart-pointer` | `(unique_ptr\|shared_ptr)\s*<[^>]*>\s*\w*\s*[({]\s*new\b` | like `reset-with-new`: use `std::make_unique` or `std::make_shared` |
| `manual-array` | `\bnew\s+[\w:<>]+\s*\[`, `\bdelete\s*\[\]` | use `std::vector` or `std::array` |
| `malloc-in-cpp` | `\b(malloc\|calloc\|realloc\|free)\s*\(` | no constructors or destructors, manual lifetime |
| `thread-detach` | `\.detach\s*\(\s*\)` | the thread can outlive the data it uses |
| `hardcoded-secret` | `(?i)(password\|passwd\|secret\|token)\w*\s*=\s*"[^"]+"` | credentials in the source |
| `commented-out-code` | comment text that ends in `;` or `{` (with `without_comments()`) | dead code in comments |
| `constant-macro` | `#define\s+[A-Z_]\w*\s+[-+]?\d` | use `constexpr` |
| `missing-include-guard` | a header without `#pragma once` and without an `#ifndef`/`#define` pair (a check per file) | the header breaks when it is included twice |
| `dangling-c-str` | `=\s*[^;]*\w\([^;]*\)\.c_str\s*\(\)\s*;` | a pointer into a temporary string that is already destroyed; clang reports only some cases |

## Suggested order

1. Fix the confirmed bugs, each with a test.
2. Match rules only in code, comments or both ([structural improvements](#structural-improvements), point 1); this
   removes most false positives.
3. Remove or lower the priority of the rules that compilers already report.
4. Add new rules, starting with `unnamed-lock`, `suppressed-warning` and `empty-catch`.

## Status

Done:
- All confirmed bugs above are fixed, each with a test.
- Every line rule is in one table (structural improvement 2), and the C++ rules only look at the code, not at
  comments and string literals (point 1); `todo` only looks at comments, `non-english-word` at code and comments,
  `misspelled-word` at everything. `--mark-comments` is removed, there is nothing in comments left for it to mark.
- The category of `assign-in-condition` is `bug` (point 3, partly).
- `unnamed-lock`, `suppressed-warning` and `empty-catch` are added.

Open:
- Remove or lower the priority of the rules that compilers already report; this depends on the warnings that are
  enabled in the builds that OpenCanary collects.
- Make the description prefixes consistent (point 3) and speed up the line checks (point 4).
- The other proposed rules, from `assert-side-effect` on.
- A raw string literal (`R"(...)"`) that spans lines is not recognized as a literal.
