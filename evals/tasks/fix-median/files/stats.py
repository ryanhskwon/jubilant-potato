def median(values):
    """values의 중앙값. 빈 리스트면 ValueError."""
    if not values:
        raise ValueError("empty")
    s = sorted(values)
    return s[len(s) // 2]
