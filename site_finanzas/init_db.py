from app import create_app, db
from app.models import Category, AppConfig, UserEmailConfig, PasswordResetToken, RecurringTransaction, CategoryBudget
from sqlalchemy import inspect, text

app = create_app()

DEFAULT_CATEGORIES = [
    ('Alimentación', 'expense'),
    ('Transporte', 'expense'),
    ('Vivienda', 'expense'),
    ('Servicios', 'expense'),
    ('Salud', 'expense'),
    ('Educación', 'expense'),
    ('Ocio', 'expense'),
    ('Otros', 'expense'),
    ('Sueldo', 'income'),
    ('Freelance', 'income'),
    ('Inversiones', 'income'),
    ('Otros Ingresos', 'income'),
]

FIRST_ADMIN_EMAIL = 'e.esepulvedah@gmail.com'

with app.app_context():
    db.create_all()

    existing_cols = [c['name'] for c in inspect(db.engine).get_columns('users')]
    with db.engine.connect() as conn:
        if 'country' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN country VARCHAR(100) NULL"))
            conn.commit()
            print('Columna country agregada a users.')
        if 'currency_symbol' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN currency_symbol VARCHAR(10) NULL DEFAULT '$'"))
            conn.commit()
            print("Columna currency_symbol agregada a users.")
        if 'currency_code' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN currency_code VARCHAR(10) NULL DEFAULT 'USD'"))
            conn.commit()
            print("Columna currency_code agregada a users.")
        if 'currency_locale' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN currency_locale VARCHAR(20) NULL DEFAULT 'es'"))
            conn.commit()
            print("Columna currency_locale agregada a users.")
        if 'role' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
            conn.commit()
            print("Columna role agregada a users.")
        if 'is_first_admin' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_first_admin BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.commit()
            print("Columna is_first_admin agregada a users.")
        if 'language' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN language VARCHAR(5) NULL DEFAULT 'es'"))
            conn.commit()
            print("Columna language agregada a users.")
        if 'theme' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN theme VARCHAR(20) NULL DEFAULT 'dark'"))
            conn.commit()
            print("Columna theme agregada a users.")
        if 'has_seen_onboarding' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN has_seen_onboarding BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.commit()
            print("Columna has_seen_onboarding agregada a users.")
        if 'help_mode_enabled' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN help_mode_enabled BOOLEAN NOT NULL DEFAULT TRUE"))
            conn.commit()
            print("Columna help_mode_enabled agregada a users.")
        if 'mfa_enabled' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.commit()
            print("Columna mfa_enabled agregada a users.")
        if 'mfa_secret_encrypted' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN mfa_secret_encrypted LONGBLOB NULL"))
            conn.commit()
            print("Columna mfa_secret_encrypted agregada a users.")
        if 'weekly_report_enabled' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN weekly_report_enabled TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna weekly_report_enabled agregada a users.")

        # Assign first admin to the designated user if it exists
        result = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {'email': FIRST_ADMIN_EMAIL}
        ).fetchone()
        if result:
            conn.execute(
                text("UPDATE users SET role='admin', is_first_admin=TRUE WHERE email=:email"),
                {'email': FIRST_ADMIN_EMAIL}
            )
            conn.commit()
            print(f"Usuario {FIRST_ADMIN_EMAIL} configurado como administrador principal.")
        else:
            print(f"Usuario {FIRST_ADMIN_EMAIL} no encontrado; el primer registro será admin.")

    # Initialize AppConfig if it doesn't exist
    if not AppConfig.query.first():
        db.session.add(AppConfig(allow_registration=True))
        db.session.commit()
        print("Configuración global creada (allow_registration=True).")
    else:
        print("Configuración global ya existente.")

    tx_cols = [c['name'] for c in inspect(db.engine).get_columns('transactions')]
    with db.engine.connect() as conn:
        if 'recurring_id' not in tx_cols:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN recurring_id INTEGER NULL"))
            conn.commit()
            print("Columna recurring_id agregada a transactions.")
        if 'is_demo' not in tx_cols:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT FALSE"))
            conn.commit()
            print("Columna is_demo agregada a transactions.")

    # category_budgets table is created by db.create_all() via the model.
    # No ALTER TABLE needed — new table, not a column addition.

    if not Category.query.filter_by(user_id=None).first():
        for name, type_ in DEFAULT_CATEGORIES:
            db.session.add(Category(name=name, type=type_, user_id=None))
        db.session.commit()
        print('Base de datos inicializada con categorías predeterminadas.')
    else:
        print('La base de datos ya estaba inicializada.')
