# -*- mode:python; coding:utf-8 -*-
# Copyright (c) 2020 IBM Corp. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Compliance automation locker tests module."""

import json
import logging
import os
import shutil
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.evidence import (
    DAY, RawEvidence, ReportEvidence, TmpEvidence, get_evidence_by_path
)
from compliance.locker import INDEX_FILE, Locker
from compliance.utils.data_parse import get_sha256_hash

from git import Repo

REPO_DIR = 'test_locker_repo'
FILES_DIR = os.path.join(tempfile.gettempdir(), 'test_locker_files')
logger = logging.getLogger()


def setup_temp():
    """Initialize tmp folder for each test."""
    clean_temp()
    os.mkdir(FILES_DIR)
    os.mkdir(os.path.join(tempfile.gettempdir(), REPO_DIR))


def clean_temp():
    """Clean up tmp folder for each test."""
    shutil.rmtree(
        os.path.join(tempfile.gettempdir(), REPO_DIR), ignore_errors=True
    )
    shutil.rmtree(FILES_DIR, ignore_errors=True)


class LockerTest(unittest.TestCase):
    """Locker test class."""

    def setUp(self):
        """Initialize each test."""
        setup_temp()

    def tearDown(self):
        """Clean up after each test."""
        clean_temp()

    def test_repo_dir(self):
        """Test that different URLs set repo_dir properly."""
        examples = [
            'https://user:pass@github.com/cloudant/test.git',
            'https://github.com/cloudant/test.git',
            'git@github.com:cloudant/test.git'
        ]
        for url in examples:
            locker = Locker(repo_url=url)
            self.assertEqual(locker.name, 'test.git')

    @patch('git.Repo')
    def test_clone(self, git_mock):
        """Test that clone is called when URL is provided."""
        url = 'git@github.com:my-example-org/locker-demo.git'
        locker = Locker(repo_url=url)
        locker.checkout()
        git_mock.clone_from.assert_called_with(
            url,
            os.path.join(tempfile.gettempdir(), 'locker-demo.git'),
            branch='master'
        )

    def test_raw_evidence(self):
        """Test putting RawEvidence into the locker."""
        locker = Locker(name=REPO_DIR)
        with locker:
            f = tempfile.mkstemp(
                prefix='testfile', suffix='.json', dir=FILES_DIR
            )
            evidence_name = os.path.split(f[1])[1]
            evidence = RawEvidence(
                evidence_name, 'test_category', DAY, 'This tests evidence.py'
            )
            test_content = '{"Squirtle": true, "Pikachu": 1, "Bulbasaur": 2}'
            evidence.set_content(test_content)

            locker.add_evidence(evidence)

        self.assertEqual(len(locker.touched_files), 1)

    def test_report_evidence(self):
        """Test putting ReportEvidence into the locker."""
        locker = Locker(name=REPO_DIR)
        with locker:
            f = tempfile.mkstemp(
                prefix='testfile', suffix='.json', dir=FILES_DIR
            )
            evidence_name = os.path.split(f[1])[1]
            evidence = ReportEvidence(
                evidence_name, 'test_category', DAY, 'This tests evidence.py'
            )
            test_content = '{"BLAH": "Test"}'
            evidence.set_content(test_content)

            locker.add_evidence(evidence)

        self.assertEqual(len(locker.touched_files), 1)

    def test_tmp_evidence(self):
        """Test putting TmpEvidence into the locker."""
        locker = Locker(name=REPO_DIR)
        with locker:
            f = tempfile.mkstemp(
                prefix='testfile', suffix='.json', dir=FILES_DIR
            )
            evidence_name = os.path.split(f[1])[1]
            tmp_evidence = TmpEvidence(
                evidence_name, 'test_category', DAY, 'This tests evidence.py'
            )
            raw_evidence = RawEvidence(
                evidence_name, 'test_category', DAY, 'This tests evidence.py'
            )
            test_content = '{"BLAH": "Test"}'
            tmp_evidence.set_content(test_content)
            raw_evidence.set_content(test_content)
            locker.add_evidence(tmp_evidence)
            locker.add_evidence(raw_evidence)

        self.assertEqual(len(locker.touched_files), 1)

    @patch('compliance.check.get_config')
    @patch('compliance.evidence.get_config')
    @patch('compliance.locker.Locker.validate')
    def test_validate_raw_evidence(
        self, validation, check_mock, evidence_mock
    ):
        """Test validate method in locker for an evidence."""
        config = ComplianceConfig()
        check_mock.return_value = config
        evidence_mock.return_value = config
        with Locker(name=REPO_DIR, do_push=True) as locker:
            f = tempfile.mkstemp(
                prefix='testfile', suffix='.json', dir=FILES_DIR
            )
            test_evidence_name = os.path.split(f[1])[1]
            evidence = RawEvidence(
                test_evidence_name,
                'test_category',
                DAY,
                'This tests if the validation works'
            )
            config.add_evidences([evidence])
            test_content = '{"Squirtle": true, "Pikachu": 1, "Bulbasaur": 2}'
            evidence.set_content(test_content)
            locker.add_evidence(evidence)
            evidence = get_evidence_by_path(
                os.path.join(
                    evidence.rootdir, evidence.category, evidence.name
                )
            )
            self.assertTrue(isinstance(evidence, RawEvidence))
            validation.return_value = True
            locker.get_evidence(
                os.path.join('raw', 'test_category', test_evidence_name)
            )

    @patch('compliance.utils.credentials.Config')
    @patch('git.Repo')
    def test_check_creds(self, mock_config, git_mock):
        """Test that credentials are present in REPO URL."""
        url = 'https://test:pass@github.com/my-example-org/test.git'
        repo_mock = MagicMock()
        repo_mock.git_dir = os.path.join(tempfile.gettempdir(), REPO_DIR)
        repo_mock.remotes = [repo_mock]
        git_mock.clone_from.return_value = repo_mock

        with Locker(name=REPO_DIR, repo_url=url, creds=mock_config()) as lckr:
            self.assertIn(url[8:], lckr.repo_url)

    def test_locker_as_expected(self):
        """Test that checks contents of the locker are as expected."""
        with Locker(name=REPO_DIR) as locker:
            test_content_one = '{"key": "value1"}'
            evidence_one = RawEvidence(
                'test_one.json', 'test_category', DAY, 'This tests locker'
            )
            evidence_one.set_content(test_content_one)
            locker.add_evidence(evidence_one)
            evidence_two = RawEvidence(
                'test_two.json', 'test_category', DAY, 'This tests locker'
            )
            evidence_two.set_content(test_content_one)
            locker.add_evidence(evidence_two)
            evidence_three = RawEvidence(
                'test_three.json',
                'test_category_two',
                DAY,
                'This tests locker'
            )
            evidence_three.set_content(test_content_one)
            locker.add_evidence(evidence_three)
            locker.checkin()

            self.assertTrue(
                locker.get_index_file(evidence_one).
                endswith(f'/raw/test_category/{INDEX_FILE}')
            )
            self.assertTrue(
                locker.get_index_file(evidence_two).
                endswith(f'/raw/test_category/{INDEX_FILE}')
            )
            self.assertTrue(
                locker.get_index_file(evidence_three).
                endswith(f'/raw/test_category_two/{INDEX_FILE}')
            )
            # Test abandoned
            self.assertEqual(set(), locker.get_abandoned_evidences())
            with open(locker.get_index_file(evidence_three), 'w') as f:
                meta = (
                    '{"test_three.json":'
                    '{"last_update":"2017-10-01T00:00:00.0"} }'
                )
                f.write(meta)
            locker.checkin()
            self.assertEqual(
                {'raw/test_category_two/test_three.json'},
                locker.get_abandoned_evidences()
            )

    def test_empty_evidence(self):
        """Test that all empty evidence is identified."""
        with Locker(name=REPO_DIR) as locker:
            populated = RawEvidence(
                'populated.json', 'test_category', DAY, 'Populated evidence'
            )
            populated.set_content('{"key": "value1"}')
            locker.add_evidence(populated)
            populated0 = RawEvidence(
                'populated0.json', 'test_category', DAY, 'Populated with zero'
            )
            populated0.set_content('0')
            locker.add_evidence(populated0)
            white_space = RawEvidence(
                'white_space.txt', 'test_category', DAY, 'Whitespace only'
            )
            white_space.set_content(' ')
            locker.add_evidence(white_space)
            empty_dict = RawEvidence(
                'empty_dict.json', 'test_category', DAY, 'Empty dictionary'
            )
            empty_dict.set_content('{}')
            locker.add_evidence(empty_dict)
            empty_list = RawEvidence(
                'empty_list.json', 'test_category', DAY, 'Empty list'
            )
            empty_list.set_content('[]')
            locker.add_evidence(empty_list)
            locker.checkin()
            self.assertCountEqual(
                locker.get_empty_evidences(),
                [
                    'raw/test_category/white_space.txt',
                    'raw/test_category/empty_dict.json',
                    'raw/test_category/empty_list.json'
                ]
            )

    def test_add_partitioned_evidence(self):
        """Test that partitioned evidence is added to locker as expected."""
        with Locker(name=REPO_DIR) as locker:
            evidence = RawEvidence(
                'foo.json',
                'cat_foo',
                DAY,
                'Partitioned evidence',
                partition={'fields': ['lname']}
            )
            data = [
                {
                    'fname': 'simon', 'lname': 'metson'
                }, {
                    'fname': 'al', 'lname': 'finkel'
                }
            ]
            evidence.set_content(json.dumps(data))
            locker.add_evidence(evidence)
            location = os.path.join(locker.local_path, evidence.dir_path)
            self.assertTrue(location.endswith('/raw/cat_foo'))
            finkel_hash = get_sha256_hash('finkel', 10)
            metson_hash = get_sha256_hash('metson', 10)
            expected = [
                'index.json',
                f'{finkel_hash}_foo.json',
                f'{metson_hash}_foo.json'
            ]
            self.assertEqual(set(os.listdir(location)), set(expected))
            meta = json.loads(open(os.path.join(location, expected[0])).read())
            self.assertEqual(len(meta.keys()), 1)
            self.assertEqual(
                set(meta['foo.json'].keys()),
                {
                    'description',
                    'last_update',
                    'partition_fields',
                    'partition_root',
                    'partitions',
                    'ttl'
                }
            )
            self.assertEqual(meta['foo.json']['partition_fields'], ['lname'])
            self.assertIsNone(meta['foo.json']['partition_root'])
            self.assertEqual(len(meta['foo.json']['partitions']), 2)
            self.assertEqual(
                meta['foo.json']['partitions'][finkel_hash], ['finkel']
            )
            self.assertEqual(
                meta['foo.json']['partitions'][metson_hash], ['metson']
            )
            self.assertEqual(
                json.loads(open(os.path.join(location, expected[1])).read()),
                [{
                    'fname': 'al', 'lname': 'finkel'
                }]
            )
            self.assertEqual(
                json.loads(open(os.path.join(location, expected[2])).read()),
                [{
                    'fname': 'simon', 'lname': 'metson'
                }]
            )

    def test_get_partitioned_evidence(self):
        """Test that partitioned evidence is retrieved from the locker."""
        with Locker(name=REPO_DIR) as locker:
            evidence = RawEvidence(
                'foo.json',
                'cat_foo',
                DAY,
                'Partitioned evidence',
                partition={'fields': ['lname']}
            )
            data = [
                {
                    'fname': 'simon', 'lname': 'metson'
                }, {
                    'fname': 'al', 'lname': 'finkel'
                }
            ]
            evidence.set_content(json.dumps(data))
            locker.add_evidence(evidence)
            locker.checkin()
            partitioned = locker.get_evidence(evidence.path)
            self.assertTrue(partitioned.is_partitioned)
            content = json.loads(partitioned.content)
            self.assertEqual(len(content), 2)
            self.assertIn({'fname': 'simon', 'lname': 'metson'}, content)
            self.assertIn({'fname': 'al', 'lname': 'finkel'}, content)
            self.assertEqual(
                json.loads(partitioned.get_partition(['metson'])),
                [{
                    'fname': 'simon', 'lname': 'metson'
                }]
            )
            self.assertEqual(
                json.loads(partitioned.get_partition(['finkel'])),
                [{
                    'fname': 'al', 'lname': 'finkel'
                }]
            )
            self.assertEqual(
                json.loads(partitioned.get_partition(['meh'])), []
            )

    def test_get_unpartitioned_evidence(self):
        """Test that unpartitioned evidence is retrieved from the locker."""
        with Locker(name=REPO_DIR) as locker:
            evidence = RawEvidence(
                'foo.json', 'cat_foo', DAY, 'Partitioned evidence'
            )
            data = [
                {
                    'fname': 'simon', 'lname': 'metson'
                }, {
                    'fname': 'al', 'lname': 'finkel'
                }
            ]
            evidence.set_content(json.dumps(data))
            locker.add_evidence(evidence)
            locker.checkin()
            partitioned = locker.get_evidence(evidence.path)
            self.assertFalse(partitioned.is_partitioned)
            content = json.loads(partitioned.content)
            self.assertEqual(len(content), 2)
            self.assertIn({'fname': 'simon', 'lname': 'metson'}, content)
            self.assertIn({'fname': 'al', 'lname': 'finkel'}, content)

    def test_abandoned_partitioned_evidence(self):
        """Test that ensures abandoned partitioned evidence is found."""
        with Locker(name=REPO_DIR) as locker:
            evidence = RawEvidence(
                'foo.json',
                'cat_foo',
                DAY,
                'Partitioned evidence',
                partition={'fields': ['lname']}
            )
            data = [
                {
                    'fname': 'simon', 'lname': 'metson'
                }, {
                    'fname': 'al', 'lname': 'finkel'
                }
            ]
            evidence.set_content(json.dumps(data))
            locker.add_evidence(evidence)
            locker.checkin()
            # Test abandoned
            self.assertEqual(set(), locker.get_abandoned_evidences())
            abandoned_meta = {
                'foo.json': {
                    'last_update': '2017-10-01T00:00:00.0',
                    'partitions': {
                        '1197ced566_foo.json': 'meh',
                        '3eeaf57767_foo.json': 'bleh'
                    }
                }
            }
            with open(locker.get_index_file(evidence), 'w') as f:
                f.write(json.dumps(abandoned_meta))
            locker.checkin()
            self.assertEqual(
                {
                    'raw/cat_foo/1197ced566_foo.json',
                    'raw/cat_foo/3eeaf57767_foo.json'
                },
                locker.get_abandoned_evidences()
            )

    def test_get_hash(self):
        """Test that get_hash returns a valid commit hash."""
        with Locker(name=REPO_DIR, do_push=False) as locker:
            evidence = RawEvidence(
                'test.json', 'test_category', DAY, 'This tests evidence.py'
            )
            test_content = '{"key": "value"}'
            evidence.set_content(test_content)
            locker.add_evidence(evidence)
            self.assertIsNone(locker.get_hash())
        commit = locker.get_hash()
        self.assertEqual(len(commit), 40)

    def test_get_latest_commit_with_date_success(self):
        """Test get_latest_commit call when date provided."""
        locker = Locker()
        locker.repo = create_autospec(Repo)
        locker.repo.iter_commits = MagicMock()
        locker.repo.iter_commits.return_value = iter(['foo'])
        ev_date = datetime(2019, 11, 15)

        self.assertEqual(
            locker.get_latest_commit('raw/foo/foo.json', ev_date), 'foo'
        )
        locker.repo.iter_commits.assert_called_once_with(
            paths='raw/foo/foo.json', max_count=1, until='2019-11-15'
        )

    def test_get_latest_commit_without_date_success(self):
        """Test get_latest_commit call when date omitted."""
        locker = Locker()
        locker.repo = create_autospec(Repo)
        locker.repo.iter_commits = MagicMock()
        locker.repo.iter_commits.return_value = iter(['foo'])

        self.assertEqual(locker.get_latest_commit('raw/foo/foo.json'), 'foo')
        locker.repo.iter_commits.assert_called_once_with(
            paths='raw/foo/foo.json', max_count=1
        )

    def test_get_latest_commit_exception(self):
        """Test get_latest_commit call when no commits available."""
        locker = Locker()
        locker.repo = create_autospec(Repo)
        locker.repo.iter_commits = MagicMock()
        locker.repo.iter_commits.return_value = iter([])

        self.assertIsNone(locker.get_latest_commit('raw/foo/foo.json'))
        locker.repo.iter_commits.assert_called_once_with(
            paths='raw/foo/foo.json', max_count=1
        )
