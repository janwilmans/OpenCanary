from __future__ import print_function
import sys, os

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    
def sprint(*args, **kwargs):
    print(*args, file=sys.stdout, **kwargs)
