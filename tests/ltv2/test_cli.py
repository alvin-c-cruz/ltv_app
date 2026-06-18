from ltv2.models.user import User


def test_create_admin(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "root", "r@x.com", "password123"])
    assert result.exit_code == 0
    u = User.query.filter_by(username="root").first()
    assert u is not None and u.role == "admin"
    assert u.check_password("password123")


def test_create_admin_rejects_short_password(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "root", "r@x.com", "short"])
    assert result.exit_code != 0
    assert User.query.filter_by(username="root").first() is None


def test_create_admin_rejects_duplicate(app):
    runner = app.test_cli_runner()
    runner.invoke(args=["create-admin", "root", "r@x.com", "password123"])
    result = runner.invoke(args=["create-admin", "root", "r@x.com", "password123"])
    assert result.exit_code != 0
    assert User.query.filter_by(username="root").count() == 1
