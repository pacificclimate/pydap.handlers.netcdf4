import os
import re
import time
from stat import ST_MTIME
from email.utils import formatdate
from itertools import islice
from warnings import warn
from logging import info, debug, warning

import h5py
from pupynere import REVERSE

from pydap.model import DatasetType, StructureType, SequenceType, GridType, BaseType
from pydap.handlers.lib import BaseHandler
from pydap.exceptions import OpenFileError

from pdb import set_trace

class HDF5Handler(BaseHandler):

    extensions = re.compile(r"^.*(\.nc4?|\.h(df)?[45]?)$", re.IGNORECASE)

    def __init__(self, filepath):
        BaseHandler.__init__(self)

        try:
            self.fp = h5py.File(filepath, 'r')
        except Exception, exc:
            message = 'Unable to open file %s: %s' % (filepath, exc)
            raise OpenFileError(message)

        self.additional_headers.append(
                ('Last-modified', (formatdate(time.mktime(time.localtime(os.stat(filepath)[ST_MTIME]))))))

        attrs = {'NC_GLOBAL': process_attrs(self.fp.attrs)}

        unlim = find_unlimited(self.fp)
        if len(unlim) > 1:
            raise Exception("Found %d unlimited dimensions %s, but DAP supports no more than one.")
        elif len(unlim) == 1:
            attrs.update({'DODS_EXTRA': {'Unlimited_Dimension': unlim.pop()}})

        # build dataset
        name = os.path.split(filepath)[1]
        self.dataset = DatasetType(name, attributes=attrs)

        def is_gridded(dst):
            return sum([len(dim) for dim in dst.dims]) > 0

        def add_variables(dataset, h5, level=0):
            assert type(h5) in (h5py.File, h5py.Group, h5py.Dataset)
            name = h5.name.lstrip('/')
            attrs = process_attrs(h5.attrs)
    
            # struct
            if type(h5) in (h5py.File, h5py.Group):
                foo = StructureType(name, attributes=attrs)
                name = foo.name
                dataset[name] = foo
                for bar in h5.values():
                    add_variables(dataset[name], bar, level+1)
                return

            # Recursion base cases
            rank = len(h5.shape)
            # basetype
            if rank == 0:
                dataset[name] = BaseType(name, data=Hdf5Data(h5), dimensions=(), attributes=attrs)
            # sequence?
            #elif rank == 1:
            #    dataset[name] = SequenceType(name, data=h5, attributes=h5.attrs)
            # grid
            elif is_gridded(h5):
                parent = dataset[name] = GridType(name, attributes=attrs)
                dims = tuple([ d.keys()[0] for d in h5.dims ])
                parent[name] = BaseType(name, data=Hdf5Data(h5), dimensions=dims, attributes=attrs) # Add the main variable
                for dim in h5.dims: # and all of the dimensions
                    add_variables(parent, dim[0], level+1) # Why would dims have more than one h5py.Dataset?
            # BaseType
            else:
                dataset[name] = BaseType(name, data=Hdf5Data(h5), attributes=attrs)

        for varname in self.fp:
            add_variables(self.dataset, self.fp[varname])

    def close(self):
        self.fp.close()
        
def find_unlimited(h5):
    'Recursively construct a set of names for unlimited dimensions in an hdf dataset'
    rv = set()
    if type(h5) == h5py.Dataset:
        try:
            dims = tuple([ d.keys()[0] for d in h5.dims ])
        except:
            return set()
        maxshape = h5.maxshape
        rv = [ dimname for dimname, length in zip(dims, maxshape) if not length ] # length is None for unlimited dimensions
        return set(rv)
    for child in h5.values():
        rv.update(find_unlimited(child))
    return rv

def process_attrs(attrs):
    rv = {}
    for key in attrs.keys():
        try:
            val = attrs.get(key) # Potentially raises TypeError: No NumPy equivalent for TypeVlenID exists
            REVERSE(val.dtype) # This will raise Exception of the type is not convertable
            rv[key] = val
        except:
            warn("Failed to convert attribute " + key)
    return rv

class Hdf5Data(object):
    """
    A wrapper for Hdf5 variables, ensuring support for iteration and the dtype
    property
    """
    def __init__(self, var, slices=None):
        self.var = var
        debug('%s', slices)

        rank = len(var.shape)
        assert rank > 0

        if not slices:
            self._slices = [ slice(None) for i in range(rank) ]
        else:
            assert len(slices) == rank
            self._slices = slices

        self._major_slice = self._slices[0]
        if rank > 1:
            self._minor_slices = self._slices[1:]
        else:
            self._minor_slices = None
            
        # Set up the iterator
        if rank > 1 or None in self.var.maxshape:
            self.iter = islice(iter(self.var), self._major_slice.start, self._major_slice.stop, self._major_slice.step)
        else:
            self.iter = iter([self.var])

        debug('end Hdf5Data.__init__()')

    def __getitem__(self, slices):
        # for a 1d slice, there will (should) only be one slice
        if type(slices) == slice:
            slices = (slices,)
        for slice_ in self._slices:
            if slice_ != slice(None):
                raise NotImplementedError("Haven't yet implemented a subset of a subset")
        if len(slices) != len(self.shape):
            raise ValueError("dataset has {0} dimensions, but the slice has {1} dimensions".format(len(slices), len(self.shape)))
        return Hdf5Data(self.var, slices)

    def __iter__(self):
        debug('returning from __iter__')
        return self

    def next(self):
        try:
            x = self.iter.next()
            if self._minor_slices:
                return x[self._minor_slices]
            else:
                return x
        except StopIteration:
            self.iter = islice(iter(self.var), self._major_slice.start, self._major_slice.stop, self._major_slice.step)
            raise

    def __len__(self): return self.var.shape[0]

    @property
    def dtype(self):
        return self.var.dtype

    @property
    def shape(self):
        debug("in shape with major_slice=%s and slices=%s", self._major_slice, self._slices)
        myshape = self.var.shape
        myshape = sliced_shape(self._slices, myshape)
        debug("leaving shape with result %s", myshape)
        return myshape

    def byteswap(self):
        x = self.var.__getitem__(self._slices)
        return x.byteswap()

def sliced_shape(slice_, shape_):
    assert len(slice_) == len(shape_)
    rv = [ sh if sl == slice(None) else len(range(sh)[sl]) for sl, sh in zip(slice_, shape_) ]
    return tuple(rv)

if __name__ == "__main__":
    import sys
    from werkzeug.serving import run_simple

    application = HDF5Handler(sys.argv[1])
    run_simple('localhost', 8002, application, use_reloader=True)
