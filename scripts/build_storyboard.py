#!/usr/bin/env python3
"""把「节拍 + 画面设计」组装成 STORYBOARD_BASE.json，并生成逐镜提示词。

hbg-life-simulation 的校验器要求每个镜头的 cue 是 SCRIPT.md 里**按顺序出现**的
原文片段。本脚本自动挑选可定位的 cue，并处理三件手工做很容易错的事：

1. 镜头运动交替（skill 要求不许连续相同运动，否则像 PPT）
2. 数字白名单——描述里含具体数字的镜头必须放开阿拉伯数字，否则那一镜就废了
3. 汉字一律禁止（生图模型写不对中文，出过剧本里不存在的人名）

用法：
    python3 build_storyboard.py --beats /tmp/beats.json --visuals /tmp/visuals.json

visuals.json 格式：{"<节拍下标>": [画面描述, 景别, 运动, 人数, [允许角色], 是否高风险]}
角色 id 与 characters.json 的键对应。
"""
import json, re, argparse, os

MOTION_FIX = {"pan-down": "zoom-in", "pan-up": "zoom-out"}
OPP = {"zoom-in": "zoom-out", "zoom-out": "zoom-in",
       "pan-left": "pan-right", "pan-right": "pan-left"}

# 描述里出现这些，说明画面主体就是那个数字/日期，必须放开阿拉伯数字
DIGIT_KW = ["时间", "日期", "编号", "金额", "数字", "台历", "日历", "百分之",
            "点几", "余额", "工号", "分数", "价格", "费用", "%", ":"]

STYLE_DEFAULT = (
    "现代中式都市写实漫画，干净线稿加柔和上色，人物有适度体积感的明暗过渡"
    "（不是纯平涂也不是重厚涂），中等偏低饱和度，冷灰蓝为主色调，"
    "写实成年人体比例与长相，非Q版非大眼萌系，背景做虚化处理。")

FRAME = (
    "【画幅】必须是原生 16:9 横向宽幅构图（1920×1080），主体内容铺满整个画面，"
    "四边一律不留白边、不留黑边、不做信箱式或立柱式留边。"
    "人物头顶与画面上边缘之间要留出余量，禁止切到头顶或下巴。")

BAN_BASE = ("画面中不得出现任何可辨认的汉字、中文字幕、品牌logo、水印或签名。"
            "不得出现多余的手、融合的手指、断离的肢体或结构不可能的人体。")
BAN_NODIGIT = BAN_BASE + "也不要出现任何可读的字母或数字，屏幕与纸张上的内容用抽象的线条和色块表示。"
BAN_DIGIT = BAN_BASE + "允许并且需要出现清晰可读的阿拉伯数字（这正是本镜头的主体内容），但除数字外不得出现任何可读的汉字或单词。"
HIGH_RISK = ("\n【高风险】必须单图生成，禁止进宫格。生成后在全分辨率下逐指追溯到唯一的手腕和前臂；"
             "**手机屏幕必须朝向持机人自己、镜头看到的是手机背面**；工具与手真实接触。"
             "不合格整张重生成，不许裁切或模糊掩盖。")


def cue_candidates(txt):
    sents = [s.strip() for s in re.findall(r"[^。！？]*[。！？]?", txt) if s.strip()]
    for s in sents[:3]:
        for n in (12, 16, 20, 26, 34, len(s)):
            if n <= len(s):
                yield s[:n]
        if len(s) < 12:
            yield s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--beats", default="/tmp/beats.json")
    ap.add_argument("--visuals", default="/tmp/visuals.json")
    ap.add_argument("--script", default="SCRIPT.md")
    ap.add_argument("--characters", default="characters.json",
                    help="角色 id → 不可变特征描述")
    ap.add_argument("--style", default=None, help="覆盖默认画风段落")
    a = ap.parse_args()

    beats = json.load(open(a.beats))
    V = {int(k): v for k, v in json.load(open(a.visuals)).items()}
    if len(V) != len(beats):
        raise SystemExit(f"画面设计 {len(V)} 条 ≠ 节拍 {len(beats)} 条")
    TR = json.load(open(a.characters)) if os.path.exists(a.characters) else {}
    style = a.style or STYLE_DEFAULT
    script = open(a.script).read()

    out, prompts, sf = [], [], 0
    for i, b in enumerate(beats):
        cue = next((c for c in cue_candidates(b["text"]) if script.find(c, sf) >= 0), None)
        if cue is None:
            raise SystemExit(f"节拍 {i} 无法在 SCRIPT.md 中按顺序定位：{b['text'][:30]}")
        sf = script.find(cue, sf) + max(1, len(cue))

        vis, shot, motion, cnt, allowed, hr = V[i]
        out.append({
            "id": f"s{i+1:03d}", "chapter": b["ch"], "cue": cue,
            "narration": b["text"], "description": vis,
            "characters": allowed,
            "participants": {"count": cnt, "allowed": allowed},
            "shot": shot, "motion": MOTION_FIX.get(motion, motion),
            "duration_hint": b["est"], "highRisk": hr,
            "asset": f"assets/generated/scenes/s{i+1:03d}.png",
        })

    # 运动交替：连续相同就翻向。hold 是刻意的停顿，不动。
    prev, flipped = None, 0
    for s in out:
        if s["motion"] == "hold":
            prev = "hold"
            continue
        if s["motion"] == prev:
            s["motion"] = OPP[s["motion"]]
            flipped += 1
        prev = s["motion"]

    for s in out:
        digits = any(k in s["description"] for k in DIGIT_KW) or re.search(r"[0-9]", s["description"])
        tr = "".join(TR[c] + "\n" for c in s["participants"]["allowed"] if c in TR)
        n = s["participants"]["count"]
        people = ("【人数】画面中不出现任何可辨认身份的人物。No recognizable person may appear."
                  if n == 0 else
                  f"【人数】画面中恰好可见 {n} 个人，且只允许是："
                  f"{'、'.join(s['participants']['allowed'])}。No other person may appear.")
        prompts.append({
            "id": s["id"], "chapter": s["chapter"], "highRisk": s["highRisk"],
            "asset": s["asset"],
            "prompt": f"{style}\n{FRAME}\n【画面】{s['description']}\n【景别】{s['shot']}\n"
                      f"{tr}{people}\n{BAN_DIGIT if digits else BAN_NODIGIT}"
                      f"{HIGH_RISK if s['highRisk'] else ''}",
        })

    json.dump(out, open("STORYBOARD_BASE.json", "w"), ensure_ascii=False, indent=2)
    json.dump(prompts, open("PROMPTS_SCENES.json", "w"), ensure_ascii=False, indent=1)
    nd = sum(1 for p in prompts if "允许并且需要出现清晰可读的阿拉伯数字" in p["prompt"])
    noface = sum(1 for s in out if s["participants"]["count"] == 0)
    print(f"STORYBOARD_BASE.json {len(out)} 镜 | 高风险 {sum(1 for s in out if s['highRisk'])}")
    print(f"运动翻向 {flipped} 处 | 放开数字 {nd} 镜 | 无人物 {noface} 镜 = {noface/len(out)*100:.0f}%（skill 要求 ≥25%）")
    print("PROMPTS_SCENES.json 已生成，下一步交给 codex 出图")


if __name__ == "__main__":
    main()
