#!/usr/bin/env python3

import logging
import os
import subprocess
import sys
import time
from datetime import datetime

import zign.api

from zmon_slr.client import Client
from zmon_slr.generate_slr import generate_weekly_report

OUTPUT_DIR = os.environ.get('SLR_OUTPUT_DIR', '/var/www/reports')

SLR_URI = os.environ.get('SLR_URI')
SLR_TOKEN = os.environ.get('SLR_TOKEN')
S3_BUCKET = os.environ.get('SLR_S3_BUCKET')


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.setLevel(logging.INFO)


def sync_reports(to_local=True):
    if not S3_BUCKET:
        return

    src, dst = (S3_BUCKET, OUTPUT_DIR) if to_local else (OUTPUT_DIR, S3_BUCKET)

    retries = 5

    while retries:
        try:
            logger.info('Starting S3 sync from {} to {}'.format(src, dst))

            res = subprocess.check_output(['aws', 's3', 'sync', src, dst], stderr=subprocess.STDOUT)
            for line in res.splitlines():
                logger.debug(line)

            retries = 0
            logger.info('Successfully completed S3 sync from {} to {}'.format(src, dst))
        except subprocess.CalledProcessError:
            retries -= 1
            logger.exception('Failed to S3 sync from {} to {}'.format(src, dst))
            time.sleep(60)


def main():
    if not SLR_URI:
        logger.error('SLR_URI environment variable is required. Terminating ...')
        sys.exit(1)

    try:
        subprocess.check_output(['which', 'gnuplot'])
    except subprocess.CalledProcessError:
        logger.error('Missing system dependency. Please install *gnuplot* system package!')
        sys.exit(1)

    successful_reports = []

    t_start = datetime.now()

    # Get last reports
    sync_reports(to_local=True)

    try:
        token = SLR_TOKEN if SLR_TOKEN else zign.api.get_token('uid', ['uid'])
        client = Client(SLR_URI, token)

        # 1. Get all products
        logger.info('Starting reports generation ...')
        products = client.product_list(limit=1000)

        for product in products:

            # Token could expire if report generation takes a long time!
            token = SLR_TOKEN if SLR_TOKEN else zign.api.get_token('uid', ['uid'])
            client = Client(SLR_URI, token)

            name = product['name']
            try:
                # Make sure the product has the minimum req for generating a report
                slos = client.slo_list(product)
                if not slos:
                    logger.info('Skipping generating report for product "{}". Reason: No SLO defined!'.format(name))
                    continue

                slis = client.sli_list(product)
                if not slis:
                    logger.info('Skipping generating report for product "{}". Reason: No SLI defined!'.format(name))
                    continue

                # Finally, generate the report
                logger.info('Generating report for product: {}'.format(name))
                generate_weekly_report(client, product, OUTPUT_DIR)
                logger.info('Finished generating report for product: {}'.format(name))

                successful_reports.append(name)

                if not len(successful_reports) % 10:
                    time.sleep(60)

            except KeyboardInterrupt:
                logger.info('Report generation interrupted. Terminating ...')
                return
            except Exception:
                logger.exception('Failed to generate report for product: {}'.format(name))
    except KeyboardInterrupt:
        logger.info('Report generation interrupted. Terminating ...')
        return
    except Exception:
        logger.exception('Failed in generating reports. Terminating ...')
        sys.exit(1)

    duration = datetime.now() - t_start

    logger.info('Finished generating reports for products: {}'.format(successful_reports))
    logger.info('Finished generating reports for {} products successfully in {} minutes'.format(
        len(successful_reports), duration.seconds / 60))

    # Upload latest reports to s3
    sync_reports(to_local=False)

    logger.info('Done!')


if __name__ == '__main__':
    main()
