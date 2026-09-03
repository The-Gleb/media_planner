"""Кривая отклика «расход → показы» с ростом цены при выкупе ёмкости.

eCPM растёт линейно с долей выкупленной ёмкости: cpm_eff = cpm * (1 + k * impressions / capacity).
Тогда spend = impressions * cpm_eff / 1000 — квадратное уравнение относительно impressions,
решается в замкнутой форме. Кривая вогнутая, насыщается, упирается в жёсткий потолок capacity.
"""

import math


def compute_impressions(spend_rub: float, cpm_rub: float, capacity: float, price_growth: float) -> float:
    if spend_rub <= 0 or capacity <= 0:
        return 0.0
    raw_impressions = 1000.0 * spend_rub / cpm_rub
    if price_growth <= 0:
        return min(raw_impressions, capacity)
    discriminant = 1.0 + 4.0 * price_growth * raw_impressions / capacity
    impressions = (math.sqrt(discriminant) - 1.0) * capacity / (2.0 * price_growth)
    return min(impressions, capacity)


def compute_spend(impressions: float, cpm_rub: float, capacity: float, price_growth: float) -> float:
    if impressions <= 0:
        return 0.0
    effective_cpm = cpm_rub * (1.0 + price_growth * impressions / capacity)
    return impressions * effective_cpm / 1000.0
