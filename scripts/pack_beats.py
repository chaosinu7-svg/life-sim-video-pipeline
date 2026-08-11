#!/usr/bin/env python3
"""把 SCRIPT.md 打包成镜头节拍（beats），落在 4–8 秒的甜点区。

为什么要这一步：hbg-life-simulation 要求 STORYBOARD_BASE.json 由 agent 语义编排，
但它没给编排工具。手工排 150+ 镜既慢又容易出现 20 秒以上的缺图缺陷。
本脚本用真实语速把段落装箱成节拍，保证零镜头超时，再由 agent 逐条配画面。

用法：
    python3 pack_beats.py [--rate 5.62] [--out /tmp/beats.json]

    --rate 是**实测**语速（字/秒），不要用 skill 手册里的 3.4–4.2。
    Edge TTS 云健 +0% 实测 4.68；+20% 得 5.62，对齐 B站爆款的 5.59。
    先跑一次 build_narration.mjs，用 audio_meta.body.duration 除以正文字数得到真值。
"""
import re, json, argparse
from collections import Counter

TARGET = 6.4    # 目标镜头时长
MAX = 9.5       # 单镜上限（skill 规定 >12 秒必须拆，>16 秒判缺图，留足余量）

# 重锤短句：允许单独成镜，不与相邻句合并。
# ⚠️ 这是**逐集不同**的，必须每集自己定。漏一条不会报错，但那一句会被并进
# 前一镜，**从此往后所有镜头编号平移一位**——已生成的图会全部配错画面。
# 用 --punch punch.txt 显式指定（每行一句），不要依赖下面的默认值。
DEFAULT_PUNCH = {
    "他没抬头。", "四。", "后面没有了。", "是他在办手续。", "你手抖。",
    "你没觉得烫。", "你站住了。", "你的名字在上面。", "他是不用再写了。",
}


def load_paragraphs(path="SCRIPT.md"):
    """按章节读出正文段落，跳过标题与元数据行。"""
    ch, paras = 0, []
    for ln in open(path).read().split("\n"):
        s = ln.strip()
        if s.startswith("## 第") and "章" in s:
            ch += 1
            continue
        if not s or s.startswith("#") or s == "- 无":
            continue
        paras.append((ch, s))
    return paras


def pack(paras, rate, punch):
    """贪心装箱：同章内累加句子直到接近 TARGET，超过 MAX 就断开。"""
    units = []
    for c, p in paras:
        if p in punch:
            units.append((c, p, True))
            continue
        for s in (re.findall(r"[^。！？]*[。！？]", p) or [p]):
            if s.strip():
                units.append((c, s.strip(), False))

    beats, cur = [], None
    for c, s, is_punch in units:
        d = len(s) / rate
        if is_punch:
            if cur:
                beats.append(cur)
                cur = None
            beats.append([c, s, d])
            continue
        if cur and cur[0] == c and (cur[2] + d) <= MAX and cur[2] < TARGET:
            cur[1] += s
            cur[2] += d
        else:
            if cur:
                beats.append(cur)
            cur = [c, s, d]
            while cur[2] > MAX:            # 单句超长，硬切
                cut = int(MAX * rate)
                beats.append([c, cur[1][:cut], cut / rate])
                cur = [c, cur[1][cut:], len(cur[1][cut:]) / rate]
    if cur:
        beats.append(cur)
    return beats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=5.62, help="实测语速 字/秒")
    ap.add_argument("--script", default="SCRIPT.md")
    ap.add_argument("--out", default="/tmp/beats.json")
    ap.add_argument("--punch", default=None,
                    help="重锤短句清单，每行一句。强烈建议逐集显式提供")
    a = ap.parse_args()

    paras = load_paragraphs(a.script)
    if a.punch:
        punch = {l.strip() for l in open(a.punch) if l.strip()}
        print(f"重锤短句 {len(punch)} 条（来自 {a.punch}）")
    else:
        punch = DEFAULT_PUNCH
        print(f"⚠️ 用的是默认重锤清单 {len(punch)} 条。逐集应当用 --punch 显式指定，"
              f"漏一条会让后续镜头编号整体平移。")
    beats = pack(paras, a.rate, punch)
    total = sum(b[2] for b in beats)

    over12 = [b for b in beats if b[2] > 12]
    over16 = [b for b in beats if b[2] > 16]
    print(f"镜头数 {len(beats)} | 正文约 {total:.0f}s = {total/60:.1f}分 | 平均 {total/len(beats):.2f}s")
    print(f"超12秒 {len(over12)}（需拆） | 超16秒 {len(over16)}（判缺图） | 短于2秒 {sum(1 for b in beats if b[2] < 2)}（重锤）")
    print("每章:", dict(sorted(Counter(b[0] for b in beats).items())))
    if over16:
        print("⚠️ 有镜头超过 16 秒，skill 会判为缺图缺陷：")
        for b in over16:
            print(f"   {b[2]:.1f}s  {b[1][:40]}")

    json.dump([{"ch": b[0], "text": b[1], "est": round(b[2], 2)} for b in beats],
              open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"已写出 {a.out}")


if __name__ == "__main__":
    main()
