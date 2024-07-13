#!/bin/bash
# this script finds unique words in source code
# it can be used to discover dead code and/or unused defines

echo "Collecting files... *.h, *.cc, *.c"
cat `find . -name "*.h" -o -name "*.cc" -o -name "*.c"` > /tmp/bigfile

# build a sorted list of all words with 4 or more letters, \w matches [A-Za-z0-9_]
grep -o -E '\w{4,}' /tmp/bigfile | sort > /tmp/wordfile

LINES=`cat /tmp/bigfile | wc -l`
echo "Found $LINES source lines."

# keep only the words that occur once
cat /tmp/wordfile | uniq -u > /tmp/uniquewords

WORDS=`cat /tmp/uniquewords | wc -l`
echo "Found $WORDS unique words matching pattern '[A-Za-z0-9_]{4,}')."
echo "Find unique defines, this can take a few minutes..."

# xargs -I implies -n 1 so we can leave it out (use one argument per command line)
# search for unique words in a specfic context (variable declaration)
cat /tmp/uniquewords | xargs -I {} grep -o '#define {}\s' /tmp/bigfile > /tmp/uniquevariables
cat /tmp/uniquevariables

