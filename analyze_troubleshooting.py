"""
Provided with a path to the file with logs from a reports generator run,
this script looks for all debug file locations, downloads them from S3 bucket
and tries to match them to the well-known errors.
If cannot do so, dumps all the necessary troubleshooting data into OUTPUT_DIR
in a convenient format.
"""
import io
import json
import pathlib
import re
import shutil
import sys

import boto3

S3_BUCKET='zalando-slr-service-level-reporting-s3-bucket'
FILEPATH_PATTERN = re.compile(r"([\w/\-.]+(?:\.debug\.json|.tsv))")
YRANGE_TOO_SMALL = re.compile(r"set\s+yrange\s+\[(.+):\1\]")
OUTPUT_DIR = pathlib.Path('troubleshooting/')
shutil.rmtree(OUTPUT_DIR, ignore_errors=True)

s3 = boto3.client('s3')

log_file = open(sys.argv[1])
for line in log_file:
    filepath = FILEPATH_PATTERN.findall(line)
    if not filepath:
        continue
    filepath = filepath[0].replace('/var/', '')

    stream = io.BytesIO()
    s3.download_fileobj(S3_BUCKET, filepath, stream)

    tb_data = json.loads(stream.getvalue())
    gnuplot_result = ''.join(tb_data['gnuplot_result']).strip()
    gnuplot_data = tb_data['gnuplot_data']

    issues = set()
    if YRANGE_TOO_SMALL.findall(tb_data['gnuplot_data']):
        issues.add('YRANGE_TOO_SMALL')

    tsv_paths = FILEPATH_PATTERN.findall(gnuplot_data)
    for tsv_path in tsv_paths:
        tsv = tb_data['tsvs'][tsv_path]
        if not tsv:
            issues.add('NO_SLI_VALUES')

    if not issues:
        issues.add('N/A')
        OUTPUT_DIR.mkdir(exist_ok=True)

        output_path = OUTPUT_DIR / (filepath.replace('/', '_'))
        output_path.mkdir()
        (output_path / 'tb_data.json').write_bytes(stream.getvalue())

        (output_path / 'gnuplot_result').write_text(gnuplot_result)
        (output_path / 'gnuplot_data').write_text(gnuplot_data)
        
        for tsv_path in FILEPATH_PATTERN.findall(gnuplot_data):
            (output_path / tsv_path.replace('/', '_')).write_text(tb_data['tsvs'][tsv_path])

    print(f"{filepath:180} {','.join(issues)}")
