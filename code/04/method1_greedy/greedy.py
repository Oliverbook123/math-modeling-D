# -*- coding: utf-8 -*-
"""
问题 4 方案 1：贪心 + 优先级 + 间隔调整维度

与问题 2 方案 1 同框架，唯一的扩展：
  C 类计划新增一种动作——调整间隔时长，新间隔与原间隔差异 ≤ 10Δt，
  且为避免装备自身各场次重叠（自干扰），新间隔不小于单次使用时长。
  每个计划仍然"最多只调整一个参数"，所以间隔调整与频段/时间平移互斥。

动作优先级（幅度小者优先）：
  保留 → 频段平移(±1..±10) → 时间平移(±1..±5) → 间隔调整(仅C类) → 撤销

运行方式（项目根目录下）：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl python code/04/method1_greedy/greedy.py
"""

import csv
import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
if CODE01_DIR not in sys.path:
    sys.path.insert(0, CODE01_DIR)

from common.data_loader import Plan, load_plans, get_data_path  # noqa: E402
import openpyxl

# ---------------- 常量 ----------------
MAX_FREQ_SHIFT = 10          # 频段最大平移幅度
MAX_TIME_SHIFT = 5           # 时间最大平移幅度
MAX_INTERVAL_DELTA = 10      # 问题4新增：间隔调整最大差异
FREQ_BAND = (0, 100)         # 系统可用频段范围
EXPECTED_CONFLICTS = 237     # 问题1基准冲突数
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "04", "method1_greedy")
CATEGORY_RANK = {"A": 0, "B": 1, "C": 2}


# ---------------- 基础判定 ----------------

def intervals_overlap(a_start, a_end, b_start, b_end):
    """左闭右开区间 [a,b) 与 [c,d) 交叠判定"""
    return a_start < b_end and b_start < a_end


def plans_conflict(p1, p2):
    """两个计划冲突 ⟺ 频段交叠 且 至少一对时间实例交叠"""
    if not intervals_overlap(p1.freq_start, p1.freq_end, p2.freq_start, p2.freq_end):
        return False
    for ts1, te1 in p1.time_instances():
        for ts2, te2 in p2.time_instances():
            if intervals_overlap(ts1, te1, ts2, te2):
                return True
    return False


def make_plan(plan, freq_shift=0, time_shift=0, interval_delta=0):
    """按计划原参数 + 三种平移量生成新计划（interval_delta 仅 C 类可用）"""
    return Plan(
        id=plan.id, category=plan.category,
        freq_start=plan.freq_start + freq_shift,
        freq_end=plan.freq_end + freq_shift,
        time_start=plan.time_start + time_shift,
        time_end=plan.time_end + time_shift,
        interval=plan.interval + interval_delta,
        count=plan.count,
    )


# ---------------- 动作枚举 ----------------

def get_ordered_actions(plan):
    """
    返回某计划的全部候选动作（不含撤销），按"幅度从小到大"排列。
    决策元组: (action, freq_shift, time_shift, interval_delta)
    """
    actions = [('keep', 0, 0, 0)]

    # 频段平移：幅度 1..10，先正后负同幅度成对展开
    for mag in range(1, MAX_FREQ_SHIFT + 1):
        for df in (mag, -mag):
            if plan.freq_start + df >= FREQ_BAND[0] and plan.freq_end + df <= FREQ_BAND[1]:
                actions.append(('freq', df, 0, 0))

    # 时间平移：幅度 1..5
    for mag in range(1, MAX_TIME_SHIFT + 1):
        for dt in (mag, -mag):
            if plan.time_start + dt >= 0:
                actions.append(('time', 0, dt, 0))

    # 间隔调整（问题4新增，仅 C 类）：
    # 新间隔 ∈ [δ-10, δ+10]，且 ≥1；同时要求新间隔 ≥ 单次时长，
    # 避免调整后的 12 个时间实例互相重叠造成装备自干扰。
    if plan.category == 'C':
        min_interval = max(1, plan.time_width)
        for mag in range(1, MAX_INTERVAL_DELTA + 1):
            for di in (mag, -mag):
                new_interval = plan.interval + di
                if new_interval >= min_interval:
                    actions.append(('interval', 0, 0, di))

    return actions


# ---------------- 贪心主逻辑 ----------------

def greedy_resolve(plans):
    """
    贪心消解：按 (类别优先级, 冲突度降序) 依次处理每个计划，
    尝试它与已保留计划集无冲突的最小幅度动作，全部失败则撤销。
    返回决策列表 [(action, df, dt, di), ...]
    """
    n = len(plans)

    # 先算原始冲突度（同类内冲突多的先处理，先占资源）
    conflict_degree = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if plans_conflict(plans[i], plans[j]):
                conflict_degree[i] += 1
                conflict_degree[j] += 1

    order = sorted(range(n), key=lambda i: (CATEGORY_RANK[plans[i].category],
                                            -conflict_degree[i], plans[i].id))

    decisions = [None] * n
    kept = []  # [(索引, 变换后的计划)]
    for idx in order:
        p = plans[idx]
        placed = False
        for action in get_ordered_actions(p):
            at, df, dt, di = action
            np_ = make_plan(p, df, dt, di)
            # 与所有已保留计划做无冲突检查
            if any(plans_conflict(np_, kp) for _, kp in kept):
                continue
            decisions[idx] = action
            kept.append((idx, np_))
            placed = True
            break
        if not placed:
            decisions[idx] = ('revoke', 0, 0, 0)
    return decisions


# ---------------- 统计与输出 ----------------

def count_conflicts_active(plans, decisions):
    """对消解后的活跃计划重新做全量冲突检测（自检用）"""
    active = [make_plan(plans[i], d[1], d[2], d[3])
              for i, d in enumerate(decisions) if d[0] != 'revoke']
    c = 0
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            if plans_conflict(active[i], active[j]):
                c += 1
    return c


def build_summary(plans, decisions, fc, elapsed):
    """生成表1统计与目标函数值"""
    table1 = {}
    for cat in ("A", "B", "C"):
        table1[cat] = {
            "保留": sum(1 for i, d in enumerate(decisions) if d[0] == 'keep' and plans[i].category == cat),
            "调整": sum(1 for i, d in enumerate(decisions) if d[0] not in ('keep', 'revoke') and plans[i].category == cat),
            "撤销": sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == cat),
        }
    total_rev = sum(v["撤销"] for v in table1.values())
    total_adj = sum(v["调整"] for v in table1.values())
    total_mag = sum(abs(d[1]) + abs(d[2]) + abs(d[3]) for d in decisions if d[0] not in ('keep', 'revoke'))
    interval_adj = sum(1 for d in decisions if d[0] == 'interval')
    summary = {
        "方法": "方案1_贪心+间隔维度",
        "表1": table1,
        "目标函数": {
            "第1层_撤销总数": total_rev,
            "第2层_A撤销": table1["A"]["撤销"],
            "第2层_B撤销": table1["B"]["撤销"],
            "第2层_C撤销": table1["C"]["撤销"],
            "第3层_调整数": total_adj,
            "第4层_总调整幅度": total_mag,
            "其中间隔调整个数": interval_adj,
        },
        "冲突对数_原始": EXPECTED_CONFLICTS,
        "最终冲突数": fc,
        "耗时秒": round(elapsed, 2),
        "自检": {
            "最终冲突数": fc,
            "每计划最多动1参数": True,
            "间隔调整仅限C类": all(plans[i].category == 'C' for i, d in enumerate(decisions) if d[0] == 'interval'),
            "表1总数20_40_90": all(
                table1[c]["保留"] + table1[c]["调整"] + table1[c]["撤销"] == cnt
                for c, cnt in (("A", 20), ("B", 40), ("C", 90))),
        },
    }
    return summary


def write_outputs(plans, decisions, summary):
    """输出 result.csv / summary.json / result4_greedy.xlsx / 图表"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # CSV：逐计划决策明细
    csv_path = os.path.join(OUTPUT_DIR, "result.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['装备编号', '类别', '决策', '频段平移', '时间平移', '间隔调整',
                    '调整后频段区间', '调整后时间区间', '调整后间隔'])
        for i, (at, df, dt, di) in enumerate(decisions):
            p = plans[i]
            if at == 'revoke':
                w.writerow([p.id, p.category, '撤销', '', '', '', '', '', ''])
            else:
                np_ = make_plan(p, df, dt, di)
                label = {'keep': '保留', 'freq': '调频段', 'time': '调时间', 'interval': '调间隔'}[at]
                w.writerow([p.id, p.category, label, df, dt, di,
                            f'[{np_.freq_start},{np_.freq_end})',
                            f'[{np_.time_start},{np_.time_end})', np_.interval])

    # summary.json
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # result4 模板：仅输出需调整/撤销的装备（A编号 B频段 C时间 D间隔 E撤销）
    xlsx_path = os.path.join(OUTPUT_DIR, "result4_greedy.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(['用频装备编号', '调整后频段范围', '调整后时间区间', '调整后间隔时长', '是否撤销用频计划'])
    for i, (at, df, dt, di) in enumerate(decisions):
        p = plans[i]
        if at == 'revoke':
            ws.append([p.id, None, None, None, '是'])
        elif at == 'freq':
            ws.append([p.id, f'[{p.freq_start + df},{p.freq_end + df})', None, None, None])
        elif at == 'time':
            ws.append([p.id, None, f'[{p.time_start + dt},{p.time_end + dt})', None, None])
        elif at == 'interval':
            ws.append([p.id, None, None, p.interval + di, None])
    wb.save(xlsx_path)

    # 图表：各类别 保留/调整/撤销 堆叠条形图
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        cats = ["A", "B", "C"]
        keep = [summary["表1"][c]["保留"] for c in cats]
        adj = [summary["表1"][c]["调整"] for c in cats]
        rev = [summary["表1"][c]["撤销"] for c in cats]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(cats, keep, label='keep', color='#4CAF50')
        ax.bar(cats, adj, bottom=keep, label='adjust', color='#FFC107')
        ax.bar(cats, rev, bottom=[k + a for k, a in zip(keep, adj)], label='revoke', color='#F44336')
        ax.set_title('Greedy + interval dim: keep/adjust/revoke by category')
        ax.set_ylabel('count')
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(OUTPUT_DIR, "result_chart.png"), dpi=120)
        plt.close(fig)
    except Exception as e:  # 图表失败不影响主流程
        print(f"  (图表生成失败: {e})")

    return xlsx_path


def main():
    import time
    print("=" * 60)
    print("问题 4 方案 1：贪心 + 优先级 + 间隔调整维度")
    print("=" * 60)

    plans = load_plans(get_data_path())
    n = len(plans)
    print(f"加载 {n} 个计划")

    # 基准冲突数校验
    cc = sum(1 for i in range(n) for j in range(i + 1, n) if plans_conflict(plans[i], plans[j]))
    print(f"原始冲突: {cc} (基准 {EXPECTED_CONFLICTS})")
    assert cc == EXPECTED_CONFLICTS

    t0 = time.time()
    decisions = greedy_resolve(plans)
    elapsed = time.time() - t0

    fc = count_conflicts_active(plans, decisions)
    assert fc == 0, f"贪心消解后仍有 {fc} 对冲突！"
    print(f"消解完成，最终冲突 0，耗时 {elapsed:.2f}s")

    summary = build_summary(plans, decisions, fc, elapsed)
    xlsx_path = write_outputs(plans, decisions, summary)

    obj = summary["目标函数"]
    print(f"撤销 {obj['第1层_撤销总数']}（A{obj['第2层_A撤销']}/B{obj['第2层_B撤销']}/C{obj['第2层_C撤销']}）"
          f" 调整 {obj['第3层_调整数']} 幅度 {obj['第4层_总调整幅度']}"
          f"（其中调间隔 {obj['其中间隔调整个数']} 个）")
    print(f"输出: {xlsx_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
