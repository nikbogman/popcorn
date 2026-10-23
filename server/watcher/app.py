import asyncpg
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .auth import create_auth
from .collection import Collection, collection_routes
from .csv_io import csv_routes
from .movies import movie_routes
from .reels.queue import ReelQueue, reel_routes
from .tmdb import Tmdb, TmdbUnreachable


def create_app(pool: asyncpg.Pool, tmdb: Tmdb, password: str):
    collection = Collection(pool, tmdb)
    auth, require_token = create_auth(pool, password)
    app = FastAPI(title='Watcher')

    # Every failure has the same { error } shape; unexpected ones (e.g. the database) are a 500.
    @app.exception_handler(HTTPException)
    async def http_error(_: Request, e: HTTPException):
        return JSONResponse({'error': e.detail}, e.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, e: RequestValidationError):
        return JSONResponse({'error': '; '.join(f'{".".join(map(str, err["loc"]))}: {err["msg"]}' for err in e.errors())}, 400)

    @app.exception_handler(TmdbUnreachable)
    async def tmdb_down(_: Request, e: TmdbUnreachable):
        return JSONResponse({'error': str(e)}, 502)

    @app.exception_handler(Exception)
    async def internal(_: Request, e: Exception):
        return JSONResponse({'error': 'Internal error'}, 500)

    signed_in = [Depends(require_token)]
    app.include_router(auth, prefix='/api/auth')
    app.include_router(movie_routes(tmdb, collection), prefix='/api', dependencies=signed_in)
    app.include_router(collection_routes(collection), prefix='/api/collection', dependencies=signed_in)
    app.include_router(csv_routes(collection, tmdb), prefix='/api/collection', dependencies=signed_in)
    app.include_router(reel_routes(ReelQueue(pool)), prefix='/api/reels', dependencies=signed_in)
    return app
