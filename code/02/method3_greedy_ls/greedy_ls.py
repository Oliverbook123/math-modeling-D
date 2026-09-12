# -*- coding: utf-8 -*-
"""
问题 2 方案 3：贪心构造（与方案1同逻辑，动作选择按幅度递增）
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
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "code", "output", "02", "method3_greedy_ls")
CATEGORY_RANK = {"A": 0, "B": 1, "C": 2}

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

def count_conflicts_active(plans, decisions):
    active=[]
    for i,(at,df,dt) in enumerate(decisions):
        if at=='revoke': continue
        active.append(make_shifted_plan(plans[i], df, dt))
    c=0
    for i in range(len(active)):
        for j in range(i+1, len(active)):
            if plans_conflict(active[i], active[j]): c+=1
    return c

def main():
    plans = load_plans(get_data_path())
    n = len(plans)
    print(f"加载 {n} 个计划")

    # 重算冲突
    cc=0
    for i in range(n):
        for j in range(i+1, n):
            if plans_conflict(plans[i], plans[j]): cc+=1
    assert cc == EXPECTED_CONFLICTS

    # 冲突度数
    conflict_degree = [0]*n
    for i in range(n):
        for j in range(i+1, n):
            if plans_conflict(plans[i], plans[j]):
                conflict_degree[i]+=1; conflict_degree[j]+=1

    # 排序：A<B<C, 冲突度降序, 编号
    order = sorted(range(n), key=lambda i: (CATEGORY_RANK[plans[i].category], -conflict_degree[i], plans[i].id))

    # 贪心入座
    decisions = [None]*n
    kept = []
    for idx in order:
        p = plans[idx]
        actions = get_actions_for_plan(p)
        # 按幅度递增选择（与方案1一致）
        sorted_actions = sorted([a for a in actions if a[0]!='revoke'],
                                key=lambda a: (abs(a[1])+abs(a[2]), 0 if a[0]=='freq' else 1, a[1], a[2]))
        sorted_actions.append(('revoke', 0, 0))
        found = False
        for at, df, dt in sorted_actions:
            np = make_shifted_plan(p, df, dt)
            conflict = False
            for k, kp in kept:
                if plans_conflict(np, kp):
                    conflict = True; break
            if not conflict:
                decisions[idx] = (at, df, dt)
                if at != 'keep': kept.append((idx, np))
                else: kept.append((idx, np))
                found = True; break
        if not found:
            decisions[idx] = ('revoke', 0, 0)

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
    assert fc == 0
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

    summary={"方法":"方案3_贪心构造(纯贪心)","表1":{"A":{"保留":a_keep,"调整":a_adj,"撤销":a_rev},"B":{"保留":b_keep,"调整":b_adj,"撤销":b_rev},"C":{"保留":c_keep,"调整":c_adj,"撤销":c_rev}},"目标函数":{"第1层_撤销总数":a_rev+b_rev+c_rev,"第2层_A撤销":a_rev,"第2层_B撤销":b_rev,"第2层_C撤销":c_rev,"第3层_调整数":a_adj+b_adj+c_adj,"第4层_总调整幅度":total_mag},"冲突对数_原始":cc,"最终冲突数":fc,"自检":{"最终冲突数":fc,"每计划最多动1参数":True,"表1总数20_40_90":True}}
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
    wb.save(os.path.join(OUTPUT_DIR,"result2_greedy_ls.xlsx"))
    print(f"输出: {OUTPUT_DIR}")

if __name__=="__main__": main()
