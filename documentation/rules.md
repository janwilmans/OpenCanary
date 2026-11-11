# OpenCanary rules

The rules that OpenCanary reports itself: `oc_cpp_issues.py` checks every line of the headers and sources (and the
Visual Studio projects) for common C++ problems. This page explains, per rule, why it is reported and how to solve it.
In the report, the rule links to its section here, and so does the light bulb after it (see `rules/links.txt`);
every section has an anchor: `rules.md#manual-delete` for `manual-delete`.

Rules are named like the clang warnings (lowercase words separated by `-`), but never with the name of a compiler
warning: `rules/priorities.txt` matches on the rule name only, so `c-style-pointer-cast` can get another priority than
clang's `old-style-cast`. (`rules/links.txt` gives the solution link to every issue with source `opencanary`.) Until
November 2026 the rules were numbered (`AP#13` is now `manual-delete`); the table below also lists the old names. The
checks are plain text searches, without a C++ parser, so they can report a line that is fine (in a comment or a string,
for example). Exclude files with `.opencanaryignore`, or drop a rule with `rules/interest.txt`. The default priorities
are in `rules/priorities.txt`, the exact patterns in [details.md](details.md#oc_cpp_issuespy).

| Rule | Category | In short | Was |
|------|----------|----------|-----|
| [make-unique-header](#make-unique-header) | modernize | `#include` of a `make_unique` header | `MO#1` |
| [unqualified-make-unique](#unqualified-make-unique) | modernize | `make_unique` that is not `std::make_unique` | `MO#2` |
| [reinterpret-cast](#reinterpret-cast) | casting | `reinterpret_cast` | `AP#3` |
| [volatile-variable](#volatile-variable) | redflag | `volatile` | `AP#4` |
| [warnings-not-errors](#warnings-not-errors) | redflag | project does not treat warnings as errors | `UD#4` |
| [null-macro](#null-macro) | modernize | `NULL` | `MO#5` |
| [warning-level-not-4](#warning-level-not-4) | redflag | project warning level is not 4 | `UD#5` |
| [non-english-word](#non-english-word) | readability | Dutch words in code or comments | `AP#6` |
| [constant-if-directive](#constant-if-directive) | readability | `#if 0` / `#if 1` | `AP#7` |
| [c-style-pointer-cast](#c-style-pointer-cast) | modernize | C-style pointer cast | `AP#8` |
| [reserved-macro-name](#reserved-macro-name) | ub | `#define` of a reserved name (starting with `_`) | `AP#9` |
| [min-max-macro](#min-max-macro) | modernize | `min` or `max` macro | `AP#10` |
| [extern](#extern) | redflag | `extern` | `AP#11` |
| [register-keyword](#register-keyword) | redflag | `register` (disabled) | `AP#12` |
| [manual-delete](#manual-delete) | redflag | `delete` | `AP#13` |
| [extern-volatile](#extern-volatile) | redflag | `extern volatile` | `AP#14` |
| [string-literal-cast](#string-literal-cast) | ub | casting away the constness of a string literal | `AP#15` |
| [const-cast](#const-cast) | readability | `const_cast` | `AP#16` |
| [using-namespace-in-header](#using-namespace-in-header) | redflag | `using namespace` in a header | `AP#17` |
| [assign-in-condition](#assign-in-condition) | assign_in_condition | assignment in an `if`, `while` or `switch` condition | `AP#18` |
| [misspelled-word](#misspelled-word) | spelling | misspelled word | `AP#19` |
| [parse-error](#parse-error) | parse | file could not be read | `PARSE` |

### make-unique-header

**`#include` of a `make_unique` header.** Reported for a line that contains `/make_unique`, such as
`#include "util/make_unique.h"`.

Since C++14 `std::make_unique` is part of the standard library, so a project specific implementation is no longer
needed. **Solve:** include `<memory>` instead, use `std::make_unique`, and remove the own implementation once nothing
uses it.

### unqualified-make-unique

**`make_unique` that is not `std::make_unique`.** Reported for a line that uses `make_unique` without `std::`.

A project specific or unqualified `make_unique` hides which implementation is used and can be found by argument
dependent lookup. **Solve:** write `std::make_unique<T>(...)` and include `<memory>`.

### reinterpret-cast

**`reinterpret_cast`.** Reported for a line that contains `reinterpret_cast<`.

`reinterpret_cast` tells the compiler to treat memory as another type. Accessing an object through a pointer of an
unrelated type is undefined behavior (strict aliasing), and the result depends on the platform. **Solve:**
- to look at the bytes of an object, copy them: `std::memcpy`, or `std::bit_cast` (C++20);
- for a class hierarchy use `static_cast` (or `dynamic_cast` when the type is not known);
- for an API that needs it (sockets, OS handles), keep the cast in one small, documented function.

### volatile-variable

**`volatile`.** Reported for a line that declares something `volatile`.

`volatile` only stops the compiler from optimizing away reads and writes; it does not make access atomic and does
not order it between threads. It is meant for memory mapped hardware registers. **Solve:** for data shared between
threads use `std::atomic<T>` or a `std::mutex`; keep `volatile` only for hardware access.

### warnings-not-errors

**The project does not treat warnings as errors.** Reported for a Visual Studio project (`*.vcxproj`) configuration
without `<TreatWarningAsError>true</TreatWarningAsError>`.

Without it, new warnings pile up unnoticed. **Solve:** set *C/C++ > General > Treat Warnings As Errors* to *Yes (/WX)*
for every configuration, after solving (or explicitly disabling) the current warnings.

### null-macro

**`NULL`.** Reported for a line with `NULL` surrounded by whitespace.

`NULL` is an integer constant: it takes part in overload resolution and template deduction as an `int`, not as a
pointer. **Solve:** use `nullptr`. `clang-tidy` can do this automatically (`modernize-use-nullptr`).

### warning-level-not-4

**The project warning level is not 4.** Reported for a Visual Studio project configuration whose `<WarningLevel>`
does not end with `4`.

Level 4 reports many problems that the default level 3 hides. **Solve:** set *C/C++ > General > Warning Level* to
*Level4 (/W4)* for every configuration.

### non-english-word

**Dutch words in code or comments.** Reported for a line with words such as `deze`, `niet`, `naam`, `als`, `voet` or a
word ending in `ectie`, ignoring case.

Code is read by people who do not all speak Dutch, and mixed languages make names hard to find. **Solve:** translate the
comment or name to English. Exclude generated or translated files (for example translation tables) in
`.opencanaryignore`.

### constant-if-directive

**`#if 0` / `#if 1`.** Reported for a line with `#if` followed by a number.

Code that is switched off with the preprocessor is not compiled, so it is not kept up to date and only confuses the
reader. Version control keeps the history. **Solve:** delete the disabled branch (`#if 0`), or remove the condition and
keep the code (`#if 1`). For a real configuration option, use a named macro or a CMake option.

### c-style-pointer-cast

**C-style pointer cast.** Reported for a cast such as `(Foo *)p`.

A C-style cast silently does whatever is needed to compile: a `static_cast`, a `const_cast`, a `reinterpret_cast` or a
combination, so a mistake is not reported. **Solve:** use the C++ cast that states the intent: `static_cast`,
`dynamic_cast`, or (rarely, see [reinterpret-cast](#reinterpret-cast) and [const-cast](#const-cast)) `reinterpret_cast`
or `const_cast`. Better still, change the types so no cast is needed.

### reserved-macro-name

**`#define` of a reserved name.** Reported for `#define _Name`.

Names that start with an underscore followed by a capital letter (and all names with a double underscore) are reserved
for the compiler and the standard library; defining one is undefined behavior and can clash with system headers.
**Solve:** rename the macro, for example `_MY_HEADER_H` to `MY_HEADER_H`, or use `#pragma once` for include guards.

### min-max-macro

**`min` or `max` macro.** Reported for a `#define` of `min` or `max` with a conditional expression.

A macro evaluates its arguments more than once (`min(i++, j)`), has no type checking and breaks `std::min` and
`std::max` in every file that includes it. **Solve:** use `std::min` / `std::max` from `<algorithm>`. For `<windows.h>`,
define `NOMINMAX` before including it.

### extern

**`extern`.** Reported for a line with `extern` (not `extern "C"`).

An `extern` variable is a global that any file can change, which hides dependencies and makes the initialization order
between files undefined. **Solve:** pass the value as a parameter or make it a member; for a constant use `constexpr` or
`inline constexpr` in a header; for a single shared instance use a function that returns a reference to a local static.

### register-keyword

**`register` (disabled).** This check is disabled: it gave too many false positives and compilers already report
`register`, which is removed in C++17. **Solve:** remove the `register` keyword.

### manual-delete

**`delete`.** Reported for `delete name;`.

Manual `delete` is easy to forget on an early return or an exception (a leak) or to do twice (undefined behavior).
**Solve:** let an owner release the object: `std::unique_ptr` (create it with `std::make_unique`), a container such as
`std::vector`, or the parent object in a framework that owns its children (for example a `QObject` parent).

### extern-volatile

**`extern volatile`.** Reported for a line with `extern volatile`.

A global, mutable variable that is also `volatile` combines the problems of [extern](#extern) and
[volatile-variable](#volatile-variable), and is almost always an attempt at sharing data between threads or with an
interrupt. **Solve:** use `std::atomic<T>` owned by one module, with functions to read and change it.

### string-literal-cast

**Casting away the constness of a string literal.** Reported for `(char *)"..."`.

A string literal is constant; writing to it through the cast is undefined behavior (and usually a crash). **Solve:**
use `const char *` or `std::string_view`. When an old API needs a `char *` it does not change, keep the cast in one
place; when it does change the text, copy it into a `std::string` or a `char` array first.

### const-cast

**`const_cast`.** Reported for a line that contains `const_cast<`.

Removing `const` breaks the promise the type makes, and changing an object that really is `const` is undefined behavior.
**Solve:** fix the constness of the function that is called (make it take a `const` reference), or provide a `const`
overload. Use `mutable` for members that are only a cache. Keep a `const_cast` only for an old API that does not change
the object, with a comment.

### using-namespace-in-header

**`using namespace` in a header.** Reported for a header line that starts with `using namespace`.

Every file that includes the header gets the whole namespace, which can cause name clashes and changes overload
resolution in code that never asked for it. **Solve:** write the qualified names (`std::string`) in headers, or use a
`using` declaration for one name inside a function or class. `using namespace` is fine inside a `.cpp` file.

### assign-in-condition

**Assignment in a condition.** Reported for `if`, `while` or `switch` with ` = ` inside the parentheses.

`if (a = b)` is a classic typo for `if (a == b)`, and when the assignment is intended the reader cannot tell the
difference. **Solve:** compare with `==` if that was meant. Otherwise move the assignment before the condition, or use
the C++17 init-statement: `if (auto it = map.find(key); it != map.end())`.

### misspelled-word

**Misspelled word.** Reported for a common misspelling, such as `recieve`, `seperate` or `wich`, as a whole word in a
header or source. Needs [ripgrep](https://github.com/BurntSushi/ripgrep) (`rg`).

Misspelled names make code hard to search, and a misspelling in an interface spreads to all its users. **Solve:**
correct the spelling; for a name in an interface, rename it everywhere (the IDE's rename refactoring helps). The list of
words is `wrong_word_list` in `oc_cpp_issues.py`.

### parse-error

**The file could not be read.** Reported when a project, header or source could not be parsed, for example because it
is not UTF-8.

The other checks skipped this file. **Solve:** save the file as UTF-8, or exclude it (generated or third party code) in
`.opencanaryignore`.
