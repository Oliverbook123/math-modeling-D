# -*- coding: utf-8 -*-
"""
问题3 方法2：空闲格子扫描（扫描线优化）
先按频段分组，扫描每个频段的空闲时间窗口，在窗口内密集放置。
比纯贪心更高效：跳过已知被占用的区域。
"""

from typing import List, Set, Tuple, Dict
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.data_loader import (
    Plan, build_occupied_set, get_max_time, can_place_c, place_c,
    FREQ_BAND, C_FREQ_WIDTH, C_TIME_WIDTH, C_INTERVAL, C_COUNT
)


def run(active_plans: List[Plan]) -> List[Plan]:
    """
    扫描线法主函数。
    1. 构建占用集合
    2. 对每个可行的频段起点 f0 (0~97)，提取该频段范围内的空闲时间窗口
    3. 在每个窗口内按步长 C_INTERVAL 密集放置 C 类装备
    """
    occupied = build_occupied_set(active_plans)
    max_time = get_max_time(active_plans)
    time_end = max_time - (C_COUNT - 1) * C_INTERVAL - C_TIME_WIDTH + 1
    if time_end <= 0:
        time_end = 1

    new_plans = []

    # 对每个频段起点 f0，扫描可放置的时间位置
    for f0 in range(FREQ_BAND[1] - C_FREQ_WIDTH + 1):
        # 收集该频段范围 [f0, f0+3) 内所有被占用的时间格子
        occupied_times = set()
        for f in range(f0, f0 + C_FREQ_WIDTH):
            for (ff, tt) in occupied:
                if ff == f:
                    occupied_times.add(tt)

        # 扫描时间轴，找空闲窗口
        # 在窗口内以 C_INTERVAL 为步长尝试放置
        t = 0
        while t < time_end:
            # 检查当前位置是否可行
            if can_place_c(f0, t, occupied):
                new_plans.append(place_c(f0, t, occupied))
                t += C_INTERVAL  # 跳到下一次尝试位置
            else:
                t += 1  # 步进1继续搜索

    return new_plans
