import json

from connexion import NoContent

from app.db import dbconn
from app.utils import strip_column_prefix


def get(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT p.p_name, p.p_slug, ds.ds_sli_name, ds.ds_definition FROM zsm_data.product AS p,
            zsm_data.data_source AS ds  WHERE p.p_id=ds.ds_product_id AND p.p_slug = %s
        ''', (product,))
        rows = cur.fetchall()
        res = [strip_column_prefix(r._asdict()) for r in rows]
    return res


def add(product, data_source):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''
        INSERT INTO zsm_data.data_source (ds_product_id, ds_sli_name, ds_definition)
        VALUES ((SELECT p_id FROM zsm_data.product WHERE p_slug = %s), %s, %s)
        ''', (product, data_source['sli_name'], json.dumps(data_source['definition']),))
        conn.commit()
        return NoContent, 201


def delete(product, sli_name):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''
        DELETE FROM zsm_data.data_source WHERE ds_product_id =
        (SELECT p_id FROM zsm_data.product WHERE p_slug = %s) AND ds_sli_name = %s
        ''', (product, sli_name))
        conn.commit()
        return (NoContent, 200) if cur.rowcount != 0 else (NoContent, 404)
