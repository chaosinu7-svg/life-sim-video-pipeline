#!/usr/bin/env python3
"""合成 HBG 开头预览 qa/opening-preview.mp4。

顺序是 skill 写死的，不能动（references/opening-system.md）：
  引导语「今天体验的人生副本是……」
  → 引导语结束后 ≤0.05 秒立刻上齿轮音效与快闪，两者同时发生
  → 停在选中的那条人生
  → 画面保持，读出完整的人生剧本标题
  → 正文才开始

标题用本脚本渲染（HTML/drawtext），不让生图模型写中文。
版式参数全部取自 HBG_STYLE.json，不自己发明。
"""
import subprocess, json, os

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
style = json.load(open("HBG_STYLE.json"))
spec = json.load(open("PROJECT_SPEC.json"))
meta = json.load(open("audio_meta.json"))

W = style["canvas"]["width"]; H = style["canvas"]["height"]; FPS = style["canvas"]["fps"]
L = style["opening"]["layout"]
S0 = style["opening"]["selectedScaleStart"]; S1 = style["opening"]["selectedScaleEnd"]
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
GRAIN = 11      # 荧幕噪点
VIGN = "vignette=PI/4.2"
SHAKE = 5       # 手持摇晃振幅
WORK = "/tmp/hbg_opening_work"
OUT = "qa/opening-preview.mp4"

op = meta["opening"]
lead_start = op["lead"]["start"]; lead_end = op["lead"]["end"]
flash_start = op["flash"]["start"]; flash_end = op["flash"]["end"]
reveal_start = op["reveal"]["start"]; reveal_end = op["reveal"]["end"]
body_start = op["bodyStart"]

def esc(s):
    return s.replace("\\", r"\\").replace(":", r"\:").replace("'", r"\'").replace("%", r"\%")

def run(args):
    subprocess.run(args, check=True)

def main():
    os.makedirs(WORK, exist_ok=True)
    os.makedirs("qa", exist_ok=True)

    # ── A 段：引导语文字卡，0 → flash_start ──────────────────────────────
    a_dur = flash_start
    a_frames = int(round(a_dur * FPS))
    lead_text = esc(spec["opening"]["leadDisplayText"])
    # 文字在 0.04 秒后淡入，对齐 build_composition 的 GSAP 时序
    # 文字上滑淡入，不是干巴巴地淡出来（拆解里点名「开头的文字要加动画」）
    vf_a = (f"drawtext=fontfile='{FONT}':text='{lead_text}':fontcolor=0xFFF9F1:"
            f"fontsize={L['leadFontSize']}:x=(w-tw)/2:"
            f"y='(h-th)/2+28*max(0,1-(t-0.04)/0.45)':"
            f"alpha='if(lt(t,0.04),0,min(1,(t-0.04)/0.38))',"
            f"noise=alls={GRAIN}:allf=t+u,{VIGN}")
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"color=c=0x0C0807:s={W}x{H}:d={a_dur}:r={FPS}",
         "-vf", vf_a, "-frames:v", str(a_frames),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", f"{WORK}/A.mp4"])
    print(f"A 引导语 {a_dur:.3f}s / {a_frames}帧", flush=True)

    # ── B 段：快闪（已含棘轮音效），直接用 ──────────────────────────────
    run(["ffmpeg", "-v", "error", "-y", "-i", "assets/opening/flash.mp4",
         "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", f"{WORK}/B.mp4"])
    print(f"B 快闪 {flash_end-flash_start:.3f}s", flush=True)

    # ── C 段：选中人生慢推 + 标题卡 ────────────────────────────────────
    c_dur = body_start - flash_end
    c_frames = int(round(c_dur * FPS))
    p_size = L["primaryTitleFontSize"]; s_size = L["secondaryTitleFontSize"]
    lines = spec["titleLines"]
    # C 版：左对齐 + 左侧砖红竖条。层级倒置——先铺情境（小、暖灰），再砸标签（大、白）
    ctx_size = s_size            # 第一行：情境，小
    tag_size = p_size + 26       # 第二行：标签，砸下来
    tx = 340                     # 文字左边界
    bar_x = 300                  # 竖条
    cy = int(H * L["titleTopPercent"] / 100)
    ctx_y = cy - 118
    tag_y = cy - 24
    bar_y = ctx_y - 14
    bar_h = (tag_y + tag_size + 18) - bar_y
    appear = 0.04
    big_w, big_h = int(W * S1 * 1.12), int(H * S1 * 1.12)
    zexpr = f"{S0}+({S1}-{S0})*on/{max(1,c_frames-1)}"
    xexpr = (f"iw/2-(iw/zoom/2)+(-10+22*on/{max(1,c_frames-1)})"
             f"+{SHAKE}*sin(on*0.9)")
    yexpr = (f"ih/2-(ih/zoom/2)+(10-24*on/{max(1,c_frames-1)})"
             f"+{SHAKE}*cos(on*0.7)")
    # 底部压暗必须是渐变，不能用硬边矩形——矩形会在画面中间留一条可见的横向接缝
    vf_c = (
        f"scale={big_w}:{big_h}:flags=lanczos,"
        f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':d={c_frames}:s={W}x{H}:fps={FPS},"
        f"lenscorrection=k1=-0.03:k2=-0.006[bg];"
        f"[bg][1:v]overlay=0:0[grad];"
        f"[grad]"
        # 左侧砖红竖条，从上往下长出来
        f"drawbox=x={bar_x}:y={bar_y}:w=6:"
        f"h='min({bar_h},{bar_h}*(t-{appear})/0.28)':color=0xC8402E:t=fill:"
        f"enable='gte(t,{appear})',"
        # 第一行：情境
        f"drawtext=fontfile='{FONT}':text='{esc(lines[0])}':fontcolor=0xD9D2C9:fontsize={ctx_size}:"
        f"x={tx}:y={ctx_y}:shadowcolor=black@0.85:shadowx=0:shadowy=4:"
        f"alpha='if(lt(t,{appear}),0,min(1,(t-{appear})/0.30))',"
        # 第二行：标签，晚 0.22 秒砸下来
        f"drawtext=fontfile='{FONT}':text='{esc(lines[1])}':fontcolor=white:fontsize={tag_size}:"
        f"x={tx}:y='{tag_y}+18*max(0,1-(t-{appear+0.22})/0.22)':"
        f"shadowcolor=black@0.9:shadowx=0:shadowy=7:"
        f"alpha='if(lt(t,{appear+0.22}),0,min(1,(t-{appear+0.22})/0.18))',"
        # 标签砸下来那一瞬间的冲击闪 + 色差
        f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.55:t=fill:"
        f"enable='between(t,{appear+0.22},{appear+0.28})',"
        f"rgbashift=rh=-6:bh=6:enable='between(t,{appear+0.22},{appear+0.32})',"
        f"unsharp=5:5:0.6:5:5:0.0,"
        f"noise=alls={GRAIN}:allf=t+u,{VIGN}[v]"
    )
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", "assets/opening/final.jpg",
         "-loop", "1", "-i", "/tmp/opening_gradient.png",
         "-filter_complex", vf_c, "-map", "[v]", "-frames:v", str(c_frames),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", f"{WORK}/C.mp4"])
    print(f"C 选中人生 {c_dur:.3f}s / {c_frames}帧  scale {S0}→{S1}  情境{ctx_size}px@y{ctx_y} 标签{tag_size}px@y{tag_y} 竖条x{bar_x}", flush=True)

    # ── 拼视频 ────────────────────────────────────────────────────────
    with open(f"{WORK}/list.txt", "w") as f:
        for s in ("A", "B", "C"):
            f.write(f"file '{WORK}/{s}.mp4'\n")
    # ⚠️ 必须重编码，不能用 -c copy。
    # -c copy 会让每段保留各自的帧编号与时基，容器时长和播放都正常，
    # 但下游 render_streaming_ffmpeg 用的 trim=start_frame 会在第二段末尾就停止计数，
    # 导致标题卡整段丢失。踩过一次，别再改回去。
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{WORK}/list.txt",
         "-vsync", "cfr", "-r", str(FPS),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", f"{WORK}/video.mp4"])

    # ── 混音：引导语 + 棘轮 + 标题揭示，按 audio_meta 的时间码 ──────────
    run(["ffmpeg", "-v", "error", "-y",
         "-i", op["lead"]["path"], "-i", "assets/audio/sfx/ratchet.wav", "-i", op["reveal"]["path"],
         "-filter_complex",
         f"[0:a]adelay={int(lead_start*1000)}|{int(lead_start*1000)}[a0];"
         f"[1:a]adelay={int(flash_start*1000)}|{int(flash_start*1000)}[a1];"
         f"[2:a]adelay={int(reveal_start*1000)}|{int(reveal_start*1000)}[a2];"
         f"[a0][a1][a2]amix=inputs=3:normalize=0,alimiter=limit=0.89,"
         f"apad=whole_dur={body_start},atrim=0:{body_start}[out]",
         "-map", "[out]", "-ac", "2", "-ar", "48000", f"{WORK}/audio.wav"])

    run(["ffmpeg", "-v", "error", "-y", "-i", f"{WORK}/video.mp4", "-i", f"{WORK}/audio.wav",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", OUT])
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", OUT], capture_output=True, text=True).stdout.strip()
    print(f"\n已写出 {OUT}  {dur}s  (bodyStart={body_start})")
    print(f"时序自检：引导语 {lead_start}-{lead_end} / 快闪 {flash_start}-{flash_end} "
          f"(间隔 {flash_start-lead_end:.3f}s，规格要求 ≤0.05) / 标题揭示 {reveal_start}-{reveal_end}")


if __name__ == "__main__":
    main()
