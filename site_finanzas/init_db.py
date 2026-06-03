from app import create_app, db
from app.models import Category, AppConfig, UserEmailConfig, PasswordResetToken, EmailActivationToken, RecurringTransaction, CategoryBudget, UserSeenAnnouncement, DemoState, CustomBudget, AuditLog, UsdCategory, UsdTransaction, UsdBudget, UserAIConfig, ApiToken  # noqa: F401
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

DEFAULT_CATEGORY_COLORS = {
    'Alimentación':   '#00C896',
    'Transporte':     '#F2C94C',
    'Vivienda':       '#38BDF8',
    'Servicios':      '#EF4444',
    'Salud':          '#8B5CF6',
    'Educación':      '#F97316',
    'Ocio':           '#FB7185',
    'Otros':          '#1FE0B0',
    'Sueldo':         '#34D399',
    'Freelance':      '#FFD76A',
    'Inversiones':    '#60A5FA',
    'Otros Ingresos': '#A78BFA',
}

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
        if 'insights_panel_enabled' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN insights_panel_enabled TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna insights_panel_enabled agregada a users.")
        if 'usd_rate' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN usd_rate DECIMAL(12,4) NULL"))
            conn.commit()
            print("Columna usd_rate agregada a users.")
        if 'email_verified' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified TINYINT(1) NOT NULL DEFAULT 0"))
            conn.execute(text("UPDATE users SET email_verified = 1"))
            conn.commit()
            print("Columna email_verified agregada a users (usuarios existentes marcados como verificados).")
        if 'email_verified_at' not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified_at DATETIME NULL"))
            conn.execute(text("UPDATE users SET email_verified_at = NOW() WHERE email_verified = 1"))
            conn.commit()
            print("Columna email_verified_at agregada a users.")

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

    rec_cols = [c['name'] for c in inspect(db.engine).get_columns('recurring_transactions')]
    with db.engine.connect() as conn:
        if 'end_date' not in rec_cols:
            conn.execute(text("ALTER TABLE recurring_transactions ADD COLUMN end_date DATE NULL"))
            conn.commit()
            print("Columna end_date agregada a recurring_transactions.")
        if 'is_demo' not in rec_cols:
            conn.execute(text("ALTER TABLE recurring_transactions ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna is_demo agregada a recurring_transactions.")

    savings_cols = [c['name'] for c in inspect(db.engine).get_columns('savings_goals')]
    with db.engine.connect() as conn:
        if 'is_demo' not in savings_cols:
            conn.execute(text("ALTER TABLE savings_goals ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna is_demo agregada a savings_goals.")

    demo_state_cols = [c['name'] for c in inspect(db.engine).get_columns('demo_state')]
    with db.engine.connect() as conn:
        if 'demo_years' not in demo_state_cols:
            conn.execute(text("ALTER TABLE demo_state ADD COLUMN demo_years TEXT NULL"))
            conn.execute(text("UPDATE demo_state SET demo_years = '[]' WHERE demo_years IS NULL"))
            conn.execute(text("ALTER TABLE demo_state MODIFY COLUMN demo_years TEXT NOT NULL"))
            conn.commit()
            print("Columna demo_years agregada a demo_state.")

    cat_cols = [c['name'] for c in inspect(db.engine).get_columns('categories')]
    with db.engine.connect() as conn:
        if 'color' not in cat_cols:
            conn.execute(text("ALTER TABLE categories ADD COLUMN color VARCHAR(7) NULL"))
            conn.commit()
            print('Columna color agregada a categories.')

    if not Category.query.filter_by(user_id=None).first():
        for name, type_ in DEFAULT_CATEGORIES:
            color = DEFAULT_CATEGORY_COLORS.get(name, '#00C896')
            db.session.add(Category(name=name, type=type_, user_id=None, color=color))
        db.session.commit()
        print('Base de datos inicializada con categorías predeterminadas.')
    else:
        updated = 0
        for name, color in DEFAULT_CATEGORY_COLORS.items():
            cat = Category.query.filter_by(user_id=None, name=name).first()
            if cat and not cat.color:
                cat.color = color
                updated += 1
        if updated:
            db.session.commit()
            print(f'{updated} categorías predeterminadas actualizadas con color.')
        else:
            print('La base de datos ya estaba inicializada.')

    # ── CategoryBudget: add year+month columns and update unique constraint ──────
    cb_cols = [c['name'] for c in inspect(db.engine).get_columns('category_budgets')]
    with db.engine.connect() as conn:
        if 'year' not in cb_cols:
            conn.execute(text("ALTER TABLE category_budgets ADD COLUMN year INT NULL"))
            conn.commit()
            print("Columna year agregada a category_budgets.")
        if 'month' not in cb_cols:
            conn.execute(text("ALTER TABLE category_budgets ADD COLUMN month INT NULL"))
            conn.commit()
            print("Columna month agregada a category_budgets.")
        conn.execute(text(
            "UPDATE category_budgets SET year = YEAR(NOW()), month = MONTH(NOW()) "
            "WHERE year IS NULL OR month IS NULL"
        ))
        conn.commit()

    cb_cols_now = {c['name']: c for c in inspect(db.engine).get_columns('category_budgets')}
    with db.engine.connect() as conn:
        if cb_cols_now.get('year', {}).get('nullable', True):
            conn.execute(text("ALTER TABLE category_budgets MODIFY COLUMN year INT NOT NULL"))
            conn.commit()
            print("Columna year NOT NULL en category_budgets.")
        if cb_cols_now.get('month', {}).get('nullable', True):
            conn.execute(text("ALTER TABLE category_budgets MODIFY COLUMN month INT NOT NULL"))
            conn.commit()
            print("Columna month NOT NULL en category_budgets.")

    cb_constraints = {uc['name'] for uc in inspect(db.engine).get_unique_constraints('category_budgets')}
    old_exists = 'uq_user_category_budget' in cb_constraints
    new_exists = 'uq_user_year_month_cat_budget' in cb_constraints
    with db.engine.connect() as conn:
        if old_exists and not new_exists:
            # Drop old + add new in one atomic statement — MySQL won't allow dropping
            # the old index alone while a FK depends on it; the combined statement works
            # because MySQL sees user_id is still covered by the new index.
            conn.execute(text(
                "ALTER TABLE category_budgets "
                "DROP INDEX uq_user_category_budget, "
                "ADD CONSTRAINT uq_user_year_month_cat_budget UNIQUE (user_id, year, month, category_id)"
            ))
            conn.commit()
            print("Constraint uq_user_category_budget reemplazado por uq_user_year_month_cat_budget.")
        elif old_exists:
            conn.execute(text("ALTER TABLE category_budgets DROP INDEX uq_user_category_budget"))
            conn.commit()
            print("Constraint uq_user_category_budget eliminado.")
        elif not new_exists:
            conn.execute(text(
                "ALTER TABLE category_budgets ADD CONSTRAINT uq_user_year_month_cat_budget "
                "UNIQUE (user_id, year, month, category_id)"
            ))
            conn.commit()
            print("Constraint uq_user_year_month_cat_budget creado.")

    # Ensure global fallback category for custom budget deletions
    if not Category.query.filter_by(user_id=None, name='Sin categoría').first():
        db.session.add(Category(name='Sin categoría', type='expense', user_id=None, color='#78909C'))
        db.session.commit()
        print("Categoría global 'Sin categoría' creada.")

    # ── AuditLog: table created by db.create_all() via the model. ─────────────
    # Add any future column migrations here using the ALTER TABLE pattern.
    if 'audit_logs' in inspect(db.engine).get_table_names():
        print("Tabla audit_logs verificada.")

    # ── USD section: tables created by db.create_all() via the models. ────────
    tbls = inspect(db.engine).get_table_names()
    for t in ('usd_categories', 'usd_transactions', 'usd_budgets'):
        if t in tbls:
            print(f"Tabla {t} verificada.")

    usd_category_cols = [c['name'] for c in inspect(db.engine).get_columns('usd_categories')]
    usd_transaction_cols = [c['name'] for c in inspect(db.engine).get_columns('usd_transactions')]
    usd_budget_cols = [c['name'] for c in inspect(db.engine).get_columns('usd_budgets')]
    with db.engine.connect() as conn:
        if 'is_demo' not in usd_category_cols:
            conn.execute(text("ALTER TABLE usd_categories ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna is_demo agregada a usd_categories.")
        if 'is_demo' not in usd_transaction_cols:
            conn.execute(text("ALTER TABLE usd_transactions ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna is_demo agregada a usd_transactions.")
        if 'is_demo' not in usd_budget_cols:
            conn.execute(text("ALTER TABLE usd_budgets ADD COLUMN is_demo TINYINT(1) NOT NULL DEFAULT 0"))
            conn.commit()
            print("Columna is_demo agregada a usd_budgets.")

    # ── transactions.description: migrate VARCHAR(200) → TEXT ─────────────────
    tx_desc_col = {c['name']: c for c in inspect(db.engine).get_columns('transactions')}.get('description')
    if tx_desc_col is not None:
        col_type_str = str(tx_desc_col['type']).upper()
        if 'TEXT' not in col_type_str:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE transactions MODIFY COLUMN description TEXT NULL"))
                conn.commit()
            print("Columna description en transactions migrada a TEXT.")
        else:
            print("Columna description ya es TEXT.")

    # ── user_ai_config: table created by db.create_all() via the model. ───────
    if 'user_ai_config' in inspect(db.engine).get_table_names():
        print("Tabla user_ai_config verificada.")

    # ── Default 'Scanner' category (global, fallback for receipt scanning) ────
    if not Category.query.filter_by(user_id=None, name='Scanner').first():
        db.session.add(Category(name='Scanner', type='expense', user_id=None, color='#06B6D4'))
        db.session.commit()
        print("Categoría global 'Scanner' creada.")
    else:
        # Ensure color is set if missing
        scanner_cat = Category.query.filter_by(user_id=None, name='Scanner').first()
        if scanner_cat and not scanner_cat.color:
            scanner_cat.color = '#06B6D4'
            db.session.commit()
            print("Color de categoría 'Scanner' actualizado.")
