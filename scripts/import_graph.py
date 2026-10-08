"""Idempotent versioned import. Activate only after counts have been validated."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.graph import GraphStore

ROOT = Path(__file__).resolve().parents[1]

def run_import():
    doc = json.loads((ROOT/'data/processed/movies.json').read_text(encoding='utf-8'))
    ds, movies = doc['dataset'], doc['movies']
    graph = GraphStore()
    try:
        for label in ['MovieGraphMovie','MovieGraphGenre','MovieGraphTag','MovieGraphUser','MovieGraphState']:
            graph.run(f'CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE')
        graph.run('CREATE INDEX moviegraph_dataset IF NOT EXISTS FOR (m:MovieGraphMovie) ON (m.dataset)')
        for start in range(0,len(movies),400):
            batch = movies[start:start+400]
            graph.run('''UNWIND $rows AS row
                MERGE (m:MovieGraphMovie {key:$ds+':'+toString(row.movieId)})
                SET m.dataset=$ds, m.movieId=row.movieId, m.title=row.title, m.year=row.year,
                    m.imdbId=row.imdbId, m.tmdbId=row.tmdbId,
                    m.ratingCount=row.ratingCount, m.averageRating=row.averageRating
                FOREACH (name IN row.genres |
                    MERGE (g:MovieGraphGenre {key:$ds+':'+name}) SET g.dataset=$ds, g.name=name
                    MERGE (m)-[:IN_GENRE]->(g))
                FOREACH (name IN row.tags |
                    MERGE (t:MovieGraphTag {key:$ds+':'+name}) SET t.dataset=$ds, t.name=name
                    MERGE (m)-[:HAS_TAG]->(t))''', ds=ds, rows=batch)
            print(f'Imported {min(start+400,len(movies))}/{len(movies)}', flush=True)
        graph.run('CREATE INDEX moviegraphuser_dataset IF NOT EXISTS FOR (u:MovieGraphUser) ON (u.dataset)')
        for start in range(0, len(doc['ratings']), 2000):
            graph.run('''UNWIND $rows AS row
                MATCH (m:MovieGraphMovie {key:$ds+':'+toString(row.movieId)})
                MERGE (u:MovieGraphUser {key:$ds+':'+toString(row.userId)})
                SET u.dataset=$ds, u.userId=row.userId
                MERGE (u)-[r:RATED]->(m)
                SET r.rating=row.rating, r.timestamp=row.timestamp, r.datetimeUTC=row.datetimeUTC''',
                ds=ds, rows=doc['ratings'][start:start+2000])
            print(f'Ratings {min(start+2000,len(doc["ratings"]))}/{len(doc["ratings"])}', flush=True)
        counts = graph.run('''MATCH (m:MovieGraphMovie {dataset:$ds}) RETURN count(m) AS movies,
            sum(size([(m)-[:IN_GENRE]->() | 1])) AS genres,
            sum(size([(m)-[:HAS_TAG]->() | 1])) AS tags''', ds=ds)[0]
        expected = dict(movies=len(movies), genres=sum(len(m['genres']) for m in movies), tags=sum(len(m['tags']) for m in movies))
        if counts != expected:
            raise RuntimeError(f'Graph count mismatch: {counts} != {expected}')
        extra = graph.run('''MATCH (u:MovieGraphUser {dataset:$ds})
            OPTIONAL MATCH (u)-[r:RATED]->(:MovieGraphMovie {dataset:$ds})
            RETURN count(DISTINCT u) AS users, count(r) AS ratings''', ds=ds)[0]
        if extra != dict(users=len(doc['users']), ratings=len(doc['ratings'])):
            raise RuntimeError(f'User/rating count mismatch: {extra}')
        graph.run("MERGE (s:MovieGraphState {key:'current'}) SET s.dataset=$ds, s.schemaVersion=2", ds=ds)
        print(f'ACTIVE {ds}: {counts}')
    finally:
        graph.close()

if __name__ == '__main__':
    run_import()
