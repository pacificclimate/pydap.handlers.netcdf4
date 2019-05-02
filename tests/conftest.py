import os
from tempfile import NamedTemporaryFile
from pkg_resources import resource_filename

import pytest
import numpy.random
import netCDF4
from pydap.handlers.netcdf4 import NetCDF4Data

test_nc = resource_filename('pydap.handlers.netcdf4', 'data/test.nc')


@pytest.fixture(scope="function", params=['tasmax', 'tasmin', 'pr'])
def data_instance_3d(request):
    f = netCDF4.Dataset(test_nc, 'r')
    dst = f[request.param]
    return NetCDF4Data(dst)


@pytest.fixture(scope="module", params=['lat', 'lon', 'time'])
def data_instance_1d(request):
    f = netCDF4.Dataset(test_nc, 'r')
    dst = f[request.param]
    return NetCDF4Data(dst)


# _All_ the variables should be iterable
@pytest.fixture(scope="module",
                params=['tasmax', 'tasmin', 'pr', 'lat', 'lon', 'time'])
def data_iterable(request):
    f = netCDF4.Dataset(test_nc, 'r')
    dst = f[request.param]
    return NetCDF4Data(dst)


@pytest.fixture(scope="function")
def nc4_dst(request):
    f = NamedTemporaryFile()
    nc = netCDF4.Dataset(f.name, mode='w')
    group = hf.create_group('foo')
    dst = group.create_dataset(
        'bar', (10, 10, 10), '=f8', maxshape=(None, 10, 10))
    dst[:, :, :] = numpy.random.rand(10, 10, 10)

    def fin():
        nc.close()
        os.remove(f.name)
    request.addfinalizer(fin)

    return dst
