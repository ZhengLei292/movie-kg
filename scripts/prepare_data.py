"""Download once, retain provenance, normalize movies/tags, and fingerprint output."""
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://files.grouplens.org/datasets/movielens/ml-latest-small.zip'

def normalize_tag(tag):
    return ' '.join(unicodedata.normalize('NFKC', tag).split()).casefold()

def prepare():
    raw = ROOT / 'data/raw'
    out = ROOT / 'data/processed'
    raw.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    archive = raw / 'ml-latest-small.zip'
    if not archive.exists():
        import truststore
        truststore.inject_into_ssl()
        with urllib.request.urlopen(URL, timeout=120) as r:
            payload = r.read()
        archive.write_bytes(payload)
    with zipfile.ZipFile(archive) as z:
        for name in ('movies.csv','tags.csv','README.txt'):
            (raw / name).write_bytes(z.read('ml-latest-small/' + name))
    movies = {}
    with (raw / 'movies.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            mid = int(r['movieId'])
            if mid in movies:
                raise ValueError(f'Duplicate movieId: {mid}')
            title = r['title'].strip()
            if not title:
                raise ValueError(f'Empty title: {mid}')
            match = re.search(r'\((\d{4})\)\s*$', title)
            movies[mid] = dict(movieId=mid, title=title, year=int(match[1]) if match else None,
                genres=sorted({g.strip() for g in r['genres'].split('|') if g.strip() and g != '(no genres listed)'}), tags=[])
    tags = defaultdict(set)
    audit = Counter()
    with (raw / 'tags.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            audit['rawTagRows'] += 1
            mid, tag = int(r['movieId']), normalize_tag(r['tag'])
            if mid not in movies:
                audit['orphanTagRows'] += 1
            elif not tag:
                audit['emptyTagRows'] += 1
            elif tag in tags[mid]:
                audit['duplicateTagRows'] += 1
            else:
                tags[mid].add(tag)
    for mid, movie in movies.items():
        movie['tags'] = sorted(tags[mid])
    rows = sorted(movies.values(), key=lambda m: m['movieId'])
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    dataset = hashlib.sha256(payload.encode()).hexdigest()[:20]
    (out / 'movies.json').write_text(json.dumps({'dataset':dataset,'movies':rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    for fname, field in [('movie_genres.csv','genres'),('movie_tags.csv','tags')]:
        with (out / fname).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['movieId', 'name'])
            w.writerows((m['movieId'], value) for m in rows for value in m[field])
    with (out / 'movies.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(['movieId','title','year'])
        w.writerows((m['movieId'],m['title'],m['year']) for m in rows)
    stats = dict(audit)
    stats.update(movies=len(rows), genres=len({g for m in rows for g in m['genres']}),
        tags=len({t for m in rows for t in m['tags']}),
        genreRelations=sum(len(m['genres']) for m in rows), tagRelations=sum(len(m['tags']) for m in rows),
        noTags=sum(not m['tags'] for m in rows), noGenres=sum(not m['genres'] for m in rows),
        missingYears=sum(m['year'] is None for m in rows),
        duplicateTitleGroups=sum(n>1 for n in Counter(m['title'] for m in rows).values()),
        dataset=dataset, source=URL, archiveSHA256=hashlib.sha256(archive.read_bytes()).hexdigest())
    (out / 'stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))
    return stats

if __name__ == '__main__':
    prepare()

