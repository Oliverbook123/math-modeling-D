# Agent: D题 时频冲突检测与消解

## 任务总览

基于附件 1 的 150 个用频装备计划，完成 4 个子问题。

---

## 项目树规范

```
数学建模实验D题/
├── AGENTS.md              # 任务说明与算法设计（本文件）
├── D题.md                 # 题目原文（markdown 版）
├── D题.pdf                # 题目原文（pdf 原件）
├── IDEA.md                # 解题思路与论文大纲
├── code/
│   ├── 01/                # 问题 1 代码
│   ├── 02/                # 问题 2 代码
│   ├── 03/                # 问题 3 代码
│   ├── 04/                # 问题 4 代码
│   └── output/
│       ├── 01/            # 问题 1 输出（result1.xlsx）
│       ├── 02/            # 问题 2 输出（result2.xlsx）
│       ├── 03/            # 问题 3 输出（result3.xlsx）
│       └── 04/            # 问题 4 输出（result4.xlsx）
└── 附件/
    ├── 附件1.xlsx          # 原始数据：150 个装备用频计划
    └── 附件2/              # 结果模板
        ├── result1.xlsx
        ├── result2.xlsx
        ├── result3.xlsx
        └── result4.xlsx
```

### 规范要求

1. **按题号分目录**：`code/01` 对应问题 1，`code/02` 对应问题 2，依此类推
2. **输出统一归档**：`code/output/01/` 存放问题 1 的 result1.xlsx，以此类推
3. **不修改 `附件/` 目录**：模板和原始数据保持只读
4. **输出文件与模板列对齐**：严格按模板格式填写，不多不少
5. **IDEA.md 记录论文思路**：写论文时从中取结构和结论

---

## 数据结构

```python
@dataclass
class Plan:
    id: str              # 装备编号，如 "A001"
    category: str        # A / B / C
    freq_start: int      # 频段起点
    freq_end: int        # 频段终点（左闭右开）
    time_start: int      # 首次时间起点
    time_end: int        # 首次时间终点（左闭右开）
    interval: int        # 间隔时长
    count: int           # 使用次数

    @property
    def freq_width(self) -> int:
        return self.freq_end - self.freq_start

    @property
    def time_width(self) -> int:
        return self.time_end - self.time_start

    def time_instances(self) -> list[tuple[int, int]]:
        """返回所有使用时间区间 [(start, end), ...]"""
        return [
            (self.time_start + k * self.interval,
             self.time_end + k * self.interval)
            for k in range(self.count)
        ]
```

### 数据特征

| 类别 | 数量 | 频段宽度 | 时间宽度 | 间隔 | 使用次数 |
|------|------|----------|----------|------|----------|
| A    | 20   | 10       | 5Δt      | 60Δt | 3        |
| B    | 40   | 15       | 3Δt      | 40Δt | 4        |
| C    | 90   | 3        | 2Δt      | 8Δt  | 12       |

---

## 问题 1：时频冲突检测

### 判定规则

两个计划冲突 ⟺ 频段有交叠 ∧ 至少一对时间实例有交叠。

### 算法

```
冲突对 = []
对每对 (i, j), i < j:
  if 频段不交叠: continue
  for t_i in i 的所有时间实例:
    for t_j in j 的所有时间实例:
      if t_i 与 t_j 交叠:
        冲突对.append((i.id, j.id))
        break
  // 内层 break 只跳出 j 循环，需标记跳出
```

### 区间交叠判断

区间 $[a, b)$ 与 $[c, d)$ 交叠 ⟺ $a < d$ 且 $c < b$。

### 输出

`result1.xlsx`：A 列序号，B 列装备 1，C 列装备 2。

### 复杂度

- 对数：C(150,2) = 11,175
- 每对最多检查 12×12 = 144 次时间交叠
- 总计 ~160 万次判断，暴力枚举 < 1 秒

---

## 问题 2：时频冲突消解

### 目标

调整或撤销部分计划，使消解后**无冲突**。

### 约束

1. 每个计划最多调整 1 个参数（频段或时间）或撤销
2. 不调整使用次数和间隔时长
3. 优先级：A > B > C（高优先级尽量保留）
4. 频段最大平移 10Δf，时间最大平移 5Δt
5. 尽量少撤销、少调整

### 算法思路

贪心 + 优先级排序：

```
按优先级排序所有计划（A > B > C，同类内按冲突数降序）
对每个计划 p（按优先级从高到低）:
  if p 已标记撤销: skip
  计算 p 与已保留计划的冲突集
  if 无冲突: 标记保留
  else:
    尝试频段平移（±1 到 ±10），检查是否消解所有冲突
    尝试时间平移（±1 到 ±5），检查是否消解所有冲突
    if 可消解: 应用最小幅度的平移
    else: 尝试让低优先级冲突方调整/撤销
    if 仍无法消解: 标记撤销
```

### 输出

`result2.xlsx`：A 列装备编号，B 列调整后频段，C 列调整后时间，D 列"是"（撤销）。

---

## 问题 3：最大化 C 类装备数

### 目标

基于问题 2 的无冲突方案，不限平移幅度，新增尽可能多的 C 类装备。

### 约束

- 不增加时频资源（频段 0~99，时间不受限但不新增资源）
- 新增装备必须无冲突

### 算法思路

本质上是**区间打包问题**（Interval Packing）：

```
已有方案 = 问题 2 的无冲突计划集
候选 C 类装备 = 原始 90 个 C 类装备（或可自定义新装备）
对每个候选装备:
  枚举所有可能的频段平移和时间平移
  检查是否与已有方案无冲突
  if 可安排: 记录方案
```

由于不限平移幅度，相当于在时频平面上寻找空闲格子来放置 C 类装备的占用区域。

### 输出

`result3.xlsx`：A 列序号，B 列频段区间，C 列时间区间。

---

## 问题 4：放宽间隔约束的冲突消解

### 目标

与问题 2 相同，但允许 C 类装备调整间隔时长，差异 ≤ 10Δt。

### 新增自由度

- C 类装备可调整间隔时长：原间隔 δ → [δ-10, δ+10] 范围内的整数
- 仍受其他约束（频段平移 ≤ 10Δf，时间平移 ≤ 5Δt）

### 算法

在问题 2 的消解算法基础上，对 C 类装备增加一个搜索维度：尝试调整间隔时长。

```
对 C 类计划 p:
  在问题 2 的消解逻辑中，额外尝试:
  for 新间隔 in [原间隔 - 10, 原间隔 + 10]:
    重新计算 p 的所有时间实例
    检查是否与已保留计划无冲突
    if 可消解: 应用调整
```

### 输出

`result4.xlsx`：A 列装备编号，B 列频段，C 列时间，D 列间隔，E 列"是"（撤销）。

---

## 开发环境

### ⚠️ 强制规则：只用 `uv`

**禁止使用以下命令**安装包或执行代码：
- `pip`、`pip3`
- `python`、`python3`
- `python -m venv`、`python3 -m venv`

所有 Python 包安装和脚本执行**必须**通过 `uv` 完成：

```bash
# 创建虚拟环境
uv venv .venv

# 激活
source .venv/bin/activate

# 安装依赖（唯一合法方式）
uv pip install openpyxl matplotlib

# 执行脚本（唯一合法方式）
uv run python code/01/main.py
```

### 问题 1 代码结构

`code/01/` 下按方法分子目录，每种方法独立：

```
code/01/
├── main.py                  # 主入口：依次运行所有方法，汇总结果
├── method1_bruteforce/      # 方法 1：暴力枚举
│   ├── __init__.py
│   └── bruteforce.py
├── method2_freqsort/        # 方法 2：频段排序优化
│   ├── __init__.py
│   └── freqsort.py
├── method3_timesort/        # 方法 3：时间排序优化
│   ├── __init__.py
│   └── timesort.py
└── common/                  # 公共模块（数据加载、Plan 类等）
    ├── __init__.py
    └── data_loader.py

code/output/01/
├── method1_bruteforce/
│   ├── result.json          # 冲突对列表 + 统计
│   └── conflict_chart.png   # 可视化图表
├── method2_freqsort/
│   ├── result.json
│   └── conflict_chart.png
├── method3_timesort/
│   ├── result.json
│   └── conflict_chart.png
├── result1.xlsx             # 最终结果（模板对齐）
└── summary.json             # 汇总：各方法冲突数、耗时、一致性
```

### 代码规范

1. **完整中文注释**：每个函数、每个逻辑块都要有中文注释
2. **输出 JSON**：每个方法的 result.json 包含冲突对列表和统计信息
3. **输出图表**：每个方法生成 matplotlib 可视化图表
4. **汇总文件**：summary.json 对比各方法的结果一致性和性能

---

## 实现计划

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | 读取附件 1，解析为 Plan 列表 | `code/01/common/data_loader.py` |
| 2 | 问题 1 方法 1：暴力枚举冲突检测 | `code/01/method1_bruteforce/bruteforce.py` |
| 3 | 问题 1 方法 2：频段排序优化 | `code/01/method2_freqsort/freqsort.py` |
| 4 | 问题 1 方法 3：时间排序优化 | `code/01/method3_timesort/timesort.py` |
| 5 | 问题 1 主入口 + 汇总 | `code/01/main.py → code/output/01/` |
| 6 | 问题 2：贪心消解 | `code/02/main.py → code/output/02/result2.xlsx` |
| 7 | 问题 3：C 类扩容 | `code/03/main.py → code/output/03/result3.xlsx` |
| 8 | 问题 4：放宽间隔约束消解 | `code/04/main.py → code/output/04/result4.xlsx` |

依赖：`openpyxl`（读写 xlsx）、`matplotlib`（可视化图表）、`scikit-learn`（聚类等优化算法）

---

## 验证

每个问题完成后需验证：

1. **问题 1**：抽样检查几对冲突，手动验证频段和时间确实交叠
2. **问题 2–4**：对最终方案重新运行冲突检测，确认 0 冲突
3. **问题 2**：统计表 1（A/B/C 各类保留/调整/撤销数量）
4. **问题 3**：确认新增装备数最大（可对比上下界）
