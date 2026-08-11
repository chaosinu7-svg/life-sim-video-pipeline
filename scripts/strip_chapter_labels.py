#!/usr/bin/env python3
"""渲染前清掉 audio_meta.chapters，去掉画面上的「第X幕 标题」。

为什么这么做：渲染器在 render_streaming_ffmpeg.mjs 第 180 行按
audio_meta.chapters 往 ASS 里画章节卡。主理人要求画面上不出现章节标记
（自己在剪辑里断），但 build_narration 每次都会重新写回这个数组。

所以这一步必须在 build_narration 之后、render 之前跑，且每次重跑 TTS 后都要再跑一次。
"""
import json, sys
p = "audio_meta.json"
d = json.load(open(p, encoding="utf-8"))
n = len(d.get("chapters") or [])
d["chapters"] = []
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"✓ 已清空 {n} 条章节标签，画面上不会再出现「第X幕」")
