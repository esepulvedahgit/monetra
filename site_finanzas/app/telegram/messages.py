"""Mensajes del bot de Telegram en ES/EN.

Se selecciona el idioma según ``User.language``. Como el webhook no corre dentro
de una sesión autenticada, no se usa Flask-Babel aquí: las cadenas viven en este
diccionario y se eligen con :func:`t`.
"""

_DEFAULT_LANG = 'es'
_SUPPORTED = ('es', 'en')

MESSAGES = {
    'welcome_unlinked': {
        'es': (
            "👋 <b>Bienvenido a Monetra Bot</b>\n\n"
            "Para usar este bot, vincula tu cuenta desde <b>Configuración → Telegram</b> en la app web.\n"
            "Recibirás un enlace de un solo uso para completar la vinculación."
        ),
        'en': (
            "👋 <b>Welcome to Monetra Bot</b>\n\n"
            "To use this bot, link your account from <b>Settings → Telegram</b> in the web app.\n"
            "You'll get a one-time link to complete the connection."
        ),
    },
    'linked_ok': {
        'es': (
            "✅ <b>¡Hola, {name}!</b> Tu cuenta de Monetra quedó vinculada correctamente.\n"
            "Ahora puedes enviar fotos de recibos o texto como \"Café 3.50\" para registrar gastos."
        ),
        'en': (
            "✅ <b>Hi, {name}!</b> Your Monetra account is now linked.\n"
            "You can send receipt photos or text like \"Coffee 3.50\" to log expenses."
        ),
    },
    'already_linked': {
        'es': "ℹ️ Hola {name}, tu cuenta ya está vinculada. Puedes enviar fotos de recibos o texto para registrar gastos.",
        'en': "ℹ️ Hi {name}, your account is already linked. You can send receipt photos or text to log expenses.",
    },
    'code_invalid': {
        'es': "❌ El código de vinculación es inválido o ha expirado. Genera uno nuevo desde Configuración → Telegram.",
        'en': "❌ The linking code is invalid or has expired. Generate a new one from Settings → Telegram.",
    },
    'not_linked': {
        'es': "❌ Tu chat no está vinculado a ninguna cuenta de Monetra. Ve a Configuración → Telegram para activar el bot.",
        'en': "❌ This chat isn't linked to any Monetra account. Go to Settings → Telegram to activate the bot.",
    },
    'ai_not_configured': {
        'es': "⚠️ Tu cuenta de Monetra no tiene configurado el Escáner IA. Ve a Configuración → Escáner IA para habilitarlo.",
        'en': "⚠️ Your Monetra account doesn't have the AI Scanner configured. Go to Settings → AI Scanner to enable it.",
    },
    'ai_quota_exceeded': {
        'es': "⚠️ Has alcanzado el límite diario de escaneos con la IA compartida. Vuelve a intentarlo mañana o activa tu propia clave de IA en Configuración.",
        'en': "⚠️ You've reached today's limit for shared AI scans. Try again tomorrow or activate your own AI key in Settings.",
    },
    'extract_error': {
        'es': "⚠️ No pude extraer los datos del recibo. Intenta con una foto más clara o escribe el gasto manualmente.",
        'en': "⚠️ I couldn't extract the receipt data. Try a clearer photo or type the expense manually.",
    },
    'text_parse_help': {
        'es': (
            "ℹ️ Escribe el gasto en formato: <code>descripción monto</code>\n"
            "Ejemplo: <code>Café 3.50</code> o <code>3.50 café</code>"
        ),
        'en': (
            "ℹ️ Type the expense as: <code>description amount</code>\n"
            "Example: <code>Coffee 3.50</code> or <code>3.50 coffee</code>"
        ),
    },
    'cancelled': {
        'es': "❌ Transacción cancelada.",
        'en': "❌ Transaction cancelled.",
    },
    'saved': {
        'es': "✅ Gasto registrado: <b>{description}</b> — <b>{amount}</b>",
        'en': "✅ Expense saved: <b>{description}</b> — <b>{amount}</b>",
    },
    'pending_expired': {
        'es': "⏱️ Esta transacción ya expiró. Envía el recibo de nuevo.",
        'en': "⏱️ This transaction has expired. Send the receipt again.",
    },
    'confirm_card': {
        'es': (
            "📋 <b>Confirmar gasto</b>\n\n"
            "📝 <b>Descripción:</b> {desc}\n"
            "💰 <b>Monto:</b> {amount}\n"
            "📅 <b>Fecha:</b> {date}\n\n"
            "¿Guardar esta transacción?"
        ),
        'en': (
            "📋 <b>Confirm expense</b>\n\n"
            "📝 <b>Description:</b> {desc}\n"
            "💰 <b>Amount:</b> {amount}\n"
            "📅 <b>Date:</b> {date}\n\n"
            "Save this transaction?"
        ),
    },
    'btn_confirm': {'es': "✅ Confirmar", 'en': "✅ Confirm"},
    'btn_cancel': {'es': "❌ Cancelar", 'en': "❌ Cancel"},
    'toast_saved': {'es': "✅ Guardado", 'en': "✅ Saved"},
    'toast_cancelled': {'es': "❌ Cancelado", 'en': "❌ Cancelled"},
    'toast_expired': {'es': "⏱️ Expirado", 'en': "⏱️ Expired"},
    'toast_error': {'es': "❌ Error", 'en': "❌ Error"},
    'default_description': {'es': "Gasto", 'en': "Expense"},
    'ask_type': {
        'es': "👋 <b>Hola, {name}!</b> ¿Qué tipo de transacción deseas agregar?",
        'en': "👋 <b>Hi, {name}!</b> What type of transaction would you like to add?",
    },
    'btn_type_principal': {'es': "💰 Principal", 'en': "💰 Principal"},
    'btn_type_usd': {'es': "💵 USD", 'en': "💵 USD"},
    'prompt_expense': {
        'es': (
            "✍️ Escribe el gasto en formato: <code>descripción monto</code> o adjunta una imagen.\n"
            "Ejemplo: <code>Café 3000</code>"
        ),
        'en': (
            "✍️ Type the expense as: <code>description amount</code> or attach an image.\n"
            "Example: <code>Coffee 3.50</code>"
        ),
    },
}


def t(key, lang=None):
    """Devuelve el mensaje ``key`` en ``lang`` (es/en), con fallback a español."""
    lang = lang if lang in _SUPPORTED else _DEFAULT_LANG
    entry = MESSAGES.get(key, {})
    return entry.get(lang) or entry.get(_DEFAULT_LANG, '')
