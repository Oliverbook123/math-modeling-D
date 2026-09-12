
# -*- coding: utf-8 -*-
"""问题2审查脚本：独立验证4个方案"""
import csv, json, os, sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
if CODE01_DIR not in sys.path:
    sys.path.insert(0, CODE01_DIR)
from common.data_loader import Plan, load_plans, get_data_path

def intervals_overlap(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end

def plans_conflict(p1, p2):
    if not intervals_overlap(p1.freq_start, p1.freq_end, p2.freq_start, p2.freq_end):
        return False
    for ts1, te1 in p1.time_instances():
        for ts2, te2 in p2.time_instances():
            if intervals_overlap(ts1, te1, ts2, te2):
                return True
    return False

def make_shifted_plan(plan, freq_shift=0, time_shift=0):
    return Plan(id=plan.id, category=plan.category,
                freq_start=plan.freq_start+freq_shift, freq_end=plan.freq_end+freq_shift,
                time_start=plan.time_start+time_shift, time_end=plan.time_end+time_shift,
                interval=plan.interval, count=plan.count)

plans = load_plans(get_data_path())
n = len(plans)

# C2: 独立冲突检测
print("=" * 60)
print("C2: 独立冲突检测")
conflict_pairs = []
for i in range(n):
    for j in range(i+1, n):
        if plans_conflict(plans[i], plans[j]):
            conflict_pairs.append((plans[i].id, plans[j].id))
print(f"  原始冲突对数: {len(conflict_pairs)} (基准237)")
assert len(conflict_pairs) == 237
aa = [p for p in conflict_pairs if p[0][0]=='A' and p[1][0]=='A']
print(f"  A-A冲突: {aa}")

methods = {
    "方案1_贪心": "code/output/02/method1_greedy",
    "方案2_ILP": "code/output/02/method2_ilp",
    "方案3_贪心": "code/output/02/method3_greedy_ls",
    "方案4_SA": "code/output/02/method4_sa",
}

def read_decisions(method_dir):
    csv_path = os.path.join(PROJECT_ROOT, method_dir, "result.csv")
    decisions = {}
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            pid = row[0]
            decision = row[2]
            if decision == '撤销':
                decisions[pid] = ('revoke', 0, 0)
            elif decision == '保留':
                decisions[pid] = ('keep', 0, 0)
            elif decision == '调频段':
                df = int(row[3])
                decisions[pid] = ('freq', df, 0)
            elif decision == '调时间':
                dt = int(row[4])
                decisions[pid] = ('time', 0, dt)
    return decisions

results = {}
for name, path in methods.items():
    print(f"\n{'='*60}")
    print(f"审查: {name}")
    print(f"{'='*60}")
    
    decisions = read_decisions(path)
    print(f"  读取{len(decisions)}个计划决策")
    
    # 统计表1
    a_keep=a_adj=a_rev=0
    b_keep=b_adj=b_rev=0
    c_keep=c_adj=c_rev=0
    total_mag = 0
    issues = []
    
    for p in plans:
        pid = p.id
        if pid not in decisions:
            issues.append(f"  {pid}: 缺失决策")
            continue
        at, df, dt = decisions[pid]
        cat = p.category
        
        # A1: 只动1个参数
        if at not in ('keep', 'revoke'):
            if df != 0 and dt != 0:
                issues.append(f"  {pid}: 同时调整频段和时间!")
        
        # A2: 幅度
        if at == 'freq' and abs(df) > 10:
            issues.append(f"  {pid}: 频段平移{df}超限!")
        if at == 'time' and abs(dt) > 5:
            issues.append(f"  {pid}: 时间平移{dt}超限!")
        
        # A3: 边界
        if at not in ('keep', 'revoke'):
            np = make_shifted_plan(p, df, dt)
            if np.freq_start < 0 or np.freq_end > 100:
                issues.append(f"  {pid}: 频段越界[{np.freq_start},{np.freq_end})")
            if np.time_start < 0:
                issues.append(f"  {pid}: 时间起点{np.time_start}<0")
            total_mag += abs(df) + abs(dt)
        
        # 统计
        if at == 'revoke':
            if cat == 'A': a_rev += 1
            elif cat == 'B': b_rev += 1
            else: c_rev += 1
        elif at != 'keep':
            if cat == 'A': a_adj += 1
            elif cat == 'B': b_adj += 1
            else: c_adj += 1
        else:
            if cat == 'A': a_keep += 1
            elif cat == 'B': b_keep += 1
            else: c_keep += 1
    
    # 独立冲突检测
    active = []
    for p in plans:
        pid = p.id
        at, df, dt = decisions[pid]
        if at == 'revoke': continue
        active.append(make_shifted_plan(p, df, dt))
    fc = 0
    for i in range(len(active)):
        for j in range(i+1, len(active)):
            if plans_conflict(active[i], active[j]):
                fc += 1
    
    print(f"  独立冲突检测: {fc} (应为0)")
    print(f"  表1: A({a_keep}/{a_adj}/{a_rev}) B({b_keep}/{b_adj}/{b_rev}) C({c_keep}/{c_adj}/{c_rev})")
    print(f"  撤销总数: {a_rev+b_rev+c_rev}, 调整数: {a_adj+b_adj+c_adj}, 幅度: {total_mag}")
    
    if issues:
        print(f"  ⚠️ 问题:")
        for issue in issues[:10]:
            print(f"    {issue}")
    else:
        print(f"  ✅ 无约束违规")
    
    if fc == 0:
        print(f"  ✅ 冲突消解正确")
    else:
        print(f"  ❌ 仍有{fc}对冲突!")
    
    if a_rev == 0:
        print(f"  ✅ A撤销=0")
    else:
        print(f"  ⚠️ A撤销={a_rev}（可能因A-A冲突对）")
    
    results[name] = {
        "conflicts": fc,
        "table1": {"A": {"保留": a_keep, "调整": a_adj, "撤销": a_rev},
                   "B": {"保留": b_keep, "调整": b_adj, "撤销": b_rev},
                   "C": {"保留": c_keep, "调整": c_adj, "撤销": c_rev}},
        "total_rev": a_rev+b_rev+c_rev,
        "total_adj": a_adj+b_adj+c_adj,
        "total_mag": total_mag,
        "issues": issues
    }

# 汇总
print(f"\n{'='*60}")
print("汇总对比")
print(f"{'='*60}")
print(f"{'方案':<15} {'冲突':>4} {'撤销':>4} {'A撤':>4} {'调整':>4} {'幅度':>6}")
print("-" * 45)
for name, r in results.items():
    print(f"{name:<15} {r['conflicts']:>4} {r['total_rev']:>4} {r['table1']['A']['撤销']:>4} {r['total_adj']:>4} {r['total_mag']:>6}")

# 写审查报告
os.makedirs(os.path.join(PROJECT_ROOT, "docs", "check", "02"), exist_ok=True)
for name, r in results.items():
    report = f"# {name} 审查报告\n\n"
    report += f"结论: {'通过' if r['conflicts']==0 and not r['issues'] else '不通过'}\n\n"
    report += f"## 独立冲突检测\n- 冲突数: {r['conflicts']}\n\n"
    report += f"## 表1\n"
    for cat in ['A', 'B', 'C']:
        report += f"- {cat}: 保留={r['table1'][cat]['保留']}, 调整={r['table1'][cat]['调整']}, 撤销={r['table1'][cat]['撤销']}\n"
    report += f"\n## 目标值\n"
    report += f"- 撤销总数: {r['total_rev']}\n"
    report += f"- A撤销: {r['table1']['A']['撤销']}\n"
    report += f"- 调整数: {r['total_adj']}\n"
    report += f"- 总幅度: {r['total_mag']}\n"
    if r['issues']:
        report += f"\n## 问题\n"
        for issue in r['issues']:
            report += f"- {issue}\n"
    else:
        report += f"\n## 约束审计\n- ✅ 无违规\n"
    
    safe_name = name.replace("/", "_")
    report_path = os.path.join(PROJECT_ROOT, "docs", "check", "02", f"审查报告_{safe_name}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  审查报告: {report_path}")
