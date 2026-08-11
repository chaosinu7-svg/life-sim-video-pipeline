#!/usr/bin/env python3
"""合成 HBG 开头的快闪片段 assets/opening/flash.mp4（重特效版）。

规格底线来自 skill 的 references/opening-system.md：
  - 约九条候选人生，铺在 1.4–1.8 秒内
  - 每一帧交替强 zoom-in / zoom-out，带反向 x/y 漂移。**一串静止硬切不算数**
  - 音轨是棘轮音效

在规格之上，按抖音/B站头部的做法加了这些
（手法来源：桃泯丨《Ai做体验人生副本，最高点赞74万，制作全流程拆解教学》BV1b1jX6gEig）：
  荧幕噪点 · 手持摇晃 · 暗角 · 每次切换的冲击闪（白黑交替频闪）·
  RGB 色差分离 · 镜头畸变 · 锐化 · 切换速率加密
"""
import subprocess, os, json

W, H, FPS = 1920, 1080, 30
TOTAL = 1.667
CUTS = 12                 # 切换次数：原 8 次加密到 12 次 ≈ 每帧 0.139s
RATCHET = "assets/audio/sfx/ratchet.wav"
OUT = "assets/opening/flash.mp4"
WORK = "/tmp/hbg_flash_work"
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"

SCALE_MIN, SCALE_MAX = 1.00, 1.34   # 推拉幅度再加大
DRIFT = 26                          # 反向漂移
SHAKE = 9                           # 手持摇晃振幅
GRAIN = 12                          # 荧幕噪点
RGB_SHIFT = 7                       # 色差分离像素


def main():
    spec = json.load(open("PROJECT_SPEC.json"))
    lives = spec["opening"]["flashLives"]
    imgs = [l["asset"] for l in lives]
    labels = [l["label"] for l in lives]
    missing = [p for p in imgs + [RATCHET] if not os.path.exists(p)]
    if missing:
        raise SystemExit("缺素材: " + ", ".join(missing))
    os.makedirs(WORK, exist_ok=True)

    # 12 次切换：8 张各出一次（带标签），前 4 张再闪一次（不带标签，纯冲击）
    order = (list(range(len(imgs))) + list(range(4)))[:CUTS]
    show_label = ([True] * len(imgs) + [False] * 4)[:CUTS]

    total_frames = int(round(TOTAL * FPS))
    base, extra = divmod(total_frames, CUTS)
    plan = [base + (1 if i < extra else 0) for i in range(CUTS)]
    print(f"总帧数 {total_frames} ({total_frames/FPS:.3f}s) / {CUTS} 次切换 分配 {plan}", flush=True)

    segs = []
    for i, idx in enumerate(order):
        frames = plan[i]
        n = max(1, frames - 1)
        zoom_in = (i % 2 == 0)
        s0, s1 = (SCALE_MIN, SCALE_MAX) if zoom_in else (SCALE_MAX, SCALE_MIN)
        dx0, dx1 = (-DRIFT, DRIFT) if zoom_in else (DRIFT, -DRIFT)
        dy0, dy1 = (DRIFT, -DRIFT) if zoom_in else (-DRIFT, DRIFT)
        big_w, big_h = int(W * SCALE_MAX * 1.12), int(H * SCALE_MAX * 1.12)
        z = f"{s0}+({s1}-{s0})*on/{n}"
        x = f"iw/2-(iw/zoom/2)+({dx0}+({dx1}-{dx0})*on/{n})+{SHAKE}*sin(on*2.3+{i})"
        y = f"ih/2-(ih/zoom/2)+({dy0}+({dy1}-{dy0})*on/{n})+{SHAKE}*cos(on*1.9+{i})"

        punch = "white@0.62" if i % 2 == 0 else "black@0.70"
        chain = [
            f"scale={big_w}:{big_h}:flags=lanczos",
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS}",
            "lenscorrection=k1=-0.055:k2=-0.012",          # 广角冲击感
            f"rgbashift=rh=-{RGB_SHIFT}:bh={RGB_SHIFT}:rv={RGB_SHIFT//2}:bv=-{RGB_SHIFT//2}"
            f":enable='lt(t,{2/FPS:.3f})'",                 # 色差只在切入两帧最强
            "unsharp=5:5:0.9:5:5:0.0",
            f"drawbox=x=0:y=0:w=iw:h=ih:color={punch}:t=fill:enable='lt(t,{1.2/FPS:.3f})'",
            f"noise=alls={GRAIN}:allf=t+u",
            "vignette=PI/4.0",
        ]
        if show_label[i]:
            lab = labels[idx].replace(":", r"\:").replace("'", r"\'")
            chain.append(f"drawbox=x=0:y={H//2-72}:w={W}:h=144:color=black@0.5:t=fill")
            chain.append(
                f"drawtext=fontfile='{FONT}':text='{lab}':fontcolor=0xFFF9F1:fontsize=58:"
                f"x=(w-tw)/2:y=(h-th)/2:borderw=3:bordercolor=black@0.9")
        seg = f"{WORK}/seg{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", imgs[idx],
                        "-vf", ",".join(chain), "-frames:v", str(frames),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", seg], check=True)
        segs.append(seg)
        print(f"  切{i+1:2d}/{CUTS} {'推' if zoom_in else '拉'} {s0:.2f}→{s1:.2f} "
              f"{frames}帧 {'白闪' if i % 2 == 0 else '黑闪'}{' [标签]' if show_label[i] else ''}",
              flush=True)

    with open(f"{WORK}/list.txt", "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", f"{WORK}/list.txt", "-i", RATCHET,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", OUT], check=True)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", OUT], capture_output=True, text=True).stdout.strip()
    print(f"已写出 {OUT}  {dur}s")


if __name__ == "__main__":
    main()
