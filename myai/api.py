"""API for a locally hosted model. Requires per-store server-side API keys.

Do not directly expose this development server to the public internet.
"""
import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,HTTPException,Header,Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict, model_validator
from .db import connect,initialize,resolve_api_key
from .engine import SalesAssistant,LocalQwen
from .retrieval import SearchFilters, search_products

ROOT=Path(__file__).resolve().parents[1]
DB_PATH=os.getenv('MYAI_DB',str(ROOT/'data'/'myai.sqlite3'))
MODEL=LocalQwen(os.getenv('MYAI_MODEL',str(ROOT/'models'/'Qwen3.5-9B')),
                os.getenv('MYAI_ADAPTER',str(ROOT/'adapters'/'myai-sales-v0.3-9B')),
                quantize=os.getenv('MYAI_INFER_4BIT','1')=='1')



def get_conn():
    conn=connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def authenticate(x_api_key:str|None=Header(default=None),conn=Depends(get_conn)):
    store=resolve_api_key(conn,x_api_key)
    if store is None:
        raise HTTPException(status_code=401,detail='Missing or invalid X-API-Key')
    return store


class ChatRequest(BaseModel):
    question:str=Field(min_length=2,max_length=1200)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str = Field(default='', max_length=1200)
    min_price: int | None = Field(default=None, ge=0, strict=True)
    max_price: int | None = Field(default=None, ge=0, strict=True)
    in_stock: bool | None = Field(default=None, strict=True)
    attributes: dict[str, str | int | float | bool | list[str | int | float | bool]] = Field(default_factory=dict, max_length=30)
    limit: int = Field(default=6, ge=1, le=100, strict=True)

    @model_validator(mode='after')
    def validate_price_range(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError('Minimum price exceeds maximum price')
        return self


@asynccontextmanager
async def lifespan(app):
    conn=connect(DB_PATH)
    try:initialize(conn)
    finally:conn.close()
    # Search is usable before model installation; generate() still verifies files.
    yield

app=FastAPI(title='MyAI local sales assistant',version='0.3.0',lifespan=lifespan)


@app.get('/')
def index():
    return FileResponse(ROOT/'web'/'index.html')


@app.get('/health')
def health():
    return {'status':'ok','mode':'local-qlora','model_loaded':MODEL._model is not None,
            'model_files_present':(MODEL.model_path/'config.json').is_file(),
            'adapter_files_present':(MODEL.adapter_path/'adapter_config.json').is_file()}


@app.post('/search')
def search(request: SearchRequest, store=Depends(authenticate), conn=Depends(get_conn)):
    filters = SearchFilters(request.min_price, request.max_price, request.in_stock, request.attributes)
    products = search_products(conn, store['id'], request.query, request.limit, filters)
    return {'store_id': store['id'], 'products': products, 'count': len(products)}


@app.post('/chat')
def chat(request:ChatRequest,store=Depends(authenticate),conn=Depends(get_conn)):
    try:
        return SalesAssistant(conn,MODEL).respond(store['id'],request.question)
    except ValueError as e:
        raise HTTPException(status_code=400,detail=str(e)) from e
    except (OSError,RuntimeError,ImportError) as e:
        # Only log server side; never expose private filesystem details to customers.
        logging.getLogger(__name__).exception('Local Qwen inference failed')
        raise HTTPException(status_code=503,detail='Local model unavailable or out of resources; check server logs.') from e
