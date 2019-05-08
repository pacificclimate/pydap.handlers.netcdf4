pydap.handlers.netcdf4
======================

This is a *fork* of the PCIC's version of the `pydap.handlers.hdf5`_
package. This was essentially just a quick-and-dirty hack to get
things up and running.

Why? PCIC's performance testing has indicated that accessing netCDF
files with the `netCDF4`_ package is generally in the range of 10x
faster than the exact same access patterns using `h5py`_.

The code for this project isn't *great*, and it is not compatible with
the official `PyDAP`_ release. Please do not try to use them
together. By 2020 and the deprecation of Python 2, we intend to have
upstreamed (if necessary) any and all of the functionality contained
herein.

.. _`pydap.handler.hdf5`: https://github.com/pacificclimate/pydap.handlers.hdf5
.. _`h5py`: https://www.h5py.org/
.. _`netCDF4`: https://unidata.github.io/netcdf4-python/netCDF4/index.html
.. _`PyDAP`: https://github.com/pydap/pydap
