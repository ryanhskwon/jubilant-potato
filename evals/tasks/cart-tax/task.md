장바구니 합계를 고치세요.
1. `pricing.py`의 `apply_discount()`에 버그가 있습니다. `percent`는 0~100 사이 값입니다 (예: 10 = 10% 할인).
2. `pricing.py`에 `add_tax(amount, rate)`를 추가하세요. `rate`는 0~1 사이 값입니다 (예: 0.1 = 10%). 결과는 소수 둘째 자리에서 반올림합니다.
3. `cart.py`의 `Cart.total()`이 할인 후 세금(기본 0.1)을 더한 금액을 반환하도록 고치세요.
