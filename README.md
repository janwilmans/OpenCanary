# OpenCanary
A set of scripts for aggregation, analysis and reporting of build and static analysis results.
Its purpose is to give you a failing CI build if new issues are introduced and a team specific prioritized list of issue to work on.

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

Parse all warnings/issues into a single comma-separated format. Actually | - pipe separated seems to work good, because semicolons (;) and comma (,) are sometimes used in messages.

format:
`priority | team | component | fileref | source | category | rule | description | [n]{url}[n]{url}... `

where columns category -> rule -> description are in ordered from coarse to fine
and the lines are ordered in order of priority first, and second in order of file(name)
that way issues are clustered per-file as good as possible.

* priority - team assigned priority
* team - name of the team responsible
* component - name of the component the issue is associated to 
* fileref - file + linenumber "/path/foo:14" with optional columnnumber "/path/foo:14:35"
* source - the tools that produced the issue (gcc/coverage, cppcheck/opencanary,ubsan,etc.)
* category - tool specific (ie. PARSE ERROR, COMPILE ERROR, ISSUE)
* rule - optional tools specific fields (warnings Cxxxx, or POR#xxx")
* *wiki* - wiki link to gather typical solving strategies, note: generated from 'rule' 
* description - actual message the was reported
* link - tool specific links where [n] refers back to a 0-indexed column (so 0=priority, 1=team etc.)

## category and rule 
Its important the rule is specific enough to advice can be offered on how to handle a particular issue. This is because the rule is what makes links to the Wiki pages unique. Conversely the category must be broad enough to group silimar issues together, but typically only issues with the same priority. However, the latter is not strictly required, specfic rules _can_ have a different priority from their category. 

## links
The links are intended to be combined in the report in such a way that when the value in 'priority' is clicked, it is linking to the url in [0]{url} etc. This way any tool can add custom links into the report.

## Transformations 
- Pre-filter: optional step; remove non-team issues (doing this first prevent unneeded work in following steps) 
- Interest
  - filter out false positives, tooling errors and 3rd party paths
- Valuable
  - filter out what are _not_ errors, but the team should ignore (unmaintained code for example) 
  - assign priorities according to the teams judgement
  - **the result of this yields a prioritized work-list for the team**
- Regression
   - exclude all projects or categories of issues that are not at zero yet
  - **any issues that pass this filter fail the build**


tricks for finding high-priority issues
- three (or more) consecutive lines with the same error
- the same class name mentioned more then three times
- assert(pointer); to detect null-pointers will prevent crash and cause a hang that delays CI tests

## Failure is an option

- if any issues remain after the regression filter, fail the build.

## Report

- send out nightly emails with a report showing the prioritized list of issues

# References

- https://github.com/mherrmann/gitignore_parser

