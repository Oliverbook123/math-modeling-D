# -*- coding: utf-8 -*-
"""
问题 4 方案 4：整数规划 ILP 冲突消解（含间隔动作，简化版）

沿用问题 2 的方案 2 框架：
  - A 类全部保留不动（各方案均得 A 撤销 = 0，固定无风险）
  - 只对 B/C 类建 ILP；动作空间：保留 / 频段平移 / 时间平移 / 撤销，
    并且问题 4 为 C 类新增"struct间隔调整"动作（差 ≤ 10，新间隔 ≥ 单次时长）
  - 候选冲突对窗口剪枝 + 预计算不兼容动作对
  - 目标：最小化加权撤销数（B=10^3, C=1）；限时 120s（与问题2同参），
    超时后取当前最好解并贪心修复

运行方式（项目根目录下）：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl --with pulp python code/04/method4_ilp/ilp.py
"""

import csv
import json
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
CODE04_DIR = os.path.join(PROJECT_ROOT, "code", "04")
for p in (CODE01_DIR, CODE04_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from common.data_loader import load_plans, get_data_path  # noqa: E402
from method1_greedy.greedy import (  # noqa: E402
    plans_conflict, make_plan, get_ordered_actions,
    count_conflicts_active, build_summary, EXPECTED_CONFLICTS,
    MAX_FREQ_SHIFT, MAX_TIME_SHIFT,
)
import openpyxl

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "04", "method4_ilp")
TIME_LIMIT = 120  # CBC 求解时限（秒），与问题2方案2一致


def get_ilp_actions(plan):
    """ILP 动作表：保留 + 频段/时间平移 + 间隔调整(C类) + 撤销（撤销固定放最后）"""
    actions = [a for a in get_ordered_actions(plan)]
    actions.append(('revoke', 0, 0, 0))
    return actions


def main():
    import pulp

    print("=" * 60)
    print("问题 4 方案 4：整数规划 ILP（含间隔动作）")
    print("=" * 60)

    plans = load_plans(get_data_path())
    n = len(plans)
    cc = sum(1 for i in range(n) for j in range(i + 1, n) if plans_conflict(plans[i], plans[j]))
    print(f"加载 {n} 个计划，原始冲突 {cc} (基准 {EXPECTED_CONFLICTS})")
    assert cc == EXPECTED_CONFLICTS

    a_indices = [i for i in range(n) if plans[i].category == 'A']
    bc_indices = [i for i in range(n) if plans[i].category in ('B', 'C')]
    print(f"A类 {len(a_indices)} (固定保留)，B/C类 {len(bc_indices)} (ILP优化)")

    decisions = [('keep', 0, 0, 0)] * n
    bc_actions = {i: get_ilp_actions(plans[i]) for i in bc_indices}
    print(f"BC类平均动作数: {sum(len(v) for v in bc_actions.values()) / len(bc_indices):.1f}")

    # 全量 BC 计划对（不做窗口剪枝——剪枝会漏约束，导致"最优"解实际带冲突）
    candidate_pairs = [(bc_indices[ii], bc_indices[jj])
                       for ii in range(len(bc_indices))
                       for jj in range(ii + 1, len(bc_indices))]

    # BC 与固定 A 的冲突
    bc_a_conflicts = {}
    for i in bc_indices:
        bad_a = [j for j in a_indices if plans_conflict(plans[i], plans[j])]
        if bad_a:
            bc_a_conflicts[i] = bad_a
    print(f"BC间候选对: {len(candidate_pairs)}, BC与A冲突: {len(bc_a_conflicts)}")

    # 动作兼容矩阵预计算
    t0 = time.time()
    print("预计算不兼容动作对...")
    incompatible = {}
    total_bad = 0
    for (i, j) in candidate_pairs:
        bad = []
        for ai, act_i in enumerate(bc_actions[i]):
            if act_i[0] == 'revoke':
                continue
            pi_s = make_plan(plans[i], *act_i[1:])
            for aj, act_j in enumerate(bc_actions[j]):
                if act_j[0] == 'revoke':
                    continue
                if plans_conflict(pi_s, make_plan(plans[j], *act_j[1:])):
                    bad.append((ai, aj))
        total_bad += len(bad)
        if bad:
            incompatible[(i, j)] = bad
    print(f"不兼容动作对总数: {total_bad}（{time.time() - t0:.1f}s）")

    bc_a_incompatible = {}
    for i, conflicting_a in bc_a_conflicts.items():
        bad_actions = []
        for ai, act in enumerate(bc_actions[i]):
            if act[0] == 'revoke':
                continue
            pi_s = make_plan(plans[i], *act[1:])
            if any(plans_conflict(pi_s, plans[j]) for j in conflicting_a):
                bad_actions.append(ai)
        if bad_actions:
            bc_a_incompatible[i] = bad_actions

    # 建 ILP
    print("建 ILP 模型...")
    prob = pulp.LpProblem("ConflictResolutionP4", pulp.LpMinimize)
    y = {}
    for i in bc_indices:
        for a_idx in range(len(bc_actions[i])):
            y[i, a_idx] = pulp.LpVariable(f"y_{i}_{a_idx}", cat=pulp.LpBinary)

    for i in bc_indices:
        prob += pulp.lpSum(y[i, a] for a in range(len(bc_actions[i]))) == 1
    for (i, j), bad in incompatible.items():
        for ai, aj in bad:
            prob += y[i, ai] + y[j, aj] <= 1
    for i, bad_actions in bc_a_incompatible.items():
        for ai in bad_actions:
            prob += y[i, ai] == 0

    obj = 0
    for i in bc_indices:
        weight = {'B': 10 ** 3, 'C': 1}[plans[i].category]
        obj += weight * y[i, len(bc_actions[i]) - 1]  # 撤销位
    prob += obj

    print(f"求解中（限时 {TIME_LIMIT}s）...")
    status = prob.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=TIME_LIMIT))
    status_str = pulp.LpStatus[status]
    print(f"求解状态: {status_str}, 加权目标值: {pulp.value(prob.objective)}")

    for i in bc_indices:
        for a_idx in range(len(bc_actions[i])):
            v = pulp.value(y[i, a_idx])
            if v and v > 0.5:
                decisions[i] = bc_actions[i][a_idx]
                break

    # 贪心修复残留冲突（撤销优先级低者）
    fc = count_conflicts_active(plans, decisions)
    if fc > 0:
        print(f"ILP 解残留 {fc} 对冲突，贪心修复...")
        changed = True
        while changed:
            changed = False
            active = [(i, make_plan(plans[i], *decisions[i][1:]))
                      for i in range(n) if decisions[i][0] != 'revoke']
            for a in range(len(active)):
                for b in range(a + 1, len(active)):
                    if plans_conflict(active[a][1], active[b][1]):
                        ra = active[a][1].category
                        rb = active[b][1].category
                        victim = active[a][0] if ra >= rb else active[b][0]
                        decisions[victim] = ('revoke', 0, 0, 0)
                        changed = True
                        break
                if changed:
                    break
        fc = count_conflicts_active(plans, decisions)
        print(f"修复后冲突: {fc}")

    elapsed = time.time() - t0
    assert fc == 0, f"仍有 {fc} 对冲突！"

    summary = build_summary(plans, decisions, fc, elapsed)
    summary["方法"] = "方案4_整数规划ILP+间隔动作"
    summary["求解状态"] = status_str
    summary["求解时限秒"] = TIME_LIMIT

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

    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    xlsx_path = os.path.join(OUTPUT_DIR, "result4_ilp.xlsx")
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

    obj = summary["目标函数"]
    print(f"\nFINAL 撤销 {obj['第1层_撤销总数']}（A{obj['第2层_A撤销']}/B{obj['第2层_B撤销']}/C{obj['第2层_C撤销']}）"
          f" 调整 {obj['第3层_调整数']} 幅度 {obj['第4层_总调整幅度']}"
          f"（调间隔 {obj['其中间隔调整个数']} 个），耗时 {elapsed:.1f}s")

    print(f"\n输出: {xlsx_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
