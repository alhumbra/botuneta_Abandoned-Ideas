#!/usr/bin/env python3
"""Extract MSX disk images from MSXPLAYer 2005 single-file executables.

Static parser only: the input EXE is never executed.
Tested with MSX Magazine Permanent Preservation Edition 3 / Chaos Angels.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import struct
import sys
from pathlib import Path


# Table referenced by the MSXPLAYer decoding routine at VA 0x0044A0E0
# in the analyzed build (ProductVersion 0.11.5.44).
DECODE_KEY = bytes.fromhex("b4 d1 b4 bd b4 af b8 bd b1 bf bc b4 b0 bc ae dd")


def u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


class PEFile:
    def __init__(self, path: Path):
        self.path = path
        self.data = path.read_bytes()
        if self.data[:2] != b"MZ":
            raise ValueError("MZ header not found")
        pe = u32(self.data, 0x3C)
        if self.data[pe:pe + 4] != b"PE\0\0":
            raise ValueError("PE header not found")
        file_header = pe + 4
        section_count = u16(self.data, file_header + 2)
        optional_size = u16(self.data, file_header + 16)
        optional = file_header + 20
        magic = u16(self.data, optional)
        if magic not in (0x10B, 0x20B):
            raise ValueError("unsupported PE optional header")
        directories = optional + (96 if magic == 0x10B else 112)
        self.resource_rva = u32(self.data, directories + 16)
        section_table = optional + optional_size
        self.sections = []
        for index in range(section_count):
            off = section_table + 40 * index
            name = self.data[off:off + 8].split(b"\0", 1)[0].decode("ascii", "replace")
            virtual_size = u32(self.data, off + 8)
            virtual_address = u32(self.data, off + 12)
            raw_size = u32(self.data, off + 16)
            raw_offset = u32(self.data, off + 20)
            self.sections.append((name, virtual_address, virtual_size, raw_offset, raw_size))

    def rva_to_offset(self, rva: int) -> int:
        for _name, va, virtual_size, raw_offset, raw_size in self.sections:
            if va <= rva < va + max(virtual_size, raw_size):
                return raw_offset + (rva - va)
        raise ValueError(f"unmapped RVA 0x{rva:X}")

    def resources(self):
        if not self.resource_rva:
            return []
        base = self.rva_to_offset(self.resource_rva)
        found = []

        def entry_name(value: int):
            if not value & 0x80000000:
                return value
            off = base + (value & 0x7FFFFFFF)
            length = u16(self.data, off)
            return self.data[off + 2:off + 2 + length * 2].decode("utf-16le", "replace")

        def walk(relative: int, path: list):
            directory = base + relative
            count = u16(self.data, directory + 12) + u16(self.data, directory + 14)
            for index in range(count):
                entry = directory + 16 + index * 8
                name = entry_name(u32(self.data, entry))
                target = u32(self.data, entry + 4)
                if target & 0x80000000:
                    walk(target & 0x7FFFFFFF, path + [name])
                else:
                    descriptor = base + target
                    data_rva = u32(self.data, descriptor)
                    size = u32(self.data, descriptor + 4)
                    data_offset = self.rva_to_offset(data_rva)
                    found.append((path + [name], data_offset,
                                  self.data[data_offset:data_offset + size]))

        walk(0, [])
        return found


def decode_msxplayer_resource(blob: bytes) -> bytes | None:
    """Apply the exact inverse transformation used by MSXPLAYer 2005."""
    if len(blob) < 2 or blob[0] & 0xF0 != 0x80:
        return None
    control = blob[0]
    rotate = 4 - (control & 3)
    key_start = control & 0xFC
    output = bytearray(len(blob) - 1)
    for index, value in enumerate(blob[1:]):
        rotated = ((value >> rotate) | (value << (8 - rotate))) & 0xFF
        output[index] = rotated ^ DECODE_KEY[(key_start + index) & 0x0F]
    return bytes(output)


def disk_geometry(data: bytes):
    """Return a conservative FAT12/MSX disk geometry match, or None."""
    if len(data) < 512:
        return None
    bytes_per_sector = u16(data, 11)
    sectors_per_cluster = data[13]
    reserved = u16(data, 14)
    fats = data[16]
    root_entries = u16(data, 17)
    sectors = u16(data, 19) or u32(data, 32)
    media = data[21]
    sectors_per_fat = u16(data, 22)
    sides = u16(data, 26)
    expected = bytes_per_sector * sectors
    valid = (
        data[:3] in (b"\xEB\xFE\x90", b"\xEB\x3C\x90")
        and bytes_per_sector in (256, 512, 1024)
        and sectors_per_cluster in (1, 2, 4, 8, 16)
        and 1 <= reserved <= 16
        and 1 <= fats <= 4
        and root_entries and root_entries % 16 == 0
        and media >= 0xF0 and sectors_per_fat > 0
        and sides in (1, 2)
        and expected == len(data)
    )
    if not valid:
        return None
    return {
        "bytes_per_sector": bytes_per_sector,
        "sectors": sectors,
        "sides": sides,
        "size": expected,
        "media": f"0x{media:02X}",
    }


def safe_component(value) -> str:
    value = str(value)
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value or "unnamed"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Statically extract encrypted DRIVE resources from MSXPLAYer 2005 EXEs")
    parser.add_argument("exe", type=Path, help="MSXPLAYer-based .exe")
    parser.add_argument("-o", "--output", type=Path, default=Path("extracted_msx"),
                        help="output directory (default: extracted_msx)")
    parser.add_argument("--roms", action="store_true",
                        help="also decode SYSTEM resources as .rom files")
    parser.add_argument("--list", action="store_true",
                        help="inspect only; do not write extracted files")
    args = parser.parse_args()

    try:
        pe = PEFile(args.exe)
        resources = pe.resources()
    except (OSError, ValueError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    candidates = []
    for path, offset, blob in resources:
        if not path:
            continue
        resource_type = str(path[0]).upper()
        decoded = decode_msxplayer_resource(blob)
        if decoded is None:
            continue
        geometry = disk_geometry(decoded)
        if resource_type == "DRIVE" and geometry:
            suffix = ".dsk"
        elif resource_type == "SYSTEM" and args.roms:
            suffix = ".rom"
        else:
            continue
        identity = path[1] if len(path) > 1 else len(candidates) + 1
        stem = "drive" + f"{identity:02d}" if resource_type == "DRIVE" and isinstance(identity, int) else safe_component(identity)
        name = stem if stem.lower().endswith(suffix) else stem + suffix
        candidates.append((name, path, offset, decoded, geometry))

    print(f"Input: {args.exe}")
    print(f"SHA-256: {hashlib.sha256(pe.data).hexdigest()}")
    print(f"PE resources: {len(resources)}")
    if not candidates:
        print("No supported encrypted disk resources found.")
        return 1

    if not args.list:
        args.output.mkdir(parents=True, exist_ok=True)
    for name, path, offset, decoded, geometry in candidates:
        digest = hashlib.sha256(decoded).hexdigest()
        details = f"FAT/MSX {geometry}" if geometry else "decoded resource"
        print(f"{path!r} @ file+0x{offset:X} -> {name} ({len(decoded)} bytes, {details}, SHA-256 {digest})")
        if not args.list:
            (args.output / name).write_bytes(decoded)
    if not args.list:
        print(f"Wrote {len(candidates)} file(s) to: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
