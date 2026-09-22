import json,glob,re,sys
N={'t1':5,'t2':5,'t3':1,'t4':5,'t5':5,'t6':5,'t7':5,'t8':5}
def row(f):
    d=json.load(open(f)); g=d['grade']; t=d['task']; h=g['hidden']
    fail=0 if h=='OK' else sum(int(x) for x in re.findall(r'=(\d+)',h)) or N[t]
    retr=sum((x.get('api_retries') or 0) for x in d['turns'])
    return d, N[t]-fail, retr
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv)>1 else 'results/c*-r1.json')):
    d,p,r=row(f); g=d['grade']
    print(f"{d['id']:12} pass={p}/{N[d['task']]} wall={d['wall_total']/60:5.1f}m cost=${d['cost_usd']:6.2f} asks={d['user_replies']} retries={r} errs={d['errors']} diff={g['diff_stat']} commits={g.get('commits_made')}")
