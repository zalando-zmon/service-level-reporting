from connexion import NoContent

from app.handler.db import dbconn


def get_product_groups():
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT pg_name, pg_slug, pg_department FROM zsm_data.product_group''')
        rows = cur.fetchall()
        return rows


def add_product_group(product_group):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''INSERT INTO zsm_data.product_group (pg_name, pg_department, pg_slug) VALUES (%S, %S, %S)''',
                    (product_group['name'], product_group['department'], product_group['slug']))
        conn.commit()
        cur.close()
        return NoContent, 201
