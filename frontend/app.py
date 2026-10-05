import html
import json
import os
from pathlib import Path
import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
API = os.getenv('MOVIEGRAPH_API', 'http://127.0.0.1:18080')
graph_component = components.declare_component('moviegraph', path=str(ROOT/'frontend/graph_component'))

st.set_page_config(page_title='MovieGraph · 电影知识图谱', page_icon='◉', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:2.2rem;max-width:1480px;padding-bottom:2rem}
div[data-testid="stToolbar"]{display:none}
header[data-testid="stHeader"]{background:transparent}
[data-testid="stSidebar"]{background:#e9eee7;border-right:1px solid #d9e0d7}
[data-testid="stSidebar"] .block-container{padding-top:2rem}
h1,h2,h3{letter-spacing:-.045em;font-weight:650!important}
h1{font-size:2.65rem!important;line-height:1.15!important}
h3{font-size:1.35rem!important}
.eyebrow{font-size:11px;letter-spacing:.19em;color:#517466;font-weight:700;margin-bottom:12px}
.hero-note{font-size:15px;color:#63746b;margin:10px 0 24px;line-height:1.8}
.brand{font-size:29px;font-weight:750;letter-spacing:-1.5px;margin-bottom:2px}
.brand span{color:#217561}
.sidebar-note{color:#6f7d73;font-size:12px;line-height:1.8;margin-bottom:25px}
.movie-meta{font-family:monospace;font-size:12px;color:#76877b;letter-spacing:.06em;margin:10px 0}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 18px}
.chip{font-size:12px;padding:5px 11px;border-radius:5px;background:#e3eee5;color:#276146;border:1px solid #d3e3d6}
.chip.tag{background:#f3ebde;border-color:#e8dcc7;color:#8b6835}
.score{font-size:24px;font-weight:700;color:#217561;text-align:right}
.reason{font-size:13px;color:#66756a;line-height:1.7;margin:8px 0}
.rec-title{font-size:17px;font-weight:650;line-height:1.4}
.legend{font-size:12px;color:#687a6d;margin-bottom:12px}
.footer{font-size:11px;color:#819085;margin-top:32px;padding-top:15px;border-top:1px solid #dce3d9}
[data-testid="stMetric"]{border-top:1px solid #d5ded3;padding-top:12px}
[data-testid="stMetricValue"]{font-size:1.85rem}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:12px}
.stButton>button{border-radius:7px}
[data-testid="stSidebar"] .stButton>button{text-align:left;justify-content:flex-start;font-size:13px}
</style>''', unsafe_allow_html=True)

def api(path, allow_missing=False, **params):
    try:
        r = requests.get(API + path, params=params, timeout=20)
        if allow_missing and r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        st.error('暂时无法读取图数据库。请运行 start.bat，或查看项目 logs 文件夹后重试。')
        if st.button('重新连接'):
            st.rerun()
        st.stop()

def choose(mid):
    st.session_state.movie_id = int(mid)
    st.session_state.pop('feature', None)
    st.query_params['movie'] = str(mid)

def chips(values, tag=False):
    if values:
        st.markdown('<div class="chips">' + ''.join('<span class="chip'+(' tag' if tag else '')+'">'+html.escape(x)+'</span>' for x in values) + '</div>', unsafe_allow_html=True)

if 'movie_id' not in st.session_state:
    try:
        st.session_state.movie_id = int(st.query_params.get('movie', '1'))
    except ValueError:
        st.session_state.movie_id = 1

with st.sidebar:
    st.markdown('<div class="brand">Movie<span>Graph</span></div><div class="sidebar-note">电影知识图谱与可解释推荐系统</div>',unsafe_allow_html=True)
    q = st.text_input('搜索电影', placeholder='输入英文片名，如 Toy Story', key='search')
    st.caption('支持部分片名 · 使用 MovieLens 原始标题')
    if st.session_state.get('_last_query') != q:
        st.session_state.page = 0
        st.session_state._last_query = q
    page = st.session_state.get('page',0)
    results = api('/api/movies',q=q,offset=page*10,limit=10)
    st.markdown(f'**{results["total"]:,} 部匹配电影**')
    if not results['items']:
        st.info('没有找到电影，试试更短的英文名称。')
    for item in results['items']:
        st.button(f'{item["title"]}  ·  #{item["movieId"]}',key=f'search-{item["movieId"]}',
            use_container_width=True, type='primary' if item['movieId']==st.session_state.movie_id else 'secondary',
            on_click=choose,args=(item['movieId'],))
    a,b = st.columns(2)
    if a.button('上一页',disabled=page==0,use_container_width=True):
        st.session_state.page=page-1
        st.rerun()
    if b.button('下一页',disabled=(page+1)*10>=results['total'],use_container_width=True):
        st.session_state.page=page+1
        st.rerun()
    st.caption(f'第 {page+1} / {max(1,(results["total"]+9)//10)} 页')
    st.divider()
    st.markdown('**快速探索**')
    for mid,title in [(1,'Toy Story'),(2571,'The Matrix'),(260,'Star Wars')]:
        st.button(title,key=f'quick-{mid}',on_click=choose,args=(mid,),use_container_width=True)
    st.markdown('<div class="sidebar-note">数据集：MovieLens Latest Small<br>图数据库：Neo4j<br>查询、探索、理解推荐理由</div>',unsafe_allow_html=True)

stats = api('/api/stats')
st.markdown('<div class="eyebrow">CONNECTED STORIES / 电影关系探索</div>',unsafe_allow_html=True)
st.title('每一次推荐，都有迹可循。')
st.markdown('<div class="hero-note">从一部电影出发，沿着类型和标签发现相似作品。点击图谱节点，继续探索电影之间的联系。</div>',unsafe_allow_html=True)
cols=st.columns(4)
for col,key,label in zip(cols,['movies','genres','tags','relations'],['电影实体','类型','独立标签','图谱关系']):
    col.metric(label,f'{stats[key]:,}')

# Distinguish a missing deep-link from a database outage.
movie = api(f'/api/movies/{st.session_state.movie_id}',allow_missing=True)
if movie is None:
    st.warning('链接中的电影不存在，请在左侧选择电影。')
    st.stop()
st.divider()
main,right=st.columns([1.8,1],gap='large')
with main:
    st.markdown(f'<div class="movie-meta">MOVIE #{movie["movieId"]} / {movie["year"] or "年份未知"}</div>',unsafe_allow_html=True)
    st.header(movie['title'])
    chips(movie['genres'])
    if not movie['genres']:
        st.caption('数据集中未列出类型')
    tab1,tab2,tab3=st.tabs(['关系图谱','电影标签','数据概览'])
    with tab1:
        st.markdown('<div class="legend">● 深绿：当前电影　● 蓝：关联电影　● 绿：类型　● 金：标签</div>',unsafe_allow_html=True)
        limit=st.slider('关联电影数量',0,12,6)
        graph=api(f'/api/movies/{movie["movieId"]}/graph',limit=limit)
        event=graph_component(graph=graph,key=f'graph-{movie["movieId"]}',default=None)
        if event and event.get('nonce') != st.session_state.get('_graph_event'):
            st.session_state._graph_event=event['nonce']
            if event['kind'] in ['movie','center']:
                choose(event['movieId'])
                st.rerun()
            else:
                st.session_state.feature=(event['kind'],event['label'])
                st.session_state.feature_page=0
        st.caption('点击节点查看关联电影；拖动节点调整布局。滚轮缩放，双击空白处复位。')
        if graph['hiddenTags']:
            st.caption(f'为保持可读性，图谱省略 {graph["hiddenTags"]} 个标签；全部标签在“电影标签”中。')
        with st.expander('按类型或标签查看关联电影（键盘可用）'):
            features=[('genre',g) for g in movie['genres']]+[('tag',t) for t in movie['tags']]
            if features:
                f=st.selectbox('选择关系',features,format_func=lambda x:('类型 · ' if x[0]=='genre' else '标签 · ')+x[1])
                if st.button('查看关联电影'):
                    st.session_state.feature=f
                    st.session_state.feature_page=0
        if 'feature' in st.session_state:
            kind,name=st.session_state.feature
            fp=st.session_state.get('feature_page',0)
            related=api(f'/api/features/{kind}',name=name,offset=fp*10,limit=10)
            st.markdown(f'**{name}** · {related["total"]:,} 部关联电影')
            for m in related['items']:
                st.button(f'{m["title"]} · #{m["movieId"]}',key=f'feature-{m["movieId"]}',on_click=choose,args=(m['movieId'],))
            aa,bb=st.columns(2)
            if aa.button('关联上一页',disabled=fp==0):
                st.session_state.feature_page=fp-1
                st.rerun()
            if bb.button('关联下一页',disabled=(fp+1)*10>=related['total']):
                st.session_state.feature_page=fp+1
                st.rerun()
    with tab2:
        st.subheader(f'{len(movie["tags"])} 个真实标签')
        if movie['tags']:
            chips(movie['tags'],tag=True)
        else:
            st.info('这部电影没有用户标签，推荐将仅根据共同类型计算。')
        st.caption('标签来自用户标注，清洗时统一大小写、空白和 Unicode 形式，并按电影去重。')
        st.download_button('下载本片信息 JSON',json.dumps(movie,ensure_ascii=False,indent=2),file_name=f'movie-{movie["movieId"]}.json',mime='application/json')
    with tab3:
        st.subheader('类型分布')
        st.bar_chart(pd.DataFrame(stats['genreDistribution']).set_index('name'),horizontal=True,color='#217561')
        st.caption(f'{stats["taggedMovies"]:,} 部电影有标签；{stats["movies"]-stats["taggedMovies"]:,} 部没有标签。电影可同时属于多个类型。')
        st.markdown('[数据来源与使用条件](https://grouplens.org/datasets/movielens/latest/)')
        st.caption('本系统不使用评分、演员、导演、剧情简介或用户画像。')
with right:
    st.subheader('相似电影')
    st.caption('共同类型 + 共同标签 · 最多 5 部')
    recs=api(f'/api/movies/{movie["movieId"]}/recommendations')['items']
    if not recs:
        st.info('没有共享类型或标签的其他电影，暂时无法推荐。')
    for index,rec in enumerate(recs,1):
        with st.container(border=True):
            a,b=st.columns([5,1])
            a.markdown(f'<div class="rec-title">{index:02d} &nbsp; {html.escape(rec["title"])}</div>',unsafe_allow_html=True)
            b.markdown(f'<div class="score">{rec["score"]}</div>',unsafe_allow_html=True)
            st.markdown('<div class="reason">'+html.escape(rec['reason'])+'</div>',unsafe_allow_html=True)
            st.caption(f'{len(rec["sharedGenres"])} 个共同类型 + {len(rec["sharedTags"])} 个共同标签')
            st.button('探索这部电影 ↗',key=f'rec-{rec["movieId"]}',on_click=choose,args=(rec['movieId'],),use_container_width=True)
    st.caption('同分按 movieId 升序。分数表示共享关系数量，不代表预测评分。')
st.markdown('<div class="footer">MOVIEGRAPH　/　基于真实图关系的基础推荐　　数据：GroupLens · MovieLens Latest Small</div>',unsafe_allow_html=True)
