"""Genera un mundo real con una semilla y lo pregenera con Chunky.

Se usa el servidor de verdad —con sus 340 mods— porque BiomesOPlenty y TerraBlender reescriben
la distribución de biomas: cualquier simulador externo (Chunkbase, cubiomes, Amidst) mostraría
un mundo que no es el que se va a jugar.

El servidor arranca en un directorio de trabajo propio: `mods/` y `libraries/` van por symlink
(nunca se escriben) y `config/` se copia (los mods sí escriben ahí), de modo que la instalación
base queda intacta. Se para siempre con el comando `stop` por consola, nunca matando el proceso.
"""
from __future__ import annotations

import os
import random
import re
import shutil
import signal
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
# Un arranque que revienta no siempre mata el proceso: Forge deja la JVM viva y el servidor nunca
# llega a "Done". Sin esto, la espera se comía el timeout entero (pasó con una carrera de Create:
# "Mod 'create' encountered an error in a deferred task").
FATAL_RE = re.compile(
    r"encountered an error in a deferred task"
    r"|Exception in thread \"main\""
    r"|Failed to start the minecraft server"
    r"|A fatal error has occurred"
    r"|Loading errors have been found"
    r"|The server encountered an unexpected error"
)
MOD_RE = re.compile(r"Mod '([^']+)'")
SAVED_RE = re.compile(r"Saved the game|Saving the game")


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
    center: tuple[int, int] = (0, 0)

    @property
    def elapsed(self) -> float:
        return time.time() - self.started


class WorldRunner:
    """Mantiene **un** servidor vivo entre generaciones.

    La semilla se fija al crear el mundo, así que cambiar de semilla obliga a reiniciar: eso no
    tiene vuelta de hoja en Forge. Lo que sí se evita es el arranque de 83 s cuando se vuelve a
    generar sobre la misma semilla (ampliar el radio) o cuando se para y arranca a mano.
    """

    def __init__(self, config: Config, on_update: Callable[[RunState], None] | None = None):
        self.config = config
        self.on_update = on_update or (lambda _state: None)
        self.process: subprocess.Popen | None = None
        self.seed: int | None = None
        self.work: Path | None = None
        self.log_path: Path | None = None
        self._booted = threading.Event()
        self._chunky_done = threading.Event()
        self._failed = threading.Event()
        self._saved = threading.Event()
        self._failure: str = ""
        self._state: RunState | None = None

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

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
        for name in getattr(self.config, "link_contents_dirs", ()):
            source = base / name
            if not source.is_dir():
                continue
            target = work / name
            target.mkdir()
            for item in source.iterdir():
                if item.is_file():
                    (target / item.name).symlink_to(item.resolve())
                elif item.is_dir():
                    # `mods/.connector` son los jars de Fabric ya remapeados por Connector. Sin
                    # esa caché el remapeo se rehace en cada arranque y cambia el orden de carga;
                    # es la sospecha del fallo intermitente de Create en tareas diferidas.
                    shutil.copytree(item, target / item.name, symlinks=True)
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

    def _send(self, line: str) -> None:
        if not self.alive:
            raise RuntimeError("el servidor no está arrancado")
        self.process.stdin.write(line + "\n")  # type: ignore[union-attr]
        self.process.stdin.flush()  # type: ignore[union-attr]

    def _pump(self) -> None:
        with self.log_path.open("w") as log:  # type: ignore[union-attr]
            for line in self.process.stdout:  # type: ignore[union-attr]
                log.write(line)
                log.flush()
                state = self._state
                if not self._booted.is_set() and DONE_RE.search(line):
                    self._booted.set()
                if not self._booted.is_set() and FATAL_RE.search(line):
                    culprit = MOD_RE.search(line)
                    self._failure = (f"el mod '{culprit.group(1)}' hizo fallar el arranque"
                                     if culprit else line.strip()[:160])
                    self._failed.set()
                    self._booted.set()  # deja de esperar: el arranque ya no va a llegar
                if SAVED_RE.search(line):
                    self._saved.set()
                if "Chunky" in line and state:
                    found = PROGRESS_RE.search(line)
                    if found:
                        state.progress = float(found.group(1).replace(",", "."))
                        state.message = line.strip()[-120:]
                        self.on_update(state)
                    if CHUNKY_DONE_RE.search(line):
                        self._chunky_done.set()

    def start(self, seed: int, state: RunState | None = None) -> None:
        """Arranca el servidor para esa semilla. Si ya está vivo con otra, lo para antes."""
        if self.alive and self.seed == seed:
            return
        if self.alive:
            self.stop()
        state = state or RunState(seed=seed)
        self._state = state
        self._booted.clear()
        self._failed.clear()
        self._failure = ""
        state.phase = "preparando"
        self.on_update(state)
        self.work = self.prepare(seed)
        self.seed = seed
        self.log_path = self.work / "seedscout.log"
        state.world_dir = self.work / "world"
        state.log_path = self.log_path

        state.phase = "arrancando"
        self.on_update(state)
        command = [self.config.java, *self.config.jvm_args, f"@{self.config.forge_args}", "nogui"]
        self.process = subprocess.Popen(
            command, cwd=self.work, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        threading.Thread(target=self._pump, daemon=True).start()
        if not self._booted.wait(self.config.boot_timeout_s):
            self.stop()
            raise TimeoutError(f"el servidor no arrancó en {self.config.boot_timeout_s}s")
        if self._failed.is_set():
            message = self._failure or "el arranque falló"
            self.stop()
            raise RuntimeError(f"{message} (log: {self.log_path})")
        state.phase = "servidor listo"
        self.on_update(state)

    def stop(self) -> None:
        """Siempre por consola: matar el proceso deja regiones a medio escribir."""
        if not self.alive:
            self.process = None
            self.seed = None
            return
        try:
            self._send("save-all flush")
            self._send("stop")
        except Exception:
            pass
        try:
            self.process.wait(timeout=self.config.stop_timeout_s)  # type: ignore[union-attr]
        except subprocess.TimeoutExpired:
            # Un servidor que ya reventó no atiende la consola. SIGTERM es el apagado ordenado
            # (Minecraft lo engancha), no un kill a secas; solo se usa con los servidores que
            # lanza SeedScout y cuando `stop` no ha servido.
            self.process.send_signal(signal.SIGTERM)  # type: ignore[union-attr]
            try:
                self.process.wait(timeout=30)  # type: ignore[union-attr]
            except subprocess.TimeoutExpired:
                self.process.kill()  # type: ignore[union-attr]
                self.process.wait(timeout=15)  # type: ignore[union-attr]
        self.process = None
        self.seed = None

    def world_spawn(self) -> tuple[int, int] | None:
        """Spawn que el servidor fijó al crear el mundo.

        Hay que forzar un guardado antes de leerlo: al terminar el arranque el spawn ya está
        decidido en memoria, pero `level.dat` todavía no se ha escrito en disco y se leería el
        del mundo recién creado (0, 0).
        """
        if not self.work or not self.alive:
            return None
        from .world import read_spawn

        self._saved.clear()
        try:
            self._send("save-all flush")
        except RuntimeError:
            return None
        self._saved.wait(60)
        time.sleep(1)
        return read_spawn(self.work / "world")

    def pregenerate(self, radius: int, state: RunState, center: tuple[int, int] = (0, 0)) -> None:
        self._chunky_done.clear()
        self._state = state
        state.phase = "generando"
        state.progress = 0.0
        state.message = f"Chunky, radio {radius} bloques alrededor de {center[0]}, {center[1]}"
        self.on_update(state)
        self._send("chunky world minecraft:overworld")
        self._send(f"chunky center {center[0]} {center[1]}")
        self._send(f"chunky radius {radius}")
        self._send("chunky start")
        if not self._chunky_done.wait(self.config.chunky_timeout_s):
            self._send("chunky cancel")
            raise TimeoutError(f"Chunky no terminó en {self.config.chunky_timeout_s}s")
        state.phase = "guardando"
        state.progress = 100.0
        self.on_update(state)
        self._send("save-all flush")
        time.sleep(5)

    def generate(self, seed: int, radius: int | None = None, keep_alive: bool = True,
                 center: tuple[int, int] | None = None) -> RunState:
        """Genera (o amplía) el mundo de una semilla. Deja el servidor vivo salvo que se diga lo contrario."""
        radius = radius or self.config.radius
        state = RunState(seed=seed)
        self.on_update(state)
        try:
            self.start(seed, state)
            follow_spawn = center is None and self.config.center == "spawn"
            if center is None:
                center = (self.world_spawn() if follow_spawn else None) or (0, 0)
            state.center = center
            self.pregenerate(radius, state, center)
            if follow_spawn:
                # El spawn definitivo no está fijado cuando arranca el servidor: Lost Cities lo
                # mueve junto a uno de sus edificios y eso puede ocurrir durante la generación.
                # Se relee al terminar y, si quedó fuera de lo generado, se hace otra pasada.
                spawn = self.world_spawn()
                if spawn and max(abs(spawn[0] - center[0]), abs(spawn[1] - center[1])) > radius:
                    state.message = f"el spawn quedó en {spawn[0]}, {spawn[1]}: se genera alrededor"
                    self.on_update(state)
                    state.center = center = spawn
                    self.pregenerate(radius, state, spawn)
        except Exception as error:
            state.error = str(error)
        if not keep_alive or state.error:
            state.phase = "parando"
            self.on_update(state)
            self.stop()
        state.finished = True
        state.phase = "listo" if not state.error else "error"
        self.on_update(state)
        return state
