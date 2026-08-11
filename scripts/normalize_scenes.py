#!/usr/bin/env python3
"""把 scenes/ 下的图统一成铺满画面的 1920×1080。

背景：内置 image_gen 交付的像素尺寸不等于请求尺寸，实测出过
1448×1086(4:3)、1672×941、810×1080(竖) 等。让生图侧自己"凑尺寸"
会得到等比缩放加黑边（立柱/信箱），带 zoom/pan 一动黑边就漂，成片必废。
所以几何一律由本脚本处理，生图侧只管出原图。

策略：
  1. 逐列/逐行找纯黑填充带，裁出真正的内容框
  2. 内容框宽高比 >= 1.20 的，按 16:9 裁切填满（偏上裁，保住头顶），再缩放
  3. 宽高比 < 1.20 的（方构图/竖构图）不硬裁，列为「需重生成」
用法：python3 normalize_scenes.py [--apply]
"""
import subprocess, sys, os, shutil

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets/generated/scenes")
BACKUP = os.path.join(os.path.dirname(DIR), "_padded_backup")
W, H = 1920, 1080
MIN_RATIO = 1.20      # 低于此比例不硬裁，交给重生成
TOP_BIAS = 0.15       # 裁切时从顶部让出多少比例的损失量（越小越保头顶）
BLACK = 1             # 只认纯黑。暗夜镜头的边缘很暗但不会精确为 0，
                      # 用 6 会把"凌晨屏幕特写"这类误判成黑边。
SYM_TOL = 4           # 填充带必须左右（或上下）对称，否则视为画面内容


def probe(f):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v",
                          "-show_entries", "stream=width,height", "-of", "csv=p=0", f],
                         capture_output=True, text=True).stdout.strip()
    w, h = out.split(",")
    return int(w), int(h)


def band(f, vf):
    return subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-vf", vf,
                           "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                          capture_output=True).stdout


def content_box(f, w, h):
    """只裁掉左右或上下对称的纯黑填充带，不动画面本身的暗部。"""
    cols = band(f, f"scale={w}:1,format=gray")
    rows = band(f, f"scale=1:{h},format=gray")
    nzc = [i for i, v in enumerate(cols) if v > BLACK] or [0, w - 1]
    nzr = [i for i, v in enumerate(rows) if v > BLACK] or [0, h - 1]
    x0, x1 = nzc[0], nzc[-1]
    y0, y1 = nzr[0], nzr[-1]
    if abs(x0 - (w - 1 - x1)) > SYM_TOL:   # 左右不对称 → 不是填充带
        x0, x1 = 0, w - 1
    if abs(y0 - (h - 1 - y1)) > SYM_TOL:   # 上下不对称 → 不是填充带
        y0, y1 = 0, h - 1
    return x0, y0, x1 - x0 + 1, y1 - y0 + 1


def main(apply_changes):
    os.makedirs(BACKUP, exist_ok=True)
    ok = fixed = 0
    regen = []
    for name in sorted(os.listdir(DIR)):
        if not name.endswith(".png"):
            continue
        f = os.path.join(DIR, name)
        w, h = probe(f)
        x, y, cw, chh = content_box(f, w, h)
        ratio = cw / chh
        # 容差：内容框覆盖 ≥99% 画幅即视为满画（最边上一两列本身偏暗不算黑边）
        full = (w, h) == (W, H) and cw >= w * 0.99 and chh >= h * 0.99
        if full:
            ok += 1
            continue
        if ratio < MIN_RATIO:
            regen.append((name, f"内容框 {cw}x{chh} 比例 {ratio:.2f} 过窄，硬裁会砍掉 "
                                f"{(1-(cw/16*9)/chh)*100:.0f}% 高度"))
            continue
        if ratio >= W / H:                 # 内容比 16:9 更宽 → 裁宽度，高度保留
            th = chh
            tw = int(round(chh * 16 / 9))
            tx = x + (cw - tw) // 2
            ty = y
        else:                              # 内容比 16:9 更高 → 裁高度，偏上保头顶
            tw = cw
            th = int(round(cw * 9 / 16))
            tx = x
            ty = y + int(round((chh - th) * TOP_BIAS))
        cw, x = tw, tx
        if apply_changes:
            shutil.copy(f, os.path.join(BACKUP, name))
            tmp = f + ".tmp.png"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f, "-vf",
                            f"crop={cw}:{th}:{x}:{ty},scale={W}:{H}:flags=lanczos", tmp], check=True)
            shutil.move(tmp, f)
        print(f"{name}: 内容 {cw}x{chh}@({x},{y}) 比例{ratio:.2f} → 裁 {cw}x{th}@({x},{ty}) → {W}x{H}"
              f"  损失高度 {(chh-th)/chh*100:.0f}%")
        fixed += 1
    print(f"\n已合格 {ok} 张 | {'已修' if apply_changes else '待修'} {fixed} 张 | 需重生成 {len(regen)} 张")
    for n, why in regen:
        print(f"  ⚠️ {n}  {why}")
    return regen


if __name__ == "__main__":
    main("--apply" in sys.argv)
