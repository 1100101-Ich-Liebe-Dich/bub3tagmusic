"""Liste exportieren (Phase 4): CSV für Tabellenkalkulationen, HTML zum Anschauen und Drucken.

Ohne Qt – die Oberfläche liefert Spaltenköpfe und fertige Zellentexte
(genau das, was in der Liste zu sehen ist, in derselben Reihenfolge).
"""

from __future__ import annotations

import base64
import csv
import datetime as _dt
import html
import os

from .. import APP_NAME, PRESENTER, PRESENTER_URL

DELIMITERS = {
    "semicolon": (";", "Semikolon – LibreOffice/Excel auf Deutsch"),
    "comma": (",", "Komma – international"),
    "tab": ("\t", "Tabulator"),
}
_WORDMARK = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "export", "wordmark.ttf")


def write_csv(path: str, headers: list[str], rows: list[list[str]], delimiter: str = ";") -> None:
    """UTF-8 mit BOM – so erkennen auch Excel und LibreOffice die Umlaute sofort."""
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
        w.writerow(headers)
        w.writerows(rows)
    os.replace(tmp, path)


def _font_face() -> str:
    try:
        with open(_WORDMARK, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
    except OSError:
        return ""
    return ("@font-face { font-family: 'BuB3Mark'; font-weight: 800; "
            f"src: url(data:font/ttf;base64,{data}) format('truetype'); }}")


def _palette_css(p: dict[str, str]) -> str:
    keys = ("bg", "panel", "raised", "sunken", "line", "line_soft", "text", "muted", "faint", "accent",
            "accent_soft", "hover", "wordmark")
    return " ".join(f"--{k.replace('_', '-')}: {p[k]};" for k in keys if k in p)


def build_html(headers: list[str], rows: list[list[str]], *, title: str, subtitle: str = "",
               numeric: set[int] | None = None, dark: dict | None = None, light: dict | None = None,
               created: _dt.datetime | None = None) -> str:
    """Eine einzige, eigenständige HTML-Datei: sortierbar (Klick auf Spaltenkopf), mit Suchfeld,
    hell/dunkel passend zum System, druckfreundlich."""
    numeric = numeric or set()
    created = created or _dt.datetime.now()
    dark = dark or {}
    light = light or {}
    esc = html.escape

    head_cells = "".join(
        f'<th data-col="{i}"{" class=num" if i in numeric else ""}>{esc(h)}</th>' for i, h in enumerate(headers))
    body = []
    for r in rows:
        cells = "".join(f'<td{" class=num" if i in numeric else ""}>{esc(v)}</td>' for i, v in enumerate(r))
        body.append(f"<tr>{cells}</tr>")
    n = len(rows)
    count = f"{n:,} {'Datei' if n == 1 else 'Dateien'}".replace(",", ".")
    meta = " · ".join(x for x in (count, subtitle, f"erstellt am {created:%d.%m.%Y um %H:%M}") if x)

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="{APP_NAME} – präsentiert von {PRESENTER}">
<title>{esc(title)} – {APP_NAME}</title>
<style>
{_font_face()}
:root {{ {_palette_css(light)} color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root {{ {_palette_css(dark)} color-scheme: dark; }} }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text);
       font: 14px/1.45 Inter, "Segoe UI", system-ui, -apple-system, Roboto, sans-serif; }}
header {{ background: var(--panel); border-bottom: 1px solid var(--line); padding: 18px 28px 16px;
         display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px 28px; }}
.mark {{ font-family: BuB3Mark, Impact, "Arial Narrow", sans-serif; font-weight: 800; font-size: 34px;
        letter-spacing: .5px; line-height: 1; margin: 0; color: var(--wordmark, var(--text)); }}
.by {{ color: var(--muted); font-size: 12px; margin-top: 4px; }}
.by a, footer a {{ color: var(--muted); font-weight: 600; text-decoration: none; }}
.by a:hover, footer a:hover {{ color: var(--accent); }}
.titles {{ flex: 1 1 300px; }}
h1 {{ font-size: 18px; margin: 0; font-weight: 600; }}
.meta {{ color: var(--muted); font-size: 13px; }}
.tools {{ padding: 14px 28px 0; display: flex; gap: 12px; align-items: center; }}
input[type=search] {{ background: var(--raised); color: var(--text); border: 1px solid var(--line);
       border-radius: 9px; padding: 8px 12px; font: inherit; width: min(360px, 100%); }}
input[type=search]:focus {{ outline: none; border-color: var(--accent); }}
#shown {{ color: var(--faint); font-size: 13px; }}
main {{ padding: 12px 28px 28px; }}
.wrap {{ background: var(--sunken); border: 1px solid var(--line); border-radius: 12px; overflow: auto; }}
table {{ border-collapse: collapse; width: 100%; }}
th {{ position: sticky; top: 0; background: var(--sunken); color: var(--muted); font-size: 12px;
     font-weight: 600; text-align: left; padding: 9px 12px; border-bottom: 1px solid var(--line);
     cursor: pointer; user-select: none; white-space: nowrap; }}
th:hover {{ color: var(--text); }}
th.asc::after {{ content: " ▲"; color: var(--accent); }}
th.desc::after {{ content: " ▼"; color: var(--accent); }}
td {{ padding: 7px 12px; border-bottom: 1px solid var(--line-soft); white-space: nowrap;
     max-width: 360px; overflow: hidden; text-overflow: ellipsis; }}
tr:hover td {{ background: var(--hover); }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
footer {{ color: var(--faint); font-size: 12px; padding: 0 28px 24px; }}
@media print {{
  :root {{ {_palette_css(light)} }}
  .tools {{ display: none; }} header {{ background: none; }} .wrap {{ border: none; overflow: visible; }}
  th {{ position: static; }} td {{ white-space: normal; }}
}}
</style>
</head>
<body>
<header>
  <div><p class="mark">{APP_NAME}</p>
  <div class="by">präsentiert von <a href="{PRESENTER_URL}">{PRESENTER}</a></div></div>
  <div class="titles"><h1>{esc(title)}</h1><div class="meta">{esc(meta)}</div></div>
</header>
<div class="tools"><input type="search" id="q" placeholder="Liste filtern …" aria-label="Liste filtern">
<span id="shown"></span></div>
<main><div class="wrap"><table id="list">
<thead><tr>{head_cells}</tr></thead>
<tbody>
{chr(10).join(body)}
</tbody></table></div></main>
<footer>Erstellt mit {APP_NAME} – präsentiert von <a href="{PRESENTER_URL}">{PRESENTER}</a></footer>
<script>
(function () {{
  var tb = document.querySelector('#list tbody'), rows = Array.prototype.slice.call(tb.rows);
  var q = document.getElementById('q'), shown = document.getElementById('shown');
  var coll = new Intl.Collator('de', {{numeric: true, sensitivity: 'base'}});
  function key(tr, c) {{ return tr.cells[c] ? tr.cells[c].textContent : ''; }}
  document.querySelectorAll('#list th').forEach(function (th) {{
    th.addEventListener('click', function () {{
      var c = +th.dataset.col, desc = th.classList.contains('asc');
      document.querySelectorAll('#list th').forEach(function (x) {{ x.classList.remove('asc', 'desc'); }});
      th.classList.add(desc ? 'desc' : 'asc');
      rows.sort(function (a, b) {{
        var x = key(a, c), y = key(b, c);
        if (!x && y) return 1; if (x && !y) return -1;
        var r = coll.compare(x, y); return desc ? -r : r; }});
      rows.forEach(function (tr) {{ tb.appendChild(tr); }});
    }});
  }});
  q.addEventListener('input', function () {{
    var words = q.value.toLowerCase().split(/\\s+/).filter(Boolean), n = 0;
    rows.forEach(function (tr) {{
      var t = tr.textContent.toLowerCase();
      var ok = words.every(function (w) {{ return t.indexOf(w) >= 0; }});
      tr.style.display = ok ? '' : 'none'; if (ok) n++;
    }});
    shown.textContent = words.length ? n + ' von ' + rows.length : '';
  }});
}})();
</script>
</body>
</html>
"""


def write_html(path: str, headers: list[str], rows: list[list[str]], **kw) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(build_html(headers, rows, **kw))
    os.replace(tmp, path)


def default_name(base: str, ext: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_.()&" else "_" for ch in base).strip() or "Liste"
    return f"{APP_NAME} - {safe}.{ext}"
