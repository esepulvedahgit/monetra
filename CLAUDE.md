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

# Docker dev (from docker/)
docker compose up --build

# Docker prod (from docker/)
docker compose -f docker-compose.prod.yml up -d

# Build ARM64 image (requires multiplatform builder set up first)
docker buildx build --platform linux/arm64 -t monetra:1.8-arm64 --load ../site_finanzas
```

**Environment variables:** All are defined in `docker/.env` (single source of truth for both dev and prod). Required: `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `MYSQL_ROOT_PASSWORD`. Optional: `JWT_SECRET_KEY`, `CORS_ORIGINS`, `FLASK_DEBUG`.

**Line endings:** `.gitattributes` enforces `eol=crlf` for all files except `*.sh` (`eol=lf`). Never normalize `entrypoint.sh` to CRLF — Linux containers cannot execute scripts with CRLF shebangs.

## Architecture

### Blueprint structure

```
site_finanzas/
  run.py
  init_db.py             # Schema creation + safe ALTER TABLE migrations + default category seeding
  entrypoint.sh          # Docker: waits for MySQL → init_db.py → gunicorn (1 worker)
  babel.cfg
  config.py              # Config class — reads all secrets from env vars, fallback auto-generates keys
  app/
    __init__.py          # App factory, extensions init, get_locale(), |money and |month_name filters,
                         # 404/429/500 error handlers (db.session.rollback on 500)
    models.py            # All SQLAlchemy models (12 total)
    announcements.py     # Version announcement registry — CURRENT_ANNOUNCEMENT + ANNOUNCEMENTS dict
    email_service.py     # SMTP send + Fernet encryption for SMTP passwords and MFA secrets
    scheduler.py         # APScheduler: weekly Excel report job (Mondays 10:00 UTC)
    auth/                # /login, /register, /logout, /forgot-password, /reset-password, MFA verify
                         # All POST endpoints rate-limited via @limiter.limit (see Rate Limiting section)
    main/
      routes.py          # All web views (~1300 lines) + inject_period() + inject_announcement() context processors
      forms.py           # 9 WTForms: Transaction, Category, Budget, CategoryBudget,
                         # SavingsGoal, RecurringTransaction, Config, SMTP, ChangePassword
    api/                 # REST API blueprint at /api/v1 — JWT auth, CSRF exempt
    export/              # Excel report generator (xlsxwriter), route at /export/excel
    demo_data/           # Admin blueprint at /admin/demo — load/reset demo transactions
    services/
      finance.py         # Business logic and shared DB queries (used by both web views and API)
    templates/
      base.html          # Authenticated layout — navbar, period selector, idle timeout modal,
                         # announcement modal (shown once per version to existing users)
      auth_base.html     # Unauthenticated layout — has {% block scripts %}{% endblock %} after Bootstrap bundle for page-specific JS
      errors/
        base_error.html  # Standalone error base (does NOT extend base.html — safe for 500s)
        404.html         # Extends base_error.html
        429.html         # Extends base_error.html — shown after rate limit exceeded
        500.html         # Extends base_error.html
      main/              # dashboard, transactions, categories, budget, global_dashboard,
                         # recurrentes, metas, configurar, transaction_form, recurrente_form, meta_form
      auth/              # login, register, forgot_password, reset_password, mfa_verify
      partials/
        hint.html        # Reusable hint icon macro
        announcements/   # Per-version announcement modal content (v1_7.html, v1_8.html, ...)
```

### Models (app/models.py)

| Model | Table | Key notes |
|---|---|---|
| `User` | `users` | `role` ('admin'/'user'), `is_first_admin`, `language`, `theme`, `currency_*`, `mfa_enabled`, `weekly_report_enabled` |
| `Category` | `categories` | `user_id=NULL` → global/default; `color VARCHAR(7)` for per-category hex color |
| `Transaction` | `transactions` | `is_demo` flag for demo data; `recurring_id` FK to RecurringTransaction |
| `Budget` | `budgets` | Monthly budget per user/year/month |
| `CategoryBudget` | `category_budgets` | Per-category monthly limit, max 3 per user |
| `RecurringTransaction` | `recurring_transactions` | Auto-generates Transaction entries on dashboard load |
| `SavingsGoal` | `savings_goals` | `progress_pct`, `remaining`, `days_left` as computed properties |
| `UserYear` | `user_years` | Explicit year tracking per user |
| `UserEmailConfig` | `user_email_config` | SMTP config with Fernet-encrypted password |
| `AppConfig` | `app_config` | Single-row global config (`allow_registration`) |
| `PasswordResetToken` | `password_reset_token` | Expiring tokens for password recovery |
| `UserSeenAnnouncement` | `user_seen_announcements` | Tracks which version announcement each user has seen; UNIQUE(user_id, announcement_key) |

### Context processors

**`inject_period`** — defined as `@main.app_context_processor` in `main/routes.py` — runs for **all** templates. Injects: `sel_year`, `sel_month`, `available_years`, `next_year`, `month_names_nav` (locale-aware), `is_tx_page`, `currency_symbol / code / locale / decimals`.

**`inject_announcement`** — also in `main/routes.py` — injects `announcement_to_show` (key string or `None`). Returns `None` for unauthenticated users, new users (created on or after `released_at`), and users who already saw the announcement. Wrapped in `try/except` so a missing DB table never breaks the app.

Error page templates (`errors/`) bypass both processors because they are standalone.

### Announcement system

To release a new version announcement:

1. Update `CURRENT_ANNOUNCEMENT` and add an entry in `app/announcements.py`:
```python
CURRENT_ANNOUNCEMENT = 'v1.9'
ANNOUNCEMENTS = {
    ...
    'v1.9': {'key': 'v1.9', 'released_at': datetime(2026, N, N, tzinfo=timezone.utc)},
}
```
2. Create `templates/partials/announcements/v1_9.html` with modal header/body/footer blocks.
3. Run `init_db.py` — the `user_seen_announcements` table must exist.

The modal is shown once: `base.html` fires `fetch POST /announcements/<key>/seen` on `show.bs.modal`, which writes a `UserSeenAnnouncement` row. New users (created ≥ `released_at`) skip it automatically — no DB write needed.

### Rate limiting

Flask-Limiter uses `get_remote_address` (client IP) as key, stored **in-memory**. Gunicorn runs **1 worker** (`entrypoint.sh`) — critical: multiple workers would split the in-memory counter and allow bypass. Do not increase workers without switching to a shared storage backend (Redis).

| Route | Limit |
|---|---|
| `POST /register` | 5 / minute |
| `POST /login` | 5 / minute |
| `POST /mfa-verify` | 5 / minute |
| `POST /forgot-password` | 3 / 15 minutes |
| `POST /reset-password/<token>` | 5 / 15 minutes |

All limits apply to POST only (`methods=['POST']`). GET requests are never counted.

### Category color system

Two palettes defined at the top of `main/routes.py`:
- `DEFAULT_CATEGORY_COLORS` — dict mapping the 12 default category names to specific vivid hex colors
- `DEFAULT_PALETTE` — 21 vivid colors (for global categories, `user_id=NULL`)
- `CUSTOM_PALETTE` — 21 compound/muted colors (for user-created categories, `user_id=current_user.id`)

`_next_custom_color(user_id)` walks `CUSTOM_PALETTE` and returns the first color not already used by the user's categories. The `color` column is migrated via `init_db.py`. Dashboard charts (`dashboard()` and `global_dashboard()`) use the stored `category.color` in their queries — the GROUP BY must include `Category.id, Category.name, Category.color`.

### REST API (`app/api/`)

JWT-based (Flask-JWT-Extended), registered as `api_v1` blueprint at `/api/v1`, exempted from CSRF. Endpoints: auth (login/refresh/logout/me), transactions, budgets, categories, dashboard/summary, recurring, savings. All authentication uses `@api_login_required` from `app/api/decorators.py`, not Flask-Login's `@login_required`. Business logic is shared with web views via `app/services/finance.py`.

### Database migrations

`init_db.py` handles all schema migrations with `sqlalchemy.inspect` + raw `ALTER TABLE`. Pattern for every new column:

```python
existing_cols = [c['name'] for c in inspect(db.engine).get_columns('table_name')]
with db.engine.connect() as conn:
    if 'new_col' not in existing_cols:
        conn.execute(text("ALTER TABLE t ADD COLUMN new_col VARCHAR(X) NULL DEFAULT 'val'"))
        conn.commit()
```

Default categories are seeded on first run with `color` values from `DEFAULT_CATEGORY_COLORS`. Re-running `init_db.py` retroactively fills `color=NULL` rows.

After adding a new model, import it in `init_db.py` so `db.create_all()` picks up the new table.

### Scheduler

`app/scheduler.py` uses APScheduler to send weekly Excel reports. It is started in `create_app()` with a guard against double-start under Werkzeug's reloader:

```python
if not app.testing:
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        from app.scheduler import init_scheduler
        init_scheduler(app)
```

### Session-based inter-request communication

When a category deletion is blocked by associated data, the route stores details in session instead of using a flash message:

```python
session['_cat_blocked'] = {'name': ..., 'tx': count, 'rec': count, 'cb': count}
```

The `categories()` route pops this with `session.pop('_cat_blocked', None)` and passes it to the template, which renders a Bootstrap modal. Use this pattern for any case where a redirect needs to carry structured data to the next page.

### i18n rules

- **Route-level strings** (flash messages, computed titles): `from flask_babel import gettext as _` → `_('string')`
- **Form field definitions** (module-level): `from flask_babel import lazy_gettext as _l` → `_l('string')`
- **Templates**: `{{ _('string') }}` or `{{ _('Hello %(name)s', name=x) }}`
- **Month names**: Always via `babel.dates.get_month_names(style, locale=str(get_locale()))` at request time. Never hardcode.
- **Form choices that need translation**: set `form.field.choices` dynamically in the route *before* `validate_on_submit()`, not in the form class.
- `get_locale()` is exposed to Jinja2 via `inject_get_locale` context processor in `__init__.py`. Flask-Babel 3.x does **not** inject it automatically.
- Locale priority: `current_user.language` → `session['lang']` → `Accept-Language` → `'es'`
- After adding strings: run the full extract → update → edit .po → compile cycle.

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

### Error pages

`errors/base_error.html` is a fully standalone template — it does NOT extend `base.html`. This is intentional: a 500 error may have occurred in the DB or context processor layer, so extending `base.html` would cause a secondary failure. Error templates apply the user's theme via `data-theme="{{ current_user.theme if current_user.is_authenticated else 'dark' }}"` and use only CSS variables from `themes.css`.

All three handlers (404, 429, 500) are registered in `app/__init__.py`. The 429 template uses `--monetra-gold` as the accent color to distinguish it visually from 404 (primary) and 500 (danger/red).
