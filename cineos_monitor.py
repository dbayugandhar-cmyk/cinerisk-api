"""
CINEOS Railway Monitor — add to crontab:
*/5 * * * * cd ~/Desktop/cinerisk && python3 cineos_monitor.py >> logs/monitor.log 2>&1
"""
import urllib.request, json, os
from datetime import datetime, timezone, timedelta

API='https://cinerisk-api-production.up.railway.app'
KEY='cineos_internal_2026'
IST=timezone(timedelta(hours=5,minutes=30))

def now():
    return datetime.now(IST).strftime('%Y-%m-%d %H:%M IST')

def chk(path,key=None):
    import time
    t=time.time()
    try:
        req=urllib.request.Request(API+path)
        if key: req.add_header('X-API-Key',key)
        r=json.loads(urllib.request.urlopen(req,timeout=12).read())
        return True,round((time.time()-t)*1000),r
    except Exception as e:
        return False,-1,str(e)

def load_st():
    try: return json.load(open('logs/monitor_status.json'))
    except: return {'was_down':False,'checks':0}

def save_st(s):
    os.makedirs('logs',exist_ok=True)
    json.dump(s,open('logs/monitor_status.json','w'),indent=2)

def alert(msg):
    os.makedirs('logs',exist_ok=True)
    with open('logs/monitor_alerts.log','a') as f:
        f.write(f'[{now()}] {msg}\n')
    print(f'ALERT: {msg}')

def main():
    st=load_st()
    st['checks']=st.get('checks',0)+1
    checks=[
        ('/health',None,lambda r:r.get('status')=='ok' and r.get('alerts',0)>100),
        ('/api/v1/demo?q=917455697977',None,lambda r:'risk_level' in r),
        ('/api/v1/graph',None,lambda r:r.get('total_nodes',0)>10),
    ]
    results=[(p,*chk(p,k),v) for p,k,v in checks]
    all_ok=all(ok for _,ok,_,_,_ in results)
    ts=now()
    print(f'[{ts}] Check #{st["checks"]} — {"ALL OK" if all_ok else "FAILURE"}')
    for p,ok,ms,r,_ in results:
        alerts_val=r.get('alerts','') if isinstance(r,dict) else ''
        print(f'  {"OK" if ok else "FAIL"} {p.split("?")[0]:35} {ms}ms {alerts_val}')
    if not all_ok:
        if not st.get('was_down'):
            st['was_down']=True; st['down_since']=ts
            alert(f'CINEOS DOWN — {ts}')
    else:
        if st.get('was_down'):
            alert(f'CINEOS RECOVERED — {ts}')
        st['was_down']=False; st['last_ok']=ts
    save_st(st)

if __name__=='__main__':
    main()
