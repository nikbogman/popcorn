import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response

from .api import Api
from .collection import Collection, NewEntry
from .tmdb import Tmdb

HEADER = ['TMDB ID', 'Title', 'Year', 'Status', 'Favourite', 'Added', 'Watched']


def to_csv(header: list[str], rows: list[list[str]]):
    """A CSV with CRLF line endings, quoting only the cells that need it."""
    out = io.StringIO()
    csv.writer(out, lineterminator='\r\n').writerows([header, *rows])
    return out.getvalue()


def _iso(d: datetime):
    return d.astimezone(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


async def export_csv(collection: Collection):
    """The whole Collection, oldest added first, in the format import_csv reads."""
    return to_csv(
        HEADER,
        [
            [
                str(e['tmdb_id']),
                e['title'],
                '' if e['year'] is None else str(e['year']),
                e['status'],
                str(e['favourite']).lower(),
                _iso(e['added_at']),
                _iso(e['watched_at']) if e['watched_at'] else '',
            ]
            for e in await collection.all()
        ],
    )


def _date(text: str, fallback: datetime):
    if not text:
        return fallback
    d = datetime.fromisoformat(text)
    return d if d.tzinfo else d.replace(tzinfo=UTC)


class ImportResult(Api):
    movies: int
    added: int
    not_found: list[str]
    invalid: list[str]


async def import_csv(collection: Collection, tmdb: Tmdb, text: str):
    """
    Adds the CSV's movies to the Collection. A row is matched by TMDB ID, else by title and year.
    Watched if it has a Watched date, Status watched or is a Favourite. Movies already in it are left alone, so it is safe to rerun.
    Rows with an unreadable TMDB ID, year or date are skipped and reported as invalid.
    """
    reader = csv.DictReader(io.StringIO(text), restval='')
    rows = list(reader)
    if rows and not set(HEADER) <= set(reader.fieldnames or []):
        raise HTTPException(400, f"The CSV's header must be {','.join(HEADER)}")
    at = datetime.now(UTC)
    not_found: list[str] = []
    invalid: list[str] = []
    entries: list[NewEntry] = []
    for r in rows:
        name = f'{r["Title"]} ({r["Year"]})'
        favourite = r['Favourite'] == 'true'
        try:
            tmdb_id = int(r['TMDB ID']) if r['TMDB ID'] else None
            year = int(r['Year']) if r['Year'] else None
            added_at = _date(r['Added'], at)
            watched_at = _date(r['Watched'], added_at) if r['Watched'] or r['Status'] == 'watched' or favourite else None
        except ValueError:
            invalid.append(name)
            continue
        # ponytail: without a TMDB ID, exact title + year match on TMDB's first page, else skipped and reported
        movie = await tmdb.details(tmdb_id) if tmdb_id else next((m for m in await tmdb.search(r['Title']) if m.year == year), None)
        if movie:
            entries.append(NewEntry(movie, added_at, watched_at, favourite))
        else:
            not_found.append(name)
    return ImportResult(movies=len(rows), added=await collection.add(entries), not_found=not_found, invalid=invalid)


def csv_routes(collection: Collection, tmdb: Tmdb):
    """POST /import takes the CSV as the request body; GET /export downloads the Collection in the same format."""
    router = APIRouter()

    @router.post('/import', openapi_extra={'requestBody': {'content': {'text/csv': {'schema': {'type': 'string'}}}, 'required': True}})
    async def import_collection(request: Request) -> ImportResult:
        return await import_csv(collection, tmdb, (await request.body()).decode())

    @router.get('/export', response_class=Response, responses={200: {'content': {'text/csv': {'schema': {'type': 'string'}}}}})
    async def export_collection():
        return Response(
            await export_csv(collection),
            media_type='text/csv; charset=utf-8',
            headers={'content-disposition': 'attachment; filename="watcher.csv"'},
        )

    return router
