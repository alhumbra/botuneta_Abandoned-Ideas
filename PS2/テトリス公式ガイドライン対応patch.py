# -*- coding: utf-8 -*-
"""Tetris (set 2, Japan, System 16B) tetris2d の 公式ガイドライン対応版を、zipに差分パッチを当てて作ります。
使い方: MAMEのtetris2dのzip(元のファイルのもの)を、このファイルと同じフォルダに置いて(「テトリスの素バージョン抽出.py」で作ったフォルダが隣にあれば、そのzipも使います)、ダブルクリックで実行します。
出力: 「テトリス公式ガイドライン対応版」フォルダの中に tetris2d.zip と 改変の説明.txt。CRCは強制しません。
このファイルの末尾の「#|」で始まる部分は、差分パッチと説明文です(消さないでください)。"""
# ======================================================================
# 共通部分(両方のツールで同じ)
# ======================================================================
import os, sys, zlib, hashlib, zipfile

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

def say(s=""): print(s)
def crc32(b): return zlib.crc32(b) & 0xFFFFFFFF
def sha1(b): return hashlib.sha1(b).hexdigest()

# 入力ファイル(PS2「SEGA AGES 2500 Vol.28 テトリスコレクション」のディスクの中身)
NEED = ["tetrisd.p94", "tet_dec.p00", "tetris.scr", "tetris.obj", "tetris.snd"]

# MAME の定義(segas16b.cpp)にある tetris2d の ROM: 名前 -> (大きさ, CRC32, SHA1)
EXPECT = {
    "bootleg_epr-12193.a7": (65536, "e8c59f9d", "88aa9c7868b914e5cbd3fc0def5d61d5d5c37d21"),
    "bootleg_epr-12192.a5": (65536, "8ff44f5f", "a590d695c7d802ad7afe77990dd15775c03c727a"),
    "epr-12165.b9":  (65536, "62640221", "c311d3847a981d0e1609f9b3d80481565d32d78c"),
    "epr-12166.b10": (65536, "9abd183b", "621b017cb34973f9227be383e26b5cd41aea9422"),
    "epr-12167.b11": (65536, "2495fd4e", "2db94ead9223a67238a97e724668076fc43e5534"),
    "mpr-12194.b1":  (65536, "2fb38880", "0e1b601bbda78d1887951c1f7e752531c281bc83"),
    "mpr-12195.b5":  (65536, "d6a02cba", "d80000f92e754e89c6ca7b7273feab448fc9a061"),
    "epr-12168.a7":  (32768, "bd9ba01b", "fafa7dc36cc057a50ae4cdf7a35f3594292336f4"),
    "315-5298.b9":   (235,   "39b47212", "432b47aee5ecbf08a8a6dc2f8379c816feb86328"),
}
ORDER = ["bootleg_epr-12192.a5", "bootleg_epr-12193.a7", "epr-12165.b9", "epr-12166.b10", "epr-12167.b11",
         "epr-12168.a7", "mpr-12194.b1", "mpr-12195.b5", "315-5298.b9"]
PLD_NAME, PLD_SIZE, PLD_CRC = "315-5298.b9", 235, 0x39b47212

class Inputs:
    """このスクリプトと同じフォルダ(と、その中の BIN フォルダ)からファイルを探す"""
    def __init__(self, folders):
        self.map = {}
        for fo in folders:
            if os.path.isdir(fo):
                for n in os.listdir(fo):
                    p = os.path.join(fo, n)
                    if os.path.isfile(p) and n.lower() not in self.map:
                        self.map[n.lower()] = p
    def has(self, n): return n.lower() in self.map
    def read(self, n):
        with open(self.map[n.lower()], "rb") as f: return f.read()

def here_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0] if sys.argv and sys.argv[0] else __file__))

def read_inputs(inp):
    miss = [n for n in NEED if not inp.has(n)]
    if miss:
        raise SystemExit("入力が足りません: " + ", ".join(miss) + "\nディスクの BIN フォルダの中身を、このファイルと同じフォルダ(か BIN フォルダ)に置いてください。")
    d = {n: inp.read(n) for n in NEED}
    if len(d["tet_dec.p00"]) != 0x10000 or len(d["tetrisd.p94"]) != 0x20000: raise SystemExit("tet_dec.p00 / tetrisd.p94 のサイズが想定と違います")
    if len(d["tetris.obj"]) != 0x20000: raise SystemExit("tetris.obj のサイズが想定と違います")
    if len(d["tetris.scr"]) % 4: raise SystemExit("tetris.scr のサイズが想定と違います")
    return d

# ---------------------------------------------------------------- 絵データ(タイル)
def scr_to_planes(s):
    """タイル(4バイト=8ピクセル×4bit)を3プレーンの ROM に変換"""
    n = len(s) // 4
    pl = [bytearray(n) for _ in range(3)]
    for i in range(n):
        w = int.from_bytes(s[i*4:i*4+4], "big")
        for k in range(8):
            q = (w >> (28 - 4*k)) & 15
            m = 0x80 >> k
            if q & 1: pl[0][i] |= m
            if q & 2: pl[1][i] |= m
            if q & 4: pl[2][i] |= m
    return [bytes(x) for x in pl]

# ---------------------------------------------------------------- プログラム(68000)
def build_program(d):
    """tet_dec.p00(前半32KB)と tetrisd.p94(後半)から、tetris2d のプログラム2本(a5=偶数番地側 / a7=奇数番地側)を作る"""
    dd, p = d["tet_dec.p00"], d["tetrisd.p94"]
    r92 = bytearray(0x10000); r93 = bytearray(0x10000)
    for i in range(0x8000):
        r92[i] = dd[i*2]; r93[i] = dd[i*2+1]
        r92[0x8000+i] = p[0x10000+i*2]; r93[0x8000+i] = p[0x10000+i*2+1]
    for k, v in {0x01F8: 0x55, 0x01F9: 0xC8, 0x0203: 0x00, 0x27B5: 0xFF, 0x27B6: 0xDC, 0x27B7: 0x01}.items(): r92[k] = v
    for k, v in {0x01F8: 0x61, 0x01F9: 0xBD, 0x0203: 0x60, 0x1441: 0x7F, 0x27B4: 0x02, 0x27B5: 0xFF, 0x27B6: 0xFE, 0x27B7: 0x98}.items(): r93[k] = v
    return bytes(r92), bytes(r93)

# ---------------------------------------------------------------- スプライト(素バージョン)
def sprite_rows():
    """スプライトの全2680行の(開始位置, 語数)。絵のコマの並びから決まる"""
    blocks = {}
    blocks["p4"] = [(4*r, 4) for r in range(8)]
    for k in range(43): blocks["i%d" % k] = [(0x16 + 480*k + 10*r, 10) for r in range(1, 49)]
    blocks["p3"] = [(0x50c0 + 3*r, 3) for r in range(8)]
    for j in range(2): blocks["q8_%d" % j] = [(0x50d0 + 144*j + 8*r, 8) for r in range(1, 19)]
    for j in range(4): blocks["q12_%d" % j] = [(0x51ec + 684*j + 12*r, 12) for r in range(1, 58)]
    for j in range(7): blocks["q24_%d" % j] = [(0x5c90 + 1152*j + 24*r, 24) for r in range(1, 49)]
    return [r for n in blocks for r in blocks[n]]

def structure_sprites(obj):
    """tetris.obj から素バージョンのスプライトROM(b1, b5)を作る。
    tetris.obj は 4bit の F(透明の印)がすべて 0 に変えられている。
    MAME のスプライト描画は、各行を「ピクセル3(各語の右端)が F の語」まで読む。
    そこで全2680行に、その印を1個ずつ(絵のある最後の語に)だけ戻す。ほかの透明Fは戻さない。"""
    b1r = obj[1::2][:0x8000]; b5r = obj[0::2][:0x8000]
    if obj[0::2][0x8000:] != obj[1::2][:0x8000] or set(obj[1::2][0x8000:]) != {0}:
        raise SystemExit("tetris.obj の中身が想定と違います")
    rows = sprite_rows()
    assert len(rows) == 2680
    m1 = bytearray(b1r)
    for s, p in rows:
        art = [w for w in range(s, s + p) if b1r[w] or b5r[w]]
        if not art:
            w = s
        else:
            b = art[-1]
            w = b if b1r[b] & 15 == 0 else b + 1
        if m1[w] & 15: raise SystemExit("行の終わりの印の位置に想定外の値があります")
        m1[w] |= 0x0F
    b1 = bytes(m1) + b"\xff" * 0x8000       # 本物の基板のROMの形: b1 = 前半32KB + FF埋め
    b5 = bytes(b5r) + bytes(m1)             #                        b5 = 前半32KB + b1の前半と同じもの
    return b1, b5, len(rows)

def make_dummy_pld(): return b"\0" * PLD_SIZE

def find_user_pld(inp):
    if inp.has(PLD_NAME):
        d = inp.read(PLD_NAME)
        if len(d) == PLD_SIZE and crc32(d) == PLD_CRC: return d
        say("※ 同じ場所の %s は大きさか CRC32 が違うので使いません" % PLD_NAME)
    return None

def write_zip(path, files):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path): os.remove(path)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        def same(n):
            d, e = files[n], EXPECT[n]
            return len(d) == e[0] and "%08x" % crc32(d) == e[1] and sha1(d) == e[2]
        # MAMEの定義と一致するファイルは zip の直下、一致しないファイルは modified フォルダの中
        for n in [x for x in ORDER if same(x)] + [x for x in ORDER if not same(x)]:
            arc = n if same(n) else "modified/" + n
            zi = zipfile.ZipInfo(arc, (2020, 1, 1, 0, 0, 0)); zi.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(zi, files[n])

def report(files):
    say("  ファイル                  CRC32     MAMEの定義との比較")
    for n in ORDER:
        d = files[n]; e = EXPECT[n]; c = "%08x" % crc32(d)
        same = (len(d) == e[0] and c == e[1] and sha1(d) == e[2])
        say("  %-22s %s  %s" % (n, c, "一致" if same else "違う(MAME定義 %s)" % e[1]))

def pause():
    try: input("\nEnter キーで終了します。")
    except Exception: pass
# ======================================================================
# tetris2d 公式ガイドライン対応版 作成(元の tetris2d.zip に差分パッチを当てる)
# ======================================================================
OUT_FOLDER = "テトリス公式ガイドライン対応版"
PATCH_FILES = ["bootleg_epr-12192.a5", "bootleg_epr-12193.a7", "epr-12165.b9", "epr-12166.b10", "epr-12167.b11"]

def read_sections():
    """このファイルの末尾に入れてある部分(差分パッチと説明文)を読む。各行の頭の「#|」を外す"""
    with open(os.path.abspath(__file__), encoding="utf-8") as f: lines = f.read().splitlines()
    secs, cur = {}, None
    for ln in lines:
        if ln.startswith("#@@ "): cur = ln[4:].strip(); secs[cur] = []
        elif cur is not None and ln.startswith("#|"): secs[cur].append(ln[2:])
    return {k: "\n".join(v) + "\n" for k, v in secs.items()}

def apply_ips(data, ips):
    """IPS形式の差分パッチを当てる(変更するバイトの位置と値だけが入っている)"""
    a = bytearray(data)
    if ips[:5] != b"PATCH": raise SystemExit("パッチの形式が違います")
    p = 5
    while ips[p:p+3] != b"EOF":
        off = int.from_bytes(ips[p:p+3], "big"); ln = int.from_bytes(ips[p+3:p+5], "big"); p += 5
        if off + ln > len(a): raise SystemExit("パッチの位置が範囲外です")
        a[off:off+ln] = ips[p:p+ln]; p += ln
    return bytes(a)

def load_patches(secs):
    import base64
    res = {}
    for ln in secs["PATCH"].splitlines():
        if ln.strip():
            name, base_sha1, crc, sha, b64 = ln.split("|")
            res[name] = (base_sha1, crc, sha, base64.b64decode(b64))
    return res

def read_zip_files(path):
    """zipの中身を、フォルダ(modified など)に関係なく、ファイル名で読む"""
    out = {}
    with zipfile.ZipFile(path) as z:
        for zi in z.infolist():
            if not zi.is_dir():
                out.setdefault(os.path.basename(zi.filename), z.read(zi))
    return out

def main():
    here = here_dir()
    out = os.path.join(here, OUT_FOLDER)
    say("Tetris (set 2, Japan, System 16B) tetris2d 公式ガイドライン対応版 作成(zipに差分パッチを当てます)")
    say("入力: " + here)
    say("出力: " + out)
    say()
    secs = read_sections()
    patches = load_patches(secs)
    zips = []
    for d in [here, os.path.join(here, "テトリス素バージョン")]:
        if os.path.isdir(d):
            zips += [os.path.join(d, n) for n in sorted(os.listdir(d)) if n.lower().endswith(".zip") and os.path.isfile(os.path.join(d, n))]
    done = 0
    for zn in zips:
        try:
            files = read_zip_files(zn)
        except Exception:
            say("%s: zipとして読めないので飛ばします" % os.path.relpath(zn, here)); continue
        if not all(n in files for n in PATCH_FILES):
            say("%s: 必要なファイルが入っていないので飛ばします" % os.path.relpath(zn, here)); continue
        if not all(sha1(files[n]) == patches[n][0] for n in PATCH_FILES):
            say("%s: 中身が、パッチの対象(MAMEのtetris2dの元のファイル)と違うので飛ばします" % os.path.relpath(zn, here)); continue
        new = dict(files)
        for n in PATCH_FILES:
            _b, crc, sha, ips = patches[n]
            new[n] = apply_ips(files[n], ips)
            if "%08x" % crc32(new[n]) != crc or sha1(new[n]) != sha: raise SystemExit("パッチを当てた結果が想定と違います: " + n)
        say("%s: パッチを当てました(%d ファイル)" % (os.path.relpath(zn, here), len(PATCH_FILES)))
        for n in ORDER:
            if n not in new and n == PLD_NAME: new[n] = make_dummy_pld()
        missing = [n for n in ORDER if n not in new]
        if missing: raise SystemExit("%s に足りないファイル: %s" % (zn, ", ".join(missing)))
        say()
        report({n: new[n] for n in ORDER})
        write_zip(os.path.join(out, "tetris2d.zip" if done == 0 else "tetris2d_%d.zip" % (done + 1)), {n: new[n] for n in ORDER})
        done += 1
    if not done:
        raise SystemExit("パッチを当てられるzipが見つかりませんでした。MAMEのtetris2dのzipを、このファイルと同じフォルダに置いてください。")
    with open(os.path.join(out, "改変の説明.txt"), "w", encoding="utf-8") as f: f.write(secs["DOC"])
    say()
    say("tetris2d.zip と 改変の説明.txt を作りました。CRCは強制していません(パッチを当てた中身そのままのCRCです)。")
    say("MAMEは「CRCが違う」と警告を出しますが、遊べます。")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e)
    except Exception as e:
        import traceback; traceback.print_exc(); print("エラー:", e)
    pause()

#@@ PATCH
#|bootleg_epr-12192.a5|a590d695c7d802ad7afe77990dd15775c03c727a|602f50b5|a63305c78df3a6a690329b3944fdd65c9b807e5d|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
#|bootleg_epr-12193.a7|88aa9c7868b914e5cbd3fc0def5d61d5d5c37d21|cb89135a|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
#|epr-12165.b9|c311d3847a981d0e1609f9b3d80481565d32d78c|872ce037|ce2bff7d5a49d15316a3b1d55c6fa456d92601ce|UEFUQ0gAAIgAJOf3Cf8h/ynn//8Q/BzwAf/n/4J8Av8px///BDwEPAQ8Dg4CDwAArQAbDwoFc/OQ8xDzoEPOz0DPQs9CznBwkPAQ8JBwAAYAAAj+ufHjx42ZfwAQCAAI/4GBgYGBgf8AWAgACP+BgYGBgYH/AFoIAAj/gYGBgYGB/wBcCAAI/4GBgYGBgf8AXggACP+BgYGBgYH/AGAIAAj/gYGBgYGB/wBiCAAI/4GBgYGBgf8A/AAACP658ePHjZl/AP4IABgRRBFEEUQRRKpVqlWqVapVqlWqVbvuu+4A/iQAHCKIVapVqt3/d92qVf////fX39/f39///7//v/9FT0Y=
#|epr-12166.b10|621b017cb34973f9227be383e26b5cd41aea9422|8d383201|47a140aa6c6c9a5b91e56dd359de2cc31198c9ad|UEFUQ0gAAIgAJCER//8hMe/nAR/w/BwQ//8hEf58AhHvxwHHPDwEBDw8AgMPDwAArgAaDwUQkPPzEBDjQ0JBz89CQ87OEBDw8BAQ8HAABgEAB3lxYUEDB38A9hgAAf8A9h8AAv//APYnAAL//wD2LwAC//8A9jcAAv//APY/AAL//wD2RwAB/wD8AQAHeXFhQQMHfwD+AAAr///////////uu+677rvuu1WqVapVqlWqVapVqkQRRBH/////3XeqVapVIgD+LAAciCJVqv////f39/f39/e3t/e397f//////////0VPRg==
#|epr-12167.b11|2db94ead9223a67238a97e724668076fc43e5534|32af678f|682fd77e555ffe338a5b177bfcc50d4329961de0|UEFUQ0gAAIgAQCERCQH//+/nAR8QBPzw//8hEYJEfv/vxwHHBAQ8PDw8AgICAg8PDwUQkJCQ8/PjQ0JBQEDPz87OEBCQEPDw8HAABgAACAEHDx8/f3//ABAIAAj/gYGBgYGB/wBYCAAI/4GBgYGBgf8AWggACP+BgYGBgYH/AFwIAAj/gYGBgYGB/wBeCAAI/4GBgYGBgf8AYAgACP+BgYGBgYH/AGIIAAj/gYGBgYGB/wD8AAAIAQcPHz9/f/8A/gAAK///////////7rvuu+677rtVqlWqVapVqlWqVapEEUQR/////913qlWqVSIA/jAAGAgICAgoKCgoKCgICEhISAj//////////0VPRg==

#@@ DOC
#|Tetris (set 2, Japan, System 16B) 公式ガイドライン対応版
#|作成方法(zipにパッチを当てる版)
#|MAME登録名:tetris2d (bootleg of FD1094 317-0092 set を元にした改造版)
#|
#|1. このツールについて
#|
#|このファイルと同じフォルダに置いた tetris2d のzip(と、同じフォルダの中の「テトリス素バージョン」フォルダにあるzip)に、差分パッチを当てて、テトリス公式ガイドライン対応の改造版zipを作ります。MAME専用です。
#|zipの中のファイルは、フォルダ(modifiedなど)に関係なく、ファイル名で見つけます。パッチを当てるのは5ファイル(a5・a7・b9・b10・b11)で、音・スプライト・PLDは、入力zipのままです。
#|同じフォルダに複数のzipがある場合は、パッチの対象に合うものすべてに当てます(出力は tetris2d.zip、tetris2d_2.zip …)。合わないzipは飛ばします。
#|このツールの中に、完成したROMは入っていません。入っているのは、改造部分の差分パッチ(変更するバイトの位置と値だけ)です。
#|本ROMは、アーケード基板のオリジナルROMを完全に再現したものではありません。また、MAMEのROM定義に記載されているCRC・SHA1に合わせるための加工や、ハッシュ値の偽装は行っていません。
#|
#|2. 差分パッチについて
#|
#|形式はIPSです。IPSパッチには、変更する位置と、変更後のデータが記録されています。元のROMファイル全体は収録していません。
#|対象は5ファイルで、各ファイルの大きさは変わりません。
#|  変更するバイト数: bootleg_epr-12192.a5: 3,786 / bootleg_epr-12193.a7: 3,583 / epr-12165.b9: 187 / epr-12166.b10: 159 / epr-12167.b11: 203(合計 7,918バイト)
#|  パッチファイルの大きさ(位置などの管理情報を含む): bootleg_epr-12192.a5.ips: 6,369バイト / bootleg_epr-12193.a7.ips: 7,431バイト / epr-12165.b9.ips: 260バイト / epr-12166.b10.ips: 232バイト / epr-12167.b11.ips: 271バイト
#|音、スプライト、PLDにはパッチを当てません。
#|
#|確認は、当てる前と当てたあとの2回行います。
#|  当てる前: zip内の対象5ファイルが、次の基準のSHA1と一致することを確認します(CRCも同じ値です)。この5ファイルは、MAMEのROM定義(tetris2d)と同じ値です。
#|  bootleg_epr-12192.a5  CRC32 8ff44f5f  SHA1 a590d695c7d802ad7afe77990dd15775c03c727a
#|  bootleg_epr-12193.a7  CRC32 e8c59f9d  SHA1 88aa9c7868b914e5cbd3fc0def5d61d5d5c37d21
#|  epr-12165.b9  CRC32 62640221  SHA1 c311d3847a981d0e1609f9b3d80481565d32d78c
#|  epr-12166.b10  CRC32 9abd183b  SHA1 621b017cb34973f9227be383e26b5cd41aea9422
#|  epr-12167.b11  CRC32 2495fd4e  SHA1 2db94ead9223a67238a97e724668076fc43e5534
#|  当てたあと: 生成されたファイルが、次の基準のCRC・SHA1と一致することを確認します。
#|  bootleg_epr-12192.a5  CRC32 602f50b5  SHA1 a63305c78df3a6a690329b3944fdd65c9b807e5d
#|  bootleg_epr-12193.a7  CRC32 cb89135a  SHA1 7cc38ec4ab7dd6436a2ca1a4c49e77b87b5eacfb
#|  epr-12165.b9  CRC32 872ce037  SHA1 ce2bff7d5a49d15316a3b1d55c6fa456d92601ce
#|  epr-12166.b10  CRC32 8d383201  SHA1 47a140aa6c6c9a5b91e56dd359de2cc31198c9ad
#|  epr-12167.b11  CRC32 32af678f  SHA1 682fd77e555ffe338a5b177bfcc50d4329961de0
#|  どちらかが一致しなければ、ROMは作りません。
#|
#|3. MAMEのROM定義との違い
#|
#|パッチを当てた5ファイルは、MAMEのROM定義に記載されているCRC・SHA1とは異なります。CRCは、パッチを当てた中身そのままの値です(2章のとおり)。
#|それ以外のファイルは、入力zipのままです。
#|出力zipでは、MAMEの定義と一致しないファイルを modified フォルダに入れ、一致するファイルをzip直下に置きます。
#|MAME起動時にはチェックサムの警告が表示されますが、ゲームの起動とプレイは可能です。-verifyroms は「bad」になります。
