"""Configuración: de dónde sale el servidor base y cómo se generan los mundos."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_PATH = Path.home() / ".config" / "seedscout" / "config.json"


@dataclass
class Config:
    """`base_server` es una instalación ya montada y probada; SeedScout nunca escribe en ella."""

    base_server: str = "/media/sotano/Media/Documentos/ClaudeCode/Minecraft/Modpacks/CNNY-Server/server/dc-test"
    java: str = "/usr/lib/jvm/java-17-temurin/bin/java"
    forge_args: str = "libraries/net/minecraftforge/forge/1.20.1-47.4.10/unix_args.txt"
    jvm_args: list[str] = field(default_factory=lambda: ["-Xms2G", "-Xmx6G"])
    work_dir: str = str(Path.home() / ".local" / "share" / "seedscout" / "runs")
    seeds_dir: str = str(Path.home() / "Documentos" / "Minecraft" / "SeedScout")
    radius: int = 768
    game_port: int = 25599
    view_distance: int = 6
    boot_timeout_s: int = 600
    chunky_timeout_s: int = 3600
    keep_worlds: bool = False

    # Se copian porque los mods escriben dentro; el resto se enlaza por symlink.
    copy_dirs: tuple[str, ...] = ("config", "defaultconfigs", "kubejs")
    link_dirs: tuple[str, ...] = (
        "mods", "libraries", "customnpcs", "patchouli_books",
        "quests_structures", "generated_datapacks", "media",
    )
    copy_files: tuple[str, ...] = ("eula.txt", "default-server.properties", "nedologin.json")

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "Config":
        if path.exists():
            data = json.loads(path.read_text())
            known = {f for f in cls.__dataclass_fields__}
            return cls(**{k: v for k, v in data.items() if k in known})
        return cls()

    def save(self, path: Path = DEFAULT_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False))
