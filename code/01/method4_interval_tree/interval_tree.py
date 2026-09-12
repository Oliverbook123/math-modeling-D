"""
方法4：区间树法冲突检测
对频段维度建立手写区间树（Interval Tree），快速查询频段交叠的装备对
然后逐一检查时间实例是否交叠

复杂度：
- 建树：O(n log n)
- 单次查询：O(log n + k)，k 为交叠区间数
- 总体：O(n log n + n * (log n + k) * count_i * count_j)
- 对于本题 n=150，实际性能与暴力法接近，但理论上在大规模数据下更优
"""

import sys
import os

# 将项目根目录加入 sys.path，以便导入 common 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.data_loader import Plan


# ============================================================
# 手写区间树实现（不依赖 sortedcontainers）
# ============================================================

class IntervalNode:
    """
    区间树节点
    每个节点存储一个区间 [low, high)，以及该子树中最大的 high 值
    """
    def __init__(self, low, high, plan):
        self.low = low          # 区间起点
        self.high = high        # 区间终点
        self.plan = plan        # 关联的装备计划
        self.max_high = high    # 子树中最大区间终点
        self.left = None        # 左子树
        self.right = None       # 右子树


class IntervalTree:
    """
    手写区间树（Interval Tree）
    支持插入区间和查询与给定区间交叠的所有区间
    使用二叉搜索树结构，按区间起点排序
    """

    def __init__(self):
        """初始化空区间树"""
        self.root = None

    def insert(self, low, high, plan):
        """
        插入一个区间及其关联的装备计划
        参数:
            low: 区间起点
            high: 区间终点
            plan: 关联的装备计划对象
        """
        self.root = self._insert(self.root, low, high, plan)

    def _insert(self, node, low, high, plan):
        """
        递归插入区间到子树中
        按区间起点 low 排序，同时维护子树最大终点 max_high
        """
        if node is None:
            return IntervalNode(low, high, plan)

        # 按 low 值决定插入方向
        if low < node.low:
            node.left = self._insert(node.left, low, high, plan)
        else:
            node.right = self._insert(node.right, low, high, plan)

        # 更新子树最大终点
        if high > node.max_high:
            node.max_high = high
        if node.left and node.left.max_high > node.max_high:
            node.max_high = node.left.max_high
        if node.right and node.right.max_high > node.max_high:
            node.max_high = node.right.max_high

        return node

    def query_overlap(self, low, high):
        """
        查询与给定区间 [low, high) 交叠的所有装备计划
        参数:
            low: 查询区间起点
            high: 查询区间终点
        返回:
            交叠的装备计划列表
        """
        results = []
        self._query(self.root, low, high, results)
        return results

    def _query(self, node, low, high, results):
        """
        递归查询与 [low, high) 交叠的区间
        利用 max_high 剪枝：如果子树最大终点 <= 查询起点，则该子树无交叠
        """
        if node is None:
            return

        # 检查当前节点区间是否与查询区间交叠
        # 交叠条件：node.low < high 且 low < node.high
        if node.low < high and low < node.high:
            results.append(node.plan)

        # 如果左子树存在且其最大终点 > 查询起点，则左子树可能有交叠
        if node.left and node.left.max_high > low:
            self._query(node.left, low, high, results)

        # 如果当前节点起点 < 查询终点，则右子树可能有交叠
        if node.low < high:
            self._query(node.right, low, high, results)


# ============================================================
# 冲突检测辅助函数
# ============================================================

def intervals_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """
    判断两个左闭右开区间 [a_start, a_end) 与 [b_start, b_end) 是否交叠
    交叠条件：a_start < b_end 且 b_start < a_end
    """
    return a_start < b_end and b_start < a_end


def run(plan_list: list[Plan]) -> list[tuple[str, str]]:
    """
    区间树法冲突检测
    对频段维度建立区间树，对每个装备查询频段交叠的候选装备，
    然后检查时间实例是否交叠

    参数:
        plan_list: 所有装备计划列表
    返回:
        冲突对列表 [(id1, id2), ...]，按编号排序
    """
    conflict_pairs = []  # 存储所有冲突对
    n = len(plan_list)

    # 第一步：建立频段区间树
    # 将每个装备的频段区间插入区间树
    tree = IntervalTree()
    for plan in plan_list:
        tree.insert(plan.freq_start, plan.freq_end, plan)

    # 第二步：对每个装备，查询频段交叠的候选装备
    # 用集合记录已检查的装备对，避免重复
    checked = set()

    for i in range(n):
        pi = plan_list[i]
        # 获取装备 i 的所有时间实例
        ti_instances = pi.time_instances()

        # 用区间树查询频段与 pi 交叠的所有装备
        candidates = tree.query_overlap(pi.freq_start, pi.freq_end)

        for pj in candidates:
            # 跳过自身
            if pj.id == pi.id:
                continue

            # 确保每个冲突对只检查一次（小ID在前）
            pair_key = (min(pi.id, pj.id), max(pi.id, pj.id))
            if pair_key in checked:
                continue
            checked.add(pair_key)

            # 检查是否有时间实例交叠
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
                conflict_pairs.append((min(pi.id, pj.id), max(pi.id, pj.id)))

    return conflict_pairs
