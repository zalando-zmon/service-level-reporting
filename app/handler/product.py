import logging

import connexion
from connexion import NoContent
from psycopg2 import IntegrityError

from app.db import dbconn
from app.utils import strip_column_prefix, slugger

logger = logging.getLogger('slo-product')


def get(pg=None):
    with dbconn() as conn:
        cur = conn.cursor()
        param_dict = {}
        if pg:
            param_dict['pg'] = pg
            clause = ' AND pg_slug = %(pg)s '
        else:
            clause = ''
        cur.execute('''SELECT p.*, pg_name AS pg_product_group_name, pg_slug AS pg_product_group_slug, pg_department
                FROM zsm_data.product p, zsm_data.product_group pg WHERE pg_id = p_product_group_id''' + clause,
                    param_dict)
        rows = cur.fetchall()
        res = [strip_column_prefix(r._asdict()) for r in rows]
    return res


def get_product(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT p_product_group_id, p_name, p_slug, p_delivery_team
            FROM zsm_data.product WHERE p_slug = %s''', (product,))
        rows = cur.fetchall()
        if len(rows) < 1:
            return connexion.problem(status=404, title='Product not found',
                                     detail='Product with id {} does not exist'.format(product))
        else:
            return strip_column_prefix(rows[0]._asdict())


def add(product):
    with dbconn() as conn:
        cur = conn.cursor()

        cur.execute('''SELECT * FROM zsm_data.product_group WHERE pg_slug = %s''', (product['product_group'],))
        row = cur.fetchone()
        if not row:
            return connexion.problem(status=404, title='Product group not found',
                                     detail='Can not find product group: {}'.format(product['product_group']))

        product_group = strip_column_prefix(row._asdict())

        try:
            cur.execute('''INSERT INTO zsm_data.product (p_name, p_slug, p_product_group_id) VALUES (%s, %s, %s)''',
                        (product['name'], slugger(product['name']), product_group['id'],))
            conn.commit()
        except IntegrityError:
            return connexion.problem(status=400, title='Product Already Exists',
                                     detail='Product with name: "{}" already exists!'.format(product['name']))
        return NoContent, 201


def delete(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''DELETE FROM zsm_data.product WHERE p_slug = %s''', (product,))
        conn.commit()
        return (NoContent, 200,) if cur.rowcount else (NoContent, 404,)
