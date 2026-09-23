"""Lector de NBT y de región Anvil (1.18+), solo lo que hace falta para el mapa.

No existe dependencia de librerías de NBT a propósito: solo se leen biomas y heightmaps,
y arrastrar una dependencia entera para dos etiquetas no compensa.
"""
from __future__ import annotations

import gzip
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG = 0, 1, 2, 3, 4
TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING = 5, 6, 7, 8
TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY, TAG_LONG_ARRAY = 9, 10, 11, 12


class NbtReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def _take(self, n: int) -> bytes:
        chunk = self.data[self.pos:self.pos + n]
        if len(chunk) != n:
            raise ValueError(f"NBT truncado: faltan {n - len(chunk)} bytes en {self.pos}")
        self.pos += n
        return chunk

    def _string(self) -> str:
        (length,) = struct.unpack(">H", self._take(2))
        return self._take(length).decode("utf-8", "replace")

    def value(self, tag: int):
        if tag == TAG_BYTE:
            return struct.unpack(">b", self._take(1))[0]
        if tag == TAG_SHORT:
            return struct.unpack(">h", self._take(2))[0]
        if tag == TAG_INT:
            return struct.unpack(">i", self._take(4))[0]
        if tag == TAG_LONG:
            return struct.unpack(">q", self._take(8))[0]
        if tag == TAG_FLOAT:
            return struct.unpack(">f", self._take(4))[0]
        if tag == TAG_DOUBLE:
            return struct.unpack(">d", self._take(8))[0]
        if tag == TAG_BYTE_ARRAY:
            (n,) = struct.unpack(">i", self._take(4))
            return self._take(n)
        if tag == TAG_STRING:
            return self._string()
        if tag == TAG_LIST:
            (inner,) = struct.unpack(">B", self._take(1))
            (n,) = struct.unpack(">i", self._take(4))
            return [self.value(inner) for _ in range(n)]
        if tag == TAG_COMPOUND:
            out = {}
            while True:
                (kind,) = struct.unpack(">B", self._take(1))
                if kind == TAG_END:
                    return out
                name = self._string()
                out[name] = self.value(kind)
        if tag == TAG_INT_ARRAY:
            (n,) = struct.unpack(">i", self._take(4))
            return list(struct.unpack(f">{n}i", self._take(4 * n)))
        if tag == TAG_LONG_ARRAY:
            (n,) = struct.unpack(">i", self._take(4))
            return list(struct.unpack(f">{n}q", self._take(8 * n)))
        raise ValueError(f"tag NBT desconocido: {tag}")

    def root(self) -> dict:
        (kind,) = struct.unpack(">B", self._take(1))
        if kind != TAG_COMPOUND:
            raise ValueError("la raíz de un NBT debe ser un compound")
        self._string()
        return self.value(TAG_COMPOUND)


def parse_nbt(data: bytes) -> dict:
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return NbtReader(data).root()


@dataclass
class RegionFile:
    """Un `r.X.Z.mca`. Los chunks se leen bajo demanda: una región llena son ~1024 chunks."""

    path: Path
    rx: int
    rz: int

    @classmethod
    def open(cls, path: Path) -> "RegionFile":
        parts = path.name.split(".")
        return cls(path=path, rx=int(parts[1]), rz=int(parts[2]))

    def chunk(self, cx: int, cz: int) -> dict | None:
        """Chunk por coordenada absoluta de chunk; None si no está generado."""
        local_x, local_z = cx & 31, cz & 31
        index = 4 * (local_x + local_z * 32)
        with self.path.open("rb") as fh:
            fh.seek(index)
            header = fh.read(4)
            if len(header) != 4:
                return None
            offset = int.from_bytes(header[:3], "big")
            if offset == 0:
                return None
            fh.seek(offset * 4096)
            (length,) = struct.unpack(">I", fh.read(4))
            (compression,) = struct.unpack(">B", fh.read(1))
            payload = fh.read(length - 1)
        if compression == 1:
            payload = gzip.decompress(payload)
        elif compression == 2:
            payload = zlib.decompress(payload)
        elif compression != 3:
            raise ValueError(f"compresión de chunk no soportada: {compression}")
        return NbtReader(payload).root()

    def chunk_coords(self) -> list[tuple[int, int]]:
        out = []
        with self.path.open("rb") as fh:
            table = fh.read(4096)
        for i in range(1024):
            if int.from_bytes(table[i * 4:i * 4 + 3], "big"):
                out.append((self.rx * 32 + (i % 32), self.rz * 32 + (i // 32)))
        return out


def unpack_bits(longs: list[int], bits: int, count: int) -> list[int]:
    """Desempaqueta el formato de 1.16+: los valores no cruzan el límite de un long."""
    if bits <= 0:
        return [0] * count
    per_long = 64 // bits
    mask = (1 << bits) - 1
    out = []
    for value in longs:
        raw = value & 0xFFFFFFFFFFFFFFFF
        for slot in range(per_long):
            if len(out) == count:
                return out
            out.append((raw >> (slot * bits)) & mask)
    while len(out) < count:
        out.append(0)
    return out
