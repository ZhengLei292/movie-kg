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
        for label in ['MovieGraphMovie','MovieGraphGenre','MovieGraphTag','MovieGraphState']:
            graph.run(f'CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE')
        graph.run('CREATE INDEX moviegraph_dataset IF NOT EXISTS FOR (m:MovieGraphMovie) ON (m.dataset)')
        for start in range(0,len(movies),400):
            batch = movies[start:start+400]
            graph.run('''UNWIND $rows AS row
                MERGE (m:MovieGraphMovie {key:$ds+':'+toString(row.movieId)})
                SET m.dataset=$ds, m.movieId=row.movieId, m.title=row.title, m.year=row.year
                FOREACH (name IN row.genres |
                    MERGE (g:MovieGraphGenre {key:$ds+':'+name}) SET g.dataset=$ds, g.name=name
                    MERGE (m)-[:IN_GENRE]->(g))
                FOREACH (name IN row.tags |
                    MERGE (t:MovieGraphTag {key:$ds+':'+name}) SET t.dataset=$ds, t.name=name
                    MERGE (m)-[:HAS_TAG]->(t))''', ds=ds, rows=batch)
            print(f'Imported {min(start+400,len(movies))}/{len(movies)}', flush=True)
        counts = graph.run('''MATCH (m:MovieGraphMovie {dataset:$ds}) RETURN count(m) AS movies,
            sum(size([(m)-[:IN_GENRE]->() | 1])) AS genres,
            sum(size([(m)-[:HAS_TAG]->() | 1])) AS tags''', ds=ds)[0]
        expected = dict(movies=len(movies), genres=sum(len(m['genres']) for m in movies), tags=sum(len(m['tags']) for m in movies))
        if counts != expected:
            raise RuntimeError(f'Graph count mismatch: {counts} != {expected}')
        graph.run("MERGE (s:MovieGraphState {key:'current'}) SET s.dataset=$ds", ds=ds)
        print(f'ACTIVE {ds}: {counts}')
    finally:
        graph.close()

if __name__ == '__main__':
    run_import()
