import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response

from . import collection as rules  # rules.now(), read through the module so tests' clock applies
from .api import Api, iso
from .collection import Collection, Place
from .tmdb import Movie, Tmdb

HEADER = ['TMDB ID', 'Title', 'Year', 'Status', 'Favourite', 'Added', 'Watched']


def to_csv(header: list[str], rows: list[list[str]]):
    """A CSV with CRLF line endings, quoting only the cells that need it."""
    out = io.StringIO()
    csv.writer(out, lineterminator='\r\n').writerows([header, *rows])
    return out.getvalue()


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
                iso(e['added_at']),
                iso(e['watched_at']) if e['watched_at'] else '',
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
    Rows with an unreadable TMDB ID, year or date are skipped and reported as invalid. Raises ValueError for another format.
    """
    reader = csv.DictReader(io.StringIO(text), restval='')
    rows = list(reader)
    if rows and not set(HEADER) <= set(reader.fieldnames or []):
        raise ValueError(f"The CSV's header must be {','.join(HEADER)}")
    at = rules.now()
    not_found: list[str] = []
    invalid: list[str] = []
    entries: list[tuple[Movie, Place]] = []
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
            place = Place('watched', added_at, watched_at, favourite) if watched_at else Place.to_watch(added_at)
            entries.append((movie, place))
        else:
            not_found.append(name)
    return ImportResult(movies=len(rows), added=await collection.add(entries), not_found=not_found, invalid=invalid)


def csv_routes(collection: Collection, tmdb: Tmdb):
    """POST /import takes the CSV as the request body; GET /export downloads the Collection in the same format."""
    router = APIRouter()

    @router.post('/import', openapi_extra={'requestBody': {'content': {'text/csv': {'schema': {'type': 'string'}}}, 'required': True}})
    async def import_collection(request: Request) -> ImportResult:
        try:
            # utf-8-sig drops the byte order mark Excel and Numbers start their CSVs with.
            text = (await request.body()).decode('utf-8-sig')
        except UnicodeDecodeError:
            raise HTTPException(400, 'The CSV must be UTF-8') from None
        try:
            return await import_csv(collection, tmdb, text)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

    @router.get('/export', response_class=Response, responses={200: {'content': {'text/csv': {'schema': {'type': 'string'}}}}})
    async def export_collection():
        return Response(
            await export_csv(collection),
            media_type='text/csv; charset=utf-8',
            headers={'content-disposition': 'attachment; filename="popcorn.csv"'},
        )

    return router
