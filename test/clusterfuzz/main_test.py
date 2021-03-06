"""Tests the module that parses and executes commands."""
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

import unittest
import mock

from clusterfuzz import main
from test import helpers


class MainTest(unittest.TestCase):
  """Test main."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.commands.reproduce.execute'
    ])

  def test_parse_reproduce(self):
    """Test parse reproduce command."""
    main.execute(['reproduce', '1234'])
    main.execute(['reproduce', '1234', '--current'])
    main.execute(['reproduce', '1234', '--download'])
    main.execute(['reproduce', '1234', '--current', '--download'])

    self.mock.execute.assert_has_calls(
        [mock.call('1234', False, False), mock.call('1234', True, False),
         mock.call('1234', False, True), mock.call('1234', True, True)])
