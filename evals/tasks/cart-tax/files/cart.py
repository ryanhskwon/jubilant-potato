from pricing import apply_discount


class Cart:
    def __init__(self, discount_percent=0, tax_rate=0.1):
        self.items = []
        self.discount_percent = discount_percent
        self.tax_rate = tax_rate

    def add(self, price, qty=1):
        self.items.append((price, qty))

    def subtotal(self):
        return sum(p * q for p, q in self.items)

    def total(self):
        return apply_discount(self.subtotal(), self.discount_percent)
