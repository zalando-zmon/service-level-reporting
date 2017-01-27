from connexion import NoContent

from app.db import dbconn
from app.utils import strip_column_prefix, slugger


def get():
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT p.*, pg_name AS pg_product_group_name, pg_slug AS pg_product_group_slug, pg_department
                FROM zsm_data.product p
                JOIN zsm_data.product_group ON pg_id = p_product_group_id''')
        rows = cur.fetchall()
        res = [strip_column_prefix(r._asdict()) for r in rows]
    return res


def add(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute(
            '''INSERT INTO zsm_data.product (p_name, p_slug, p_product_group_id)
              VALUES (%s, %s, (SELECT pg_id FROM zsm_data.product_group WHERE pg_slug = %s))''',
            (product['name'], slugger(product['name']), product['product_group']))
        conn.commit()
        cur.close()
        return NoContent, 201


def delete(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''DELETE FROM zsm_data.product WHERE p_slug = %s''', (product,))
        conn.commit()
        return (NoContent, 200,) if cur.rowcount else (NoContent, 404,)
