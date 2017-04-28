@echo off
cd %~dp0
C:\pypy2\pypy.exe ticstool.py convert tem_platform\Configuration -i tem_platform\tem_tics.txt > all_issues.txt

:: ticstool.py convert tem_platform\Configuration -i tem_platform\tem_tics.txt > all_issues.txt
:: ticstool.py convert motion_main\Configuration -i motion_main\motion_tics.txt >> all_issues.txt


:: filter by team 'MOTION'
:: ticstool.py filter -t MOTION -p motion2 -i tem_platform\tem_tics_out.txt > motion_main\issues.txt

:: filter by profile 'motion2' and my profile 'zerotolerance'
:: ticstool.py filter -p motion2 -p zerotolerance -i motion_main\motion_tics_out.txt >> motion_main\issues.txt

