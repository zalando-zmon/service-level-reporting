"""Setup file for ZMON service level reports command line tool"""

import os

from setuptools import setup


def read_version(package):
    data = {}
    with open(os.path.join(package, '__init__.py'), 'r') as fd:
        exec(fd.read(), data)
    return data['__version__']


MAIN_PACKAGE = 'zmon_slr'
VERSION = read_version(MAIN_PACKAGE)
DESCRIPTION = 'ZMON SLO reports.'

CONSOLE_SCRIPTS = ['zmon-slr = zmon_slr.main:main']
PACKAGE_DATA = {MAIN_PACKAGE: ['templates/*.*']}

REQUIREMENTS = ['clickclick', 'stups-zign', 'zmon-cli']

setup(
    name='zmon-slr',
    version=VERSION,
    description=DESCRIPTION,
    long_description=open('README.rst').read(),
    license=open('LICENSE').read(),
    packages=[MAIN_PACKAGE],
    package_data=PACKAGE_DATA,
    install_requires=REQUIREMENTS,
    setup_requires=['pytest-runner'],
    test_suite='tests',
    tests_require=['pytest', 'pytest_cov', 'mock==2.0.0'],
    entry_points={'console_scripts': CONSOLE_SCRIPTS},
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Networking :: Monitoring',
    ]
)
