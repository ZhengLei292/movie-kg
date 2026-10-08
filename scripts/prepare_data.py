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
from datetime import datetime, timezone
import math
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
    required = ('movies.csv', 'tags.csv', 'ratings.csv', 'links.csv', 'README.txt')
    if not all((raw / name).exists() for name in required) and not archive.exists():
        import truststore
        truststore.inject_into_ssl()
        with urllib.request.urlopen(URL, timeout=120) as r:
            payload = r.read()
        archive.write_bytes(payload)
    if not all((raw / name).exists() for name in required):
        with zipfile.ZipFile(archive) as z:
            for name in required:
                if not (raw / name).exists():
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
    ratings_by_pair = {}
    with (raw / 'ratings.csv').open(encoding='utf-8-sig', newline='') as f:
        for index, r in enumerate(csv.DictReader(f)):
            audit['rawRatingRows'] += 1
            try:
                uid, mid, timestamp = int(r['userId']), int(r['movieId']), int(r['timestamp'])
                rating = float(r['rating'])
                if uid <= 0 or timestamp < 0 or not math.isfinite(rating) or not .5 <= rating <= 5 or not (rating * 2).is_integer():
                    raise ValueError('invalid rating domain')
                utc = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            except (ValueError, OverflowError, OSError):
                audit['invalidRatingRows'] += 1
                continue
            if mid not in movies:
                audit['orphanRatingRows'] += 1
                continue
            pair = (uid, mid)
            old = ratings_by_pair.get(pair)
            if old:
                audit['duplicateRatingRows'] += 1
                if timestamp < old['timestamp']:
                    continue
            ratings_by_pair[pair] = dict(userId=uid, movieId=mid, rating=rating, timestamp=timestamp, datetimeUTC=utc)
    ratings = sorted(ratings_by_pair.values(), key=lambda r: (r['userId'], r['movieId']))
    by_movie = defaultdict(list)
    for r in ratings:
        by_movie[r['movieId']].append(r['rating'])
    seen_links = set()
    with (raw / 'links.csv').open(encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            audit['rawLinkRows'] += 1
            mid = int(r['movieId'])
            if mid not in movies:
                audit['orphanLinkRows'] += 1
                continue
            if mid in seen_links:
                raise ValueError(f'Duplicate links.movieId: {mid}')
            seen_links.add(mid)
            for field in ('imdbId', 'tmdbId'):
                value = r[field].strip()
                parsed = None
                if value:
                    try:
                        number = float(value)
                        if not math.isfinite(number) or number <= 0 or not number.is_integer():
                            raise ValueError('invalid identifier')
                        parsed = int(number)
                    except ValueError:
                        audit['invalidExternalIds'] += 1
                movies[mid][field] = parsed
    for mid, m in movies.items():
        m.setdefault('imdbId', None)
        m.setdefault('tmdbId', None)
        m['ratingCount'] = len(by_movie[mid])
        m['averageRating'] = sum(by_movie[mid]) / len(by_movie[mid]) if by_movie[mid] else None
    rows = sorted(movies.values(), key=lambda m: m['movieId'])
    users = sorted({r['userId'] for r in ratings})
    content = dict(schemaVersion=2, movies=rows, ratings=ratings, users=users)
    payload = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    dataset = hashlib.sha256(payload.encode()).hexdigest()[:20]
    (out / 'movies.json').write_text(json.dumps({'dataset':dataset, **content}, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'ratings.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['userId','movieId','rating','timestamp','datetimeUTC'])
        w.writeheader(); w.writerows(ratings)
    with (out / 'links.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f); w.writerow(['movieId','imdbId','tmdbId'])
        w.writerows((m['movieId'],m['imdbId'],m['tmdbId']) for m in rows)
    for fname, field in [('movie_genres.csv','genres'),('movie_tags.csv','tags')]:
        with (out / fname).open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['movieId', 'name'])
            w.writerows((m['movieId'], value) for m in rows for value in m[field])
    with (out / 'movies.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        fields=['movieId','title','year','ratingCount','averageRating','imdbId','tmdbId']
        w.writerow(fields)
        w.writerows(tuple(m[k] for k in fields) for m in rows)
    stats = dict(audit)
    stats.update(movies=len(rows), genres=len({g for m in rows for g in m['genres']}),
        tags=len({t for m in rows for t in m['tags']}),
        genreRelations=sum(len(m['genres']) for m in rows), tagRelations=sum(len(m['tags']) for m in rows),
        noTags=sum(not m['tags'] for m in rows), noGenres=sum(not m['genres'] for m in rows),
        missingYears=sum(m['year'] is None for m in rows),
        duplicateTitleGroups=sum(n>1 for n in Counter(m['title'] for m in rows).values()),
        users=len(users), ratingRelations=len(ratings), ratedMovies=sum(bool(m['ratingCount']) for m in rows),
        imdbMovies=sum(m['imdbId'] is not None for m in rows), tmdbMovies=sum(m['tmdbId'] is not None for m in rows),
        schemaVersion=2, dataset=dataset, source=URL,
        sourceSHA256={name:hashlib.sha256((raw/name).read_bytes()).hexdigest() for name in required},
        archiveSHA256=hashlib.sha256(archive.read_bytes()).hexdigest() if archive.exists() else None)
    (out / 'stats.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(stats,ensure_ascii=False,indent=2))
    return stats

if __name__ == '__main__':
    prepare()
