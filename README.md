## Run the GUI

From a fresh Command Prompt, go to the cloned repo folder and run the launcher:

```
cd <path-to-cloned-repo>
run_gui.bat
```

That is the only step after cloning the repo. `run_gui.bat` uses the system Python
(`py -3`) and the libraries already in `xdw\Lib\site-packages`.

Needs, once per machine:

```
py -3 -m pip install PyQt6 numpy
```

There is no virtual environment to activate. `xdw\Lib\site-packages` only holds the
bundled libraries, and `run_gui.bat` points Python at that folder.

If those library files are empty, `run_gui.bat` restores them from git before starting.
A newly cloned copy already has them, so it starts directly.
