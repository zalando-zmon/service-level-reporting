from connexion import NoContent

from app.handler.db import dbconn
from app.slo import process_sli
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


def update_service_level_objectives(product):
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT sli_name, EXTRACT(EPOCH FROM now() - MAX(sli_timestamp)) AS seconds_ago
                FROM zsm_data.service_level_indicator
                JOIN zsm_data.product ON p_id = sli_product_id
                WHERE p_slug = %s
                GROUP BY sli_name''', (product,))
        rows = cur.fetchall()
    res = {}
    for row in rows:
        res[row.sli_name] = {'start': (row.seconds_ago // 60) + 5}
        response = post_update(product, row.sli_name, res[row.sli_name])
        res[row.sli_name]['count'] = response['count']

    return res


def post_update(product, name, body):
    kairosdb_url = os.getenv('KAIROSDB_URL')
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT ds_definition FROM zsm_data.data_source WHERE '
            'ds_product_id = (SELECT p_id FROM zsm_data.product WHERE p_slug = %s) AND ds_sli_name = %s',
            (product, name))
        row = cur.fetchone()
        if not row:
            return 'Not found', 404
        definition, = row
    count = process_sli(product, name, definition, kairosdb_url, body.get('start', 5), 'minutes', database_uri)
    return {'count': count}


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
