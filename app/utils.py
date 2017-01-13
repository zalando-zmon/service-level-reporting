from slugify import Slugify

custom_slugify = Slugify(to_lower=True)


def strip_column_prefix(d):
    res = {}
    for k, v in d.items():
        res[k.split('_', 1)[1]] = v
    return res


def slugger(name: str):
    return custom_slugify(name)
