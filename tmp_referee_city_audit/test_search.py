import json, requests, time
from pathlib import Path
URL='https://visu.floorball.fr/api/public_global_search.php'
HEADERS={'Accept':'application/json','Content-Type':'application/json; charset=UTF-8'}
names=['Georges Thomé','Simon Bénard','Manaure Russo-Mendoza','David Alin','Robinn Swinnen-Willems']
out=[]
for name in names:
    t=time.time()
    try:
        r=requests.post(URL,json={'idseason':23,'search_type':'player','text':name},headers=HEADERS,timeout=60)
        r.raise_for_status()
        out.append({'name':name,'seconds':round(time.time()-t,2),'data':r.json()})
    except Exception as e:
        out.append({'name':name,'seconds':round(time.time()-t,2),'error':repr(e)})
Path('search-test-output').mkdir(exist_ok=True)
Path('search-test-output/results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'name':x['name'],'seconds':x['seconds'],'error':x.get('error'),'type':type(x.get('data')).__name__,'len':len(x.get('data') or []) if isinstance(x.get('data'),list) else None} for x in out],ensure_ascii=False))
