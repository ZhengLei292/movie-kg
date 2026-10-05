from neo4j import GraphDatabase
from .settings import URI, USER, PASSWORD, DATABASE


class GraphStore:
    def __init__(self):
        self.driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD) if PASSWORD else None,
                                          connection_timeout=5)

    def close(self):
        self.driver.close()

    def run(self, query, **params):
        with self.driver.session(database=DATABASE) as session:
            return session.run(query, **params).data()

    def dataset(self):
        rows = self.run("MATCH (s:MovieGraphState {key:'current'}) RETURN s.dataset AS dataset")
        if not rows:
            raise RuntimeError('数据尚未导入，请运行 rebuild.bat')
        return rows[0]['dataset']

    def movie(self, movie_id):
        rows = self.run('''MATCH (m:MovieGraphMovie {dataset:$ds, movieId:$id})
            RETURN m.movieId AS movieId, m.title AS title, m.year AS year,
            [(m)-[:IN_GENRE]->(g:MovieGraphGenre) | g.name] AS genres,
            [(m)-[:HAS_TAG]->(t:MovieGraphTag) | t.name] AS tags''', ds=self.dataset(), id=movie_id)
        if not rows:
            return None
        row = rows[0]
        row['genres'].sort()
        row['tags'].sort()
        return row

    def search(self, q='', offset=0, limit=20):
        params = dict(ds=self.dataset(), q=q.strip().lower(), offset=offset, limit=limit)
        base = 'MATCH (m:MovieGraphMovie {dataset:$ds}) WHERE toLower(m.title) CONTAINS $q '
        total = self.run(base + 'RETURN count(m) AS total', **params)[0]['total']
        rows = self.run(base + '''RETURN m.movieId AS movieId, m.title AS title, m.year AS year,
            [(m)-[:IN_GENRE]->(g) | g.name] AS genres,
            size([(m)-[:HAS_TAG]->(t) | t]) AS tagCount
            ORDER BY toLower(m.title), m.movieId SKIP $offset LIMIT $limit''', **params)
        return dict(items=rows, total=total, offset=offset, limit=limit)

    def recommend(self, movie_id, limit=5):
        rows = self.run('''MATCH (m:MovieGraphMovie {dataset:$ds, movieId:$id})
            MATCH (m)-[:IN_GENRE|HAS_TAG]->(f)<-[:IN_GENRE|HAS_TAG]-(n:MovieGraphMovie)
            WHERE n.dataset=$ds AND n.movieId<>m.movieId
            WITH n, collect(DISTINCT CASE WHEN f:MovieGraphGenre THEN f.name END) AS genres,
                    collect(DISTINCT CASE WHEN f:MovieGraphTag THEN f.name END) AS tags
            WITH n, genres, tags, size(genres)+size(tags) AS score
            RETURN n.movieId AS movieId, n.title AS title, n.year AS year,
                   genres AS sharedGenres, tags AS sharedTags, score
            ORDER BY score DESC, n.movieId ASC LIMIT $limit''', ds=self.dataset(), id=movie_id, limit=limit)
        for row in rows:
            row['sharedGenres'].sort()
            row['sharedTags'].sort()
            parts = []
            if row['sharedGenres']:
                parts.append('共享类型：' + '、'.join(row['sharedGenres']))
            if row['sharedTags']:
                parts.append('共享标签：' + '、'.join(row['sharedTags']))
            row['reason'] = '；'.join(parts)
        return rows

    def related(self, kind, name, offset=0, limit=20):
        # Only these hard-coded patterns can become Cypher identifiers.
        label, rel = ('MovieGraphGenre', 'IN_GENRE') if kind == 'genre' else ('MovieGraphTag', 'HAS_TAG')
        base = f'MATCH (m:MovieGraphMovie {{dataset:$ds}})-[:{rel}]->(f:{label} {{name:$name}}) '
        params = dict(ds=self.dataset(), name=name, offset=offset, limit=limit)
        total = self.run(base + 'RETURN count(DISTINCT m) AS total', **params)[0]['total']
        items = self.run(base + '''RETURN DISTINCT m.movieId AS movieId, m.title AS title,
            m.year AS year ORDER BY m.movieId SKIP $offset LIMIT $limit''', **params)
        return dict(items=items, total=total, offset=offset, limit=limit)

    def local_graph(self, movie_id, limit=8):
        center = self.movie(movie_id)
        if not center:
            return None
        recs = self.recommend(movie_id, limit)
        features = [('genre', g) for g in center['genres']] + [('tag', t) for t in center['tags'][:24]]
        nodes = [dict(id=f'm:{movie_id}', label=center['title'], kind='center', movieId=movie_id)]
        edges = []
        for kind, name in features:
            fid = f'{kind}:{name}'
            nodes.append(dict(id=fid, label=name, kind=kind))
            edges.append(dict(source=f'm:{movie_id}', target=fid, relation='IN_GENRE' if kind == 'genre' else 'HAS_TAG'))
        for rec in recs:
            mid = f"m:{rec['movieId']}"
            visible = [(k, n) for k, n in features if n in rec['sharedGenres' if k == 'genre' else 'sharedTags']]
            if not visible:
                continue
            nodes.append(dict(id=mid, label=rec['title'], kind='movie', movieId=rec['movieId']))
            for kind, name in visible:
                edges.append(dict(source=mid, target=f'{kind}:{name}', relation='IN_GENRE' if kind == 'genre' else 'HAS_TAG'))
        return dict(nodes=nodes, edges=edges, hiddenTags=max(0, len(center['tags'])-24), movieId=movie_id)

    def stats(self):
        ds = self.dataset()
        row = self.run('''MATCH (m:MovieGraphMovie {dataset:$ds})
            RETURN count(m) AS movies,
            sum(CASE WHEN EXISTS {(m)-[:HAS_TAG]->()} THEN 1 ELSE 0 END) AS taggedMovies,
            sum(CASE WHEN NOT EXISTS {(m)-[:IN_GENRE]->()} THEN 1 ELSE 0 END) AS noGenreMovies''', ds=ds)[0]
        for label, key in [('MovieGraphGenre','genres'),('MovieGraphTag','tags')]:
            row[key] = self.run(f'MATCH (n:{label} {{dataset:$ds}}) RETURN count(n) AS count', ds=ds)[0]['count']
        row['relations'] = self.run('MATCH (:MovieGraphMovie {dataset:$ds})-[r:IN_GENRE|HAS_TAG]->() RETURN count(r) AS count', ds=ds)[0]['count']
        row['genreDistribution'] = self.run('''MATCH (m:MovieGraphMovie {dataset:$ds})-[:IN_GENRE]->(g)
            RETURN g.name AS name, count(m) AS count ORDER BY count DESC, name''', ds=ds)
        row['dataset'] = ds
        row['source'] = 'MovieLens Latest Small / GroupLens'
        return row

