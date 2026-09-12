"""
问题1 主入口：时频冲突检测
依次运行7种冲突检测方法，对比结果，生成输出文件

输出:
  code/output/01/method1_bruteforce/result.csv + conflict_chart.png
  code/output/01/method2_freqsort/result.csv + conflict_chart.png
  code/output/01/method3_timesort/result.csv + conflict_chart.png
  code/output/01/method4_interval_tree/result.csv + conflict_chart.png
  code/output/01/method5_sweep_line/result.csv + conflict_chart.png
  code/output/01/method6_grid_index/result.csv + conflict_chart.png
  code/output/01/method7_spatial_hash/result.csv + conflict_chart.png
  code/output/01/result1.xlsx  (模板对齐的冲突对结果)
  code/output/01/summary.json  (各方法汇总对比)
"""

import csv
import json
import os
import sys
import time
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')  # 无界面后端，用于服务器环境
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import openpyxl


# ============================================================
# 中文字体设置
# ============================================================

def setup_chinese_font():
    """
    设置 matplotlib 中文字体，避免乱码
    macOS 优先用 PingFang SC，备选 Heiti SC、STHeiti 等
    """
    font_candidates = [
        'PingFang SC', 'Heiti SC', 'STHeiti', 'Songti SC',
        'Arial Unicode MS', 'SimHei', 'Microsoft YaHei'
    ]
    for font_name in font_candidates:
        matches = [f for f in fm.fontManager.ttflist if font_name in f.name]
        if matches:
            plt.rcParams['font.sans-serif'] = [font_name]
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            return font_name
    # 如果都没找到，使用默认字体
    plt.rcParams['axes.unicode_minus'] = False
    return None


# ============================================================
# 路径与模块导入
# ============================================================

# 将 code/01/ 加入 sys.path，以便导入子模块
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from common.data_loader import load_plans, get_data_path, get_output_dir
from method1_bruteforce.bruteforce import run as bruteforce_run
from method2_freqsort.freqsort import run as freqsort_run
from method3_timesort.timesort import run as timesort_run
from method4_interval_tree.interval_tree import run as interval_tree_run
from method5_sweep_line.sweep_line import run as sweep_line_run
from method6_grid_index.grid_index import run as grid_index_run
from method7_spatial_hash.spatial_hash import run as spatial_hash_run


# ============================================================
# 统计函数
# ============================================================

def compute_category_stats(plan_list, conflict_pairs):
    """
    统计各类别之间的冲突数量
    参数:
        plan_list: 装备计划列表
        conflict_pairs: 冲突对列表 [(id1, id2), ...]
    返回:
        嵌套字典 {category_i: {category_j: count}}
        例如 {"A": {"A": 5, "B": 10}, "B": {"B": 3, "C": 7}, ...}
    """
    # 建立 id -> category 映射表
    id_to_cat = {p.id: p.category for p in plan_list}

    stats = defaultdict(lambda: defaultdict(int))
    for id1, id2 in conflict_pairs:
        cat1 = id_to_cat[id1]
        cat2 = id_to_cat[id2]
        # 统计时，较小类别在前（保证 A-A, A-B, A-C, B-B, B-C, C-C 顺序）
        c1, c2 = sorted([cat1, cat2])
        stats[c1][c2] += 1

    return {k: dict(v) for k, v in stats.items()}


# ============================================================
# 可视化图表生成
# ============================================================

def generate_chart(conflict_pairs, plan_list, method_name, output_path):
    """
    生成冲突可视化图表，包含两个子图：
    子图1：各类别冲突数量柱状图（A-A, A-B, A-C, B-B, B-C, C-C）
    子图2：冲突装备的频段-时间分布散点图（按类别着色）
    """
    id_to_plan = {p.id: p for p in plan_list}

    # --- 子图1数据：统计各类别冲突数 ---
    cat_stats = defaultdict(int)
    for id1, id2 in conflict_pairs:
        cat1 = id_to_plan[id1].category
        cat2 = id_to_plan[id2].category
        c1, c2 = sorted([cat1, cat2])
        cat_stats[f"{c1}-{c2}"] += 1

    # 创建画布：1行2列
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # --- 子图1：冲突类别分布柱状图 ---
    ax1 = axes[0]
    if cat_stats:
        labels = sorted(cat_stats.keys())
        values = [cat_stats[k] for k in labels]
        colors = ['#4ECDC4', '#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD']
        bars = ax1.bar(labels, values, color=colors[:len(labels)], edgecolor='#333', linewidth=0.5)
        ax1.set_xlabel('冲突类别', fontsize=11)
        ax1.set_ylabel('冲突对数', fontsize=11)
        ax1.set_title(f'{method_name} - 冲突类别分布', fontsize=12)
        # 在柱子上方显示数值标签
        for bar, val in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                     str(val), ha='center', va='bottom', fontsize=9)
    else:
        ax1.text(0.5, 0.5, '无冲突', ha='center', va='center', fontsize=14)
        ax1.set_title(f'{method_name} - 冲突类别分布', fontsize=12)

    # --- 子图2：冲突装备的频段中点 vs 时间中点散点图 ---
    ax2 = axes[1]
    if conflict_pairs:
        # 收集所有参与冲突的装备ID
        conflict_ids = set()
        for id1, id2 in conflict_pairs:
            conflict_ids.add(id1)
            conflict_ids.add(id2)

        # 按类别绘制散点（A类红色圆点，B类绿色方块，C类蓝色三角）
        cat_markers = {'A': 'o', 'B': 's', 'C': '^'}
        cat_color_map = {'A': '#FF6B6B', 'B': '#4ECDC4', 'C': '#45B7D1'}

        for cat in ['A', 'B', 'C']:
            # 筛选该类别的冲突装备
            ids = [pid for pid in conflict_ids if id_to_plan[pid].category == cat]
            if not ids:
                continue
            # 计算频段中点和时间中点
            freq_mids = [(id_to_plan[pid].freq_start + id_to_plan[pid].freq_end) / 2 for pid in ids]
            time_mids = [(id_to_plan[pid].time_start + id_to_plan[pid].time_end) / 2 for pid in ids]
            ax2.scatter(freq_mids, time_mids, c=cat_color_map[cat],
                        marker=cat_markers[cat], label=f'{cat}类', alpha=0.6, s=30)

        ax2.set_xlabel('频段中点', fontsize=11)
        ax2.set_ylabel('时间中点（首次使用）', fontsize=11)
        ax2.set_title(f'{method_name} - 冲突装备分布', fontsize=12)
        ax2.legend(fontsize=9)
    else:
        ax2.text(0.5, 0.5, '无冲突', ha='center', va='center', fontsize=14)
        ax2.set_title(f'{method_name} - 冲突装备分布', fontsize=12)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  图表已保存: {output_path}")


# ============================================================
# 结果保存函数
# ============================================================

def save_result_csv(method_name, conflict_pairs, elapsed, output_dir):
    """
    保存单个方法的 result.csv 文件
    CSV格式: 序号, 装备1, 装备2
    编码: UTF-8 with BOM（方便Excel直接打开显示中文）
    同时返回类别统计信息，供 summary.json 使用

    参数:
        method_name: 方法名称（如 'bruteforce'）
        conflict_pairs: 冲突对列表 [(id1, id2), ...]
        elapsed: 执行耗时（秒）
        output_dir: 输出目录路径
    返回:
        dict: 包含冲突数、耗时、类别统计等信息
    """
    # 加载计划数据以计算类别统计
    data_path = get_data_path()
    plan_list = load_plans(data_path)
    cat_stats = compute_category_stats(plan_list, conflict_pairs)

    # 保存 CSV 文件（UTF-8 with BOM）
    csv_path = os.path.join(output_dir, "result.csv")
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        # 写表头
        writer.writerow(["序号", "装备1", "装备2"])
        # 写数据行
        for idx, (id1, id2) in enumerate(conflict_pairs, start=1):
            writer.writerow([idx, id1, id2])

    print(f"  结果已保存: {csv_path}")

    # 返回统计信息（供 summary.json 使用）
    return {
        "method": method_name,
        "total_conflicts": len(conflict_pairs),
        "execution_time_seconds": round(elapsed, 4),
        "category_stats": cat_stats,
    }


# ============================================================
# Excel 结果生成
# ============================================================

def generate_result1_xlsx(conflict_pairs, output_path):
    """
    生成 result1.xlsx，与模板列完全对齐
    模板格式: A列=序号, B列=冲突装备1, C列=冲突设备2
    注意: C列标题是"冲突设备2"而非"冲突装备2"（与模板一致）
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"

    # 写表头（与模板完全一致）
    ws.append(["序号", "冲突装备1", "冲突设备2"])

    # 写数据行
    for idx, (id1, id2) in enumerate(conflict_pairs, start=1):
        ws.append([idx, id1, id2])

    wb.save(output_path)
    print(f"  result1.xlsx 已保存: {output_path}")


# ============================================================
# 主函数
# ============================================================

def main():
    """
    主函数：依次运行7种冲突检测方法，汇总对比结果
    流程：
    1. 加载数据
    2. 依次运行暴力枚举、频段排序、时间排序、区间树、扫描线、网格索引、空间哈希七种方法
    3. 每种方法生成 result.csv + conflict_chart.png
    4. 生成 result1.xlsx（与模板对齐）
    5. 生成 summary.json（汇总对比）
    """
    # 设置中文字体
    setup_chinese_font()

    # 加载数据
    data_path = get_data_path()
    output_dir = get_output_dir()
    print(f"数据文件: {data_path}")
    print(f"输出目录: {output_dir}")

    plan_list = load_plans(data_path)
    print(f"共加载 {len(plan_list)} 个装备计划")

    # 定义七种检测方法
    methods = [
        ("bruteforce", "暴力枚举", bruteforce_run, "method1_bruteforce"),
        ("freqsort", "频段排序优化", freqsort_run, "method2_freqsort"),
        ("timesort", "时间排序优化", timesort_run, "method3_timesort"),
        ("interval_tree", "区间树法", interval_tree_run, "method4_interval_tree"),
        ("sweep_line", "扫描线法", sweep_line_run, "method5_sweep_line"),
        ("grid_index", "网格索引法", grid_index_run, "method6_grid_index"),
        ("spatial_hash", "空间哈希法", spatial_hash_run, "method7_spatial_hash"),
    ]

    # 存储各方法的汇总信息
    results_summary = {}
    # 存储各方法的冲突集合（用于一致性检查）
    all_conflict_sets = []
    # 缓存各方法的冲突对列表（避免重复计算）
    all_conflict_pairs = {}

    # --- 依次运行七种方法 ---
    for method_key, method_label, run_func, dir_name in methods:
        print(f"\n{'='*50}")
        print(f"运行方法: {method_label} ({method_key})")
        print(f"{'='*50}")

        # 创建输出子目录
        method_output_dir = os.path.join(output_dir, dir_name)
        os.makedirs(method_output_dir, exist_ok=True)

        # 运行冲突检测并计时
        start_time = time.time()
        conflict_pairs = run_func(plan_list)
        elapsed = time.time() - start_time

        print(f"  冲突对数: {len(conflict_pairs)}")
        print(f"  耗时: {elapsed:.4f} 秒")

        # 保存 result.csv（替换原来的 result.json）
        result_info = save_result_csv(method_key, conflict_pairs, elapsed, method_output_dir)

        # 生成可视化图表
        chart_path = os.path.join(method_output_dir, "conflict_chart.png")
        generate_chart(conflict_pairs, plan_list, method_label, chart_path)

        # 记录汇总信息（包含类别统计）
        results_summary[method_key] = {
            "conflicts": result_info["total_conflicts"],
            "time": result_info["execution_time_seconds"],
            "category_stats": result_info["category_stats"],
        }
        # 缓存冲突集合（用于一致性检查）和冲突对列表（用于生成xlsx）
        all_conflict_sets.append(set(map(tuple, conflict_pairs)))
        all_conflict_pairs[method_key] = conflict_pairs

    # --- 一致性检查：七种方法结果是否完全相同 ---
    all_consistent = all(s == all_conflict_sets[0] for s in all_conflict_sets)

    # --- 生成 result1.xlsx（使用暴力枚举方法的结果，因为它是基准） ---
    print(f"\n{'='*50}")
    print("生成 result1.xlsx")
    print(f"{'='*50}")
    base_pairs = all_conflict_pairs["bruteforce"]
    result1_path = os.path.join(output_dir, "result1.xlsx")
    generate_result1_xlsx(base_pairs, result1_path)

    # --- 生成 summary.json（汇总对比文件，保持JSON格式） ---
    summary = {
        "methods": results_summary,
        "all_consistent": all_consistent,
        "result_file": "result1.xlsx",
    }
    summary_path = os.path.join(output_dir, "summary.json")
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n汇总文件已保存: {summary_path}")

    # --- 打印最终汇总 ---
    print(f"\n{'='*50}")
    print("汇总结果")
    print(f"{'='*50}")
    for method_key, info in results_summary.items():
        print(f"  {method_key}: {info['conflicts']} 对冲突, {info['time']} 秒")
    print(f"  七种方法结果一致: {'是' if all_consistent else '否'}")


if __name__ == '__main__':
    main()
