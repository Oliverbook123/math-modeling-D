# -*- coding: utf-8 -*-
"""
问题 4 方案 3：贪心 + 回溯重试 + 局部搜索（含间隔维度）

比方案1多了两个阶段：
  阶段1 贪心：与方案1相同（间隔维度已并入动作空间）。
  阶段2 撤销恢复（局部搜索一）：遍历每个被撤销计划，尝试在其他计划
        只允许"更小幅度的既有调整"不变的前提下把它救回来；
        若能以不新增撤销的方式安置则接受。
  阶段3 调整瘦身（局部搜索二）：对每个被调整的计划，尝试回退为 keep
        或幅度更小的动作，只要不产生新冲突。

运行方式（项目根目录下）：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl python code/04/method3_greedy_ls/greedy_ls.py
"""

import csv
import json
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
CODE04_DIR = os.path.join(PROJECT_ROOT, "code", "04")
for p in (CODE01_DIR, CODE04_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from common.data_loader import load_plans, get_data_path  # noqa: E402
from method1_greedy.greedy import (  # noqa: E402
    plans_conflict, make_plan, get_ordered_actions, greedy_resolve,
    count_conflicts_active, build_summary, EXPECTED_CONFLICTS,
)
import openpyxl

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "04", "method3_greedy_ls")


def action_mag(action):
    """动作幅度 = |频移| + |时移| + |间隔调整|"""
    return abs(action[1]) + abs(action[2]) + abs(action[3])


def revive_revoked(plans, decisions):
    """
    局部搜索一：逐个尝试把撤销计划救回来。
    按 类别优先级(A>B>C) → 编号 顺序尝试；成功条件：存在一个动作使它与
    全部活跃计划无冲突。撤销数单调下降且消毒过的解保持0冲突，故直接接受。
    """
    order = sorted((i for i, d in enumerate(decisions) if d[0] == 'revoke'),
                   key=lambda i: (plans[i].category == 'C', plans[i].category == 'B', plans[i].id))
    revived = 0
    for idx in order:
        p = plans[idx]
        active = [(j, make_plan(plans[j], *decisions[j][1:]))
                  for j, d in enumerate(decisions) if d[0] != 'revoke']
        for action in get_ordered_actions(p):
            np_ = make_plan(p, *action[1:])
            if any(plans_conflict(np_, ap) for _, ap in active):
                continue
            decisions[idx] = action
            active.append((idx, np_))
            revived += 1
            break
    return decisions, revived


def shrink_adjustments(plans, decisions):
    """
    局部搜索二：调整瘦身。多轮扫描，每个调整计划尝试换更小幅度的无冲突动作
    （包括完全回退为 keep）。只减幅度不减约束，冲突始终保持0。
    """
    improved = 0
    changed = True
    while changed:
        changed = False
        for idx, d in enumerate(decisions):
            if d[0] in ('keep', 'revoke'):
                continue
            p = plans[idx]
            cur_mag = action_mag(d)
            active = [(j, make_plan(plans[j], *decisions[j][1:]))
                      for j in range(len(plans))
                      if decisions[j][0] != 'revoke' and j != idx]
            for action in get_ordered_actions(p):
                if action_mag(action) >= cur_mag:
                    break  # 动作已按幅度升序，后面只会更大
                np_ = make_plan(p, *action[1:])
                if any(plans_conflict(np_, ap) for _, ap in active):
                    continue
                decisions[idx] = action
                improved += 1
                changed = True
                break
    return decisions, improved


def main():
    print("=" * 60)
    print("问题 4 方案 3：贪心 + 撤销恢复 + 调整瘦身（含间隔维度）")
    print("=" * 60)

    plans = load_plans(get_data_path())
    n = len(plans)
    cc = sum(1 for i in range(n) for j in range(i + 1, n) if plans_conflict(plans[i], plans[j]))
    print(f"加载 {n} 个计划，原始冲突 {cc} (基准 {EXPECTED_CONFLICTS})")
    assert cc == EXPECTED_CONFLICTS

    t0 = time.time()
    # 阶段1：贪心
    decisions = greedy_resolve(plans)
    fc = count_conflicts_active(plans, decisions)
    rev0 = sum(1 for d in decisions if d[0] == 'revoke')
    print(f"阶段1 贪心: 撤销 {rev0}, 冲突 {fc}")

    # 阶段2：撤销恢复
    decisions, revived = revive_revoked(plans, decisions)
    fc = count_conflicts_active(plans, decisions)
    rev1 = sum(1 for d in decisions if d[0] == 'revoke')
    print(f"阶段2 撤销恢复: 救回 {revived} 个, 撤销 {rev1}, 冲突 {fc}")

    # 阶段3：调整瘦身
    decisions, improved = shrink_adjustments(plans, decisions)
    fc = count_conflicts_active(plans, decisions)
    print(f"阶段3 调整瘦身: {improved} 处改进, 冲突 {fc}")
    elapsed = time.time() - t0
    assert fc == 0, f"仍有 {fc} 对冲突！"

    summary = build_summary(plans, decisions, fc, elapsed)
    summary["方法"] = "方案3_贪心+局部搜索+间隔维度"
    summary["局部搜索"] = {"阶段1贪心撤销": rev0, "救回个数": revived,
                           "阶段3瘦身次数": improved}

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUTPUT_DIR, "result.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['装备编号', '类别', '决策', '频段平移', '时间平移', '间隔调整',
                    '调整后频段区间', '调整后时间区间', '调整后间隔'])
        for i, (at, df, dt, di) in enumerate(decisions):
            p = plans[i]
            if at == 'revoke':
                w.writerow([p.id, p.category, '撤销', '', '', '', '', '', ''])
            else:
                np_ = make_plan(p, df, dt, di)
                label = {'keep': '保留', 'freq': '调频段', 'time': '调时间', 'interval': '调间隔'}[at]
                w.writerow([p.id, p.category, label, df, dt, di,
                            f'[{np_.freq_start},{np_.freq_end})',
                            f'[{np_.time_start},{np_.time_end})', np_.interval])

    with open(os.path.join(OUTPUT_DIR, "summary.json"), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    xlsx_path = os.path.join(OUTPUT_DIR, "result4_greedy_ls.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(['用频装备编号', '调整后频段范围', '调整后时间区间', '调整后间隔时长', '是否撤销用频计划'])
    for i, (at, df, dt, di) in enumerate(decisions):
        p = plans[i]
        if at == 'revoke':
            ws.append([p.id, None, None, None, '是'])
        elif at == 'freq':
            ws.append([p.id, f'[{p.freq_start + df},{p.freq_end + df})', None, None, None])
        elif at == 'time':
            ws.append([p.id, None, f'[{p.time_start + dt},{p.time_end + dt})', None, None])
        elif at == 'interval':
            ws.append([p.id, None, None, p.interval + di, None])
    wb.save(xlsx_path)

    obj = summary["目标函数"]
    print(f"\n最终: 撤销 {obj['第1层_撤销总数']}（A{obj['第2层_A撤销']}/B{obj['第2层_B撤销']}/C{obj['第2层_C撤销']}）"
          f" 调整 {obj['第3层_调整数']} 幅度 {obj['第4层_总调整幅度']}"
          f"（调间隔 {obj['其中间隔调整个数']} 个），耗时 {elapsed:.2f}s")
    print(f"输出: {xlsx_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
