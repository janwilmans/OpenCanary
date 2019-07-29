set dir=%~dp0

type %~dpnx1 | %dir%filter_thirdparty.py /msvc | %dir%parse_msvc.py env.txt > issues.txt
%dir%oc_cpp_issues.py %dir%.. 2>nul | %dir%filter_thirdparty.py /msvc >> issues.txt
%dir%cppcheck.py env.txt %dir%..\components %dir%..\.. | %dir%normalize_paths.py >> issues.txt
type issues.txt | %dir%sortby.py | %dir%create_report.py env.txt > report.html

if [%CI_SERVER%] == [] (
    start report.html
) else (
    %dir%send_email.py report.html issues.txt
)
