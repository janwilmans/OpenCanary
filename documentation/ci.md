# CI jobs that find more

OpenCanary only reports what the tools in the build tell it, so what it finds depends on the builds that run. This
page recommends a set of CI jobs for a C++ project: which builds to run when, which warnings to turn on, which
sanitizers to run the tests under, and why a second compiler and an LTO build each find problems that the other builds
do not. The examples use GitLab CI and CMake; the ideas apply to any CI system and build generator.

## The jobs

A typical project has these kinds of jobs. Fast checks run on every push, and the slow, thorough builds run every
night, so they still report a problem within a day.

| Job | When | What it is for | OpenCanary input |
|-----|------|----------------|------------------|
| verification | every push, first | formatting, file checks, quick text checks; stops the pipeline before the builds when it fails | `cpp-issues` |
| debug (GCC) | every push | the configuration that developers use; assertions on | `gcc` log |
| release (GCC) + UBSan | every push | the configuration that is shipped, with cheap undefined behavior checks while the tests run | `gcc` log |
| release (Clang) | every push | a second compiler: other warnings, other diagnostics, other standard library assumptions | `gcc` log (Clang has the same format) |
| release (MSVC) | every push, when the code also targets Windows | a third compiler and standard library | `msvc` log |
| debug + ASan + UBSan | nightly | memory errors and undefined behavior while the tests run, with the debug checks on | test logs |
| release + ASan + UBSan | nightly | the same with optimization, which makes other bugs visible | test logs |
| debug + TSan, release + TSan | nightly | data races; TSan cannot be combined with ASan | test logs |
| release + LTO | nightly, and for tagged releases | the build that is shipped, and the only build in which GCC checks the whole program, see [LTO builds](#lto-builds) | `gcc` log |
| quality report | nightly | Clang with many extra warnings and GCC, both without `-Werror` so every warning is reported; `oc_cpp_issues.py`; `compile_flags.py` | `gcc` (for both), `cpp-issues`, `compile-flags` |
| clang-tidy, coverage | nightly | checks and figures that are too slow for every push | `gcc` log (clang-tidy), coverage report |
| integration test | nightly | the installed product on a real machine | test logs |

Every build job writes its compile database (`-DCMAKE_EXPORT_COMPILE_COMMANDS=ON`, for the Ninja and Makefile
generators), keeps its build log as an artifact and pipes the log through OpenCanary. Use `tr_regression.py` to fail
the job on new issues, so the number of issues can only go down.

```yaml
.build:
  script:
    - cmake -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=ON ${CMAKE_CMDLINE}
    - $OC/pype.py captured_build.log build_summary -- cmake --build ${BUILD_OUTPUT_DIR} -- -v
    - cat captured_build.log | $OC/parse_gcc.py gcc > issues.txt
    - $OC/oc_cpp_issues.py . >> issues.txt
    - $OC/compile_flags.py ${BUILD_OUTPUT_DIR} >> issues.txt
    - cat issues.txt | $OC/tr_regression.py
```

With `opencanary.py run` the same inputs are tables in `opencanary.toml`:

```toml
[[input]]
format = "gcc"
source = "clang"
path = "captured_clang.txt"

[[input]]
format = "gcc"
source = "gcc"
path = "captured_gcc.txt"

[[input]]
format = "cpp-issues"
path = "."

[[input]]
format = "compile-flags"
path = "build/release"     # the build directory, or its compile_commands.json
```

## Warning settings

Most bugs that a compiler can find are behind a warning that is off by default. Turn the useful ones on in every
build, and make them errors in the builds that run on every push, so a new warning stops the merge request instead of
adding to a list. Keep two exceptions:

- **The quality report build does not use `-Werror`.** A build that stops at the first warning reports one warning.
  Build with `-Wno-error` (or without `-Werror`), and let OpenCanary collect, prioritize and count all of them.
- **Third party headers are system headers.** Include them with `-isystem` (CMake: `SYSTEM` on
  `target_include_directories`, or an imported target), or `/external:I` with `/external:W0` for MSVC. Their warnings
  are not yours to fix, and a `#pragma` that suppresses them in your own code is reported as
  [suppressed-warning](rules.md#suppressed-warning).

A good start for GCC and Clang:

| Flags | Why |
|-------|-----|
| `-Wall -Wextra` | the common set; despite its name `-Wall` is far from all |
| `-Wconversion -Wsign-conversion` | implicit conversions that lose data or change the sign |
| `-Wshadow` | a variable that hides another one |
| `-Wnon-virtual-dtor -Woverloaded-virtual -Wsuggest-override` | class hierarchies: a missing virtual destructor, a function that hides instead of overrides |
| `-Wnull-dereference -Wcast-align -Wformat=2 -Wvla` | null pointers on a code path, misaligned access, unsafe format strings, variable length arrays |
| `-Wduplicated-cond -Wduplicated-branches -Wlogical-op` (GCC) | copy/paste errors in conditions |
| `-Weverything` with a list of `-Wno-...` (Clang, quality report only) | everything Clang knows; switch off the warnings that the team decided not to follow (`-Wno-c++98-compat`, `-Wno-padded`, ...) instead of only switching on the ones it knows |

For MSVC: `/W4 /permissive-`, and the off-by-default warnings that point at likely bugs: `/w14263 /w14264 /w14265`
(a function that hides a virtual function, a missing virtual destructor). `/permissive-` makes MSVC follow the
standard for two-phase name lookup and other rules that GCC and Clang already enforce, so code that only compiles with
MSVC is found in the MSVC build.

The default `rules/priorities.txt` gives the warnings of all three compilers a priority; adjust it to the team.

## Sanitizers

A sanitizer adds checks to the program and reports a problem when the tests run into it, with the stack trace of the
place it happened. It finds what no warning can: the actual out of bounds access, the actual data race.

| Sanitizer | Finds | Combine with |
|-----------|-------|--------------|
| AddressSanitizer (`-fsanitize=address`) | out of bounds access, use after free, double free, leaks (LeakSanitizer), global variables with an ODR violation (`ASAN_OPTIONS=detect_odr_violation=2`, the default) | UBSan |
| UndefinedBehaviorSanitizer (`-fsanitize=undefined`) | signed overflow, invalid shifts, misaligned access, invalid enum and bool values, null references | ASan, or alone; cheap enough for the normal release build |
| ThreadSanitizer (`-fsanitize=thread`) | data races, lock order inversions | nothing: a separate build |
| MemorySanitizer (`-fsanitize=memory`, Clang only) | reads of uninitialized memory | nothing; every library has to be built with it, including the standard library, so it is the most work |

Recommendations:

- Run the tests under ASan + UBSan and under TSan every night, in a debug and in a release build. The optimizer
  changes which bugs are visible: a release build inlines, reorders and removes code, and that is where undefined
  behavior starts to matter. A debug build keeps the assertions and the debug checks of the standard library.
- Add `-fno-omit-frame-pointer` (and `-g`) for useful stack traces, and `-fno-sanitize-recover=undefined` once the
  code is clean, so UBSan stops the test at the first problem instead of only printing it.
- UBSan in the normal release build costs little and catches problems in every test run.
- A sanitizer only finds what the tests run, so its value grows with the test coverage.

## Build configurations

A different configuration compiles different code, and the compiler sees it differently:

- **Release** (`-O2`) makes the flow analysis warnings possible: `-Wmaybe-uninitialized`, `-Wnull-dereference`,
  `-Warray-bounds` and `-Wstringop-overflow` need the optimizer to follow the code, and report little or nothing at
  `-O0`.
- **Debug** compiles the code between `#ifndef NDEBUG` and makes `assert` work. Add `-D_GLIBCXX_ASSERTIONS` (libstdc++)
  or `_LIBCPP_HARDENING_MODE` (libc++) for bounds checks on `std::vector::operator[]` and other standard library
  preconditions, at little cost. MSVC's debug runtime has these checks already.
- **Unity builds** (`CMAKE_UNITY_BUILD`) put several source files in one translation unit, so two functions with the
  same name in an anonymous namespace become a compile error, and a `using namespace` in one file can make a name in
  the next one ambiguous. A periodic unity
  build finds these, and so a lack of isolation between source files.
- **Header checks** compile every public header on its own, which finds headers that do not include what they use.
- **The shipped configuration** (often release with LTO) is the one that matters most: build it every night, and run
  the tests on it, not only on the configurations that are convenient for developers.

## More than one compiler

Each compiler has its own warnings, its own analysis and its own standard library, so a second compiler finds
problems that the first one never reports:

- **Other warnings.** Clang has `-Wshadow-field`, `-Wunreachable-code`, `-Wcomma`, `-Wthread-safety` and
  `-Weverything`; GCC has `-Wduplicated-branches`, `-Wlogical-op`, and flow analysis based warnings that
  follow the code through the optimizer (`-Wmaybe-uninitialized`, `-Wstringop-overflow`). MSVC warns about other
  conversions and hidden virtual functions.
- **Other standard libraries.** libstdc++, libc++ and the MSVC STL include different headers from their own headers.
  Code that uses `std::string` without `#include <string>` compiles with one and fails with another. Building with each of
  them keeps the includes complete.
- **Stricter or different parsing.** Code that one compiler accepts as an extension (variable length arrays,
  `__attribute__`, missing `typename`, MSVC's non standard name lookup without `/permissive-`) fails on another one, so
  the code stays standard C++.
- **Other undefined behavior.** Code with undefined behavior often works by accident with one compiler and fails with
  another one, which optimizes differently. A test that fails with only one compiler is a hint to look for it.
- **Tooling.** clang-tidy, the Clang static analyzer and MemorySanitizer need the code to compile with Clang.

The second compiler does not have to produce the shipped product: a Clang build on every push (or every night) gives
most of the benefit.

## LTO builds

With link-time optimization (`-flto`, CMake: `CMAKE_INTERPROCEDURAL_OPTIMIZATION`) the compiler writes its
intermediate representation into the object files and optimizes again when the program is linked. At that point it
sees the whole program instead of one translation unit, and that gives it information that no other build has:

- **ODR violations.** GCC's `-Wodr` (on by default with `-flto`) compares the definitions of the same type in all
  translation units and reports a type that has two different definitions, such as a class built on a library that
  is `std::variant` in one part of the program and its own implementation in another (see
  [inconsistent-compile-flags](rules.md#inconsistent-compile-flags)). No other build reports this: the compiler
  sees one translation unit, and the linker only compares names.
- **Mismatched declarations.** `-Wlto-type-mismatch` (also on by default) reports a global declared with different
  types in different files, such as `extern int count;` in one and `long count;` in the other.
- **Warnings across files.** Inlining across translation units lets the flow analysis warnings (`-Wmaybe-uninitialized`,
  `-Warray-bounds`, `-Wstringop-overflow`, `-Wnull-dereference`, `-Wfree-nonheap-object`) follow a value into a
  function in another file, so they find bugs that are invisible when each file is compiled alone.
- **Undefined behavior that only shows when inlined.** Code that is only wrong in combination with its caller
  in another file behaves differently once it is inlined; the tests on an LTO build (with UBSan) catch it.

These warnings appear when the program is linked, so capture the output of the link step too (`cmake --build ... -- -v`
captures everything) and pipe the log through `parse_gcc.py` like the other builds. Use `-flto=auto` to run the
link-time optimization on every core.

Limits: only code that was compiled with `-flto` takes part. A library that arrives prebuilt (a system package, a
Conan binary) is not checked. Clang's LTO does not have `-Wodr`. LTO needs more memory and time, which is why it is a
nightly build; ship from it, so the tests run on the code that is shipped.

## Finding ODR violations

An ODR violation (two different definitions of the same type, function or variable in one program) is one of the
hardest bugs to find: the program compiles and links without a warning and then crashes at random places. The
checks, from cheap to thorough:

1. [hardcoded-cxx-standard](rules.md#hardcoded-cxx-standard) (`cpp-issues`): a C++ standard that is fixed in a
   `CMakeLists.txt` of a dependency, the usual cause.
2. [inconsistent-compile-flags](rules.md#inconsistent-compile-flags) (`compile-flags`): every target in the compile
   database that is built with another standard or other ABI relevant flags than the rest.
3. The LTO build with GCC, which reports the violations themselves, see [LTO builds](#lto-builds).
4. AddressSanitizer reports a global variable that is defined in two libraries.
5. For prebuilt libraries: GCC records the language standard and the options of every translation unit in the debug
   information (`DW_AT_producer`, such as `GNU C++14 12.2.0 -mtune=generic -g -O2`). This counts the standards in a
   program and its libraries, built with `-g`; more than one is a reason to look closer:

   ```sh
   readelf --debug-dump=info --dwarf-depth=1 my_program libdependency.so | grep -o 'GNU C++[0-9]*' | sort | uniq -c
   ```

   Clang does not record the standard there, and records its options only with `-grecord-command-line`.
