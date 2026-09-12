"""
问题2 主入口：时频冲突消解
依次运行4种冲突消解方法，对比结果，生成输出文件

输出:
  code/output/02/method1_greedy/result.csv + summary.json + result2_greedy.xlsx
  code/output/02/method2_ilp/result.csv + summary.json + result2_ilp.xlsx
  code/output/02/method3_greedy_ls/result.csv + summary.json + result2_greedy_ls.xlsx
  code/output/02/method4_sa/result.csv + summary.json + result2_sa.xlsx
  code/output/02/result2.xlsx  (最终采用的消解方案)
  code/output/02/summary.json  (各方法汇总对比)
"""

import json
import os
import subprocess
import sys
import time

import openpyxl


# ============================================================
# 路径配置
# ============================================================

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 代码目录
CODE_DIR = os.path.join(PROJECT_ROOT, "code")
# 输出目录
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "02")
# 附件目录
ATTACHMENT_DIR = os.path.join(PROJECT_ROOT, "附件")


# ============================================================
# 方法定义
# ============================================================

# 4种消解方法的配置
METHODS = [
    {
        "key": "greedy",
        "label": "方案1: 贪心+优先级",
        "script": "code/02/method1_greedy/greedy.py",
        "output_dir": "code/output/02/method1_greedy",
        "xlsx_name": "result2_greedy.xlsx",
    },
    {
        "key": "ilp",
        "label": "方案2: 整数规划ILP",
        "script": "code/02/method2_ilp/ilp.py",
        "output_dir": "code/output/02/method2_ilp",
        "xlsx_name": "result2_ilp.xlsx",
    },
    {
        "key": "greedy_ls",
        "label": "方案3: 贪心+局部搜索",
        "script": "code/02/method3_greedy_ls/greedy_ls.py",
        "output_dir": "code/output/02/method3_greedy_ls",
        "xlsx_name": "result2_greedy_ls.xlsx",
    },
    {
        "key": "sa",
        "label": "方案4: 模拟退火",
        "script": "code/02/method4_sa/sa.py",
        "output_dir": "code/output/02/method4_sa",
        "xlsx_name": "result2_sa.xlsx",
    },
]


# ============================================================
# 运行单个方法
# ============================================================

def run_method(method_config):
    """
    运行单个消解方法
    
    参数:
        method_config: 方法配置字典
    返回:
        dict: 包含运行结果的字典
    """
    script_path = os.path.join(PROJECT_ROOT, method_config["script"])
    output_dir = os.path.join(PROJECT_ROOT, method_config["output_dir"])
    
    print(f"\n{'='*60}")
    print(f"运行: {method_config['label']}")
    print(f"脚本: {script_path}")
    print(f"{'='*60}")
    
    # 检查脚本是否存在
    if not os.path.exists(script_path):
        print(f"  ❌ 脚本不存在: {script_path}")
        return {
            "key": method_config["key"],
            "label": method_config["label"],
            "status": "missing",
            "error": f"脚本不存在: {script_path}",
        }
    
    # 运行脚本（使用 uv）
    start_time = time.time()
    try:
        result = subprocess.run(
            ["uv", "run", "--with", "openpyxl", "python", script_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600,  # 10分钟超时
            env={**os.environ, "UV_INDEX_URL": "https://mirrors.aliyun.com/pypi/simple/"},
        )
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"  ✅ 运行成功 ({elapsed:.1f}s)")
            # 读取summary.json
            summary_path = os.path.join(output_dir, "summary.json")
            if os.path.exists(summary_path):
                with open(summary_path, 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                return {
                    "key": method_config["key"],
                    "label": method_config["label"],
                    "status": "success",
                    "elapsed": elapsed,
                    "summary": summary,
                    "output_dir": output_dir,
                    "xlsx_name": method_config["xlsx_name"],
                }
            else:
                print(f"  ⚠️ summary.json不存在")
                return {
                    "key": method_config["key"],
                    "label": method_config["label"],
                    "status": "partial",
                    "elapsed": elapsed,
                    "error": "summary.json不存在",
                }
        else:
            print(f"  ❌ 运行失败 (exit code: {result.returncode})")
            print(f"  stderr: {result.stderr[-500:]}")
            return {
                "key": method_config["key"],
                "label": method_config["label"],
                "status": "failed",
                "elapsed": elapsed,
                "error": result.stderr[-500:],
                "stdout": result.stdout[-500:],
            }
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f"  ❌ 运行超时 ({elapsed:.1f}s)")
        return {
            "key": method_config["key"],
            "label": method_config["label"],
            "status": "timeout",
            "elapsed": elapsed,
            "error": "运行超时(600s)",
        }
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ❌ 运行异常: {e}")
        return {
            "key": method_config["key"],
            "label": method_config["label"],
            "status": "error",
            "elapsed": elapsed,
            "error": str(e),
        }


# ============================================================
# 生成汇总结果
# ============================================================

def generate_summary(method_results):
    """
    生成汇总对比文件
    
    参数:
        method_results: 各方法运行结果列表
    返回:
        dict: 汇总信息
    """
    summary = {
        "methods": {},
        "best_method": None,
        "best_score": None,
    }
    
    best_method = None
    best_score = None
    
    for result in method_results:
        key = result["key"]
        if result["status"] == "success":
            method_summary = result["summary"]
            summary["methods"][key] = {
                "label": result["label"],
                "status": "success",
                "elapsed": result["elapsed"],
                "table1": method_summary.get("表1", {}),
                "objective": method_summary.get("目标函数", {}),
                "conflicts": method_summary.get("最终冲突数", -1),
            }
            
            # 比较得分（字典序：撤销数 → A撤销 → 调整数 → 幅度）
            obj = method_summary.get("目标函数", {})
            score = (
                obj.get("第1层_撤销总数", 999),
                obj.get("第2层_A撤销", 999),
                obj.get("第3层_调整数", 999),
                obj.get("第4层_总调整幅度", 999),
            )
            
            if best_score is None or score < best_score:
                best_score = score
                best_method = key
        else:
            summary["methods"][key] = {
                "label": result["label"],
                "status": result["status"],
                "elapsed": result.get("elapsed", 0),
                "error": result.get("error", "未知错误"),
            }
    
    summary["best_method"] = best_method
    summary["best_score"] = list(best_score) if best_score else None
    
    return summary


# ============================================================
# 生成最终result2.xlsx
# ============================================================

def generate_result2_xlsx(method_results, summary):
    """
    生成最终的result2.xlsx（采用最优方法的结果）
    
    参数:
        method_results: 各方法运行结果列表
        summary: 汇总信息
    """
    best_method = summary["best_method"]
    if not best_method:
        print("  ❌ 无最优方法，无法生成result2.xlsx")
        return
    
    # 找到最优方法的结果
    best_result = None
    for result in method_results:
        if result["key"] == best_method:
            best_result = result
            break
    
    if not best_result or best_result["status"] != "success":
        print(f"  ❌ 最优方法{best_method}结果不可用")
        return
    
    # 复制最优方法的xlsx文件
    src_xlsx = os.path.join(best_result["output_dir"], best_result["xlsx_name"])
    dst_xlsx = os.path.join(OUTPUT_DIR, "result2.xlsx")
    
    if os.path.exists(src_xlsx):
        # 使用openpyxl复制（确保格式一致）
        wb = openpyxl.load_workbook(src_xlsx)
        wb.save(dst_xlsx)
        wb.close()
        print(f"  ✅ result2.xlsx已生成: {dst_xlsx}")
        print(f"     采用方法: {best_result['label']}")
    else:
        print(f"  ❌ 源文件不存在: {src_xlsx}")


# ============================================================
# 打印汇总表格
# ============================================================

def print_summary_table(summary):
    """打印汇总对比表格"""
    print(f"\n{'='*80}")
    print("汇总对比")
    print(f"{'='*80}")
    
    # 表头
    print(f"{'方案':<20} {'状态':>6} {'冲突':>4} {'撤销':>4} {'A撤':>4} {'调整':>4} {'幅度':>6} {'耗时':>8}")
    print("-" * 80)
    
    for key, info in summary["methods"].items():
        if info["status"] == "success":
            obj = info.get("objective", {})
            table1 = info.get("table1", {})
            a_rev = table1.get("A", {}).get("撤销", 0)
            print(f"{info['label']:<20} {'✅':>6} {info['conflicts']:>4} "
                  f"{obj.get('第1层_撤销总数', '?'):>4} {a_rev:>4} "
                  f"{obj.get('第3层_调整数', '?'):>4} {obj.get('第4层_总调整幅度', '?'):>6} "
                  f"{info['elapsed']:>7.1f}s")
        else:
            print(f"{info['label']:<20} {'❌':>6} {'':>4} {'':>4} {'':>4} {'':>4} {'':>6} "
                  f"{info.get('elapsed', 0):>7.1f}s")
    
    print("-" * 80)
    if summary["best_method"]:
        best_info = summary["methods"][summary["best_method"]]
        print(f"最优方法: {best_info['label']}")
        print(f"最优得分: {summary['best_score']}")


# ============================================================
# 主函数
# ============================================================

def main():
    """
    主函数：依次运行4种冲突消解方法，汇总对比结果
    流程：
    1. 依次运行贪心、ILP、贪心+局部搜索、模拟退火四种方法
    2. 每种方法生成 result.csv + summary.json + result2_*.xlsx
    3. 生成 result2.xlsx（采用最优方法的结果）
    4. 生成 summary.json（汇总对比）
    """
    print("=" * 60)
    print("问题2: 时频冲突消解")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"输出目录: {OUTPUT_DIR}")
    
    # 确保输出目录存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 依次运行4种方法
    method_results = []
    for method_config in METHODS:
        result = run_method(method_config)
        method_results.append(result)
    
    # 生成汇总
    summary = generate_summary(method_results)
    
    # 打印汇总表格
    print_summary_table(summary)
    
    # 生成最终result2.xlsx
    print(f"\n{'='*60}")
    print("生成最终结果文件")
    print(f"{'='*60}")
    generate_result2_xlsx(method_results, summary)
    
    # 保存汇总文件
    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"  ✅ summary.json已保存: {summary_path}")
    
    # 最终统计
    success_count = sum(1 for r in method_results if r["status"] == "success")
    print(f"\n{'='*60}")
    print(f"完成: {success_count}/{len(METHODS)} 个方法成功运行")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
