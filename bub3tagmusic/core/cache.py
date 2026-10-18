"""SQLite-Zwischenspeicher.

* files:   gelesene Tags je Datei + Änderungsdatum/Größe. Stimmen beide
           noch, wird die Datei beim nächsten Öffnen nicht neu gelesen.
* folders: Bearbeitungs-Status der Ordner (fertig / offen).
* fingerprints: Audio-Fingerabdrücke (Phase 4: AcoustID, Duplikate) – die
           Berechnung dauert, deshalb wird jeder Abdruck gemerkt.
* Weitere Tabellen für spätere Phasen (z. B. Online-Antworten) werden
  über user_version migriert.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA_VERSION = 2

FOLDER_OPEN = 0
FOLDER_DONE = 1


class Cache:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._local = threading.local()
        self._migrate()

    # ------------------------------------------------------------------
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def _migrate(self) -> None:
        c = self._conn()
        version = c.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS files (
                    path  TEXT PRIMARY KEY,
                    mtime INTEGER NOT NULL,
                    size  INTEGER NOT NULL,
                    data  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS folders (
                    path    TEXT PRIMARY KEY,
                    status  INTEGER NOT NULL DEFAULT 0,
                    updated REAL
                );
                """
            )
        if version < 2:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS fingerprints (
                    path     TEXT PRIMARY KEY,
                    mtime    INTEGER NOT NULL,
                    size     INTEGER NOT NULL,
                    duration REAL NOT NULL,
                    fp       BLOB NOT NULL
                );
                """
            )
        # Hier kommen spätere Migrationen hin (if version < 3: ...)
        c.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        c.commit()

    # --- Dateien ---------------------------------------------------------
    def get_many(self, stats: dict[str, tuple[int, int]]) -> dict[str, dict]:
        """stats: {pfad: (mtime_ns, size)} → nur passende (aktuelle) Einträge."""
        out: dict[str, dict] = {}
        paths = list(stats)
        c = self._conn()
        for i in range(0, len(paths), 500):
            chunk = paths[i:i + 500]
            q = "SELECT path, mtime, size, data FROM files WHERE path IN (%s)" % ",".join("?" * len(chunk))
            for path, mtime, size, data in c.execute(q, chunk):
                if stats.get(path) == (mtime, size):
                    try:
                        out[path] = json.loads(data)
                    except ValueError:
                        pass
        return out

    def put_many(self, records: list[dict]) -> None:
        rows = [
            (r["path"], r["mtime"], r["size"], json.dumps(r, ensure_ascii=False))
            for r in records if not r.get("error") and r.get("mtime")
        ]
        if not rows:
            return
        c = self._conn()
        c.executemany("INSERT OR REPLACE INTO files(path, mtime, size, data) VALUES (?,?,?,?)", rows)
        c.commit()

    def rename_paths(self, pairs: list[tuple[str, str]]) -> None:
        """Nach dem Umbenennen: Einträge auf den neuen Pfad umziehen."""
        c = self._conn()
        for old, new in pairs:
            c.execute("DELETE FROM fingerprints WHERE path=?", (new,))
            c.execute("UPDATE fingerprints SET path=? WHERE path=?", (new, old))
            row = c.execute("SELECT mtime, size, data FROM files WHERE path=?", (old,)).fetchone()
            c.execute("DELETE FROM files WHERE path=?", (old,))
            if row is None:
                continue
            try:
                data = json.loads(row[2])
            except ValueError:
                continue
            data["path"] = new
            c.execute("INSERT OR REPLACE INTO files(path, mtime, size, data) VALUES (?,?,?,?)",
                      (new, row[0], row[1], json.dumps(data, ensure_ascii=False)))
        c.commit()

    def rename_folder(self, old: str, new: str) -> None:
        """Ordner umbenannt: alle Dateien darunter und den Fertig-Status mitnehmen."""
        old, new = old.rstrip("/"), new.rstrip("/")
        c = self._conn()
        like = old.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "/%"
        rows = c.execute("SELECT path, mtime, size, data FROM files WHERE path LIKE ? ESCAPE '\\'",
                         (like,)).fetchall()
        for path, mtime, size, data in rows:
            target = new + path[len(old):]
            try:
                d = json.loads(data)
                d["path"] = target
                data = json.dumps(d, ensure_ascii=False)
            except ValueError:
                pass
            c.execute("DELETE FROM files WHERE path=?", (path,))
            c.execute("INSERT OR REPLACE INTO files(path, mtime, size, data) VALUES (?,?,?,?)",
                      (target, mtime, size, data))
        c.execute("UPDATE OR REPLACE fingerprints SET path=? || substr(path, ?) WHERE path LIKE ? ESCAPE '\\'",
                  (new, len(old) + 1, like))
        frows = c.execute("SELECT path, status, updated FROM folders WHERE path=? OR path LIKE ? ESCAPE '\\'",
                          (old, like)).fetchall()
        for path, status, updated in frows:
            c.execute("DELETE FROM folders WHERE path=?", (path,))
            c.execute("INSERT OR REPLACE INTO folders(path, status, updated) VALUES (?,?,?)",
                      (new + path[len(old):], status, updated))
        c.commit()

    def forget(self, paths: list[str]) -> None:
        c = self._conn()
        c.executemany("DELETE FROM files WHERE path=?", [(p,) for p in paths])
        c.commit()

    # --- Fingerabdrücke (Phase 4) ------------------------------------------
    def get_fingerprints(self, stats: dict[str, tuple[int, int]]) -> dict[str, tuple[float, bytes]]:
        out: dict[str, tuple[float, bytes]] = {}
        paths = list(stats)
        c = self._conn()
        for i in range(0, len(paths), 500):
            chunk = paths[i:i + 500]
            q = "SELECT path, mtime, size, duration, fp FROM fingerprints WHERE path IN (%s)" % ",".join("?" * len(chunk))
            for path, mtime, size, duration, fp in c.execute(q, chunk):
                if stats.get(path) == (mtime, size):
                    out[path] = (duration, bytes(fp))
        return out

    def put_fingerprints(self, rows: list[tuple[str, int, int, float, bytes]]) -> None:
        if not rows:
            return
        c = self._conn()
        c.executemany("INSERT OR REPLACE INTO fingerprints(path, mtime, size, duration, fp) VALUES (?,?,?,?,?)", rows)
        c.commit()

    # --- Ordner-Status ---------------------------------------------------
    def folder_status_all(self) -> dict[str, int]:
        return dict(self._conn().execute("SELECT path, status FROM folders"))

    def set_folder_status(self, paths: list[str], status: int) -> None:
        now = time.time()
        c = self._conn()
        c.executemany(
            "INSERT INTO folders(path, status, updated) VALUES (?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET status=excluded.status, updated=excluded.updated",
            [(p, status, now) for p in paths],
        )
        c.commit()

    def stats(self) -> dict:
        c = self._conn()
        return {
            "files": c.execute("SELECT COUNT(*) FROM files").fetchone()[0],
            "folders_done": c.execute("SELECT COUNT(*) FROM folders WHERE status=1").fetchone()[0],
        }

    def clear_files(self) -> None:
        c = self._conn()
        c.execute("DELETE FROM files")
        c.execute("DELETE FROM fingerprints")
        c.commit()
        c.execute("VACUUM")
