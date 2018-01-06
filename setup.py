from setuptools import setup
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst')) as f:
    long_description = f.read()


setup(
    name="minimalcluster",
    version="0.1.0.dev13",
    description='A minimal cluster computing framework',
    long_description=long_description,
    url='https://github.com/XD-DENG/minimalcluster-py',
    author='Xiaodong DENG',
    author_email='xd.deng.r@gmail.com',
    license='MIT',
    keywords='parallel cluster multiprocessing',
    packages=["minimalcluster"]
    )
