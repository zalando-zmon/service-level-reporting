import io
import json
import pathlib
import re
import sys

import boto3

S3_BUCKET='zalando-slr-service-level-reporting-s3-bucket'
FILEPATH_PATTERN = re.compile(r"([\w/\-.]+(?:\.debug\.json|.tsv))")
OUTPUT_DIR = pathlib.Path('output/')
OUTPUT_DIR.mkdir(exist_ok=True)

s3 = boto3.client('s3')

log_file = open(sys.argv[1])
for line in log_file:
    filepath = FILEPATH_PATTERN.findall(line)
    if not filepath:
        continue
    filepath = filepath[0][5:]

    stream = io.BytesIO()
    s3.download_fileobj(S3_BUCKET, filepath, stream)
    output_path = OUTPUT_DIR / filepath
    output_path.parent.mkdir(exist_ok=True, parents=True)
    output_path.write_bytes(stream.getvalue())

    tb_data = json.loads(stream.getvalue())
    gnuplot_result = ''.join(tb_data['gnuplot_result']).strip()
    tsvpath = FILEPATH_PATTERN.findall(gnuplot_result)
    if tsvpath:
        tsvpath = tsvpath[0]
        tsv = tb_data['tsvs'][tsvpath]
    else:
        for name, content in tb_data['tsvs'].items():
            tsv += f'{name}\n{content}\n\n'

    print(f"{filepath}\n\nGnuplot result:\n{gnuplot_result}\n\nTSV:\n{tsv}\n-------")
