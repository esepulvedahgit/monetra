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
            "Ahora puedes enviar fotos de recibos o texto como \"Café 3.50\" para registrar gastos.\n"
            "Escribe /carrito para llevar la cuenta de una compra en el supermercado."
        ),
        'en': (
            "✅ <b>Hi, {name}!</b> Your Monetra account is now linked.\n"
            "You can send receipt photos or text like \"Coffee 3.50\" to log expenses.\n"
            "Type /cart to keep track of a supermarket purchase."
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
    # ── Mi Carrito ────────────────────────────────────────────────────────────
    'btn_type_cart': {'es': "🛒 Carrito", 'en': "🛒 Cart"},
    'cart_started': {
        'es': (
            "🛒 <b>Carrito iniciado en {store}</b>\n\n"
            "¿Cómo quieres agregar los productos?\n"
            "✋ <b>Manual</b>: confirmas cada producto antes de sumarlo.\n"
            "⚡ <b>Automático</b>: se suma apenas lo envías y ves el total al instante."
        ),
        'en': (
            "🛒 <b>Cart started at {store}</b>\n\n"
            "How do you want to add products?\n"
            "✋ <b>Manual</b>: you confirm each product before it's added.\n"
            "⚡ <b>Automatic</b>: it's added as soon as you send it and you see the total right away."
        ),
    },
    'btn_cart_mode_manual': {'es': "✋ Manual", 'en': "✋ Manual"},
    'btn_cart_mode_auto': {'es': "⚡ Automático", 'en': "⚡ Automatic"},
    'cart_mode_set_manual': {
        'es': (
            "✋ <b>Modo manual.</b> Envía cada producto como texto (<code>Leche 1290</code>, "
            "<code>2 x 990 yogurt</code>) o una foto de la etiqueta de precio. Lo confirmas antes de sumarlo.\n\n"
            "Si llevas varias unidades, escribe la cantidad en el texto de la foto (ej: <code>3</code>) "
            "o usa 🔢 Cantidad. Para descartar la compra, escribe /cancelar."
        ),
        'en': (
            "✋ <b>Manual mode.</b> Send each product as text (<code>Milk 3.50</code>, "
            "<code>2 x 1.20 yogurt</code>) or a photo of the price label. You confirm it before it's added.\n\n"
            "If you take several units, type the quantity as the photo caption (e.g. <code>3</code>) "
            "or use 🔢 Quantity. To discard the purchase, type /cancel."
        ),
    },
    'cart_mode_set_auto': {
        'es': (
            "⚡ <b>Modo automático.</b> Envía cada producto como texto (<code>Leche 1290</code>, "
            "<code>2 x 990 yogurt</code>) o una foto de la etiqueta de precio. Se suma al carrito al instante; "
            "si algo quedó mal, usa ↩️ Quitar último.\n\n"
            "Si llevas varias unidades, escribe la cantidad en el texto de la foto (ej: <code>3</code>) "
            "o usa 🔢 Cantidad. Para descartar la compra, escribe /cancelar."
        ),
        'en': (
            "⚡ <b>Automatic mode.</b> Send each product as text (<code>Milk 3.50</code>, "
            "<code>2 x 1.20 yogurt</code>) or a photo of the price label. It's added right away; "
            "if something is wrong, use ↩️ Remove last.\n\n"
            "If you take several units, type the quantity as the photo caption (e.g. <code>3</code>) "
            "or use 🔢 Quantity. To discard the purchase, type /cancel."
        ),
    },
    'cart_mode_manual': {'es': "✋ manual", 'en': "✋ manual"},
    'cart_mode_auto': {'es': "⚡ automático", 'en': "⚡ automatic"},
    'btn_cart_switch_manual': {'es': "✋ Cambiar a manual", 'en': "✋ Switch to manual"},
    'btn_cart_switch_auto': {'es': "⚡ Cambiar a automático", 'en': "⚡ Switch to automatic"},
    'cart_resumed': {
        'es': "🛒 Tienes un carrito en curso en {store}: <b>{total}</b> ({count} productos), modo {mode}. Sigue enviando productos.",
        'en': "🛒 You have a cart in progress at {store}: <b>{total}</b> ({count} products), {mode} mode. Keep sending products.",
    },
    'cart_item_card': {
        'es': "🛒 <b>Confirmar producto</b>\n\n📝 {name}\n💰 <b>{amount}</b>{extra}\n\n¿Agregar al carrito?",
        'en': "🛒 <b>Confirm product</b>\n\n📝 {name}\n💰 <b>{amount}</b>{extra}\n\nAdd to cart?",
    },
    'cart_qty_line': {'es': "\n🔢 {qty} × {unit}", 'en': "\n🔢 {qty} × {unit}"},
    'cart_offer_line': {'es': "\n🏷 Oferta: <b>{amount}</b>{text}", 'en': "\n🏷 Offer: <b>{amount}</b>{text}"},
    'cart_note_line': {'es': "\nℹ️ {note}", 'en': "\nℹ️ {note}"},
    'cart_note_per_kg': {
        'es': "Precio por kg: si pesaste el producto, usa ✏️ Corregir con el monto de la balanza.",
        'en': "Price per kg: if you weighed the product, use ✏️ Fix with the scale amount.",
    },
    'cart_note_per_kg_auto': {
        'es': "Precio por kg: si pesaste el producto, usa ↩️ Quitar último y escribe el monto de la balanza.",
        'en': "Price per kg: if you weighed the product, use ↩️ Remove last and type the scale amount.",
    },
    'cart_auto_offer_line': {
        'es': "\n🏷 Oferta: <b>{amount}</b>{text}. Se sumó el precio normal; si pagas la oferta, usa ↩️ Quitar último y escríbela.",
        'en': "\n🏷 Offer: <b>{amount}</b>{text}. The regular price was added; if you pay the offer, use ↩️ Remove last and type it.",
    },
    'cart_auto_added': {
        'es': "✅ <b>{name}</b> — {amount}{extra}\n\n🛒 <b>Total del carrito: {total}</b>\n📦 {count} productos",
        'en': "✅ <b>{name}</b> — {amount}{extra}\n\n🛒 <b>Cart total: {total}</b>\n📦 {count} products",
    },
    'btn_cart_add': {'es': "✅ Agregar", 'en': "✅ Add"},
    'btn_cart_add_offer': {'es': "🏷 Agregar {amount}", 'en': "🏷 Add {amount}"},
    'btn_cart_fix': {'es': "✏️ Corregir", 'en': "✏️ Fix"},
    'btn_cart_skip': {'es': "❌ Descartar", 'en': "❌ Discard"},
    'cart_added': {
        'es': "✅ <b>{name}</b> — {amount}\n\n🛒 <b>Total del carrito: {total}</b>\n📦 {count} productos",
        'en': "✅ <b>{name}</b> — {amount}\n\n🛒 <b>Cart total: {total}</b>\n📦 {count} products",
    },
    'cart_status': {
        'es': "🛒 <b>Total del carrito: {total}</b>\n📦 {count} productos",
        'en': "🛒 <b>Cart total: {total}</b>\n📦 {count} products",
    },
    'btn_cart_more': {'es': "➕ Agregar otro", 'en': "➕ Add another"},
    'btn_cart_undo': {'es': "↩️ Quitar último", 'en': "↩️ Remove last"},
    'btn_cart_finish': {'es': "🏁 Finalizar", 'en': "🏁 Finish"},
    'btn_cart_cancel': {'es': "🗑 Cancelar", 'en': "🗑 Cancel"},
    'btn_cart_qty': {'es': "🔢 Cantidad", 'en': "🔢 Quantity"},
    'btn_cart_qty_more': {'es': "Más…", 'en': "More…"},
    'cart_qty_prompt': {
        'es': "🔢 ¿Cuántas unidades de <b>{name}</b> llevas? ({unit} c/u)",
        'en': "🔢 How many <b>{name}</b> are you taking? ({unit} each)",
    },
    'cart_qty_set': {'es': "🔢 <b>{name}</b> — {amount}", 'en': "🔢 <b>{name}</b> — {amount}"},
    'cart_qty_unavailable': {
        'es': "ℹ️ Ese producto ya no está en un carrito abierto.",
        'en': "ℹ️ That product is no longer in an open cart.",
    },
    'btn_cart_cancel_empty': {'es': "🗑 Cancelar carrito", 'en': "🗑 Cancel cart"},
    'cart_nothing_to_cancel': {
        'es': "ℹ️ No tienes un carrito abierto. Escribe /carrito para empezar uno.",
        'en': "ℹ️ You don't have an open cart. Type /cart to start one.",
    },
    'cart_prompt_next': {
        'es': "📸 Envía el siguiente producto (texto o foto).",
        'en': "📸 Send the next product (text or photo).",
    },
    'cart_fix_prompt': {
        'es': "✏️ Escribe el producto con el precio correcto. Ejemplo: <code>Leche 1290</code>",
        'en': "✏️ Type the product with the correct price. Example: <code>Milk 3.50</code>",
    },
    'cart_item_skipped': {'es': "❌ Producto descartado.", 'en': "❌ Product discarded."},
    'cart_undone': {'es': "↩️ Quitado: <b>{name}</b> — {amount}", 'en': "↩️ Removed: <b>{name}</b> — {amount}"},
    'cart_nothing_to_undo': {'es': "ℹ️ El carrito está vacío.", 'en': "ℹ️ The cart is empty."},
    'cart_finish_summary': {
        'es': (
            "🏁 <b>Resumen de tu carrito</b>\n\n{lines}\n\n"
            "💰 <b>Total: {total}</b> ({count} productos)\n\n¿Cómo quieres guardarlo?"
        ),
        'en': (
            "🏁 <b>Your cart summary</b>\n\n{lines}\n\n"
            "💰 <b>Total: {total}</b> ({count} products)\n\nHow do you want to save it?"
        ),
    },
    'cart_line': {'es': "• {name} — {amount}", 'en': "• {name} — {amount}"},
    'cart_more_lines': {'es': "… y {n} más", 'en': "… and {n} more"},
    'btn_cart_save_only': {'es': "💾 Solo guardar", 'en': "💾 Save only"},
    'btn_cart_save_movement': {'es': "📥 Guardar y agregar a movimientos", 'en': "📥 Save and add to transactions"},
    'btn_cart_continue': {'es': "⬅️ Seguir comprando", 'en': "⬅️ Keep shopping"},
    'btn_cart_discard': {'es': "🗑 Descartar carrito", 'en': "🗑 Discard cart"},
    'cart_saved_only': {
        'es': (
            "💾 <b>Compra guardada</b> — {total} ({count} productos).\n\n"
            "Cuando pagues, puedes registrarla como movimiento desde la app en <b>Movimientos → Carrito</b>, "
            "ajustando el monto si cambió en caja."
        ),
        'en': (
            "💾 <b>Purchase saved</b> — {total} ({count} products).\n\n"
            "After checkout you can record it as a transaction from the app in <b>Transactions → Cart</b>, "
            "adjusting the amount if it changed at the register."
        ),
    },
    'cart_saved_movement': {
        'es': "✅ <b>Compra guardada y agregada a tus movimientos</b>\n\n💰 {total} · 🏷 {category}",
        'en': "✅ <b>Purchase saved and added to your transactions</b>\n\n💰 {total} · 🏷 {category}",
    },
    'cart_movement_error': {
        'es': "⚠️ No pude crear el movimiento. La compra quedó guardada; regístrala desde la app en <b>Movimientos → Carrito</b>.",
        'en': "⚠️ I couldn't create the transaction. The purchase was saved; record it from the app in <b>Transactions → Cart</b>.",
    },
    'cart_discard_confirm': {
        'es': "⚠️ ¿Descartar el carrito con {count} productos ({total})? No se puede deshacer.",
        'en': "⚠️ Discard the cart with {count} products ({total})? This can't be undone.",
    },
    'btn_cart_discard_yes': {'es': "🗑 Sí, descartar", 'en': "🗑 Yes, discard"},
    'btn_cart_discard_no': {'es': "⬅️ No, volver", 'en': "⬅️ No, go back"},
    'cart_discarded': {'es': "🗑 Carrito descartado.", 'en': "🗑 Cart discarded."},
    'cart_empty_finish': {
        'es': "ℹ️ El carrito está vacío. Agrega al menos un producto antes de finalizar, o cancélalo.",
        'en': "ℹ️ The cart is empty. Add at least one product before finishing, or cancel it.",
    },
    'cart_not_active': {
        'es': "ℹ️ Este carrito ya no está activo. Escribe /carrito para empezar uno nuevo.",
        'en': "ℹ️ This cart is no longer active. Type /cart to start a new one.",
    },
    'cart_stale_saved': {
        'es': "ℹ️ Tu carrito anterior estaba inactivo y se guardó en el historial ({total}).",
        'en': "ℹ️ Your previous cart was idle and was saved to your history ({total}).",
    },
    'cart_full': {
        'es': "⚠️ El carrito alcanzó el máximo de productos. Finalízalo para empezar otro.",
        'en': "⚠️ The cart reached the maximum number of products. Finish it to start another.",
    },
    'cart_price_not_found': {
        'es': (
            "⚠️ No pude leer el precio en la imagen. Acércate a la etiqueta e intenta de nuevo, "
            "o escribe el producto y su precio."
        ),
        'en': (
            "⚠️ I couldn't read the price in the image. Get closer to the label and try again, "
            "or type the product and its price."
        ),
    },
    'cart_text_help': {
        'es': (
            "ℹ️ Escribe el producto y su precio: <code>Leche 1290</code> o <code>2 x 990 yogurt</code>\n\n"
            "Escribe /carrito para ver las opciones o /cancelar para descartar el carrito."
        ),
        'en': (
            "ℹ️ Type the product and its price: <code>Milk 3.50</code> or <code>2 x 1.20 yogurt</code>\n\n"
            "Type /cart to see the options or /cancel to discard the cart."
        ),
    },
    'cart_default_item': {'es': "Producto", 'en': "Product"},
    'cart_no_store': {'es': "supermercado sin nombre", 'en': "unnamed store"},
    'cart_ask_store': {
        'es': "🏪 <b>¿En qué supermercado estás?</b>\n\nEscribe el nombre (ej: <code>Lider</code>, <code>Jumbo</code>) o elige uno reciente.",
        'en': "🏪 <b>Which store are you at?</b>\n\nType the name (e.g. <code>Walmart</code>) or pick a recent one.",
    },
    'cart_ask_store_recent': {
        'es': "🏪 <b>¿En qué supermercado estás?</b>\n\nElige uno reciente o toca ➕ <b>Nuevo supermercado</b>.",
        'en': "🏪 <b>Which store are you at?</b>\n\nPick a recent one or tap ➕ <b>New store</b>.",
    },
    'btn_cart_new_store': {'es': "➕ Nuevo supermercado", 'en': "➕ New store"},
    'cart_new_store_prompt': {
        'es': "✍️ Escribe el nombre del supermercado (ej: <code>Lider</code>, <code>Jumbo</code>).",
        'en': "✍️ Type the store name (e.g. <code>Walmart</code>).",
    },
    'cart_store_invalid': {
        'es': "✍️ Necesito el nombre del supermercado para empezar el carrito. Escríbelo como texto (ej: <code>Lider</code>).",
        'en': "✍️ I need the store name to start the cart. Type it as text (e.g. <code>Walmart</code>).",
    },
    'btn_cart_cancel_start': {'es': "❌ Cancelar", 'en': "❌ Cancel"},
    'cart_start_cancelled': {'es': "❌ No se creó el carrito.", 'en': "❌ The cart was not created."},
}


def t(key, lang=None):
    """Devuelve el mensaje ``key`` en ``lang`` (es/en), con fallback a español."""
    lang = lang if lang in _SUPPORTED else _DEFAULT_LANG
    entry = MESSAGES.get(key, {})
    return entry.get(lang) or entry.get(_DEFAULT_LANG, '')
