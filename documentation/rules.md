# OpenCanary rules

The rules that OpenCanary reports itself: `oc_cpp_issues.py` checks every line of the headers and sources (and the
Visual Studio projects) for common C++ problems. This page explains, per rule, why it is reported and how to solve it.
In the report, the rule links to its section here, and so does the light bulb after it (see `rules/links.txt`);
every section has an anchor: `rules.md#manual-delete` for `manual-delete`.

Rules are named like the clang warnings (lowercase words separated by `-`), but never with the name of a compiler
warning: `rules/priorities.txt` matches on the rule name only, so `c-style-pointer-cast` can get another priority than
clang's `old-style-cast`; for the same reason a name does not contain a part that `priorities.txt` matches for compiler
warnings with `~`, such as `comment`. (`rules/links.txt` gives the solution link to every issue with source
`opencanary`.) Until November 2026 the rules were numbered (`AP#13` is now `manual-delete`); the table below also lists
the old names. The checks are plain text searches, without a C++ parser, so they can report a line that is fine (in a
comment or a string, for example). Exclude files with `.opencanaryignore`, or drop a rule with `rules/interest.txt`. The
default priorities are in `rules/priorities.txt`, the exact patterns in [details.md](details.md#oc_cpp_issuespy).

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
| [reserved-macro-name](#reserved-macro-name) | ub | `#define` of a reserved name (starting with `_` or with `__`) | `AP#9` |
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
| [memset-zero-size](#memset-zero-size) | bug | `memset` with size 0 | |
| [string-braced-size](#string-braced-size) | bug | `std::string s{n}` | |
| [assign-to-self](#assign-to-self) | bug | `x = x;` | |
| [self-include](#self-include) | bug | a header that includes itself | |
| [address-null-check](#address-null-check) | ub | `&x == nullptr` | |
| [void-pointer-pointer-cast](#void-pointer-pointer-cast) | ub | cast to `void **` | |
| [throw-pointer](#throw-pointer) | redflag | `throw new` | |
| [dangling-range-for](#dangling-range-for) | bug | range-for over a member of a temporary | |
| [include-source-file](#include-source-file) | redflag | `#include` of a `.cpp` file | |
| [throw-non-exception](#throw-non-exception) | redflag | `throw "text"` or `throw 1` | |
| [catch-by-value](#catch-by-value) | redflag | `catch (std::exception e)` | |
| [uninitialized-variable](#uninitialized-variable) | ub | `int x;` in a source file | |
| [short-macro-name](#short-macro-name) | redflag | macro with a name of 3 characters or less | |
| [deprecated-uncaught-exception](#deprecated-uncaught-exception) | modernize | `std::uncaught_exception()` | |
| [undef-macro](#undef-macro) | redflag | `#undef` | |
| [reset-with-new](#reset-with-new) | modernize | `.reset(new ...)` | |
| [triple-pointer](#triple-pointer) | readability | `T ***` | |
| [empty-special-member](#empty-special-member) | modernize | `Foo::Foo() {}` | |
| [duplicate-include](#duplicate-include) | readability | the same `#include` twice | |
| [short-include-guard](#short-include-guard) | readability | include guard such as `MOVE_H` | |
| [foreach-macro](#foreach-macro) | modernize | `foreach`, `Q_FOREACH`, `BOOST_FOREACH` | |
| [endless-for](#endless-for) | readability | `for (;;)` | |
| [redundant-semicolon](#redundant-semicolon) | readability | `;;` | |
| [todo](#todo) | readability | `TODO` | |
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

**`#define` of a reserved name.** Reported for `#define _Name` and for a name with a double underscore
(`#define MY__NAME`).

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

### memset-zero-size

**`memset` with size 0.** Reported for a `memset` call whose last argument is `0`.

`memset(p, sizeof(p), 0)` sets nothing: the last two arguments (value and size) are easy to swap. **Solve:** write
`memset(p, 0, sizeof(p))`, or better, value-initialize the object (`Foo foo{};`) or use `std::fill`.

### string-braced-size

**`std::string s{n}`.** Reported for a `std::string` or `std::wstring` initialized with a number in braces.

Braces select the initializer list constructor: `std::string buffer{10}` is a string of one character with value 10,
not a buffer of 10 characters. **Solve:** use parentheses, `std::string buffer(10, '\0')`.

### assign-to-self

**Assignment of a variable to itself.** Reported for `x = x;`.

This does nothing, and usually one side was meant to be another name, for example a member and a parameter with the
same name (`int x = x;` even reads an uninitialized value). **Solve:** assign the intended variable, for example
`this->x = x`, or rename the parameter.

### self-include

**A header that includes itself.** Reported for an `#include` of a file with the same name as the header.

With an include guard it does nothing, without one it recurses until the compiler gives up; either way it is a
mistake, often a copy-paste of the include list of the source file. **Solve:** remove the include.

### address-null-check

**The address of an object compared to `nullptr`.** Reported for `&ref == nullptr` (or `!=`).

The address of an object or a reference is never `nullptr`; a reference bound to `*nullptr` is already undefined
behavior. The compiler may remove the check entirely. **Solve:** check the pointer before it is dereferenced into a
reference, or pass a pointer when "no object" is a valid value.

### void-pointer-pointer-cast

**Cast to `void **`.** Reported for `(void **)` and `reinterpret_cast<void **>`.

`T**` does not convert to `void**`; the cast compiles, but writing a `void*` through the result accesses a `T*`
object as a `void*` object, which breaks strict aliasing (undefined behavior). This is common with COM style
`QueryInterface(..., (void **)&p)` calls. **Solve:** use a `void *` variable and `static_cast` it to `T*` afterwards,
or an API helper such as `IID_PPV_ARGS`.

### throw-pointer

**`throw new`.** Reported for `throw new ...`.

A thrown pointer must be deleted by whoever catches it, and `catch (const std::exception &)` does not catch it at all.
**Solve:** throw by value and catch by reference: `throw std::runtime_error("...")`.

### dangling-range-for

**Range-based for over a member of a temporary.** Reported for `for (auto &x : list.transform().view())`.

Before C++23 only the result of the last call lives as long as the loop; the temporary returned by `transform()` is
destroyed before the first iteration, so a `view()` into it dangles. **Solve:** store the temporary in a variable
first: `auto transformed = list.transform(); for (auto &x : transformed.view())`. The rule is a text search, it
cannot see whether the first call returns a reference (then the loop is fine).

### include-source-file

**`#include` of a source file.** Reported for `#include "foo.cpp"`.

When the included source is also compiled by itself, its functions are defined twice (an ODR violation, a linker
error or undefined behavior), and it hides the real dependency. **Solve:** include the header and link the source;
for a unity build let the build system (CMake `UNITY_BUILD`) do it.

### throw-non-exception

**Throwing something that is not an exception.** Reported for `throw "this is wrong";` or `throw 1;`.

A `catch (const std::exception &)` does not catch it, so it ends the program or needs a `catch (...)` that cannot
tell what went wrong. **Solve:** throw an exception class, such as `std::runtime_error("this is wrong")` or a class
derived from `std::exception`.

### catch-by-value

**Catching an exception by value.** Reported for `catch (std::exception e)`.

Catching by value copies the exception and slices a derived exception to the caught type, so `what()` and the type
of the derived class are lost, and a `throw e;` rethrows the sliced copy. **Solve:** catch by const reference:
`catch (const std::exception &e)`, and rethrow with `throw;`.

### uninitialized-variable

**Variable without an initial value.** Reported for `int x;` (also `bool`, `double`, `float`) in a source file.

Reading it before it is assigned is undefined behavior, and on every path a later change can introduce that read.
**Solve:** give it a value where it is declared: `int x = 0;`, or declare it where its value is known. Headers are
not checked: there such a line is usually a member that the constructor initializes.

### short-macro-name

**Macro with a very short name.** Reported for `#define` of a name of 3 characters or less, such as `#define N 10`.

A macro replaces the name everywhere after it, also in other headers, so a short name such as `N`, `PI` or `MAX`
easily changes unrelated code. **Solve:** use a `constexpr` variable or an `enum`, or give the macro a long name with
a project prefix.

### deprecated-uncaught-exception

**`std::uncaught_exception()`.** Reported for a call of `uncaught_exception()`.

It is deprecated in C++17 and removed in C++20: it cannot tell a destructor that runs during stack unwinding apart
from a destructor of an object created during that unwinding. **Solve:** use `std::uncaught_exceptions()`, which
returns a count; compare it with the count stored in the constructor.

### undef-macro

**`#undef`.** Reported for every `#undef`.

Undefining a macro changes the meaning of every header included after it, depending on the include order, and is
usually a workaround for a macro that should not exist (such as `min` and `max` from `<windows.h>`). **Solve:**
remove the macro at its source (for `<windows.h>`: define `NOMINMAX`), or replace it with a function or constant.
Keep `#undef` only for a macro that is defined and undefined locally in the same file.

### reset-with-new

**`.reset(new ...)`.** Reported for `ptr.reset(new Foo(...))`.

A bare `new` mixes manual and automatic ownership, and `std::make_shared` allocates the object and its control block
at once. **Solve:** `ptr = std::make_unique<Foo>(...)` or `ptr = std::make_shared<Foo>(...)` (or
`boost::make_shared`).

### triple-pointer

**Pointer to a pointer to a pointer.** Reported for `char ***p`.

Three levels of indirection are very hard to follow and usually mean ownership and arrays are managed by hand.
**Solve:** use containers and references, for example `std::vector<std::vector<std::string>>` or
`std::vector<std::string> &`.

### empty-special-member

**Empty constructor or destructor.** Reported for `Foo::Foo() {}` and `Foo::~Foo() {}`.

A user-provided empty constructor or destructor makes the class non-trivial and, for the destructor, removes the
implicit move operations. **Solve:** remove it, or declare it `= default` (in the header, or in the source file when
the destructor must see a complete type, as with `std::unique_ptr` members).

### duplicate-include

**Duplicate `#include`.** Reported for the second `#include` of the same file in one file.

It does nothing (the include guard skips it) and makes the include list harder to maintain. **Solve:** remove the
second include.

### short-include-guard

**Include guard that is not unique.** Reported for an include guard of 8 characters or less, such as
`#define MOVE_H`.

When two headers in the build use the same guard, the second one is silently skipped, which gives confusing errors.
**Solve:** use `#pragma once`, or a guard with the project and path in it: `MYPROJECT_ALGORITHM_MOVE_H`.

### foreach-macro

**`foreach` macro.** Reported for Qt's `foreach` / `Q_FOREACH` and `BOOST_FOREACH`.

The language has a range-based for since C++11; Qt's `foreach` also copies the container and is deprecated.
**Solve:** `for (const auto &item : list)`; to iterate a Qt container that is not `const`, use `std::as_const(list)`
to avoid a detach.

### endless-for

**`for (;;)`.** Reported for an endless `for` loop.

`while (true)` says the same thing in words. **Solve:** write `while (true)`.

### redundant-semicolon

**Redundant semicolon.** Reported for `;;` outside a `for`.

The empty statement does nothing, but it can hide an editing mistake. **Solve:** remove the extra `;`.

### todo

**`TODO`.** Reported for the word `todo` (any case).

A todo in the code is work that is not tracked anywhere and is easily forgotten. **Solve:** do it, or move it to the
issue tracker and remove the comment (or refer to the issue in it).

### parse-error

**The file could not be read.** Reported when a project, header or source could not be parsed, for example because it
is not UTF-8.

The other checks skipped this file. **Solve:** save the file as UTF-8, or exclude it (generated or third party code) in
`.opencanaryignore`.
