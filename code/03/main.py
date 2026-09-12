# -*- coding: utf-8 -*-
"""
问题3 主入口：最大化 C 类装备数
依次运行3种方法，对比结果，生成输出文件

运行方式（项目根目录下）：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl --with pulp python code/03/main.py

输出:
  code/output/03/method1_greedy/result.csv + summary.json
  code/output/03/method2_sweep/result.csv + summary.json
  code/output/03/method3_ilp/result.csv + summary.json
  code/output/03/result3.xlsx   (最终结果，模板对齐)
  code/output/03/summary.json   (各方法汇总对比)
"""

import csv
import json
import os
import sys
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import openpyxl

# ============================================================
# 路径与模块导入
# ============================================================

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from common.data_loader import (
    load_plans, get_data_path, get_project_root, load_problem2_result,
    verify_no_conflict, write_result3_xlsx, fmt_interval,
    plans_conflict, C_FREQ_WIDTH, C_TIME_WIDTH, C_INTERVAL, C_COUNT
)
from method1_greedy.greedy import run as greedy_run
from method2_sweep.sweep import run as sweep_run
from method3_ilp.ilp import run as ilp_run

PROJECT_ROOT = get_project_root()
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "03")


# ============================================================
# 中文字体
# ============================================================

def setup_chinese_font():
    for name in ['SimHei', 'Microsoft YaHei', 'PingFang SC', 'Heiti SC']:
        if any(name in f.name for f in fm.fontManager.ttflist):
            plt.rcParams['font.sans-serif'] = [name]
            plt.rcParams['axes.unicode_minus'] = False
            return name
    plt.rcParams['axes.unicode_minus'] = False
    return None


# ============================================================
# 结果保存
# ============================================================

def save_method_result(method_name, new_plans, active_plans, elapsed, output_dir):
    """保存单个方法的 result.csv 和 summary.json"""
    os.makedirs(output_dir, exist_ok=True)

    # 写 CSV
    csv_path = os.path.join(output_dir, "result.csv")
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(["序号", "频段起点", "频段终点", "时间起点", "时间终点"])
        for i, p in enumerate(new_plans, 1):
            w.writerow([i, p.freq_start, p.freq_end, p.time_start, p.time_end])

    # 频段分布统计
    freq_dist = {}
    for p in new_plans:
        freq_dist[p.freq_start] = freq_dist.get(p.freq_start, 0) + 1

    summary = {
        "方法": method_name,
        "新增C类装备数": len(new_plans),
        "问题2活跃计划数": len(active_plans),
        "总计划数": len(active_plans) + len(new_plans),
        "耗时秒": round(elapsed, 4),
        "频段分布": freq_dist,
    }

    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


# ============================================================
# 可视化
# ============================================================

def generate_chart(method_name, new_plans, active_plans, output_path):
    """生成时频占用可视化图"""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # 已有计划的频段-时间分布
    ax1 = axes[0]
    for p in active_plans:
        for ts, te in p.time_instances():
            mid_t = (ts + te) / 2
            mid_f = (p.freq_start + p.freq_end) / 2
            cat_color = {'A': '#FF6B6B', 'B': '#4ECDC4', 'C': '#45B7D1'}
            ax1.scatter(mid_f, mid_t, c=cat_color.get(p.category, '#999'),
                        s=10, alpha=0.5)
    ax1.set_xlabel('频段中点')
    ax1.set_ylabel('时间中点')
    ax1.set_title(f'{method_name} - 已有计划分布')

    # 新增 C 类装备分布
    ax2 = axes[1]
    for p in active_plans:
        for ts, te in p.time_instances():
            mid_t = (ts + te) / 2
            mid_f = (p.freq_start + p.freq_end) / 2
            ax2.scatter(mid_f, mid_t, c='#CCCCCC', s=10, alpha=0.3)
    for p in new_plans:
        for ts, te in p.time_instances():
            mid_t = (ts + te) / 2
            mid_f = (p.freq_start + p.freq_end) / 2
            ax2.scatter(mid_f, mid_t, c='#FF4444', s=15, alpha=0.7, marker='s')
    ax2.set_xlabel('频段中点')
    ax2.set_ylabel('时间中点')
    ax2.set_title(f'{method_name} - 新增C类装备 (红) vs 已有 (灰)')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  图表已保存: {output_path}")


# ============================================================
# 主函数
# ============================================================

def main():
    setup_chinese_font()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ---- 1. 加载数据 ----
    print("=" * 60)
    print("问题3：最大化 C 类装备数")
    print("=" * 60)

    data_path = get_data_path()
    plans = load_plans(data_path)
    print(f"[1] 加载原始计划: {len(plans)} 个")

    # ---- 2. 加载问题2结果 ----
    result2_path = os.path.join(PROJECT_ROOT, "code", "output", "02", "result2.xlsx")
    active_plans = load_problem2_result(result2_path, plans)
    print(f"[2] 问题2活跃计划: {len(active_plans)} 个")

    # ---- 3. 定义三种方法 ----
    methods = [
        ("greedy", "贪心枚举", greedy_run, "method1_greedy"),
        ("sweep", "空闲格子扫描", sweep_run, "method2_sweep"),
        ("ilp", "整数线性规划ILP", ilp_run, "method3_ilp"),
    ]

    results_summary = {}
    all_results = {}

    # ---- 4. 依次运行 ----
    for method_key, method_label, run_func, dir_name in methods:
        print(f"\n{'='*50}")
        print(f"运行方法: {method_label}")
        print(f"{'='*50}")

        method_output_dir = os.path.join(OUTPUT_DIR, dir_name)
        os.makedirs(method_output_dir, exist_ok=True)

        t0 = time.time()
        new_plans = run_func(active_plans)
        elapsed = time.time() - t0

        print(f"  新增 C 类装备数: {len(new_plans)}")
        print(f"  耗时: {elapsed:.2f} 秒")

        # 验证
        all_plans = active_plans + new_plans
        conflicts = verify_no_conflict(all_plans)
        print(f"  验证冲突对数: {conflicts}")
        assert conflicts == 0, f"验证失败！{conflicts} 对冲突"

        # 保存
        summary = save_method_result(method_label, new_plans, active_plans,
                                      elapsed, method_output_dir)

        # 可视化
        chart_path = os.path.join(method_output_dir, "result_chart.png")
        generate_chart(method_label, new_plans, active_plans, chart_path)

        results_summary[method_key] = summary
        all_results[method_key] = new_plans

    # ---- 5. 取最优结果写入 result3.xlsx ----
    print(f"\n{'='*50}")
    print("生成 result3.xlsx")
    print(f"{'='*50}")

    best_key = max(all_results, key=lambda k: len(all_results[k]))
    best_plans = all_results[best_key]
    best_label = [m[1] for m in methods if m[0] == best_key][0]

    result3_path = os.path.join(OUTPUT_DIR, "result3.xlsx")
    write_result3_xlsx(best_plans, result3_path)
    print(f"  最优方法: {best_label}")
    print(f"  新增装备数: {len(best_plans)}")
    print(f"  result3.xlsx: {result3_path}")

    # ---- 6. 汇总 summary.json ----
    final_summary = {
        "problem2_source": result2_path,
        "methods": results_summary,
        "best_method": best_label,
        "best_count": len(best_plans),
        "result_file": "result3.xlsx",
    }
    summary_path = os.path.join(OUTPUT_DIR, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(final_summary, f, ensure_ascii=False, indent=2)
    print(f"  summary.json: {summary_path}")

    # ---- 7. 打印汇总 ----
    print(f"\n{'='*60}")
    print("汇总结果")
    print(f"{'='*60}")
    for mk, info in results_summary.items():
        print(f"  {info['方法']}: 新增 {info['新增C类装备数']} 个, "
              f"耗时 {info['耗时秒']}s")
    print(f"  最优: {best_label} ({len(best_plans)} 个)")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
