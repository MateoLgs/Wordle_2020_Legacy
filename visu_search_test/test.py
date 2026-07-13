import json, requests, time
from pathlib import Path
URL='https://visu.floorball.fr/api/public_global_search.php'
HEADERS={'Accept':'application/json','Content-Type':'application/json; charset=UTF-8'}
queries=[]
for season in [23,22]:
    for st in ['player','players','person','individual']:
        for text in ['David','Alin','David Alin','']:
            queries.append({'idseason':season,'search_type':st,'text':text})
queries += [
 {'idseason':23,'search_type':'team','text':'Caen'},
 {'idseason':23,'search_type':'team','text':''},
]
out=[]
for q in queries:
    t=time.time()
    try:
        r=requests.post(URL,json=q,headers=HEADERS,timeout=30); r.raise_for_status(); data=r.json()
        out.append({'query':q,'seconds':round(time.time()-t,2),'data':data})
    except Exception as e:
        out.append({'query':q,'seconds':round(time.time()-t,2),'error':repr(e)})
Path('search-test-output').mkdir(exist_ok=True)
Path('search-test-output/results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'q':x['query'],'sec':x['seconds'],'type':type(x.get('data')).__name__,'len':len(x.get('data') or []) if isinstance(x.get('data'),list) else None,'error':x.get('error')} for x in out],ensure_ascii=False))
