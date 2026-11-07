def test_landing_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"Claimora" in res.data
