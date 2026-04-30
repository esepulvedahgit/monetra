import click
from flask.cli import with_appcontext

from app.demo_data.service import generate_demo_data, reset_demo_data
from app.models import User


def register_cli(app):
    @app.cli.group('demo')
    def demo_group():
        """Gestión de datos demo."""

    @demo_group.command('load')
    @click.option('--user-id', type=int, default=None, help='ID del usuario (por defecto: primer admin)')
    @with_appcontext
    def demo_load(user_id):
        """Carga transacciones demo para un usuario."""
        uid = user_id or _first_user_id()
        if uid is None:
            click.echo('No hay usuarios registrados.')
            return
        ok, msg = generate_demo_data(uid)
        click.echo(msg)

    @demo_group.command('reset')
    @click.option('--user-id', type=int, default=None, help='ID del usuario (por defecto: primer admin)')
    @with_appcontext
    def demo_reset(user_id):
        """Elimina transacciones demo de un usuario."""
        uid = user_id or _first_user_id()
        if uid is None:
            click.echo('No hay usuarios registrados.')
            return
        count = reset_demo_data(uid)
        click.echo(f'{count} registros demo eliminados.')


def _first_user_id():
    user = User.query.filter_by(role='admin').order_by(User.id).first()
    if not user:
        user = User.query.order_by(User.id).first()
    return user.id if user else None
