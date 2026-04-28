# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Monetra** — personal finance web app. Source lives in `site_finanzas/`. Run via Docker (MySQL + Flask) or locally against a MySQL instance.

## Commands

```bash
# Run locally (from site_finanzas/)
python run.py

# Initialize / migrate the database (safe to re-run — adds missing columns only)
python init_db.py

# Compile translations after editing .po files
pybabel compile -d app/translations

# Extract new translatable strings and update .po files
pybabel extract -F babel.cfg -k _l -o messages.pot .
pybabel update -i messages.pot -d app/translations
# Then edit app/translations/en/LC_MESSAGES/messages.po and compile again

# Docker (from site_finanzas/)
docker build -t monetra .
docker run -p 8000:8000 --env-file .env monetra
```

Required env vars: `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, and either `DATABASE_URL` or the individual `DB_USER / DB_PASSWORD / DB_HOST / DB_PORT / DB_NAME` vars.

## Architecture

### Blueprint structure

```
site_finanzas/
  run.py
  init_db.py             # Schema creation + safe ALTER TABLE migrations
  babel.cfg              # String extraction config
  app/
    __init__.py          # App factory, Babel init, get_locale(), inject_get_locale(), |money and |month_name filters
    models.py            # All SQLAlchemy models
    email_service.py     # SMTP send + Fernet encryption for stored SMTP passwords
    auth/
      routes.py          # /login, /register, /logout, /forgot-password, /reset-password/<token>
      forms.py           # LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm
    main/
      routes.py          # All main views + inject_period() context processor + /set-language/<lang>
      forms.py           # TransactionForm, CategoryForm, BudgetForm, ConfigForm, SMTPConfigForm
    translations/
      es/LC_MESSAGES/messages.po|mo
      en/LC_MESSAGES/messages.po|mo
    templates/
      base.html          # Authenticated layout — navbar, period selector, ES|EN in user dropdown
      auth_base.html     # Unauthenticated layout — floating ES|EN switcher
      main/              # dashboard, transactions, categories, budget, global_dashboard, transaction_form, settings
      auth/              # login, register, forgot_password, reset_password
```

### Context processor (`inject_period`)

Defined in `main/routes.py`, runs on every authenticated request. Injects into all templates: `sel_year`, `sel_month`, `available_years`, `month_names_nav` (locale-aware), `is_tx_page`, `currency_symbol / code / locale / decimals`.

### i18n rules

- **Route-level strings** (flash messages, computed titles): `from flask_babel import gettext as _` → `_('string')`
- **Form field definitions** (module-level): `from flask_babel import lazy_gettext as _l` → `_l('string')`
- **Templates**: `{{ _('string') }}` or `{{ _('Hello %(name)s', name=x) }}`
- **Month names**: Always generated at request time via `babel.dates.get_month_names(style, locale=str(get_locale()))`. Never hardcode Spanish month names in Python.
- **Form choices that need translation** (type select, month select): set `form.field.choices` dynamically in the route *before* calling `validate_on_submit()`, not in the form class.
- `get_locale()` is exposed to Jinja2 via `inject_get_locale` context processor in `__init__.py`. Flask-Babel 3.x does **not** inject it automatically.
- Locale priority: `current_user.language` → `session['lang']` → `Accept-Language` header → `'es'`
- Language switch: `GET /set-language/<lang>` (no `@login_required`) — saves to `user.language` if authenticated, else `session['lang']`
- After adding strings to templates or Python files, run the full extract → update → edit → compile cycle.

### Database migrations

`init_db.py` handles schema migrations using `sqlalchemy.inspect` + raw `ALTER TABLE`. Always add new columns there with an existence check:

```python
if 'new_col' not in existing_cols:
    conn.execute(text("ALTER TABLE users ADD COLUMN new_col VARCHAR(X) NULL DEFAULT 'val'"))
    conn.commit()
```

### Chart.js pattern (critical)

Every `<canvas>` **must** be wrapped in a fixed-height container; otherwise Chart.js enters a resize feedback loop:

```html
<div style="position: relative; height: 320px; width: 100%;">
    <canvas id="myChart"></canvas>
</div>
```

Always include in every Chart options object:

```js
responsive: true,
maintainAspectRatio: false,
resizeDelay: 200,
```

Never put `min-height` or `max-height` directly on `<canvas>`.

### Navbar z-index

`.monetra-navbar` has `backdrop-filter` which creates a CSS stacking context. It must have `position: relative; z-index: 1030` in `style.css` or dropdowns will render behind page content (chart wrappers also use `position: relative`).

### User model key fields

`language` (VARCHAR 5, default `'es'`), `currency_symbol`, `currency_code`, `currency_locale`, `country`, `role` (`'admin'` / `'user'`), `is_first_admin`.
