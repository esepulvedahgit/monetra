"""
translate_missing.py — Auto-translate empty and fuzzy EN strings in messages.po

Uses:
  - polib  : parse/write .po files
  - deep-translator : free Google Translate wrapper

Usage:
    cd site_finanzas
    venv/Scripts/python.exe tools/translate_missing.py

The script:
  1. Fixes 8 known fuzzy entries with wrong placeholders (hardcoded corrections)
  2. Translates all empty msgstr entries (ES → EN) via Google Translate
  3. Retranslates fuzzy entries that have wrong/outdated msgstr
  4. Removes #, fuzzy flags from entries that now have a correct translation
  5. Saves the .po file in-place
"""

import re
import time
import sys
import os

# Force UTF-8 output on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------------------
# Paths (relative to site_finanzas/)
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR   = os.path.dirname(SCRIPT_DIR)
PO_PATH    = os.path.join(BASE_DIR, 'app', 'translations', 'en', 'LC_MESSAGES', 'messages.po')

# ---------------------------------------------------------------------------
# Known corrections for the 8 fuzzy entries with wrong placeholders.
# Key = msgid (exact), Value = correct English msgstr.
# ---------------------------------------------------------------------------
KNOWN_CORRECTIONS = {
    'Presupuesto "%(n)s" eliminado junto con %(tx)s movimientos y %(rec)s recurrentes asociados.':
        'Budget "%(n)s" deleted along with %(tx)s transactions and %(rec)s associated recurring entries.',

    'La fecha de término debe estar dentro del año de la recurrente.':
        'The end date must be within the year of the recurring entry.',

    '¡Bienvenido a Monetra!':
        'Welcome to Monetra!',

    'Reenviar correo de activación':
        'Resend activation email',

    '¿Eliminar la categoría %(name)s?':
        'Delete category %(name)s?',

    'debe estar dentro del mes activo':
        'must be within the active month',

    'Las fechas deben estar dentro del mismo mes.':
        'Dates must be within the same month.',

    '¿Eliminar la categoría %(n)s?':
        'Delete category %(n)s?',
}

# ---------------------------------------------------------------------------
# Placeholder handling for python-format strings
# ---------------------------------------------------------------------------
PH_RE = re.compile(r'%\((\w+)\)[diouxXeEfFgGcrsab%]|%[diouxXeEfFgGcrsab%]')


def _extract_placeholders(text: str):
    """Return (tokenized_text, {token: original}) so Google Translate won't mangle them."""
    tokens = {}
    def replacer(m):
        tok = f'XPLACEHOLDERX{len(tokens)}X'
        tokens[tok] = m.group(0)
        return tok
    tokenized = PH_RE.sub(replacer, text)
    return tokenized, tokens


def _restore_placeholders(text: str, tokens: dict) -> str:
    for tok, orig in tokens.items():
        text = text.replace(tok, orig)
    return text


# ---------------------------------------------------------------------------
# Google Translate wrapper with simple retry
# ---------------------------------------------------------------------------
try:
    from deep_translator import GoogleTranslator
    _translator = GoogleTranslator(source='es', target='en')
except ImportError:
    print("ERROR: deep-translator not installed. Run: venv/Scripts/python.exe -m pip install deep-translator")
    sys.exit(1)


def translate(text: str, is_python_format: bool = False) -> str:
    """Translate a single string ES→EN. Returns original on failure."""
    if not text.strip():
        return text

    if is_python_format:
        tokenized, tokens = _extract_placeholders(text)
    else:
        tokenized, tokens = text, {}

    for attempt in range(3):
        try:
            result = _translator.translate(tokenized)
            if result:
                break
        except Exception as exc:
            if attempt == 2:
                print(f"  ⚠ Translation failed: {exc}")
                return text
            time.sleep(1)
    else:
        return text

    if tokens:
        result = _restore_placeholders(result, tokens)

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    try:
        import polib
    except ImportError:
        print("ERROR: polib not installed. Run: venv/Scripts/python.exe -m pip install polib")
        sys.exit(1)

    print(f"Loading {PO_PATH}")
    po = polib.pofile(PO_PATH, encoding='utf-8')

    stats = {'fixed_known': 0, 'translated_empty': 0, 'translated_fuzzy': 0,
             'defuzzied': 0, 'skipped': 0, 'errors': 0}

    total = len(po)
    print(f"Total entries: {total}")
    print()

    for i, entry in enumerate(po):
        if not entry.msgid:
            continue  # header

        is_fmt     = 'python-format' in (entry.flags or [])
        is_fuzzy   = 'fuzzy' in (entry.flags or [])
        has_msgstr = bool(entry.msgstr and entry.msgstr.strip())

        # ── 1. Apply known corrections first ──────────────────────────────
        if entry.msgid in KNOWN_CORRECTIONS:
            correct = KNOWN_CORRECTIONS[entry.msgid]
            entry.msgstr = correct
            if 'fuzzy' in entry.flags:
                entry.flags.remove('fuzzy')
            stats['fixed_known'] += 1
            print(f"  [KNOWN] {entry.msgid[:60]!r}")
            continue

        # ── 2. Translate empty msgstr ──────────────────────────────────────
        if not has_msgstr:
            translated = translate(entry.msgid, is_fmt)
            if translated and translated != entry.msgid:
                entry.msgstr = translated
                if 'fuzzy' in entry.flags:
                    entry.flags.remove('fuzzy')
                stats['translated_empty'] += 1
                if i % 25 == 0:
                    print(f"  [{i}/{total}] {entry.msgid[:55]!r} -> {translated[:40]!r}")
            else:
                stats['errors'] += 1
            time.sleep(0.12)
            continue

        # ── 3. Re-translate fuzzy entries (wrong msgstr) ──────────────────
        if is_fuzzy and has_msgstr:
            translated = translate(entry.msgid, is_fmt)
            if translated and translated != entry.msgid:
                entry.msgstr = translated
                entry.flags.remove('fuzzy')
                stats['translated_fuzzy'] += 1
                if i % 25 == 0:
                    print(f"  [{i}/{total}] DEFUZZ {entry.msgid[:55]!r}")
            else:
                # Can't translate — just remove fuzzy to avoid compile errors
                entry.flags.remove('fuzzy')
                stats['defuzzied'] += 1
            time.sleep(0.12)
            continue

        stats['skipped'] += 1

    print()
    print("─" * 60)
    print(f"Known corrections applied : {stats['fixed_known']}")
    print(f"Empty strings translated  : {stats['translated_empty']}")
    print(f"Fuzzy strings retranslated: {stats['translated_fuzzy']}")
    print(f"Fuzzy flags removed       : {stats['defuzzied']}")
    print(f"Already translated        : {stats['skipped']}")
    print(f"Errors                    : {stats['errors']}")
    print()

    print(f"Saving {PO_PATH}")
    po.save(PO_PATH)
    print("Done.")


if __name__ == '__main__':
    main()
