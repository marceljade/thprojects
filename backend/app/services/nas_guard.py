"""Schreibschutz für den NAS-Basispfad (Invariante 11), technisch erzwungen.

Beim Start werden die schreibenden Dateifunktionen von os, shutil, pathlib und open() so umhüllt, dass jeder
Aufruf mit einem Pfad unterhalb des Basispfads der Projektordner mit NasWriteBlocked abbricht, egal aus welchem
Modul er kommt. Lesen bleibt erlaubt (Ordner finden, öffnen). Alles außerhalb des Basispfads (backend/data,
Exporte) bleibt unberührt. Die Sperre gilt für den ganzen Serverprozess.
"""
from __future__ import annotations

import builtins
import functools
import io
import os
import shutil
from pathlib import Path

_base: str = ""
_installed = False
_WRITE_MODES = set("wax+")


class NasWriteBlocked(PermissionError):
    """Ein Schreibzugriff unterhalb des Basispfads wurde geblockt."""


def set_base(path: str | None) -> None:
    """Basispfad merken, gegen den geprüft wird. Leer = keine Sperre nötig."""
    global _base
    p = (path or "").strip().rstrip("\\/")
    _base = os.path.normcase(os.path.abspath(p)) if p else ""


def base() -> str:
    return _base


def active() -> bool:
    return _installed and bool(_base)


def _norm(p) -> str | None:
    if p is None or isinstance(p, int):      # Dateideskriptoren
        return None
    try:
        s = os.fspath(p)
    except TypeError:
        return None
    if isinstance(s, bytes):
        s = s.decode(errors="ignore")
    return os.path.normcase(os.path.abspath(s))


def under_base(p) -> bool:
    if not _base:
        return False
    n = _norm(p)
    return n is not None and (n == _base or n.startswith(_base + os.sep) or n.startswith(_base + "/"))


def _deny(p) -> None:
    raise NasWriteBlocked(f"Die App schreibt nicht auf dem NAS, der Zugriff wurde geblockt: {os.fspath(p)}. "
                          "Ordner und Dateien dort legst du selbst an.")


def _guard(fn, positions=(0,), names=()):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        for i in positions:
            if i < len(args) and under_base(args[i]):
                _deny(args[i])
        for k in names:
            if k in kwargs and under_base(kwargs[k]):
                _deny(kwargs[k])
        return fn(*args, **kwargs)
    wrapper.__pmth_guarded__ = True  # type: ignore[attr-defined]
    return wrapper


def _guard_open(fn, file_pos=0):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        file = args[file_pos] if len(args) > file_pos else kwargs.get("file", kwargs.get("self"))
        mode = args[file_pos + 1] if len(args) > file_pos + 1 else kwargs.get("mode", "r")
        if isinstance(mode, str) and (_WRITE_MODES & set(mode)) and under_base(file):
            _deny(file)
        return fn(*args, **kwargs)
    wrapper.__pmth_guarded__ = True  # type: ignore[attr-defined]
    return wrapper


class as_user:
    """Nur für Tests: simuliert, dass der Nutzer selbst auf dem NAS arbeitet (Sperre kurz aus)."""

    def __enter__(self):
        global _base
        self._saved = _base
        _base = ""
        return self

    def __exit__(self, *exc):
        global _base
        _base = self._saved
        return False


class as_user:
    """Nur für Tests: simuliert, dass der Nutzer selbst auf dem NAS arbeitet (Sperre kurz aus)."""

    def __enter__(self):
        global _base
        self._saved = _base
        _base = ""
        return self

    def __exit__(self, *exc):
        global _base
        _base = self._saved
        return False


def install() -> None:
    """Einmal je Prozess. Idempotent."""
    global _installed
    if _installed:
        return
    for name, pos in (("mkdir", (0,)), ("makedirs", (0,)), ("rename", (0, 1)), ("renames", (0, 1)), ("replace", (0, 1)),
                      ("remove", (0,)), ("unlink", (0,)), ("rmdir", (0,)), ("removedirs", (0,)), ("truncate", (0,)),
                      ("link", (0, 1)), ("symlink", (0, 1))):
        if hasattr(os, name):
            setattr(os, name, _guard(getattr(os, name), pos, ("path", "src", "dst")))
    for name, pos in (("rmtree", (0,)), ("move", (0, 1)), ("copyfile", (1,)), ("copy", (1,)), ("copy2", (1,)), ("copytree", (1,))):
        setattr(shutil, name, _guard(getattr(shutil, name), pos, ("path", "src", "dst")))
    for name, pos in (("mkdir", (0,)), ("rename", (0, 1)), ("replace", (0, 1)), ("unlink", (0,)), ("rmdir", (0,)),
                      ("touch", (0,)), ("write_text", (0,)), ("write_bytes", (0,))):
        setattr(Path, name, _guard(getattr(Path, name), pos, ("target",)))
    Path.open = _guard_open(Path.open)  # type: ignore[method-assign]
    io.open = _guard_open(io.open)  # type: ignore[assignment]
    builtins.open = io.open  # type: ignore[assignment]
    _installed = True
