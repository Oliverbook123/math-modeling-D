# -*- coding: utf-8 -*-
"""
问题 2 方案 2：整数规划 ILP 冲突消解（简化版）

运行方式：
    UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/" uv run --with openpyxl --with pulp python code/02/method2_ilp/main.py

简化策略：
  - A类全部保留不动（其他方案均得A撤销=0，固定无风险）
  - 只对B/C类建ILP，动作空间：保留/频段平移/时间平移/撤销
  - 候选冲突对窗口收紧，减少约束数量
"""

import csv, json, os, sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
CODE01_DIR = os.path.join(PROJECT_ROOT, "code", "01")
if CODE01_DIR not in sys.path:
    sys.path.insert(0, CODE01_DIR)

from common.data_loader import Plan, load_plans, get_data_path
import openpyxl

MAX_FREQ_SHIFT = 10
MAX_TIME_SHIFT = 5
FREQ_BAND = (0, 100)
EXPECTED_CONFLICTS = 237
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "02", "method2_ilp")


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


def get_actions_for_plan(plan):
    actions = [('keep', 0, 0)]
    for df in range(-MAX_FREQ_SHIFT, MAX_FREQ_SHIFT+1):
        if df == 0: continue
        if plan.freq_start+df >= FREQ_BAND[0] and plan.freq_end+df <= FREQ_BAND[1]:
            actions.append(('freq', df, 0))
    for dt in range(-MAX_TIME_SHIFT, MAX_TIME_SHIFT+1):
        if dt == 0: continue
        if plan.time_start+dt >= 0:
            actions.append(('time', 0, dt))
    actions.append(('revoke', 0, 0))
    return actions


def count_conflicts_active(plans, decisions):
    active = []
    for i, (at, df, dt) in enumerate(decisions):
        if at == 'revoke': continue
        active.append(make_shifted_plan(plans[i], df, dt))
    c = 0
    for i in range(len(active)):
        for j in range(i+1, len(active)):
            if plans_conflict(active[i], active[j]):
                c += 1
    return c


def score_solution(plans, decisions):
    a_rev=b_rev=c_rev=0; adj=total_mag=0
    for i,(at,df,dt) in enumerate(decisions):
        cat=plans[i].category
        if at=='revoke':
            if cat=='A':a_rev+=1
            elif cat=='B':b_rev+=1
            else:c_rev+=1
        elif at!='keep':
            adj+=1; total_mag+=abs(df)+abs(dt)
    return (a_rev+b_rev+c_rev, a_rev, b_rev, c_rev, adj, total_mag)


def main():
    import pulp

    plans = load_plans(get_data_path())
    n = len(plans)
    print(f"加载 {n} 个计划")

    # 验证冲突
    cc = 0
    for i in range(n):
        for j in range(i+1, n):
            if plans_conflict(plans[i], plans[j]):
                cc += 1
    assert cc == EXPECTED_CONFLICTS

    # 分离A类（固定保留）和BC类（ILP优化）
    a_indices = [i for i in range(n) if plans[i].category == 'A']
    bc_indices = [i for i in range(n) if plans[i].category in ('B', 'C')]
    print(f"A类: {len(a_indices)} (固定保留), B/C类: {len(bc_indices)} (ILP优化)")

    # A类固定保留
    decisions = [('keep', 0, 0)] * n

    # 为BC类生成动作
    bc_actions = {}
    for i in bc_indices:
        bc_actions[i] = get_actions_for_plan(plans[i])
    print(f"BC类平均动作数: {sum(len(a) for a in bc_actions.values())/len(bc_indices):.1f}")

    # 候选冲突对（只考虑BC类之间，或BC类与A类的冲突）
    # BC类之间：窗口剪枝（放宽：频段距离≤宽度和+20，时间距离≤宽度和+10）
    candidate_pairs = []
    for ii in range(len(bc_indices)):
        for jj in range(ii+1, len(bc_indices)):
            i, j = bc_indices[ii], bc_indices[jj]
            pi, pj = plans[i], plans[j]
            w1 = pi.freq_end - pi.freq_start
            w2 = pj.freq_end - pj.freq_start
            # 频段窗口
            if pi.freq_start - MAX_FREQ_SHIFT >= pj.freq_end + MAX_FREQ_SHIFT + w1 + w2:
                continue
            if pj.freq_start - MAX_FREQ_SHIFT >= pi.freq_end + MAX_FREQ_SHIFT + w1 + w2:
                continue
            # 时间窗口
            ts1, te1 = min(s for s,e in pi.time_instances()), max(e for s,e in pi.time_instances())
            ts2, te2 = min(s for s,e in pj.time_instances()), max(e for s,e in pj.time_instances())
            if ts1 - MAX_TIME_SHIFT >= te2 + MAX_TIME_SHIFT + 10:
                continue
            if ts2 - MAX_TIME_SHIFT >= te1 + MAX_TIME_SHIFT + 10:
                continue
            candidate_pairs.append((i, j))

    # BC类与A类的冲突（A固定保留，BC的动作必须避开A）
    bc_a_conflicts = {}  # bc_idx -> 与哪些A冲突
    for i in bc_indices:
        conflicting_a = []
        for j in a_indices:
            if plans_conflict(plans[i], plans[j]):
                conflicting_a.append(j)
        if conflicting_a:
            bc_a_conflicts[i] = conflicting_a

    print(f"BC类间候选对: {len(candidate_pairs)}, BC类与A类冲突: {len(bc_a_conflicts)}")

    # 预计算不兼容动作对
    print("预计算不兼容动作对...")
    incompatible = {}
    for (i, j) in candidate_pairs:
        acts_i = bc_actions[i]
        acts_j = bc_actions[j]
        bad = []
        for ai, (at_i, df_i, dt_i) in enumerate(acts_i):
            if at_i == 'revoke': continue
            pi_s = make_shifted_plan(plans[i], df_i, dt_i)
            for aj, (at_j, df_j, dt_j) in enumerate(acts_j):
                if at_j == 'revoke': continue
                pj_s = make_shifted_plan(plans[j], df_j, dt_j)
                if plans_conflict(pi_s, pj_s):
                    bad.append((ai, aj))
        if bad:
            incompatible[(i, j)] = bad
    print(f"有不兼容动作的对数: {len(incompatible)}")

    # 预计算BC类与A类不兼容动作（BC的动作不能与固定的A冲突）
    bc_a_incompatible = {}  # bc_idx -> [不兼容的动作索引]
    for i, conflicting_a in bc_a_conflicts.items():
        bad_actions = []
        for ai, (at_i, df_i, dt_i) in enumerate(bc_actions[i]):
            if at_i == 'revoke': continue
            pi_s = make_shifted_plan(plans[i], df_i, dt_i)
            for j in conflicting_a:
                # A类固定原位
                if plans_conflict(pi_s, plans[j]):
                    bad_actions.append(ai)
                    break
        if bad_actions:
            bc_a_incompatible[i] = bad_actions
    print(f"与A类冲突的BC动作数: {sum(len(v) for v in bc_a_incompatible.values())}")

    # 建ILP模型
    print("建ILP模型...")
    prob = pulp.LpProblem("ConflictResolution", pulp.LpMinimize)

    # 变量
    y = {}
    for i in bc_indices:
        for a_idx in range(len(bc_actions[i])):
            y[i, a_idx] = pulp.LpVariable(f"y_{i}_{a_idx}", cat=pulp.LpBinary)

    # 约束1：每个BC类恰好选一个动作
    for i in bc_indices:
        prob += pulp.lpSum(y[i, a] for a in range(len(bc_actions[i]))) == 1

    # 约束2：BC类间不兼容动作对
    for (i, j), bad in incompatible.items():
        for ai, aj in bad:
            prob += y[i, ai] + y[j, aj] <= 1

    # 约束3：BC类动作不能与固定的A类冲突
    for i, bad_actions in bc_a_incompatible.items():
        for ai in bad_actions:
            prob += y[i, ai] == 0

    # 目标：最小化加权撤销（A=10^6, B=10^3, C=1）
    obj = 0
    for i in bc_indices:
        cat = plans[i].category
        weight = {'B': 10**3, 'C': 1}[cat]
        revoke_idx = len(bc_actions[i]) - 1
        obj += weight * y[i, revoke_idx]
    prob += obj

    # 求解
    print("求解中...")
    solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=120)
    status = prob.solve(solver)
    status_str = pulp.LpStatus[status]
    print(f"求解状态: {status_str}, 目标值: {pulp.value(prob.objective)}")

    # 提取解
    for i in bc_indices:
        for a_idx in range(len(bc_actions[i])):
            if pulp.value(y[i, a_idx]) and pulp.value(y[i, a_idx]) > 0.5:
                decisions[i] = bc_actions[i][a_idx]
                break

    # 贪心修复剩余冲突
    fc = count_conflicts_active(plans, decisions)
    if fc > 0:
        print(f"ILP解有{fc}对冲突，贪心修复中...")
        # 找出冲突的活跃计划
        active_indices = [i for i in range(n) if decisions[i][0] != 'revoke']
        for i in active_indices:
            for j in active_indices:
                if j <= i: continue
                pi = make_shifted_plan(plans[i], decisions[i][1], decisions[i][2])
                pj = make_shifted_plan(plans[j], decisions[j][1], decisions[j][2])
                if plans_conflict(pi, pj):
                    # 撤销优先级低的
                    ri = {'A': 0, 'B': 1, 'C': 2}[plans[i].category]
                    rj = {'A': 0, 'B': 1, 'C': 2}[plans[j].category]
                    victim = i if ri >= rj else j
                    decisions[victim] = ('revoke', 0, 0)
        fc = count_conflicts_active(plans, decisions)
        print(f"修复后冲突: {fc}")

    # 统计
    a_keep=sum(1 for i,d in enumerate(decisions) if d[0]=='keep' and plans[i].category=='A')
    a_adj=sum(1 for i,d in enumerate(decisions) if d[0] not in ('keep','revoke') and plans[i].category=='A')
    a_rev=sum(1 for i,d in enumerate(decisions) if d[0]=='revoke' and plans[i].category=='A')
    b_keep=sum(1 for i,d in enumerate(decisions) if d[0]=='keep' and plans[i].category=='B')
    b_adj=sum(1 for i,d in enumerate(decisions) if d[0] not in ('keep','revoke') and plans[i].category=='B')
    b_rev=sum(1 for i,d in enumerate(decisions) if d[0]=='revoke' and plans[i].category=='B')
    c_keep=sum(1 for i,d in enumerate(decisions) if d[0]=='keep' and plans[i].category=='C')
    c_adj=sum(1 for i,d in enumerate(decisions) if d[0] not in ('keep','revoke') and plans[i].category=='C')
    c_rev=sum(1 for i,d in enumerate(decisions) if d[0]=='revoke' and plans[i].category=='C')
    total_mag=sum(abs(d[1])+abs(d[2]) for d in decisions if d[0] not in ('keep','revoke'))

    fc = count_conflicts_active(plans, decisions)
    score = score_solution(plans, decisions)
    print(f"得分: {score}, 冲突: {fc}")
    print(f"表1: A({a_keep}/{a_adj}/{a_rev}) B({b_keep}/{b_adj}/{b_rev}) C({c_keep}/{c_adj}/{c_rev})")
    assert fc == 0, f"冲突数: {fc}"
    assert a_keep+a_adj+a_rev==20 and b_keep+b_adj+b_rev==40 and c_keep+c_adj+c_rev==90

    # 输出
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(OUTPUT_DIR, "result.csv"), 'w', newline='', encoding='utf-8-sig') as f:
        w=csv.writer(f)
        w.writerow(['装备编号','类别','决策','频段平移','时间平移','调整后频段区间','调整后时间区间'])
        for i,(at,df,dt) in enumerate(decisions):
            p=plans[i]
            if at=='revoke': w.writerow([p.id,p.category,'撤销','','','',''])
            elif at=='keep': w.writerow([p.id,p.category,'保留',0,0,f'[{p.freq_start},{p.freq_end})',f'[{p.time_start},{p.time_end})'])
            else:
                np=make_shifted_plan(p,df,dt)
                w.writerow([p.id,p.category,'调频段' if at=='freq' else '调时间',df,dt,f'[{np.freq_start},{np.freq_end})',f'[{np.time_start},{np.time_end})'])

    summary={"方法":"方案2_整数规划ILP","表1":{"A":{"保留":a_keep,"调整":a_adj,"撤销":a_rev},"B":{"保留":b_keep,"调整":b_adj,"撤销":b_rev},"C":{"保留":c_keep,"调整":c_adj,"撤销":c_rev}},"目标函数":{"第1层_撤销总数":a_rev+b_rev+c_rev,"第2层_A撤销":a_rev,"第2层_B撤销":b_rev,"第2层_C撤销":c_rev,"第3层_调整数":a_adj+b_adj+c_adj,"第4层_总调整幅度":total_mag},"求解状态":status_str,"冲突对数_原始":cc,"最终冲突数":fc,"自检":{"最终冲突数":fc,"每计划最多动1参数":True,"表1总数20_40_90":True}}
    with open(os.path.join(OUTPUT_DIR,"summary.json"),'w',encoding='utf-8') as f: json.dump(summary,f,ensure_ascii=False,indent=2)

    wb=openpyxl.Workbook(); ws=wb.active; ws.title="Sheet1"
    ws.append(['用频装备编号','调整后频段区间','调整后时间区间','是否撤销用频计划'])
    for i,(at,df,dt) in enumerate(decisions):
        p=plans[i]
        if at=='revoke': ws.append([p.id,None,None,'是'])
        elif at!='keep':
            np=make_shifted_plan(p,df,dt)
            if at=='freq': ws.append([p.id,f'[{np.freq_start},{np.freq_end})',None,None])
            else: ws.append([p.id,None,f'[{np.time_start},{np.time_end})',None])
    wb.save(os.path.join(OUTPUT_DIR,"result2_ilp.xlsx"))
    print(f"输出: {OUTPUT_DIR}")

if __name__=="__main__": main()
