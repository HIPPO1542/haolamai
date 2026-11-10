r"""Read-only inspector for external dataset files downloaded on Windows.
Supports JSONL, JSON, CSV; Parquet if optional pyarrow is installed.
It never changes source files or sends data to the Internet.
Usage: py -3.11 .\MyAI_Data_Pack_v1\tools\inspect_downloaded.py path\to\dataset_folder
"""
import argparse, csv, json, sys
from pathlib import Path

def sample(path):
    if path.suffix.lower() in ('.jsonl','.ndjson'):
        with path.open(encoding='utf-8-sig') as f:
            for line in f:
                if line.strip():return json.loads(line)
    if path.suffix.lower()=='.json':
        x=json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(x,list):return x[0] if x else {}
        return x
    if path.suffix.lower()=='.csv':
        with path.open(encoding='utf-8-sig',newline='') as f:return next(csv.DictReader(f),{})
    if path.suffix.lower()=='.parquet':
        import pyarrow.parquet as pq
        table=pq.read_table(path)
        return table.slice(0,1).to_pylist()[0] if table.num_rows else {}
    return {}

def main():
    p=argparse.ArgumentParser();p.add_argument('paths',nargs='+')
    args=p.parse_args()
    for raw in args.paths:
        path=Path(raw)
        if not path.exists():print('NOT FOUND',path);continue
        files=[path] if path.is_file() else [p for p in path.rglob('*') if p.suffix.lower() in ('.jsonl','.ndjson','.json','.csv','.parquet')]
        if not files:print('NO SUPPORTED FILES IN',path);continue
        for f in files[:35]:
            try:
                record=sample(f)
                print('\nFILE',f,'size_kb',round(f.stat().st_size/1024))
                print('Top-level record shape:',type(record).__name__)
                print('Fields:',list(record) if isinstance(record,dict) else 'non-object')
                print('Example value types:',{k:type(v).__name__ for k,v in record.items()} if isinstance(record,dict) else '')
            except Exception as e:print('SKIP',f,type(e).__name__,str(e)[:180])
    print('\nRead-only inspection complete. Do not merge until licenses and field mappings are checked.')
if __name__=='__main__':main()
