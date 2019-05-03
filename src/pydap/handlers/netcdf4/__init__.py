import os
import re
import time
from stat import ST_MTIME
from email.utils import formatdate
import logging

import netCDF4

from pydap.lib import quote
from pydap.model import DatasetType, StructureType, GridType, BaseType
from pydap.handlers.lib import BaseHandler
from pydap.exceptions import OpenFileError
from .stack_slice import StackableSlice

logger = logging.getLogger(__name__)


class NetCDF4Handler(BaseHandler):

    extensions = re.compile(r"^.*(\.nc4?|\.h(df)?[45]?)$", re.IGNORECASE)

    def __init__(self, filepath):
        BaseHandler.__init__(self)

        try:
            self.fp = netCDF4.Dataset(filepath, 'r')
        except Exception as exc:
            message = 'Unable to open file %s: %s' % (filepath, exc)
            raise OpenFileError(message)

        self.additional_headers.append(
            ('Last-modified',
             (formatdate(
                 time.mktime(
                     time.localtime(
                         os.stat(filepath)[ST_MTIME]))))))

        ncattrs = {attr: self.fp.__dict__[attr] for attr in self.fp.ncattrs()}
        attrs = {'NC_GLOBAL': ncattrs}

        unlim = find_unlimited(self.fp)
        if unlim:
            attrs.update({'DODS_EXTRA': {'Unlimited_Dimension': unlim}})

        # build dataset
        name = quote(os.path.split(filepath)[1])
        self.dataset = DatasetType(name, attributes=attrs)

        def is_gridded(dst):
            return sum([len(dim) for dim in dst.dims]) > 0

        def add_variables(dataset, var_):
            name = var_.name
            logger.debug("Adding variable %s", var_.name)
            varattrs = {}
            if hasattr(var_, 'ncattrs'):
                varattrs = {attr: var_.__dict__[attr] for attr in var_.ncattrs()}

            #attrs = process_attrs(varattrs)

            if hasattr(var_, 'shape'):
                rank = len(var_.shape)
            else:
                rank = 1

            if rank == 0:
                logger.debug("rank 0 variable: %s", name)
                dataset[name] = BaseType(name, data=NetCDF4Data(
                    var_), dimensions=(), attributes=varattrs)
            # sequence?
            # elif rank == 1:
            #    dataset[name] = SequenceType(name, data=h5,
            #                                 attributes=h5.attrs)
            # grid
            elif rank > 1:
                logger.debug("rank %d variable: %s", rank, name)
                parent = dataset[name] = GridType(name, attributes=varattrs)
                dims = var_.dimensions
                logger.debug("DIMENSIONS: {}".format(dims))
                parent[name] = BaseType(
                    name,
                    data=NetCDF4Data(var_),
                    dimensions=dims,
                    attributes=varattrs)  # Add the main variable
                for dimname in dims:
                    # Add all of the dimensions if they exist as a variable
                    dim = self.fp.dimensions[dimname]
                    if dim in self.fp.variables.keys():
                        add_variables(parent, dim)
                    # Otherwise add it as a variable with no data
                    dataset[dimname] = BaseType(dimname)

            # BaseType
            else:
                logger.debug("rank 1 variable: %s", name)
                dataset[name] = BaseType(
                    name, data=NetCDF4Data(var_), attributes=varattrs)

        for variable in self.fp.variables.values():
            add_variables(self.dataset, variable)

    def close(self):
        self.fp.close()


def find_unlimited(nc):
    '''Find and return the name of the unlimited dimension of the NetCDF Dataset
       Return None if one does not exist.
    '''
    for dim_name, dim in nc.dimensions.items():
        if dim.isunlimited():
            return dim_name


def has_unlimited(var):
    '''Returns True if a NetCDF variable has an unlimited dimension'''
    if hasattr(var, '_nunlimdim') and var._nunlimdim > 0:
        return True
    if hasattr(var, 'isunlimited'):
        return var.isunlimited()
    return False


class NetCDF4Data(object):
    """
    A wrapper for NetCDF4 variables, ensuring support for iteration and the dtype
    property
    """

    def __init__(self, var, slices=None):
        assert type(var) == netCDF4.Variable
        self.var = var
        logger.debug('NetCDf4Data.__init__({}, {})'.format(var, slices))

        if hasattr(var, 'shape'):
            rank = len(var.shape)
        else:
            rank = 1

        assert rank > 0

        if not slices:
            self._slices = [StackableSlice(None, None, None)
                            for i in range(rank)]
        else:
            assert len(slices) == rank
            self._slices = [StackableSlice(
                s.start, s.stop, s.step) for s in slices]

        self._major_slice = self._slices[0]
        if rank > 1:
            self._minor_slices = self._slices[1:]
        else:
            self._minor_slices = None

        self._init_iter()

        logger.debug('end NetCDF4Data.__init__()')

    def _init_iter(self):
        '''Initialize the iterator'''
        if self._major_slice.start:
            self.pos = self._major_slice.start
        else:
            self.pos = 0

    def __getitem__(self, slices):
        logger.debug('HDF5Data({}.__getitem({})'.format(self.var, slices))
        # There are three types of acceptable keys...
        # A single integer
        if isinstance(slices, int):
            slices = (StackableSlice(slices, slices + 1, 1),)
        # A single slice for a 1d dataset
        elif type(slices) in (slice, StackableSlice):
            assert self.rank == 1
            slices = (slices,)
        # A tuple of slices where the number of elements in the tuple equals
        # the number of dimensions in the dataset
        elif type(slices) in (tuple, list):
            if len(slices) != self.rank:
                raise ValueError("dataset has {0} dimensions, but the slice "
                                 "has {1} dimensions".format(len(slices),
                                                             self.rank))
        else:
            raise TypeError()

        # convert all regular slices into stackable slices for the addition
        converted_slices = []
        for s in slices:
            if isinstance(s, StackableSlice):
                converted_slices.append(s)
            elif isinstance(s, int):
                converted_slices.append(StackableSlice(s, s + 1, 1))
            elif isinstance(s, slice):
                converted_slices.append(
                    StackableSlice(s.start, s.stop, s.step))
            else:
                raise TypeError("__getitem__ should be called with a list of "
                                "slices (or StackableSlices), not {}"
                                .format([type(s) for s in slices]))
        slices = converted_slices

        subset_slices = [orig_slice + subset_slice for orig_slice,
                         subset_slice in zip(self._slices, slices)]

        return NetCDF4Data(self.var, subset_slices)

    def __iter__(self):
        logger.debug('returning from __iter__')
        return NetCDF4Data(self.var, self._slices)

    def next(self):
        if hasattr(self.var, 'shape'):
            end = self.var.shape[0]
        else:
            end = self.var.size

        stop = self._major_slice.stop if self._major_slice.stop \
               else end
        step = self._major_slice.step if self._major_slice.step else 1
        if self.pos < stop:

            # Special case: for 1d variables, non-record variables return
            # output on the first iteration in a single numpy array
            if self.rank == 1 and has_unlimited(self.var):
                self.pos = float('inf')
                return self.var[self._major_slice.slice]

            x = self.var[self.pos]
            self.pos += step
            if self._minor_slices:
                # Can't actually index with sequence of stackable slices...
                # convert to slices
                minor_slices = [s.slice for s in self._minor_slices]
                return x[minor_slices]
            else:
                return x
        else:
            self._init_iter()
            raise StopIteration

    def __len__(self): return self.var.shape[0]

    @property
    def dtype(self):
        return self.var.dtype

    @property
    def shape(self):
        logger.debug(
            "HDF5Data({}).shape : major_slice={} and slices={}".format(
                self.var,
                self._major_slice,
                self._slices))
        if hasattr(self.var, 'shape'):
            myshape = self.var.shape
        else:
            myshape = (self.var.size,)
        true_slices = [s.slice for s in self._slices]
        myshape = sliced_shape(true_slices, myshape)
        logger.debug("leaving shape with result %s", myshape)
        return myshape

    @property
    def rank(self):
        return len(self.shape)

    def byteswap(self):
        x = self.var.__getitem__(self._slices)
        return x.byteswap()

    def astype(self, type_):
        slices = tuple([ss.slice for ss in self._slices])
        x = self.var.__getitem__(slices)
        return x.astype(type_)


def sliced_shape(slice_, shape_):
    assert len(slice_) == len(shape_)
    rv = [sh if sl == slice(None) else len(range(sh)[sl])
          for sl, sh in zip(slice_, shape_)]
    return tuple(rv)


if __name__ == "__main__":
    import sys
    from werkzeug.serving import run_simple

    application = HDF5Handler(sys.argv[1])
    run_simple('localhost', 8002, application, use_reloader=True)
