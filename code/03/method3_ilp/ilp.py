# -*- coding: utf-8 -*-
"""
问题3 方法3：整数线性规划（ILP）
建模为最大独立集问题：每个候选位置是一个 0-1 变量，
冲突的位置不能同时选中，最大化选中数量。
"""

from typing import List, Set, Tuple
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.data_loader import (
    Plan, build_occupied_set, get_max_time, can_place_c, make_c_plan,
    plans_conflict, FREQ_BAND, C_FREQ_WIDTH, C_TIME_WIDTH, C_INTERVAL, C_COUNT
)


def run(active_plans: List[Plan]) -> List[Plan]:
    """
    ILP 求解主函数。
    1. 枚举所有可行候选位置（不与问题2冲突）
    2. 预计算候选位置之间的冲突关系
    3. 用 PuLP 建模求解最大独立集
    """
    try:
        import pulp
    except ImportError:
        print("[ILP] 需要 PuLP，回退到贪心法")
        from method1_greedy.greedy import run as greedy_run
        return greedy_run(active_plans)

    occupied = build_occupied_set(active_plans)
    max_time = get_max_time(active_plans)
    time_end = max_time - (C_COUNT - 1) * C_INTERVAL - C_TIME_WIDTH + 1
    if time_end <= 0:
        time_end = 1

    # ---- 步骤1：枚举所有可行候选位置 ----
    candidates = []  # [(f0, t0), ...]
    for f0 in range(FREQ_BAND[1] - C_FREQ_WIDTH + 1):
        for t0 in range(time_end):
            if can_place_c(f0, t0, occupied):
                candidates.append((f0, t0))

    n_cand = len(candidates)
    print(f"[ILP] 可行候选位置数: {n_cand}")

    if n_cand == 0:
        return []

    # 为每个候选位置创建 Plan 对象
    cand_plans = [make_c_plan(f0, t0) for f0, t0 in candidates]

    # ---- 步骤2：预计算候选位置之间的冲突关系 ----
    print(f"[ILP] 预计算冲突关系...")
    conflicts = []  # [(i, j), ...]
    for i in range(n_cand):
        for j in range(i + 1, n_cand):
            if plans_conflict(cand_plans[i], cand_plans[j]):
                conflicts.append((i, j))

    print(f"[ILP] 候选冲突对数: {len(conflicts)}")

    # ---- 步骤3：ILP 建模 ----
    print(f"[ILP] 建模求解...")
    prob = pulp.LpProblem("MaxCPacking", pulp.LpMaximize)

    # 决策变量：x[i] = 1 表示选中第 i 个候选位置
    x = [pulp.LpVariable(f"x_{i}", cat=pulp.LpBinary) for i in range(n_cand)]

    # 目标函数：最大化选中数量
    prob += pulp.lpSum(x)

    # 约束：冲突的两个位置不能同时选中
    for i, j in conflicts:
        prob += x[i] + x[j] <= 1

    # 求解
    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=300)
    status = prob.solve(solver)
    status_str = pulp.LpStatus[status]
    print(f"[ILP] 求解状态: {status_str}")

    # ---- 步骤4：提取结果 ----
    selected = []
    for i in range(n_cand):
        if pulp.value(x[i]) and pulp.value(x[i]) > 0.5:
            f0, t0 = candidates[i]
            p = make_c_plan(f0, t0)
            selected.append(p)

    print(f"[ILP] 最优解: 新增 {len(selected)} 个 C 类装备")
    return selected
