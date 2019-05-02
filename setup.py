from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys, os

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
NEWS = open(os.path.join(here, 'NEWS.txt')).read()

class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = ['-v', '--tb=no', 'tests']
        self.test_suite = True
    def run_tests(self):
        import pytest
        errno = pytest.main(self.test_args)
        sys.exit(errno)

version = '0.0.1'

install_requires = [
    'netCDF4',
    'pupynere_pdp >=1.1.4',
    'pydap_pdp >=3.2.6'
]

setup(name='pydap.handlers.netcdf4',
    version=version,
    description="NetCDF4 handler for Pydap",
    long_description=README + '\n\n' + NEWS,
    classifiers=[
      # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    ],
    keywords='netcdf4 opendap dods dap science meteorology oceanography',
    author='James Hiebert',
    author_email='james@hiebert.name',
#    url='http://pydap.org/handlers.html#hdf5',
    license='MIT',
    packages=find_packages('src'),
    package_dir = {'': 'src'},
    namespace_packages = ['pydap', 'pydap.handlers'],
    package_data={'': ['pydap/handlers/netcdf4/data/*.nc']},
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    entry_points="""
        [pydap.handler]
        nc = pydap.handlers.netcdf4:NetCDF4Handler
    """,
    tests_require=['pytest', 'numpy'],
    cmdclass = {'test': PyTest},
)
