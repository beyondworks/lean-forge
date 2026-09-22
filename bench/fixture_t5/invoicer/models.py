from dataclasses import dataclass, field
from datetime import date


@dataclass
class LineItem:
    name: str
    unit_price: int  # won
    qty: int


@dataclass
class Invoice:
    id: str
    customer: str
    issued: date
    items: list = field(default_factory=list)
    discount_rate: float = 0.0  # 0.1 == 10% off
