#!/usr/bin/env python3
"""改过文案之后，把已生成的图按新的镜头编号重新对应。

为什么需要它：镜头是靠 cue（正文原句片段）锚定的。文案一改，节拍重排、
编号整体平移，**已有的 sXXX.png 就会全部配错画面**——而且渲染不会报错，
成片能正常播放，只有逐镜看才发现。

做法：用文本相似度把新节拍匹配回旧节拍，继承对应的图；匹配不上的列出来重生成。

用法：
    python3 remap_scenes.py --old /tmp/beats_old.json --new /tmp/beats_new.json [--apply]

不带 --apply 只报告，不动文件。
"""
import json, difflib, os, shutil, argparse

THRESHOLD = 0.60   # 低于此相似度视为新镜头
SRC = "assets/generated/scenes"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", default="/tmp/beats_old.json")
    ap.add_argument("--new", default="/tmp/beats_new.json")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    old = json.load(open(a.old))
    new = json.load(open(a.new))
    oldtexts = [b["text"] for b in old]

    pairs, used, miss = {}, set(), []
    for i, b in enumerate(new):
        best, bestr = None, 0.0
        for j, ot in enumerate(oldtexts):
            if j in used:
                continue
            r = difflib.SequenceMatcher(None, b["text"], ot).ratio()
            if r > bestr:
                bestr, best = r, j
        if bestr >= THRESHOLD:
            pairs[i] = best
            used.add(best)
        else:
            miss.append((i, b["ch"], b["text"][:44], round(bestr, 2)))

    print(f"新节拍 {len(new)} 条 | 可继承 {len(pairs)} | 需新生成 {len(miss)}")
    for i, ch, txt, r in miss:
        print(f"  s{i+1:03d}  c{ch}  相似度{r}  {txt}")

    if not a.apply:
        print("\n（仅报告。加 --apply 执行搬运）")
        return

    tmp = "/tmp/_scenes_remap"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    moved = 0
    for ni, oj in pairs.items():
        src = f"{SRC}/s{oj+1:03d}.png"
        if os.path.exists(src):
            shutil.copy(src, f"{tmp}/s{ni+1:03d}.png")
            moved += 1
    backup = "assets/generated/_scenes_old_ids"
    shutil.rmtree(backup, ignore_errors=True)
    shutil.move(SRC, backup)
    shutil.move(tmp, SRC)
    print(f"\n已搬运 {moved} 张到新编号；旧编号原图备份在 {backup}/")
    json.dump([i + 1 for i, *_ in miss], open("/tmp/need_new.json", "w"))
    print("待生成编号写入 /tmp/need_new.json")


if __name__ == "__main__":
    main()
