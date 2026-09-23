"""Carpeta por semilla, más la galería comparativa."""
from __future__ import annotations

import html
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .colors import pretty


@dataclass
class SavedSeed:
    seed: int
    path: Path
    data: dict

    @property
    def notes(self) -> str:
        notes = self.path / "notas.md"
        return notes.read_text() if notes.exists() else ""


class SeedStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def folder(self, seed: int) -> Path:
        return self.root / str(seed)

    def save(self, seed: int, map_png: Path, share_png: Path, data: dict, notes: str) -> Path:
        folder = self.folder(seed)
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(map_png, folder / "mapa.png")
        shutil.copy2(share_png, folder / "mapa-compartir.png")
        data = dict(data, seed=seed, guardada=datetime.now().isoformat(timespec="seconds"))
        (folder / "datos.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
        (folder / "notas.md").write_text(self._notes_markdown(seed, data, notes))
        self.write_gallery()
        return folder

    def _notes_markdown(self, seed: int, data: dict, notes: str) -> str:
        lines = [f"# Semilla {seed}", ""]
        lines.append(f"- Generada: {data.get('guardada', '')}")
        lines.append(f"- Radio pregenerado: {data.get('radio', '?')} bloques")
        lines.append(f"- Chunks leídos: {data.get('chunks', '?')}")
        lines.append(f"- Ciudades detectadas: {len(data.get('ciudades', []))}")
        top = data.get("biomas", [])[:8]
        if top:
            lines += ["", "## Biomas dominantes", ""]
            lines += [f"- {pretty(name)} — {share:.1f}%" for name, share in top]
        cities = data.get("ciudades", [])[:8]
        if cities:
            lines += ["", "## Ciudades", ""]
            lines += [
                f"- {c['chunks']} chunks ({c['buildings']} con edificio) — centro {c['center'][0]}, {c['center'][1]}"
                for c in cities
            ]
        lines += ["", "## Notas", "", notes.strip() or "_(sin notas)_", ""]
        return "\n".join(lines)

    def list(self) -> list[SavedSeed]:
        out: list[SavedSeed] = []
        for folder in sorted(self.root.iterdir(), reverse=True):
            data_file = folder / "datos.json"
            if folder.is_dir() and data_file.exists():
                data = json.loads(data_file.read_text())
                out.append(SavedSeed(seed=int(data.get("seed", folder.name)), path=folder, data=data))
        return out

    def delete(self, seed: int) -> None:
        folder = self.folder(seed)
        if folder.is_dir():
            shutil.rmtree(folder)
        self.write_gallery()

    def write_gallery(self) -> Path:
        cards = []
        for saved in self.list():
            biomes = ", ".join(
                f"{pretty(name)} {share:.0f}%" for name, share in saved.data.get("biomas", [])[:4]
            )
            cities = saved.data.get("ciudades", [])
            biggest = f"{cities[0]['chunks']} chunks" if cities else "ninguna"
            cards.append(
                f"""<article>
  <a href="{saved.seed}/mapa.png"><img src="{saved.seed}/mapa.png" alt="mapa de {saved.seed}"></a>
  <h2>{saved.seed}</h2>
  <p class="meta">{html.escape(biomes)}</p>
  <p class="meta">Ciudades: {len(cities)} · mayor {biggest} · {saved.data.get('chunks', '?')} chunks</p>
  <pre>{html.escape(saved.notes.split('## Notas')[-1].strip().lstrip('#').strip())}</pre>
  <p class="links"><a href="{saved.seed}/mapa-compartir.png">imagen para compartir</a> · <a href="{saved.seed}/datos.json">datos</a></p>
</article>"""
            )
        page = GALLERY_TEMPLATE.replace("{{CARDS}}", "\n".join(cards) or "<p>Todavía no hay semillas guardadas.</p>")
        path = self.root / "galeria.html"
        path.write_text(page)
        return path


GALLERY_TEMPLATE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>SeedScout — semillas guardadas</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root { color-scheme: dark; --bg:#16181c; --card:#1e2127; --line:#2c313a; --text:#e6e8ec; --dim:#9aa0a8; --accent:#ffc460; }
body { margin:0; padding:24px; background:var(--bg); color:var(--text); font:15px/1.5 system-ui, sans-serif; }
h1 { font-size:22px; margin:0 0 20px; }
main { display:grid; gap:18px; grid-template-columns:repeat(auto-fill, minmax(320px, 1fr)); }
article { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px; }
img { width:100%; border-radius:6px; display:block; background:#000; }
h2 { font-size:16px; margin:12px 0 6px; color:var(--accent); font-family:ui-monospace, monospace; }
.meta { color:var(--dim); font-size:13px; margin:2px 0; }
pre { white-space:pre-wrap; font:13px/1.45 ui-monospace, monospace; color:var(--text); background:#14161a; border-radius:6px; padding:8px; margin:10px 0 6px; }
.links a { color:var(--accent); }
</style></head>
<body><h1>SeedScout — semillas guardadas</h1><main>{{CARDS}}</main></body></html>
"""
