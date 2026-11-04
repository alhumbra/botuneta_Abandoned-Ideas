# -*- coding: utf-8 -*-
"""Tetris (set 2, Japan, System 16B) tetris2d の「素バージョン」を、PS2版のディスクのファイルから作ります。
使い方: このファイルを、ディスクの BIN フォルダの中身(tetrisd.p94, tet_dec.p00, tetris.scr, tetris.obj, tetris.snd)と
同じフォルダ(か、その中の BIN フォルダ)に置いて、ダブルクリックで実行します。
出力: 「テトリス素バージョン」フォルダの中に tetris2d.zip と説明。CRCは強制しません。"""
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
# tetris2d 素バージョン 作成
# ======================================================================
OUT_FOLDER = "テトリス素バージョン"
EXPLAIN = """Tetris (set 2, Japan, System 16B)
素バージョンROMの作成方法と技術的説明
MAME登録名:tetris2d

1. このROMについて

本ROMは、PS2用ソフト「SEGA AGES 2500 Vol.28 テトリスコレクション」に収録されているデータを元に、MAMEで動作する形式に再構成したものです。
作成にあたっては、ディスク内のBINフォルダに含まれるゲームデータを使用しています。
プログラム、背景画像、音声データについては、元のデータから必要な部分を抽出して使用しています。
一方、スプライト(キャラクターなどの画像)については、PS2版のデータがアーケード版とは異なる形式に変更されているため、そのままでは正常に表示できませんでした。
そこで、MAMEのスプライト描画処理を解析し、ゲームの表示に必要な構造情報だけを追加する方法で対応しました。
このため、本ROMはアーケード基板のオリジナルROMを完全に再現したものではありません。
また、MAMEのROM定義に記載されているCRC・SHA1に合わせるための加工や、ハッシュ値の偽装は行っていません。

2. 作成の基本方針

今回の作成では、次の2段階で検証を行いました。

第1段階: ゲームを動作させるための再構成
ディスク内のデータからプログラム、画像、音声を抽出しました。
スプライトについては、MAME上で実際に読み込まれるデータを調査し、正常な描画に必要な行末情報を補うことで、ゲームが動作する状態にしました。

第2段階: スプライトデータの構造検証
MAMEのROM定義にあるCRC・SHA1を参考に、元のアーケードROMと同じデータを再現できないか検証しました(これは一例で、ほかにも手がかりを探しました)。
セガのスプライトROMの構造やデータ配置の規則を調べた結果、前半ROM(b1)は規則に従って再構成することでMAMEの定義と一致しました。
しかし、後半ROM(b5)は、ゲームの表示に関係しない領域のデータ配置まで一致させることができませんでした。
公開されている関連ツールの処理内容も確認した結果、ゲームの動作情報だけからオリジナルROMの全データを復元することはできないと判断しました。
そこで、オリジナルROMの完全再現ではなく、ゲームの動作と表示に必要な構造だけを再構成する方式を採用しました。
これを「素バージョン」としています。

3. スプライトの素バージョンについて

今回の素バージョンで最も重要な変更点は、スプライトの行末情報です。

PS2版のスプライトデータでは、本来透明色として使用されるペン15(4ビットの値F)がすべて0に置き換えられています。
MAMEのSystem 16系スプライト描画処理(sega16sp.cpp)では、各行を読み込み、特定位置のペン15(F)を行末の終了マーカーとして扱います。
このマーカーが存在しない場合、次の行のデータまで読み込んでしまい、正常な画像表示ができません。
そこで、スプライトデータ全2680行について、絵のある最後の語に行末マーカーを1個ずつ追加しました。
それ以外の透明なFは追加していません。
ペン15は透明色として扱われるため、行末マーカーより前に存在する透明なFの有無は画面表示に影響しません。また、行末マーカー以降のデータは読み込まれません。
この方法により、画像データ自体を変更することなく、正常なスプライト描画に必要な構造を確保しています。

Fのニブル(4ビットの単位)の数は次のとおりです。
  すべての透明Fを戻した場合: 25,648個
  今回の素バージョン: 2,680個(全2680行に各1個の行末マーカー)

4. ROMの生成方法

入力として使用するファイルは、ディスク内のBINフォルダにある次の5ファイルです。
  tetrisd.p94(128KB) / tet_dec.p00(64KB) / tetris.scr / tetris.obj(128KB) / tetris.snd

各ROMの生成方法は以下のとおりです。

プログラムROM
  bootleg_epr-12192.a5(64KB) / bootleg_epr-12193.a7(64KB)
  tet_dec.p00の先頭32KBと、tetrisd.p94の0x10000以降の32KBを使用します。
  それぞれのデータを偶数バイト側と奇数バイト側に分離し、2つのROMに配置します。
  その後、公開されているTetris2dRomBuilderの処理と同じ値を使用して、必要なプログラム領域を14バイト変更します。
    a5: 0x1F8=55 / 0x1F9=C8 / 0x203=00 / 0x27B5=FF / 0x27B6=DC / 0x27B7=01
    a7: 0x1F8=61 / 0x1F9=BD / 0x203=60 / 0x1441=7F / 0x27B4=02 / 0x27B5=FF / 0x27B6=FE / 0x27B7=98
  この14バイトのうち7バイト(a5の0x27B5〜0x27B7、a7の0x27B4〜0x27B7)は、tetrisd.p94の元の値と同じです。
  残りの7バイトは、ゲームの動きに関係しない場所で、元の値に戻しても画面と動きは変わらないことを確認しています。

背景画像ROM
  epr-12165.b9 / epr-12166.b10 / epr-12167.b11(各64KB)
  tetris.scrを元に、4バイト(横8ピクセル・1ピクセル4ビット)単位でデータを読み込み、ビット0・1・2をそれぞれのROMに分配します。

スプライトROM
  mpr-12194.b1 / mpr-12195.b5(各64KB)
  tetris.objを偶数バイト側と奇数バイト側に分離し(偶数側がb5の元、奇数側がb1の元)、それぞれの前半32KBを使用します。
  全2680行について、絵のある最後の語に行末マーカー(ピクセル3=F)を追加します。
  mpr-12194.b1: 行末マーカーを追加した32KB + FFによる32KBの埋め合わせ
  mpr-12195.b5: 元のデータの32KB + b1の前半32KBと同じデータ

音声ROM
  epr-12168.a7(32KB)
  tetris.sndをそのまま使用します。音声データの加工は行っていません。

PLD
  315-5298.b9(235バイト)
  実際のPLDデータを再現したものではなく、動作に必要なROM構成を満たすためのゼロ埋めダミーファイルです。

5. MAMEのROM定義との違い

次の3ファイルは、MAMEのROM定義に記載されているCRC・SHA1とは異なります。
  mpr-12194.b1 / mpr-12195.b5 / 315-5298.b9
これらは生成したデータをそのまま収録しており、MAMEのチェックサムに合わせる加工はしていません。
この3ファイルは、ZIP内のmodifiedフォルダに入れてあります。
MAME起動時には「INCORRECT CHECKSUM」と表示される場合がありますが、ゲームの起動とプレイは可能です。

6. 動作と表示の検証

素バージョンのスプライトについて、次の検証を実施しています。

スプライト全行の比較
全2680行について、すべての透明Fを戻した場合と素バージョンの表示結果を1行ずつ比較しました。
結果は2680行すべて一致し、表示上の相違はありませんでした。
また、行末マーカーを1個取り除いた場合に、比較プログラムが相違を検出することも確認しています。

MAME上での動作比較
MAMEで14400フレームまで動作させ、コイン投入、スタート、ランダム操作を含む同一条件で画面を比較しました。
疑似乱数の種も固定し、ゲームオーバーや猿の登場まで確認しています。
b1がMAMEの定義と一致する版との比較では、保存した307枚の画面すべてが一致しました。
なお、音声については音声ROMを変更していないため、影響は想定していませんが、別途の聴感比較は実施していません。

7. まとめ

今回のROMは、PS2版に収録されているゲームデータを元に、MAMEで動作させるために必要なデータ構造を再構成したものです。
スプライトについては、オリジナルROMの完全復元を目的とせず、MAMEの描画処理を調査したうえで、ゲームの表示に必要な行末マーカーだけを追加しています。
その結果、全2680行の表示比較と、MAME上での307画面の比較において、同一の表示結果を確認しています。
"""

def main():
    here = here_dir()
    inp = Inputs([here, os.path.join(here, "BIN"), os.path.join(here, "bin")])
    out = os.path.join(here, OUT_FOLDER)
    say("Tetris (set 2, Japan, System 16B) tetris2d 素バージョン 作成")
    say("入力: " + here)
    say("出力: " + out)
    say()
    d = read_inputs(inp)
    a5, a7 = build_program(d)
    pl = scr_to_planes(d["tetris.scr"])
    b1, b5, nrows = structure_sprites(d["tetris.obj"])
    say("スプライトの行の数: %d(行の終わりの印を %d 個戻しました)" % (nrows, nrows))
    user_pld = find_user_pld(inp)
    files = {"bootleg_epr-12192.a5": a5, "bootleg_epr-12193.a7": a7,
             "epr-12165.b9": pl[0], "epr-12166.b10": pl[1], "epr-12167.b11": pl[2],
             "epr-12168.a7": d["tetris.snd"], "mpr-12194.b1": b1, "mpr-12195.b5": b5,
             PLD_NAME: user_pld if user_pld else make_dummy_pld()}
    say("315-5298.b9: " + ("同じ場所にあった本物を使いました" if user_pld else "ディスクに無いのでダミーを入れました"))
    say()
    report(files)
    write_zip(os.path.join(out, "tetris2d.zip"), files)
    with open(os.path.join(out, "素バージョンの説明.txt"), "w", encoding="utf-8-sig") as f: f.write(EXPLAIN)
    say()
    say("tetris2d.zip を作りました。CRCは強制していません。")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        print(e)
    except Exception as e:
        import traceback; traceback.print_exc(); print("エラー:", e)
    pause()
