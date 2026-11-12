"""Import a COPY of the application in-process, with fresh state (docs/split-plan.md 1.3).

    from harness.appcopy import copy_app
    from harness.appload import load_app
    copy_app(dest, PROJECT)
    app = load_app(dest)
    P = app.P                      # the module that holds the code ("player" on the single-file layout, "cpl.legacy" while the split is under way)
    app.modules                    # {"player": <module>}  or  {"cpl.legacy": <module>, ...}
    app.unload()                   # in tearDown: purge the modules and the sys.path entry

Every call starts from a clean slate: all `cpl*` entries are removed from sys.modules first (otherwise a second test would see the
state of the first one), and the single-file layout is executed as a new module object each time, as the tests did before.
`sys.argv` is set to ["player.py"] while importing (the helper entry points look at it).
Works on both layouts: today's single player.py, and player.py + cpl/ (the module list then holds cpl.legacy, later the real modules).
"""
import importlib, importlib.util, sys
from pathlib import Path
from types import SimpleNamespace


def purge(prefix="cpl"):
    for name in [n for n in sys.modules if n == prefix or n.startswith(prefix + ".")]:
        del sys.modules[name]


def load_app(dest, argv=("player.py",)):
    dest = Path(dest).resolve()
    purge()
    sys.argv = list(argv)
    if (dest / "cpl" / "__init__.py").is_file():
        sys.path.insert(0, str(dest))
        importlib.invalidate_caches()
        main = importlib.import_module("cpl.legacy")           # P1-P8: everything not yet moved lives here; P9 replaces this with cpl.app
        modules = {n: m for n, m in sys.modules.items() if n == "cpl" or n.startswith("cpl.")}
        added = str(dest)
    else:
        spec = importlib.util.spec_from_file_location("player_t_%d" % id(dest), dest / "player.py")
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        modules = {"player": main}
        added = None

    def unload():
        purge()
        if added and added in sys.path:
            sys.path.remove(added)

    def mod(name):
        """the module `cpl.<name>` of this copy (imported on demand; same module objects as in `modules`)"""
        return importlib.import_module("cpl." + name)

    return SimpleNamespace(P=main, modules=modules, dest=dest, unload=unload, mod=mod)
