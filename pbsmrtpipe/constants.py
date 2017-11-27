import functools
# This is where all the rdf imports should be. Other modules should import them
# from here because of the plugin registry.
import os
import re
import socket


ENV_PRESET = 'PB_SMRTPIPE_XML_PRESET'
# Extra Directory for JSON Tool Contracts
ENV_TC_DIR = "PB_TOOL_CONTRACT_DIR"

# Extra Directory for JSON/Avro Pipeline Templates
ENV_PT_DIR = "PB_PIPELINE_TEMPLATE_DIR"

# Chunk Operators
ENV_CHK_OPT_DIR = "PB_CHUNK_OPERATOR_DIR"

# External resources bundle
ENV_BUNDLE_DIR = "SMRT_PIPELINE_BUNDLE_DIR"
ENV_IGNORE_BUNDLE = "SMRT_IGNORE_PIPELINE_BUNDLE" # for testing


PBSMRTPIPE_PID_KILL_FILE_SCRIPT = ".pbsmrtpipe-terminate.sh"

# Map of exception types to exit codes.
EXCEPTION_TO_EXIT_CODE = {KeyboardInterrupt: 7, IOError: 2, socket.error: 7}
TERM_FILE = ".TERMINATED"
EXIT_SUCCESS = 0
EXIT_FAILURE = 1
EXIT_TERMINATED = 7
# For Unknown error
DEFAULT_EXIT_CODE = EXIT_FAILURE

DEEP_DEBUG = False

# Global Env vars that are necessary to do *anything*. This is stupid.
SEYMOUR_HOME = 'SEYMOUR_HOME'

SLOG_PREFIX = 'status.'

DATASTORE_VERSION = "0.2.1"
CHUNK_API_VERSION = "0.1.0"

ENTRY_PREFIX = "$entry:"

# Generic Id
RX_TASK_ID = re.compile(r'^([A-z0-9_]*)\.tasks\.([A-z0-9_]*)$')
RX_PIPELINE_ID = re.compile(r'^([A-z0-9_]*)\.pipelines\.([A-z0-9_\.]*)$')
RX_FILE_TYPES_ID = re.compile(r'^([A-z0-9_]*)\.files\.([A-z0-9_\.]*)$')
RX_TASK_OPTION_ID = re.compile(r'^([A-z0-9_]*)\.task_options\.([A-z0-9_\.]*)')

# Bindings format
# Only Task includes the :0
RX_BINDING_TASK = re.compile(r'^([A-z0-9_]*)\.tasks\.([A-z0-9_]*):(\d*)$')
# Advanced bindings referencing an instance of a task
# {namespace}:tasks:{instance-id}:{in_out_index}
RX_BINDING_TASK_ADVANCED = re.compile(r'^([A-z0-9_]*)\.tasks\.([A-z0-9_]*):(\d*):(\d*)$')

# {pipeline_id}:{task_id}:{instance_id}
RX_BINDING_PIPELINE_TASK = re.compile(r'^([A-z0-9_]*).pipelines.([A-z0-9_]*):([A-z0-9_]*).tasks.(\w*):([0-9]*)$')
# {pipeline_id}:$entry:{entry_label}
RX_BINDING_PIPELINE_ENTRY = re.compile(r'^([A-z0-9_]*).pipelines.([A-z0-9_]*):\$entry:([A-z0-9_]*)$')
# Only Entry points
RX_ENTRY = re.compile(r'^\$entry:([A-z0-9_]*)$')
# to be consistent with the new naming scheme
RX_BINDING_ENTRY = re.compile(r'^\$entry:([A-z0-9_]*)$')

RX_VALID_BINDINGS = (RX_BINDING_PIPELINE_TASK,
                     RX_BINDING_PIPELINE_ENTRY,
                     RX_BINDING_TASK,
                     RX_BINDING_TASK_ADVANCED,
                     RX_BINDING_ENTRY)

# This should really use a semantic version lib
RX_VERSION = re.compile(r'(\d*).(\d*).(\d*)')

# Chunk Key $chunk.my_label_id
RX_CHUNK_KEY = re.compile(r'^\$chunk\.([A-z0-9_]*)')
RX_CHUNK_ID = re.compile(r'(^[A-z0-9_]*)')


TASK_MANIFEST_JSON = 'task-manifest.json'
RUNNABLE_TASK_JSON = "runnable-task.json"
TASK_MANIFEST_VERSION = '0.3.0'

RESOLVED_TOOL_CONTRACT_JSON = "resolved-tool-contract.json"
RESOLVED_TOOL_CONTRACT_AVRO = 'resolved-tool-contract.avro'
TOOL_CONTRACT_JSON = "tool-contract.json"

SOURCE_ID_MASTER_LOG = "pbsmrtpipe::pbsmrtpipe.log"
SOURCE_ID_INFO_LOG = "pbsmrtpipe::pbsmrtpipe-info.log"

# ***** DEFAULT PIPELINE LEVEL OPTIONS ******
# Global hard limit on the maximum number of chunks per task are created
MAX_NCHUNKS = 128
MAX_NPROC = 16
MAX_TOTAL_NPROC = None
MAX_NWORKERS = 100
CHUNKED_MODE = False
# Only if the CLUSTER_MANAGER_DIR is defined
DISTRIBUTED_MODE = True
CLUSTER_MANAGER_DIR = None
TMP_DIR = os.getenv('TMP_DIR', '/tmp')
EXIT_ON_FAILIURE = False
DEBUG_MODE = False
