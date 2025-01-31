# Maybe to use 'pluralize' from 'inflect' library in the future
def pluralize(count: int, singular: str, plural: str | None = None, include_count: bool = True) -> str:
    """
    Returns a string with the correct plural or singular form based on count.
    
    Args:
        count: The number of items
        singular: The singular form of the word
        plural: The plural form of the word. If None, appends 's' to singular form
        include_count: Whether to include the count in the returned string
    
    Examples:
        >>> pluralize(1, "incident")
        "1 incident"
        >>> pluralize(2, "incident")
        "2 incidents"
        >>> pluralize(2, "category", "categories")
        "2 categories"
        >>> pluralize(1, "incident", include_count=False)
        "incident"
    """
    if plural is None:
        plural = singular + 's'
        
    word = plural if count != 1 else singular
    return f"{count} {word}" if include_count else word