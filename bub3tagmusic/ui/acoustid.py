"""Unbekannte Dateien erkennen (Phase 4) – Fingerabdruck + AcoustID, mit Vorschau.

Links: Key, welche Dateien, welche Felder, Start. Rechts: Vorschau wie bei den
Werkzeugen. Übernehmen = ein Rückgängig-Schritt, gelb markiert bis zum Speichern.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLineEdit, QProgressBar, QPushButton

from ..core.fields import FIELD_BY_KEY
from ..core.fingerprint import FingerprintError, compress, fingerprint, from_blob, to_blob
from ..core.tools_external import find_tool, install_hint
from ..online import acoustid
from ..online.base import OnlineError
from .tools import CHANGED, ERROR, UNCHANGED, WARN, Preview, PreviewRow, ToolDialog
from .widgets import FieldPicker, hint, section
from .workers import Task

FIELDS = ["title", "artist", "album", "albumartist", "year", "track", "disc"]
WAIT = "wait"


class AcoustIDDialog(ToolDialog):
    feature_id = "acoustid"

    def build_options(self):
        self._results: dict[int, object] = {}       # id(item) → AcoustMatch | Fehlertext
        self.task: Task | None = None
        f = self.form
        f.addWidget(section("AcoustID-Key"))
        self.key = QLineEdit(self.settings.acoustid_key)
        self.key.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.key.setPlaceholderText("Key hier einfügen")
        self.key.editingFinished.connect(self._store_key)
        f.addWidget(self.key)
        link = hint(f'Kostenlos unter <a href="{acoustid.KEY_URL}">acoustid.org/new-application</a> '
                    "(Anmeldung mit MusicBrainz- oder Google-Konto, Name z. B. „BuB3TAGMUSIC“).")
        link.setOpenExternalLinks(True)
        f.addWidget(link)
        f.addSpacing(6)
        f.addWidget(section("Welche Dateien?"))
        self.add_check("Nur Dateien ohne Titel oder Interpret", "only_unknown", True,
                       "Aus: alle gewählten Dateien werden erkannt (z. B. um Tags zu prüfen).")
        f.addSpacing(6)
        f.addWidget(section("Felder übernehmen"))
        self.fields = FieldPicker(FIELDS, self.opts.get("fields", ["title", "artist", "album", "year", "track"]))
        self.fields.changed.connect(lambda: (self.opts.__setitem__("fields", self.fields.selected()), self.later()))
        f.addWidget(self.fields)
        self.add_check("Nur sichere Treffer", "sure_only", True,
                       f"Treffer unter {int(acoustid.GOOD_SCORE * 100)} % werden gezeigt, aber nicht übernommen.")
        f.addSpacing(10)
        self.start_btn = QPushButton("Erkennen starten")
        self.start_btn.setProperty("kind", "primary")
        self.start_btn.clicked.connect(self.start)
        f.addWidget(self.start_btn)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.hide()
        f.addWidget(self.bar)
        self.fpcalc = find_tool("fpcalc")
        if not self.fpcalc:
            self.start_btn.setEnabled(False)
            f.addWidget(hint(install_hint("fpcalc"), "muted"))
        else:
            f.addWidget(hint("Pro Datei ein Fingerabdruck (etwa eine Sekunde) und eine Anfrage an AcoustID. "
                             "Abdrücke werden gemerkt.", "muted"))

    def _store_key(self):
        key = self.key.text().strip()
        if key != self.settings.acoustid_key:
            self.settings.acoustid_key = key
            try:
                self.settings.save()
            except OSError:
                pass

    # --- welche Dateien -------------------------------------------------------------
    def targets(self):
        if not self.opts.get("only_unknown", True):
            return list(self.items)
        return [it for it in self.items if not it.error and
                (not it.tags.get("title", "").strip() or not it.tags.get("artist", "").strip())]

    # --- Erkennen ----------------------------------------------------------------------
    def start(self):
        if self.task is not None and self.task.isRunning():
            self.task.cancel()
            self.start_btn.setText("Breche ab …")
            return
        self._store_key()
        key = self.settings.acoustid_key
        if not key:
            self.message.setText("Erst den AcoustID-Key eintragen – kostenlos unter acoustid.org/new-application")
            self.message.show()
            self.key.setFocus()
            return
        items = [it for it in self.targets() if not isinstance(self._results.get(id(it)), acoustid.AcoustMatch)]
        if not items:
            self.message.setText("Keine Datei zu erkennen – „Nur Dateien ohne Titel oder Interpret“ ausschalten?")
            self.message.show()
            return
        jobs = [(id(it), it.path, int(it.rec.get("mtime") or 0), int(it.rec.get("size") or 0),
                 it.tags.get("album", "")) for it in items]
        cache, exe, results = self.win.cache, self.fpcalc, self._results

        def work(progress, cancelled):
            stats = {p: (m, s) for _i, p, m, s, _a in jobs}
            known = cache.get_fingerprints(stats)
            fresh = []
            for n, (iid, path, mtime, size, album) in enumerate(jobs):
                if cancelled():
                    break
                progress(n, len(jobs), "Erkenne")
                try:
                    if path in known:
                        dur, fp = known[path][0], from_blob(known[path][1])
                    else:
                        dur, fp = fingerprint(path, exe=exe)
                        if mtime:
                            fresh.append((path, mtime, size, dur, to_blob(fp)))
                    matches = acoustid.lookup(compress(fp), dur, key, album)
                    results[iid] = matches[0] if matches else "kein Treffer bei AcoustID"
                except FingerprintError as exc:
                    results[iid] = f"kein Fingerabdruck: {exc}"
                except OnlineError as exc:
                    cache.put_fingerprints(fresh)
                    raise exc
            cache.put_fingerprints(fresh)
            progress(len(jobs), len(jobs), "Erkenne")
            return len(jobs)

        self.task = Task(work)
        self.task.progress.connect(self._progress)
        self.task.done.connect(lambda _n: self._finished(""))
        self.task.failed.connect(self._finished)
        self.message.hide()
        self.start_btn.setText("Abbrechen")
        self.start_btn.setProperty("kind", "")
        self._repolish(self.start_btn)
        self.bar.setRange(0, len(jobs))
        self.bar.setValue(0)
        self.bar.show()
        self.task.start()

    @staticmethod
    def _repolish(w):
        w.style().unpolish(w)
        w.style().polish(w)

    def _progress(self, d: int, t: int, _text: str):
        self.bar.setRange(0, max(1, t))
        self.bar.setValue(d)
        self.summary.setText(f"Erkenne … {d:,} / {t:,}".replace(",", "."))
        self.later()

    def _finished(self, error: str):
        self.bar.hide()
        self.start_btn.setText("Erkennen starten")
        self.start_btn.setProperty("kind", "primary")
        self._repolish(self.start_btn)
        self.refresh()
        if error:
            self.message.setText(error)
            self.message.show()

    # --- Vorschau ------------------------------------------------------------------------
    def compute(self) -> Preview:
        keys = self.fields.selected()
        self._changes = []
        if not keys:
            return Preview(message="Mindestens ein Feld auswählen")
        targets = self.targets()
        sure = self.opts.get("sure_only", True)
        rows, unsure, missing, waiting = [], 0, 0, 0
        for it in targets:
            r = self._results.get(id(it))
            if r is None:
                waiting += 1
                rows.append(PreviewRow(it.name, [(it.tags.get(k, ""), None) for k in keys], "wartet", WAIT, it.path))
                continue
            if isinstance(r, str):
                missing += 1
                rows.append(PreviewRow(it.name, [(it.tags.get(k, ""), None) for k in keys], r, ERROR, it.path))
                continue
            new = {k: v for k, v in r.tags().items() if k in keys}
            diff = {k: v for k, v in new.items() if it.tags.get(k, "") != v}
            pct = f"{round(r.score * 100)} %"
            cells = [(diff[k], it.tags.get(k, "")) if k in diff else (it.tags.get(k, ""), None) for k in keys]
            tip = f"{r.artist} – {r.title}\nAlbum: {r.album or '?'} ({r.kind or 'unbekannt'})"
            if r.others:
                tip += f"\n{r.others} weitere Veröffentlichung(en) dieses Titels"
            if sure and r.score < acoustid.GOOD_SCORE:
                unsure += 1
                rows.append(PreviewRow(it.name, [(new.get(k, it.tags.get(k, "")), None) for k in keys],
                                       f"unsicher ({pct}) – wird nicht übernommen", WARN, tip))
                continue
            if diff:
                self._changes.append((it, diff))
                rows.append(PreviewRow(it.name, cells, f"erkannt ({pct})", CHANGED, tip))
            else:
                rows.append(PreviewRow(it.name, cells, f"stimmt schon ({pct})", UNCHANGED, tip))
        extra = [f"{waiting} warten" if waiting else "", f"{missing} nicht erkannt" if missing else "",
                 f"{unsure} unsicher" if unsure else ""]
        msg = ""
        if not targets:
            msg = "Alle gewählten Dateien haben Titel und Interpret – zum Prüfen „Nur Dateien ohne Titel oder " \
                  "Interpret“ ausschalten."
        elif waiting == len(targets) and not self.settings.acoustid_key:
            msg = "AcoustID-Key eintragen, dann „Erkennen starten“."
        p = Preview([FIELD_BY_KEY[k].label for k in keys], rows,
                    self.summary_text(len(self._changes), len(targets), extra), len(self._changes), msg)
        return p

    def done(self, r):
        if self.task is not None and self.task.isRunning():
            self.task.cancel()
        super().done(r)

