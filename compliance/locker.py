# Copyright (c) 2021, 2022 IBM Corp. All rights reserved.
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
import re
import shutil
import tempfile
import time
from datetime import datetime as dt, timedelta
from pathlib import Path, PurePath
from threading import Lock
from urllib.parse import urlparse

from compliance.agent import ComplianceAgent
from compliance.config import get_config
from compliance.evidence import CONTENT_FLAGS, TmpEvidence, get_evidence_class
from compliance.utils.data_parse import format_json, get_sha256_hash, parse_dot_key
from compliance.utils.exceptions import (
    EvidenceNotFoundError,
    HistoricalEvidenceNotFoundError,
    LockerPushError,
    StaleEvidenceError,
    UnverifiedEvidenceError,
)

import git

INDEX_FILE = "index.json"
DAY = 60 * 60 * 24
AE_DEFAULT = 30 * DAY
READMES = ["README.md", "readme.md", "Readme.md"]
AE_EXEMPT = [INDEX_FILE] + READMES
NOT_EVIDENCE = AE_EXEMPT
KB = 1000
MB = KB * 1000
LF_DEFAULT = 50 * MB


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
        branch=None,
        creds=None,
        do_push=False,
        ttl_tolerance=0,
        gitconfig=None,
        local_path=None,
        use_extra_lockers=True,
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
        :param local_path: a path to a local git repository.
        :param use_extra_lockers: get evidence from configured 'extra' lockers.
        """
        self.repo_url = repo_url
        self.repo_url_with_creds = self.repo_url
        self.creds = creds
        if self.creds is not None:
            service_hostname = urlparse(self.repo_url).hostname
            token = None
            if "github.com" in service_hostname:
                token = self.creds["github"].token
            elif "github" in service_hostname:
                token = self.creds["github_enterprise"].token
            elif "bitbucket" in service_hostname:
                token = self.creds["bitbucket"].token
            elif "gitlab" in service_hostname:
                token = self.creds["gitlab"].token
            if token:
                self.repo_url_with_creds = re.sub(
                    "://", f"://{token}@", self.repo_url_with_creds
                )
        self.default_branch = self.branch = get_config().get(
            "locker.default_branch", default="master"
        )
        if branch:
            self.branch = branch
        self._new_branch = False
        if name is not None:
            self.name = name
        elif repo_url is not None and name is None:
            self.name = repo_url.rsplit("/", 1)[1]
        elif repo_url is None and name is None:
            self.name = "example"
        if local_path:
            self.local_path = local_path
        else:
            self.local_path = str(PurePath(tempfile.gettempdir(), self.name))
        self._do_push = do_push
        self.ttl_tolerance = ttl_tolerance
        self.gitconfig = gitconfig or {}
        self.logger = logging.getLogger(name=f"compliance.locker.{self.name}")
        self._handler = logging.StreamHandler()
        self._handler.setFormatter(logging.Formatter("\n%(levelname)s: %(message)s"))
        self.logger.handlers.clear()
        self.logger.addHandler(self._handler)
        self.logger.setLevel(logging.INFO)
        self.commit_date = dt.utcnow().isoformat()
        self.forced_evidence = []
        self.dependency_rerun = []
        if use_extra_lockers:
            self._extra_lockers = self._get_extra_lockers()
        else:
            self._extra_lockers = []
        self._clone_depth = get_config().get("locker.depth")
        days = get_config().get("locker.shallow_days")
        self._clone_shallow_since_days = days

    @property
    def clone_depth(self):
        """
        Provide the commit depth used when cloning the repository.

        :returns: the clone depth.
        """
        return self._clone_depth

    @property
    def clone_shallow_since_days(self):
        """
        Provide the maximum commit age to fetch when cloning the repository.

        :returns: the shallow since days.
        """
        return self._clone_shallow_since_days

    @property
    def head_commit_hexsha(self):
        """
        Get SHA of repository head commit.

        :returns: 40 byte hexadecimal version of 20 byte binary SHA.
        """
        with self.lock:
            return self.repo.head.commit.hexsha

    @property
    def touched_files(self):
        """
        Provide paths to files that have been touched in the local locker.

        Files are considered "touched" if they have been added/updated in
        the locker.

        :returns: a list of touched files.
        """
        index_files = [
            f[0] for f in self.repo.index.entries.keys() if is_index_file(f[0])
        ]
        touched_files = []
        for f in index_files:
            content = json.loads(Path(self.local_path, f).read_text())
            for t, desc in content.items():
                if type(desc) is dict:
                    ts = desc.get("last_update")
                else:
                    ts = desc
                if ts == self.commit_date:
                    touched_files.append(str(PurePath(f).with_name(t)))
        return touched_files

    @clone_depth.setter
    def clone_depth(self, depth):
        self._clone_depth = depth

    @clone_shallow_since_days.setter
    def clone_shallow_since_days(self, days):
        self._clone_shallow_since_days = days

    def _get_extra_lockers(self):
        """Get extra locker configurations."""
        extra_lockers_cfg = get_config().get("locker.extra", [])
        prev_repo_url = get_config().get("locker.prev_repo_url")
        if prev_repo_url:
            extra_lockers_cfg.append({"repo_url": prev_repo_url})
        extra_lockers = []
        for extra_locker_cfg in extra_lockers_cfg:
            extra_locker = Locker(
                branch=extra_locker_cfg.get("branch"),
                creds=self.creds,
                local_path=extra_locker_cfg.get("local_path"),
                repo_url=extra_locker_cfg["repo_url"],
                use_extra_lockers=False,
            )
            extra_locker.clone_depth = extra_locker_cfg.get("depth")
            days = extra_locker_cfg.get("shallow_days")
            extra_locker.clone_shallow_since_days = days
            extra_locker.get_locker_repo(locker=extra_locker.name)
            extra_lockers.append(extra_locker)
        return extra_lockers

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
            f'{r["module"]}.{r["class"]}.{r["method"]}' for r in self.dependency_rerun
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
        gpgsign = self.gitconfig.get("commit", {}).get("gpgsign")
        if self._do_push and not gpgsign:
            self.logger.warning(
                "Commits may not be cryptographically signed, best "
                "practice is to set gitconfig.commit.gpgsign to true "
                "in your locker configuration."
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
            raise ValueError(f"Evidence {evidence.name} has no content")

        path = Path(self.local_path, evidence.dir_path)
        path.mkdir(parents=True, exist_ok=True)
        if getattr(evidence, "is_partitioned", False):
            for key in evidence.partition_keys:
                ev_name = f"{get_sha256_hash(key, 10)}_{evidence.name}"
                Path(path, ev_name).write_text(evidence.get_partition(key))
        elif not getattr(evidence, "binary_content", False):
            Path(path, evidence.name).write_text(evidence.content)
        else:
            Path(path, evidence.name).write_bytes(evidence.content)
        if not evidence.path.startswith("tmp/"):
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
            index_file = Path(self.get_index_file(evidence))
            repo_files = [str(index_file)]
            metadata = {}
            if index_file.is_file():
                metadata = json.loads(index_file.read_text())
            ev_meta = metadata.get(evidence.name, {})
            old_parts = ev_meta.get("partitions", {}).keys()
            metadata[evidence.name] = {
                "last_update": self.commit_date,
                "ttl": evidence.ttl,
                "description": evidence.description,
            }
            if evidence.signature:
                metadata[evidence.name].update(
                    {
                        "agent_name": evidence.agent.name,
                        "digest": evidence.digest,
                        "signature": evidence.signature,
                    }
                )
            if evidence.is_empty:
                metadata[evidence.name]["empty"] = True
            tombstones = None
            if getattr(evidence, "is_partitioned", False):
                unpartitioned = self.get_file(evidence.path)
                if Path(unpartitioned).is_file():
                    # Remove/tombstone unpartitioned evidence file
                    # replaced by partitioned evidence files
                    self.repo.index.remove([unpartitioned], working_tree=True)
                    tombstones = self.create_tombstone_metadata(
                        evidence.name, ev_meta, "Evidence is partitioned"
                    )
                parts = {}
                for key in evidence.partition_keys:
                    sha256_hash = get_sha256_hash(key, 10)
                    parts[sha256_hash] = key
                    repo_file = self.get_file(
                        f"{evidence.dir_path}/{sha256_hash}_{evidence.name}"
                    )
                    repo_files.append(repo_file)
                dead_parts = set(old_parts) - set(parts.keys())
                if dead_parts:
                    # Remove/tombstone partitioned evidence files
                    # no longer part of the evidence content
                    self.remove_partitions(evidence, dead_parts)
                    tombstones = self.create_tombstone_metadata(
                        dead_parts, ev_meta, "Partition no longer part of evidence"
                    )
                metadata[evidence.name].update(
                    {
                        "partition_fields": evidence.part_fields,
                        "partition_root": evidence.part_root,
                        "partitions": parts,
                    }
                )
                if tombstones is None:
                    # Preserve prior tombstones
                    tombstones = ev_meta.get("tombstones")
            else:
                # Remove/tombstone partitioned evidence files
                # replaced by unpartitioned evidence file
                self.remove_partitions(evidence, old_parts)
                tombstones = self.create_tombstone_metadata(
                    old_parts, ev_meta, "Evidence no longer partitioned"
                )
                repo_files.append(self.get_file(evidence.path))
            if tombstones:
                metadata[evidence.name]["tombstones"] = tombstones
            for content_flag in CONTENT_FLAGS:
                if getattr(evidence, content_flag, False):
                    metadata[evidence.name][content_flag] = True
            if checks is not None:
                metadata[evidence.name]["checks"] = checks
            if evidence_used is not None:
                metadata[evidence.name]["evidence"] = evidence_used
            index_file.write_text(format_json(metadata))
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
        path = PurePath(self.local_path, evidence.dir_path)
        ev_files = [str(path.joinpath(f"{h}_{evidence.name}")) for h in hashes]
        self.repo.index.remove(ev_files, working_tree=True)

    def create_tombstone_metadata(self, candidate, metadata, reason):
        """
        Create tombstones for evidence being removed from the locker.

        :param candidate: either the name of the evidence file or an iterable
          of partition hashes.
        :param metadata: the evidence metadata dictionary.
        :param reason: the reason evidence is being removed.

        :returns: a list of tombstones.
        """
        tombstones = metadata.get("tombstones", {})
        if isinstance(candidate, str):
            tombstones.setdefault(candidate, []).append(
                {
                    "eol": self.commit_date,
                    "last_update": metadata["last_update"],
                    "reason": reason,
                }
            )
        else:
            for part in candidate:
                tombstones.setdefault(part, []).append(
                    {
                        "eol": self.commit_date,
                        "last_update": metadata["last_update"],
                        "partition_fields": metadata["partition_fields"],
                        "partition_root": metadata["partition_root"],
                        "partition_key": metadata["partitions"][part],
                        "reason": reason,
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
            [f[0] for f in self.repo.index.entries.keys() if is_index_file(f[0])]
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
        path = PurePath(self.local_path, evidence_path).with_name(INDEX_FILE)
        return str(path)

    def get_file(self, filename):
        """
        Provide the path for a file in the locker.

        The file may or may not exist in the locker.

        :param filename: the name of a file in the locker.

        :returns: the path to the filename provided.
        """
        return str(PurePath(self.local_path, filename))

    def get_remote_location(
        self, filename, include_commit=True, sha=None, locker_url=None
    ):
        """
        Provide the path for a file/commit SHA in the locker.

        The file may or may not exist in the locker.

        :param filename: the name of a file in the locker.
        :param include_commit: if the latest commit SHA should be included.
        :param sha: use this commit SHA; requires include_commit to be False.
        :param locker_url: use this locker_url instead of self.repo_url.

        :returns: the remote repository path to the filename provided.
        """
        if not self.repo_url_with_creds:
            return self.get_file(filename)
        ref = self.branch
        if include_commit:
            ref = self.repo.head.commit.hexsha
        elif not include_commit and sha:
            ref = sha
        repo_url = locker_url or self.repo_url
        return f'{repo_url}/blob/{ref}/{filename.strip("/")}'

    def get_evidence(self, evidence_path, ignore_ttl=False, evidence_dt=None):
        """
        Provide the evidence from the locker.

        The evidence may or may not exist in the locker.  If the evidence is
        historical but not found in the immediate locker and a previous locker
        URL is provided in the configuration then an attempt to get the
        historical version of the evidence will be made from the previous
        locker.

        :param evidence_path: string path of the evidence within the locker.
          For example, `raw/service1/output.json`.
        :param ignore_ttl: boolean value to ignore evidence time to live.
          Defaults to False.
        :param evidence_dt: datetime of the evidence file version to retrieve.
          Defaults to None which translates to "now".

        :returns: the populated evidence object.
        """
        missing_errs = (EvidenceNotFoundError, HistoricalEvidenceNotFoundError)
        try:
            evidence = self._get_evidence(evidence_path, ignore_ttl, evidence_dt)
            evidence.locker = self
            return evidence
        except missing_errs as missing_err:
            for extra_locker in self._extra_lockers:
                try:
                    evidence = extra_locker._get_evidence(
                        evidence_path, ignore_ttl, evidence_dt
                    )
                    evidence.locker = extra_locker
                    return evidence
                except missing_errs:
                    continue
            raise missing_err

    def load_content(self, evidence, ignore_ttl=False, evidence_dt=None):
        """
        Populate the content of the evidence from the locker.

        :param evidence: an evidence object.
        :param ignore_ttl: Boolean for TTL validation.  Defaults to False.
        :param evidence_dt: The date of the evidence content to load.

        :returns: The evidence object with content.
        """
        self._validate_evidence(evidence, ignore_ttl)
        if getattr(evidence, "is_partitioned", False):
            metadata = self.get_evidence_metadata(evidence.path, evidence_dt)
            content = None
            for part_hash in metadata["partitions"].keys():
                data = json.loads(
                    self._get_file_content(
                        f"{evidence.dir_path}/{part_hash}_{evidence.name}", evidence_dt
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
            evidence.set_content(format_json(content), sign=False)
        else:
            evidence.set_content(
                self._get_file_content(
                    evidence.path,
                    evidence_dt,
                    getattr(evidence, "binary_content", False),
                ),
                sign=False,
            )
        ign_sig = get_config().get("locker.ignore_signatures", default=False)
        if not ign_sig and evidence.is_signed(self):
            if not evidence.verify_signature(self):
                raise UnverifiedEvidenceError(
                    f"Evidence {evidence.path} is signed but the signature "
                    "could not be verified.",
                    evidence,
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
            return Path(self.local_path, evidence.path).is_file()
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
        self.get_locker_repo()
        self.init_config()

    def get_locker_repo(self, locker="evidence locker"):
        """
        Pull (clone) the remote repository to the local git repository.

        :param locker: the locker "name" used in logging
        """
        if Path(self.local_path, ".git").is_dir():
            self.logger.info(f"Using {locker} found in {self.local_path}...")
            if not hasattr(self, "repo"):
                self.repo = git.Repo(self.local_path)
        else:
            self.logger.info(
                f"Cloning {locker} {self.repo_url} to {self.local_path}..."
            )
            kwargs = {"branch": self.default_branch}
            addl_msg = None
            if self.clone_depth:
                kwargs["depth"] = self.clone_depth
            if self.clone_shallow_since_days:
                days = self.clone_shallow_since_days + 1
                since_dt = dt.utcnow() - timedelta(days=days)
                since = since_dt.strftime("%Y/%m/%d")
                kwargs["shallow_since"] = since
                addl_msg = f"{locker.title()} contains commits since {since}"
            start = time.perf_counter()
            self.repo = git.Repo.clone_from(
                self.repo_url_with_creds, self.local_path, single_branch=True, **kwargs
            )
            duration = time.perf_counter() - start
            self.logger.info(f"{locker.title()} cloned in {duration:.3f}s")
            if addl_msg:
                self.logger.info(addl_msg)
        self._checkout_branch()

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
            updated_files = "\n".join(self.touched_files)
            message = (
                f"Files updated at local time {time.ctime(time.time())}"
                f"\n\n{updated_files}"
            )
        self.logger.info(f"Committing changes to local locker in {self.local_path}...")
        try:
            diff = self.repo.index.diff("HEAD")
            if len(diff) > 0:
                self.repo.git.commit(message=message)
        except git.BadName:
            self.repo.git.commit(message=message)

    def push(self):
        """Push the local git repository to the remote repository."""
        if self._do_push:
            remote = self.repo.remote()
            self.logger.info(
                f"Syncing local locker with remote repo {self.repo_url}..."
            )
            remote.fetch()
            if not self._new_branch:
                remote.pull(rebase=True)
            self._log_large_files()
            self.logger.info(f"Pushing local locker to remote repo {self.repo_url}...")
            push_info = remote.push(
                self.branch,
                force=get_config().get("locker.force_push", default=False),
                set_upstream=True,
            )[0]
            if push_info.flags >= git.remote.PushInfo.ERROR:
                raise LockerPushError(push_info)

    def add_content_to_locker(self, content, folder="", filename=None):
        """
        Add non-evidence text content to the local locker.

        :param content: the content to add to the local locker.
        :param folder: the folder in the local locker to add the content to.
        :param filename: the name of the file in the local locker.
        """
        if not filename:
            raise ValueError("You must provide a filename.")
        path = Path(self.local_path, folder)
        path.mkdir(parents=True, exist_ok=True)
        results_file = Path(path, filename)
        results_file.write_text(content)
        self.repo.index.add([str(results_file)])

    def get_content_from_locker(self, folder="", filename=None):
        """
        Read non-evidence text content from the local locker.

        :param folder: the folder in the local locker to get the content from.
        :param filename: the name of the file in the local locker.
        """
        if not filename:
            raise ValueError("You must provide a filename.")
        file_path = Path(self.local_path, folder, filename)
        content = None
        if file_path.is_file():
            content = file_path.read_text()
        return content

    def get_reports_metadata(self):
        """
        Provide all metadata related to reports as a dictionary.

        :returns: reports metadata.
        """
        metadata = {}
        for idx in Path(self.local_path, "reports").rglob(INDEX_FILE):
            for rpt_name, rpt_metadata in json.loads(idx.read_text()).items():
                rpt_path = idx.relative_to(self.local_path).with_name(rpt_name)
                metadata[str(rpt_path)] = rpt_metadata
        return metadata

    def get_abandoned_evidences(self, threshold=None):
        """
        Provide a set of evidence where the update ``threshold`` has passed.

        :param int threshold: the time in seconds after TTL expires that
          evidence can remain un-updated before it is considered abandoned.
          The abandoned evidence threshold defaults to 30 days if none is
          provided.

        :returns: a set of abandoned evidence file relative paths.
        """
        abandoned_evidence = set()
        for f in self._get_git_files("evidence"):
            metadata = self.get_evidence_metadata(f.path, dt.utcnow())
            if self._evidence_abandoned(metadata, threshold):
                abandoned_evidence.add(f.path)
        return abandoned_evidence

    def get_empty_evidences(self):
        """
        Provide a list of evidence paths to empty evidence files.

        Evidence content is considered empty based on an evidence object's
        is_empty property.  This information is stored in evidence metadata.

        :returns: a list of empty evidence file relative paths.
        """
        empty_evidence = []
        for f in self._get_git_files("index"):
            for ev_name, ev_meta in json.loads(f.data_stream.read()).items():
                if ev_meta.get("empty", False):
                    empty_evidence.append(str(PurePath(f.path).with_name(ev_name)))
        return empty_evidence

    def get_large_files(self, size=LF_DEFAULT):
        """
        Provide a dictionary of "large" evidence locker files.

        A "large" file is one whose size is > the ``size`` argument provided.

        :param int size: file size threshold.

        :returns: a dictionary of file paths and sizes of "large" files.
        """
        return {f.path: f.size for f in self._get_git_files() if f.size > size}

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
        options = {"max_count": 1}
        if dt:
            options["until"] = dt.strftime("%Y-%m-%d")
        try:
            with self.lock:
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
        pkg_index_path = Path(self.get_index_file_by_path(evidence_path))
        if not pkg_index_path.is_file():
            return
        ev_path, ev_name = evidence_path.rsplit("/", 1)
        if evidence_dt:
            pkg_index_path = str(PurePath(ev_path, INDEX_FILE))
            commit = self.get_latest_commit(pkg_index_path, evidence_dt)
            if not commit:
                return
            metadata = json.loads(commit.tree[pkg_index_path].data_stream.read())
        else:
            metadata = json.loads(pkg_index_path.read_text())
        return metadata.get(
            ev_name, self._get_partitioned_evidence_metadata(metadata, ev_name)
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
        Handle local locker check-in and remote push if applicable.

        Log an exception if raised, commit the files to the repo and if
        configured push it up to the `repo_url`.
        """
        if exc_type:
            self.logger.error(" ".join([str(exc_type), str(exc_val)]))
        self.checkin()
        if self.repo_url_with_creds:
            self.push()
        return

    def _repo_init(self):
        if Path(self.local_path, ".git").is_dir():
            self.logger.info(f"Using locker found in {self.local_path}...")
            self.repo = git.Repo(self.local_path)
        else:
            self.logger.info(f"Creating locker in {self.local_path}...")
            self.repo = git.Repo.init(self.local_path)
        self._checkout_branch()
        self.init_config()

    def _checkout_branch(self):
        if self.repo.active_branch.name == self.branch:
            return
        try:
            self.repo.git.checkout(self.branch)
        except git.exc.GitCommandError:
            self._new_branch = True
            self.repo.git.checkout("-b", self.branch)

    def _get_evidence(self, evidence_path, ignore_ttl=False, evidence_dt=None):
        agent = None
        evidence = None
        try:
            metadata = self.get_evidence_metadata(evidence_path, evidence_dt)
            if metadata and metadata.get("agent_name"):
                agent = ComplianceAgent(
                    name=metadata.get("agent_name"),
                    use_agent_dir=evidence_path.startswith(ComplianceAgent.AGENTS_DIR),
                )
            class_type, category, evidence_name = evidence_path.split("/")[-3:]
            evidence_class_obj = get_evidence_class(class_type)
            evidence = evidence_class_obj(
                evidence_name,
                category,
                metadata["ttl"],
                metadata["description"],
                partition={
                    "fields": metadata.get("partition_fields"),
                    "root": metadata.get("partition_root"),
                },
                binary_content=metadata.get("binary_content", False),
                filtered_content=metadata.get("filtered_content", False),
                agent=agent,
                evidence_dt=evidence_dt,
            )
        except TypeError:
            ev_dt_str = (evidence_dt or dt.utcnow()).strftime("%Y-%m-%d")
            raise EvidenceNotFoundError(
                f"Evidence {evidence_path} is not found in the locker "
                f"for {ev_dt_str}. It may not be a valid evidence path."
            )
        return self.load_content(evidence, ignore_ttl, evidence_dt)

    def _get_partitioned_evidence_metadata(self, metadata, evidence_name):
        try:
            part, ev_name = evidence_name.split("_", 1)
            if part in metadata.get(ev_name, {}).get("partitions", {}).keys():
                return metadata[ev_name]
        except ValueError:
            return

    def _evidence_ttl_expired(self, evidence, last_update):
        expired = False
        last_update_ts = dt.strptime(last_update, "%Y-%m-%dT%H:%M:%S.%f")
        time_diff = dt.utcnow() - last_update_ts
        if time_diff.total_seconds() >= evidence.ttl - self.ttl_tolerance:
            expired = True
        return expired

    def _stale_message(self, message):
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.info(message)
        self._handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    def _evidence_abandoned(self, metadata=None, threshold=None):
        if metadata is None or metadata.get("last_update") is None:
            return True
        last_update = dt.strptime(metadata["last_update"], "%Y-%m-%dT%H:%M:%S.%f")
        time_diff = dt.utcnow() - last_update
        if threshold is None:
            threshold = AE_DEFAULT
        threshold += metadata.get("ttl", 0)
        if time_diff.total_seconds() >= threshold:
            return True
        return False

    def _get_file_content(self, file_path, file_dt=None, binary_content=False):
        if not file_dt:
            p = Path(self.local_path, file_path)
            return p.read_text() if not binary_content else p.read_bytes()
        commit = self.get_latest_commit(file_path, file_dt)
        if not commit:
            raise HistoricalEvidenceNotFoundError(
                f"Evidence {file_path} was not found in the locker "
                f'for {file_dt.strftime("%Y-%m-%d")}'
            )
        return commit.tree[file_path].data_stream.read()

    def _validate_evidence(self, evidence, ignore_ttl):
        if evidence.path in self.forced_evidence:
            raise StaleEvidenceError(f"Evidence {evidence.path} is forced stale")

        paths = []
        metadata = self.get_evidence_metadata(evidence.path) or {}
        if getattr(evidence, "is_partitioned", False):
            for part_hash in metadata["partitions"].keys():
                paths.append(
                    PurePath(evidence.dir_path, f"{part_hash}_{evidence.name}")
                )
        else:
            paths.append(PurePath(evidence.path))
        for path in paths:
            if not Path(self.local_path, path).is_file():
                raise ValueError(f"Evidence {path} was not found in the locker")
        ttl_expired = self._evidence_ttl_expired(evidence, metadata["last_update"])
        if not ignore_ttl and ttl_expired:
            raise StaleEvidenceError(f"Evidence {evidence.path} is stale")

    def _get_git_files(self, file_type="all"):
        iz = {
            "all": lambda g: g.type == "blob",
            "evidence": is_evidence_file,
            "index": is_index_file,
        }
        return filter(iz[file_type], self.repo.head.commit.tree.traverse())

    def _log_large_files(self):
        large_files = self.get_large_files(
            get_config().get("locker.large_file_threshold", LF_DEFAULT)
        )
        if large_files:
            msg = ["LARGE FILES (Hosting service may reject due to size):\n"]
            for fpath, size in large_files.items():
                formatted_size = f"{size/MB:.1f} MB"
                if formatted_size == "0.0 MB":
                    formatted_size = f"{str(size)} Bytes"
                msg.append(f"      {fpath} is {formatted_size}")
            self.logger.info("\n".join(msg) + "\n")


def is_evidence_file(git_obj):
    """
    Confirm whether the supplied git object is an evidence file.

    :param git_obj: A GitPython object

    :returns: True or False (Object is or isn't an evidence file)
    """
    return (
        git_obj.type == "blob"
        and not git_obj.path.startswith("notifications/")
        and git_obj.path != "check_results.json"
        and PurePath(git_obj.path).name not in NOT_EVIDENCE
    )


def is_index_file(obj):
    """
    Confirm whether the supplied object is, or points to, an index file.

    :param obj: Either a GitPython object or a relative file path as a string

    :returns: True or False (Object is or isn't an index file)
    """
    if isinstance(obj, str):
        return PurePath(obj).name == INDEX_FILE
    return obj.type == "blob" and PurePath(obj.path).name == INDEX_FILE
