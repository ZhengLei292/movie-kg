"""Edge cases for four-file cleaning and version fingerprints; no database needed."""
import csv
import json
import tempfile
from pathlib import Path
from scripts import prepare_data

def run():
    build=Path(__file__).resolve().parents[1]/'.build'
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=build) as tmp:
        prepare_data.ROOT=Path(tmp)
        raw=Path(tmp)/'data/raw';raw.mkdir(parents=True)
        def write(name,rows):
            with (raw/name).open('w',encoding='utf-8',newline='') as f:csv.writer(f).writerows(rows)
        write('movies.csv',[['movieId','title','genres'],[1,'Demo (2000)','Comedy'],[2,'Missing','(no genres listed)']])
        write('tags.csv',[['userId','movieId','tag','timestamp'],[1,1,' PIXAR ',1],[2,1,'pixar',2],[1,99,'orphan',2]])
        write('links.csv',[['movieId','imdbId','tmdbId'],[1,'0000001','123.0'],[2,'','']])
        rows=[['userId','movieId','rating','timestamp'],[1,1,4,2],[1,1,5,1],[1,2,3.5,3],[2,1,'NaN',3],[3,1,4.1,3],[4,99,4,3],[5,1,4,-1]]
        write('ratings.csv',rows);(raw/'README.txt').write_text('test fixture',encoding='utf-8')
        first=prepare_data.prepare()
        doc=json.loads((Path(tmp)/'data/processed/movies.json').read_text(encoding='utf-8'))
        assert len(doc['ratings'])==2 and doc['ratings'][0]['rating']==4
        assert first['users']==1 and first['invalidRatingRows']==3 and first['orphanRatingRows']==1
        assert first['duplicateRatingRows']==1 and first['duplicateTagRows']==1
        assert first['tmdbMovies']==1 and doc['movies'][1]['genres']==[]
        assert doc['ratings'][0]['datetimeUTC'].endswith('+00:00')
        rows[1][2]=4.5;write('ratings.csv',rows)
        second=prepare_data.prepare();assert second['dataset']!=first['dataset']
        write('links.csv',[['movieId','imdbId','tmdbId'],[1,'0000002','123'],[2,'','']])
        third=prepare_data.prepare();assert third['dataset']!=second['dataset']
        assert prepare_data.prepare()['dataset']==third['dataset']
        print('PASS: normalization, invalid ratings, latest deduplication, missing IDs, UTC, four-file fingerprints')

if __name__=='__main__':run()
