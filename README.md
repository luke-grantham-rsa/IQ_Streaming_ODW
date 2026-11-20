Run GUI (recommended on this machine)
Open a fresh Command Prompt, go to the repo folder, and run:

>> cd C:\Users\grantham\Documents\IQ_Streaming_ODW
>> run_gui.bat

Do NOT run xdw\Scripts\activate first. The xdw virtual environment is broken here:
xdw\Scripts\python.exe points to a Python 3.12 install that is not present, so
"python" fails with "No Python at ...Python312\python.exe". If you already activated it,
run "deactivate" (run_gui.bat also ignores an active venv).

run_gui.bat uses the system Python (py -3) and restores the library folders
(rsxdwstreaming, bitstring, pyqtgraph, colorama) from git into
%LOCALAPPDATA%\IQ_Streaming_ODW\lib the first time, which takes about 30 seconds.
Later runs reuse that copy. It needs git and a system Python with PyQt6 and numpy.
If the library files ever look wrong, delete %LOCALAPPDATA%\IQ_Streaming_ODW\lib and
run run_gui.bat again.

---

Original steps (only work if the xdw virtual environment is healthy)

Start virtual environment
>> xdw\Scripts\activate

First time? 
install rsxdwstreaming 
>> python -m pip install rsxdwstreaming-3.0.2-py3-none-any.whl

Run GUI
>> python Test_ODW.py

Done?
>> deactivate
