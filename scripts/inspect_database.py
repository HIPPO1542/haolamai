"""Inspect SQLite schema/counts read-only, without printing products or key digests."""
import argparse
import json
from pathlib import Path
import sqlite3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='data/myai.sqlite3')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output).resolve()
    if not output.is_relative_to(root) or any(output.is_relative_to(root/name) for name in ('data', 'datasets', 'models', 'adapters')):
        parser.error('Choose an audit output inside workspace, outside protected inputs')
    database = Path(args.db).resolve()
    conn = sqlite3.connect(database.as_uri()+'?mode=ro', uri=True)
    try:
        schema = conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        tables = {name for name, _ in schema}
        counts = {name: conn.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]
                  for name in ('stores', 'products', 'knowledge', 'api_keys') if name in tables}
        integrity = conn.execute('PRAGMA quick_check').fetchone()[0]
        foreign_key_errors = len(conn.execute('PRAGMA foreign_key_check').fetchall())
        invalid_attributes = 0
        if 'products' in tables:
            for (attributes,) in conn.execute('SELECT attributes_json FROM products'):
                try:
                    valid = isinstance(json.loads(attributes), dict)
                except (TypeError, ValueError):
                    valid = False
                invalid_attributes += not valid
        report = {'mode': 'read-only', 'schema': schema, 'counts': counts, 'quick_check': integrity,
                  'foreign_key_errors': foreign_key_errors, 'invalid_product_attributes': invalid_attributes}
    finally:
        conn.close()
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in report.items() if key != 'schema'}, ensure_ascii=False))
    return int(integrity != 'ok' or foreign_key_errors or invalid_attributes)


if __name__ == '__main__':
    raise SystemExit(main())
