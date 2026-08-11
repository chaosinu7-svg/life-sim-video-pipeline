#!/usr/bin/env python3
"""生成抖音封面（1080×1440，3:4，个人主页九宫格比例）。

封面套路来自两条真实爆款的反推：
- 184万那条：**纯画面零文字**，靠三个人的表情对比把故事讲完，而且是专门画的不是片中截图
- 122万那条：**大字压底**，红字黑粗描边，画面在上文字在下

抖音缩略图小，大字路线更安全——刷到时要能一眼读到人格标签。
本脚本默认出「大字版 + 无字版」两版，让主理人挑。

标题结构照爆款：**情境（小）+ 人格标签（大）**。标签必须是缩略图也能读的字号。

用法：
    python3 build_cover.py --art cover-A.png --ctx "抢了同事三年功劳的" --tag "汇报天才"
"""
import subprocess, argparse, os

W, H = 1080, 1440
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"


def make_gradient(path):
    """自下而上的透明→暗渐变，给标题托底。用真渐变，不用叠矩形。"""
    import struct, zlib
    rows = []
    for y in range(H):
        f = max(0.0, (y - (H - 620)) / 620.0)      # 底部 620px 内渐入
        alpha = int(min(1.0, f ** 1.6) * 0.80 * 255)
        rows.append(bytes([12, 8, 7, alpha]) * W)
    raw = b"".join(b"\x00" + r for r in rows)
    def chunk(t_, d):
        c = t_ + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    open(path, "wb").write(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def esc(s):
    return s.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace("%", r"\%")


def probe(f):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0", f],
                       capture_output=True, text=True).stdout.strip()
    w, h = o.split(",")
    return int(w), int(h)


def fit(src, dst):
    """裁切填满 3:4，不留边。生图侧交付的比例通常不准，几何一律在这里做。"""
    w, h = probe(src)
    if w / h > W / H:                      # 太宽 → 裁宽度
        cw, ch = int(round(h * W / H)), h
        x, y = (w - cw) // 2, 0
    else:                                  # 太高 → 裁高度，偏上保住头
        cw, ch = w, int(round(w * H / W))
        x, y = 0, int(round((h - ch) * 0.12))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src,
                    "-vf", f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos", dst], check=True)
    return f"{w}x{h} → 裁 {cw}x{ch}@({x},{y}) → {W}x{H}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--art", required=True, help="封面底图")
    ap.add_argument("--ctx", required=True, help="情境行（小字）")
    ap.add_argument("--tag", required=True, help="人格标签（大字，缩略图靠它）")
    ap.add_argument("--outdir", default="assets/cover")
    ap.add_argument("--tag-color", default="0xFFD400", help="标签颜色，默认亮黄")
    a = ap.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    base = os.path.join(a.outdir, "_fitted.png")
    print("几何:", fit(a.art, base))

    stem = os.path.splitext(os.path.basename(a.art))[0]
    plain = os.path.join(a.outdir, f"{stem}-无字版.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base, "-c:v", "png", plain], check=True)

    # 大字版：底部渐变压暗 + 情境行 + 标签行（黑色粗描边保证任何背景可读）
    tag_size = 168 if len(a.tag) <= 4 else 132
    ctx_size = 60
    tag_y = H - 250
    ctx_y = tag_y - ctx_size - 34
    # ⚠️ 底部压暗必须是真渐变。叠几个 drawbox 会留出可见的横向台阶——
    # 开头合成那次栽过同一个坑，别用矩形凑。
    grad = os.path.join(a.outdir, "_grad.png")
    make_gradient(grad)
    vf = (
        f"drawtext=fontfile='{FONT}':text='{esc(a.ctx)}':fontcolor=white:fontsize={ctx_size}:"
        f"x=(w-tw)/2:y={ctx_y}:borderw=7:bordercolor=black@0.95,"
        f"drawtext=fontfile='{FONT}':text='{esc(a.tag)}':fontcolor={a.tag_color}:fontsize={tag_size}:"
        f"x=(w-tw)/2:y={tag_y}:borderw=13:bordercolor=black"
    )
    titled = os.path.join(a.outdir, f"{stem}-大字版.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base, "-i", grad,
                    "-filter_complex", "[0][1]overlay=0:0[bg];[bg]" + vf + "[v]",
                    "-map", "[v]", "-c:v", "png", titled], check=True)
    os.remove(base); os.remove(grad)
    for f in (titled, plain):
        print(f"  {f}  {probe(f)[0]}x{probe(f)[1]}")
    print("\n两版都出，让主理人挑：大字版缩略图可读性好，无字版靠表情讲故事（对齐 184万 那条的做法）")


if __name__ == "__main__":
    main()
