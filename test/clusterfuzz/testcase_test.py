"""Test the 'testcase' module and class."""
# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import mock

from test import helpers
from clusterfuzz import testcase

def build_base_testcase(stacktrace_lines=None, revision=None, build_url=None,
                        window_arg='', minimized_args=''):
  """Builds a testcase instance that can be used for testing."""
  if stacktrace_lines is None:
    stacktrace_lines = []
  testcase_json = {
      'id': '12345',
      'crash_stacktrace': {'lines': stacktrace_lines},
      'crash_revision': revision,
      'metadata': {'build_url': build_url},
      'testcase': {'window_argument': window_arg,
                   'minimized_arguments': minimized_args}}

  return testcase.Testcase(testcase_json)


class TestcaseSetupTest(helpers.ExtendedTestCase):
  """Tests populating the testcase parameters."""

  def test_parsing_json(self):
    """Ensures the JSON is parsed correctly."""

    stacktrace_lines = [
        {'content': '[Environment] TEST_ARGS = first=1:second=2'},
        {'content': 'Not an env line'},
        {'content': '[Environment] TEST_TWO = third=3:fourth=4'}]
    result = build_base_testcase(
        stacktrace_lines=stacktrace_lines, revision=5,
        window_arg='--random-seed=23', minimized_args='--turbo',
        build_url='build_url')
    self.assertEqual(result.id, '12345')
    self.assertEqual(result.revision, 5)
    self.assertEqual(result.environment, {'TEST_ARGS': 'first=1:second=2',
                                          'TEST_TWO': 'third=3:fourth=4'})
    self.assertEqual(result.reproduction_args, '--random-seed=23 --turbo')
    self.assertEqual(result.build_url, 'build_url')


class GetTestcasePathTest(helpers.ExtendedTestCase):
  """Tests the get_testcase_path method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.get_stored_auth_header',
        'clusterfuzz.common.execute'])
    self.mock.get_stored_auth_header.return_value = 'Bearer 1a2s3d4f'
    self.testcase_dir = os.path.expanduser(os.path.join(
        '~', '.clusterfuzz', 'testcases', '12345_testcase'))
    self.test = build_base_testcase()

  def test_already_downloaded(self):
    """Tests the scenario in which the testcase is already downloaded."""

    filename = os.path.join(self.testcase_dir, 'testcase.js')
    os.makedirs(self.testcase_dir)
    with open(filename, 'w') as f:
      f.write('testcase exists')
    self.assertTrue(os.path.isfile(filename))

    result = self.test.get_testcase_path()
    self.assertEqual(result, filename)
    self.assert_n_calls(0, [self.mock.get_stored_auth_header,
                            self.mock.execute])

  def test_not_already_downloaded(self):
    """Tests the creation of folders & downloading of the testcase"""

    filename = os.path.join(self.testcase_dir, 'testcase.js')
    self.assertFalse(os.path.exists(self.testcase_dir))

    result = self.test.get_testcase_path()

    self.assertEqual(result, filename)
    self.assert_exact_calls(self.mock.get_stored_auth_header, [mock.call()])
    self.assert_exact_calls(self.mock.execute, [mock.call(
        ('wget --header="Authorization: %s" "%s" -O ./testcase.js' %
         (self.mock.get_stored_auth_header.return_value,
          testcase.CLUSTERFUZZ_TESTCASE_URL % str(12345))),
        self.testcase_dir)])
    self.assertTrue(os.path.exists(self.testcase_dir))
