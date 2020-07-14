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
"""Compliance locker management automation module."""

import json
import logging
import os
import re
import shutil
import tempfile
import time
from datetime import datetime as dt
from threading import Lock
from urllib.parse import urlparse

from compliance.evidence import TmpEvidence, get_evidence_class
from compliance.utils.data_parse import (
    format_json, get_sha256_hash, parse_dot_key
)
from compliance.utils.exceptions import (
    EvidenceNotFoundError, HistoricalEvidenceNotFoundError, StaleEvidenceError
)

import git

INDEX_FILE = 'index.json'
DAY = 60 * 60 * 24
AE_DEFAULT = 30 * DAY
AE_EXEMPT = [INDEX_FILE, 'README.md', 'readme.md']


class Locker(object):
    """
    The locker (context manager) class.

    The evidence locker maintains a git repository of evidence and places new
    evidence into it. It can validate a piece of evidence against a time to
    live.  The Locker is a context manager. On instantiation it will retrieve
    the configured git repository.
    """

    lock = Lock()

    def __init__(
        self,
        name=None,
        repo_url=None,
        branch='master',
        creds=None,
        do_push=False,
        ttl_tolerance=0,
        gitconfig=None
    ):
        """
        Construct and initialize the locker object.

        :param name: name (not path) to create a git repo in, if
          a url is not specified.
        :param repo_url: the URL of a git repository, credentials are supplied
          via envvars. If not set, create a local repo and commit without
          pushing to a remote.
        :param branch: branch of the repo, defaults to master, only used if
          repo is cloned from repo_url.
        :param creds: a compliance.utils.credentials.Config object containing
          remote locker credentials.
        :param do_push: if True, perform push to remove git repo if needed.
        :param ttl_tolerance: the applied to evidence time to live.  If within
          that tolerance the evidence will be treated as stale.
        :param gitconfig: the git configuration to be applied to the locker.
        """
        self.repo_url = repo_url
        self.repo_url_with_creds = self.repo_url
        if creds is not None:
            service_hostname = urlparse(self.repo_url).hostname
            token = None
            if 'github.com' in service_hostname:
                token = creds['github'].token
            elif 'github' in service_hostname:
                token = creds['github_enterprise'].token
            elif 'bitbucket' in service_hostname:
                token = creds['bitbucket'].token
            elif 'gitlab' in service_hostname:
                token = creds['gitlab'].token
            if token:
                self.repo_url_with_creds = re.sub(
                    '://', f'://{token}@', self.repo_url_with_creds
                )
        self.branch = branch
        if name is not None:
            self.name = name
        elif repo_url is not None and name is None:
            self.name = os.path.split(self.repo_url)[1]
        elif repo_url is None and name is None:
            self.name = 'example'
        self.local_path = os.path.join(tempfile.gettempdir(), self.name)
        self._do_push = do_push
        self.ttl_tolerance = ttl_tolerance
        self.gitconfig = gitconfig or {}
        self.logger = logging.getLogger(name='compliance.locker')
        self._handler = logging.StreamHandler()
        self._handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        self.logger.handlers.clear()
        self.logger.addHandler(self._handler)
        self.logger.setLevel(logging.INFO)
        self.commit_date = dt.utcnow().isoformat()
        self.forced_evidence = []
        self.dependency_rerun = []

    @property
    def touched_files(self):
        """
        Provide paths to files that have been touched in the local locker.

        Files are considered "touched" if they have been added/updated in
        the locker.

        :returns: a list of touched files.
        """
        index_files = [
            f[0]
            for f in self.repo.index.entries.keys()
            if is_index_file(f[0])
        ]
        touched_files = []
        for f in index_files:
            index_dir = os.path.dirname(f)
            content = json.loads(open(os.path.join(self.local_path, f)).read())
            for t, desc in content.items():
                if type(desc) is dict:
                    ts = desc.get('last_update')
                else:
                    ts = desc
                if ts == self.commit_date:
                    touched_files.append(os.path.join(index_dir, t))
        return touched_files

    def reset_depenency_rerun(self):
        """Reset the dependency_rerun attribute to an empty list."""
        self.dependency_rerun = []

    def get_dependency_reruns(self):
        """
        Provide dot notation path to fetcher methods to be re-executed.

        Fetchers will only be considered for re-execution if they initially
        failed to execute due to a dependency error.

        :returns: a list of fetcher methods to re-execute.
        """
        return {
            f'{r["module"]}.{r["class"]}.{r["method"]}'
            for r in self.dependency_rerun
        }

    def init(self):
        """
        Initialize the local git repository.

        If repo_url was provided to the locker object, the repository will
        be cloned. If not, a fresh new git repository will be created locally.
        """
        if self.repo_url_with_creds:
            self.checkout()
        else:
            self._repo_init()

    def logger_init_msgs(self):
        """Log locker initialization information."""
        self.logger.info(f'Local locker location is {self.local_path}')
        gpgsign = self.gitconfig.get('commit', {}).get('gpgsign')
        if self._do_push and not gpgsign:
            self.logger.warning(
                'Commits will not be cryptographically signed, best '
                'practice is to set gitconfig.commit.gpgsign to true '
                'in your locker configuration.'
            )

    def add_evidence(self, evidence, checks=None, evidence_used=None):
        """
        Add the evidence to the locker.

        The locker will generate the file internally and add it to the
        local git repository.

        :param evidence: the evidence to add. Note that evidence content
          attribute must be populated.
        :param checks: A list of checks used to generate report content.  Only
          applicable for check generated ReportEvidence.
        :param evidence_used: metadata for evidence used by a check.  Only
          applicable for check generated ReportEvidence.
        """
        if evidence.content is None:
            raise ValueError(f'Evidence {evidence.name} has no content')

        if not os.path.isdir(os.path.join(self.local_path, evidence.dir_path)):
            os.makedirs(os.path.join(self.local_path, evidence.dir_path))
        if getattr(evidence, 'is_partitioned', False):
            for key in evidence.partition_keys:
                full_path = os.path.join(
                    self.local_path,
                    evidence.dir_path,
                    f'{get_sha256_hash(key, 10)}_{evidence.name}'
                )
                with open(full_path, 'w') as f:
                    f.write(evidence.get_partition(key))
        else:
            full_path = os.path.join(self.local_path, evidence.path)
            with open(full_path, 'w') as f:
                f.write(evidence.content)
        if not evidence.path.startswith('tmp/'):
            self.index(evidence, checks, evidence_used)

    def index(self, evidence, checks=None, evidence_used=None):
        """
        Add an evidence to the git index.

        :param evidence: the evidence object.
        :param checks: A list of checks used to generate report content.  Only
          applicable for check generated ReportEvidence.
        :param evidence_used: metadata for evidence used by a check.  Only
          applicable for check generated ReportEvidence.
        """
        with self.lock:
            index_file = self.get_index_file(evidence)
            repo_files = [index_file]
            if not os.path.exists(index_file):
                metadata = {}
            else:
                metadata = json.loads(open(index_file).read())
            ev_meta = metadata.get(evidence.name, {})
            old_parts = ev_meta.get('partitions', {}).keys()
            metadata[evidence.name] = {
                'last_update': self.commit_date,
                'ttl': evidence.ttl,
                'description': evidence.description
            }
            tombstones = None
            if getattr(evidence, 'is_partitioned', False):
                unpartitioned = self.get_file(evidence.path)
                if os.path.isfile(unpartitioned):
                    # Remove/tombstone unpartitioned evidence file
                    # replaced by partitioned evidence files
                    self.repo.index.remove([unpartitioned], working_tree=True)
                    tombstones = self.create_tombstone_metadata(
                        evidence.name, ev_meta, 'Evidence is partitioned'
                    )
                parts = {}
                for key in evidence.partition_keys:
                    sha256_hash = get_sha256_hash(key, 10)
                    parts[sha256_hash] = key
                    repo_file = self.get_file(
                        f'{evidence.dir_path}/{sha256_hash}_{evidence.name}'
                    )
                    repo_files.append(repo_file)
                dead_parts = set(old_parts) - set(parts.keys())
                if dead_parts:
                    # Remove/tombstone partitioned evidence files
                    # no longer part of the evidence content
                    self.remove_partitions(evidence, dead_parts)
                    tombstones = self.create_tombstone_metadata(
                        dead_parts,
                        ev_meta,
                        'Partition no longer part of evidence'
                    )
                metadata[evidence.name].update(
                    {
                        'partition_fields': evidence.part_fields,
                        'partition_root': evidence.part_root,
                        'partitions': parts
                    }
                )
                if tombstones is None:
                    # Preserve prior tombstones
                    tombstones = ev_meta.get('tombstones')
            else:
                # Remove/tombstone partitioned evidence files
                # replaced by unpartitioned evidence file
                self.remove_partitions(evidence, old_parts)
                tombstones = self.create_tombstone_metadata(
                    old_parts, ev_meta, 'Evidence no longer partitioned'
                )
                repo_files.append(self.get_file(evidence.path))
            if tombstones:
                metadata[evidence.name]['tombstones'] = tombstones
            if checks is not None:
                metadata[evidence.name]['checks'] = checks
            if evidence_used is not None:
                metadata[evidence.name]['evidence'] = evidence_used
            with open(index_file, 'w') as f:
                f.write(format_json(metadata))
            self.repo.index.add(repo_files)

    def remove_partitions(self, evidence, hashes):
        """
        Remove partition files for the specified evidence hash keys.

        Used when switching from partitioned evidence to unpartitioned evidence
        and when partitioned file content is no longer part of the overall
        evidence content.

        :param evidence: the evidence object.
        :param hashes: an iterable with evidence partition hashes.
        """
        if not hashes:
            return
        self.repo.index.remove(
            [
                os.path.join(
                    self.local_path,
                    evidence.dir_path,
                    f'{part_hash}_{evidence.name}'
                ) for part_hash in hashes
            ],
            working_tree=True
        )

    def create_tombstone_metadata(self, candidate, metadata, reason):
        """
        Create tombstones for evidence being removed from the locker.

        :param candidate: either the name of the evidence file or an iterable
          of partition hashes.
        :param metadata: the evidence metadata dictionary.
        :param reason: the reason evidence is being removed.

        :returns: a list of tombstones.
        """
        tombstones = metadata.get('tombstones', {})
        if isinstance(candidate, str):
            tombstones.setdefault(candidate, []).append(
                {
                    'eol': self.commit_date,
                    'last_update': metadata['last_update'],
                    'reason': reason
                }
            )
        else:
            for part in candidate:
                tombstones.setdefault(part, []).append(
                    {
                        'eol': self.commit_date,
                        'last_update': metadata['last_update'],
                        'partition_fields': metadata['partition_fields'],
                        'partition_root': metadata['partition_root'],
                        'partition_key': metadata['partitions'][part],
                        'reason': reason
                    }
                )
        return tombstones

    def write_pkg_indexes(self):
        """
        Add package index files to the local git repository index.

        Update the package index files with the new timestamp for the
        updated evidence.
        """
        self.repo.index.add(
            [
                f[0]
                for f in self.repo.index.entries.keys()
                if is_index_file(f[0])
            ]
        )

    def get_index_file(self, evidence):
        """
        Provide the full path to the index file of the given evidence.

        :param evidence: the evidence object to be used.
        """
        return self.get_index_file_by_path(evidence.path)

    def get_index_file_by_path(self, evidence_path):
        """
        Provide the full path to the supplied evidence's index file.

        :param evidence_path: the path to the evidence within the evidence
          locker.

        :returns: the full path to the evidence's index file.
        """
        path = evidence_path.rsplit('/', 1).pop(0)
        return os.path.join(self.local_path, path, INDEX_FILE)

    def get_file(self, filename):
        """
        Provide the path for a file in the locker.

        The file may or may not exist in the locker.

        :param filename: the name of a file in the locker.

        :returns: the path to the filename provided.
        """
        return os.path.join(self.local_path, filename)

    def get_remote_location(self, filename, include_commit=True):
        """
        Provide the path for a file/commit SHA in the locker.

        The file may or may not exist in the locker.

        :param filename: the name of a file in the locker.
        :param include_commit: if the commit SHA should be included.

        :returns: the remote repository path to the filename provided.
        """
        if not self.repo_url_with_creds:
            return os.path.join(self.local_path, filename)

        ref = 'master'
        if include_commit:
            ref = self.repo.head.commit.hexsha
        return f'{self.repo_url}/blob/{ref}/{filename}'

    def get_evidence(self, evidence_path, ignore_ttl=False, evidence_dt=None):
        """
        Provide the evidence from the locker.

        The evidence may or may not exist in the locker.

        :param evidence_path: string path of the evidence within the locker.
          For example, `raw/service1/output.json`

        :returns: the populated evidence object.
        """
        evidence = None
        try:
            metadata = self.get_evidence_metadata(evidence_path, evidence_dt)
            class_type, category, evidence_name = evidence_path.split('/')
            evidence_class_obj = get_evidence_class(class_type)
            evidence = evidence_class_obj(
                evidence_name,
                category,
                metadata['ttl'],
                metadata['description'],
                partition={
                    'fields': metadata.get('partition_fields'),
                    'root': metadata.get('partition_root')
                }
            )
        except TypeError:
            raise EvidenceNotFoundError(
                f'Evidence {evidence_path} is not valid '
                'or not present within the locker'
            )
        return self.load_content(evidence, ignore_ttl, evidence_dt)

    def load_content(self, evidence, ignore_ttl=False, evidence_dt=None):
        """
        Populate the content of the evidence from the locker.

        :param evidence: an evidence object.
        :param ignore_ttl: Boolean for TTL validation.  Defaults to False.
        :param evidence_dt: The date of the evidence content to load.

        :returns: The evidence object with content.
        """
        self._validate_evidence(evidence, ignore_ttl)
        if getattr(evidence, 'is_partitioned', False):
            metadata = self.get_evidence_metadata(evidence.path, evidence_dt)
            content = None
            for part_hash in metadata['partitions'].keys():
                data = json.loads(
                    self._get_file_content(
                        f'{evidence.dir_path}/{part_hash}_{evidence.name}',
                        evidence_dt
                    )
                )
                if content is None:
                    content = data
                    root = content
                    if evidence.part_root:
                        root = parse_dot_key(root, evidence.part_root)
                    continue
                if evidence.part_root:
                    root.extend(parse_dot_key(data, evidence.part_root))
                else:
                    root.extend(data)
            evidence.set_content(format_json(content))
        else:
            evidence.set_content(
                self._get_file_content(evidence.path, evidence_dt)
            )
        return evidence

    def validate(self, evidence, ignore_ttl=False):
        """
        Validate the evidence against the time to live.

        :param evidence: an Evidence object.
        :param ignore_ttl: ignore time to live if set to True.

        :returns: True/False time to live validation.
        """
        if isinstance(evidence, TmpEvidence):
            full_path = os.path.join(self.local_path, evidence.path)
            return os.path.exists(full_path)
        try:
            self._validate_evidence(evidence, ignore_ttl)
            return True
        except (ValueError, KeyError):
            pass
        except StaleEvidenceError as stale_evidence:
            self._stale_message(stale_evidence.args[0])
        return False

    def checkout(self):
        """Pull (clone) the remote repository to the local git repository."""
        if os.path.isdir(os.path.join(self.local_path, '.git')):
            self.repo = git.Repo(self.local_path)
        else:
            self.repo = git.Repo.clone_from(
                self.repo_url_with_creds, self.local_path, branch=self.branch
            )
        self.init_config()

    def init_config(self):
        """Apply the git configuration."""
        with self.repo.config_writer() as cw:
            for (section, cfg) in self.gitconfig.items():
                for key, value in cfg.items():
                    cw.set_value(section, key, value)

    def checkin(self, message=None):
        """
        Commit changed files to the local git repository.

        :param message: the message to apply on the commit.
        """
        self.write_pkg_indexes()
        if not message:
            updated_files = '\n'.join(self.touched_files)
            message = (
                f'Files updated at local time {time.ctime(time.time())}'
                f'\n\n{updated_files}'
            )
        try:
            diff = self.repo.index.diff('HEAD')
            if len(diff) > 0:
                self.repo.git.commit(message=message)
        except git.BadName:
            self.repo.git.commit(message=message)

    def push(self):
        """Push the local git repository to the remote repository."""
        if self._do_push:
            self.repo.remotes[0].push()

    def add_content_to_locker(self, content, folder='', filename=None):
        """
        Add non-evidence related content to the local locker.

        :param content: the content to add to the local locker.
        :param folder: the folder in the local locker to add the content to.
        :param filename: the name of the file in the local locker.
        """
        path = os.path.join(self.local_path, folder)
        if not os.path.exists(path):
            os.mkdir(path)
        if not filename:
            raise ValueError('Filename cannot be empty.')
        results_file = os.path.join(path, filename)
        with open(results_file, 'w+') as f:
            f.write(content)
        self.repo.index.add([results_file])

    def get_reports_metadata(self):
        """
        Provide all metadata related to reports as a dictionary.

        :returns: reports metadata.
        """
        metadata = {}
        rpts = os.walk(os.path.join(self.local_path, 'reports'))
        for path in [rpath for rpath, _, files in rpts if INDEX_FILE in files]:
            with open(os.path.join(path, INDEX_FILE), 'r') as f:
                for rpt_name, rpt_metadata in json.loads(f.read()).items():
                    rpt_path = os.path.join(
                        path.split(self.local_path).pop(), rpt_name
                    )
                    metadata[rpt_path] = rpt_metadata
        return metadata

    def get_abandoned_evidences(self, threshold=None):
        """
        Provide a list of evidence where the update ``threshold`` has passed.

        :param int threshold: the time in seconds after TTL expires that
          evidence can remain un-updated before it is considered abandoned.
          The abandoned evidence threshold defaults to 30 days if none is
          provided.

        :returns: a list of abandoned evidence files.
        """
        abandoned_evidence = []
        tree = self.repo.head.commit.tree
        for f in tree.traverse():
            if (f.type != 'blob' or f.path.startswith('notifications/')
                    or f.path == 'check_results.json'
                    or f.path.split('/').pop() in AE_EXEMPT):
                continue
            metadata = self.get_evidence_metadata(f.path, dt.utcnow())
            if self._evidence_abandoned(metadata, threshold):
                abandoned_evidence.append(f.path)
        return set(abandoned_evidence)

    def delete_repo_locally(self):
        """Remove the local git repository."""
        try:
            shutil.rmtree(self.local_path)
        except OSError:
            pass

    def get_hash(self):
        """
        Provide the current master revision.

        :returns: the commit SHA or None.
        """
        if self.repo.heads:
            return self.repo.heads.master.commit.hexsha

    def get_latest_commit(self, path, dt=None):
        """
        Provide the most recent commit for the file and date specified.

        :param path: the relative path to the file.
        :param dt: the upper bound commit date.

        :returns: the latest commit containing the file specified.
        """
        commit = None
        options = {'max_count': 1}
        if dt:
            options['until'] = dt.strftime('%Y-%m-%d')
        try:
            commit = next(self.repo.iter_commits(paths=path, **options))
        except StopIteration:
            pass
        return commit

    def get_evidence_metadata(self, evidence_path, evidence_dt=None):
        """
        Provide evidence metadata from package index file.

        :param evidence_path: the evidence relative path.
        :param evidence_dt: the upper bound evidence commit date.

        :returns: the metadata for the evidence specified.
        """
        pkg_index_path = self.get_index_file_by_path(evidence_path)
        if not os.path.exists(pkg_index_path):
            return
        ev_path, ev_name = evidence_path.rsplit('/', 1)
        if evidence_dt:
            pkg_index_path = os.path.join(ev_path, INDEX_FILE)
            commit = self.get_latest_commit(pkg_index_path, evidence_dt)
            if not commit:
                return
            metadata = json.loads(
                commit.tree[pkg_index_path].data_stream.read()
            )
        else:
            metadata = json.loads(open(pkg_index_path).read())
        return metadata.get(
            ev_name,
            self._get_partitioned_evidence_metadata(metadata, ev_name)
        )

    def __enter__(self):
        """
        Initialize the local git repository.

        Either check out the repository from `repo_url` or create a local one.
        """
        self.init()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Handle local locker checkin and remote push if applicable.

        Log an exception if raised, commit the files to the repo and if
        configured push it up to the `repo_url`.
        """
        if exc_type:
            self.logger.error(' '.join([str(exc_type), str(exc_val)]))
        self.checkin()
        if self.repo_url_with_creds:
            self.push()
        return

    def _repo_init(self):
        if os.path.isdir(os.path.join(self.local_path, '.git')):
            self.repo = git.Repo(self.local_path)
        else:
            self.repo = git.Repo.init(self.local_path)
        self.init_config()

    def _get_partitioned_evidence_metadata(self, metadata, evidence_name):
        try:
            part, ev_name = evidence_name.split('_', 1)
            if part in metadata.get(ev_name, {}).get('partitions', {}).keys():
                return metadata[ev_name]
        except ValueError:
            return

    def _evidence_ttl_expired(self, evidence, last_update):
        expired = False
        last_update_ts = dt.strptime(last_update, '%Y-%m-%dT%H:%M:%S.%f')
        time_diff = dt.utcnow() - last_update_ts
        if time_diff.total_seconds() >= evidence.ttl - self.ttl_tolerance:
            expired = True
        return expired

    def _stale_message(self, message):
        self._handler.setFormatter(logging.Formatter('%(message)s'))
        self.logger.info(message)
        self._handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )

    def _evidence_abandoned(self, metadata=None, threshold=None):
        if metadata is None or metadata.get('last_update') is None:
            return True
        last_update = dt.strptime(
            metadata['last_update'], '%Y-%m-%dT%H:%M:%S.%f'
        )
        time_diff = dt.utcnow() - last_update
        if threshold is None:
            threshold = AE_DEFAULT
        threshold += metadata.get('ttl', 0)
        if time_diff.total_seconds() >= threshold:
            return True
        return False

    def _get_file_content(self, file_path, file_dt=None):
        if not file_dt:
            return open(os.path.join(self.local_path, file_path)).read()
        commit = self.get_latest_commit(file_path, file_dt)
        if not commit:
            raise HistoricalEvidenceNotFoundError(
                f'Evidence {file_path} was not found in the locker '
                f'for {file_dt.strftime("%Y-%m-%d")}'
            )
        return commit.tree[file_path].data_stream.read()

    def _validate_evidence(self, evidence, ignore_ttl):
        if evidence.path in self.forced_evidence:
            raise StaleEvidenceError(
                f'Evidence {evidence.path} is forced stale'
            )

        paths = []
        metadata = self.get_evidence_metadata(evidence.path) or {}
        if getattr(evidence, 'is_partitioned', False):
            for part_hash in metadata['partitions'].keys():
                paths.append(
                    os.path.join(
                        evidence.dir_path, f'{part_hash}_{evidence.name}'
                    )
                )
        else:
            paths.append(evidence.path)
        for path in paths:
            full_path = os.path.join(self.local_path, path)
            if not os.path.exists(full_path):
                raise ValueError(
                    f'Evidence {path} was not found in the locker'
                )
        ttl_expired = self._evidence_ttl_expired(
            evidence, metadata['last_update']
        )
        if not ignore_ttl and ttl_expired:
            raise StaleEvidenceError(f'Evidence {evidence.path} is stale')


def is_index_file(path):
    """Confirm whether the supplied path is to an index file."""
    return os.path.basename(path) == INDEX_FILE
