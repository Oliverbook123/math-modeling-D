"""
方法3：时间排序优化冲突检测
将所有装备的所有时间实例展开，按时间排序
利用时间窗口滑动快速排除时间不交叠的对
再结合频段检查确认冲突
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
    时间排序优化的冲突检测
    步骤：
    1. 展开每个装备的所有时间实例，生成 (装备id, 时间起点, 时间终点, 频段起点, 频段终点)
    2. 按时间起点排序
    3. 对每个时间实例，只检查时间窗口可能交叠的后续实例
    4. 时间交叠后再检查频段交叠
    参数:
        plan_list: 所有装备计划列表
    返回:
        冲突对列表 [(id1, id2), ...]，按编号排序
    """
    # 展开所有时间实例
    # 每条记录: (plan_id, time_start, time_end, freq_start, freq_end)
    events = []
    for p in plan_list:
        for t_s, t_e in p.time_instances():
            events.append((p.id, t_s, t_e, p.freq_start, p.freq_end))

    # 按时间起点升序排序
    events.sort(key=lambda x: x[1])

    conflict_set = set()  # 存储冲突对，自动去重
    n = len(events)

    for i in range(n):
        id_i, ts_i, te_i, fs_i, fe_i = events[i]

        for j in range(i + 1, n):
            id_j, ts_j, te_j, fs_j, fe_j = events[j]

            # 同一装备的不同时间实例不算冲突
            if id_i == id_j:
                continue

            # 优化：如果 events[j] 的时间起点 >= events[i] 的时间终点
            # 则 j 及之后所有事件的时间都不与 i 交叠（已按时间起点排序）
            if ts_j >= te_i:
                break

            # 时间交叠已确认（ts_j < te_i 且 ts_i < te_j，后者由排序保证）
            # 检查频段是否交叠
            if intervals_overlap(fs_i, fe_i, fs_j, fe_j):
                # 确认冲突，按编号排序存储
                pair = tuple(sorted([id_i, id_j]))
                conflict_set.add(pair)

    # 转为排序后的列表
    conflict_pairs = sorted(conflict_set)
    return conflict_pairs
