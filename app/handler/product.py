from connexion import NoContent

from app.handler.db import dbconn
from app.utils import strip_column_prefix


def get_products():
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT p.*, pg_name AS pg_product_group_name, pg_slug AS pg_product_group_slug, pg_department
                FROM zsm_data.product p
                JOIN zsm_data.product_group ON pg_id = p_product_group_id''')
        rows = cur.fetchall()
        res = [strip_column_prefix(r._asdict()) for r in rows]
    return res


def add_product(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute(
            '''INSERT INTO zsm_data.product (p_product_group_id, p_name, p_slug, p_delivery_team)
              VALUES (%s, %s, %s, %s)''',
            (product['product_group_id'], product['name'], product['slug'], product['delivery_team']))
        conn.commit()
        cur.close()
        return NoContent, 201
