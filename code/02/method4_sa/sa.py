# -*- coding: utf-8 -*-
"""
问题 2 方案 4：模拟退火冲突消解

运行方式（项目根目录下）：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl python code/02/method4_sa/main.py

算法概述：
  能量 = 元组 (冲突对数, A撤销, B撤销, C撤销, 调整数, 总幅度)，元组字典序比较。
  Metropolis 接受概率用标量化近似：exp(-ΔE_scalar/T)。
  扰动：随机挑1~3个计划换合法动作。
  初始解：内置贪心（与方案1同逻辑）。
  ≥5个固定种子各跑一遍，收尾贪心消毒保证最终0冲突。
"""

import csv
import json
import os
import sys
import random
import math
from itertools import combinations

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
if CODE01_DIR not in sys.path:
    sys.path.insert(0, CODE01_DIR)

from common.data_loader import Plan, load_plans, get_data_path  # noqa: E402
import openpyxl

MAX_FREQ_SHIFT = 10
MAX_TIME_SHIFT = 5
FREQ_BAND = (0, 100)
EXPECTED_CONFLICTS = 237
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "02", "method4_sa")
CATEGORY_RANK = {"A": 0, "B": 1, "C": 2}


def intervals_overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def plans_conflict(p1, p2):
    if not intervals_overlap(p1.freq_start, p1.freq_end, p2.freq_start, p2.freq_end):
        return False
    for ts1, te1 in p1.time_instances():
        for ts2, te2 in p2.time_instances():
            if intervals_overlap(ts1, te1, ts2, te2):
                return True
    return False


def make_shifted_plan(plan, freq_shift=0, time_shift=0):
    return Plan(
        id=plan.id, category=plan.category,
        freq_start=plan.freq_start + freq_shift,
        freq_end=plan.freq_end + freq_shift,
        time_start=plan.time_start + time_shift,
        time_end=plan.time_end + time_shift,
        interval=plan.interval, count=plan.count,
    )


def get_actions_for_plan(plan):
    actions = [('keep', 0, 0)]
    for df in range(-MAX_FREQ_SHIFT, MAX_FREQ_SHIFT + 1):
        if df == 0: continue
        if plan.freq_start + df >= FREQ_BAND[0] and plan.freq_end + df <= FREQ_BAND[1]:
            actions.append(('freq', df, 0))
    for dt in range(-MAX_TIME_SHIFT, MAX_TIME_SHIFT + 1):
        if dt == 0: continue
        if plan.time_start + dt >= 0:
            actions.append(('time', 0, dt))
    actions.append(('revoke', 0, 0))
    return actions


def energy_tuple(plans, decisions):
    """计算能量元组: (冲突对数, A撤销, B撤销, C撤销, 调整数, 总幅度)"""
    conflicts = 0
    active_plans = []
    for i, (at, df, dt) in enumerate(decisions):
        if at == 'revoke': continue
        active_plans.append((i, make_shifted_plan(plans[i], df, dt)))
    for a in range(len(active_plans)):
        for b in range(a + 1, len(active_plans)):
            if plans_conflict(active_plans[a][1], active_plans[b][1]):
                conflicts += 1
    a_rev = sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == 'A')
    b_rev = sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == 'B')
    c_rev = sum(1 for i, d in enumerate(decisions) if d[0] == 'revoke' and plans[i].category == 'C')
    adj = sum(1 for d in decisions if d[0] not in ('keep', 'revoke'))
    mag = sum(abs(d[1]) + abs(d[2]) for d in decisions if d[0] not in ('keep', 'revoke'))
    return (conflicts, a_rev, b_rev, c_rev, adj, mag)


def energy_scalar(e):
    """元组 → 标量，用于 Metropolis 接受概率计算"""
    return e[0] * 10**8 + e[1] * 10**6 + e[2] * 10**3 + e[3] * 1 + e[4] * 10 + e[5] * 1


def greedy_construct(plans):
    n = len(plans)
    conflict_degree = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            if plans_conflict(plans[i], plans[j]):
                conflict_degree[i] += 1
                conflict_degree[j] += 1
    order = sorted(range(n), key=lambda i: (CATEGORY_RANK[plans[i].category],
                                            -conflict_degree[i], plans[i].id))
    decisions = [None] * n
    kept = []
    for idx in order:
        p = plans[idx]
        actions = get_actions_for_plan(p)
        found = False
        for at, df, dt in actions:
            if at == 'revoke': continue
            np = make_shifted_plan(p, df, dt)
            conflict = False
            for k, kp in kept:
                if plans_conflict(np, kp):
                    conflict = True
                    break
            if not conflict:
                decisions[idx] = (at, df, dt)
                kept.append((idx, np))
                found = True
                break
        if not found:
            decisions[idx] = ('revoke', 0, 0)
    return decisions


def random_valid_action(plan, rng):
    """随机选一个合法动作"""
    actions = get_actions_for_plan(plan)
    return rng.choice(actions)


def repair_conflicts(plans, decisions):
    """贪心消毒：逐个处理仍有冲突的活跃计划"""
    n = len(plans)
    changed = True
    while changed:
        changed = False
        # 找出冲突的活跃计划对
        active = [(i, make_shifted_plan(plans[i], decisions[i][1], decisions[i][2]))
                  for i in range(n) if decisions[i][0] != 'revoke']
        for a in range(len(active)):
            for b in range(a + 1, len(active)):
                ia, pa = active[a]
                ib, pb = active[b]
                if plans_conflict(pa, pb):
                    # 撤销优先级低的那个
                    ra = CATEGORY_RANK[plans[ia].category]
                    rb = CATEGORY_RANK[plans[ib].category]
                    victim = ia if ra >= rb else ib
                    decisions[victim] = ('revoke', 0, 0)
                    changed = True
                    break
            if changed: break
    return decisions


def simulated_annealing(plans, seed, use_greedy_init=True, T0=50.0, alpha=0.97,
                        samples_per_temp=300, min_T=0.01, max_iter=100000):
    rng = random.Random(seed)
    n = len(plans)

    # 初始解
    if use_greedy_init:
        decisions = greedy_construct(plans)
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
    no_improve = 0

    while T > min_T and iters < max_iter:
        for _ in range(samples_per_temp):
            iters += 1
            # 随机扰动1~3个计划
            num_change = rng.randint(1, min(3, n))
            indices = rng.sample(range(n), num_change)
            old_actions = [cur_dec[i] for i in indices]
            for i in indices:
                cur_dec[i] = random_valid_action(plans[i], rng)
            # 如果有冲突，尝试修复
            new_e = energy_tuple(plans, cur_dec)
            if new_e[0] > 0:
                cur_dec = repair_conflicts(plans, cur_dec)
                new_e = energy_tuple(plans, cur_dec)
            new_s = energy_scalar(new_e)
            # Metropolis
            delta = new_s - cur_s
            if delta <= 0 or rng.random() < math.exp(-delta / T):
                cur_e = new_e
                cur_s = new_s
                # 更新最优
                if new_e < best_e:
                    best_e = new_e
                    best_s = new_s
                    best_dec = list(cur_dec)
                    no_improve = 0
                else:
                    no_improve += 1
            else:
                # 拒绝：恢复
                for idx, i in enumerate(indices):
                    cur_dec[i] = old_actions[idx]
                no_improve += 1
        T *= alpha

    # 最终收尾消毒
    best_dec = repair_conflicts(plans, best_dec)
    final_e = energy_tuple(plans, best_dec)
    return best_dec, final_e, iters


def count_conflicts_active(plans, decisions):
    active = []
    for i, (at, df, dt) in enumerate(decisions):
        if at == 'revoke': continue
        active.append(make_shifted_plan(plans[i], df, dt))
    c = 0
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            if plans_conflict(active[i], active[j]):
                c += 1
    return c


def main():
    print("=" * 60)
    print("问题 2 方案 4：模拟退火冲突消解")
    print("=" * 60)

    plans = load_plans(get_data_path())
    n = len(plans)
    print(f"加载 {n} 个计划")

    # 验证冲突数
    cc = 0
    for i in range(n):
        for j in range(i + 1, n):
            if plans_conflict(plans[i], plans[j]):
                cc += 1
    print(f"原始冲突: {cc} (基准 {EXPECTED_CONFLICTS})")
    assert cc == EXPECTED_CONFLICTS

    # 5个种子
    seeds = [42, 123, 456, 789, 2024]
    all_results = []
    best_overall_dec = None
    best_overall_e = (999, 999, 999, 999, 999, 999)

    for seed in seeds:
        print(f"\n--- 种子 {seed} ---")
        dec, e, iters = simulated_annealing(plans, seed, use_greedy_init=True)
        fc = count_conflicts_active(plans, dec)
        print(f"  能量: {e}, 冲突: {fc}, 迭代: {iters}")
        all_results.append({"seed": seed, "energy": list(e), "conflicts": fc, "iterations": iters})
        if e < best_overall_e:
            best_overall_e = e
            best_overall_dec = list(dec)

    # 随机初始解对照
    print(f"\n--- 随机初始解 (seed=42) ---")
    dec_r, e_r, iters_r = simulated_annealing(plans, 42, use_greedy_init=False)
    fc_r = count_conflicts_active(plans, dec_r)
    print(f"  能量: {e_r}, 冲突: {fc_r}, 迭代: {iters_r}")
    all_results.append({"seed": 42, "energy": list(e_r), "conflicts": fc_r, "iterations": iters_r, "random_init": True})

    # 最终消毒
    best_dec = repair_conflicts(plans, best_overall_dec)
    final_e = energy_tuple(plans, best_dec)
    final_fc = count_conflicts_active(plans, best_dec)
    assert final_fc == 0, f"消毒后仍有 {final_fc} 对冲突！"

    # 统计
    a_keep = sum(1 for i, d in enumerate(best_dec) if d[0] == 'keep' and plans[i].category == 'A')
    a_adj = sum(1 for i, d in enumerate(best_dec) if d[0] not in ('keep','revoke') and plans[i].category == 'A')
    a_rev = sum(1 for i, d in enumerate(best_dec) if d[0] == 'revoke' and plans[i].category == 'A')
    b_keep = sum(1 for i, d in enumerate(best_dec) if d[0] == 'keep' and plans[i].category == 'B')
    b_adj = sum(1 for i, d in enumerate(best_dec) if d[0] not in ('keep','revoke') and plans[i].category == 'B')
    b_rev = sum(1 for i, d in enumerate(best_dec) if d[0] == 'revoke' and plans[i].category == 'B')
    c_keep = sum(1 for i, d in enumerate(best_dec) if d[0] == 'keep' and plans[i].category == 'C')
    c_adj = sum(1 for i, d in enumerate(best_dec) if d[0] not in ('keep','revoke') and plans[i].category == 'C')
    c_rev = sum(1 for i, d in enumerate(best_dec) if d[0] == 'revoke' and plans[i].category == 'C')
    total_mag = sum(abs(d[1]) + abs(d[2]) for d in best_dec if d[0] not in ('keep','revoke'))

    print(f"\n表1: A({a_keep}/{a_adj}/{a_rev}) B({b_keep}/{b_adj}/{b_rev}) C({c_keep}/{c_adj}/{c_rev})")
    print(f"撤销: {a_rev+b_rev+c_rev}, 调整: {a_adj+b_adj+c_adj}, 幅度: {total_mag}")

    # 输出
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    csv_path = os.path.join(OUTPUT_DIR, "result.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['装备编号', '类别', '决策', '频段平移', '时间平移', '调整后频段区间', '调整后时间区间'])
        for i, (at, df, dt) in enumerate(best_dec):
            p = plans[i]
            if at == 'revoke':
                w.writerow([p.id, p.category, '撤销', '', '', '', ''])
            elif at == 'keep':
                w.writerow([p.id, p.category, '保留', 0, 0, f'[{p.freq_start},{p.freq_end})', f'[{p.time_start},{p.time_end})'])
            else:
                np = make_shifted_plan(p, df, dt)
                w.writerow([p.id, p.category, '调频段' if at == 'freq' else '调时间', df, dt,
                            f'[{np.freq_start},{np.freq_end})', f'[{np.time_start},{np.time_end})'])

    summary = {
        "方法": "方案4_模拟退火",
        "表1": {
            "A": {"保留": a_keep, "调整": a_adj, "撤销": a_rev},
            "B": {"保留": b_keep, "调整": b_adj, "撤销": b_rev},
            "C": {"保留": c_keep, "调整": c_adj, "撤销": c_rev}
        },
        "目标函数": {
            "第1层_撤销总数": a_rev+b_rev+c_rev,
            "第2层_A撤销": a_rev, "第2层_B撤销": b_rev, "第2层_C撤销": c_rev,
            "第3层_调整数": a_adj+b_adj+c_adj,
            "第4层_总调整幅度": total_mag
        },
        "各种子结果": all_results,
        "最优种子能量": list(final_e),
        "冲突对数_原始": cc,
        "最终冲突数": final_fc,
        "自检": {
            "最终冲突数": final_fc,
            "每计划最多动1参数": True,
            "表1总数20_40_90": (a_keep+a_adj+a_rev == 20 and b_keep+b_adj+b_rev == 40 and c_keep+c_adj+c_rev == 90),
        }
    }
    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    xlsx_path = os.path.join(OUTPUT_DIR, "result2_sa.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(['用频装备编号', '调整后频段区间', '调整后时间区间', '是否撤销用频计划'])
    for i, (at, df, dt) in enumerate(best_dec):
        p = plans[i]
        if at == 'revoke':
            ws.append([p.id, None, None, '是'])
        elif at != 'keep':
            np = make_shifted_plan(p, df, dt)
            if at == 'freq':
                ws.append([p.id, f'[{np.freq_start},{np.freq_end})', None, None])
            else:
                ws.append([p.id, None, f'[{np.time_start},{np.time_end})', None])
    wb.save(xlsx_path)

    print(f"\n输出: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
