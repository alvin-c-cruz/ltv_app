import click
from flask.cli import with_appcontext
from ltv2.extensions import db
from ltv2.models.user import User


@click.command("create-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
@with_appcontext
def create_admin(username, email, password):
    if len(password) < 8:
        raise click.ClickException("Password must be at least 8 characters.")
    if User.query.filter_by(username=username).first():
        raise click.ClickException(f"User {username!r} already exists.")
    u = User(username=username, email=email, role="admin")
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    click.echo(f"Created admin {username!r}.")
