"""Copy the application (player.py plus, when they exist, cpl/ and static/) into a test folder, and fingerprint the whole app tree."""
import hashlib, shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
APP_DIRS = ("cpl", "static")


def copy_app(dest, project=PROJECT):
    """Copy player.py and the cpl/ and static/ folders (if present) from project to dest. Returns dest/player.py."""
    project, dest = Path(project), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(project / "player.py", dest / "player.py")
    for d in APP_DIRS:
        if (project / d).is_dir():
            shutil.copytree(project / d, dest / d, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dest / "player.py"


def app_files(project=PROJECT):
    project = Path(project)
    files = [project / "player.py"]
    for d in APP_DIRS:
        if (project / d).is_dir():
            files += sorted(p for p in (project / d).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    return files


def tree_hash(project=PROJECT):
    """sha256 over the relative names and bytes of every app file, and the number of files and bytes."""
    project = Path(project)
    h, n, size = hashlib.sha256(), 0, 0
    for f in app_files(project):
        try:
            data = f.read_bytes()
        except OSError:
            continue
        h.update(f.relative_to(project).as_posix().encode() + b"\0" + hashlib.sha256(data).digest())
        n, size = n + 1, size + len(data)
    return h.hexdigest(), n, size
