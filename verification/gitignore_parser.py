# this files was created from creatively reshuffling
# https://github.com/snark/ignorance/blob/master/ignorance/git.py
# and
# https://github.com/snark/ignorance/blob/master/ignorance/utils.py
# at hash
# https://github.com/snark/ignorance/tree/c9ec7881165e309c6d18cf00d8d62c9b80ea1168

# -*- coding: utf-8 -*-
import sys

# actually we should require 3.7 (https://docs.python.org/3/library/re.html
# Changed in version 3.7: Only characters that can have special meaning in a regular expression are escaped. As a result, '!', '"', '%', "'", ',', '/', ':', ';', '<', '=', '>', '@', and "`" are no longer escaped.

if sys.hexversion < 0x03040000:
    sys.exit("Python 3.4 or newer is required to run this program, you are running " + ".".join(map(str, sys.version_info)))

import collections
import itertools
import os
import re

from os import walk as _walk

try:
    # pathlib is in python stdlib in python 3.5+
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

os_sep = os.sep

def ancestor_vcs_directory(filepath, dirname='.git'):
    """
    Find the closet parent directory containing a magic VCS directory.
    """
    orig_path = filepath
    filepath = os.path.expanduser(filepath)
    if not os.path.exists(filepath):
        raise ValueError("{} does not exist".format(orig_path))
    # Edge case
    if os.path.isdir(filepath) and os.path.split(filepath)[1] == '.git':
        return filepath
    path = Path(os.path.abspath(filepath))
    if path.is_file():
        path = path.parent
    parents = list(path.parents)
    parents.reverse()
    found = None
    current_dir = path
    while not found and parents:
        test = current_dir / dirname
        if test.exists() and test.is_dir():
            found = str(current_dir)
        else:
            current_dir = parents.pop()
    return found


def walk(directory, onerror=None, filenames=['.gitignore'],
         overrides=None, ignore_completely=None):
    """
    Generate the file names in a directory tree by walking the tree
    top-down, while obeying the rules of .gitignore. Links will not
    be followed.
    """
    starting_directory = Path(os.path.abspath(directory))

    if not overrides:
        overrides = []
    overrides = [rule_from_pattern(
        p, str(starting_directory), source=('manual override', None)
    ) for p in overrides]

    # Git is incapable of adding .git files to stage -- by default walk()
    # will skip it entirely in a *non-overrideable* manner.
    if ignore_completely is None:
        ignore_completely = ['.git']
    elif not ignore_completely:
        ignore_completely = []
    ignore_completely = [
        rule_from_pattern(p, source=('application-level override', None))
        for p in ignore_completely
    ]
    if [rule for rule in ignore_completely if rule.negation]:
        raise ValueError('negation rules are not allowed in the '
                         'ignore completely rules')

    # Rule list will be a dict, keyed by directory with each value a
    # possibly-empty list of IgnoreRules
    rule_list = {}
    while True:
        for root, dirs, files in _walk(directory, onerror=onerror):
            rules = []
            for filename in filenames:
                if filename in files:
                    rules.extend(rules_from_file(filename, os.path.abspath(root)))
            current_dir = Path(os.path.abspath(root))
            rel_path = str(current_dir.relative_to(starting_directory))
            rule_list[rel_path] = rules
            # Now, make a list of rules, working our way back to the
            # base directory.
            applicable_rules = [rule_list[rel_path]]
            if root != directory:
                for p in Path(root).parents:
                    rel_parent = str(p.relative_to(starting_directory))
                    applicable_rules.append(rule_list[rel_parent])
                    if p not in starting_directory.parents:
                        break
            applicable_rules.append(rule_list['.'])
            # Our rules are actually ordered from the base down
            applicable_rules = applicable_rules[::-1]
            flat_list = list(
                itertools.chain.from_iterable(applicable_rules)
            )
            # overrides and ignore-completely patterns are always applicable
            flat_list.extend(overrides)
            flat_list.extend(ignore_completely)
            ignore = []
            for d in dirs:
                included = True
                path = os.path.abspath(os.path.join(root, d))
                for rule in flat_list:
                    if included != rule.negation:
                        if rule.match(path):
                            included = not included
                if not included:
                    ignore.append(d)
            dirs[:] = [d for d in dirs if d not in ignore]
            ignore = []
            for f in files:
                included = True
                path = os.path.join(root, f)
                for rule in flat_list:
                    if rule.directory_only:
                        continue
                    if included != rule.negation:
                        if rule.match(os.path.abspath(path)):
                            included = not included
                if not included:
                    ignore.append(f)
            files[:] = [f for f in files if f not in ignore]
            yield root, dirs, files
        return


def rules_from_file(filename, base_path):
    return_rules = []
    full_path = os.path.join(base_path, filename)
    with open(full_path) as ignore_file:
        counter = 0
        for line in ignore_file:
            counter += 1
            line = line.rstrip('\n')
            rule = rule_from_pattern(line, os.path.abspath(base_path),
                                     source=(full_path, counter))
            if rule:
                return_rules.append(rule)
    return return_rules


def rule_from_pattern(pattern, base_path=None, source=None):
    """
    Take a .gitignore match pattern, such as "*.py[cod]" or "**/*.bak",
    and return an IgnoreRule suitable for matching against files and
    directories. Patterns which do not match files, such as comments
    and blank lines, will return None.
    Because git allows for nested .gitignore files, a base_path value
    is required for correct behavior. The base path should be absolute.
    """
    if base_path and base_path != os.path.abspath(base_path):
        raise ValueError('base_path must be absolute')
    # Store the exact pattern for our repr and string functions
    orig_pattern = pattern
    # Early returns follow
    # Discard comments and seperators
    if pattern.strip() == '' or pattern[0] == '#':
        return
    # Discard anything with more than two consecutive asterisks
    if pattern.find('***') > -1:
        return
    # Strip leading bang before examining double asterisks
    if pattern[0] == '!':
        negation = True
        pattern = pattern[1:]
    else:
        negation = False
    # Discard anything with invalid double-asterisks -- they can appear
    # at the start or the end, or be surrounded by slashes
    for m in re.finditer(r'\*\*', pattern):
        start_index = m.start()
        if (start_index != 0 and start_index != len(pattern) - 2 and
                (pattern[start_index - 1] != '/' or
                 pattern[start_index + 2] != '/')):
            return

    # Special-casing '/', which doesn't match any files or directories
    if pattern.rstrip() == '/':
        return

    directory_only = pattern[-1] == '/'
    # A slash is a sign that we're tied to the base_path of our rule
    # set.
    anchored = '/' in pattern[:-1]
    if pattern[0] == '/':
        pattern = pattern[1:]
    if pattern[0] == '*' and pattern[1] == '*':
        pattern = pattern[2:]
        anchored = False
    if pattern[0] == '/':
        pattern = pattern[1:]
    if pattern[-1] == '/':
        pattern = pattern[:-1]
    regex = fnmatch_pathname_to_regex(pattern)
    if anchored:
        regex = ''.join(['^', regex])
    return IgnoreRule(
        pattern=orig_pattern,
        regex=regex,
        negation=negation,
        directory_only=directory_only,
        anchored=anchored,
        base_path=Path(base_path) if base_path else None,
        source=source
    )


whitespace_re = re.compile(r'(\\ )+$')

IGNORE_RULE_FIELDS = [
    'pattern', 'regex',  # Basic values
    'negation', 'directory_only', 'anchored',  # Behavior flags
    'base_path',  # Meaningful for gitignore-style behavior
    'source'  # (file, line) tuple for reporting
]


class IgnoreRule(collections.namedtuple('IgnoreRule_', IGNORE_RULE_FIELDS)):
    # TODO Add source to __str__ or perhaps a method
    def __str__(self):
        return self.pattern

    def __repr__(self):
        return ''.join(['IgnoreRule(\'', self.pattern, '\')'])

    def match(self, abs_path):
        matched = False
        if self.base_path:
            rel_path = str(Path(abs_path).relative_to(self.base_path))
        else:
            rel_path = str(Path(abs_path))
        if rel_path.startswith('./'):
            rel_path = rel_path[2:]

        if re.search(self.regex, rel_path):
            matched = True
        return matched

def escaped_sep():
    if os_sep == "\\":
        return "\\\\"
    return os_sep

# Frustratingly, python's fnmatch doesn't provide the FNM_PATHNAME
# option that .gitignore's behavior depends on.
def fnmatch_pathname_to_regex(pattern):
    """
    Implements fnmatch style-behavior, as though with FNM_PATHNAME flagged;
    the path separator will not match shell-style '*' and '.' wildcards.
    """
    i, n = 0, len(pattern)
    nonsep = ''.join(['[^', escaped_sep(), ']'])
    res = []
    while i < n:
        c = pattern[i]
        i = i + 1
        if c == '*':
            try:
                if pattern[i] == '*':
                    i = i + 1
                    res.append('.*')
                    if pattern[i] == '/':
                        i = i + 1
                        res.append(''.join([escaped_sep(), '?']))
                else:
                    res.append(''.join([nonsep, '*']))
            except IndexError:
                res.append(''.join([nonsep, '*']))
        elif c == '?':
            res.append(nonsep)
        elif c == '/':
            res.append(escaped_sep())
        elif c == '[':
            j = i
            if j < n and pattern[j] == '!':
                j = j + 1
            if j < n and pattern[j] == ']':
                j = j + 1
            while j < n and pattern[j] != ']':
                j = j + 1
            if j >= n:
                res.append('\\[')
            else:
                stuff = pattern[i:j].replace('\\', '\\\\')
                i = j + 1
                if stuff[0] == '!':
                    stuff = ''.join('^', stuff[1:])
                elif stuff[0] == '^':
                    stuff = ''.join('\\' + stuff)
                res.append('[{}]'.format(stuff))
        else:
            res.append(re.escape(c))
    res.append('\Z(?ms)')
    return ''.join(res)
