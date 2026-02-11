"""Optional registry: name -> forecaster class for config-driven runs."""

from typing import Type

from forecasting_lab.models.base import BaseForecaster


_REGISTRY: dict[str, Type[BaseForecaster]] = {}


def register(name: str, cls: Type[BaseForecaster]) -> None:
    _REGISTRY[name] = cls


def get(name: str) -> BaseForecaster:
    if name not in _REGISTRY:
        if name == "hybrid":
            from forecasting_lab.models.hybrid_ensemble_forecaster import HybridEnsembleForecaster
            register("hybrid", HybridEnsembleForecaster)
        else:
            raise ValueError(f"Unknown model: {name}. Registered: {list(_REGISTRY)}")
    return _REGISTRY[name]()


# Built-in
from forecasting_lab.models.naive_forecaster import NaiveForecaster  # noqa: E402
register("naive", NaiveForecaster)
