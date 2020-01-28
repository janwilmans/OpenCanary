# OpenCanary
A set of scripts for aggregation, analysis and reporting of build and static analysis results.
Its purpose is to give you a failing CI build if new issues are introduced and a team specific prioritized list of issues to work on.

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

Parse all warnings/issues into a single comma-separated format. Actually pipe (|) separated seems to work good, because semicolons (;) and comma (,) are often used in messages and pipe symbols much less. Such a | occur, then its 'escaped' as [[pipe]] instead.

format:
`priority | team | component | fileref | source | category | rule | description | [n]{url}[n]{url}... `

where columns category -> rule -> description are in ordered from coarse to fine
and the lines are ordered in order of priority first and second in order of file(name)
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
Its important the rule is specific enough so advice can be offered on how to handle a particular issue. This is because the rule is what makes links to the Wiki pages unique. Conversely the category must be broad enough to group silimar issues together, but typically only issues with the same priority. However, the latter is not strictly required, specfic rules _can_ have a different priority from their category. 

## links
The links are intended to be combined in the report in such a way that when (as an example) the value in 'priority' is clicked, it is linking to the url in [0]{url} etc. This way any tool can add custom links into the report. This is mostly used to create links from the fileref to the source repository (permalinks) so issues can be viewed easily in full context.

## Possible transformations 

These steps are suggestions, you can design your own process flow, but this order worked well for me:

- Pre-filter: optional step; remove non-team issues (doing this first prevents unneeded work in following steps) 
  - the .opencanaryignore file uses the same fnmatch() syntax that .gitignore uses, currently only oc_cpp_issues.py 
    respects these ignore rules.
- Interest
  - filter out false positives, tooling errors and 3rd party paths
- Valuable
  - filter out what are _not_ errors, but the team should ignore (unmaintained code for example) 
- Prioritize 
  - assign priorities according to the teams judgement
  - override the priorities to promote rules that have very few issues (to solve low hanging fruit first)
  - **the result of this yields a prioritized work-list for the team**
- Generate report
  - transform the issue list into a html report for easy access and/or sending emails 
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

- send out nightly emails with a top-50? report showing the prioritized list of issues

# References

- https://github.com/snark/ignorance (A spec-compliant gitignore parser) provides a .gitignore-aware wrapper around os.walk

