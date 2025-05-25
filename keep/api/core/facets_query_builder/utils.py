import hashlib


def get_facet_key(facet_property_path: str, filter_cel, facet_cel: str) -> str:
    """
    Generates a unique key for the facet based on its property path and CEL expression.

    Args:
        facet_property_path (str): The property path of the facet.
        facet_cel (str): The CEL expression associated with the facet.

    Returns:
        str: A unique key for the facet.
    """
    return (
        facet_property_path
        + hashlib.sha1((filter_cel + facet_cel).encode("utf-8")).hexdigest()
    )
