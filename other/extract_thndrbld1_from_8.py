#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
#
# Thunder Blade 3D / 3DS extracted payload -> MAME Thunder Blade (Japan)
# thndrbld1 ROM restoration (31 verified ROM files; one Z80 sound ROM differs).
#
# ROM names/offset organization and reference checksums are based on:
#   MAME, src/mame/sega/segaxbd.cpp
#   https://github.com/mamedev/mame/blob/master/src/mame/sega/segaxbd.cpp
#   MAME source license: BSD-3-Clause; copyright-holders: Aaron Giles.
#   MAME's segaic16_road.cpp decoding method is also BSD-3-Clause.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its contributors
#    may be used to endorse or promote products derived from this software
#    without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
#
# ROM data itself remains the property of its respective rights holders.
# This tool does not download, bundle, or distribute ROM data.
#
# Usage: Put this script and the original file named "8" in the same folder;
#        run: python extract_thndrbld1_from_8.py
#        (optional input: python extract_thndrbld1_from_8.py file.bin)
# No third-party Python packages are needed.

from __future__ import annotations
import hashlib
import sys
import zlib
from pathlib import Path

# CRC32 / SHA1 in the MAME thndrbld1 set. Any mismatch is *not* written under
# an original MAME ROM name.
ROM_CHECKS = {
    'epr-11312.ic17': (0x3b974ed2, 'cf18a2d0f01643c747a884bf00e5b7037ba2e64a'),
    'epr-11304.ic58': (0xa90630ef, '8f29e020119b2243b1c95e15546af1773327ae85'),
    'epr-11305.ic63': (0x9ba3ef61, 'f75748b37ce35b0ef881804f73417643068dfbb2'),
    'epr-11306.ic57': (0x4b95f2b4, '9e0ff898a2af05c35db3551e52c7485748698c28'),
    'epr-11307.ic62': (0x2d6833e4, 'b39a744370014237121f0010d18897e63f7058cf'),
    'epr-11308.ic20': (0x7956c238, '4608225cfd6ea3d38317cbe970f26a5fc2f8e320'),
    'epr-11309.ic29': (0xc887f620, '644c47cc2cf75cbe489ea084c13c59d94631e83f'),
    'epr-11310.ic21': (0x5d9fa02c, '0ca71e35cf9740e38a52960f7d1ef96e7e1dda94'),
    'epr-11311.ic30': (0x483de21b, '871f0e856dcc81dcef1d9846261b3c011fa26dde'),
    'epr-11314.ic154': (0xd4f954a9, '93ee8cf8fcf4e1d0dd58329bba9b594431193449'),
    'epr-11315.ic153': (0x35813088, 'ea1ec982d1509efb26e7b6a150825a6a905efed9'),
    'epr-11316.ic152': (0x84290dff, 'c13fb6ef12a991f79a95072f953a02b5c992aa2d'),
    'epr-11323.ic90': (0x27e40735, '284ddb88efe741fb78199ea619c9b230ee689803'),
    'epr-11322.ic94': (0x10364d74, '393b19a972b5d8817ffd438f13ded73cd58ebe56'),
    'epr-11321.ic98': (0x8e738f58, '9f2dceebf01e582cf60f072ae411000d8503894b'),
    'epr-11320.ic102': (0xa95c76b8, 'cda62f3c25b9414a523c2fc5d109031ed560069e'),
    'epr-11327.ic91': (0xdeae90f1, 'c73c23bab949041242302cec13d653dcc71bb944'),
    'epr-11326.ic95': (0x29198403, '3ecf315a0e6b3ed5005f8bdcb2e2a884c8b176c7'),
    'epr-11325.ic99': (0xb9e98ae9, 'c4932e2590b10d54fa8ded94593dc4203fccc60d'),
    'epr-11324.ic103': (0x9742b552, '922032264d469e943dfbcaaf57464efc638fcf73'),
    'epr-11331.ic92': (0x3a2c042e, 'c296ff222d156d3bdcb42bef321831f502830fd6'),
    'epr-11330.ic96': (0xaa7c70c5, 'b6fea17392b7821b8b3bba78002f9c1604f09edc'),
    'epr-11329.ic100': (0x31b20257, '7ce10a94bce67b2d15d7b576b0f7d47389dc8948'),
    'epr-11328.ic104': (0xda39e89c, '526549ce9112754c82743552eeebec63fe7ad968'),
    # These four are the JAPAN thndrbld1 set, NOT the newer thndrbld set.
    'epr-11335.ic93': (0xf19b3e86, '40e8ba10cd5020782b82279974d13330a9c015e5'),
    'epr-11334.ic97': (0x348f91c7, '03da6a4fee1fdea76058be4bc5ffcde7a79e5948'),
    'epr-11333.ic101': (0x05a2333f, '70f213945fa7fe056fe17a02558638e87f2c001e'),
    'epr-11332.ic105': (0xdc089ec6, 'd72390c45138a507e79af112addbc015560fc248'),
    'epr-11313.ic29': (0x6a56c4c3, 'c1b8023cb2ba4e96be052031c24b6ae424225c71'),
    'epr-11317.ic11': (0xd4e7ac1f, 'ec5d6e4949938adf56e5613801ae56ff2c3dede5'),
    'epr-11318.ic12': (0x70d3f02c, '391aac2bc5673e06150de27e19c7c6359da8ca82'),
    'epr-11319.ic13': (0x50d9242e, 'a106371bf680c3088ec61f07fc5c4ce467973c15'),
}

BASE = 0x162464
EXPECTED_SIZE = 0x572000


def extract_tiles(data: bytes):
    """Undo the 3DS pre-decoding: 8x8, 4-bit pixels, lo nibble first.

    MAME ROMs are three separate 1-bit 8x8 bitplanes (8 bytes/tile/plane).
    """
    if len(data) != 0x40000:
        raise ValueError('Tile data length is incorrect')
    lut = [tuple((((v >> 0) >> plane) & 1) * 2 + (((v >> 4) >> plane) & 1)
                 for v in range(256)) for plane in range(3)]
    out = [bytearray(0x10000) for _ in range(3)]
    for tile in range(8192):
        inp = tile * 32
        dest = tile * 8
        for y in range(8):
            i = inp + y * 4
            a, b, c, d = data[i:i+4]
            for plane in range(3):
                l = lut[plane]
                out[plane][dest+y] = (l[a] << 6) | (l[b] << 4) | (l[c] << 2) | l[d]
    return [bytes(x) for x in out]


def extract_road(data: bytes):
    """Inverse of unpacked road pixel data, according to Sega road bitplanes.

    4-bit road markers in this 3DS image: {1..4} -> {0..3}, 0 -> 3
    (the 0 marker indicates a special stripe, but same two low bits).
    Each of two 256x512 decoded pictures in the supplied file is identical.
    Restore two planes of 0x4000 bytes each and repeat the planes once.
    """
    if len(data) != 0x40000 or data[:0x20000] != data[0x20000:]:
        raise ValueError('Unexpected road data format')
    p0, p1 = bytearray(0x4000), bytearray(0x4000)
    src = memoryview(data)
    for pos in range(0x4000):
        v0 = v1 = 0
        for x in range(8):
            pix = (src[pos*8+x] - 1) & 3
            v0 = (v0 << 1) | (pix & 1)
            v1 = (v1 << 1) | ((pix >> 1) & 1)
        p0[pos] = v0
        p1[pos] = v1
    half = bytes(p0) + bytes(p1)
    return half + half


def main():
    path = Path(sys.argv[1]).resolve() if len(sys.argv) >= 2 else Path(__file__).resolve().parent / '8'
    dest = path.parent
    if not path.is_file():
        raise SystemExit(f'Input file not found: {path}')
    b = path.read_bytes()
    if len(b) != EXPECTED_SIZE:
        raise SystemExit(f'Unexpected size: 0x{len(b):X} (expected 0x{EXPECTED_SIZE:X})')
    if zlib.crc32(b) != 0xbe129c67:
        print('[WARNING] Input CRC differs from the analyzed file; individual CRC/SHA1 checks remain mandatory.')

    outputs = {}
    # 4 interleaved 68000 pairs (thndrbld1).
    pairs = [
        ('epr-11304.ic58', 'epr-11305.ic63'),
        ('epr-11306.ic57', 'epr-11307.ic62'),
        ('epr-11308.ic20', 'epr-11309.ic29'),
        ('epr-11310.ic21', 'epr-11311.ic30'),
    ]
    for idx, names in enumerate(pairs):
        start = BASE + 0x40000 * idx
        block = b[start:start+0x40000]
        if len(block) != 0x40000:
            raise SystemExit('Truncated 68000 program region')
        outputs[names[0]] = block[0::2]
        outputs[names[1]] = block[1::2]

    # Sound Z80 occupies the 0x10000 region immediately after the 68000 code.
    # This supplied 3DS/M2 build differs from MAME epr-11312.ic17.
    # Do NOT mislabel an unverified sound file as an original MAME ROM.
    sound = b[0x262464:0x272464]
    if zlib.crc32(sound) == 0x3b974ed2:
        outputs['epr-11312.ic17'] = sound
    else:
        candidate_name = f'soundcpu_candidate_crc{zlib.crc32(sound):08x}.bin'
        (dest / candidate_name).write_bytes(sound)
        print(f'[UNMATCHED] Z80 sound CPU: CRC32={zlib.crc32(sound):08X}; '
              'MAME thndrbld1 expects 3B974ED2.')
        print('            Candidate saved separately, not as an original MAME ROM.')

    tiles = extract_tiles(b[0x272464:0x2b2464])
    for name, plane in zip(('epr-11314.ic154','epr-11315.ic153','epr-11316.ic152'), tiles):
        outputs[name] = plane

    sprite_names = [
        ['epr-11323.ic90', 'epr-11322.ic94', 'epr-11321.ic98', 'epr-11320.ic102'],
        ['epr-11327.ic91', 'epr-11326.ic95', 'epr-11325.ic99', 'epr-11324.ic103'],
        ['epr-11331.ic92', 'epr-11330.ic96', 'epr-11329.ic100', 'epr-11328.ic104'],
        ['epr-11335.ic93', 'epr-11334.ic97', 'epr-11333.ic101', 'epr-11332.ic105'],
    ]
    for group_idx, group in enumerate(sprite_names):
        start = 0x2b2464 + group_idx * 0x80000
        src = b[start:start + 0x80000]
        for lane, name in enumerate(group):
            outputs[name] = src[lane::4]

    outputs['epr-11313.ic29'] = extract_road(b[0x4b2464:0x4f2464])
    for i, name in enumerate(('epr-11317.ic11','epr-11318.ic12','epr-11319.ic13')):
        st = 0x4f2464 + i*0x20000
        outputs[name] = b[st:st+0x20000]

    # Verify all data BEFORE writing even a single original ROM filename.
    mismatch = []
    for name, content in outputs.items():
        crc, sha1 = ROM_CHECKS[name]
        got_crc, got_sha1 = zlib.crc32(content), hashlib.sha1(content).hexdigest()
        if got_crc != crc or got_sha1 != sha1:
            mismatch.append(f'{name}: crc={got_crc:08X} sha1={got_sha1}')
    if mismatch:
        raise SystemExit('Verification failed. No MAME ROMs written:\n'+'\n'.join(mismatch))

    for name, content in outputs.items():
        (dest / name).write_bytes(content)
        print(f'[OK] {name:<20} {len(content):6d} bytes  CRC32={zlib.crc32(content):08X}  SHA1={hashlib.sha1(content).hexdigest()}')
    print(f'\nVerified: {len(outputs)}/{len(ROM_CHECKS)} MAME thndrbld1 ROMs')
    print('Note: thndrbld (upright FD1094) is a DIFFERENT ROM set.')
    print('MAME thndrbld1 cannot pass audit until epr-11312.ic17 is restored.')

if __name__ == '__main__':
    main()
