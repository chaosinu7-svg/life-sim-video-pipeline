#!/usr/bin/env python3
"""用 facebook/musicgen-small 生成本片 BGM。

走的是 media-use 官方的本地回退路径（无需 HeyGen 账号、无需任何 API key），
结构照抄 ~/.codex/skills/media-use/audio/scripts/lib/bgm.mjs 里的 musicgenScript：
生成一段种子 → 余弦交叉淡化循环铺到全片长度。

提示词按本片需求定：恒定垫底、无旋律钩子、冷、克制、不推动。
"""
import math, os
from pathlib import Path
import numpy as np
import soundfile as sf
from transformers import MusicgenForConditionalGeneration, AutoProcessor

PROMPT = (
    "sparse minimal ambient underscore for a serious documentary, "
    "slow sustained low strings and occasional soft single piano notes, "
    "cold restrained and understated, quietly melancholic without sentimentality, "
    "no drums, no percussion, no beat, no melodic hook, no build-up, "
    "steady and unchanging throughout, dark neutral harmony, cinematic bed"
)
OUT = "assets/audio/bgm/musicgen-seed.wav"
TARGET_S = 1046.0
SEED_S = 30.0
TOKEN_RATE = 50
CROSSFADE_S = 1.2


def apply_fade(arr, sr, fade_in_s=0.08, fade_out_s=0.5):
    n_in = min(int(round(fade_in_s * sr)), arr.shape[0] // 2)
    n_out = min(int(round(fade_out_s * sr)), arr.shape[0] // 2)
    if n_in > 1:
        arr[:n_in] *= np.linspace(0.0, 1.0, n_in, dtype="float32")
    if n_out > 1:
        arr[-n_out:] *= np.linspace(1.0, 0.0, n_out, dtype="float32")
    return arr


def loop_crossfade(seed, target_len, xf):
    if seed.shape[0] >= target_len:
        return seed[:target_len]
    xf = min(xf, seed.shape[0] // 2)
    if xf < 1:
        reps = int(math.ceil(target_len / seed.shape[0]))
        return np.tile(seed, reps)[:target_len]
    t = np.linspace(0.0, 1.0, xf, dtype="float32")
    fade_out = np.cos(t * (math.pi / 2))
    fade_in = np.sin(t * (math.pi / 2))
    out = seed.copy()
    while out.shape[0] < target_len:
        tail = out[-xf:] * fade_out
        head = seed[:xf] * fade_in
        out = np.concatenate([out[:-xf], tail + head, seed[xf:]])
    return out[:target_len]


def main():
    Path(os.path.dirname(OUT)).mkdir(parents=True, exist_ok=True)
    print("[musicgen] 加载 facebook/musicgen-small ...", flush=True)
    processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
    model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
    model.eval()
    sr = int(model.config.audio_encoder.sampling_rate)
    tokens = max(1, int(math.ceil(SEED_S * TOKEN_RATE)))
    print(f"[musicgen] 采样率={sr} 种子={SEED_S}s tokens={tokens}", flush=True)
    inputs = processor(text=[PROMPT], padding=True, return_tensors="pt")
    audio = model.generate(**inputs, do_sample=True, guidance_scale=3.0, max_new_tokens=tokens)
    seed = audio[0, 0].cpu().numpy().astype("float32")
    print(f"[musicgen] 种子生成完毕 {seed.shape[0]/sr:.2f}s", flush=True)
    target_len = int(round(TARGET_S * sr))
    full = loop_crossfade(seed, target_len, int(round(CROSSFADE_S * sr)))
    full = apply_fade(full, sr, 3.0, 3.0)
    peak = float(np.max(np.abs(full))) or 1.0
    full = (full / peak) * 0.7
    sf.write(OUT, full, sr)
    print(f"[musicgen] 已写出 {OUT}  {full.shape[0]/sr:.1f}s", flush=True)


if __name__ == "__main__":
    main()
