Generic c++ issues:
-	using namespace in header files!!!
-	custom make_unique-like constructs that pre-date C++11's std::make_unique

Post-build related:
-	collect compiler warnings from build-logfiles from projects that don't have 'set warnings as errors' (very good for projects that 'set warnings as errors' off and cannot be turned on right now due to the amount of work involved)
-	collect warnings from installer-build 
-	collect warnings from smoketest-installation

Visual studio project related:
-	solutions containing non-existing projects
-	projects containing non-existing files *.h or *.txt etc.
-	project references that use 'link referenced library' for non-static libraries
-	including files (.h and .cpp) from a different projects (../ backreferences)
-	projects that dont have Warning level 4 and 'set warnings as errors'
-	<DisableSpecificWarnings>

COM related:
-	guid uniqueness over IDLs
-	ignore "derives publicly from class 'CComObjectRootEx' "
-	ignore "derives publicly from class [empty] " as this is a Tiobe bug

tricks for finding high-prio issues (indicators for 'easy to solve in little time' kind of issues)
- three (or more) consecutive lines with the same error
- the same class name mentioned more then three times
- assert(pointer); to detect null-pointers will prevent crash and cause a hanging process?


