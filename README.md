# OpenCanary
set of scripts for static analysis of source code and build results

The purpose of this repo is to provide a set of scripts that can be used to build your own build-canary.
A build-canary is a system that gives you early warning when new problems have been introduced. (so code quality _as you define it_ has regressed). Also a (nighly?) report can be generated to provide you and your team guidenance to start improving you code base. The report is a prioritized list (_you define you own team priorities_) of issues to solve.

The process works in a couple of steps that are executed as post-build steps as part of the CI build.

## Gather
- gcc / clang compiler warnings
- gcc / clang commandline warnings
- msvc warnings
- cppcheck issues
- sanitizer (ubsan, tsan, asan, etc) issues 
- clang-tidy
- coverage results
- more?

Parse all warnings/issues into a single comma-separated format (actually | - pipe separated seems to work good, because ; and comma are sometimes used in messages.)

format:
priority | team | component | file | source | rule | category | description | link

* priority - team assigned priority
* team - name of the team responsible
* component - name of the component the issue is associated to 
* file - file + linenumber  "/path/foo:14"
* source - the tools that produced the issue (gcc/coverage, cppcheck/opencanary,ubsan,etc.)
* category - tool specific (ie. PARSE ERROR, COMPILE ERROR, ISSUE)
* rule - optional tools specific fields (warnings Cxxxx, or POR#xxx")
* *wiki* - wiki link to gather typical solving strategies, note: generated from 'rule' 
* description - actual message the was reported
* link - tool specific reference link (for example to an external issue tracker or the source tool web interface)

## Filter
- Pre-filter: optionally remove non-team issue (doing this first prevent unneeded work in following steps) 
- Interest
  - filter out false positives, tooling errors and 3rd party paths
- Valuable
  - filter out what are _not_ errors, but the team should ignore (unmaintained code for example) 
  - assign priorities according to the teams judgement
  - **the result of this yields a prioritized work-list for the team**
- Regression
  - include all catagories that should currently have zero issues
  - exclude all projects that do not comply yet
  - **any issues that pass this filter fail the build**


tricks for finding high-priority issues
- three (or more) consecutive lines with the same error
- the same class name mentioned more then three times
- assert(pointer); to detect null-pointers will prevent crash and cause a hanging process?

## Failure is an option

- if any issues remain after the regression filter, fail the build.

## Report

- send out nightly emails with a report showing the prioritized list of issues

