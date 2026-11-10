"""SQLite storage for one self-hosted development deployment.

Every query is tenant-scoped; keys are random bearer credentials stored only as SHA-256 digests.
SQLite is not the recommended database for high-concurrency public SaaS deployments.
"""
import hashlib
import json
import os
import secrets
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(os.getenv('MYAI_DB', 'data/myai.sqlite3'))


def connect(path=None):
    path = Path(path) if path is not None else DEFAULT_DB
    if str(path) != ':memory:':
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    return conn


def initialize(conn):
    conn.executescript('''
    CREATE TABLE IF NOT EXISTS stores (
      id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS products (
      id TEXT NOT NULL,
      store_id TEXT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
      name TEXT NOT NULL, price_vnd INTEGER NOT NULL CHECK(price_vnd >= 0),
      stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
      description TEXT NOT NULL DEFAULT '', attributes_json TEXT NOT NULL DEFAULT '{}',
      active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
      PRIMARY KEY (store_id, id)
    );
    CREATE INDEX IF NOT EXISTS idx_products_store ON products(store_id,active);
    CREATE TABLE IF NOT EXISTS knowledge (
      id TEXT NOT NULL, store_id TEXT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
      title TEXT NOT NULL, content TEXT NOT NULL,
      PRIMARY KEY (store_id,id)
    );
    CREATE TABLE IF NOT EXISTS api_keys (
      key_digest TEXT PRIMARY KEY,
      store_id TEXT NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      revoked_at TEXT DEFAULT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_keys_store ON api_keys(store_id);
    ''')
    conn.commit()


def add_store(conn, store_id, name, category):
    conn.execute('INSERT INTO stores(id,name,category) VALUES(?,?,?) '
                 'ON CONFLICT(id) DO UPDATE SET name=excluded.name,category=excluded.category',
                 (store_id, name, category))
    conn.commit()


def add_product(conn, product):
    conn.execute('''INSERT INTO products
      (id,store_id,name,price_vnd,stock,description,attributes_json,active)
      VALUES (?,?,?,?,?,?,?,?)
      ON CONFLICT(store_id,id) DO UPDATE SET
      name=excluded.name,price_vnd=excluded.price_vnd,stock=excluded.stock,
      description=excluded.description,attributes_json=excluded.attributes_json,
      active=excluded.active''',
      (product['id'], product['store_id'], product['name'], product['price_vnd'],
       product['stock'], product.get('description',''),
       json.dumps(product.get('attributes',{}), ensure_ascii=False), int(product.get('active',1))))
    conn.commit()


def add_knowledge(conn, doc_id, store_id, title, content):
    conn.execute('''INSERT INTO knowledge(id,store_id,title,content) VALUES(?,?,?,?)
      ON CONFLICT(store_id,id) DO UPDATE SET title=excluded.title,content=excluded.content''',
      (doc_id,store_id,title,content))
    conn.commit()


def get_store(conn, store_id):
    row = conn.execute('SELECT id,name,category FROM stores WHERE id=?', (store_id,)).fetchone()
    return dict(row) if row else None


def get_products(conn, store_id, limit=2000, *, min_price=None, max_price=None, in_stock=None):
    sql = 'SELECT * FROM products WHERE store_id=? AND active=1'
    params = (store_id,)
    if min_price is not None:
        sql += ' AND price_vnd>=?'
        params += (min_price,)
    if max_price is not None:
        sql += ' AND price_vnd<=?'
        params += (max_price,)
    if in_stock is not None:
        clause = ' AND stock>0' if in_stock else ' AND stock=0'
        sql += clause
    sql += ' ORDER BY name'
    if limit is not None:
        sql += ' LIMIT ?'
        params += (limit,)
    rows = conn.execute(sql, params)
    result=[]
    for row in rows:
        p=dict(row)
        p['attributes']=json.loads(p.pop('attributes_json'))
        result.append(p)
    return result


def get_knowledge(conn, store_id):
    return [dict(row) for row in conn.execute('SELECT * FROM knowledge WHERE store_id=?',(store_id,))]


def _digest(key):
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def create_api_key(conn, store_id):
    if get_store(conn, store_id) is None:
        raise ValueError('Store does not exist')
    key='myai_'+secrets.token_urlsafe(32)
    conn.execute('INSERT INTO api_keys(key_digest,store_id) VALUES (?,?)',(_digest(key),store_id))
    conn.commit()
    return key  # Show ONCE. Never log or persist the cleartext key.


def resolve_api_key(conn, key):
    if not key or not key.startswith('myai_') or len(key)>128:
        return None
    row=conn.execute('''SELECT stores.id,stores.name,stores.category FROM api_keys
       JOIN stores ON stores.id=api_keys.store_id
       WHERE key_digest=? AND revoked_at IS NULL''',(_digest(key),)).fetchone()
    return dict(row) if row else None


def revoke_api_key(conn, key):
    conn.execute('UPDATE api_keys SET revoked_at=CURRENT_TIMESTAMP WHERE key_digest=?',(_digest(key),))
    conn.commit()
