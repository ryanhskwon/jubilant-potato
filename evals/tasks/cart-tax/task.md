Fix the cart total.
1. `apply_discount()` in `pricing.py` has a bug. `percent` is a value between 0 and 100 (e.g. 10 = 10% off).
2. Add `add_tax(amount, rate)` to `pricing.py`. `rate` is a value between 0 and 1 (e.g. 0.1 = 10%). Round the result to two decimal places.
3. Fix `Cart.total()` in `cart.py` so it returns the discounted amount plus tax (default 0.1).
