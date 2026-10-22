"""Domain-specific errors for the stock market."""


class StockError(Exception):
    """Base class for user-facing stock errors."""


class ValidationError(StockError):
    pass


class NotFoundError(StockError):
    pass


class InsufficientFundsError(StockError):
    pass


class InsufficientSharesError(StockError):
    pass


class NoSupplyError(StockError):
    pass


class TradingHaltedError(StockError):
    pass


class LimitError(StockError):
    pass
