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
from datetime import datetime
from unittest.mock import MagicMock, create_autospec, patch

from compliance.config import ComplianceConfig
from compliance.evidence import (
    DAY, RawEvidence, ReportEvidence, TmpEvidence, get_evidence_by_path
)
from compliance.locker import INDEX_FILE, Locker
from compliance.utils.data_parse import get_sha256_hash

from git import Repo

from nose import with_setup
from nose.tools import (
    assert_equals,
    assert_false,
    assert_in,
    assert_is_none,
    assert_true,
)

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


def test_repo_dir():
    """Test that different URLs set repo_dir properly."""
    examples = [
        'https://user:pass@github.com/cloudant/test.git',
        'https://github.com/cloudant/test.git',
        'git@github.com:cloudant/test.git'
    ]
    for url in examples:
        locker = Locker(repo_url=url)
        assert_equals(locker.name, 'test.git')


@patch('git.Repo')
def test_clone(git_mock):
    """Test that clone is called when URL is provided."""
    url = 'git@github.com:my-example-org/locker-demo.git'
    locker = Locker(repo_url=url)
    locker.checkout()
    git_mock.clone_from.assert_called_with(
        url,
        os.path.join(tempfile.gettempdir(), 'locker-demo.git'),
        branch='master'
    )


@with_setup(setup_temp, clean_temp)
def test_raw_evidence():
    """Test putting RawEvidence into the locker."""
    locker = Locker(name=REPO_DIR)
    with locker:
        f = tempfile.mkstemp(prefix='testfile', suffix='.json', dir=FILES_DIR)
        evidence_name = os.path.split(f[1])[1]
        evidence = RawEvidence(
            evidence_name, 'test_category', DAY, 'This tests evidence.py'
        )
        test_content = '{"Squirtle": true, "Pikachu": 1, "Bulbasaur": 2}'
        evidence.set_content(test_content)

        locker.add_evidence(evidence)

    assert_equals(len(locker.touched_files), 1)


@with_setup(setup_temp, clean_temp)
def test_report_evidence():
    """Test putting ReportEvidence into the locker."""
    locker = Locker(name=REPO_DIR)
    with locker:
        f = tempfile.mkstemp(prefix='testfile', suffix='.json', dir=FILES_DIR)
        evidence_name = os.path.split(f[1])[1]
        evidence = ReportEvidence(
            evidence_name, 'test_category', DAY, 'This tests evidence.py'
        )
        test_content = '{"BLAH": "Test"}'
        evidence.set_content(test_content)

        locker.add_evidence(evidence)

    assert_equals(len(locker.touched_files), 1)


@with_setup(setup_temp, clean_temp)
def test_tmp_evidence():
    """Test putting TmpEvidence into the locker."""
    locker = Locker(name=REPO_DIR)
    with locker:
        f = tempfile.mkstemp(prefix='testfile', suffix='.json', dir=FILES_DIR)
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

    assert_equals(len(locker.touched_files), 1)


@with_setup(setup_temp, clean_temp)
@patch('compliance.check.get_config')
@patch('compliance.evidence.get_config')
@patch('compliance.locker.Locker.validate')
def test_validate_raw_evidence(validation, check_mock, evidence_mock):
    """Test validate method in locker for an evidence."""
    config = ComplianceConfig()
    check_mock.return_value = config
    evidence_mock.return_value = config
    with Locker(name=REPO_DIR, do_push=True) as locker:
        f = tempfile.mkstemp(prefix='testfile', suffix='.json', dir=FILES_DIR)
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
            os.path.join(evidence.rootdir, evidence.category, evidence.name)
        )
        assert_true(isinstance(evidence, RawEvidence))
        validation.return_value = True
        locker.get_evidence(
            os.path.join('raw', 'test_category', test_evidence_name)
        )


@with_setup(setup_temp, clean_temp)
@patch('utilitarian.credentials.Config')
@patch('git.Repo')
def test_check_creds(mock_config, git_mock):
    """Test that credentials are present in REPO URL."""
    url = 'https://test:pass@github.com/my-example-org/test.git'
    repo_mock = MagicMock()
    repo_mock.git_dir = os.path.join(tempfile.gettempdir(), REPO_DIR)
    repo_mock.remotes = [repo_mock]
    git_mock.clone_from.return_value = repo_mock

    with Locker(name=REPO_DIR, repo_url=url, creds=mock_config()) as locker:
        assert_in(url[8:], locker.repo_url)


@with_setup(setup_temp, clean_temp)
def test_locker_as_expected():
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
            'test_three.json', 'test_category_two', DAY, 'This tests locker'
        )
        evidence_three.set_content(test_content_one)
        locker.add_evidence(evidence_three)
        locker.checkin()

        assert_true(
            locker.get_index_file(evidence_one).
            endswith(f'/raw/test_category/{INDEX_FILE}')
        )
        assert_true(
            locker.get_index_file(evidence_two).
            endswith(f'/raw/test_category/{INDEX_FILE}')
        )
        assert_true(
            locker.get_index_file(evidence_three).
            endswith(f'/raw/test_category_two/{INDEX_FILE}')
        )
        # Test abandoned
        assert_equals(set(), locker.get_abandoned_evidences())
        with open(locker.get_index_file(evidence_three), 'w') as f:
            f.write(
                '{"test_three.json":{"last_update":"2017-10-01T00:00:00.0"} }'
            )
        locker.checkin()
        assert_equals(
            {'raw/test_category_two/test_three.json'},
            locker.get_abandoned_evidences()
        )


@with_setup(setup_temp, clean_temp)
def test_add_partitioned_evidence():
    """Test that partitioned evidence is added to the locker as expected."""
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
        assert_true(location.endswith('/raw/cat_foo'))
        finkel_hash = get_sha256_hash('finkel', 10)
        metson_hash = get_sha256_hash('metson', 10)
        expected = [
            'index.json', f'{finkel_hash}_foo.json', f'{metson_hash}_foo.json'
        ]
        assert_equals(set(os.listdir(location)), set(expected))
        meta = json.loads(open(os.path.join(location, expected[0])).read())
        assert_equals(len(meta.keys()), 1)
        assert_equals(
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
        assert_equals(meta['foo.json']['partition_fields'], ['lname'])
        assert_is_none(meta['foo.json']['partition_root'])
        assert_equals(len(meta['foo.json']['partitions']), 2)
        assert_equals(meta['foo.json']['partitions'][finkel_hash], ['finkel'])
        assert_equals(meta['foo.json']['partitions'][metson_hash], ['metson'])
        assert_equals(
            json.loads(open(os.path.join(location, expected[1])).read()),
            [{
                'fname': 'al', 'lname': 'finkel'
            }]
        )
        assert_equals(
            json.loads(open(os.path.join(location, expected[2])).read()),
            [{
                'fname': 'simon', 'lname': 'metson'
            }]
        )


@with_setup(setup_temp, clean_temp)
def test_get_partitioned_evidence():
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
        assert_true(partitioned.is_partitioned)
        content = json.loads(partitioned.content)
        assert_equals(len(content), 2)
        assert_in({'fname': 'simon', 'lname': 'metson'}, content)
        assert_in({'fname': 'al', 'lname': 'finkel'}, content)
        assert_equals(
            json.loads(partitioned.get_partition(['metson'])),
            [{
                'fname': 'simon', 'lname': 'metson'
            }]
        )
        assert_equals(
            json.loads(partitioned.get_partition(['finkel'])),
            [{
                'fname': 'al', 'lname': 'finkel'
            }]
        )
        assert_equals(json.loads(partitioned.get_partition(['meh'])), [])


@with_setup(setup_temp, clean_temp)
def test_get_unpartitioned_evidence():
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
        assert_false(partitioned.is_partitioned)
        content = json.loads(partitioned.content)
        assert_equals(len(content), 2)
        assert_in({'fname': 'simon', 'lname': 'metson'}, content)
        assert_in({'fname': 'al', 'lname': 'finkel'}, content)


@with_setup(setup_temp, clean_temp)
def test_abandoned_partitioned_evidence():
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
        assert_equals(set(), locker.get_abandoned_evidences())
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
        assert_equals(
            {
                'raw/cat_foo/1197ced566_foo.json',
                'raw/cat_foo/3eeaf57767_foo.json'
            },
            locker.get_abandoned_evidences()
        )


@with_setup(setup_temp, clean_temp)
def test_get_hash():
    """Test that get_hash returns a valid commit hash."""
    with Locker(name=REPO_DIR, do_push=False) as locker:
        evidence = RawEvidence(
            'test.json', 'test_category', DAY, 'This tests evidence.py'
        )
        test_content = '{"key": "value"}'
        evidence.set_content(test_content)
        locker.add_evidence(evidence)
        assert_is_none(locker.get_hash())
    commit = locker.get_hash()
    assert_equals(len(commit), 40)


def test_get_latest_commit_with_date_success():
    """Test get_latest_commit call when date provided."""
    locker = Locker()
    locker.repo = create_autospec(Repo)
    locker.repo.iter_commits = MagicMock()
    locker.repo.iter_commits.return_value = iter(['foo'])
    ev_date = datetime(2019, 11, 15)

    assert_equals(locker.get_latest_commit('raw/foo/foo.json', ev_date), 'foo')
    locker.repo.iter_commits.assert_called_once_with(
        paths='raw/foo/foo.json', max_count=1, until='2019-11-15'
    )


def test_get_latest_commit_without_date_success():
    """Test get_latest_commit call when date omitted."""
    locker = Locker()
    locker.repo = create_autospec(Repo)
    locker.repo.iter_commits = MagicMock()
    locker.repo.iter_commits.return_value = iter(['foo'])

    assert_equals(locker.get_latest_commit('raw/foo/foo.json'), 'foo')
    locker.repo.iter_commits.assert_called_once_with(
        paths='raw/foo/foo.json', max_count=1
    )


def test_get_latest_commit_exception():
    """Test get_latest_commit call when no commits available."""
    locker = Locker()
    locker.repo = create_autospec(Repo)
    locker.repo.iter_commits = MagicMock()
    locker.repo.iter_commits.return_value = iter([])

    assert_is_none(locker.get_latest_commit('raw/foo/foo.json'))
    locker.repo.iter_commits.assert_called_once_with(
        paths='raw/foo/foo.json', max_count=1
    )
