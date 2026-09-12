"""
方法5：扫描线法冲突检测
将所有时间实例展开为事件点（开始/结束），按时间排序后用扫描线维护活跃实例集合
对新加入的时间实例，检查与活跃实例所属装备的频段交叠

复杂度：
- 事件点总数：M = n * avg_count ≈ 150 * 8 = 1200
- 排序：O(M log M)
- 扫描过程中，每个事件对活跃集合做检查：O(M * |active|)
- 总体：O(M log M + M * |active| * freq_check)
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
    扫描线法冲突检测
    将所有时间实例展开为事件点，按时间排序后用扫描线维护当前活跃装备
    当新的时间实例开始时，检查与已有活跃装备的频段交叠

    关键：左闭右开区间 [a, b) 和 [b, c) 不交叠
    因此在同一时间点 b，必须先处理 end 事件再处理 start 事件
    排序键：end=0（优先处理），start=1（后处理）

    参数:
        plan_list: 所有装备计划列表
    返回:
        冲突对列表 [(id1, id2), ...]，按编号排序
    """
    # 建立 id -> plan 映射
    id_to_plan = {p.id: p for p in plan_list}

    # 第一步：展开所有时间实例为事件点
    # 每个事件：(时间点, 排序键, 装备ID)
    # 排序键：end=0, start=1 → 同一时间点 end 先处理
    events = []
    for plan in plan_list:
        for t_start, t_end in plan.time_instances():
            events.append((t_start, 1, plan.id))   # start 事件，排序键=1
            events.append((t_end, 0, plan.id))      # end 事件，排序键=0

    # 排序：按 (时间, 排序键) 排序
    # 同一时间点：end(0) 先于 start(1)
    events.sort()

    # 第二步：扫描线处理
    # conflict_set: 已发现的冲突对集合（避免重复）
    conflict_set = set()
    # active_refcount: 装备ID -> 活跃时间实例数量
    # 一个装备可能有多个时间实例，用引用计数跟踪
    active_refcount = {}

    for time_point, sort_key, plan_id in events:
        is_start = (sort_key == 1)

        if not is_start:
            # end 事件：时间实例结束，递减引用计数
            active_refcount[plan_id] = active_refcount.get(plan_id, 0) - 1
            if active_refcount[plan_id] <= 0:
                del active_refcount[plan_id]
        else:
            # start 事件：新的时间实例开始
            new_plan = id_to_plan[plan_id]

            # 检查与所有当前活跃装备的冲突
            for active_id in active_refcount:
                # 跳过自身
                if active_id == plan_id:
                    continue

                # 确保冲突对只记录一次（小ID在前）
                pair_key = (min(plan_id, active_id), max(plan_id, active_id))
                if pair_key in conflict_set:
                    continue

                active_plan = id_to_plan[active_id]

                # 检查频段是否交叠
                if not intervals_overlap(
                    new_plan.freq_start, new_plan.freq_end,
                    active_plan.freq_start, active_plan.freq_end
                ):
                    continue

                # 频段交叠 + 时间实例在 time_point 处都活跃 → 冲突
                conflict_set.add(pair_key)

            # 递增引用计数
            active_refcount[plan_id] = active_refcount.get(plan_id, 0) + 1

    # 将冲突对排序后返回
    return sorted(conflict_set)
