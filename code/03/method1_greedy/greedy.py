# -*- coding: utf-8 -*-
"""
问题3 方法1：贪心枚举
按频段和时间逐格扫描，能放就放。
两种遍历顺序都试，取最优。
"""

from typing import List, Set, Tuple
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.data_loader import (
    Plan, build_occupied_set, get_max_time, can_place_c, place_c,
    FREQ_BAND, C_FREQ_WIDTH, C_TIME_WIDTH, C_INTERVAL, C_COUNT
)


def run(active_plans: List[Plan]) -> List[Plan]:
    """
    贪心枚举主函数。
    用频段优先和时间优先两种策略，返回新增数量更多的结果。
    参数: active_plans - 问题2消解后的无冲突活跃计划
    返回: 新增 C 类装备列表
    """
    # 频段优先
    plans_freq = _greedy(active_plans, freq_first=True)
    # 时间优先
    plans_time = _greedy(active_plans, freq_first=False)
    # 取最优
    if len(plans_freq) >= len(plans_time):
        return plans_freq
    return plans_time


def _greedy(active_plans: List[Plan], freq_first: bool = True) -> List[Plan]:
    """内部贪心实现，freq_first=True 频段优先，False 时间优先"""
    occupied = build_occupied_set(active_plans)
    max_time = get_max_time(active_plans)
    time_end = max_time - (C_COUNT - 1) * C_INTERVAL - C_TIME_WIDTH + 1
    if time_end <= 0:
        time_end = 1

    new_plans = []
    f_range = range(FREQ_BAND[1] - C_FREQ_WIDTH + 1)  # 0~97
    t_range = range(time_end)

    if freq_first:
        for f0 in f_range:
            for t0 in t_range:
                if can_place_c(f0, t0, occupied):
                    new_plans.append(place_c(f0, t0, occupied))
    else:
        for t0 in t_range:
            for f0 in f_range:
                if can_place_c(f0, t0, occupied):
                    new_plans.append(place_c(f0, t0, occupied))

    return new_plans
