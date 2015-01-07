from distutils.cmd import Command
from distutils.core import setup
import subprocess
import sys


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = subprocess.call([sys.executable, 'runtests.py'])
        raise SystemExit(errno)

setup(
    name='restle',
    description='A REST client framework',
    keywords='rest,mapper,client',
    version='0.0.1',
    packages=['restle'],
    requires=['six', 'requests'],
    url='https://github.com/consbio/restle',
    license='BSD',
    tests_require=['pytest', 'httpretty', 'mock'],
    cmdclass={'test': PyTest}
)