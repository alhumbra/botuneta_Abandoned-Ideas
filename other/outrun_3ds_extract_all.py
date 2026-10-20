#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
#
# Out Run (3DS CRO0 module) -> MAME "outrun" ROM extractor
#
# License notice for MAME-referenced hardware formats/decoding:
#   MAME source: src/mame/sega/segaorun.cpp, segaic16_road.cpp
#   Copyright (c) Aaron Giles and the respective MAME contributors.
#   License: BSD-3-Clause (https://opensource.org/licenses/BSD-3-Clause)
#
#   Redistribution and use in source and binary forms, with or without
#   modification, are permitted provided that the following conditions are met:
#   1. Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#   2. Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#   3. Neither the name of the copyright holder nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
#   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
#   THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
#   PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
#   CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
#   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
#   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
#   OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
#   WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
#   OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#   ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# This script does not contain MAME game ROMs. Rights to the input ROM data
# remain with their respective owners. Works exclusively on user-supplied data.
#
# Usage: Place alongside the original file named "8" (or "8(3)") and run:
#     python outrun_3ds_extract_all.py
# Optional:  python outrun_3ds_extract_all.py --output OUTPUT_DIRECTORY
#
# All 31 target entries are extracted: 26 MAME-verbatim files plus 4 nonmatching
# maincpu images and 1 nonmatching PCM image. Two alternative maincpu images
# are preserved separately (8 maincpu files total).
# Nonmatching maincpu data are ONLY written inside maincpu/primary and
# maincpu/alternate, not among the CRC-verified ROMs.
# The nonmatching PCM has a .3ds_unmatched.bin suffix.
# The tool cannot make a fully working MAME outrun romset from this input alone.

from pathlib import Path
import argparse
import hashlib
import zlib

BASE = 0xD7498

# ROM name -> (CRC32, SHA1) expected by MAME for "outrun" (Rev B).
EXPECTED = {
    'epr-10327a.76': (0xe28a5baf, 'f715bde96c73ed47035acf5a41630fdeb41bb2f9'),
    'epr-10329a.58': (0xda131c81, '57d5219bd0e2fd886217e37e8773fd76be9b40eb'),
    'epr-10328a.75': (0xd5ec5e5d, 'a4e3cfca4d803e72bc4fcf91ab00e21bf3f8959f'),
    'epr-10330a.57': (0xba9ec82a, '2136c9572e26b7ae6de402c0cd53174407cc6018'),
    'opr-10268.99': (0x95344b04, 'b3480714b11fc49b449660431f85d4ba92f799ba'),
    'opr-10232.102': (0x776ba1eb, 'e3477961d19e694c97643066534a1f720e0c4327'),
    'opr-10267.100': (0xa85bb823, 'a7e0143dee5a47e679fd5155e58e717813912692'),
    'opr-10231.103': (0x8908bcbf, '8e1237b640a6f26bdcbfd5e201dadb2687c4febb'),
    'opr-10266.101': (0x9f6f1a74, '09164e858ebeedcff4d389524ddf89e7c216dcae'),
    'opr-10230.104': (0x686f5e50, '03697b892f911177968aa40de6c5f464eb0258e7'),
    'mpr-10371.9': (0x7cc86208, '21320f945f7c8e990c97c9b1232a0f4b6bd00f8f'),
    'mpr-10373.10': (0xb0d26ac9, '3a9ce8547cd43b7b04abddf9a9ab5634e0bbfaba'),
    'mpr-10375.11': (0x59b60bd7, 'e5d8c67e020608edd24ba87b7687b2ac2483ee7f'),
    'mpr-10377.12': (0x17a1b04a, '9f7210cb4153ac9029a785dcd4b45f4513a4b008'),
    'mpr-10372.13': (0xb557078c, 'a3746a2da077a8df4932348f650a061f413e8430'),
    'mpr-10374.14': (0x8051e517, '9c8509fbed170b4ac74c169da573393e54774f49'),
    'mpr-10376.15': (0xf3b8f318, 'a5f2532613f33a64441e0f75443c10ba78dccc6e'),
    'mpr-10378.16': (0xa1062984, '4399030a155caf71f2dec7f75c4b65531ab53576'),
    'opr-10186.47': (0x22794426, 'a554d4b68e71861a0d0da4d031b3b811b246f082'),
    'opr-10185.11': (0x22794426, 'a554d4b68e71861a0d0da4d031b3b811b246f082'),
    'epr-10187.88': (0xa10abaa9, '01c8a819587a66d2ee4d255656e36fa0904377b0'),
    'opr-10193.66': (0xbcd10dde, '417ce1d7242884640c5b14f4db8ee57cde7d085d'),
    'opr-10192.67': (0x770f1270, '686bdf44d45c1d6002622f6658f037735382f3e0'),
    'opr-10191.68': (0x20a284ab, '7c9027416d4122791ba53782fe2230cf02b7d506'),
    'opr-10190.69': (0x7cab70e2, 'a3c581d2b438630d0d4c39481dcfd85681c9f889'),
    'opr-10188.71': (0xbad30ad9, 'f70dd3a6362c314adef313b064102f7a250401c8'),
}

# MAME maincpu Rev B expected checksums; data in the 3DS source do not match.
MAINCPU = (
    ('epr-10380b.133', 0x1f6cadad, '31e870f307f44eb4f293b607123b623beee2bc3c'),
    ('epr-10382b.118', 0xc4c3fa1a, '69236cf9f27691dee290c79db1fc9b5e73ea77d7'),
    ('epr-10381b.132', 0xbe8c412b, 'bf3ff05bbf81bdd44567f3b9bb4919ed4a499624'),
    ('epr-10383b.117', 0x10a2014a, '1970895145ad8b5735f66ed8c837d9d453ce9b23'),
)

# Original target CRC/SHA1 for the missing PCM ROM.
PCM_NAME = 'opr-10189.70'
PCM_EXPECTED = (0x01366b54, 'f467a6b807694d5832a985f5381c170d24aaee4e')
MAINCPU_SECTIONS = (('primary', 0x0D7498), ('alternate', 0x31D620))


def sha1(data):
    return hashlib.sha1(data).hexdigest()


def split_tiles(b):
    """Invert 3DS packed 4-bpp tile pixels to original 3 planar ROM streams."""
    src = memoryview(b)[0x15F498:0x19F498]
    if len(src) != 0x40000:
        raise ValueError('Tile section truncated')
    planes = [bytearray(0x10000) for _ in range(3)]
    # 8192 tiles, each 8x8 pixels, 2 pixels per source byte.
    # Source: low nibble = left pixel, high nibble = right pixel.
    for tile in range(8192):
        src_pos = tile * 32
        for y in range(8):
            packed = src[src_pos + y * 4:src_pos + y * 4 + 4]
            row_out = [0, 0, 0]
            for val in packed:
                for pixel in (val & 0x0f, val >> 4):
                    for bit in range(3):
                        row_out[bit] = (row_out[bit] << 1) | ((pixel >> bit) & 1)
            for bit in range(3):
                planes[bit][tile * 8 + y] = row_out[bit]
    names = [
        ('opr-10268.99', 'opr-10232.102'),
        ('opr-10267.100', 'opr-10231.103'),
        ('opr-10266.101', 'opr-10230.104'),
    ]
    for plane, files in zip(planes, names):
        yield files[0], bytes(plane[:0x8000])
        yield files[1], bytes(plane[0x8000:])


def unpack_road(b):
    """Invert 3DS road pixel indices into two original 1bpp bitplanes."""
    src = memoryview(b)[0x29F498:0x2BF498]
    if len(src) != 0x20000:
        raise ValueError('Road section truncated')
    plane0 = bytearray(0x4000)
    plane1 = bytearray(0x4000)
    # Original: 256 lines * 512 pixels, 2 planar bits/pixel.
    # 3DS indices 0,1,2,3,4 map to original 3,0,1,2,3.
    for y in range(256):
        for xbyte in range(64):
            a = c = 0
            off = y * 512 + xbyte * 8
            for p in src[off:off + 8]:
                value = (p + 3) % 4 if p < 4 else 3
                a = (a << 1) | (value & 1)
                c = (c << 1) | ((value >> 1) & 1)
            plane0[y * 64 + xbyte] = a
            plane1[y * 64 + xbyte] = c
    return bytes(plane0 + plane1)


def extract_known(b):
    # Sub 68000: 16-bit big-endian, split into even/odd 8-bit ROM lanes.
    sub_names = [('epr-10327a.76', 'epr-10329a.58'),
                 ('epr-10328a.75', 'epr-10330a.57')]
    for i, (even, odd) in enumerate(sub_names):
        block = b[0x117498 + i * 0x20000:0x117498 + (i + 1) * 0x20000]
        yield even, block[0::2]
        yield odd, block[1::2]
    # Tile pixels, restored from chunky 4bpp to planar 3bpp.
    yield from split_tiles(b)
    # Sprites: four 8-bit interleaved lanes, two 512-KiB groups.
    sprite_names = [
        ('mpr-10371.9','mpr-10373.10','mpr-10375.11','mpr-10377.12'),
        ('mpr-10372.13','mpr-10374.14','mpr-10376.15','mpr-10378.16'),
    ]
    for i, group in enumerate(sprite_names):
        data = b[0x19F498 + i * 0x80000:0x19F498 + (i + 1) * 0x80000]
        for j, name in enumerate(group):
            yield name, data[j::4]
    # Road ROMs are two physically identical 32-KiB chips.
    road = unpack_road(b)
    yield 'opr-10186.47', road
    yield 'opr-10185.11', road
    # Sound CPU Z80 binary is unchanged.
    yield 'epr-10187.88', b[0x157498:0x15F498]
    # PCM ROMs. The last original bad dump has stuck bit 5=1.
    for i,name in enumerate(['opr-10193.66','opr-10192.67','opr-10191.68',
                             'opr-10190.69']):
        yield name, b[0x2DF498 + i*0x8000:0x2DF498 + (i+1)*0x8000]
    pcm_last = b[0x307498:0x30F498]
    yield 'opr-10188.71', bytes(value | 0x20 for value in pcm_last)


def split_maincpu(b, section):
    """Split each 256-KiB 68000 program image into four 64-KiB ROM lanes."""
    block = b[section:section + 0x40000]
    if len(block) != 0x40000:
        raise ValueError('Truncated maincpu section at 0x{:X}'.format(section))
    lanes = (block[:0x20000:2], block[1:0x20000:2],
             block[0x20000::2], block[0x20001::2])
    return [(entry[0], data) for entry, data in zip(MAINCPU, lanes)]


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def matching(name, data, expected):
    return crc32(data) == expected[0] and sha1(data) == expected[1]


def main():
    parser = argparse.ArgumentParser(
        description='Extract all Out Run 3DS CRO0 ROM areas: 26 verified and 5 nonmatching (plus alternate maincpu)')
    parser.add_argument('input', nargs='?', help='Original 3DS CRO0 file; auto-detect 8 or 8(3) next to this script')
    parser.add_argument('--output', type=Path,
                        help='Output directory (default: directory containing the script)')
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    if args.input is not None:
        src_path = Path(args.input).resolve()
    else:
        src_path = next((script_dir / name for name in ('8', '8(3)')
                         if (script_dir / name).is_file()), None)
    if src_path is None or not src_path.is_file():
        parser.error('Source not found. Put file 8 (or 8(3)) next to the script.')
    b = src_path.read_bytes()
    if len(b) != 0x3AB000 or b[0x80:0x84] != b'CRO0':
        parser.error(f'Wrong input size or CRO0 signature: {src_path} ({len(b):#x} bytes)')

    # Validate 26 MAME-verbatim ROMs before writing any data.
    verified = list(extract_known(b))
    if len(verified) != 26 or len(EXPECTED) != 26 or set(n for n, _ in verified) != set(EXPECTED):
        raise RuntimeError('Internal error: wrong MAME ROM list or duplicate ROM name')
    for name, data in verified:
        if not matching(name, data, EXPECTED[name]):
            raise RuntimeError(f'CRC32/SHA1 mismatch for {name}: {crc32(data):08x} {sha1(data)}')

    # Include both distinct maincpu variants (4 x 64-KiB each).
    mains = [(variant, split_maincpu(b, off)) for variant, off in MAINCPU_SECTIONS]
    pcm = b[0x2FF498:0x307498]
    if len(pcm) != 0x8000:
        raise RuntimeError('Truncated PCM section')

    # Never mislabel nonmatching data as verified. If source format changes and
    # one of these unexpectedly matches MAME, stop so it can be handled properly.
    for variant, lanes in mains:
        for (name, target_crc, target_sha), (got_name, data) in zip(MAINCPU, lanes):
            if got_name != name or len(data) != 0x10000:
                raise RuntimeError('Invalid maincpu lane size/name')
            if matching(name, data, (target_crc, target_sha)):
                print(f'[NOTE] {variant}/{name} unexpectedly matches MAME!')
    if matching(PCM_NAME, pcm, PCM_EXPECTED):
        print('[NOTE] PCM unexpectedly matches MAME!')

    output = (args.output or script_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    print('Input:', src_path)
    print('Output:', output)
    print('')

    for name, data in verified:
        dest = output / name
        dest.write_bytes(data)
        print(f'[MATCH] {name:<20} CRC32={crc32(data):08x}')

    print('\n[maincpu: 3DS-modified variants, separated from MAME-verified ROMs]')
    for variant, lanes in mains:
        directory = output / 'maincpu' / variant
        directory.mkdir(parents=True, exist_ok=True)
        for (name, target_crc, target_sha), (_, data) in zip(MAINCPU, lanes):
            (directory / name).write_bytes(data)
            status = 'MATCH' if matching(name, data, (target_crc, target_sha)) else 'MODIFIED'
            print(f'[{status}] maincpu/{variant}/{name:<18} CRC32={crc32(data):08x} (MAME={target_crc:08x})')

    # Keep an explicit suffix to prevent the modified PCM from being mistaken
    # for the authentic MAME chip even though it is not a maincpu ROM.
    pcm_out = output / (PCM_NAME + '.3ds_unmatched.bin')
    pcm_out.write_bytes(pcm)
    pcm_status = 'MATCH' if matching(PCM_NAME, pcm, PCM_EXPECTED) else 'MODIFIED'
    print(f'[{pcm_status}] {pcm_out.name:<30} CRC32={crc32(pcm):08x} (MAME={PCM_EXPECTED[0]:08x})')

    print('\nDone: 26 MAME-verified files (root), 4+4 maincpu files'
          ' (maincpu/primary + maincpu/alternate), 1 modified PCM (root).')
    print('31 original ROM slots covered. Only 26/31 match MAME checksums.')
    print('This does NOT create a complete MAME-compatible outrun set.')


if __name__ == '__main__':
    main()
