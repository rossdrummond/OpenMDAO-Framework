import os
import sys
import numpy

# import ctypes
# import io

# libc = ctypes.CDLL(None)
# c_stdout = ctypes.c_void_p.in_dll(libc, 'stdout')
# c_stderr = ctypes.c_void_p.in_dll(libc, 'stderr')

def _redirect_streams(to_fd):
    """Redirect stdout/stderr to the given file descriptor.
    Based on: http://eli.thegreenplace.net/2015/redirecting-all-kinds-of-stdout-in-python/
    """

    original_stdout_fd = sys.stdout.fileno()
    original_stderr_fd = sys.stderr.fileno()

    # # Flush the C-level buffers
    # libc.fflush(c_stdout)
    # libc.fflush(c_stderr)

    # Flush and close sys.stdout/err - also closes the file descriptors (fd)
    sys.stdout.close()
    sys.stderr.close()

    # Make original_stdout_fd point to the same file as to_fd
    os.dup2(to_fd, original_stdout_fd)
    os.dup2(to_fd, original_stderr_fd)

    # Create a new sys.stdout that points to the redirected fd
    #sys.stdout = io.TextIOWrapper(os.fdopen(original_stdout_fd, 'wb')) # python 3
    sys.stdout = os.fdopen(original_stdout_fd, 'wb', 0) # 0 makes them unbuffered
    sys.stderr = os.fdopen(original_stderr_fd, 'wb', 0)

    # # Save a copy of the original stdout fd in saved_stdout_fd
    # saved_stdout_fd = os.dup(original_stdout_fd)

def use_proc_files():
    if MPI is not None:
        rank = MPI.COMM_WORLD.rank
        sname = "%s.out" % rank
        ofile = open(sname, 'wb')
        _redirect_streams(ofile.fileno())

def under_mpirun():
    """Return True if we're being executed under mpirun."""
    # TODO: this is a bit of a hack and there appears to be
    # no consistent set of environment vars between MPI
    # implementations.
    for name in os.environ.keys():
        if name.startswith('OMPI_COMM') or name.startswith('MPIR_'):
            return True
    return False

class PETSc(object):
    def __init__(self):
        self.needs_ksp = False # PETSc won't actually be imported unless this is True
        self._PETSc = None

    @property
    def installed(self):
        try:
            if self._PETSc is None:
                PETSc = _import_petsc()
                del sys.modules['petsc4py']
                self._PETSc = PETSc
            return True
        except ImportError:
            self._PETSc = None
            return False

    def __getattr__(self, name):
        if self.installed:
            return getattr(self._PETSc, name)
        raise AttributeError(name)

def create_petsc_vec(comm, arr):
    #print "create petsc: %s:  (%s)" % (arr, comm==MPI.COMM_NULL or comm==None);sys.stdout.flush()
    if under_mpirun() or PETSc.needs_ksp:
        if PETSc.installed and (MPI is None or comm != MPI.COMM_NULL):
            return PETSc.Vec().createWithArray(arr, comm=comm)

    return None

def _import_petsc():
    import petsc4py
    #petsc4py.init([]) #['-malloc_debug']) # add petsc init args here
    from petsc4py import PETSc
    return PETSc

if under_mpirun():
    from mpi4py import MPI
    PETSc = _import_petsc()
    PETSc.installed = True

    COMM_NULL = MPI.COMM_NULL

else:
    MPI = None
    COMM_NULL = None
    PETSc = PETSc()


class MPI_info(object):
    def __init__(self):
        self.requested_cpus = 1

        # the MPI communicator used by this comp and its children
        self.comm = COMM_NULL

    @property
    def size(self):
        if MPI:
            return self.comm.size
        return 1

    @property
    def rank(self):
        if MPI:
            if self.comm is not COMM_NULL:
                return self.comm.rank
            else:
                return -1
        return 0


def get_norm(vec, order=None):
    """Either do a distributed norm or a local numpy
    norm depending on whether we're running under MPI.

    vec: VecWrapper
        Returns the norm of this vector

    order: int, float, string (see numpy.linalg.norm)
        Order of the norm (ignored in MPI)
    """

    if MPI:
        vec.petsc_vec.assemble()
        return vec.petsc_vec.norm()
    else:
        return numpy.linalg.norm(vec.array, ord=order)

# npnorm = numpy.linalg.norm
# def norm(a, order=None):
#     '''This little funct for norm replaces a dependency on scipy
#     '''
#     return npnorm(numpy.asarray_chkfinite(a), ord=order)



if os.environ.get('USE_PROC_FILES'):
    use_proc_files()
