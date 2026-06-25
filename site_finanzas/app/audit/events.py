# Canonical event type constants
# Format: <category>.<action>

# Auth events
AUTH_LOGIN_SUCCESS    = 'auth.login_success'
AUTH_LOGIN_FAIL       = 'auth.login_fail'
AUTH_LOGOUT           = 'auth.logout'
AUTH_REGISTER         = 'auth.register'
AUTH_PASSWORD_CHANGE  = 'auth.password_change'
AUTH_MFA_ENABLED      = 'auth.mfa_enabled'
AUTH_MFA_DISABLED     = 'auth.mfa_disabled'
AUTH_PASSWORD_RESET_REQ  = 'auth.password_reset_req'
AUTH_PASSWORD_RESET_DONE = 'auth.password_reset_done'
AUTH_EMAIL_VERIFY        = 'auth.email_verify'
AUTH_EMAIL_RESEND        = 'auth.email_resend'
AUTH_PIN_ENABLED         = 'auth.pin_enabled'
AUTH_PIN_DISABLED        = 'auth.pin_disabled'

# Application events
APP_ERROR_500    = 'app.error_500'
APP_RATE_LIMITED = 'app.rate_limited'

# Config/settings events
CONFIG_SETTINGS      = 'config.settings'
CONFIG_SMTP          = 'config.smtp'
CONFIG_REGISTRATION  = 'config.registration'

# Admin events
ADMIN_DEMO_LOAD         = 'admin.demo_load'
ADMIN_DEMO_RESET        = 'admin.demo_reset'
ADMIN_DB_EXPORT         = 'admin.db_export'
ADMIN_DB_RESTORE        = 'admin.db_restore'
ADMIN_ACCOUNT_SUSPENDED   = 'admin.account_suspended'
ADMIN_ACCOUNT_REACTIVATED = 'admin.account_reactivated'
ADMIN_ACCOUNT_DELETED     = 'admin.account_deleted'
ADMIN_AI_ACCESS_GRANTED   = 'admin.ai_access_granted'
ADMIN_AI_ACCESS_REVOKED   = 'admin.ai_access_revoked'

# Telegram events
TELEGRAM_LINK    = 'telegram.link'
TELEGRAM_UNLINK  = 'telegram.unlink'
TELEGRAM_TX_CREATE = 'telegram.tx_create'

# Map prefix → display label + pastel color
CATEGORY_META = {
    'auth':   {'label': 'Autenticación', 'color': 'rgba(56,189,248,0.25)',  'border': '#38BDF8'},
    'app':    {'label': 'Errores App',   'color': 'rgba(252,165,165,0.25)', 'border': '#FCA5A5'},
    'config': {'label': 'Configuración', 'color': 'rgba(252,211,77,0.25)',  'border': '#FCD34D'},
    'admin':  {'label': 'Admin',         'color': 'rgba(196,181,253,0.25)', 'border': '#C4B5FD'},
    'telegram': {'label': 'Telegram', 'color': 'rgba(0,136,204,0.20)', 'border': '#0088CC'},
}


def category_of(event_type: str) -> str:
    return event_type.split('.')[0] if '.' in event_type else 'app'
