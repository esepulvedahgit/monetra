"""Message templates for alerts.

Centralized so copy stays consistent and translation can be applied in one
place. Strings use `lazy_gettext` so Flask-Babel picks them up.

Format placeholders use `{name}` (not %s) — handlers call `.format(**evidence)`.

Schema per template:
    {
        Severity.X: {
            'title':              str,
            'message':            str,
            'explanation':        str,
            'recommended_action': str,
        },
        ...
    }
"""
from __future__ import annotations
from flask_babel import lazy_gettext as _l

from app.insights.enums import Severity, AlertType


TEMPLATES: dict[AlertType, dict[Severity, dict[str, str]]] = {

    AlertType.BUDGET_BURN_RATE: {
        Severity.WARNING: {
            'title':              _l('Ritmo de gasto alto'),
            'message':            _l('Has usado el {budget_used_pct:.0f}% del presupuesto y solo ha transcurrido el {month_elapsed_pct:.0f}% del mes.'),
            'explanation':        _l('Tu ritmo actual de gasto indica que podrías superar el presupuesto antes del cierre mensual.'),
            'recommended_action': _l('Revisa gastos variables o ajusta el presupuesto si este patrón es recurrente.'),
        },
        Severity.CRITICAL: {
            'title':              _l('Vas a superar tu presupuesto'),
            'message':            _l('Con el ritmo actual cerrarás el mes en {projected_pct:.0f}% del presupuesto.'),
            'explanation':        _l('La diferencia entre el avance del mes y el consumo del presupuesto es significativa.'),
            'recommended_action': _l('Reduce gastos no esenciales o reasigna presupuesto entre categorías.'),
        },
    },

    AlertType.DEFICIT_RISK: {
        Severity.CRITICAL: {
            'title':              _l('Riesgo de déficit mensual'),
            'message':            _l('Con el ritmo actual podrías cerrar el mes con balance negativo.'),
            'explanation':        _l('Los gastos proyectados superan a los ingresos proyectados del periodo.'),
            'recommended_action': _l('Revisa gastos no esenciales, pagos recurrentes y compromisos pendientes.'),
        },
    },

    AlertType.CATEGORY_SPIKE: {
        Severity.WARNING: {
            'title':              _l('Aumento en {category_name}'),
            'message':            _l('Este mes llevas {current:.0f}, frente a un promedio histórico de {baseline:.0f}.'),
            'explanation':        _l('El gasto en esta categoría está al menos un 50% por encima del promedio.'),
            'recommended_action': _l('Revisa los movimientos de la categoría para confirmar si el aumento es esperado.'),
        },
        Severity.CRITICAL: {
            'title':              _l('Aumento fuerte en {category_name}'),
            'message':            _l('Este mes llevas {current:.0f}, el doble o más del promedio histórico.'),
            'explanation':        _l('La desviación es muy superior al patrón habitual de esta categoría.'),
            'recommended_action': _l('Verifica si hay cargos duplicados, suscripciones nuevas o gastos atípicos.'),
        },
    },

    AlertType.UNUSUAL_TRANSACTION: {
        Severity.WARNING: {
            'title':              _l('Transacción inusual detectada'),
            'message':            _l('Una transacción de {value:.0f} en {category_name} se aleja del patrón habitual.'),
            'explanation':        _l('El monto está significativamente por encima del rango típico de la categoría.'),
            'recommended_action': _l('Confirma que la transacción es correcta y que la categoría es la adecuada.'),
        },
    },

    AlertType.LOW_SAVINGS: {
        Severity.WARNING: {
            'title':              _l('Tasa de ahorro baja'),
            'message':            _l('Tu tasa de ahorro este mes es de {savings_rate_pct:.1f}%.'),
            'explanation':        _l('Una tasa de ahorro saludable suele estar por encima del 10%.'),
            'recommended_action': _l('Considera revisar gastos variables o establecer una meta de ahorro fija.'),
        },
        Severity.CRITICAL: {
            'title':              _l('Sin capacidad de ahorro'),
            'message':            _l('Este mes tu balance no permite ahorro (tasa: {savings_rate_pct:.1f}%).'),
            'explanation':        _l('Los ingresos no superan a los gastos en margen suficiente.'),
            'recommended_action': _l('Prioriza reducir gastos recurrentes o revisa fuentes de ingreso.'),
        },
    },

    AlertType.SAVINGS_GOAL_RISK: {
        Severity.WARNING: {
            'title':              _l('Meta de ahorro en riesgo'),
            'message':            _l('La meta "{goal_name}" requiere ahorrar {monthly_required:.0f} al mes.'),
            'explanation':        _l('Tu capacidad de ahorro proyectada no alcanza el ritmo necesario para cumplirla a tiempo.'),
            'recommended_action': _l('Ajusta el plazo, reduce el objetivo o define un aporte recurrente para esta meta.'),
        },
        Severity.CRITICAL: {
            'title':              _l('Meta de ahorro vencida'),
            'message':            _l('La meta "{goal_name}" tiene {remaining:.0f} pendiente y ya venció.'),
            'explanation':        _l('El objetivo no se alcanzó antes de la fecha definida.'),
            'recommended_action': _l('Actualiza la fecha objetivo o cierra la meta si ya no aplica.'),
        },
    },

    AlertType.NEGATIVE_TREND: {
        Severity.WARNING: {
            'title':              _l('Tendencia de gasto al alza'),
            'message':            _l('Tus gastos mensuales muestran una tendencia creciente en los últimos meses.'),
            'explanation':        _l('La pendiente positiva sostenida indica un cambio de patrón.'),
            'recommended_action': _l('Revisa qué categorías están creciendo más rápido que el resto.'),
        },
    },

    AlertType.DUPLICATE_SUSPECTED: {
        Severity.INFO: {
            'title':              _l('Posible movimiento duplicado'),
            'message':            _l('Se detectó una transacción muy similar a otra reciente en {category_name}.'),
            'explanation':        _l('Mismo monto, misma categoría y fecha cercana sugieren un posible duplicado.'),
            'recommended_action': _l('Verifica el detalle y elimínalo si corresponde.'),
        },
    },
}


def get_template(alert_type: AlertType, severity: Severity) -> dict[str, str] | None:
    """Safe accessor — returns None when the (alert_type, severity) combo
    has no template defined (rule should then skip the alert)."""
    return TEMPLATES.get(alert_type, {}).get(severity)
