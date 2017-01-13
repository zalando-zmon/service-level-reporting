from app.db import dbconn


def get_service_level_indicators(product, name, time_from=None, time_to=None):
    # TODO: allow filtering by time_from/time_to
    with dbconn() as conn:
        cur = conn.cursor()
        cur.execute('''SELECT sli_timestamp, sli_value FROM zsm_data.service_level_indicator
        WHERE sli_product_id = (SELECT p_id FROM zsm_data.product WHERE p_slug = %s) AND sli_name = %s
        AND sli_timestamp >= date_trunc(\'day\', \'now\'::TIMESTAMP - INTERVAL \'7 days\')
        ORDER BY 1''', (product, name))
        return cur.fetchall()
