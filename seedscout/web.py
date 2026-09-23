"""Interfaz web local: generar una semilla, mirar el mapa, anotarla y guardarla."""
from __future__ import annotations

import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

from .colors import pretty
from .config import Config
from .pipeline import Pipeline
from .store import SeedStore


def create_app(config: Config | None = None) -> Flask:
    config = config or Config.load()
    app = Flask(__name__)
    cache = Path(config.work_dir).parent / "cache"
    pipeline = Pipeline(config, cache)
    store = SeedStore(Path(config.seeds_dir))

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            config=config,
            saved=store.list(),
            job=pipeline.job.snapshot() if pipeline.job else None,
        )

    @app.post("/api/generate")
    def generate():
        payload = request.get_json(silent=True) or {}
        raw_seed = str(payload.get("seed", "")).strip()
        radius = int(payload.get("radius") or config.radius)
        try:
            seed = int(raw_seed) if raw_seed else None
        except ValueError:
            seed = sum((i + 1) * ord(ch) for i, ch in enumerate(raw_seed))  # semillas de texto, como en el juego
        try:
            job = pipeline.start(seed, radius)
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 409
        return jsonify(job.snapshot())

    @app.get("/api/status")
    def status():
        if not pipeline.job:
            return jsonify({"idle": True})
        snapshot = pipeline.job.snapshot()
        scan = pipeline.job.scan
        if scan:
            snapshot["result"] = {
                "chunks": scan.chunks,
                "biomes": [[pretty(name), round(share, 1)] for name, share in scan.biomes[:14]],
                "cities": scan.cities[:10],
                "map": f"/api/map/{scan.seed}",
            }
        return jsonify(snapshot)

    @app.get("/api/map/<int:seed>")
    def map_png(seed: int):
        path = cache / f"{seed}.png"
        if not path.exists():
            return jsonify({"error": "no hay mapa para esa semilla"}), 404
        return send_file(path, mimetype="image/png")

    @app.post("/api/save")
    def save():
        job = pipeline.job
        if not job or not job.scan:
            return jsonify({"error": "no hay ninguna semilla generada"}), 400
        notes = (request.get_json(silent=True) or {}).get("notes", "")
        share = pipeline.rerender(job, notes)
        folder = store.save(job.seed, job.scan.map_png, share, job.scan.data(), notes)
        return jsonify({"saved": str(folder), "gallery": "/galeria"})

    @app.post("/api/delete/<int:seed>")
    def delete(seed: int):
        store.delete(seed)
        return jsonify({"ok": True})

    @app.get("/galeria")
    def gallery():
        return send_file(store.write_gallery())

    @app.get("/semillas/<path:relative>")
    def saved_file(relative: str):
        return send_from_directory(store.root, relative)

    return app


def main() -> None:
    config = Config.load()
    app = create_app(config)
    url = "http://127.0.0.1:5055/"
    print(f"SeedScout en {url}  (servidor base: {config.base_server})")
    webbrowser.open(url)
    app.run(host="127.0.0.1", port=5055, threaded=True)


if __name__ == "__main__":
    main()
