from src.monitoring.price_monitor import PriceMonitor


class FakeDb:
    def __init__(self, forecast_price: float, current_price: float) -> None:
        self._forecast_price = forecast_price
        self._current_price = current_price

    def get_latest_forecast(self, symbol: str):
        return {
            "points": [{"value": self._forecast_price}],
            "atr": self._forecast_price * 0.02,
        }

    def get_current_prices(self, symbol: str):
        return {"d1": {"close": self._current_price}}


def test_price_monitor_triggers_on_atr_move():
    db = FakeDb(forecast_price=100.0, current_price=110.0)
    monitor = PriceMonitor(
        db_client=db,
        move_threshold_atr=2.0,
        move_threshold_pct=5.0,
    )
    trigger = monitor._check_symbol("AAPL")
    assert trigger is not None
    assert trigger.atr_move >= 2.0


def test_price_monitor_no_trigger_when_small_move():
    db = FakeDb(forecast_price=100.0, current_price=101.0)
    monitor = PriceMonitor(
        db_client=db,
        move_threshold_atr=2.0,
        move_threshold_pct=5.0,
    )
    trigger = monitor._check_symbol("AAPL")
    assert trigger is None
