# -*- coding: utf-8 -*-
"""
问题 4 方案 2：模拟退火冲突消解（扩展间隔动作）

与问题 2 方案 4（SA，问题2最优：撤销50）完全同框架，仅两处扩展：
  1. 动作池：C 类计划新增 'interval' 动作（新间隔与原间隔差 ≤ 10，且 ≥ 单次时长）
  2. 能量元组的总幅度项计入 |间隔调整量|

能量 = 元组 (冲突对数, A撤销, B撤销, C撤销, 调整数, 总幅度)，字典序比较。
初始解 = 方案1的贪心（含间隔维度）。≥5 固定种子取优，收尾贪心消毒保证 0 冲突。

运行方式（项目根目录下）：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl python code/04/method2_sa/sa.py
"""

import csv
import json
import os
import sys
import random
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
CODE04_DIR = os.path.join(PROJECT_ROOT, "code", "04")
for p in (CODE01_DIR, CODE04_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from common.data_loader import Plan, load_plans, get_data_path  # noqa: E402
from method1_greedy.greedy import (  # noqa: E402  复用方案1的判定/贪心/输出工具
    plans_conflict, make_plan, get_ordered_actions, greedy_resolve,
    count_conflicts_active, build_summary, MAX_FREQ_SHIFT, MAX_TIME_SHIFT,
    MAX_INTERVAL_DELTA, FREQ_BAND, EXPECTED_CONFLICTS, CATEGORY_RANK,
)
import openpyxl

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "04", "method2_sa")


# ---------------- 能量函数 ----------------

def energy_tuple(plans, decisions):
    """能量元组: (冲突对数, A撤销, B撤销, C撤销, 调整数, 总幅度)；幅度含间隔调整量"""
    active = []
    for i, (at, df, dt, di) in enumerate(decisions):
        if at == 'revoke':
            continue
        active.append(make_plan(plans[i], df, dt, di))
    conflicts = 0
    for a in range(len(active)):
        for b in range(a + 1, len(active)):
            if plans_conflict(active[a], active[b]):
                conflicts += 1
    a_rev = sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == 'A')
    b_rev = sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == 'B')
    c_rev = sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == 'C')
    adj = sum(1 for d in decisions if d[0] not in ('keep', 'revoke'))
    mag = sum(abs(d[1]) + abs(d[2]) + abs(d[3]) for d in decisions if d[0] not in ('keep', 'revoke'))
    return (conflicts, a_rev, b_rev, c_rev, adj, mag)


def energy_scalar(e):
    """元组 → 标量，用于 Metropolis 接受概率（权重与问题2方案4一致）"""
    return e[0] * 10**8 + e[1] * 10**6 + e[2] * 10**3 + e[3] * 1 + e[4] * 10 + e[5] * 1


# ---------------- 动作采样 ----------------

def random_valid_action(plan, rng):
    """
    随机选一个合法动作。
    动作池 = keep + 频段平移 + 时间平移 + 间隔调整(C类) + 撤销，均匀抽样。
    """
    actions = list(get_ordered_actions(plan))
    actions.append(('revoke', 0, 0, 0))
    return rng.choice(actions)


# ---------------- 贪心消毒 ----------------

def repair_conflicts(plans, decisions):
    """逐个撤销冲突对中优先级低（类别等级数值大）的计划，直至 0 冲突"""
    changed = True
    while changed:
        changed = False
        active = [(i, make_plan(plans[i], *decisions[i][1:]))
                  for i in range(len(plans)) if decisions[i][0] != 'revoke']
        for a in range(len(active)):
            for b in range(a + 1, len(active)):
                ia, pa = active[a]
                ib, pb = active[b]
                if plans_conflict(pa, pb):
                    ra = CATEGORY_RANK[plans[ia].category]
                    rb = CATEGORY_RANK[plans[ib].category]
                    victim = ia if ra >= rb else ib
                    decisions[victim] = ('revoke', 0, 0, 0)
                    changed = True
                    break
            if changed:
                break
    return decisions


# ---------------- 模拟退火主流程 ----------------

def simulated_annealing(plans, seed, use_greedy_init=True, T0=50.0, alpha=0.97,
                        samples_per_temp=300, min_T=0.01, max_iter=100000):
    import math
    rng = random.Random(seed)
    n = len(plans)

    if use_greedy_init:
        decisions = greedy_resolve(plans)   # 方案1贪心解作初温起点
    else:
        decisions = [random_valid_action(p, rng) for p in plans]
        decisions = repair_conflicts(plans, decisions)

    best_dec = list(decisions)
    best_e = energy_tuple(plans, decisions)
    best_s = energy_scalar(best_e)
    cur_dec = list(decisions)
    cur_e = best_e
    cur_s = best_s

    T = T0
    iters = 0
    while T > min_T and iters < max_iter:
        for _ in range(samples_per_temp):
            iters += 1
            # 随机扰动 1~3 个计划
            indices = rng.sample(range(n), rng.randint(1, min(3, n)))
            old_actions = [cur_dec[i] for i in indices]
            for i in indices:
                cur_dec[i] = random_valid_action(plans[i], rng)
            new_e = energy_tuple(plans, cur_dec)
            if new_e[0] > 0:
                cur_dec = repair_conflicts(plans, cur_dec)
                new_e = energy_tuple(plans, cur_dec)
            new_s = energy_scalar(new_e)
            delta = new_s - cur_s
            if delta <= 0 or rng.random() < math.exp(-delta / T):
                cur_e, cur_s = new_e, new_s
                if new_e < best_e:
                    best_e, best_s = new_e, new_s
                    best_dec = list(cur_dec)
            else:
                for pos, i in enumerate(indices):
                    cur_dec[i] = old_actions[pos]
        T *= alpha

    best_dec = repair_conflicts(plans, best_dec)
    return best_dec, energy_tuple(plans, best_dec), iters


# ---------------- 输出 ----------------

def write_outputs(plans, decisions, summary, all_results):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

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

    summary["各种子结果"] = all_results
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    xlsx_path = os.path.join(OUTPUT_DIR, "result4_sa.xlsx")
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

    # 图表：各种子撤销数对比
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        labels = [str(r["seed"]) + ("*" if r.get("random_init") else "") for r in all_results]
        revs = [r["energy"][1] + r["energy"][2] + r["energy"][3] for r in all_results]
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(labels, revs, color='#4C78A8')
        ax.set_title('SA per-seed revoke count (problem 4)')
        ax.set_xlabel('seed (*=random init)')
        ax.set_ylabel('revokes')
        fig.tight_layout()
        fig.savefig(os.path.join(OUTPUT_DIR, "result_chart.png"), dpi=120)
        plt.close(fig)
    except Exception as e:
        print(f"  (图表生成失败: {e})")

    return xlsx_path


def main():
    print("=" * 60)
    print("问题 4 方案 2：模拟退火冲突消解（扩展间隔动作）")
    print("=" * 60)

    plans = load_plans(get_data_path())
    n = len(plans)
    cc = sum(1 for i in range(n) for j in range(i + 1, n) if plans_conflict(plans[i], plans[j]))
    print(f"加载 {n} 个计划，原始冲突 {cc} (基准 {EXPECTED_CONFLICTS})")
    assert cc == EXPECTED_CONFLICTS

    t0 = time.time()
    seeds = [42, 123, 456, 789, 2024]
    all_results = []
    best_dec, best_e = None, (999,) * 6
    for seed in seeds:
        dec, e, iters = simulated_annealing(plans, seed, use_greedy_init=True)
        fc = count_conflicts_active(plans, dec)
        print(f"  种子 {seed}: 能量 {e}, 冲突 {fc}, 迭代 {iters}")
        all_results.append({"seed": seed, "energy": list(e), "conflicts": fc, "iterations": iters})
        if e < best_e:
            best_e, best_dec = e, list(dec)

    # 随机初始解对照
    dec_r, e_r, iters_r = simulated_annealing(plans, 42, use_greedy_init=False)
    fc_r = count_conflicts_active(plans, dec_r)
    print(f"  随机初始: 能量 {e_r}, 冲突 {fc_r}, 迭代 {iters_r}")
    all_results.append({"seed": 42, "energy": list(e_r), "conflicts": fc_r,
                        "iterations": iters_r, "random_init": True})
    if e_r < best_e:
        best_e, best_dec = e_r, list(dec_r)
    elapsed = time.time() - t0

    # 最终消毒 + 独立自检
    best_dec = repair_conflicts(plans, best_dec)
    final_fc = count_conflicts_active(plans, best_dec)
    assert final_fc == 0, f"消毒后仍有 {final_fc} 对冲突！"

    summary = build_summary(plans, best_dec, final_fc, elapsed)
    summary["方法"] = "方案2_模拟退火+间隔维度"
    xlsx_path = write_outputs(plans, best_dec, summary, all_results)

    obj = summary["目标函数"]
    print(f"\n最优解: 撤销 {obj['第1层_撤销总数']}（A{obj['第2层_A撤销']}/B{obj['第2层_B撤销']}/C{obj['第2层_C撤销']}）"
          f" 调整 {obj['第3层_调整数']} 幅度 {obj['第4层_总调整幅度']}"
          f"（其中调间隔 {obj['其中间隔调整个数']} 个），耗时 {elapsed:.1f}s")
    print(f"输出: {xlsx_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
