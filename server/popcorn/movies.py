from fastapi import APIRouter, HTTPException

from .collection import Collection, Entry
from .tmdb import MovieSummary, Tmdb, TmdbId, found, poster_url, to_row


class MoviePage(MovieSummary, Entry):
    overview: str


def movie_routes(tmdb: Tmdb, collection: Collection):
    router = APIRouter()

    @router.get('/search')
    async def search(q: str) -> list[MovieSummary]:
        if not q.strip():
            raise HTTPException(400, 'q is required')
        return [to_row(m) for m in await tmdb.search(q.strip())]

    @router.get('/movies/{tmdb_id}')
    async def movie(tmdb_id: TmdbId) -> MoviePage:
        m = found(await tmdb.details(tmdb_id))
        entry = await collection.entry(tmdb_id)
        return MoviePage(
            tmdb_id=m.tmdb_id,
            title=m.title,
            year=m.year,
            poster_url=poster_url(m.poster_path, 'page'),
            overview=m.overview,
            **entry.model_dump(),
        )

    return router
