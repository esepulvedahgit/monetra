"""Tipos de producto de supermercado y su clasificación local.

La IA clasifica los productos leídos desde una foto. Lo escrito (Telegram, web o
app) se clasifica aquí, sin costo ni red: primero por palabras clave en español y,
cuando el usuario ya tiene productos clasificados, con un Naive Bayes pequeño que
aprende de su catálogo. El tamaño (1 L, 500 g) se lee del nombre para comparar
precios por kilo o por litro.
"""
import math
import re
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation

OTHER = 'otros'

# Clave estable → (etiqueta ES, etiqueta EN, color para gráficos).
CATEGORIES = {
    'lacteos':          ('Lácteos y huevos', 'Dairy and eggs', '#4F8DFD'),
    'carnes':           ('Carnes y pescados', 'Meat and fish', '#E5484D'),
    'fiambres':         ('Fiambres y quesos', 'Deli and cheese', '#F76B15'),
    'frutas_verduras':  ('Frutas y verduras', 'Fruit and vegetables', '#30A46C'),
    'panaderia':        ('Panadería', 'Bakery', '#D6A35C'),
    'despensa':         ('Despensa', 'Pantry', '#A18072'),
    'desayuno':         ('Desayuno y dulces', 'Breakfast and sweets', '#E93D82'),
    'snacks':           ('Snacks', 'Snacks', '#FFB224'),
    'bebidas':          ('Bebidas', 'Drinks', '#00A2C7'),
    'alcohol':          ('Alcohol', 'Alcohol', '#8E4EC6'),
    'congelados':       ('Congelados', 'Frozen', '#5EB1EF'),
    'limpieza':         ('Limpieza del hogar', 'Household cleaning', '#12A594'),
    'cuidado_personal': ('Cuidado personal', 'Personal care', '#D864D8'),
    'bebe_mascotas':    ('Bebé y mascotas', 'Baby and pets', '#978365'),
    OTHER:              ('Otros', 'Other', '#8B8D98'),
}

# Prefijos de palabras (sin acentos, minúsculas) que delatan el tipo. Un prefijo
# cubre plurales y variantes: 'yogur' reconoce yogurt, yogures y yoghurt no.
_KEYWORDS = {
    'lacteos': ('leche', 'yogur', 'yoghurt', 'mantequilla', 'margarina', 'crema', 'huevo', 'manjar',
                'leche cultivada', 'kefir', 'postre lacteo', 'flan'),
    'carnes': ('carne', 'vacuno', 'posta', 'lomo', 'filete', 'asado', 'molida', 'pollo', 'pechuga', 'trutro',
               'cerdo', 'chuleta', 'costilla', 'pavo', 'pescado', 'salmon', 'merluza', 'reineta', 'atun fresco',
               'camaron', 'marisco', 'chorizo', 'longaniza', 'hamburguesa', 'churrasco', 'pulpa', 'osobuco'),
    'fiambres': ('jamon', 'queso', 'salame', 'mortadela', 'salchicha', 'vienesa', 'longanicilla', 'pate',
                 'cecina', 'quesillo', 'ricota', 'mozzarella', 'gauda', 'chanco', 'parmesano'),
    'frutas_verduras': ('manzana', 'platano', 'banana', 'naranja', 'mandarina', 'limon', 'palta', 'tomate',
                        'lechuga', 'papa', 'cebolla', 'zanahoria', 'zapallo', 'pepino', 'pimenton', 'ajo',
                        'frutilla', 'uva', 'pera', 'kiwi', 'durazno', 'sandia', 'melon', 'brocoli', 'coliflor',
                        'espinaca', 'acelga', 'cilantro', 'perejil', 'choclo', 'betarraga', 'champinon',
                        'fruta', 'verdura', 'arandano', 'frambuesa', 'piña', 'pina'),
    'panaderia': ('pan ', 'marraqueta', 'hallulla', 'baguette', 'pan molde', 'pan de molde', 'pan integral',
                  'queque', 'torta', 'kuchen', 'croissant', 'dobladita', 'tortilla', 'pita', 'bizcocho'),
    'despensa': ('arroz', 'fideo', 'spaghetti', 'tallarin', 'pasta', 'harina', 'aceite', 'azucar', 'sal ',
                 'atun', 'jurel', 'sardina', 'conserva', 'lenteja', 'poroto', 'garbanzo', 'salsa', 'ketchup',
                 'mayonesa', 'mostaza', 'vinagre', 'sopa', 'caldo', 'condimento', 'oregano', 'comino',
                 'pure', 'polenta', 'avena', 'levadura', 'aliño', 'alino', 'merken', 'pimienta'),
    'desayuno': ('cafe', 'te ', 'cereal', 'mermelada', 'miel', 'chocolate', 'cacao', 'nescafe',
                 'galleta', 'alfajor', 'dulce', 'caramelo', 'golosina', 'bombon', 'nutella',
                 'granola', 'muesli', 'infusion', 'hierbas'),
    'snacks': ('papas fritas', 'papa frita', 'ramitas', 'suflé', 'sufle', 'mani', 'nueces', 'almendra',
               'snack', 'chips', 'doritos', 'cheetos', 'pop corn', 'cabritas', 'frutos secos', 'pistacho'),
    'bebidas': ('bebida', 'gaseosa', 'coca', 'pepsi', 'sprite', 'fanta', 'agua', 'jugo', 'nectar', 'nectar',
                'energetica', 'red bull', 'isotonica', 'gatorade', 'powerade', 'kombucha', 'soda'),
    'alcohol': ('cerveza', 'vino', 'pisco', 'ron', 'whisky', 'vodka', 'gin', 'espumante', 'champaña',
                'champana', 'tequila', 'licor', 'sidra', 'cabernet', 'carmenere', 'sauvignon', 'merlot'),
    'congelados': ('congelad', 'helado', 'nugget', 'empanada congelada', 'pizza', 'papas pre', 'verduras congeladas',
                   'hielo', 'lasaña', 'lasana'),
    'limpieza': ('detergente', 'lavaloza', 'cloro', 'limpiador', 'desinfectante', 'suavizante', 'esponja',
                 'virutilla', 'papel higienico', 'confort', 'toalla de papel', 'servilleta', 'bolsa de basura',
                 'bolsas de basura', 'lysoform', 'cif', 'quix', 'omo', 'ariel', 'ace ', 'escoba', 'trapero',
                 'paño', 'pano', 'insecticida', 'aromatizante', 'lavalozas', 'lustramuebles'),
    'cuidado_personal': ('shampoo', 'champu', 'acondicionador', 'jabon', 'pasta dental', 'cepillo de dientes',
                         'desodorante', 'crema corporal', 'protector solar', 'afeitar', 'maquinilla', 'toalla higienica',
                         'toallas higienicas', 'tampon', 'algodon', 'colgate', 'gel de ducha', 'enjuague bucal',
                         'hilo dental', 'perfume', 'colonia', 'crema facial'),
    'bebe_mascotas': ('pañal', 'panal', 'toallitas humedas', 'formula infantil', 'compota', 'papilla',
                      'mamadera', 'alimento perro', 'alimento gato', 'perro', 'gato', 'mascota', 'arena sanitaria',
                      'dog chow', 'cat chow', 'pedigree', 'whiskas', 'babysec', 'huggies', 'pampers'),
}

# Envase: '1L', '500 g', '1,5 lt'; y unidades por paquete: '6x', '2 x', '12 un'.
_SIZE_RE = re.compile(
    r'(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(kg|kgs|kilo|kilos|g|gr|grs|gramos|l|lt|lts|litro|litros|ml|cc|cm3)(?![a-z])',
    re.IGNORECASE)
_PACK_RE = re.compile(r'(?<![\d.,])(\d{1,3})\s*(?:x|un|unid|unidades|u)(?![a-z])', re.IGNORECASE)
_UNIT_FACTORS = {
    'kg': ('g', 1000), 'kgs': ('g', 1000), 'kilo': ('g', 1000), 'kilos': ('g', 1000),
    'g': ('g', 1), 'gr': ('g', 1), 'grs': ('g', 1), 'gramos': ('g', 1),
    'l': ('ml', 1000), 'lt': ('ml', 1000), 'lts': ('ml', 1000), 'litro': ('ml', 1000), 'litros': ('ml', 1000),
    'ml': ('ml', 1), 'cc': ('ml', 1), 'cm3': ('ml', 1),
}


def label(key: str | None, lang: str | None = 'es') -> str:
    es, en, _color = CATEGORIES.get(key or OTHER, CATEGORIES[OTHER])
    return en if lang == 'en' else es


def color(key: str | None) -> str:
    return CATEGORIES.get(key or OTHER, CATEGORIES[OTHER])[2]


def is_valid(key) -> bool:
    return isinstance(key, str) and key in CATEGORIES


def normalize(text: str | None) -> str:
    """Minúsculas, sin acentos ni signos, espacios simples."""
    value = unicodedata.normalize('NFKD', text or '')
    value = ''.join(ch for ch in value if not unicodedata.combining(ch)).lower()
    value = re.sub(r'[^a-z0-9.,]+', ' ', value)
    return ' '.join(value.split())


def parse_size(name: str | None) -> tuple[Decimal | None, str | None]:
    """Contenido del envase en gramos o mililitros ('1L' → 1000 ml; '2 x 500 g' → 1000 g)."""
    text = normalize(name)
    match = _SIZE_RE.search(text)
    if not match:
        return None, None
    try:
        amount = Decimal(match.group(1).replace(',', '.'))
    except InvalidOperation:
        return None, None
    unit, factor = _UNIT_FACTORS[match.group(2).lower()]
    pack = _PACK_RE.search(text[:match.start()])
    if pack and int(pack.group(1)) > 1:
        amount *= int(pack.group(1))
    amount *= factor
    return (amount, unit) if amount > 0 else (None, None)


# Marcas frecuentes y marcas propias de supermercados: se quitan del nombre genérico para
# comparar el mismo producto entre marcas ("leche entera colún" y "leche entera soprole").
# No incluye marcas que son el producto mismo (coca cola, sprite).
_BRANDS = (
    'colun', 'soprole', 'nestle', 'loncoleche', 'surlat', 'calo', 'danone', 'ideal', 'castano', 'fuchs',
    'tucapel', 'carozzi', 'lucchetti', 'miraflores', 'banquete', 'chef', 'belmont', 'natura', 'iansa',
    'omo', 'ariel', 'drive', 'popeye', 'confort', 'elite', 'noble', 'favorita', 'lays', 'evercrisp',
    'marco polo', 'savory', 'colgate', 'pepsodent', 'dove', 'rexona', 'nivea', 'great value', 'cuisine co',
    'lider', 'jumbo', 'tottus', 'acuenta', 'unimarc', 'super', 'san jorge', 'pf', 'la preferida', 'quillayes',
    'watts', 'andina', 'cachantun', 'vital', 'benedictino', 'head shoulders', 'head and shoulders',
)
_BRAND_RE = re.compile(r'\b(?:' + '|'.join(re.escape(b) for b in sorted(_BRANDS, key=len, reverse=True)) + r')\b')
_STOPWORDS = {'de', 'del', 'la', 'el', 'en', 'con', 'x', 'c', 'u', 'un', 'unid', 'unidades'}


def generic_name(name: str | None) -> str:
    """Nombre para comparar entre compras: normalizado, sin tamaño, marca ni conectores sueltos."""
    text = _SIZE_RE.sub(' ', normalize(name))
    text = _PACK_RE.sub(' ', text)
    without_brand = _BRAND_RE.sub(' ', text)
    words = _plain_words(without_brand) or _plain_words(text)
    return ' '.join(words)[:120]


def _plain_words(text: str) -> list[str]:
    return [w for w in text.split() if w not in _STOPWORDS and not w.replace('.', '').replace(',', '').isdigit()]


def _tokens(text: str) -> list[str]:
    return [w for w in normalize(text).split() if len(w) > 1 and not w[0].isdigit()]


def keyword_category(name: str | None) -> str | None:
    """Tipo según palabras clave; None si no hay ninguna.

    El nombre suele empezar por el producto y seguir con marca o sabor, así que
    gana la palabra clave que está al inicio ('Yoghurt frutilla' es lácteo, no
    fruta); entre empates, la frase más larga ('pasta dental' antes que 'pasta').
    """
    text = f" {normalize(name)} "
    best, best_score = None, (False, 0)
    for category, keywords in _KEYWORDS.items():
        for keyword in keywords:
            key = normalize(keyword)
            # Prefijo de palabra: 'yogur' reconoce 'yogurt'; 'pan ' exige la palabra completa.
            needle = f" {key} " if keyword.endswith(' ') else f" {key}"
            position = text.find(needle)
            if position < 0:
                continue
            score = (position == 0, len(key))
            if score > best_score:
                best, best_score = category, score
    return best


class NaiveBayes:
    """Clasificador multinomial con suavizado de Laplace sobre las palabras del nombre."""

    def __init__(self, examples: list[tuple[str, str]]):
        self.word_counts = defaultdict(Counter)
        self.class_counts = Counter()
        for text, category in examples:
            if not is_valid(category) or category == OTHER:
                continue
            self.class_counts[category] += 1
            self.word_counts[category].update(_tokens(text))
        self.vocabulary = {w for counts in self.word_counts.values() for w in counts}
        self.totals = {c: sum(counts.values()) for c, counts in self.word_counts.items()}

    def predict(self, text: str) -> tuple[str | None, float]:
        """(tipo, probabilidad) del más probable; (None, 0) sin datos o sin palabras conocidas."""
        words = [w for w in _tokens(text) if w in self.vocabulary]
        if not words or not self.class_counts:
            return None, 0.0
        total_docs = sum(self.class_counts.values())
        vocab = len(self.vocabulary)
        scores = {}
        for category, docs in self.class_counts.items():
            score = math.log(docs / total_docs)
            counts, total = self.word_counts[category], self.totals[category]
            for word in words:
                score += math.log((counts[word] + 1) / (total + vocab))
            scores[category] = score
        best = max(scores, key=scores.get)
        peak = max(scores.values())
        norm = sum(math.exp(s - peak) for s in scores.values())
        return best, 1 / norm


# Con menos ejemplos o menos certeza, el modelo del usuario no se usa.
MIN_EXAMPLES = 8
MIN_CONFIDENCE = 0.6


def classify_local(name: str | None, examples: list[tuple[str, str]] | None = None) -> str:
    """Tipo sin IA: modelo del usuario si está seguro, si no palabras clave, si no 'otros'."""
    if examples and len(examples) >= MIN_EXAMPLES:
        category, confidence = NaiveBayes(examples).predict(name or '')
        if category and confidence >= MIN_CONFIDENCE:
            return category
    return keyword_category(name) or OTHER
