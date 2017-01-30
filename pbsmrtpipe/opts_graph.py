"""Utils for Creating and Resolving the DI options graph"""
import sys
import inspect
import json
import logging
import functools
import re
import types
import pprint
import uuid
import jsonschema

from pbcommand.models import FileTypes, TaskTypes, SymbolTypes
from pbsmrtpipe.exceptions import (InvalidDependencyInjectError,
                                   MalformedDependencyInjectionFileMetadataError)

from pbsmrtpipe.models import (MetaScatterTask,
                               MetaTask, ScatterTask, Task, MetaGatherTask,
                               GatherTask, ScatterToolContractMetaTask,
                               GatherToolContractMetaTask,
                               ToolContractMetaTask)

from pbsmrtpipe.dataset_io import (dispatch_metadata_resolver,
                                   has_metadata_resolver,
                                   DatasetMetadata)


import networkx as nx

log = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)


def get_report_json_attribute(report_file, attribute_id):

    try:
        with open(report_file, 'r') as f:
            s = f.read()

        d = json.loads(s)
        for attr in d['attributes']:
            if attr['id'] == attribute_id:
                value = attr['value']
                log.debug("Extracted report attribute {a} from {r}".format(a=attribute_id, r=report_file))
                return value
    except (ValueError, IOError, KeyError) as e:
        msg = "Unable to load report attribute '{a}' from {p}".format(a=attribute_id, p=report_file)
        log.error(msg)
        raise

    raise InvalidDependencyInjectError("Unable to find attribute '{a}' in report {r}".format(a=attribute_id, r=report_file))


def get_dataset_metadata_from_file(file_type, path, attribute_name):

    if attribute_name not in DatasetMetadata.SUPPORTED_ATTRS:
        raise InvalidDependencyInjectError("File metadata Attribute '{a}' is not support in {p}".format(a=attribute_name, p=path))

    dataset_metadata = dispatch_metadata_resolver(file_type, path)

    return getattr(dataset_metadata, attribute_name)


def get_metadata_from_file(file_type, path, attribute_name):

    if file_type == FileTypes.REPORT:
        return get_report_json_attribute(path, attribute_name)
    else:
        return get_dataset_metadata_from_file(file_type, path, attribute_name)


def resolve_di(resolved_keys_d, di_list_model):
    """
    Resolve DI values in a list

    :param resolved_keys_d: {di key : func} The Func has empty signature
    :param di_list_model: DI list model (e.g., ['$tmpfile', '$tmpdir','$nproc'])
    :return: a list of resolved DI values
    """

    resolved_specials = []
    for s in di_list_model:
        if s in resolved_keys_d:
            func = resolved_keys_d[s]
            v = func()
            resolved_specials.append(v)
        else:
            _d = dict(s=s, t=resolved_keys_d.keys())
            raise ValueError("Unable to resolve special '{s}'. Valid specials are '{t}'".format(**_d))

    return resolved_specials


def is_di_list(alist_or_item):
    """
    Validate a list or item is a properly constructed DI list

    A valid DI is

    1. Last item is a function
    2. the function has the same signature as len(di_list) - 1
    3. All DI items are Symbol types, ints, strings
    """
    if isinstance(alist_or_item, (list, tuple)):
        if isinstance(list(alist_or_item)[-1], types.FunctionType):
            return True
    return False


def default_to_ropts(user_opts, pacbio_options_list):
    """
    'Resolves' the options and returns a {id:value}

    or raises jsonschema.ValidationError
    """
    pb_opts_d = {opt.option_id: opt for opt in pacbio_options_list}

    ropts = {}
    for opt_id, pb_option in pb_opts_d.iteritems():
        if opt_id in user_opts:
            # use user defined value
            v = user_opts[opt_id]
            # jsonschema.validate({opt_id: v}, schema)
            ropts[opt_id] = v
        else:
            # must have a default value or null?
            #v = schema['pb_option']['default']
            ropts[opt_id] = pb_option.default

    return ropts


def meta_task_to_task(meta_task,
                      input_files,
                      all_task_options,
                      output_dir,
                      max_nproc, max_nchunks,
                      to_resources_func,
                      to_resolve_files_func):
    """
    Converts a MetaTask to a Task instance

    :param input_files: List of resolved input files
    :param all_task_options: Raw Unresolved task options provided by the user {id:value}
    :param output_dir: Root path to write output to (or Task-id dir?)
    :param to_resources_func: Function that has signature (resources_di) -> resources
    :param to_resolve_files_func: Function (output_types, override_file_names, mutable_files=None) -> output file paths

    :type max_nchunks: int
    :type max_nproc: int
    :type output_dir: str
    :type to_resources_func: types.FunctionType

    :rtype: Task | ScatterTask | GatherTask
    """
    # Type checking

    # Make sure the resolving func is well-defined
    if isinstance(to_resolve_files_func, functools.partial):
        f1 = to_resolve_files_func.func
        args_obj = inspect.getargspec(f1)
        if (len(args_obj.args) - len(to_resolve_files_func.args)) != 5:
            TypeError("Incorrect Function {f} args {a}".format(f=str(to_resolve_files_func), a=args_obj.args))
    elif isinstance(to_resolve_files_func, types.FunctionType):
        args_obj = inspect.getargspec(to_resolve_files_func)
        if len(args_obj.args) != 5:
            raise TypeError("Incorrect Function {f} args {a}".format(f=str(to_resolve_files_func), a=args_obj.args))
    else:
        raise TypeError("Expected function type. Got {f}".format(f=type(to_resolve_files_func)))

    # filter the opts with only the options that in the opts schema
    user_opts = {k: v for k, v in all_task_options.iteritems() if k in meta_task.option_schemas}

    def _default_resolve_nproc():
        if meta_task.nproc == SymbolTypes.MAX_NPROC:
            return max_nproc
        elif isinstance(meta_task.nproc, int):
            return min(meta_task.nproc, max_nproc)
        else:
            return 1

    def _default_task_type():
        return meta_task.is_distributed

    def _default_nchunks():
        # the old model should be removed.
        if isinstance(meta_task, (MetaScatterTask, )):
            if meta_task.chunk_di == SymbolTypes.MAX_NCHUNKS:
                return max_nchunks
            elif isinstance(meta_task.chunk_di, int):
                return min(meta_task.chunk_di, SymbolTypes.MAX_NCHUNKS)

        # default to the max number of chunks. At the tool level, it
        # should sort out how to the max number of chunks.
        log.info("Default nchunks {x}".format(x=max_nchunks))
        return max_nchunks

    r_nchunks = _default_nchunks()
    r_task_options = default_to_ropts(user_opts, meta_task.option_schemas)
    r_nproc = _default_resolve_nproc()

    # Resolve Resources
    rfiles = to_resources_func(meta_task.resource_types)

    # override output file names (if necessary)
    ofiles = to_resolve_files_func(output_dir, input_files, meta_task.output_types, meta_task.output_file_names, meta_task.mutable_files)
    log.debug(("Resolved output files", ofiles))

    task_uuid = str(uuid.uuid4())

    if isinstance(meta_task, (MetaScatterTask, ScatterToolContractMetaTask)):
        cmd_str = meta_task.to_cmd(input_files, ofiles, r_task_options, r_nproc, rfiles, r_nchunks)
        t = ScatterTask(task_uuid, meta_task.task_id, meta_task.is_distributed, input_files, ofiles,
                        r_task_options, r_nproc, rfiles, cmd_str, r_nproc, output_dir, meta_task.chunk_keys)
    elif isinstance(meta_task, (MetaGatherTask, GatherToolContractMetaTask)):
        cmd_str = meta_task.to_cmd(input_files, ofiles, r_task_options, r_nproc, rfiles)
        t = GatherTask(task_uuid, meta_task.task_id, meta_task.is_distributed, input_files, ofiles, r_task_options, r_nproc, rfiles, cmd_str, output_dir)
    elif isinstance(meta_task, (MetaTask, ToolContractMetaTask)):
        cmd_str = meta_task.to_cmd(input_files, ofiles, r_task_options, r_nproc, rfiles)
        t = Task(task_uuid, meta_task.task_id, meta_task.is_distributed, input_files, ofiles, r_task_options, r_nproc, rfiles, cmd_str, output_dir)
    else:
        raise TypeError("Unsupported meta task type {m}".format(m=meta_task))

    # log.debug(t.__dict__)

    return t
