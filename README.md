Run the GUI
From a fresh Command Prompt:

>> cd <path-to-cloned-repo>
>> run_gui.bat

That is the only step after cloning the repo. run_gui.bat uses the system Python
(py -3) and the libraries already in xdw\Lib\site-packages.

Needs, once per machine:
>> py -3 -m pip install PyQt6 numpy

Do not run xdw\Scripts\activate. That virtual environment's python.exe points to a
Python 3.12 install that is not on this machine, so "python" then fails with
"No Python at ...Python312\python.exe". If a prompt is already activated, run
"deactivate" first. run_gui.bat ignores an active virtual environment.

If the library files in the working tree are empty, run_gui.bat restores them from
git before starting. A newly cloned copy already has them, so it starts directly.
