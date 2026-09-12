"""
数据加载模块
负责读取附件1.xlsx，解析为 Plan 对象列表
"""

import re
import os
from dataclasses import dataclass
import openpyxl


@dataclass
class Plan:
    """用频装备计划数据类"""
    id: str              # 装备编号，如 'A001'
    category: str        # 类别：A / B / C
    freq_start: int      # 频段起点（含）
    freq_end: int        # 频段终点（不含，左闭右开）
    time_start: int      # 首次使用时间起点（含）
    time_end: int        # 首次使用时间终点（不含，左闭右开）
    interval: int        # 间隔时长
    count: int           # 使用次数

    @property
    def freq_width(self) -> int:
        """频段宽度"""
        return self.freq_end - self.freq_start

    @property
    def time_width(self) -> int:
        """单次使用时间宽度"""
        return self.time_end - self.time_start

    def time_instances(self) -> list[tuple[int, int]]:
        """
        返回所有使用时间区间列表 [(start, end), ...]
        每次使用的时间起点 = 首次起点 + k * 间隔
        每次使用的时间终点 = 首次终点 + k * 间隔
        """
        return [
            (self.time_start + k * self.interval,
             self.time_end + k * self.interval)
            for k in range(self.count)
        ]


def parse_interval(s: str) -> tuple[int, int]:
    """
    解析区间字符串，如 '[80,90)' -> (80, 90)
    支持 [a,b) 格式（左闭右开）
    """
    # 去除空格，用正则提取两个数字
    s = s.strip()
    match = re.match(r'[\[\(]\s*(\d+)\s*,\s*(\d+)\s*[\]\)]', s)
    if not match:
        raise ValueError(f"无法解析区间字符串: {s}")
    return int(match.group(1)), int(match.group(2))


def load_plans(filepath: str) -> list[Plan]:
    """
    从 Excel 文件加载所有装备计划
    参数:
        filepath: xlsx 文件路径
    返回:
        Plan 对象列表
    """
    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active

    plans = []
    # 跳过表头行，从第2行开始读取
    for row in ws.iter_rows(min_row=2, values_only=True):
        # 跳过空行
        if row[0] is None:
            continue

        plan_id = str(row[0]).strip()           # A列：装备编号
        category = plan_id[0]                    # 从编号首字母提取类别

        # 解析频段区间 [freq_start, freq_end)
        freq_start, freq_end = parse_interval(str(row[1]))

        # 解析时间区间 [time_start, time_end)
        time_start, time_end = parse_interval(str(row[2]))

        interval = int(row[3])                   # D列：间隔时长
        count = int(row[4])                      # E列：使用次数

        plans.append(Plan(
            id=plan_id,
            category=category,
            freq_start=freq_start,
            freq_end=freq_end,
            time_start=time_start,
            time_end=time_end,
            interval=interval,
            count=count,
        ))

    wb.close()
    return plans


def get_data_path() -> str:
    """
    获取附件1.xlsx 的绝对路径
    从当前文件向上查找项目根目录
    """
    # 当前文件: code/01/common/data_loader.py
    # 项目根目录: 向上3级
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    return os.path.join(project_root, '附件', '附件1.xlsx')


def get_output_dir() -> str:
    """
    获取输出目录 code/output/01/ 的绝对路径
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    return os.path.join(project_root, 'code', 'output', '01')
