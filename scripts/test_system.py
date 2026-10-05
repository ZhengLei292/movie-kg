"""Integration acceptance tests against raw CSV, live Neo4j, and the API."""
import csv
import json
import random
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.graph import GraphStore
from scripts.import_graph import run_import

def run():
    checks=[]
    def check(name, condition):
        assert condition,name
        checks.append(name)
        print('PASS',name,flush=True)
    base='http://127.0.0.1:18080'
    def get(path,**params):
        r=requests.get(base+path,params=params,timeout=30)
        r.raise_for_status()
        return r.json()
    raw={}
    with (ROOT/'data/raw/movies.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            raw[int(row['movieId'])]={'title':row['title'].strip(),'genres':set(row['genres'].split('|'))-{'(no genres listed)',''},'tags':set()}
    with (ROOT/'data/raw/tags.csv').open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            mid=int(row['movieId'])
            tag=' '.join(unicodedata.normalize('NFKC',row['tag']).split()).casefold()
            if mid in raw and tag:
                raw[mid]['tags'].add(tag)
    store=GraphStore()
    ds=store.dataset()
    rows=store.run('''MATCH (m:MovieGraphMovie {dataset:$ds}) RETURN m.movieId AS id, m.title AS title,
        [(m)-[:IN_GENRE]->(g)|g.name] AS genres, [(m)-[:HAS_TAG]->(t)|t.name] AS tags''',ds=ds)
    check('all_movie_ids_match_raw_csv',{r['id'] for r in rows}==set(raw))
    check('all_9742_movies_title_genre_tag_relations_match_raw_csv',all(
        r['title']==raw[r['id']]['title'] and set(r['genres'])==raw[r['id']]['genres'] and set(r['tags'])==raw[r['id']]['tags'] for r in rows))
    audit=[]
    sample=random.Random(20261002).sample(sorted(raw),20)
    for mid in sample:
        m=get(f'/api/movies/{mid}')
        check(f'audit_movie_{mid}',set(m['genres'])==raw[mid]['genres'] and set(m['tags'])==raw[mid]['tags'] and m['title']==raw[mid]['title'])
        audit.append({'movieId':mid,'title':m['title'],'genres':m['genres'],'tags':m['tags'],'result':'PASS'})
    test_ids=list(dict.fromkeys([1,2571,260]+sample))
    start=time.perf_counter()
    for mid in test_ids:
        expected=[]
        for other,val in raw.items():
            if other==mid: continue
            gs=raw[mid]['genres']&val['genres']; ts=raw[mid]['tags']&val['tags']
            if gs or ts:
                expected.append((other,len(gs)+len(ts),gs,ts))
        expected.sort(key=lambda x:(-x[1],x[0]))
        rec=get(f'/api/movies/{mid}/recommendations')['items']
        check(f'recommendation_ranking_and_evidence_{mid}',
            [(r['movieId'],r['score'],set(r['sharedGenres']),set(r['sharedTags'])) for r in rec]==expected[:5])
    no_tags=next(mid for mid,m in raw.items() if not m['tags'] and m['genres'])
    no_features=next(mid for mid,m in raw.items() if not m['tags'] and not m['genres'])
    check('no_tags_uses_genres_only',all(not r['sharedTags'] and r['score']==len(r['sharedGenres']) for r in get(f'/api/movies/{no_tags}/recommendations')['items']))
    check('no_features_returns_empty',get(f'/api/movies/{no_features}/recommendations')['items']==[])
    by_title=defaultdict(list)
    for mid,m in raw.items(): by_title[m['title']].append(mid)
    duplicates={t:ids for t,ids in by_title.items() if len(ids)>1}
    for title,ids in duplicates.items():
        found=get('/api/movies',q=title)['items']
        check(f'duplicate_title_preserves_ids_{ids}',set(ids)<={m['movieId'] for m in found})
    check('case_insensitive_partial_search',get('/api/movies',q='tOy sToRy')['total']>=3)
    check('no_search_results',get('/api/movies',q='qzxv_no_such_movie_991')['items']==[])
    check('injection_is_literal_text',get('/api/movies',q="' MATCH (n) DETACH DELETE n //")['total']==0)
    check('invalid_movie_404',requests.get(base+'/api/movies/-1',timeout=10).status_code==404)
    check('limit_validation_422',requests.get(base+'/api/movies/1/recommendations?limit=6',timeout=10).status_code==422)
    check('invalid_feature_kind_422',requests.get(base+'/api/features/invalid?name=x',timeout=10).status_code==422)
    check('negative_offset_422',requests.get(base+'/api/movies?offset=-1',timeout=10).status_code==422)
    pages=[get('/api/movies',q='star',offset=i*10,limit=10) for i in range(2)]
    check('search_pagination_no_overlap',not ({m['movieId'] for m in pages[0]['items']}&{m['movieId'] for m in pages[1]['items']}))
    graph=get('/api/movies/1/graph',limit=6)
    check('graph_neighbor_limit',sum(n['kind']=='movie' for n in graph['nodes'])<=6)
    nodes={n['id']:n for n in graph['nodes']}
    for edge in graph['edges']:
        a,b=nodes[edge['source']],nodes[edge['target']]
        assert b['label'] in raw[a['movieId']]['genres' if edge['relation']=='IN_GENRE' else 'tags']
    check('every_displayed_edge_exists_in_raw',True)
    relation=get('/api/features/genre',name='Animation',limit=100)
    check('feature_click_returns_real_neighbors',all('Animation' in raw[m['movieId']]['genres'] for m in relation['items']))
    for tag in raw[1]['tags']:
        relation=get('/api/features/tag',name=tag,limit=100)
        check(f'tag_neighbors_{tag}',all(tag in raw[m['movieId']]['tags'] for m in relation['items']))
    before=store.stats()
    run_import()
    check('repeated_import_is_idempotent',before==store.stats())
    store.close()
    report={'timestamp':datetime.now().isoformat(),'status':'PASS','checks':checks,'count':len(checks),
            'auditedAllMovies':len(raw),'sampleSeed':20261002,'sample':audit,
            'noTagsExample':no_tags,'noFeaturesExample':no_features,'duplicateTitles':duplicates,
            'recommendationCases':len(test_ids),'durationSeconds':round(time.perf_counter()-start,2)}
    (ROOT/'docs/test_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text='# 后端与数据验收记录\n\n执行时间：'+report['timestamp']+'\n\n'
    text+=f'结果：**PASS**，{len(checks)} 项检查通过。对全部 {len(raw):,} 部电影逐一比对原始 CSV 与 Neo4j 类型、标签关系。\n\n'
    text+='另外固定随机种子 20261002 抽查 20 部电影，逐项比对 API。推荐检查使用独立 Python 集合运算计算全量候选和排序，核对真实接口 Top 5。\n\n'
    text+='| movieId | 电影 | 类型数 | 标签数 | 结果 |\n|---|---|---:|---:|---|\n'
    text+=''.join(f'| {r["movieId"]} | {r["title"]} | {len(r["genres"])} | {len(r["tags"])} | PASS |\n' for r in audit)
    text+='\n## 检查项目\n\n'+''.join(f'- PASS `{name}`\n' for name in checks)
    text+='\n本记录检验功能正确性，不代表完成用户推荐满意度或预测准确率实验。\n'
    (ROOT/'docs/测试记录.md').write_text(text,encoding='utf-8')
    print(f'ALL {len(checks)} CHECKS PASSED')

if __name__=='__main__': run()

