import os
import logging

from .base import TestBase
from pbsmrtpipe.testkit.base import monkey_patch

log = logging.getLogger(__name__)


@monkey_patch
class TestCoreResources(TestBase):

    """
    Test to see of the core job directory structure and files exist
    """
    # Directories (relative to the root job) that should be created
    DIRS = ('html', 'workflow', 'tasks', 'logs')

    # Files that should exist within the 'html' subdirectory
    HTML_DIRS = ('css', 'images', 'js')
    HTML_FILES = ('index.html', 'settings.html', 'workflow.html', 'datastore.html')

    # Fils that should exist within the 'workflow' directory
    WORKFLOW_FILES = ('datastore.json', 'entry-points.json', 'report-tasks.json', 'options-task.json',
                      'options-workflow.json', 'workflow.dot', 'workflow.png', 'workflow.svg')

    def test_job_path_exists(self):
        self.assertTrue(os.path.exists(self.job_dir))
