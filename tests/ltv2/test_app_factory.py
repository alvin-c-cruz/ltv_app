def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_index_renders(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"LTV2" in resp.data


def test_test_config_uses_memory_db(app):
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
    assert "LTV Stocks.db" not in app.config["SQLALCHEMY_DATABASE_URI"]
