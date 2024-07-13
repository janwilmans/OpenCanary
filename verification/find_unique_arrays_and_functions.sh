#!/bin/bash
# this script finds unique words in source code
# it can be used to discover dead code and/or unused defines

echo "Collecting files... *.h, *.cc, *.c"
find . -name "*.h" -exec cat {} \; > /tmp/bigfile
find . -name "*.cc" -exec cat {} \; >> /tmp/bigfile
find . -name "*.c" -exec cat {} \; >> /tmp/bigfile
grep -o -E '[a-zA-Z_]{4,}' /tmp/bigfile | sort > /tmp/wordfile

LINES=`cat /tmp/bigfile | wc -l`
echo "Found $LINES source lines."

cat /tmp/wordfile | uniq -u > /tmp/uniquewords

WORDS=`cat /tmp/uniquewords | wc -l`
echo "Found $WORDS unique words (matching pattern '[a-zA-Z_]{4,}')."
echo "Find unique defines, this can take a few minutes..."

# xargs -I implies -n 1 so we can leave it out
echo "Unique Arrays:"
cat /tmp/uniquewords | xargs -I {} -exec grep '\s{}\s*\[' /tmp/bigfile > /tmp/uniquearrays
cat /tmp/uniquearrays
echo ""
echo "Unique Funtions: (can have false positives)"
cat /tmp/uniquewords | xargs -I {} -exec grep '\s{}\s*(' /tmp/bigfile > /tmp/uniquefunctions
cat /tmp/uniquefunctions
