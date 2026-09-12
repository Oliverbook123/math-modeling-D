# -*- coding: utf-8 -*-
"""生成02的汇总summary.json和result2.xlsx"""
import json, os, shutil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "02")

methods = [
    {"key": "greedy", "label": "方案1: 贪心+优先级", "output_dir": "code/output/02/method1_greedy", "xlsx_name": "result2_greedy.xlsx"},
    {"key": "ilp", "label": "方案2: 整数规划ILP", "output_dir": "code/output/02/method2_ilp", "xlsx_name": "result2_ilp.xlsx"},
    {"key": "greedy_ls", "label": "方案3: 贪心+局部搜索", "output_dir": "code/output/02/method3_greedy_ls", "xlsx_name": "result2_greedy_ls.xlsx"},
    {"key": "sa", "label": "方案4: 模拟退火", "output_dir": "code/output/02/method4_sa", "xlsx_name": "result2_sa.xlsx"},
]

summary = {"methods": {}, "best_method": None, "best_score": None}
best_method = None
best_score = None

for m in methods:
    summary_path = os.path.join(PROJECT_ROOT, m["output_dir"], "summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            ms = json.load(f)
        obj = ms.get("目标函数", {})
        table1 = ms.get("表1", {})
        score = (
            obj.get("第1层_撤销总数", 999),
            obj.get("第2层_A撤销", 999),
            obj.get("第3层_调整数", 999),
            obj.get("第4层_总调整幅度", 999),
        )
        summary["methods"][m["key"]] = {
            "label": m["label"],
            "status": "success",
            "table1": table1,
            "objective": obj,
            "conflicts": ms.get("最终冲突数", ms.get("自检", {}).get("最终冲突数", -1)),
        }
        if best_score is None or score < best_score:
            best_score = score
            best_method = m["key"]
    else:
        summary["methods"][m["key"]] = {"label": m["label"], "status": "missing"}

summary["best_method"] = best_method
summary["best_score"] = list(best_score) if best_score else None

# 复制最优方法的xlsx
if best_method:
    for m in methods:
        if m["key"] == best_method:
            src = os.path.join(PROJECT_ROOT, m["output_dir"], m["xlsx_name"])
            dst = os.path.join(OUTPUT_DIR, "result2.xlsx")
            if os.path.exists(src):
                shutil.copy2(src, dst)
                print(f"result2.xlsx: {dst} (from {m['label']})")

# 保存summary.json
summary_path = os.path.join(OUTPUT_DIR, "summary.json")
with open(summary_path, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"summary.json: {summary_path}")

# 打印汇总
print()
print(f"{'方案':<20} {'冲突':>4} {'撤销':>4} {'A撤':>4} {'调整':>4} {'幅度':>6}")
print("-" * 50)
for key, info in summary["methods"].items():
    if info["status"] == "success":
        obj = info.get("objective", {})
        table1 = info.get("table1", {})
        a_rev = table1.get("A", {}).get("撤销", 0)
        print(f"{info['label']:<20} {info['conflicts']:>4} {obj.get('第1层_撤销总数', '?'):>4} {a_rev:>4} {obj.get('第3层_调整数', '?'):>4} {obj.get('第4层_总调整幅度', '?'):>6}")
    else:
        print(f"{info['label']:<20} {'N/A':>4}")
print(f"\n最优方法: {summary['methods'].get(best_method, {}).get('label', 'N/A')}")
