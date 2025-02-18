def filter_kwargs(**kwargs):
    """Remove None values from keyword arguments."""
    return {k: v for k, v in kwargs.items() if v is not None}
