from decimal import Decimal

from slugify import Slugify
from connexion.decorators.produces import JSONEncoder


custom_slugify = Slugify(to_lower=True)


class DecimalEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)

        return super().default(o)


def strip_column_prefix(d):
    res = {}
    for k, v in d.items():
        res[k.split('_', 1)[1]] = v
    return res


def slugger(name: str) -> str:
    return custom_slugify(name)
