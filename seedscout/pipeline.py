"""Une las piezas: semilla → mundo generado → mapa + datos, listo para guardar."""
from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .city import clusters, scan
from .config import Config
from .render import MapImage, render_biomes, with_overlay
from .runner import RunState, WorldRunner, random_seed
from .world import sample_world


@dataclass
class Scan:
    seed: int
    radius: int
    chunks: int
    biomes: list[tuple[str, float]]
    cities: list[dict]
    map_png: Path
    share_png: Path
    world_dir: Path
    # El mapa se guarda dibujado porque el mundo de trabajo se borra en cuanto se ha leído:
    # rehacer la imagen para compartir con las notas no puede depender de que siga existiendo.
    rendered: MapImage | None = None

    def data(self) -> dict:
        return {
            "seed": self.seed,
            "radio": self.radius,
            "chunks": self.chunks,
            "biomas": self.biomes,
            "ciudades": self.cities,
        }


@dataclass
class Job:
    """Un trabajo en curso; la web lo consulta para pintar el progreso."""

    seed: int
    radius: int
    state: RunState | None = None
    scan: Scan | None = None
    error: str | None = None
    phase: str = "en cola"
    progress: float = 0.0
    message: str = ""
    lock: threading.Lock = field(default_factory=threading.Lock)

    def snapshot(self) -> dict:
        return {
            "seed": self.seed,
            "radius": self.radius,
            "phase": self.phase,
            "progress": round(self.progress, 1),
            "message": self.message,
            "error": self.error,
            "done": self.scan is not None or self.error is not None,
            "elapsed": round(self.state.elapsed, 0) if self.state else 0,
        }


class Pipeline:
    def __init__(self, config: Config, cache_dir: Path):
        self.config = config
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.job: Job | None = None
        self.on_cleanup: Callable[[int], None] = lambda _mb: None

    def start(self, seed: int | None = None, radius: int | None = None) -> Job:
        if self.job and not self.job.snapshot()["done"]:
            raise RuntimeError("ya hay una semilla generándose")
        job = Job(seed=seed if seed is not None else random_seed(), radius=radius or self.config.radius)
        self.job = job
        threading.Thread(target=self._run, args=(job,), daemon=True).start()
        return job

    def _run(self, job: Job) -> None:
        def update(state: RunState) -> None:
            with job.lock:
                job.state = state
                job.phase = state.phase
                job.progress = state.progress
                job.message = state.message

        try:
            runner = WorldRunner(self.config, on_update=update)
            state = runner.generate(job.seed, job.radius)
            if state.error:
                raise RuntimeError(state.error)
            job.phase = "leyendo el mundo"
            job.progress = 0.0
            world = Path(state.world_dir)  # type: ignore[arg-type]
            sample = sample_world(world)
            job.phase = "buscando ciudades"
            cities = clusters(scan(world))
            job.phase = "dibujando"
            rendered = render_biomes(sample)
            total = sum(count for _, count in rendered.legend) or 1
            biomes = [(name, 100.0 * count / total) for name, count in rendered.legend]
            map_png = self.cache_dir / f"{job.seed}.png"
            share_png = self.cache_dir / f"{job.seed}-compartir.png"
            rendered.image.save(map_png)
            with_overlay(rendered, job.seed).save(share_png)
            job.scan = Scan(
                seed=job.seed, radius=job.radius, chunks=len(sample.chunks), biomes=biomes,
                cities=cities, map_png=map_png, share_png=share_png, world_dir=world,
                rendered=rendered,
            )
            if not self.config.keep_worlds:
                job.phase = "limpiando"
                self.on_cleanup(self.discard(job.seed))
            job.phase = "listo"
            job.progress = 100.0
        except Exception as error:
            job.error = str(error)
            job.phase = "error"

    def discard(self, seed: int) -> int:
        """Borra el directorio de trabajo de una semilla. Devuelve los MB liberados."""
        work = Path(self.config.work_dir) / str(seed)
        if not work.is_dir():
            return 0
        # `mods/` y `libraries/` son symlinks: rmtree los borra como enlaces, no sigue a la
        # instalación base. El resto son copias y el mundo generado.
        size = sum(f.stat().st_size for f in work.rglob("*") if f.is_file() and not f.is_symlink())
        shutil.rmtree(work)
        return size // (1024 * 1024)

    def discard_all(self) -> tuple[int, int]:
        """Limpia los directorios de trabajo que hayan quedado de ejecuciones anteriores."""
        root = Path(self.config.work_dir)
        if not root.is_dir():
            return 0, 0
        freed = 0
        count = 0
        for folder in list(root.iterdir()):
            if folder.is_dir():
                freed += self.discard(int(folder.name)) if folder.name.lstrip("-").isdigit() else 0
                count += 1
        return count, freed

    def rerender(self, job: Job, notes: str) -> Path:
        """La imagen para compartir se rehace al guardar, para que lleve las notas escritas."""
        scan_result = job.scan
        if not scan_result or not scan_result.rendered:
            raise RuntimeError("no hay nada que dibujar todavía")
        with_overlay(scan_result.rendered, job.seed, notes=notes).save(scan_result.share_png)
        return scan_result.share_png
