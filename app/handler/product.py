import logging

from psycopg2 import IntegrityError
from connexion import NoContent, ProblemException

from app.db import dbconn
from app.utils import strip_column_prefix, slugger


logger = logging.getLogger('slo-product')


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

        cur.execute('''SELECT * FROM zsm_data.product_group WHERE pg_slug = %s''', (product['product_group'],))
        row = cur.fetchone()
        if not row:
            raise ProblemException(
                status=404,
                title='Product group not found',
                detail='Can not find product group: {}'.format(product['product_group']))

        product_group = strip_column_prefix(row._asdict())

        try:
            cur.execute('''INSERT INTO zsm_data.product (p_name, p_slug, p_product_group_id) VALUES (%s, %s, %s)''',
                        (product['name'], slugger(product['name']), product_group['id'],))
            conn.commit()
        except IntegrityError:
            raise ProblemException(
                title='Product already exists',
                detail='Product with name: "{}" already exists!'.format(product['name']))

        return NoContent, 201


def delete(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''DELETE FROM zsm_data.product WHERE p_slug = %s''', (product,))
        conn.commit()
        return (NoContent, 200,) if cur.rowcount else (NoContent, 404,)
