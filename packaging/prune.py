"""Verschlankt das AppDir: alles raus, was BuB3TAGMUSIC nicht braucht.

Aufruf (mit dem Python im AppDir): python3 prune.py APPDIR

Qt-Bibliotheken werden nicht geraten: Es bleiben genau die, die von den
behaltenen PySide6-Modulen und Qt-Plugins tatsächlich gebraucht werden (ldd).
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys

APPDIR = os.path.abspath(sys.argv[1])
PYROOT = os.path.join(APPDIR, "usr", "python")
LIB = glob.glob(os.path.join(PYROOT, "lib", "python3.*"))[0]
SITE = os.path.join(LIB, "site-packages")
PYSIDE = os.path.join(SITE, "PySide6")
QT = os.path.join(PYSIDE, "Qt")

freed = 0


def size(path: str) -> int:
    if os.path.isfile(path) or os.path.islink(path):
        return os.lstat(path).st_size
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def rm(path: str) -> None:
    global freed
    for p in glob.glob(path):
        freed += size(p)
        if os.path.isdir(p) and not os.path.islink(p):
            shutil.rmtree(p)
        else:
            os.remove(p)


# --- Python ----------------------------------------------------------------
for p in ("include", "share", "lib/pkgconfig", "lib/itcl*", "lib/tcl*", "lib/tk*", "lib/thread*",
          "lib/libtcl*", "lib/libtk*", "bin/idle*", "bin/pydoc*", "bin/pip*", "bin/2to3*",
          "bin/python3*-config",
          # das python-Programm ist statisch gebaut; libpython braucht nur, wer Python einbettet
          "lib/libpython3*.so*"):
    rm(os.path.join(PYROOT, p))
for p in ("test", "idlelib", "tkinter", "turtledemo", "ensurepip", "lib2to3", "pydoc_data",
          "config-3.*", "lib-dynload/_tkinter*", "lib-dynload/_test*", "lib-dynload/xxlimited*",
          "unittest/test", "sqlite3/test", "ctypes/test", "distutils/tests"):
    rm(os.path.join(LIB, p))
rm(os.path.join(SITE, "pip"))
rm(os.path.join(SITE, "pip-*"))

# --- PySide6: nur die Python-Module, die wir brauchen ------------------------
KEEP_MODULES = {"QtCore", "QtGui", "QtWidgets", "QtSvg", "QtSvgWidgets", "QtNetwork", "QtDBus"}
for so in glob.glob(os.path.join(PYSIDE, "Qt*.abi3.so")) + glob.glob(os.path.join(PYSIDE, "Qt*.so")):
    mod = os.path.basename(so).split(".")[0]
    if mod not in KEEP_MODULES:
        rm(so)
        rm(os.path.join(PYSIDE, mod + ".pyi"))
rm(os.path.join(PYSIDE, "*.pyi"))
for p in ("include", "typesystems", "glue", "scripts", "examples", "doc", "qml", "Qt/qml",
          "Qt/libexec", "Qt/metatypes", "Qt/mkspecs", "Qt/modules", "Qt/resources"):
    rm(os.path.join(PYSIDE, p))
# Programme wie designer, uic, rcc, lupdate … im PySide6-Ordner
for f in os.listdir(PYSIDE):
    p = os.path.join(PYSIDE, f)
    if os.path.isfile(p) and os.access(p, os.X_OK) and not f.endswith(".so") and ".so." not in f:
        rm(p)

# Übersetzungen: nur Deutsch
for f in glob.glob(os.path.join(QT, "translations", "*")):
    name = os.path.basename(f)
    if not (name.endswith("_de.qm") and name.startswith(("qtbase", "qt_"))):
        rm(f)

# Plugins: nur, was eine Desktop-Oberfläche braucht
KEEP_PLUGINS = {
    "platforms": {"libqxcb.so", "libqwayland.so", "libqwayland-generic.so", "libqwayland-egl.so",
                  "libqoffscreen.so", "libqminimal.so"},
    # ohne virtuelle Tastatur – die zieht QML/Quick (≈20 MB) mit
    "platforminputcontexts": {"libcomposeplatforminputcontextplugin.so", "libibusplatforminputcontextplugin.so"},
    "imageformats": None, "iconengines": None,
    "platformthemes": None, "xcbglintegrations": None, "generic": None,
    "wayland-decoration-client": None, "wayland-graphics-integration-client": None,
    "wayland-shell-integration": None,
}
plugdir = os.path.join(QT, "plugins")
for d in os.listdir(plugdir):
    full = os.path.join(plugdir, d)
    if d not in KEEP_PLUGINS:
        rm(full)
    elif KEEP_PLUGINS[d] is not None:
        for f in os.listdir(full):
            if f not in KEEP_PLUGINS[d]:
                rm(os.path.join(full, f))

# Qt-Bibliotheken: nur die tatsächlich benötigten (über ldd ermittelt)
qtlib = os.path.join(QT, "lib")
roots = glob.glob(os.path.join(PYSIDE, "*.so")) + glob.glob(os.path.join(plugdir, "**", "*.so"), recursive=True)
roots += glob.glob(os.path.join(SITE, "shiboken6", "*.so*"))
env = dict(os.environ, LD_LIBRARY_PATH=qtlib + ":" + os.path.join(SITE, "shiboken6"))
needed: set[str] = set()
todo = list(roots)
seen: set[str] = set()
while todo:
    f = todo.pop()
    if f in seen:
        continue
    seen.add(f)
    out = subprocess.run(["ldd", f], capture_output=True, text=True, env=env).stdout
    for line in out.splitlines():
        if "=>" in line:
            target = line.split("=>")[1].strip().split(" (")[0]
            if target.startswith(qtlib):
                name = os.path.basename(target)
                if name not in needed:
                    needed.add(name)
                    todo.append(target)
for f in os.listdir(qtlib):
    real = f.split(".so")[0]
    if not any(n.split(".so")[0] == real for n in needed):
        rm(os.path.join(qtlib, f))

# Caches
for d in glob.glob(os.path.join(APPDIR, "**", "__pycache__"), recursive=True):
    rm(d)

print(f"Verschlankt: {freed / 1e6:.0f} MB entfernt, {len(needed)} Qt-Bibliotheken behalten")
