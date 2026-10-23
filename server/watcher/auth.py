import hashlib
import hmac
import secrets
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .api import Api

# A token unused for this long stops working. Each use pushes it back.
TTL = "interval '90 days'"

_bearer = HTTPBearer(auto_error=False)


def _hash(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


class Login(Api):
    password: str


class Token(Api):
    token: str


def create_auth(pool: asyncpg.Pool, password: str):
    """One password, set in the environment, trades for bearer tokens. Returns the routes and the dependency that guards the rest."""

    async def require_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]):
        token = credentials.credentials if credentials else ''
        if not await pool.fetchval(
            f'update auth_token set expires_at = now() + {TTL} where token_hash = $1 and expires_at > now() returning true', _hash(token)
        ):
            raise HTTPException(401, 'Unauthorized')
        return token

    router = APIRouter()

    # ponytail: no rate limit; the password is long and random, so guessing it is hopeless anyway.
    @router.post('/login')
    async def login(body: Login) -> Token:
        if not hmac.compare_digest(body.password.encode(), password.encode()):
            raise HTTPException(401, 'Wrong password')
        token = secrets.token_urlsafe(32)
        await pool.execute('delete from auth_token where expires_at <= now()')
        await pool.execute(f'insert into auth_token (token_hash, expires_at) values ($1, now() + {TTL})', _hash(token))
        return Token(token=token)

    @router.post('/logout', status_code=204)
    async def logout(token: Annotated[str, Depends(require_token)]):
        await pool.execute('delete from auth_token where token_hash = $1', _hash(token))

    return router, require_token
