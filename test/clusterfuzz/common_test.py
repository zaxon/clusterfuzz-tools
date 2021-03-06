"""Test the 'common' module."""
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

import cStringIO
import subprocess
import os
import stat
import mock

from clusterfuzz import common
from test import helpers

class ConfirmTest(helpers.ExtendedTestCase):
  """Tests the confirm method."""

  def setUp(self):
    helpers.patch(self, ['__builtin__.raw_input'])

  def test_yes_default(self):
    """Tests functionality with yes as default."""

    self.mock.raw_input.side_effect = ['y', 'n', '']

    self.assertTrue(common.confirm('A question'))
    self.assertFalse(common.confirm('A question'))
    self.assertTrue(common.confirm('A question'))

    self.mock.raw_input.assert_has_calls([mock.call('A question [Y/n]: ')])
    self.assert_n_calls(3, [self.mock.raw_input])

  def test_no_default(self):
    """Tests functionality when no is the default."""

    self.mock.raw_input.side_effect = ['y', 'n', '']

    self.assertTrue(common.confirm('A question', default='n'))
    self.assertFalse(common.confirm('A question', default='n'))
    self.assertFalse(common.confirm('A question', default='n'))

    self.mock.raw_input.assert_has_calls([mock.call('A question [y/N]: ')])
    self.assert_n_calls(3, [self.mock.raw_input])

  def test_empty_default(self):
    """Tests functionality when default is explicitly None."""

    self.mock.raw_input.side_effect = ['y', 'n', '', 'n']

    self.assertTrue(common.confirm('A question', default=None))
    self.assertFalse(common.confirm('A question', default=None))
    self.assertFalse(common.confirm('A question', default=None))

    self.mock.raw_input.assert_has_calls([
        mock.call('A question [y/n]: '),
        mock.call('Please type either "y" or "n": ')])
    self.assert_n_calls(4, [self.mock.raw_input])


class ExecuteTest(helpers.ExtendedTestCase):
  """Tests the execute method."""

  def setUp(self):
    helpers.patch(self, ['subprocess.Popen'])
    self.lines = 'Line 1\nLine 2\nLine 3'

  def build_popen_mock(self, code):
    """Builds the mocked Popen object."""
    return mock.MagicMock(
        stdout=cStringIO.StringIO(self.lines),
        returncode=code)

  def run_execute(self, print_out, exit_on_err):
    return common.execute(
        'cmd',
        '~/working/directory',
        print_output=print_out,
        exit_on_error=exit_on_err)

  def run_popen_assertions(self, code, print_out=True, exit_on_err=True):
    """Runs the popen command and tests the output."""

    self.mock.Popen.reset_mock()
    self.mock.Popen.return_value = self.build_popen_mock(code)
    self.mock.Popen.return_value.wait.return_value = True
    return_code = returned_lines = None
    will_exit = exit_on_err and code != 0

    if will_exit:
      with self.assertRaises(SystemExit):
        return_code, returned_lines = self.run_execute(print_out, exit_on_err)
    else:
      return_code, returned_lines = self.run_execute(print_out, exit_on_err)

    self.assertEqual(return_code, None if will_exit else code)
    self.assertEqual(returned_lines, None if will_exit else self.lines)
    self.assert_exact_calls(self.mock.Popen.return_value.wait, [mock.call()])
    self.assert_exact_calls(self.mock.Popen, [mock.call(
        'cmd',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd='~/working/directory',
        env=None)])

  def test_process_runs_successfully(self):
    """Test execute when the process successfully runs."""

    return_code = 0
    for print_out in [True, False]:
      for exit_on_error in [True, False]:
        self.run_popen_assertions(return_code, print_out, exit_on_error)

  def test_process_run_fails(self):
    """Test execute when the process does not run successfully."""

    return_code = 1
    for print_out in [True, False]:
      for exit_on_error in [True, False]:
        self.run_popen_assertions(return_code, print_out, exit_on_error)


class StoreAuthHeaderTest(helpers.ExtendedTestCase):
  """Tests the store_auth_header method."""

  def setUp(self):
    self.setup_fake_filesystem()
    self.auth_header = 'Bearer 12345'

  def test_folder_absent(self):
    """Tests storing when the folder has not been created prior."""

    self.assertFalse(os.path.exists(self.clusterfuzz_dir))
    common.store_auth_header(self.auth_header)

    self.assertTrue(os.path.exists(self.clusterfuzz_dir))
    with open(self.auth_header_file, 'r') as f:
      self.assertEqual(f.read(), self.auth_header)
    self.assert_file_permissions(self.auth_header_file, 600)

  def test_folder_present(self):
    """Tests storing when the folder has already been created."""

    self.fs.CreateFile(self.auth_header_file)
    common.store_auth_header(self.auth_header)

    with open(self.auth_header_file, 'r') as f:
      self.assertEqual(f.read(), self.auth_header)
    self.assert_file_permissions(self.auth_header_file, 600)


class GetStoredAuthHeaderTest(helpers.ExtendedTestCase):
  """Tests the stored_auth_key method."""

  def setUp(self):
    self.setup_fake_filesystem()

  def test_file_missing(self):
    """Tests functionality when auth key file does not exist."""

    result = common.get_stored_auth_header()
    self.assertEqual(result, None)

  def test_permissions_incorrect(self):
    """Tests functionality when file exists but permissions wrong."""

    self.fs.CreateFile(self.auth_header_file)
    os.chmod(self.auth_header_file, stat.S_IWGRP)

    with self.assertRaises(common.PermissionsTooPermissiveError) as ex:
      result = common.get_stored_auth_header()
      self.assertEqual(result, None)
    self.assertIn(
        'File permissions too permissive to open',
        ex.exception.message)

  def test_file_valid(self):
    """Tests when file is accessible and auth key is returned."""

    self.fs.CreateFile(self.auth_header_file, contents='Bearer 1234')
    os.chmod(self.auth_header_file, stat.S_IWUSR|stat.S_IRUSR)

    result = common.get_stored_auth_header()
    self.assertEqual(result, 'Bearer 1234')


class CheckConfirmTest(helpers.ExtendedTestCase):
  """Tests the check_confirm method."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.confirm'])

  def test_answer_yes(self):
    self.mock.confirm.return_value = True
    common.check_confirm('Question?')
    self.assert_exact_calls(self.mock.confirm, [mock.call('Question?')])

  def test_answer_no(self):
    self.mock.confirm.return_value = False
    with self.assertRaises(SystemExit):
      common.check_confirm('Question?')
    self.assert_exact_calls(self.mock.confirm, [mock.call('Question?')])


class AskTest(helpers.ExtendedTestCase):
  """Tests the ask method."""

  def setUp(self):
    helpers.patch(self, ['__builtin__.raw_input'])
    self.mock.raw_input.side_effect = [
        'wrong', 'still wrong', 'very wrong', 'correct']

  def test_returns_when_correct(self):
    """Tests that the method only returns when the answer fits validation."""

    question = 'Initial Question'
    error_message = 'Please answer correctly'
    validate_fn = lambda x: x == 'correct'

    result = common.ask(question, error_message, validate_fn)
    self.assert_n_calls(4, [self.mock.raw_input])
    self.mock.raw_input.assert_has_calls([
        mock.call('Initial Question: '),
        mock.call('Please answer correctly: ')])
    self.assertEqual(result, 'correct')
