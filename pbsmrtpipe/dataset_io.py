"""Note, this is from an vestige from an earlier design of pbsmrtpipe.

The Dependency Injection model has largely been removed, but there's still a few places where it needs to deleted.s
"""
import logging

from pbcommand.validators import validate_file
from pbcommand.models import FileTypes


log = logging.getLogger(__name__)

__all__ = ['UnresolvableDatasetMetadataError',
           'dispatch_metadata_resolver',
           'has_metadata_resolver']


class UnresolvableDatasetMetadataError(ValueError):
    pass


class DatasetMetadata(object):

    SUPPORTED_ATTRS = ('nrecords', 'total_length')

    def __init__(self, nrecords, total_length):
        self.nrecords = nrecords
        self.total_length = total_length

    def __repr__(self):
        _d = dict(k=self.__class__.__name__, n=self.nrecords, t=self.total_length)
        return "<{k} nrecords:{n} total:{t} >".format(**_d)


REGISTERED_METADATA_RESOLVER = {}


def register_metadata_resolver(*file_type_or_types):

    if not isinstance(file_type_or_types, (list, tuple)):
        file_type_or_types = [file_type_or_types]

    def _wrapper(func):

        for file_type in file_type_or_types:
            REGISTERED_METADATA_RESOLVER[file_type] = func

        def _f(path):
            path = validate_file(path)
            return _f(path)
        return _f

    return _wrapper


def dispatch_metadata_resolver(file_type, path):
    """Simple multiple dispatch mechanism"""
    to_ds_metadata_func = REGISTERED_METADATA_RESOLVER.get(file_type, None)
    if to_ds_metadata_func is None:
        raise UnresolvableDatasetMetadataError("Unable to resolve file type {t}".format(t=file_type))
    return to_ds_metadata_func(path)


def has_metadata_resolver(file_type):
    return file_type in REGISTERED_METADATA_RESOLVER
