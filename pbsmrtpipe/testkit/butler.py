import ConfigParser
import itertools
import logging
import functools
import json
import abc
import os

from pbcommand.models import TaskOptionTypes
from pbcommand.utils import get_dataset_metadata
from pbcommand.services import ServiceEntryPoint

from pbsmrtpipe.pb_io import parse_pipeline_preset_json

log = logging.getLogger(__name__)

EXE = "pbsmrtpipe"

__all__ = ['ButlerTask',
           'ButlerWorkflow']

__author__ = "Michael Kocher"


class TestkitCfgParserError(ValueError):
    pass


class Constants(object):

    # this will be used in the Job tags
    TESTKIT_PREFIX = "TK"

    """Allowed values in cfg file."""
    CFG_JOB_ID = "id"

    CFG_ENTRY_POINTS = 'entry_points'

    CFG_PRESET_JSON = 'preset_json'
    CFG_TASK_ID = 'task_id'
    CFG_BASE_EXE = 'base_exe'
    CFG_REQUIREMENTS = 'requirements'
    CFG_XRAY_TESTS = "xray_tests"

    CFG_OUTPUT_DIR = 'output_dir'

    CFG_DEBUG = 'debug'
    CFG_MOCK = 'mock'


def _flatten_tags(requirements, xray_tests, tags, other):
    # always propagate the req and xray to the Job tags
    items = (requirements, xray_tests, tags, other)
    return {x for x in itertools.chain(*items)}


def _entrypoints_dicts(entry_points):
    """
    Extract dataset info from a list of entrypoints.
    """
    eps = []
    for entrypoint, dataset_xml in entry_points.iteritems():
        m = get_dataset_metadata(dataset_xml)
        entry = {"_comment": "pbservice auto-job",
                 "datasetId": "{u}".format(u=m.unique_id),
                 "entryId": "{k}".format(k=entrypoint),
                 "fileTypeId": "{t}".format(t=m.metatype)}
        eps.append(entry)
    return eps


def __get_option_type(val):
    option_type = TaskOptionTypes.STR

    if isinstance(val, bool):
        option_type = TaskOptionTypes.BOOL
    elif isinstance(val, int):
        option_type = TaskOptionTypes.INT
    elif isinstance(val, float):
        option_type = TaskOptionTypes.FLOAT
    elif val is None:
        val = ""
    return option_type, val


def __get_options_from_preset(attr_name, preset_json):
    opts = []
    if preset_json not in (None, ''):
        presets = parse_pipeline_preset_json(preset_json)

        for option_id, option_value in getattr(presets, attr_name):

            log.info("{x}: {i} = {v}".format(x=attr_name,
                                             i=option_id, v=option_value))

            option_type, option_value = __get_option_type(option_value)

            opts.append(dict(
                optionId=option_id,
                value=option_value,
                optionTypeId=option_type))

    return opts


_get_workflow_options_from_preset = functools.partial(__get_options_from_preset, "workflow_options")
_get_task_options_from_preset = functools.partial(__get_options_from_preset, "task_options")


class Butler(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self, job_id, output_dir, entry_points, preset_json, debug,
                 force_distribute=None, force_chunk=None, base_exe=EXE,
                 requirements=(), xray_tests=(), tags=()):
        """

        :param job_id: Test Id
        :param output_dir: Path to write the job output to
        :param entry_points: dict of Entry Id to Path
        :param preset_json: (optional) path to pbsmrtpipe Preset.JSON

        :param requirements: list of strings
        :param xray_tests: list of strings
        :param tags: list of strings. If the test id

        :type entry_points: dict[str, str]
        :type preset_json: None | string

        """
        self.output_dir = output_dir
        self.entry_points = entry_points
        self.preset_json = preset_json
        self.debug_mode = debug

        # None means no override, True|False means override
        self.force_distribute = force_distribute
        self.force_chunk = force_chunk

        # this needs to be set in the Butler.cfg file.
        self.job_id = job_id

        self.base_exe = base_exe
        self.requirements = requirements
        self.xray_tests = xray_tests

        # Always inject the TK job test id
        tag_test_id = "{}-{}".format(Constants.TESTKIT_PREFIX, job_id)

        self.tags = tuple(_flatten_tags(requirements, xray_tests, tags, (tag_test_id, )))

    def __repr__(self):
        _d = dict(k=self.__class__.__name__, p=self.prefix, r=self.requirements, x=self.xray_tests, t=self.tags)
        return "<{k} {p} req:{r} xray:{x} tags:{t} >".format(**_d)

    @abc.abstractproperty
    def prefix(self):
        # Used in the repr
        return ""

    def get_entry_point_dicts(self):
        return _entrypoints_dicts(self.entry_points)

    def get_service_entry_points(self):
        return [ServiceEntryPoint.from_d(x) for x in self.get_entry_point_dicts()]

    def get_workflow_options(self):
        return _get_workflow_options_from_preset(self.preset_json)

    def get_task_options(self):
        return _get_task_options_from_preset(self.preset_json)

    def to_cmd(self):
        return _to_pbsmrtpipe_cmd(self.prefix, self.output_dir,
                                  self.entry_points, self.preset_json,
                                  self.debug_mode, self.force_distribute,
                                  self.force_chunk, self.base_exe)


class ButlerWorkflow(Butler):

    def __init__(self, job_id, output_dir, pipeline_id, entry_points, preset_json_path, debug, force_distribute=None, force_chunk=None, base_exe=EXE, requirements=(), xray_tests=(), tags=()):
        super(ButlerWorkflow, self).__init__(job_id, output_dir, entry_points, preset_json_path, debug, force_distribute=force_distribute, force_chunk=force_chunk, base_exe=base_exe, requirements=requirements, xray_tests=xray_tests, tags=tags)
        self.pipeline_id = pipeline_id

    @property
    def prefix(self):
        return "pipeline-id {i}".format(i=self.pipeline_id)

    @staticmethod
    def from_json(file_name, force_distribute=None, force_chunk=None):

        # added for better error message that only JSON files not CFG.
        if not file_name.endswith(".json"):
            raise ValueError("Only testkit JSON files are supported. Unsupported file ({})".format(file_name))

        with open(file_name) as json_f:
            d = json.load(json_f)
            assert d.get('jobType', "pbsmrtpipe") == "pbsmrtpipe"
            return ButlerWorkflow(
                job_id=d['testId'],
                output_dir=d.get('outputDir', "job_output"),
                pipeline_id=d["pipelineId"],
                entry_points={e['entryId']:e['path'] for e in d['entryPoints']},
                preset_json_path=d.get("presetJson", None),
                debug=d.get("debug", False),
                force_distribute=force_distribute,
                force_chunk=force_chunk,
                requirements=tuple(d.get("requirements", [])),
                xray_tests=tuple(d.get("xrayTests", [])),
                tags=tuple(d.get("tags", []))
            )


class ButlerTask(Butler):

    def __init__(self, job_id, output_dir, task_id, entry_points, preset_json, debug, force_distribute=None, force_chunk=None):
        super(ButlerTask, self).__init__(job_id, output_dir, entry_points, preset_json, debug, force_distribute=force_distribute, force_chunk=force_chunk)
        self.task_id = task_id

    @property
    def prefix(self):
        return "task {i}".format(i=self.task_id)


def _to_pbsmrtpipe_cmd(prefix_mode, output_dir, entry_points_d, preset_json, debug, force_distribute, force_chunk, base_exe=EXE):
    ep_str = " ".join([" -e '" + ":".join([k, v]) + "'" for k, v in entry_points_d.iteritems()])
    d_str = '--debug' if debug else " "
    j_str = " " if preset_json is None else "--preset-json={j}".format(j=preset_json)
    m_str = ' '

    force_distribute_str = ''
    if isinstance(force_distribute, bool):
        m = {True: '--force-distributed', False: '--local-only'}
        force_distribute_str = m[force_distribute]

    force_chunk_str = ''
    if isinstance(force_chunk, bool):
        m = {True: '--force-chunk-mode', False: '--disable-chunk-mode'}
        force_chunk_str = m[force_chunk]

    _d = dict(x=base_exe, e=ep_str, d=d_str, j=j_str, m=prefix_mode, o=output_dir, k=m_str,
              f=force_distribute_str, c=force_chunk_str)
    cmd = "{x} {m} {c} {d} {e} {j} {k} {f} --output-dir={o}"
    return cmd.format(**_d)


to_task_cmd = functools.partial(_to_pbsmrtpipe_cmd, 'task')
to_workflow_cmd = functools.partial(_to_pbsmrtpipe_cmd, 'pipeline')
