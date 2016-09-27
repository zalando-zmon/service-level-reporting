#!/usr/bin/env python3

import requests
import subprocess
import sys
import zign.api


def plot(base_url, product, sli):
    fn = '/tmp/data.tsv'

    url = '{}/service-level-indicators/{}/{}'.format(base_url, product, sli)
    resp = requests.get(url, headers={'Authorization': 'Bearer {}'.format(zign.api.get_token('zmon', ['uid']))})
    resp.raise_for_status()

    with open(fn, 'w') as fd:
        data = resp.json()
        for row in data:
            fd.write('{}\t{}\n'.format(row[0], row[1]))

    plot = subprocess.Popen(['gnuplot'], stdin=subprocess.PIPE)

    gnuplot_data = '''
    set term png enhanced size 800, 400
    set xdata time
    set format x "%m-%d"
    set format y "%.0f ms"
    set yrange [50:500]
    set timefmt "%Y-%m-%dT%H:%M:%SZ"
    set arrow from graph 0,first 200 to graph 1, first 200 nohead linecolor rgb "#990000" back
    plot '{}' using 1:2 with lines title '{}'
    '''.format(fn, sli.replace('_', ' '))
    plot.communicate(gnuplot_data.encode('utf-8'))

url = sys.argv[1]
product = sys.argv[2]
sli = sys.argv[3]
plot(url, product, sli)
