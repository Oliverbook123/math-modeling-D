"""
问题4 主入口：放宽间隔约束的冲突消解

与问题2同框架，但 C 类装备新增"调整间隔时长"动作（与原间隔差异 ≤ 10Δt）。
依次运行 2 种消解方法，对比结果，生成输出文件。

输出:
  code/output/04/method1_greedy/result.csv + summary.json + result4_greedy.xlsx
  code/output/04/method2_sa/result.csv + summary.json + result4_sa.xlsx
  code/output/04/result4.xlsx  (最终采用的消解方案)
  code/output/04/summary.json  (各方法汇总对比 + 与问题2的对比)
"""

import json
import os
import subprocess
import time

import openpyxl

# ============================================================
# 路径配置
# ============================================================
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "04")

# ============================================================
# 方法定义
# ============================================================
METHODS = [
    {
        "key": "greedy_interval",
        "label": "方案1: 贪心+间隔维度",
        "script": "code/04/method1_greedy/greedy.py",
        "output_dir": "code/output/04/method1_greedy",
        "xlsx_name": "result4_greedy.xlsx",
    },
    {
        "key": "sa_interval",
        "label": "方案2: 模拟退火+间隔维度",
        "script": "code/04/method2_sa/sa.py",
        "output_dir": "code/output/04/method2_sa",
        "xlsx_name": "result4_sa.xlsx",
    },
    {
        "key": "greedy_ls_interval",
        "label": "方案3: 贪心+局部搜索+间隔维度",
        "script": "code/04/method3_greedy_ls/greedy_ls.py",
        "output_dir": "code/output/04/method3_greedy_ls",
        "xlsx_name": "result4_greedy_ls.xlsx",
    },
    {
        "key": "ilp_interval",
        "label": "方案4: 整数规划ILP+间隔动作",
        "script": "code/04/method4_ilp/ilp.py",
        "output_dir": "code/output/04/method4_ilp",
        "xlsx_name": "result4_ilp.xlsx",
    },
]

# 问题2 已知最优结果（method4_sa），用于论文对比"放开间隔约束多救回多少装备"
PROBLEM2_BEST = {
    "来源": "问题2 方案4_模拟退火",
    "撤销总数": 50,
    "调整数": 65,
    "总幅度": 393,
}


# ============================================================
# 运行单个方法
# ============================================================
def run_method(method_config):
    """运行单个消解方法脚本，读取其 summary.json"""
    script_path = os.path.join(PROJECT_ROOT, method_config["script"])
    output_dir = os.path.join(PROJECT_ROOT, method_config["output_dir"])

    print(f"\n{'='*60}")
    print(f"运行: {method_config['label']}")
    print(f"{'='*60}")

    if not os.path.exists(script_path):
        print(f"  ❌ 脚本不存在: {script_path}")
        return {"key": method_config["key"], "label": method_config["label"],
                "status": "missing", "error": f"脚本不存在: {script_path}"}

    start_time = time.time()
    try:
        result = subprocess.run(
            ["uv", "run", "--with", "openpyxl", "--with", "matplotlib", "--with", "pulp", "python", script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=900,  # SA 多种子，给 15 分钟
            env={**os.environ, "UV_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/"},
        )
        elapsed = time.time() - start_time
        if result.returncode == 0:
            print(f"  ✅ 运行成功 ({elapsed:.1f}s)")
            summary_path = os.path.join(output_dir, "summary.json")
            if os.path.exists(summary_path):
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                return {"key": method_config["key"], "label": method_config["label"],
                        "status": "success", "elapsed": elapsed, "summary": summary,
                        "output_dir": output_dir, "xlsx_name": method_config["xlsx_name"]}
            return {"key": method_config["key"], "label": method_config["label"],
                    "status": "partial", "elapsed": elapsed, "error": "summary.json不存在"}
        print(f"  ❌ 运行失败 (exit {result.returncode})")
        print(f"  stderr: {result.stderr[-500:]}")
        return {"key": method_config["key"], "label": method_config["label"],
                "status": "failed", "elapsed": elapsed, "error": result.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"key": method_config["key"], "label": method_config["label"],
                "status": "timeout", "elapsed": time.time() - start_time, "error": "运行超时(900s)"}
    except Exception as e:
        return {"key": method_config["key"], "label": method_config["label"],
                "status": "error", "elapsed": time.time() - start_time, "error": str(e)}


# ============================================================
# 汇总与最优方法选择
# ============================================================
def generate_summary(method_results):
    """字典序比较各方法：撤销总数 → A撤销 → 调整数 → 幅度"""
    summary = {"methods": {}, "best_method": None, "best_score": None,
               "问题2最优参照": PROBLEM2_BEST}
    best_method, best_score = None, None
    for result in method_results:
        key = result["key"]
        if result["status"] == "success":
            ms = result["summary"]
            obj = ms.get("目标函数", {})
            summary["methods"][key] = {
                "label": result["label"], "status": "success",
                "elapsed": result["elapsed"],
                "table1": ms.get("表1", {}),
                "objective": obj,
                "conflicts": ms.get("最终冲突数", -1),
            }
            score = (obj.get("第1层_撤销总数", 999),
                     obj.get("第2层_A撤销", 999),
                     obj.get("第3层_调整数", 999),
                     obj.get("第4层_总调整幅度", 999))
            if best_score is None or score < best_score:
                best_score, best_method = score, key
        else:
            summary["methods"][key] = {"label": result["label"], "status": result["status"],
                                       "elapsed": result.get("elapsed", 0),
                                       "error": result.get("error", "未知错误")}
    summary["best_method"] = best_method
    summary["best_score"] = list(best_score) if best_score else None

    # 与问题2最优对比
    if best_score is not None:
        summary["对比问题2"] = {
            "撤销减少": PROBLEM2_BEST["撤销总数"] - best_score[0],
            "说明": "负值表示问题4比问题2撤销更多（异常情况，应排查）",
        }
    return summary


def generate_result4_xlsx(method_results, summary):
    """采用最优方法的结果生成最终 result4.xlsx"""
    best_method = summary["best_method"]
    if not best_method:
        print("  ❌ 无最优方法，无法生成 result4.xlsx")
        return
    best_result = next((r for r in method_results
                        if r["key"] == best_method and r["status"] == "success"), None)
    if not best_result:
        print(f"  ❌ 最优方法 {best_method} 结果不可用")
        return
    src = os.path.join(best_result["output_dir"], best_result["xlsx_name"])
    dst = os.path.join(OUTPUT_DIR, "result4.xlsx")
    if os.path.exists(src):
        wb = openpyxl.load_workbook(src)
        wb.save(dst)
        wb.close()
        print(f"  ✅ result4.xlsx 已生成: {dst}")
        print(f"     采用方法: {best_result['label']}")
    else:
        print(f"  ❌ 源文件不存在: {src}")


def print_summary_table(summary):
    print(f"\n{'='*80}")
    print("汇总对比（问题4）")
    print(f"{'='*80}")
    print(f"{'方案':<24} {'状态':>4} {'冲突':>4} {'撤销':>4} {'A撤':>4} {'调整':>4} {'幅度':>6} {'耗时':>8}")
    print("-" * 80)
    for key, info in summary["methods"].items():
        if info["status"] == "success":
            obj = info.get("objective", {})
            a_rev = info.get("table1", {}).get("A", {}).get("撤销", 0)
            print(f"{info['label']:<24} {'✅':>4} {info['conflicts']:>4} "
                  f"{obj.get('第1层_撤销总数', '?'):>4} {a_rev:>4} "
                  f"{obj.get('第3层_调整数', '?'):>4} {obj.get('第4层_总调整幅度', '?'):>6} "
                  f"{info['elapsed']:>7.1f}s")
        else:
            print(f"{info['label']:<24} {'❌':>4} {'':>4} {'':>4} {'':>4} {'':>4} {'':>6} "
                  f"{info.get('elapsed', 0):>7.1f}s")
    print("-" * 80)
    p2 = summary["问题2最优参照"]
    print(f"参照: 问题2最优（SA）撤销 {p2['撤销总数']} / 调整 {p2['调整数']} / 幅度 {p2['总幅度']}")
    if summary.get("对比问题2"):
        print(f"对比: {summary['对比问题2']}")
    if summary["best_method"]:
        best = summary["methods"][summary["best_method"]]
        print(f"最优方法: {best['label']}  得分: {summary['best_score']}")


def main():
    print("=" * 60)
    print("问题4: 放宽间隔约束的冲突消解")
    print("=" * 60)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    method_results = [run_method(m) for m in METHODS]
    summary = generate_summary(method_results)
    print_summary_table(summary)

    print(f"\n{'='*60}")
    print("生成最终结果文件")
    print(f"{'='*60}")
    generate_result4_xlsx(method_results, summary)

    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  ✅ summary.json 已保存: {summary_path}")

    success = sum(1 for r in method_results if r["status"] == "success")
    print(f"\n{'='*60}")
    print(f"完成: {success}/{len(METHODS)} 个方法成功运行")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
