"""Метрики близости факта к плану: APE в конце кампании и MAPE по траектории."""

import numpy as np
import numpy.typing as npt


def compute_end_ape(planned: npt.NDArray[np.float64], actual: npt.NDArray[np.float64]) -> float:
    """Абсолютная процентная ошибка накопленного значения к концу кампании."""
    planned_final = float(planned[-1])
    if planned_final == 0:
        return 0.0
    return abs(float(actual[-1]) - planned_final) / planned_final


def compute_end_deviation(planned: npt.NDArray[np.float64], actual: npt.NDArray[np.float64]) -> float:
    """Знаковое отклонение к концу кампании: положительное — факт выше плана."""
    planned_final = float(planned[-1])
    if planned_final == 0:
        return 0.0
    return (float(actual[-1]) - planned_final) / planned_final


def compute_trajectory_mape(planned: npt.NDArray[np.float64], actual: npt.NDArray[np.float64]) -> float:
    """Средняя абсолютная процентная ошибка по всем часам накопительной траектории."""
    nonzero_mask = planned > 0
    if not nonzero_mask.any():
        return 0.0
    relative_errors = np.abs(actual[nonzero_mask] - planned[nonzero_mask]) / planned[nonzero_mask]
    return float(relative_errors.mean())
