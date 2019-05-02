from pkg_resources import resource_filename

import numpy
import numpy.ma.core
from webob.request import Request

from pydap.handlers.netcdf4 import NetCDF4Data


def test_can_instantiate(nc4_dst):
    var = NetCDF4Data(nc4_dst)
    assert var.shape == (10, 10, 10)


def test_can_iterate_on_unsliced(data_iterable):
    for data in data_iterable:
        pass
    assert True


def test_can_iterate_on_sliced_major(data_instance_3d):
    i = 0
    for data in data_instance_3d[5:10, :, :]:
        i += 1
    assert i == 5


def test_can_iterate_on_sliced_minor(data_instance_3d):
    i = 0
    for data in data_instance_3d[:, 1:2, 3:4]:
        i += 1
    assert i == 10


def test_can_iterate_on_sliced_major_minor(data_instance_3d):
    i = 0
    for data in data_instance_3d[0:2, 3:4, 5:6]:
        i += 1
    assert i == 2


def test_shape_of_unsliced_3d(data_instance_3d):
    x = data_instance_3d
    assert x.shape == (10, 10, 10)


def test_shape_of_sliced_3d(data_instance_3d):
    x = data_instance_3d
    assert x[5:10, :, :].shape == (5, 10, 10)


def test_shape_of_unsliced_1d(data_instance_1d):
    x = data_instance_1d
    assert x.shape == (10,)


def test_shape_of_sliced_1d(data_instance_1d):
    x = data_instance_1d
    assert x[5:10].shape == (5,)

# Unless 1d variables are of unlimited dimensions, you should get all of their
# output on the first iteration in a numpy array


def test_1d_iteration(data_instance_1d):
    x = data_instance_1d
    for i in iter(x):
        if data_instance_1d.var._nunlimdim > 0:
            assert type(i) in (numpy.float64, numpy.ma.core.MaskedArray)
        else:
            assert type(i) in (numpy.ndarray, numpy.ma.core.MaskedArray)
            assert len(i) == len(data_instance_1d.var)


def test_can_slice_a_sliced_dataset(data_instance_3d):
    x = data_instance_3d
    subset = x[5:10, :, :][1:2, :, :]
    assert subset.shape == (1, 10, 10)


def test_the_bounds():
    test_bounds = resource_filename('pydap.handlers.netcdf4', 'data/bounds.nc')
    from pydap.handlers.netcdf4 import NetCDF4Handler
    app = NetCDF4Handler(test_bounds)
    req = Request.blank('/bounds.nc.ascii?climatology_bounds')
    resp = req.get_response(app)
    assert resp.status == '200 OK'
    assert resp.body == '''climatology_bounds.climatology_bounds
[0.0, 10988.0]
[31.0, 11017.0]
[59.0, 11048.0]
[90.0, 11078.0]
[120.0, 11109.0]
[151.0, 11139.0]
[181.0, 11170.0]
[212.0, 11201.0]
[243.0, 11231.0]
[273.0, 11262.0]
[304.0, 11292.0]
[334.0, 11323.0]
[0.0, 11323.0]
climatology_bounds.time
climatology_bounds.bnds
[0.0, 0.0]
'''
