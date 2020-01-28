type vs2019_build.log | parse_msvc.py env.txt | apply_team_priorities.py | apply_low_hanging_fruit.py | sortby.py > issues.txt
type issues.txt | create_report.py | apply_environment.py > report.html

or 

oc_cpp_issues.py ~/project_repo | apply_team_priorities.py | apply_low_hanging_fruit.py | sortby.py > issues.txt
type issues.txt | create_report.py | apply_environment.py > open_canary_report.html

