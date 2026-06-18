from __future__ import annotations

from typing import Any

import pandas as pd

from frontend.constants import PRIORIDAD_LABELS
from frontend.logic import display_delta, display_risk, format_label


RISK_LEVEL_COLORS = {
    "critico": "#d73027",
    "alto": "#fc8d59",
    "medio": "#fee08b",
    "bajo": "#1a9850",
    "sin lectura": "#8a939b",
}
RISK_UP_COLOR = "#d73027"
RISK_DOWN_COLOR = "#1a9850"
RISK_STABLE_COLOR = "#8a939b"


def numeric(value: Any) -> float | None:
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def priority_label(row: pd.Series) -> str:
    return format_label(row.get("prioridad_visual", row.get("prioridad")), PRIORIDAD_LABELS)


def risk_level(value: Any) -> str:
    risk = numeric(value)
    if risk is None:
        return "sin lectura"
    if risk >= 55:
        return "critico"
    if risk >= 47.5:
        return "alto"
    if risk >= 35:
        return "medio"
    return "bajo"


def risk_level_label(value: Any) -> str:
    labels = {
        "critico": "Crítico",
        "alto": "Alto",
        "medio": "Medio",
        "bajo": "Bajo",
        "sin lectura": "Sin lectura",
    }
    return labels[risk_level(value)]


def risk_level_color(value: Any) -> str:
    return RISK_LEVEL_COLORS[risk_level(value)]


def risk_change_indicator(value: Any, tolerance: float = 0.5) -> dict[str, str]:
    change = numeric(value)
    if change is None:
        return {"text": "-", "color": RISK_STABLE_COLOR, "state": "sin lectura"}
    if change > tolerance:
        return {
            "text": f"▲ {abs(change):.1f}",
            "color": RISK_UP_COLOR,
            "state": "aumenta",
        }
    if change < -tolerance:
        return {
            "text": f"▼ {abs(change):.1f}",
            "color": RISK_DOWN_COLOR,
            "state": "baja",
        }
    return {
        "text": f"→ {abs(change):.1f}",
        "color": RISK_STABLE_COLOR,
        "state": "estable",
    }


def projection_sentence(row: pd.Series, horizon: int = 10) -> str:
    delta = numeric(display_delta(row, horizon, admin_mode=False))
    future = numeric(display_risk(row, horizon, admin_mode=False))

    future_text = f" hasta {future:.1f}" if future is not None else ""

    if delta is None:
        return "No hay proyección suficiente para estimar la evolución."
    if delta >= 10:
        return f"En {horizon} días podría aumentar de forma marcada{future_text}."
    if delta >= 4:
        return f"En {horizon} días podría aumentar{future_text}."
    if delta >= 1:
        return f"En {horizon} días podría aumentar levemente{future_text}."
    if delta > -1:
        return f"En {horizon} días se mantendría prácticamente estable{future_text}."
    return f"En {horizon} días no se proyecta empeoramiento relevante{future_text}."


def recent_trend_sentence(row: pd.Series) -> str | None:
    trend = numeric(row.get("tendencia_reciente_5d"))
    if trend is None:
        return None
    if trend > 2:
        return "La parcela ya venía empeorando en las últimas lecturas."
    if trend < -2:
        return "La parcela venía mejorando en las últimas lecturas."
    return "Las últimas lecturas muestran una situación estable."


def reading_sentence(row: pd.Series) -> str | None:
    date = row.get("fecha_lectura")
    if pd.isna(date):
        return None

    days = row.get("dias_desde_lectura")
    if pd.notna(days):
        return f"Lectura usada: {date} ({int(days)} días respecto de la fecha objetivo)."
    return f"Lectura usada: {date}."


def producer_feedback_lines(row: pd.Series) -> list[str]:
    current = numeric(row.get("riesgo_actual"))
    if current is None:
        status = row.get("estado_evaluacion")
        if pd.notna(status):
            return [f"{status}. La parcela entrará al análisis cuando exista una lectura válida."]
        return ["La parcela no tiene lectura suficiente para calcular estrés hídrico en esta fecha."]

    lines = [
        f"Estado actual: {risk_level_label(current).lower()} ({current:.1f}).",
        projection_sentence(row, horizon=10),
    ]

    trend = recent_trend_sentence(row)
    if trend:
        lines.append(trend)

    reading = reading_sentence(row)
    if reading:
        lines.append(reading)

    return lines


def producer_comparison_summary(row: pd.Series, ranked: pd.DataFrame) -> dict[str, Any]:
    current = numeric(row.get("riesgo_actual"))
    projected = numeric(display_risk(row, 10, admin_mode=False))
    delta = numeric(display_delta(row, 10, admin_mode=False))

    current_values = (
        pd.to_numeric(ranked.get("riesgo_actual", pd.Series(dtype=float)), errors="coerce")
        .dropna()
    )
    projected_values = ranked.apply(
        lambda item: numeric(display_risk(item, 10, admin_mode=False)),
        axis=1,
    ).dropna()

    avg_current = float(current_values.mean()) if not current_values.empty else None
    avg_projected = float(projected_values.mean()) if not projected_values.empty else None
    diff_current = (
        current - avg_current
        if current is not None and avg_current is not None
        else None
    )
    position = (
        int((current_values > current).sum()) + 1
        if current is not None and not current_values.empty
        else None
    )

    return {
        "current": current,
        "projected": projected,
        "delta": delta,
        "avg_current": avg_current,
        "avg_projected": avg_projected,
        "diff_current": diff_current,
        "position": position,
        "total": int(len(current_values)),
    }


def producer_comparison_lines(summary: dict[str, Any]) -> list[str]:
    lines = []
    position = summary.get("position")
    total = int(summary.get("total") or 0)
    diff = summary.get("diff_current")
    delta = summary.get("delta")

    if position is not None and total:
        if position <= max(1, min(3, total // 4 or 1)):
            lines.append("Dentro de tus parcelas, está entre las que más conviene revisar.")
        else:
            lines.append(f"Dentro de tus parcelas, aparece en la posición {position} de {total} por riesgo actual.")

    if diff is not None:
        if diff >= 8:
            lines.append(f"Está claramente por encima del promedio de tus parcelas ({abs(diff):.1f} puntos).")
        elif diff >= 3:
            lines.append(f"Está por encima del promedio de tus parcelas ({abs(diff):.1f} puntos).")
        elif diff <= -8:
            lines.append(f"Está claramente por debajo del promedio de tus parcelas ({abs(diff):.1f} puntos).")
        elif diff <= -3:
            lines.append(f"Está por debajo del promedio de tus parcelas ({abs(diff):.1f} puntos).")
        else:
            lines.append("Está cerca del promedio de tus parcelas.")

    if delta is not None:
        indicator = risk_change_indicator(delta)
        if delta >= 8:
            lines.append(
                f"La proyección a 10 días muestra un aumento importante ({indicator['text']} puntos)."
            )
        elif delta >= 3:
            lines.append(
                f"La proyección a 10 días muestra aumento moderado ({indicator['text']} puntos)."
            )
        elif delta >= 0:
            lines.append(f"La proyección a 10 días cambia poco ({indicator['text']} puntos).")
        else:
            lines.append("La proyección a 10 días no indica empeoramiento relevante.")

    return lines


def producer_dashboard_headline(summary: dict[str, Any]) -> str:
    total = int(summary.get("total") or 0)
    high = int(summary.get("high_or_critical") or 0)
    critical = int(summary.get("critical") or 0)
    projected_change = numeric(summary.get("projected_change"))

    if total == 0:
        return "Todavía no hay parcelas evaluadas en esta vista."

    if high == 0:
        base = "No hay parcelas en atención alta o crítica."
    elif critical:
        base = f"Hay {high} parcelas en atención, incluyendo {critical} críticas."
    else:
        base = f"Hay {high} parcelas en atención alta."

    if projected_change is None:
        return base
    if projected_change >= 5:
        return f"{base} La situación general podría empeorar en los próximos 10 días."
    if projected_change >= 1:
        return f"{base} Se espera un aumento leve en los próximos 10 días."
    return f"{base} El conjunto se mantiene estable en el escenario a 10 días."
