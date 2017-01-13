from connexion import NoContent

from app.db import dbconn
from app.utils import strip_column_prefix


def get_service_level_objectives(product):
    res = []
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT slo_id, slo_title
                FROM zsm_data.service_level_objective slo
                JOIN zsm_data.product ON p_id = slo_product_id
                WHERE p_slug = %s''', (product,))
        rows = cur.fetchall()
        for row in rows:
            d = strip_column_prefix(row._asdict())
            cur.execute(
                'SELECT slit_from, slit_to, slit_sli_name, slit_unit FROM '
                'zsm_data.service_level_indicator_target WHERE slit_slo_id = %s',
                (row.slo_id,))
            targets = cur.fetchall()
            d['targets'] = [strip_column_prefix(r._asdict()) for r in targets]
            res.append(d)
    return res





def add_slo(product, slo):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('INSERT INTO zsm_data.service_level_objective (slo_title, slo_product_id) '
                    'VALUES (%s, (SELECT p_id FROM zsm_data.product WHERE p_slug= %s)) RETURNING slo_id',
                    (slo['title'], product))
        slo_id = cur.fetchone()[0]
        for t in slo['targets']:
            cur.execute('INSERT INTO zsm_data.service_level_indicator_target '
                        '(slit_slo_id,slit_sli_name,slit_unit,slit_from,slit_to)'
                        'VALUES (%s, %s, %s, %s, %s)', (slo_id, t['sli_name'], t['unit'], t['from'], t['to']))
        conn.commit()
        return NoContent, 201
