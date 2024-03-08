from .metric import RiemannianMetric
from .utility import get_checkpoint_dir
from firedrake import COMM_WORLD
import firedrake.checkpointing as fchk
import firedrake.function as ffunc
import os

__all__ = ["load_checkpoint", "save_checkpoint"]


def _fix_checkpoint_filename(filename):
    """
    Convert a checkpoint filename to absolute form.

    :arg filename: the filename without its path
    :type filename: :class:`str`
    :returns: the absolute filename
    :rtype: :class:`str`
    """
    if "/" in filename:
        raise ValueError(
            "Provide a filename, not a filepath. Checkpoints will be stored in"
            f" '{get_checkpoint_dir()}'."
        )
    name, ext = os.path.splitext(filename)
    ext = ext or ".h5"
    if ext != ".h5":
        raise ValueError(f"File extension '{ext}' not recognised. Use '.h5'.")
    return os.path.join(get_checkpoint_dir(), name + ext)


def load_checkpoint(filename, metric_name, comm=COMM_WORLD):
    """
    Load a metric from a :class:`~.CheckpointFile`.

    Note that the checkpoint will have to be stored within Animate's ``.checkpoints``
    subdirectory.

    :arg filename: the filename of the checkpoint
    :type filename: :class:`str`
    :arg metric_name: the name used to store the metric
    :type metric_name: :class:`str`
    :kwarg comm: MPI communicator for handling the checkpoint file
    :type comm: :class:`mpi4py.MPI.Intracom`
    :returns: the mesh loaded from the checkpoint
    :rtype: :class:`firedrake.mesh.MeshGeometry`
    """
    fname = _fix_checkpoint_filename(filename)
    if not os.path.exists(fname):
        raise Exception(f"Metric file does not exist! Path: {fname}.")
    with fchk.CheckpointFile(fname, "r", comm=comm) as chk:
        mesh = chk.load_mesh()
        metric = chk.load_function(mesh, metric_name)

        # Load stashed metric parameters
        mp = chk._read_pickled_dict("metric_parameters", "mp_dict")
        for key, value in mp.items():
            if value == "Function":
                mp[key] = chk.load_function(mesh, key)

    metric = RiemannianMetric(metric.function_space()).assign(metric)
    metric.set_parameters(mp)
    return metric


def save_checkpoint(adaptor, filename, metric_name=None, comm=COMM_WORLD):
    """
    Write the metric and underlying mesh to a :class:`~.CheckpointFile`.

    Note that the checkpoint will be stored within Animate's ``.checkpoints``
    subdirectory.

    :arg filename: the filename to use for the checkpoint
    :type filename: :class:`str`
    :kwarg metric_name: the name to save the metric under
    :type metric_name: :class:`str`
    :kwarg comm: MPI communicator for handling the checkpoint file
    :type comm: :class:`mpi4py.MPI.Intracom`
    """
    fname = _fix_checkpoint_filename(filename)
    mp = adaptor.metric.metric_parameters.copy()
    with fchk.CheckpointFile(fname, "w", comm=comm) as chk:
        chk.save_mesh(adaptor.mesh)
        chk.save_function(adaptor.metric, name=metric_name or adaptor.name)

        # Stash metric parameters
        for key, value in mp.items():
            if isinstance(value, ffunc.Function):
                chk.save_function(value, name=key)
                mp[key] = "Function"
        chk._write_pickled_dict("metric_parameters", "mp_dict", mp)
