"""Test the binary_providers module."""
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
import json
import zipfile
import mock

from clusterfuzz import binary_providers
from test import helpers

class BuildRevisionToShaUrlTest(helpers.ExtendedTestCase):
  """Tests the build_revision_to_sha_url method."""

  def setUp(self):
    helpers.patch(self, [
        'urlfetch.fetch'])

  def test_correct_url_building(self):
    """Tests if the SHA url is built correctly"""

    result = binary_providers.build_revision_to_sha_url(12345, 'v8/v8')
    self.assertEqual(result, ('https://cr-rev.appspot.com/_ah/api/crrev/v1'
                              '/get_numbering?project=chromium&repo=v8%2Fv8'
                              '&number=12345&numbering_type='
                              'COMMIT_POSITION&numbering_identifier=refs'
                              '%2Fheads%2Fmaster'))


class ShaFromRevisionTest(helpers.ExtendedTestCase):
  """Tests the sha_from_revision method."""

  def setUp(self):
    helpers.patch(self, ['urlfetch.fetch'])

  def test_get_sha_from_response_body(self):
    """Tests to ensure that the sha is grabbed from the response correctly"""

    self.mock.fetch.return_value = mock.Mock(body=json.dumps({
        'id': 12345,
        'git_sha': '1a2s3d4f',
        'crash_type': 'Bad Crash'}))

    result = binary_providers.sha_from_revision(123456, 'v8/v8')
    self.assertEqual(result, '1a2s3d4f')


class DownloadBuildDataTest(helpers.ExtendedTestCase):
  """Tests the download_build_data test."""

  def setUp(self):
    helpers.patch(self, ['clusterfuzz.common.execute'])

    self.setup_fake_filesystem()
    self.build_url = 'https://storage.cloud.google.com/abc.zip'
    self.provider = binary_providers.BinaryProvider(1234, self.build_url)

  def test_build_data_already_downloaded(self):
    """Tests the exit when build data is already returned."""

    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
    os.makedirs(build_dir)
    self.provider.build_dir = build_dir
    result = self.provider.download_build_data()
    self.assert_n_calls(0, [self.mock.execute])
    self.assertEqual(result, build_dir)

  def test_get_build_data(self):
    """Tests extracting, moving and renaming the build data.."""

    os.makedirs(self.clusterfuzz_dir)
    cf_builds_dir = os.path.join(self.clusterfuzz_dir, 'builds')

    with open(os.path.join(self.clusterfuzz_dir, 'args.gn'), 'w') as f:
      f.write('use_goma = True')
    with open(os.path.join(self.clusterfuzz_dir, 'd8'), 'w') as f:
      f.write('fake d8')
    fakezip = zipfile.ZipFile(
        os.path.join(self.clusterfuzz_dir, 'abc.zip'), 'w')
    fakezip.write(os.path.join(self.clusterfuzz_dir, 'args.gn'),
                  'abc//args.gn', zipfile.ZIP_DEFLATED)
    fakezip.write(os.path.join(self.clusterfuzz_dir, 'd8'),
                  'abc//d8', zipfile.ZIP_DEFLATED)
    fakezip.close()
    self.assertTrue(
        os.path.isfile(os.path.join(self.clusterfuzz_dir, 'abc.zip')))

    self.provider.download_build_data()

    self.assert_exact_calls(self.mock.execute, [mock.call(
        'gsutil cp gs://abc.zip .',
        self.clusterfuzz_dir)])
    self.assertFalse(
        os.path.isfile(os.path.join(self.clusterfuzz_dir, 'abc.zip')))
    self.assertTrue(os.path.isdir(
        os.path.join(cf_builds_dir, '1234_build')))
    self.assertTrue(os.path.isfile(os.path.join(
        cf_builds_dir,
        '1234_build',
        'args.gn')))
    with open(os.path.join(cf_builds_dir, '1234_build', 'args.gn'), 'r') as f:
      self.assertEqual('use_goma = True', f.read())
    with open(os.path.join(cf_builds_dir, '1234_build', 'd8'), 'r') as f:
      self.assertEqual('fake d8', f.read())


class GetBinaryPathTest(helpers.ExtendedTestCase):
  """Tests the get_binary_path method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8DownloadedBinary.get_build_directory'])

  def test_call(self):
    """Tests calling the method."""

    build_dir = os.path.expanduser(os.path.join('~', 'chrome_src',
                                                'out', '12345_build'))
    self.mock.get_build_directory.return_value = build_dir

    provider = binary_providers.V8DownloadedBinary(12345, 'build_url')
    result = provider.get_binary_path()
    self.assertEqual(result, os.path.join(build_dir, 'd8'))


class V8BuilderGetBuildDirectoryTest(helpers.ExtendedTestCase):
  """Test get_build_directory inside the V8DownloadedBinary class."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8Builder.download_build_data',
        'clusterfuzz.binary_providers.sha_from_revision',
        'clusterfuzz.binary_providers.V8Builder.checkout_source_by_sha',
        'clusterfuzz.binary_providers.V8Builder.build_target',
        'clusterfuzz.common.ask'])

    self.setup_fake_filesystem()
    self.build_url = 'https://storage.cloud.google.com/abc.zip'

  def test_parameter_not_set_valid_source(self):
    """Tests functionality when build has never been downloaded."""

    chrome_source = os.path.join('chrome', 'src', 'dir')
    provider = binary_providers.V8Builder(12345, self.build_url, 54321,
                                          False, '', chrome_source)

    result = provider.get_build_directory()
    self.assertEqual(result, os.path.join(chrome_source, 'out',
                                          'clusterfuzz_12345'))
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])
    self.assert_exact_calls(self.mock.build_target, [mock.call(provider)])
    self.assert_exact_calls(self.mock.checkout_source_by_sha,
                            [mock.call(provider)])
    self.assert_n_calls(0, [self.mock.ask])

  def test_parameter_not_set_invalid_source(self):
    """Tests when build is not downloaded & no valid source passed."""

    chrome_source = os.path.join('chrome', 'src', 'dir')
    provider = binary_providers.V8Builder(12345, self.build_url, 54321,
                                          False, '', None)
    self.mock.ask.return_value = chrome_source

    result = provider.get_build_directory()
    self.assertEqual(result, os.path.join(chrome_source, 'out',
                                          'clusterfuzz_12345'))
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])
    self.assert_exact_calls(self.mock.build_target, [mock.call(provider)])
    self.assert_exact_calls(self.mock.checkout_source_by_sha,
                            [mock.call(provider)])
    self.assert_exact_calls(self.mock.ask, [
        mock.call(('This is a V8 testcase, please define $V8_SRC or enter '
                   'your V8 source location here'),
                  'Please enter a valid directory',
                  mock.ANY)])

  def test_parameter_already_set(self):
    """Tests functionality when build_directory parameter is already set."""

    provider = binary_providers.V8Builder(12345, self.build_url, '',
                                          False, '', '')
    provider.build_directory = 'dir/already/set'

    result = provider.get_build_directory()
    self.assertEqual(result, 'dir/already/set')
    self.assert_n_calls(0, [self.mock.download_build_data])

class V8DownloadedBuildGetBinaryDirectoryTest(helpers.ExtendedTestCase):
  """Test get_build_directory inside the V8DownloadedBuild class."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8DownloadedBinary.download_build_data'])

    self.setup_fake_filesystem()
    self.build_url = 'https://storage.cloud.google.com/abc.zip'

  def test_parameter_not_set(self):
    """Tests functionality when build has never been downloaded."""

    provider = binary_providers.V8DownloadedBinary(12345, self.build_url)
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '12345_build')

    result = provider.get_build_directory()
    self.assertEqual(result, build_dir)
    self.assert_exact_calls(self.mock.download_build_data,
                            [mock.call(provider)])

  def test_parameter_already_set(self):
    """Tests functionality when the build_directory parameter is already set."""

    provider = binary_providers.V8DownloadedBinary(12345, self.build_url)
    provider.build_directory = 'dir/already/set'

    result = provider.get_build_directory()
    self.assertEqual(result, 'dir/already/set')
    self.assert_n_calls(0, [self.mock.download_build_data])


class BuildTargetTest(helpers.ExtendedTestCase):
  """Tests the build_chrome method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.binary_providers.V8Builder.setup_gn_args',
        'multiprocessing.cpu_count',
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision'])
    self.mock.cpu_count.return_value = 12

  def test_correct_calls(self):
    """Tests the correct checks and commands are run to build."""

    revision_num = 12345
    testcase_id = 54321
    chrome_source = '/chrome/source'
    goma_dir = '/goma/dir/location'
    builder = binary_providers.V8Builder(
        testcase_id, 'build_url', revision_num, False, goma_dir, chrome_source)
    builder.build_directory = '/chrome/source/out/clusterfuzz_54321'
    builder.build_target()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('GYP_DEFINES=asan=1 gclient runhooks', chrome_source),
        mock.call('GYP_DEFINES=asan=1 gypfiles/gyp_v8', chrome_source),
        mock.call(
            'ninja -C /chrome/source/out/clusterfuzz_54321 -j 120 d8',
            chrome_source)])
    self.assert_exact_calls(self.mock.setup_gn_args, [mock.call(builder)])


class SetupGnArgsTest(helpers.ExtendedTestCase):
  """Tests the setup_gn_args method."""

  def setUp(self):
    self.setup_fake_filesystem()
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.binary_providers.sha_from_revision'])
    self.testcase_dir = os.path.expanduser(os.path.join('~', 'test_dir'))
    self.builder = binary_providers.V8Builder(
        1234, '', '', False, '/goma/dir', '/chrome/source/dir')

  def test_args_setup(self):
    """Tests to ensure that the args.gn is setup correctly."""

    os.makedirs(self.testcase_dir)
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'w') as f:
      f.write('Not correct args.gn')
    build_dir = os.path.join(self.clusterfuzz_dir, 'builds', '1234_build')
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, 'args.gn'), 'w') as f:
      f.write('goma_dir = /not/correct/dir')

    self.builder.build_directory = self.testcase_dir
    self.builder.setup_gn_args()

    self.assert_exact_calls(self.mock.execute, [
        mock.call('gn gen %s' % self.testcase_dir, '/chrome/source/dir')])
    with open(os.path.join(self.testcase_dir, 'args.gn'), 'r') as f:
      self.assertEqual(f.read(), 'goma_dir = /goma/dir\n')



class CheckoutSourceByShaTest(helpers.ExtendedTestCase):
  """Tests the checkout_chrome_by_sha method."""

  def setUp(self):
    helpers.patch(self, [
        'clusterfuzz.common.execute',
        'clusterfuzz.common.check_confirm',
        'clusterfuzz.binary_providers.sha_from_revision'])
    self.chrome_source = '/usr/local/google/home/user/repos/chromium/src'
    self.command = ('git fetch && git checkout 1a2s3d4f'
                    ' in %s' % self.chrome_source)
    self.builder = binary_providers.V8Builder(
        1234, '', 12345, False, '', self.chrome_source)
    self.builder.git_sha = '1a2s3d4f'

  def test_not_already_checked_out(self):
    """Tests when the correct git sha is not already checked out."""

    self.mock.execute.return_value = [0, 'not_the_same']
    self.builder.checkout_source_by_sha()

    self.assert_exact_calls(
        self.mock.execute,
        [mock.call('git rev-parse HEAD',
                   self.chrome_source,
                   print_output=False),
         mock.call('git fetch && git checkout 1a2s3d4f', self.chrome_source)])
    self.assert_exact_calls(self.mock.check_confirm,
                            [mock.call(
                                'Proceed with the following command:\n%s?' %
                                self.command)])
  def test_already_checked_out(self):
    """Tests when the correct git sha is already checked out."""

    self.mock.execute.return_value = [0, '1a2s3d4f']
    self.builder.checkout_source_by_sha()

    self.assert_exact_calls(self.mock.execute,
                            [mock.call('git rev-parse HEAD',
                                       self.chrome_source,
                                       print_output=False)])
    self.assert_n_calls(0, [self.mock.check_confirm])
