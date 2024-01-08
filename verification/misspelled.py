#!/usr/bin/env python3
""" Searched for common misspelled words
"""

import subprocess
import traceback
import sys

wrong_word_list = [
    'accomodate', 'aquire', 'arguement', 'athiest', 'belive', 'bizzare', 'calender', 'carribean',
    'cemetary', 'cheif', 'collegue', 'collectable', 'columist', 'commitee', 'comitted', 'concensus',
    'definately', 'dilemna', 'dissapoint', 'embarras', 'embarassed', 'enviroment', 'exilerate',
    'facinate', 'florescent', 'foriegn', 'fourty', 'freind', 'goverment', 'greatful',
    'happend', 'harras', 'horderves', 'humourous', 'immediatly', 'independant', 'jewelry',
    'judgement', 'knowlege', 'liesure', 'liason', 'lightening', 'maintanance', 'manuever',
    'medival', 'mementos', 'millenium', 'minature', 'mischevious', 'mispell', 'nausious',
    'neccessary', 'ocassion', 'occured', 'paralel', 'parralel', 'pavilion', 'perseverence',
    'phillipines', 'playwrite', 'privelege', 'publically', 'questionaire', 'recieve', 'recomend',
    'resistence', 'responsability', 'rythm', 'sacreligious', 'seige', 'seperate', 'strenght',
    'succesful', 'successfull', 'sucessful', 'supercede', 'tatoo', 'tendancy', 'threshhold', 'tollerance',
    'truely', 'unecessary', 'unforseen', 'untill', 'vacum', 'viscious', 'visibile', 'weather', 'wether',
    'wich', 'wierd', 'whereever', 'writting', 'yatch', 'zealos'
]


def rip_grep(word):
    command = ['rg', '-on', word]
    print(f"search: {word}")
    # do not check the exit code (rg gives a non-zero exit code if no match is found)
    subprocess.run(command, check=False)


def main():
    for word in wrong_word_list:
        rip_grep(word)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except:
        info = traceback.format_exc()
        eprint(info)
        sys.exit(1)
