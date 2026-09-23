"""CLI: generar y examinar semillas sin abrir la web."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .city import clusters, scan
from .colors import pretty
from .config import Config
from .pipeline import Pipeline
from .render import render_terrain, with_overlay
from .runner import random_seed
from .store import SeedStore
from .world import sample_world


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="seedscout", description="Explorador de semillas para modpacks pesados")
    sub = parser.add_subparsers(dest="command", required=True)

    web = sub.add_parser("web", help="abre la interfaz web (por defecto)")
    web.add_argument("--port", type=int, default=5055)

    gen = sub.add_parser("gen", help="genera una semilla y guarda su mapa")
    gen.add_argument("seed", nargs="?", type=int)
    gen.add_argument("--radius", type=int)
    gen.add_argument("--notes", default="")
    gen.add_argument("--save", action="store_true", help="guardar en la carpeta de semillas")

    render = sub.add_parser("render", help="dibuja el mapa de un mundo ya existente")
    render.add_argument("world", type=Path)
    render.add_argument("--out", type=Path, default=Path("mapa.png"))
    render.add_argument("--seed", type=int, default=0)
    render.add_argument("--scale", type=int, default=2, help="bloques por píxel")

    conf = sub.add_parser("config", help="muestra o escribe la configuración")
    conf.add_argument("--write", action="store_true")

    sub.add_parser("clean", help="borra los mundos de trabajo que hayan quedado")

    args = parser.parse_args(argv)
    config = Config.load()

    if args.command == "web":
        from .web import create_app
        create_app(config).run(host="127.0.0.1", port=args.port, threaded=True)
        return 0

    if args.command == "config":
        if args.write:
            config.save()
            print("escrita en ~/.config/seedscout/config.json")
        print(json.dumps(config.__dict__, indent=2, ensure_ascii=False))
        return 0

    if args.command == "clean":
        pipeline = Pipeline(config, Path(config.work_dir).parent / "cache")
        count, freed = pipeline.discard_all()
        print(f"{count} mundos de trabajo borrados, {freed} MB liberados")
        return 0

    if args.command == "render":
        from .biomeinfo import load as load_biomes
        from .blockcolors import build as build_block_colors
        from .world import read_spawn

        sample = sample_world(args.world)
        client = Path(config.client_jar)
        mods = sorted((Path(config.base_server) / "mods").glob("*.jar"))
        rendered = render_terrain(
            sample,
            build_block_colors(([client] if client.exists() else []) + mods),
            load_biomes(mods, client if client.exists() else None),
            blocks_per_pixel=args.scale,
            spawn=read_spawn(args.world),
        )
        with_overlay(rendered, args.seed).save(args.out)
        cities = clusters(scan(args.world))
        print(f"{len(sample.chunks)} chunks · {len(rendered.legend)} biomas · {len(cities)} ciudades → {args.out}")
        return 0

    pipeline = Pipeline(config, Path(config.work_dir).parent / "cache")
    pipeline.on_cleanup = lambda mb: print(f"  mundo de trabajo borrado ({mb} MB)")
    seed = args.seed if args.seed is not None else random_seed()
    print(f"generando la semilla {seed} (radio {args.radius or config.radius})…")
    job = pipeline.start(seed, args.radius)
    last = ""
    while not job.snapshot()["done"]:
        snapshot = job.snapshot()
        line = f"  {snapshot['phase']} {snapshot['progress']}%"
        if line != last:
            print(line, flush=True)
            last = line
        import time
        time.sleep(3)
    if job.error:
        print(f"error: {job.error}")
        return 1
    result = job.scan
    print(f"{result.chunks} chunks · {len(result.cities)} ciudades")
    for name, share in result.biomes[:8]:
        print(f"  {pretty(name):24} {share:5.1f}%")
    if args.save:
        share_png = pipeline.share_image(job)
        folder = SeedStore(Path(config.seeds_dir)).save(seed, result.map_png, share_png, result.data(), args.notes)
        print(f"guardada en {folder}")
    else:
        print(f"mapa: {result.map_png}")
    return 0
