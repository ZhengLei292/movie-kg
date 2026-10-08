"""Read-only JSON API. See http://127.0.0.1:18080/docs."""
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from .graph import GraphStore

store = GraphStore()

@asynccontextmanager
async def lifespan(app):
    yield
    store.close()

app = FastAPI(title='MovieGraph API', version='2.0.0', lifespan=lifespan,
              description='电影、类型、标签与匿名用户图谱，包含评分关系和IMDb/TMDb外部标识。')

async def db_error(request: Request, exc):
    return JSONResponse(status_code=503, content={'detail':'图数据库未就绪，请检查启动窗口和 logs 目录。'})

for exc in (Neo4jError, ServiceUnavailable, SessionExpired, RuntimeError):
    app.add_exception_handler(exc, db_error)

def require_movie(movie_id):
    item = store.movie(movie_id)
    if item is None:
        raise HTTPException(404, '电影不存在')
    return item

@app.get('/health')
def health():
    return {'status':'ok', 'database':'Neo4j', 'dataset':store.dataset()}

@app.get('/api/stats')
def stats():
    return store.stats()

@app.get('/api/movies')
def search(q: str = Query('', max_length=200), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return store.search(q, offset, limit)

@app.get('/api/movies/{movie_id}')
def movie(movie_id: int):
    return require_movie(movie_id)

@app.get('/api/movies/{movie_id}/recommendations')
def recommend(movie_id: int, limit: int = Query(5, ge=1, le=5)):
    require_movie(movie_id)
    return {'items':store.recommend(movie_id, limit), 'rule':'共同类型数 + 共同标签数；同分按 movieId 升序'}

@app.get('/api/movies/{movie_id}/graph')
def graph(movie_id: int, limit: int = Query(8, ge=0, le=12), user_limit: int = Query(0, ge=0, le=5)):
    result = store.local_graph(movie_id, limit, user_limit)
    if result is None:
        raise HTTPException(404, '电影不存在')
    return result

@app.get('/api/features/{kind}')
def related(kind: Literal['genre','tag'], name: str = Query(..., min_length=1, max_length=500),
            offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return store.related(kind, name, offset, limit)

@app.get('/api/movies/{movie_id}/ratings')
def movie_ratings(movie_id: int):
    require_movie(movie_id)
    return store.movie_ratings(movie_id)

@app.get('/api/users')
def users():
    return {'items':store.users()}

@app.get('/api/users/{user_id}')
def user(user_id: int, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    result = store.user(user_id, offset, limit)
    if result is None:
        raise HTTPException(404,'数据集中没有这个用户')
    return result

@app.get('/api/users/{user_id}/recommendations')
def user_recommend(user_id: int, limit: int = Query(5, ge=1, le=10)):
    if store.user(user_id, 0, 1) is None:
        raise HTTPException(404,'数据集中没有这个用户')
    return {'items':store.user_recommend(user_id,limit),
            'rule':'双方评分均至少4分的共同电影确定邻居；邻居高分电影排除已评分项，按支持用户数、邻居均分、movieId排序。'}
