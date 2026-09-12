"""
方法6：网格索引法冲突检测
将时频平面划分为网格（频段每10单位一格，时间每10单位一格）
将每个装备的时间实例映射到网格，只检查同一网格或相邻网格中的装备对

复杂度：
- 网格数量：G = (freq_range/10) * (time_range/10)
- 每个装备映射到若干网格：O(count * (freq_cells * time_cells))
- 检查时只比对同格和相邻格：大幅减少比较次数
- 理论复杂度：O(n * avg_cells_per_plan * avg_candidates_per_cell)
"""

import sys
import os
from collections import defaultdict

# 将项目根目录加入 sys.path，以便导入 common 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.data_loader import Plan


def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """
    判断两个左闭右开区间 [a_start, a_end) 与 [b_start, b_end) 是否交叠
    交叠条件：a_start < b_end 且 b_start < a_end
    """
    return a_start < b_end and b_start < a_end


def run(plan_list: list[Plan]) -> list[tuple[str, str]]:
    """
    网格索引法冲突检测
    将时频平面划分为网格，将装备映射到网格中，只检查同格或相邻格的装备对

    参数:
        plan_list: 所有装备计划列表
    返回:
        冲突对列表 [(id1, id2), ...]，按编号排序
    """
    # 网格大小参数
    FREQ_CELL = 10   # 频段每10单位一格
    TIME_CELL = 10   # 时间每10单位一格

    # 第一步：建立网格索引
    # grid[(freq_cell_idx, time_cell_idx)] = set of plan_id
    grid = defaultdict(set)

    for plan in plan_list:
        ti_instances = plan.time_instances()
        for t_start, t_end in ti_instances:
            # 计算该时间实例覆盖的频段网格范围
            f_lo = plan.freq_start // FREQ_CELL
            f_hi = (plan.freq_end - 1) // FREQ_CELL  # 因为左闭右开

            # 计算该时间实例覆盖的时间网格范围
            t_lo = t_start // TIME_CELL
            t_hi = (t_end - 1) // TIME_CELL

            # 将装备ID插入所有覆盖的网格
            for fi in range(f_lo, f_hi + 1):
                for ti in range(t_lo, t_hi + 1):
                    grid[(fi, ti)].add(plan.id)

    # 第二步：对每个网格，检查网格内和相邻网格中的装备对
    conflict_set = set()
    id_to_plan = {p.id: p for p in plan_list}

    # 8个相邻方向偏移量（含同格）
    neighbor_offsets = [
        (0, 0),   # 同格
        (1, 0),   # 右
        (0, 1),   # 下
        (1, 1),   # 右下
        (-1, 1),  # 左下
        (-1, 0),  # 左
        (0, -1),  # 上
        (1, -1),  # 右上
        (-1, -1), # 左上
    ]

    for (fi, ti), plan_ids in grid.items():
        # 检查当前网格内的装备对
        plan_id_list = list(plan_ids)
        for a in range(len(plan_id_list)):
            for b in range(a + 1, len(plan_id_list)):
                id1, id2 = plan_id_list[a], plan_id_list[b]
                pair_key = (min(id1, id2), max(id1, id2))
                if pair_key not in conflict_set:
                    if _check_conflict(id_to_plan[id1], id_to_plan[id2]):
                        conflict_set.add(pair_key)

        # 检查与相邻网格的装备对
        # 由于 id1 < id2 的去重条件，需要检查所有方向以避免遗漏
        for di, dj in neighbor_offsets:
            if di == 0 and dj == 0:
                continue  # 同格已处理
            ni, nj = fi + di, ti + dj
            if (ni, nj) not in grid:
                continue
            neighbor_ids = grid[(ni, nj)]
            for id1 in plan_ids:
                for id2 in neighbor_ids:
                    if id1 >= id2:
                        continue
                    pair_key = (id1, id2)
                    if pair_key not in conflict_set:
                        if _check_conflict(id_to_plan[id1], id_to_plan[id2]):
                            conflict_set.add(pair_key)

    return sorted(conflict_set)


def _check_conflict(p1: Plan, p2: Plan) -> bool:
    """
    检查两个装备是否存在时频冲突
    先检查频段交叠，再检查时间实例交叠
    """
    # 检查频段交叠
    if not intervals_overlap(p1.freq_start, p1.freq_end, p2.freq_start, p2.freq_end):
        return False

    # 检查时间实例交叠
    t1_instances = p1.time_instances()
    t2_instances = p2.time_instances()

    for t1_s, t1_e in t1_instances:
        for t2_s, t2_e in t2_instances:
            if intervals_overlap(t1_s, t1_e, t2_s, t2_e):
                return True

    return False
