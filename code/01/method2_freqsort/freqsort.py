"""
方法2：频段排序优化冲突检测
先按频段起点排序，利用频段区间快速排除不交叠的对
当频段起点之差 >= 当前装备频段宽度时，后续所有装备都不可能交叠
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.data_loader import Plan


def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """
    判断两个左闭右开区间 [a_start, a_end) 与 [b_start, b_end) 是否交叠
    """
    return a_start < b_end and b_start < a_end


def run(plan_list: list[Plan]) -> list[tuple[str, str]]:
    """
    频段排序优化的冲突检测
    步骤：
    1. 按频段起点升序排序
    2. 对每个装备 i，只检查频段可能交叠的后续装备 j
    3. 当 sorted[j].freq_start >= sorted[i].freq_end 时，j 及之后的装备频段都不与 i 交叠
    参数:
        plan_list: 所有装备计划列表
    返回:
        冲突对列表 [(id1, id2), ...]，按原始编号排序
    """
    # 按频段起点升序排序，记录原始索引用于恢复编号
    sorted_plans = sorted(enumerate(plan_list), key=lambda x: x[1].freq_start)

    conflict_set = set()  # 用集合去重，存储 (id1, id2) 元组
    n = len(sorted_plans)

    for i in range(n):
        idx_i, pi = sorted_plans[i]
        ti_instances = pi.time_instances()

        for j in range(i + 1, n):
            idx_j, pj = sorted_plans[j]

            # 优化：如果 pj 的频段起点 >= pi 的频段终点，则 pi 与 pj 及后续所有装备频段不交叠
            # 因为已按 freq_start 排序，后续的 freq_start 更大
            if pj.freq_start >= pi.freq_end:
                break  # 跳出内层循环，不再检查 j 之后的装备

            # 频段可能交叠，进一步确认
            if not intervals_overlap(pi.freq_start, pi.freq_end,
                                     pj.freq_start, pj.freq_end):
                continue

            # 检查时间实例是否交叠
            tj_instances = pj.time_instances()
            found_conflict = False

            for ti_s, ti_e in ti_instances:
                if found_conflict:
                    break
                for tj_s, tj_e in tj_instances:
                    if intervals_overlap(ti_s, ti_e, tj_s, tj_e):
                        found_conflict = True
                        break

            if found_conflict:
                # 统一按编号排序存储，保证一致性
                pair = tuple(sorted([pi.id, pj.id]))
                conflict_set.add(pair)

    # 转为列表并按编号排序
    conflict_pairs = sorted(conflict_set)
    return conflict_pairs
