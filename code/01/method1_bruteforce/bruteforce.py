"""
方法1：暴力枚举冲突检测
对所有 C(n,2) 对装备逐一检查频段和时间是否交叠
复杂度：O(n^2 * count_i * count_j)，约160万次判断
"""

import sys
import os

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
    暴力枚举所有装备对，检测时频冲突
    参数:
        plan_list: 所有装备计划列表
    返回:
        冲突对列表 [(id1, id2), ...]，按编号排序
    """
    conflict_pairs = []  # 存储所有冲突对
    n = len(plan_list)

    # 遍历所有 C(n,2) 对
    for i in range(n):
        pi = plan_list[i]
        # 获取装备 i 的所有时间实例
        ti_instances = pi.time_instances()

        for j in range(i + 1, n):
            pj = plan_list[j]

            # 第一步：检查频段是否交叠
            # 频段 [pi.freq_start, pi.freq_end) 与 [pj.freq_start, pj.freq_end)
            if not intervals_overlap(pi.freq_start, pi.freq_end,
                                     pj.freq_start, pj.freq_end):
                continue  # 频段不交叠，跳过此对

            # 第二步：频段交叠，检查是否有时间实例交叠
            tj_instances = pj.time_instances()
            found_conflict = False

            # 遍历装备 i 的每个时间实例
            for ti_s, ti_e in ti_instances:
                if found_conflict:
                    break
                # 遍历装备 j 的每个时间实例
                for tj_s, tj_e in tj_instances:
                    if intervals_overlap(ti_s, ti_e, tj_s, tj_e):
                        # 找到一对交叠的时间实例，确认冲突
                        found_conflict = True
                        break

            if found_conflict:
                # 记录冲突对，确保编号顺序一致
                conflict_pairs.append((pi.id, pj.id))

    return conflict_pairs
