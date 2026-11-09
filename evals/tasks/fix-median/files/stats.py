def median(values):
    """Median of values. Raises ValueError on an empty list."""
    if not values:
        raise ValueError("empty")
    s = sorted(values)
    return s[len(s) // 2]
