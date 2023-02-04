from itertools import groupby


def all(iterable):
    # https://stackoverflow.com/questions/3844801/check-if-all-elements-in-a-list-are-identical
    g = groupby(iterable)
    return next(g, True) and not next(g, False)


def diff(iterable):
    # Opposite of all - returns True if any element is different
    return not (all(iterable))
