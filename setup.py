import subprocess
import sys
from setuptools import setup, Command

import restle


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = subprocess.call(['py.test', 'test_restle.py', '--cov=restle', '--cov-branch'])
        raise SystemExit(errno)

setup(
    name='restle',
    description='A REST client framework',
    keywords='rest,mapper,client',
    version=restle.__version__,
    packages=['restle'],
    requires=['six', 'requests'],
    url='https://github.com/consbio/restle',
    license='BSD',
    tests_require=['pytest', 'pytest-cov', 'httpretty==0.8.6', 'mock'],
    cmdclass={'test': PyTest}
)
