from enum import Enum


class SeverityBaseInterface(Enum):
    def __new__(cls, severity_name, severity_order):
        obj = object.__new__(cls)
        obj._value_ = severity_name
        obj.severity_order = severity_order
        return obj

    @property
    def order(self):
        return self.severity_order

    def __str__(self):
        return self._value_

    @classmethod
    def from_number(cls, n):
        for severity in cls:
            if severity.order == n:
                return severity
        raise ValueError(f"No AlertSeverity with order {n}")

    def __lt__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order < other.order
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order <= other.order
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order > other.order
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, SeverityBaseInterface):
            return self.order >= other.order
        return NotImplemented
