from conftest import PASSWORD


async def test_the_password_trades_for_a_token_that_signs_requests_in(client):
    res = await client.post('/api/auth/login', json={'password': PASSWORD})
    assert res.status_code == 200
    token = res.json()['token']
    assert (await client.get('/api/reels', headers={'authorization': f'Bearer {token}'})).status_code == 200


async def test_a_wrong_password_gets_no_token(client):
    res = await client.post('/api/auth/login', json={'password': 'guess'})
    assert res.status_code == 401
    assert res.json() == {'error': 'Wrong password'}


async def test_requests_without_a_valid_token_are_refused(client):
    assert (await client.get('/api/reels')).status_code == 401
    assert (await client.get('/api/reels', headers={'authorization': 'Bearer made-up'})).status_code == 401


async def test_logging_out_ends_the_token(api):
    assert (await api.post('/api/auth/logout')).status_code == 204
    assert (await api.get('/api/reels')).status_code == 401


async def test_an_expired_token_is_refused(api, pool):
    await pool.execute("update auth_token set expires_at = now() - interval '1 second'")
    assert (await api.get('/api/reels')).status_code == 401
