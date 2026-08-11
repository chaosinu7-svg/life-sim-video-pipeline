#!/usr/bin/env python3
"""选题雷达：每天扫一遍同品类账号，找出「跑赢自己基线」的选题。

为什么看相对值不看绝对播放：
    绝对播放混着账号体量。一个均播 2000 的号突然出了条 5 万，
    说明**那个选题**有东西；一个均播 50 万的号出了条 20 万，说明那个选题拉胯。
    倍数才是选题信号，绝对值是账号信号。

用法：
    python3 topic_radar.py                # 扫默认账号池
    python3 topic_radar.py --add 某账号    # 往池子里加号
    python3 topic_radar.py -n 40          # 每个号看最近 40 条

账号池存在 ~/.life-sim/radar_accounts.txt，一行一个。
历史快照存在 ~/.life-sim/radar_history.jsonl，用来看一条片子是慢热还是真死。
"""
import argparse, json, os, re, statistics, subprocess, sys

HOME = os.path.expanduser("~/.life-sim")
ACCOUNTS_FILE = os.path.join(HOME, "radar_accounts.txt")
HISTORY_FILE = os.path.join(HOME, "radar_history.jsonl")

# 2026-08-11 从 B站「人生副本」品类搜索里扒出来的同品类账号。
# 这些号全在日更同一个句式，公开播放量就是免费的 A/B 测试结果。
SEED_ACCOUNTS = [
    "伴山拾字", "副本笔记", "一万种人生_", "万象人生_", "赛博人生卡",
    "百味人生i", "体演人生", "人生模拟卡", "赛博模拟人生", "赛博之家",
    "人间行记", "副本体验师", "看副本人生",
]


def load_accounts():
    if not os.path.exists(ACCOUNTS_FILE):
        os.makedirs(HOME, exist_ok=True)
        with open(ACCOUNTS_FILE, "w") as f:
            f.write("\n".join(SEED_ACCOUNTS) + "\n")
    with open(ACCOUNTS_FILE) as f:
        return [l.strip() for l in f if l.strip() and not l.startswith("#")]


def fetch(account, n):
    """bili user-videos 会先打一行「🔍 匹配到:」再吐 YAML，得跳过。"""
    try:
        out = subprocess.run(
            ["bili", "user-videos", account, "-n", str(n), "--json"],
            capture_output=True, text=True, timeout=120,
        ).stdout
    except subprocess.TimeoutExpired:
        return []
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0)).get("data") or []
    except json.JSONDecodeError:
        return []
    vids = []
    for v in data:
        view = (v.get("stats") or {}).get("view") or 0
        title = (v.get("title") or "").strip()
        if title and view:
            vids.append({"title": title, "view": view, "bvid": v.get("bvid", ""),
                         "account": account})
    return vids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", "--num", type=int, default=25, help="每个号看最近多少条")
    ap.add_argument("--add", action="append", default=[], help="把账号加进池子")
    ap.add_argument("--min-ratio", type=float, default=2.0, help="超过自身中位数几倍才算跑赢")
    args = ap.parse_args()

    accounts = load_accounts()
    if args.add:
        accounts = sorted(set(accounts) | set(args.add))
        with open(ACCOUNTS_FILE, "w") as f:
            f.write("\n".join(accounts) + "\n")
        print(f"账号池已更新，现有 {len(accounts)} 个\n")

    winners, all_vids = [], []
    for acc in accounts:
        vids = fetch(acc, args.num)
        if len(vids) < 4:
            print(f"  ⚠️  {acc}: 只取到 {len(vids)} 条，跳过", file=sys.stderr)
            continue
        med = statistics.median(v["view"] for v in vids)
        all_vids += vids
        for v in vids:
            v["median"] = med
            v["ratio"] = v["view"] / med if med else 0
            if v["ratio"] >= args.min_ratio:
                winners.append(v)
        print(f"  {acc:<12} {len(vids):>3} 条  中位数 {int(med):>8,}", file=sys.stderr)

    with open(HISTORY_FILE, "a") as f:
        for v in all_vids:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    winners.sort(key=lambda v: v["ratio"], reverse=True)
    print(f"\n{'倍数':>6} {'播放':>10}  {'账号':<12} 标题")
    print("-" * 88)
    for v in winners[:30]:
        print(f"{v['ratio']:>5.1f}x {v['view']:>10,}  {v['account'][:12]:<12} {v['title'][:46]}")
    print(f"\n共扫 {len(all_vids)} 条，{len(winners)} 条跑赢自身基线 {args.min_ratio}x。")
    print(f"历史已追加到 {HISTORY_FILE}（同一条片子多跑几天能看出是慢热还是真死）")


if __name__ == "__main__":
    main()
