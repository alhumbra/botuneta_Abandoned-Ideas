#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: BSD-3-Clause
#
# After Burner II (aburner2) - Nintendo 3DS CRO ROM restoration utility.
#
# Copyright (c) 2026. Released under the BSD 3-Clause License.
# See https://opensource.org/license/BSD-3-clause
#
# Based on verified ROM layouts and hashes documented by the MAME project.
# MAME's source-code license is BSD-3-Clause; see:
# https://github.com/mamedev/mame/blob/master/COPYING
# https://github.com/mamedev/mame/blob/master/src/mame/sega/segaxbd.cpp
# https://github.com/mamedev/mame/blob/master/src/mame/sega/segaic16_road.cpp
#
# The extraction/transformation code below is independently authored.
# Copyrights in the original arcade ROM content remain with the respective
# rights holders. No ROM data is included in this script.
#
# USAGE:
#   Place this .py next to the legally obtained source file "8" and run:
#       python aburner2_extract.py
#   Or supply the original file and optionally an output directory:
#       python aburner2_extract.py --output /path/to/directory
#
# Restores 24 MAME aburner2 ROMs byte-for-byte (CRC32/SHA1 verified).
# Also outputs 4 RAW, UNVERIFIED sound-ROM CANDIDATES under MAME filenames:
# one Z80 program and three PCM samples. They do NOT match MAME hashes.
# These are NOT confirmed authentic ROMs; MAME may reject or fail to use them.

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import zlib

# MAME aburner2 definitions: file name -> (size, CRC32, SHA1)
EXPECTED = {
    'epr-11107.58': (0x20000, '6d87bab7', 'ab34fe78f1f216037b3e3dca3e61f1b31c05cedf'),
    'epr-11108.63': (0x20000, '202a3e1d', 'cf2018bbad366de4b222eae35942636ca68aa581'),
    'epr-11109.20': (0x20000, '85a0fe07', '5a3a8fda6cb4898cfece4ec865b81b9b60f9ad55'),
    'epr-11110.29': (0x20000, 'f3d6797c', '17487b89ddbfbcc32a0b52268259f1c8d10fd0b2'),
    'epr-11115.154': (0x10000, 'e8e32921', '30a96e6b514a475c778296228ba5b6fb96b211b0'),
    'epr-11114.153': (0x10000, '2e97f633', '074125c106dd00785903b2e10cd7e28d5036eb60'),
    'epr-11113.152': (0x10000, '36058c8c', '52befe6c6c53f10b6fd4971098abc8f8d3eef9d4'),
    'mpr-10932.90': (0x20000, 'cc0821d6', '22e84419a585209bbda1466d2180504c316a9b7f'),
    'mpr-10934.94': (0x20000, '4a51b1fa', '2eed018a5a1e935bb72b6f440a794466a1397dc5'),
    'mpr-10936.98': (0x20000, 'ada70d64', 'ba6203b0fdb4c4998b7be5b446eb8354751d553a'),
    'mpr-10938.102': (0x20000, 'e7675baf', 'aa979319a44c0b18c462afb5ca9cdeed2292c76a'),
    'mpr-10933.91': (0x20000, 'c8efb2c3', 'ba31da93f929f2c457e60b2099d5a1ba6b5a9f48'),
    'mpr-10935.95': (0x20000, 'c1e23521', '5e95f3b6ff9f4caca676eaa6c84f1200315218ea'),
    'mpr-10937.99': (0x20000, 'f0199658', 'cd67504fef53f637a3b1c723c4a04148f88028d2'),
    'mpr-10939.103': (0x20000, 'a0d49480', '6c4234456bc09ae771beec284d7aa21ebe474f6f'),
    'epr-11103.92': (0x20000, 'bdd60da2', '01673837c5ad84fa087728a05549ac01542ef4e9'),
    'epr-11104.96': (0x20000, '06a35fce', 'c39ae02fc8246e883c4f4c320f668ce6ca9c845a'),
    'epr-11105.100': (0x20000, '027b0689', 'c704c79faadb5e445fd3bd9281683b09831782d2'),
    'epr-11106.104': (0x20000, '9e1fec09', '6cc47d86852b988bfcd64cb4ed7d832c683e3114'),
    'epr-11116.93': (0x20000, '49b4c1ba', '5419f49f091e386eead4ccf5e03f12769e278179'),
    'epr-11117.97': (0x20000, '821fbb71', 'be2366d7b4a3a2543ba5024f0e258f1bc43caec8'),
    'epr-11118.101': (0x20000, '8f38540b', '1fdfb157d1aca96cb635bd3d64f94545eb88c133'),
    'epr-11119.105': (0x20000, 'd0343a8e', '8c0c0addb6dfd0ea04c3900a9f7f7c731ca6e9ea'),
    'epr-10922.40': (0x10000, 'b49183d4', '71d87bfbce858049ccde9597ab15575b3cdba892'),
    # Sound-ROM targets. The raw candidate data does NOT match these hashes:
    'epr-11112.17': (0x10000, 'd777fc6d', '46ce1c3875437044c0a172960d560d6acd6eaa92'),
    'mpr-10931.11': (0x20000, '9209068f', '01f3dda1c066d00080c55f2c86c506b6b2407f98'),
    'mpr-10930.12': (0x20000, '6493368b', '328aff19ff1d1344e9115f519d3962390c4e5ba4'),
    'epr-11102.13': (0x20000, '6c07c78d', '3868b1824f43e4f2b4fbcd9274bfb3000c889d12'),
}

SPRITE_NAMES = (
    ('mpr-10932.90', 'mpr-10934.94', 'mpr-10936.98', 'mpr-10938.102'),
    ('mpr-10933.91', 'mpr-10935.95', 'mpr-10937.99', 'mpr-10939.103'),
    ('epr-11103.92', 'epr-11104.96', 'epr-11105.100', 'epr-11106.104'),
    ('epr-11116.93', 'epr-11117.97', 'epr-11118.101', 'epr-11119.105'),
)


def verify(name: str, data: bytes) -> None:
    size, expected_crc, expected_sha1 = EXPECTED[name]
    crc = f'{zlib.crc32(data):08x}'
    sha1 = hashlib.sha1(data).hexdigest()
    if (len(data), crc, sha1) != (size, expected_crc, expected_sha1):
        raise ValueError(
            f'{name}: verification failed: size=0x{len(data):x}, '
            f'CRC={crc}, SHA1={sha1}; '
            f'expected 0x{size:x} / {expected_crc} / {expected_sha1}'
        )


def restore(blob: bytes):
    """Yield (MAME filename, exactly restored ROM bytes)."""
    if len(blob) != 0x4E5000 or blob[0x80:0x84] != b'CRO0':
        raise ValueError('Input does not match the analyzed 3DS CRO file 8(2).')

    # Both 68000 program streams are stored even/odd-byte interleaved.
    for base, pair in (
        (0x14F994, ('epr-11107.58', 'epr-11108.63')),
        (0x18F994, ('epr-11109.20', 'epr-11110.29')),
    ):
        region = blob[base:base + 0x40000]
        for lane, name in enumerate(pair):
            yield name, region[lane::2]

    # 8192 x (8x8 pixels): four-bit packed 3DS graphics -> original
    # three independent 1-bpp tile ROM planes. Low nibble is first pixel.
    tiles = blob[0x1DFDBC:0x21FDBC]
    for plane, name in enumerate(('epr-11115.154', 'epr-11114.153', 'epr-11113.152')):
        lookup = bytes(
            (((v >> plane) & 1) << 1) | ((v >> (plane + 4)) & 1)
            for v in range(256)
        )
        rom = bytes(
            (lookup[tiles[i]] << 6) | (lookup[tiles[i + 1]] << 4)
            | (lookup[tiles[i + 2]] << 2) | lookup[tiles[i + 3]]
            for i in range(0, len(tiles), 4)
        )
        yield name, rom

    # The original X-board sprite region is four ROMs interleaved by byte
    # per 0x80000 bank, so separating each byte lane restores originals.
    for bank, names in enumerate(SPRITE_NAMES):
        start = 0x21FDBC + bank * 0x80000
        region = blob[start:start + 0x80000]
        for lane, name in enumerate(names):
            yield name, region[lane::4]

    # Road graphics are stored as expanded 512x512 (one byte/pixel) in
    # the 3DS image. Remap M2 palette codes to the two MAME road bitplanes.
    # Its fourth graphics code represents road code 3 in source ROM.
    road = blob[0x41FDBC:0x45FDBC]
    remap = (3, 0, 1, 2, 3)
    if any(pixel >= len(remap) for pixel in road):
        raise ValueError('Road graphics contain an unknown pixel code.')
    packed = bytearray(0x10000)
    for y in range(512):
        source = y * 512
        offset = (y % 256) * 0x40 + (y // 256) * 0x8000
        for x in range(0, 512, 8):
            p0 = p1 = 0
            for bit in range(8):
                value = remap[road[source + x + bit]]
                p0 |= (value & 1) << (7 - bit)
                p1 |= ((value >> 1) & 1) << (7 - bit)
            packed[offset + x // 8] = p0
            packed[offset + 0x4000 + x // 8] = p1
    yield 'epr-10922.40', bytes(packed)


# Raw sound data detected in the 3DS CRO. These four candidate regions are
# NOT verified against MAME; the start offsets are absolute file offsets.
# Filename, source offset, length
SOUND_CANDIDATES = (
    ('epr-11112.17', 0x1CF994, 0x10000),  # Z80 program candidate
    ('mpr-10931.11', 0x45FDBC, 0x20000),  # PCM candidate 1
    ('mpr-10930.12', 0x47FDBC, 0x20000),  # PCM candidate 2
    ('epr-11102.13', 0x49FDBC, 0x20000),  # PCM candidate 3
)


def sound_candidates(blob: bytes):
    """Yield (MAME filename, raw UNVERIFIED candidate data, source offset)."""
    for name, offset, length in SOUND_CANDIDATES:
        payload = blob[offset:offset + length]
        if len(payload) != length or len(payload) != EXPECTED[name][0]:
            raise ValueError(f'Sound candidate {name} is out of range.')
        yield name, payload, offset


def write_without_overwrite(destination: Path, payload: bytes) -> str:
    """Write payload, but never silently replace any different existing file."""
    if destination.exists():
        if destination.read_bytes() == payload:
            return 'SKIP (already present)'
        raise FileExistsError(f'Refusing to overwrite a different file: {destination}')
    destination.write_bytes(payload)
    return 'WRITE'


def main() -> int:
    parser = argparse.ArgumentParser(
        description='After Burner II ROM extractor: 24 verified ROMs + 4 unverified sound candidates'
    )
    parser.add_argument('--output', type=Path, default=None,
                        help='Output folder (default: same folder as the source file "8")')
    args = parser.parse_args()

    # The real source filename is exactly "8" (no extension, no "(2)").
    input_file = Path(__file__).resolve().parent / '8'
    if not input_file.is_file():
        parser.error(f'Input file "8" not found beside the script: {input_file}')

    data = input_file.read_bytes()
    # Complete all hash checks before writing any output.
    verified = list(restore(data))
    unverified = list(sound_candidates(data))
    for name, payload in verified:
        verify(name, payload)
    all_names = [name for name, _ in verified] + [name for name, _, _ in unverified]
    if len(all_names) != len(EXPECTED) or set(all_names) != set(EXPECTED):
        raise ValueError('Internal error: ROM name set or number does not match MAME.')

    output_dir = args.output if args.output is not None else input_file.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print('=== Verified MAME ROMs (CRC32 and SHA1 match) ===')
    for name, payload in verified:
        action = write_without_overwrite(output_dir / name, payload)
        print(f'[OK]   {name:18} CRC32={zlib.crc32(payload):08x}  {action}')

    print('\n=== Unverified sound-ROM candidates (raw data, hashes DO NOT match) ===')
    for name, payload, offset in unverified:
        crc = f'{zlib.crc32(payload):08x}'
        sha1 = hashlib.sha1(payload).hexdigest()
        _, expected_crc, expected_sha1 = EXPECTED[name]
        matches = crc == expected_crc and sha1 == expected_sha1
        action = write_without_overwrite(output_dir / name, payload)
        label = 'OK' if matches else 'UNVERIFIED'
        print(f'[{label}] {name:18} input=0x{offset:06X} size=0x{len(payload):05X} '
              f'CRC32={crc} (MAME={expected_crc})  {action}')

    print(f'\nFinished: {len(verified)} hash-verified + {len(unverified)} '
          f'unverified sound candidates = {len(all_names)} files.')
    print('WARNING: 4 audio candidate files have MAME ROM filenames but are NOT '
          'authenticity-verified. MAME may refuse to load them, or run incorrectly.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)
