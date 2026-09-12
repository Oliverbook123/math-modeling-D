# -*- coding: utf-8 -*-
"""
独立复审 result4.xlsx：
  1. 解析每一行的调整/撤销动作
  2. 校验约束（每计划至多动1项、幅度上限、间隔仅限C类且差≤10）
  3. 回填 150 个计划后重新做全量冲突检测，确认 0 冲突
  4. 独立重算表1统计
"""
import json
import re
import sys
from collections import Counter

sys.path.insert(0, "code/01")
from common.data_loader import Plan, load_plans, get_data_path  # noqa: E402
import openpyxl  # noqa: E402


def overlap(a1, a2, b1, b2):
    return a1 < b2 and b1 < a2


def conflict(p1, p2):
    if not overlap(p1.freq_start, p1.freq_end, p2.freq_start, p2.freq_end):
        return False
    for s1, e1 in p1.time_instances():
        for s2, e2 in p2.time_instances():
            if overlap(s1, e1, s2, e2):
                return True
    return False


def main():
    plans = load_plans(get_data_path())
    by_id = {p.id: i for i, p in enumerate(plans)}
    # 拷贝一份原始计划用于回填
    new = [Plan(p.id, p.category, p.freq_start, p.freq_end,
                p.time_start, p.time_end, p.interval, p.count) for p in plans]
    revoked = set()
    errors = []

    wb = openpyxl.load_workbook("code/output/04/result4.xlsx")
    ws = wb.active
    n_rows = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[0] is None:
            continue
        n_rows += 1
        pid, fstr, tstr, istr, rev = row[0], row[1] if len(row) > 1 else None, \
            row[2] if len(row) > 2 else None, row[3] if len(row) > 3 else None, \
            row[4] if len(row) > 4 else None
        if pid not in by_id:
            errors.append(f"未知编号 {pid}")
            continue
        i = by_id[pid]
        orig = plans[i]
        # 每行至多一个动作
        cnt = sum(x is not None for x in (fstr, tstr, istr)) + (1 if rev else 0)
        if cnt != 1:
            errors.append(f"{pid} 动了 {cnt} 项（应恰好1项）")
            continue
        if rev:
            revoked.add(pid)
            continue
        if fstr is not None:
            a, b = map(int, re.findall(r"\d+", str(fstr)))
            if abs(a - orig.freq_start) > 10 or (b - a) != orig.freq_width:
                errors.append(f"{pid} 频段调整违规 {orig.freq_start},{orig.freq_end} -> {a},{b}")
            if not (0 <= a and b <= 100):
                errors.append(f"{pid} 频段越界 {a},{b}")
            new[i].freq_start, new[i].freq_end = a, b
        elif tstr is not None:
            a, b = map(int, re.findall(r"\d+", str(tstr)))
            if abs(a - orig.time_start) > 5 or (b - a) != orig.time_width:
                errors.append(f"{pid} 时间调整违规 {orig.time_start},{orig.time_end} -> {a},{b}")
            if a < 0:
                errors.append(f"{pid} 时间越界 {a}")
            new[i].time_start, new[i].time_end = a, b
        elif istr is not None:
            v = int(istr)
            if orig.category != "C":
                errors.append(f"{pid} 非C类调间隔")
            if abs(v - orig.interval) > 10 or v < 1:
                errors.append(f"{pid} 间隔调整违规 {orig.interval} -> {v}")
            new[i].interval = v

    # 回填后全网重检
    active = [p for p in new if p.id not in revoked]
    c = sum(1 for i in range(len(active)) for j in range(i + 1, len(active))
            if conflict(active[i], active[j]))

    # 独立重算表1
    keep, adj, revc = Counter(), Counter(), Counter()
    interval_cnt = 0
    for p, o in zip(new, plans):
        if p.id in revoked:
            revc[p.category] += 1
            continue
        diff = (p.freq_start != o.freq_start) + (p.time_start != o.time_start) + (p.interval != o.interval)
        if diff == 0:
            keep[p.category] += 1
        else:
            adj[p.category] += 1
            if p.interval != o.interval:
                interval_cnt += 1

    out = {
        "result4行数": n_rows,
        "独立复检冲突数": c,
        "约束违规": errors,
        "表1": {k: {"保留": keep[k], "调整": adj[k], "撤销": revc[k]} for k in "ABC"},
        "调间隔个数": interval_cnt,
    }
    print(json.dumps(out, ensure_ascii=False, indent=1))
    assert c == 0 and not errors, "复审失败！"
    print("PASS: 0 冲突，约束全部满足")


if __name__ == "__main__":
    main()
