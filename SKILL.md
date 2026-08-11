---
name: producing-life-sim-episodes
description: Use when working on the 人生副本 / 模拟人生 long-form narrative video line — starting a new EP, choosing a topic or title, turning a Chinese script into a rendered MP4, or fixing defects found in a cut. Also use when a rendered video looks fine to the QA scripts but wrong on screen.
---

# 人生副本出片

## 这是什么

架在开源 skill `hbg-life-simulation` 之上的**加固层**。那个 skill 提供流水线
（TTS、分镜校验、样式门、渲染、成片质检），本 skill 提供它没有的三样：
**选题与叙事方法论**、**已实证的踩坑防线**、**分镜编排与几何归一的自动化**。

底层流水线一律照 `$CODEX_HOME/skills/hbg-life-simulation` 走，不要另起炉灶。

## 铁律

**自动质检查不出任何内容缺陷。**

`verify_final_video.sh` 只管黑帧、静音、响度、分辨率、True Peak。EP01 那次
它全绿，而成片里同时存在：标题卡整段丢失、出现剧本里不存在的人名、
屏幕数字与旁白对不上、合同"先公示后签署"的日期矛盾、手机屏幕朝镜头而人物在看背面、
结尾记账本换成了另一本、人物该失眠却在笑。

**「渲染成功 + 质检全绿」不等于能交付。交片前必须逐镜看。**

不要说"已完成"，说"质检项全绿，还有 N 镜没人看过"。

## 流程

| 步 | 动作 | 工具 |
|---|---|---|
| 1 | 定选题与标题 | `topic-and-narrative.md` |
| 2 | 写文案，冻结成 `SCRIPT_SOURCE.md` | 同上，六条叙事机制 |
| 3 | `PROJECT_SPEC.json` + `CHARACTERS.md` | ⚠️横屏必须显式写 `captionMaxChars: 18` |
| 4 | 出身份锚点图，**不过不许开批量** | codex 内置 image_gen |
| 5 | 真实 TTS，拿到实测语速 | `build_narration.mjs` |
| 6 | 排分镜 | `scripts/pack_beats.py --punch punch.txt` → 逐镜配画面 → `scripts/build_storyboard.py` |
| 7 | 出图 | codex，**只出图不碰几何** |
| 8 | 几何归一 | `scripts/normalize_scenes.py --apply` |
| 9 | 开头 | `scripts/build_flash.py` → `scripts/build_opening.py` → **人工批准**后绑定 |
| 10 | 合成、样式门、渲染 | `build_composition.mjs` → `validate_style_system.mjs` → `render_streaming_ffmpeg.mjs` |
| 11 | 成片质检 + **逐镜人工复看** | `verify_final_video.sh` + 联系表 |
| 12 | 抖音封面 | codex 直接出图，**标题文字让模型渲染进画面**，1080×1440 |

改过文案就跑 `scripts/remap_scenes.py`，否则所有图配错画面且不报错。

封面是**专门画的**，不是从片里截图——两条爆款的封面画风都和正片不一样。构图靠**表情对比**把故事讲完（一个得意、一个忍着）。

⚠️ **封面是「禁止汉字」那条规则的唯一例外。** 正片 155 镜一律禁汉字（模型写不对，出过剧本里不存在的人名），
但**封面的标题必须让模型直接渲染进画面**——GPT image 渲染中文够清晰，字体是海报级粗黑体带厚描边，
比事后用 drawtext/PIL 叠字好得多。**不要叠字，主理人已两次否决这个方案。**
prompt 里写死两行文字内容、颜色、描边，并要求"中文必须字形正确、笔画完整、没有错字"，有错字就重生成。

第 6 步的 `punch.txt` 是**逐集自己定**的重锤短句清单（允许单独成镜的那些狠句子，
每行一句）。**漏一条不会报错，但那句会被并进前一镜，从此往后所有镜头编号平移一位。**
EP01 实测：少一条就从第 10 镜起全部错位。

## 语速：不要用手册值

手册估 3.4–4.2 字/秒，实际差很远。**先跑一次 TTS 量真值**，再拿去排分镜。

| 来源 | 字/秒 |
|---|---|
| skill 手册估算 | 3.4–4.2 |
| Edge TTS 云健 `+0%` 实测 | **4.68** |
| B站爆款实测 | **5.59 / 6.05** |

对齐爆款节奏用 `bodyRate: +20%`（得 5.62）。开头两句可再快到 `+45%`。

## 踩坑

九条已实证的坑全在 `pitfalls.md`。**出图前和渲染前各读一次。**
最贵的三条：开头拼接禁用 `-c copy`（标题卡会静默丢失）；
生图侧禁做几何（会补黑边）；`codex exec` 后台跑要加 `< /dev/null`（否则挂在 stdin 一张图不出）。

## 红旗

出现这些念头，停下来：

- 「渲染成功了，交付吧」→ 你还没看过画面
- 「让 codex 顺手把尺寸调好」→ 它会补黑边
- 「这几张图差不多，不用逐张看」→ 林砚就是这么进去的
- 「年轻女角色的提示词跟中年角色写法一样，应该没事」→ 会跑成日系美少女，见第九条
- 「改一句文案而已，图不用动」→ 编号会平移，全片配错
- 「质检报了静音，音效没进去」→ 先逐 0.5 秒量峰值，脉冲音效会被误判
- 「开头单独播是好的」→ `-c copy` 拼的文件单独播都是好的

## 交付

成片之外另导分轨（旁白、开头音效、引导语、标题）+ 无声版视频 + 配乐时间码，
主理人自己后期配乐。成片不带 BGM，`bgmVolume` 设 0。
