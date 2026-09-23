"""Genera un mundo real con una semilla y lo pregenera con Chunky.

Se usa el servidor de verdad —con sus 340 mods— porque BiomesOPlenty y TerraBlender reescriben
la distribución de biomas: cualquier simulador externo (Chunkbase, cubiomes, Amidst) mostraría
un mundo que no es el que se va a jugar.

El servidor arranca en un directorio de trabajo propio: `mods/` y `libraries/` van por symlink
(nunca se escriben) y `config/` se copia (los mods sí escriben ahí), de modo que la instalación
base queda intacta. Se para siempre con el comando `stop` por consola, nunca matando el proceso.
"""
from __future__ import annotations

import random
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import Config

DONE_RE = re.compile(r'Done \(([\d.]+)s\)')
PROGRESS_RE = re.compile(r'(\d+(?:[.,]\d+)?)%')
CHUNKY_DONE_RE = re.compile(r'Task (?:finished|complete)', re.I)


def random_seed() -> int:
    return random.getrandbits(63) - (1 << 62)


@dataclass
class RunState:
    seed: int
    phase: str = "inactivo"
    progress: float = 0.0
    message: str = ""
    log_path: Path | None = None
    world_dir: Path | None = None
    started: float = field(default_factory=time.time)
    finished: bool = False
    error: str | None = None

    @property
    def elapsed(self) -> float:
        return time.time() - self.started


class WorldRunner:
    def __init__(self, config: Config, on_update: Callable[[RunState], None] | None = None):
        self.config = config
        self.on_update = on_update or (lambda _state: None)

    def prepare(self, seed: int) -> Path:
        base = Path(self.config.base_server)
        work = Path(self.config.work_dir) / str(seed)
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)

        for name in self.config.link_dirs:
            source = base / name
            if source.is_dir():
                (work / name).symlink_to(source)
        for name in self.config.copy_dirs:
            source = base / name
            if source.is_dir():
                shutil.copytree(source, work / name, symlinks=True)
        for name in self.config.copy_files:
            source = base / name
            if source.is_file():
                shutil.copy2(source, work / name)

        (work / "server.properties").write_text(self._properties(seed))
        (work / "ops.json").write_text("[]")
        (work / "whitelist.json").write_text("[]")
        return work

    def _properties(self, seed: int) -> str:
        base = Path(self.config.base_server) / "server.properties"
        values: dict[str, str] = {}
        if base.exists():
            for line in base.read_text().splitlines():
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    values[key] = value
        values.update(
            {
                "level-seed": str(seed),
                "level-name": "world",
                "server-port": str(self.config.game_port),
                "query.port": str(self.config.game_port),
                "enable-rcon": "false",
                "online-mode": "false",
                "max-players": "1",
                "view-distance": str(self.config.view_distance),
                "simulation-distance": "4",
                "spawn-protection": "0",
                "sync-chunk-writes": "false",
                "motd": f"SeedScout {seed}",
            }
        )
        return "\n".join(f"{k}={v}" for k, v in sorted(values.items())) + "\n"

    def generate(self, seed: int, radius: int | None = None) -> RunState:
        radius = radius or self.config.radius
        state = RunState(seed=seed, phase="preparando")
        self.on_update(state)
        work = self.prepare(seed)
        state.world_dir = work / "world"
        log_path = work / "seedscout.log"
        state.log_path = log_path

        command = [self.config.java, *self.config.jvm_args, f"@{self.config.forge_args}", "nogui"]
        state.phase = "arrancando"
        self.on_update(state)
        process = subprocess.Popen(
            command, cwd=work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )

        booted = threading.Event()
        chunky_done = threading.Event()

        def pump() -> None:
            with log_path.open("w") as log:
                for line in process.stdout:  # type: ignore[union-attr]
                    log.write(line)
                    log.flush()
                    if not booted.is_set() and DONE_RE.search(line):
                        booted.set()
                    if "Chunky" in line:
                        found = PROGRESS_RE.search(line)
                        if found:
                            state.progress = float(found.group(1).replace(",", "."))
                            state.message = line.strip()[-120:]
                            self.on_update(state)
                        if CHUNKY_DONE_RE.search(line):
                            chunky_done.set()

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()

        def send(command_line: str) -> None:
            process.stdin.write(command_line + "\n")  # type: ignore[union-attr]
            process.stdin.flush()  # type: ignore[union-attr]

        try:
            if not booted.wait(self.config.boot_timeout_s):
                raise TimeoutError(f"el servidor no arrancó en {self.config.boot_timeout_s}s")
            state.phase = "generando"
            state.message = f"Chunky, radio {radius} bloques"
            self.on_update(state)
            send("chunky world minecraft:overworld")
            send("chunky center 0 0")
            send(f"chunky radius {radius}")
            send("chunky start")
            if not chunky_done.wait(self.config.chunky_timeout_s):
                send("chunky cancel")
                raise TimeoutError(f"Chunky no terminó en {self.config.chunky_timeout_s}s")
            state.phase = "guardando"
            state.progress = 100.0
            self.on_update(state)
            send("save-all flush")
            time.sleep(5)
        except Exception as error:  # se apaga igual, para no dejar el mundo a medias
            state.error = str(error)
        finally:
            state.phase = "parando"
            self.on_update(state)
            try:
                send("stop")
            except Exception:
                pass
            process.wait(timeout=180)
            reader.join(timeout=10)

        state.finished = True
        state.phase = "listo" if not state.error else "error"
        self.on_update(state)
        return state
