"""Academic, rule-based comparison of Peru's business income-tax regimes."""

from __future__ import annotations

from typing import Any


REGIME_RULES: dict[str, dict[str, Any]] = {
    "NRUS": {
        "name": "Nuevo Régimen Único Simplificado",
        "short": "NRUS",
        "description": "Régimen simplificado para pequeños negocios de personas naturales.",
        "income_limit": 96000,
        "purchase_limit": 96000,
        "asset_limit": 70000,
        "workers_limit": None,
        "legal_person": False,
        "payment": "Cuotas mensuales según categoría; no presenta declaración anual del impuesto a la renta.",
        "income_tax": "Cuotas mensuales de S/ 20 o S/ 50, según categoría y límites aplicables.",
        "igv": "No discrimina IGV en sus comprobantes; verificar el tratamiento vigente.",
        "books": "No lleva libros contables.",
        "receipts": "Boletas de venta y tickets que no dan derecho a crédito fiscal.",
        "obligations": "Pago de cuota mensual y emisión de comprobantes permitidos.",
        "exclusions": "Personas jurídicas y actividades o condiciones excluidas por la normativa del NRUS.",
        "source": "D. Leg. 937 y modificatorias; verificación de vigencia pendiente.",
    },
    "RER": {
        "name": "Régimen Especial del Impuesto a la Renta",
        "short": "RER",
        "description": "Régimen para determinadas actividades empresariales dentro de límites legales.",
        "income_limit": 525000,
        "purchase_limit": 525000,
        "asset_limit": 126000,
        "workers_limit": 10,
        "legal_person": True,
        "payment": "Pago mensual definitivo del impuesto a la renta e IGV, sujeto a reglas vigentes.",
        "income_tax": "Pago mensual estimado de 1.5% de ingresos netos; no se modela declaración anual.",
        "igv": "Tasa general de 18% sobre operaciones gravadas, con crédito fiscal sujeto a requisitos.",
        "books": "Registro de compras y registro de ventas.",
        "receipts": "Comprobantes de pago autorizados según la operación.",
        "obligations": "Declaración y pago mensual; límites y actividades permitidas.",
        "exclusions": "Actividades y supuestos enumerados en la Ley del Impuesto a la Renta.",
        "source": "D. S. 179-2004-EF, TUO de la Ley del Impuesto a la Renta, arts. 117-124; verificar modificatorias.",
    },
    "RMT": {
        "name": "Régimen MYPE Tributario",
        "short": "RMT",
        "description": "Régimen para contribuyentes domiciliados con ingresos netos dentro del límite legal.",
        "income_limit_uit": 1700,
        "purchase_limit": None,
        "asset_limit": None,
        "workers_limit": None,
        "legal_person": True,
        "payment": "Pagos a cuenta mensuales y regularización anual, según condiciones del contribuyente.",
        "income_tax": "Tasa progresiva de 10% hasta 15 UIT de renta neta imponible y tasa general sobre el exceso.",
        "igv": "Tasa general de 18% sobre operaciones gravadas, con crédito fiscal sujeto a requisitos.",
        "books": "Libros y registros según ingresos netos anuales.",
        "receipts": "Comprobantes de pago autorizados según la operación.",
        "obligations": "Declaraciones mensuales, libros aplicables y declaración anual.",
        "exclusions": "Supuestos de vinculación, sucursales y demás exclusiones del D. Leg. 1269.",
        "source": "D. Leg. 1269 y D. S. 403-2016-EF; verificar modificatorias y UIT vigente.",
    },
    "RG": {
        "name": "Régimen General",
        "short": "RG",
        "description": "Régimen general, sin límite máximo de ingresos y con reglas completas de renta empresarial.",
        "income_limit": None,
        "purchase_limit": None,
        "asset_limit": None,
        "workers_limit": None,
        "legal_person": True,
        "payment": "Pagos a cuenta mensuales y regularización anual.",
        "income_tax": "Tasa anual general de 29.5% sobre la renta neta imponible, conforme a ley.",
        "igv": "Tasa general de 18% sobre operaciones gravadas, con crédito fiscal sujeto a requisitos.",
        "books": "Libros y registros según ingresos y normativa aplicable.",
        "receipts": "Comprobantes de pago autorizados según la operación.",
        "obligations": "Declaraciones mensuales y anuales, libros y obligaciones formales.",
        "exclusions": "Se aplican las reglas generales de renta empresarial.",
        "source": "D. S. 179-2004-EF, TUO de la Ley del Impuesto a la Renta; verificar modificatorias.",
    },
}

TAX_RATE_GENERAL = 0.295
IGV_RATE = 0.18
RMT_FIRST_BRACKET_UIT = 15
RMT_FIRST_BRACKET_RATE = 0.10


def _number(data: dict[str, Any], key: str, default: float = 0) -> float:
    try:
        value = float(data.get(key, default) or default)
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default


def evaluate_case(data: dict[str, Any], uit: float | None = None) -> dict[str, Any]:
    """Evaluate eligibility first, then estimate tax and future risks."""
    revenue = _number(data, "projected_annual_income")
    purchase = _number(data, "projected_annual_purchases")
    deductible_costs = _number(data, "annual_costs") + _number(data, "annual_expenses")
    net_income = max(0, revenue - deductible_costs)
    countable_assets = max(0, _number(data, "fixed_assets") - _number(data, "nrus_exempt_assets"))
    workers = int(_number(data, "workers"))
    workers_per_shift = int(_number(data, "workers_per_shift", workers))
    monthly_income = _number(data, "monthly_income")
    monthly_purchases = _number(data, "monthly_purchases")
    person_type = str(data.get("person_type", "natural"))
    taxable_share = min(1.0, max(0.0, _number(data, "taxable_share", 1)))
    declared_exclusion = bool(data.get("excluded_activity"))
    plans = data.get("plans") if isinstance(data.get("plans"), dict) else {}
    exclusions: list[str] = []
    alerts: list[str] = []
    enough_data = all(
        key in data and data.get(key) not in (None, "")
        for key in (
            "activity", "person_type", "monthly_income", "projected_annual_income",
            "monthly_purchases", "projected_annual_purchases", "annual_costs",
            "annual_expenses", "fixed_assets", "taxable_share", "workers", "workers_per_shift",
        )
    )
    regime_results: dict[str, dict[str, Any]] = {}
    taxable_sales = revenue * taxable_share
    estimated_igv = max(0, taxable_sales - purchase * taxable_share) * IGV_RATE

    for code, rule in REGIME_RULES.items():
        reasons: list[str] = []
        limits: list[str] = []
        missing_uit_for_rmt = False
        if code == "NRUS":
            if person_type != "natural":
                reasons.append("El NRUS está dirigido a personas naturales; se registró otro tipo de contribuyente.")
            if revenue > (rule["income_limit"] or 0):
                reasons.append("Los ingresos proyectados superan el límite anual de referencia del NRUS.")
            if purchase > (rule["purchase_limit"] or 0):
                reasons.append("Las compras proyectadas superan el límite anual de referencia del NRUS.")
            if _number(data, "monthly_income") > 8000 or _number(data, "monthly_purchases") > 8000:
                reasons.append("Los importes mensuales exceden el límite mensual de referencia del NRUS.")
            if countable_assets > rule["asset_limit"]:
                reasons.append("Los activos computables superan el límite de referencia; confirma qué bienes se excluyen del cómputo.")
            if declared_exclusion:
                reasons.append("Se indicó una actividad excluida o incompatible; requiere validación normativa.")
            for name in ("import", "export"):
                if plans.get(name):
                    reasons.append(f"El plan de {'importar' if name == 'import' else 'exportar'} requiere revisar la compatibilidad con el NRUS.")
        elif code == "RER":
            for label, amount, limit in (
                ("ingresos", revenue, rule["income_limit"]),
                ("compras", purchase, rule["purchase_limit"]),
                ("activos computables", countable_assets, rule["asset_limit"]),
            ):
                if amount > limit:
                    reasons.append(f"Los {label} proyectados exceden el límite de referencia del RER.")
            if workers_per_shift > rule["workers_limit"]:
                reasons.append("La cantidad de trabajadores excede el límite referencial por turno del RER.")
            if declared_exclusion:
                reasons.append("Se indicó una actividad excluida o incompatible con el RER.")
        elif code == "RMT":
            if not uit or uit <= 0:
                missing_uit_for_rmt = True
                reasons.append("Falta configurar la UIT para comprobar el límite de ingresos.")
            elif revenue > rule["income_limit_uit"] * uit:
                reasons.append("Los ingresos proyectados superan el límite de referencia de 1,700 UIT.")
            if declared_exclusion:
                reasons.append("Se indicó una posible exclusión; debe verificarse frente al D. Leg. 1269.")

        applicable = not reasons
        eligibility_status = (
            "unknown"
            if code == "RMT" and missing_uit_for_rmt and len(reasons) == 1
            else "eligible" if applicable else "not_eligible"
        )
        if code == "NRUS":
            monthly_band = max(monthly_income, monthly_purchases, revenue / 12, purchase / 12)
            monthly_tax = 0 if monthly_band <= 0 else (20 if monthly_band <= 5000 else 50 if monthly_band <= 8000 else None)
            annual_income_tax = monthly_tax * 12 if monthly_tax is not None else None
            annual_igv = 0
        elif code == "RER":
            monthly_tax = revenue * 0.015 / 12
            annual_income_tax = revenue * 0.015
            annual_igv = estimated_igv
        elif code == "RMT":
            monthly_tax = None
            annual_income_tax = None if not uit or uit <= 0 else min(net_income, RMT_FIRST_BRACKET_UIT * uit) * RMT_FIRST_BRACKET_RATE + max(0, net_income - RMT_FIRST_BRACKET_UIT * uit) * TAX_RATE_GENERAL
            annual_igv = estimated_igv
        else:
            monthly_tax = None
            annual_income_tax = net_income * TAX_RATE_GENERAL
            annual_igv = estimated_igv

        if applicable and annual_income_tax is not None:
            total_cost = annual_income_tax + annual_igv
        else:
            total_cost = None
        if rule.get("income_limit"):
            limits.append(f"Ingresos: S/ {rule['income_limit']:,.0f} anuales")
        if rule.get("purchase_limit"):
            limits.append(f"Compras: S/ {rule['purchase_limit']:,.0f} anuales")
        if rule.get("income_limit_uit"):
            limits.append(f"Ingresos: {rule['income_limit_uit']:,} UIT")
        regime_results[code] = {
            "code": code,
            "name": rule["name"],
            "applicable": applicable,
            "eligibility_status": eligibility_status,
            "reasons": reasons,
            "limits": limits,
            "estimated_monthly_income_tax": round(monthly_tax, 2) if monthly_tax is not None else None,
            "estimated_annual_income_tax": round(annual_income_tax, 2) if annual_income_tax is not None else None,
            "estimated_annual_igv": round(annual_igv, 2) if applicable else None,
            "estimated_annual_total": round(total_cost, 2) if total_cost is not None else None,
            "legal_source": rule["source"],
            "caveat": "Estimación académica; pagos a cuenta y determinación final dependen de reglas, créditos y datos no modelados.",
        }

    for code, rule in REGIME_RULES.items():
        if code in ("NRUS", "RER"):
            limit = rule["income_limit"]
            if limit and revenue >= limit * 0.8:
                alerts.append(f"{code}: los ingresos proyectados se acercan al límite anual de referencia.")
        if code == "RER" and purchase >= rule["purchase_limit"] * 0.8:
            alerts.append("RER: las compras proyectadas se acercan al límite anual de referencia.")
    if plans.get("increase_income"):
        alerts.append("El plan de crecimiento puede cambiar la elegibilidad; vuelve a evaluar con la proyección actualizada.")
    if plans.get("exceed_limits"):
        alerts.append("Se prevé superar límites del régimen actual; revisa el momento y las reglas de cambio de régimen.")
    if plans.get("add_branches") or plans.get("add_activities") or plans.get("grow_company"):
        alerts.append("Los planes de expansión pueden afectar la elegibilidad o las obligaciones; confirma el supuesto legal aplicable.")
    if plans.get("excluded_activity"):
        alerts.append("Se declaró un plan de actividad potencialmente excluida; revisa la norma antes de acogerte.")
    if declared_exclusion:
        alerts.append("Se marcó una posible actividad excluida. La descripción requiere revisión profesional.")

    applicable_codes = [
        code for code, result in regime_results.items()
        if result["eligibility_status"] == "eligible" and result["estimated_annual_total"] is not None
    ]
    recommendation: str
    reason: str
    decision_method = "Ponderación académica: carga estimada relativa (60%), ajuste a planes declarados (25%) y simplicidad de cumplimiento (15%). No es un criterio legal."
    decision_scores: dict[str, dict[str, float]] = {}
    if enough_data and applicable_codes:
        tax_values = {code: float(regime_results[code]["estimated_annual_total"] or 0) for code in applicable_codes}
        max_tax = max(tax_values.values(), default=0)
        growth = any(plans.get(key) for key in ("increase_income", "exceed_limits", "add_branches", "add_activities", "grow_company"))
        complexity_factor = {"NRUS": 0.0, "RER": 0.25, "RMT": 0.6, "RG": 0.9}
        growth_risk = {"NRUS": 1.0, "RER": 0.7, "RMT": 0.25, "RG": 0.1}
        for code in applicable_codes:
            relative_tax = tax_values[code] / max_tax if max_tax else 0
            future_fit = growth_risk[code] if growth else 0
            if plans.get("import") or plans.get("export"):
                future_fit += 0.2 if code == "NRUS" else 0
            score = 0.60 * relative_tax + 0.25 * min(future_fit, 1) + 0.15 * complexity_factor[code]
            decision_scores[code] = {"total_score": round(score, 4), "relative_tax_factor": round(relative_tax, 4), "future_fit_factor": round(min(future_fit, 1), 4), "complexity_factor": complexity_factor[code]}
        recommendation = min(applicable_codes, key=lambda code: decision_scores[code]["total_score"])
        reason = (
            f"{recommendation} es la alternativa recomendada entre los regímenes con elegibilidad modelada, "
            "ponderando la carga estimada, los planes declarados y la complejidad de cumplimiento. "
            "La recomendación es académica y no equivale a asesoría profesional."
        )
    else:
        recommendation = "RG"
        decision_method = "Criterio prudencial: ante información incompleta no se comparan como concluyentes las cargas estimadas; se sugiere el Régimen General como alternativa de referencia sin límite general de ingresos."
        reason = (
            "RG es la recomendación provisional más prudente con la información disponible, "
            "porque no tiene un límite general de ingresos modelado. Completa los datos faltantes "
            "y valida las condiciones legales antes de elegirlo."
        )
    if not enough_data:
        missing_inputs = [
            label for key, label in (
                ("activity", "actividad económica"),
                ("person_type", "tipo de persona"),
                ("monthly_income", "ingresos mensuales"),
                ("projected_annual_income", "ingresos anuales proyectados"),
                ("monthly_purchases", "compras mensuales"),
                ("projected_annual_purchases", "compras anuales proyectadas"),
                ("annual_costs", "costos anuales"),
                ("annual_expenses", "gastos anuales"),
                ("fixed_assets", "activos fijos"),
                ("taxable_share", "proporción de operaciones gravadas"),
                ("workers", "cantidad de trabajadores"),
                ("workers_per_shift", "trabajadores por turno"),
            )
            if data.get(key) in (None, "")
        ]
        exclusions.append("Información incompleta: " + ", ".join(missing_inputs) + ".")
    if not uit:
        exclusions.append("La elegibilidad y el impuesto anual del RMT no se pudieron verificar sin configurar la UIT en Perfil.")
    if plans.get("excluded_activity"):
        exclusions.append("Se planea incorporar una actividad potencialmente excluida; confirma su compatibilidad antes de acogerte al régimen recomendado.")
    exclusions.append("Las actividades excluidas completas y otras condiciones legales no se validan automáticamente; confirma la elegibilidad con la norma vigente.")
    future = []
    if plans.get("increase_income"):
        future.append("Incremento de ingresos declarado: actualice las proyecciones y revise límites antes de cada periodo.")
    if plans.get("hire_workers"):
        future.append("Contratación prevista: revise límites por trabajadores y obligaciones laborales/tributarias.")
    if plans.get("add_branches"):
        future.append("Apertura de sucursales prevista: confirme impacto en elegibilidad y deberes formales.")
    if plans.get("import") or plans.get("export"):
        future.append("Operaciones de comercio exterior previstas: confirme compatibilidad y obligaciones aduaneras.")
    if not future:
        future.append("No se declararon planes futuros que modifiquen la evaluación.")

    regime_benefits = {
        "NRUS": "Cuotas simplificadas y menores exigencias contables para actividades y contribuyentes que sí cumplen sus requisitos.",
        "RER": "Determinación simplificada del impuesto a la renta mediante pago mensual definitivo, sujeto a sus condiciones.",
        "RMT": "Escala progresiva anual de renta para contribuyentes comprendidos, con obligaciones ajustadas a sus ingresos.",
        "RG": "Sin límite general de ingresos y reglas aplicables a actividades empresariales de mayor alcance.",
    }
    return {
        "eligible_regimes": [
            code for code, result in regime_results.items()
            if result["eligibility_status"] == "eligible"
        ],
        "regimes": regime_results,
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "decision_method": decision_method,
        "decision_scores": decision_scores,
        "recommendation_benefits": regime_benefits[recommendation] if recommendation else None,
        "recommendation_obligations": REGIME_RULES[recommendation]["obligations"] if recommendation else None,
        "recommendation_limitations": REGIME_RULES[recommendation]["exclusions"] if recommendation else None,
        "alternatives_considered": [
            {
                "regime": code,
                "estimated_total": regime_results[code]["estimated_annual_total"],
                "reason_not_selected": "La evaluación pondera cargas estimadas, simplicidad de cumplimiento y planes futuros; la menor cifra no determina por sí sola la recomendación.",
            }
            for code in applicable_codes if code != recommendation
        ],
        "recommendation_risks": alerts,
        "future_projection": future,
        "alerts": alerts,
        "missing_or_caveats": exclusions,
        "economic_summary": {
            "annual_income": round(revenue, 2),
            "annual_purchases": round(purchase, 2),
            "estimated_taxable_margin": round(net_income, 2),
        },
        "assumptions": [
            "Parámetros referenciales integrados para fines académicos; confirmar vigencia y supuestos con SUNAT.",
            "El IGV estimado simplifica crédito fiscal a partir de compras; excluye ajustes, prorrata y operaciones especiales.",
            "Pagos a cuenta del RMT y RG requieren coeficientes e información fiscal del periodo previo, que no se modelan.",
            "Las compras no se tratan automáticamente como costo deducible para renta; la deducción depende de su reconocimiento y requisitos.",
            "La elegibilidad no sustituye la verificación de exclusiones completas, vinculación económica ni historial tributario.",
        ],
    }


def regime_catalog(uit: float | None = None) -> list[dict[str, Any]]:
    result = []
    for code, rule in REGIME_RULES.items():
        item = dict(rule)
        item["code"] = code
        item["effective_income_limit"] = (
            round(rule["income_limit_uit"] * uit, 2)
            if rule.get("income_limit_uit") and uit
            else rule.get("income_limit")
        )
        result.append(item)
    return result
