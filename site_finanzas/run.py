import os
from app import create_app, db
from app.models import User, Category, Transaction, Budget, UserYear

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Category': Category,
            'Transaction': Transaction, 'Budget': Budget, 'UserYear': UserYear}


if __name__ == '__main__':
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=os.environ.get('FLASK_DEBUG', '0') == '1'
    )
