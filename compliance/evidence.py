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
"""Compliance evidence management automation module."""

import inspect
import json
from collections import namedtuple
from functools import wraps
from pathlib import PurePath

from compliance.agent import ComplianceAgent
from compliance.check import ComplianceCheck
from compliance.config import get_config
from compliance.utils.data_parse import format_json, parse_dot_key
from compliance.utils.exceptions import (
    DependencyFetcherNotFoundError,
    DependencyUnavailableError,
    EvidenceNotFoundError,
    StaleEvidenceError,
    UnverifiedEvidenceError,
)
from compliance.utils.path import FETCH_PREFIX, substitute_config

HOUR = 60 * 60
DAY = HOUR * 24
YEAR = DAY * 365

CONTENT_FLAGS = ["binary_content", "filtered_content"]

LazyLoader = namedtuple("LazyLoader", "path ev_class")


class _BaseEvidence(object):
    """
    The evidence base class.

    :param name: the name of the evidence (e.g. 'users.csv', or
      '{org[name]}-backups.json'). Note that this parameter can be a string
      template where config values can be used.
    :param category: the category or service where this category will be
      classified (e.g. 'dbs', 'github', etc.). This is useful for grouping
      evidence that are considered of the same type or that belong to a
      specific type of source.
    :param ttl: the time (in seconds) after which the evidence will be
      considered as stale/invalid.
    :param description: a string containing a longer description about
      the evidence.
    :param agent: an agent of type :class:`compliance.agent.ComplianceAgent`.
      Defaults to `None`.
    :param evidence_dt: datetime of the evidence file version to retrieve.
      Defaults to `None` (which translates to "now").
    """

    EVIDENCE_TYPE = "base"

    def __init__(self, name, category, ttl=DAY, description="", **kwargs):
        self._name = name
        self.category = category
        self.ttl = ttl
        self.description = description
        self.locker = None
        self._agent = kwargs.get("agent") or ComplianceAgent()
        if self._agent.name and self.description:
            self.description = f"{self._agent.name}: {self.description}"
        self._config = get_config()
        self._content = None
        self._content_raw = None
        self._digest = None
        self._evidence_dt = kwargs.get("evidence_dt")
        self._raw_content = None
        self._signature = None
        self.binary_content = kwargs.get("binary_content", False)
        self.filtered_content = kwargs.get("filtered_content", False)

    @classmethod
    def from_evidence(cls, evidence):
        kwargs = {}
        for content_flag in CONTENT_FLAGS:
            if hasattr(evidence, content_flag):
                kwargs[content_flag] = getattr(evidence, content_flag)
        if hasattr(evidence, "part_fields") or hasattr(evidence, "part_root"):
            kwargs["partition"] = {
                "fields": getattr(evidence, "part_fields", None),
                "root": getattr(evidence, "part_root", None),
            }
        new_evidence = cls(
            evidence.name,
            evidence.category,
            evidence.ttl,
            evidence.description,
            agent=evidence.agent,
            **kwargs,
        )
        new_evidence.locker = evidence.locker
        new_evidence.set_digest(evidence.digest)
        new_evidence.set_signature(evidence.signature)
        new_evidence.set_content(evidence.content, sign=evidence.signature is None)
        return new_evidence

    @classmethod
    def lazy_load(cls, path):
        return LazyLoader(path, cls)

    @classmethod
    def from_locker(cls, path, locker):
        path = substitute_config(path)
        return cls(locker.get_evidence(path))

    @property
    def rootdir(self):
        return self.agent.get_path(self.EVIDENCE_TYPE)

    @property
    def dir_path(self):
        return str(PurePath(self.rootdir, self.category))

    @property
    def name(self):
        return substitute_config(self._name)

    @property
    def path(self):
        return str(PurePath(self.dir_path, self.name))

    @property
    def extension(self):
        return PurePath(self.name).suffix.lstrip(".")

    @property
    def agent(self):
        return self._agent

    @property
    def content(self):
        return self._content

    @property
    def clear_sign(self):
        retval = []
        if self._agent and self._agent.name:
            retval.append("-----BEGIN AGENT-----")
            retval.append(self._agent.name)
            retval.append("-----END AGENT-----")
        if self._content:
            retval.append("-----BEGIN CONTENT-----")
            retval.append(self._content)
            retval.append("-----END CONTENT-----")
        if self._digest:
            retval.append("-----BEGIN DIGEST-----")
            retval.append(self._digest)
            retval.append("-----END DIGEST-----")
        if self._signature:
            retval.append("-----BEGIN SIGNATURE-----")
            retval.append(self._signature)
            retval.append("-----END SIGNATURE-----")
        return "\n".join(retval)

    @property
    def content_as_json(self):
        if self.extension != "json":
            raise ValueError(f"{self.name} does not have JSON content.")
        if not hasattr(self, "_content_as_json"):
            self._content_as_json = json.loads(self.content)
        return self._content_as_json

    @property
    def is_empty(self):
        return (
            not self.content
            or not self.content.strip()
            or (
                self.extension == "json"
                and self.content_as_json != 0
                and not self.content_as_json
            )
        )

    @property
    def digest(self):
        return self._digest

    @property
    def signature(self):
        return self._signature

    def is_signed(self, locker):
        """
        Check if the evidence has been signed.

        :param locker: The evidence locker.

        :returns: `True` if the evidence is signed, else `False`.
        """
        metadata = locker.get_evidence_metadata(self.path)
        self._digest = metadata.get("digest")
        self._signature = metadata.get("signature")
        return self._signature is not None

    def set_agent(self, agent):
        """
        Set the evidence agent.

        :param agent: Agent of type :class:`compliance.agent.ComplianceAgent`.
        """
        self._agent = agent

    def set_content(self, content, sign=True):
        """
        Set the evidence content.

        :param content: The content as a string or `None`.
        :param sign: Sign the evidence content (if not already signed).
        """
        self._content = content
        if self._content is None:
            return  # Don't sign `None` evidence.
        if self.extension == "json":
            self._content = format_json(json.loads(content))
        if sign:
            if self.binary_content:
                data_bytes = self._content
            else:
                data_bytes = self._content.encode()
            self._digest, self._signature = self.agent.hash_and_sign(data_bytes)

    def set_digest(self, digest):
        """
        Set the evidence digest.

        :param digest: The evidence digest as a string or `None`.
        """
        self._digest = digest

    def set_signature(self, signature):
        """
        Set the evidence signature.

        :param signature: The evidence signature as a string or `None`.
        """
        self._signature = signature

    def verify_signature(self, locker):
        """
        Verify the evidence content.

        :param locker: The evidence locker.

        :returns: `True` for verified evidence, else `False`.
        """
        if self._content is None:
            return True  # Verify `None` evidence.
        if self.path == self.agent.PUBLIC_KEYS_EVIDENCE_PATH:
            # The public keys evidence should be signed with the private key
            # specified in the configuration.
            self._agent = ComplianceAgent.from_config()
        else:
            self.agent.load_public_key_from_locker(locker)
        signature = locker.get_evidence_metadata(
            self.path, evidence_dt=self._evidence_dt
        ).get("signature")
        if not signature:
            raise UnverifiedEvidenceError(f"Evidence {self.path} is not signed.", self)
        return self.agent.verify(self.content.encode(), signature)


class RawEvidence(_BaseEvidence):
    """
    The raw evidence class.

    Raw evidence is partition-able if the content is JSON and by providing a
    list of partition fields along with an optional partition root.  The
    evidence partitioning can be defined in configuration JSON or directly upon
    construction of a RawEvidence object.  The constructor route overrides the
    configuration settings, if both are provided.
    """

    EVIDENCE_TYPE = "raw"

    def __init__(self, *args, **kwargs):
        """Construct and initialize the raw evidence object."""
        super().__init__(*args, **kwargs)
        lp_config = self._config.get("locker.partitions", {})
        partition = kwargs.get(
            "partition", lp_config.get(f"{self.category}/{self.name}", {})
        )
        self.part_fields = partition.get("fields")
        self.part_root = partition.get("root")

    @property
    def is_partitioned(self):
        """Raw evidence partitioned status."""
        return self.part_fields is not None and self.extension == "json"

    @property
    def partition_keys(self):
        """
        All partition keys for this evidence object.

        Return all key values based on evidence content and the
        key fields provided during evidence instantiation.  Key values are
        relative to the root partition provided during evidence instantiation.

        :returns: A list of key values where the key values are lists as well.
        """
        if getattr(self, "_partition_keys", None) is None:
            keys = set()
            if self.part_root:
                root = parse_dot_key(json.loads(self._content), self.part_root)
            else:
                root = json.loads(self._content)
            for data in root:
                key_values = []
                for field in self.part_fields:
                    key_value = data
                    key_values.append(parse_dot_key(key_value, field))
                keys.add(tuple(key_values))
            self._partition_keys = [list(k) for k in keys]
        return self._partition_keys

    def get_partition(self, key):
        """
        Provide a slice of content based on the supplied partition key.

        Return a JSON document that is a slice of the original evidence
        content based on the list of key values provided.  Key values are
        expected to match the key fields provided during evidence
        instantiation and are relative to the root partition provided during
        evidence instantiation.

        :param key: A list of key values to partition by

        :returns: A JSON document filtered by the key values provided
        """
        data = json.loads(self._content)
        if not self.part_root:
            data = self._partition(data, key)
        else:
            part = data
            root = self.part_root.split(".")
            for field in root[:-1]:
                part = part[field]
            part[root[-1]] = self._partition(part[root[-1]], key)
        return format_json(data)

    def _partition(self, data, key):
        for idx, field in enumerate(self.part_fields):
            data = [d for d in data if parse_dot_key(d, field) == key[idx]]
        return data


class DerivedEvidence(_BaseEvidence):
    """The derived evidence class."""

    EVIDENCE_TYPE = "derived"


class ReportEvidence(_BaseEvidence):
    """The report evidence class."""

    EVIDENCE_TYPE = "reports"


class TmpEvidence(_BaseEvidence):
    """The temporary evidence class."""

    EVIDENCE_TYPE = "tmp"


class ExternalEvidence(_BaseEvidence):
    """The external evidence class."""

    EVIDENCE_TYPE = "external"

    def __init__(self, name, category, ttl=YEAR, description="", **kwargs):
        """Construct and initialize the external evidence object."""
        super().__init__(name, category, ttl, description, **kwargs)


class _EvidenceContextManager(object):
    """Base class for raw and temporary evidence context managers."""

    def __init__(self, locker, evidence_path, evidence_type):
        self.locker = locker
        self.evidence_path = evidence_path
        self.evidence_type = evidence_type

    def __enter__(self):
        path = self.evidence_path
        if not path.startswith(f"{self.evidence_type}/"):
            path = f"{self.evidence_type}/{path}"
        self.evidence = get_evidence_by_path(path)
        if self.locker.validate(self.evidence):
            self.evidence = None
        return self.evidence

    def __exit__(self, typ, val, traceback):
        if self.evidence and traceback is None:
            self.locker.add_evidence(self.evidence)


class raw_evidence(_EvidenceContextManager):  # noqa: N801
    """
    Helper context manager for a typical ``fetch_`` method implementation.

    Use when retrieving raw evidence by a fetcher and the name of the evidence
    is dynamic.  When the evidence name is static/known use the
    @store_raw_evidence decorator instead.

    If TTL has expired, the context manager yields the evidence object
    specified by the ``evidence_path``.  The context manager expects the
    evidence content to be retrieved and set via ``set_content`` by the calling
    ``with`` block.

    If TTL has not expired, the context manager yields ``None`` and expects the
    calling ``with`` block to exit gracefully immediately.
    """

    def __init__(self, locker, evidence_path):
        """
        Construct and initialize the raw evidence context manager.

        :param locker: The evidence locker object
        :param evidence_path: The path to the raw evidence within the evidence
          locker.  For example, ``src/my_raw_evidence.json``.
        """
        super().__init__(locker, evidence_path, "raw")


class tmp_evidence(_EvidenceContextManager):  # noqa: N801
    """
    Helper context manager for a typical ``fetch_`` method implementation.

    Use when retrieving temporary evidence by a fetcher and the name of the
    evidence is dynamic.  When the evidence name is static/known use the
    @store_tmp_evidence decorator instead.

    If the evidence is not present, the context manager yields the evidence
    object specified by the ``evidence_path``.  The context manager expects the
    evidence content to be retrieved and set via ``set_content`` by the calling
    ``with`` block.

    If the evidence is present, the context manager yields ``None`` and expects
    the calling ``with`` block to exit gracefully immediately.
    """

    def __init__(self, locker, evidence_path):
        """
        Construct and initialize the temporary evidence context manager.

        :param locker: The evidence locker object
        :param evidence_path: The path to the raw evidence within the evidence
          locker.  For example, ``src/my_tmp_evidence.json``.
        """
        super().__init__(locker, evidence_path, "tmp")


class derived_evidence(object):  # noqa: N801
    """
    Helper context manager for a typical ``fetch_`` method implementation.

    Use when retrieving derived evidence by a fetcher and the name of the
    evidence is dynamic.  When the evidence name is static/known use the
    @store_derived_evidence decorator instead.

    If TTL has expired on the derived evidence, the context manager yields a
    dictionary containing all of the source evidences as well as the derived
    evidence objects specified in the ``sources`` and ``target`` arguments.

    If TTL has not expired on the derived evidence, the context manager yields
    ``None`` and expects the calling ``with`` block to exit gracefully
    immediately.

    Inside the ``with`` block:

    If ``sources`` are provided as a list then the source evidence is
    accessible through the source path as the key for the yielded dictionary of
    evidence.

    If ``sources`` are provided as a dictionary where evidence short names are
    keys and evidence source paths are the values then the evidence is
    accessible through the evidence short name as the key for the yielded
    dictionary of evidence.

    If a single evidence source path is provided as a string then the source
    evidence is accessible by using 'source' as the key for the yielded
    dictionary of evidence.

    The derived evidence object is always accessible by using 'derived' as the
    key for the yielded dictionary of evidence.

    The context manager expects the derived evidence content to be generated
    and set via ``set_content`` by the calling ``with`` block.
    """

    def __init__(self, locker, sources, target):
        """
        Construct and initialize the derived evidence context manager.

        :param locker: The evidence locker object
        :param sources: The paths to the evidences within the evidence
          locker that will make up the derived evidence.  This can be a list,
          a dict or a string.
          For (list) example, ``['src/evidence.json', ...]``.
          For (dict) example, ``{'evidence1': 'src/evidence.json', ...}.
          For (str) example, ``'src/evidence.json'``.
        :param target: The path to the derived evidence within the evidence
          locker.  For example, ``src/my_derived_evidence.json``.
        """
        self.locker = locker
        self.sources = sources
        self.target = target
        self.evidences = None

    def __enter__(self):
        """Perform fetcher derived evidence pre-processing."""
        target_path = self.target
        if not target_path.startswith("derived/"):
            target_path = f"derived/{target_path}"
        target_evidence = get_evidence_by_path(target_path)
        if self.locker.validate(target_evidence):
            return
        self.evidences = {"derived": target_evidence}
        if isinstance(self.sources, list):
            for src in self.sources:
                self.evidences[src] = get_evidence_by_path(src, self.locker)
        elif isinstance(self.sources, dict):
            for src_name, src_path in self.sources.items():
                self.evidences[src_name] = get_evidence_by_path(src_path, self.locker)
        elif isinstance(self.sources, str):
            self.evidences["source"] = get_evidence_by_path(self.sources, self.locker)
        else:
            self.evidences = None
        return self.evidences

    def __exit__(self, typ, val, traceback):
        """Perform fetcher derived evidence post-processing."""
        if self.evidences and traceback is None:
            self.locker.add_evidence(self.evidences["derived"])


class evidences(object):  # noqa: N801
    """
    Helper context manager for a typical ``test_`` method implementation.

    Use when processing evidence by a check and the name(s) of the
    evidence is/are dynamic.  When the evidence names are static/known use the
    @with_*_evidences decorators instead.

    Inside the ``with`` block:

    If ``evidence_paths`` are provided as a list then the evidence is
    accessible through the evidence path as the key for the yielded dictionary
    of evidence.

    If ``evidence_paths`` are provided as a dictionary where evidence short
    names are keys and evidence paths are the values then the evidence is
    accessible through the evidence short name as the key for the yielded
    dictionary of evidence.

    If a single evidence path is provided as a string then the evidence object
    is yielded by this context manager.
    """

    def __init__(self, obj, from_evidences):
        """
        Construct and initialize the evidences context manager.

        :param obj: Either a check or locker object.  Needed for backward
          compatibility of evidences context manager.
        :param from_evidences: The paths to evidences within the evidence
          locker.  It can be any of the following:
          - A string path
          - A LazyLoader namedtuple
          - A list of string paths or LazyLoader namedtuples or a
          combination of string paths and LazyLoader namedtuples
          - A dictionary where a key is an evidence short name and a value
          is either string path or a LazyLoader namedtuple

          Using the LazyLoader namedtuple tells this context manager to cast
          your evidence as a subclass of one of the framework's base evidence
          classes.
        """
        if isinstance(obj, ComplianceCheck):
            self.check = obj
            self.locker = self.check.locker
        else:
            self.locker = obj
        self.from_evidences = from_evidences

    def __enter__(self):
        """Perform check evidences pre-processing."""
        evidence = {}
        rtval_dict = True
        if isinstance(self.from_evidences, list):
            for from_evidence in self.from_evidences:
                path = from_evidence
                if isinstance(from_evidence, LazyLoader):
                    # preserve original path to be used as key of evidence dict
                    path = from_evidence.path
                evidence[path] = self._get_evidence(from_evidence)
        elif isinstance(self.from_evidences, dict):
            for evidence_name, from_evidence in self.from_evidences.items():
                evidence[evidence_name] = self._get_evidence(from_evidence)
        else:
            rtval_dict = False
            evidence["evidence"] = self._get_evidence(self.from_evidences)
        if not evidence:
            raise EvidenceNotFoundError("No evidence found!")
        if hasattr(self, "check"):
            for ev in evidence.values():
                self.check.add_evidence_metadata(ev.path, evidence_locker=ev.locker)
        if rtval_dict:
            return evidence
        return next(iter(evidence.values()))

    def __exit__(self, typ, val, traceback):
        """Perform check evidences post-processing."""
        pass

    def _get_evidence(self, from_evidence):
        """
        Retrieve an evidence instance based on the from_evidence provided.

        from_evidence can be either a path to the evidence in the locker as a
        string or a LazyLoader namedtuple object that contains the path as a
        string and an evidence class to cast the evidence as.
        """
        path = from_evidence
        ev_class = None
        if isinstance(from_evidence, LazyLoader):
            path = from_evidence.path
            ev_class = from_evidence.ev_class
            ev_types = get_evidence_types()
            if not any(PurePath(path).parts[0] == et for et in ev_types):
                for ev_type in ev_types:
                    base_evidence_class = get_evidence_class(ev_type)
                    if ev_class and issubclass(ev_class, base_evidence_class):
                        path = str(PurePath(ev_type, path))
                        break
        evidence = get_evidence_by_path(path, self.locker)
        if evidence.__class__ not in get_evidence_base_classes():
            # Evidence returned from cache already cast
            ev_class = evidence.__class__
        base_evidence_class = get_evidence_class(evidence.EVIDENCE_TYPE)
        if not ev_class or not issubclass(ev_class, base_evidence_class):
            ev_class = base_evidence_class
        return ev_class.from_evidence(evidence)


__init_map = {
    evidence.EVIDENCE_TYPE: evidence
    for evidence in [
        DerivedEvidence,
        ExternalEvidence,
        RawEvidence,
        ReportEvidence,
        TmpEvidence,
    ]
}


def get_evidence_class(evidence_type):
    """
    Provide the appropriate evidence class based on the supplied type.

    Returns the corresponding evidence class object based on the category
    provided.  If no match ``None`` is returned.

    :param evidence_type: the type of evidence class desired as a string. Valid
      values are ``tmp``, ``reports``, ``derived``, ``raw``, ``external``.

    :returns: the appropriate evidence class.
    """
    return __init_map.get(evidence_type)


def get_evidence_types():
    """Provide a list of all valid evidence types."""
    return list(__init_map.keys())


def get_evidence_base_classes():
    """Provide a list of all valid base evidence class objects."""
    return list(__init_map.values())


def get_evidence_by_path(path, locker=None):
    """
    Provide an evidence object specified by the given path.

    The following strategy is used:

      * Return evidence if it is present in the evidence cache populating
        content if necessary and possible.
      * If evidence is not in the evidence cache but a locker is provided, then
        the evidence will be retrieved from the locker.
      * Otherwise, an evidence object is built with the default parameters.

    :param path: relative path to the evidence within the Locker. For example,
      ``raw/source1/evidence.json``.

    :returns: the evidence object.
    """
    path = substitute_config(path)
    evidence = get_config().get_evidence(path)

    try:
        split = path.strip("/").split("/")
        evidence_type, category, name = split[-3:]
    except ValueError:
        raise ValueError(f'Invalid evidence path format "{path}"')

    if split[0] == ComplianceAgent.AGENTS_DIR:
        agent = ComplianceAgent(name=split[1])
    else:
        agent = ComplianceAgent.from_config()
        path = agent.get_path(path)
    if evidence:
        evidence.set_agent(agent)
        if locker and evidence.content is None:
            evidence = locker.load_content(evidence)
        return evidence

    if evidence_type not in __init_map:
        raise ValueError(f"Unable to create evidence of type {evidence_type}")
    if locker:
        try:
            evidence = locker.get_evidence(path)
            get_config().add_evidences([evidence])
            return evidence
        except ValueError:
            pass
    return __init_map[evidence_type](name, category, agent=agent)


def get_evidence_dependency(path, locker, fetcher=None):
    """
    Provide evidence to fetchers that depend on that other evidence to fetch.

    Use when a fetcher needs evidence fetched by another fetcher in order to
    complete its fetch process.  The premise is that if the evidence is in the
    evidence cache then return that because it was placed there by another
    fetcher.  If not then get the evidence directly from the locker without
    putting that evidence into the evidence cache.  When an evidence dependency
    is not found the fetcher is queued up as a dependency rerun for subsequent
    processing.

    :param path: relative path to the evidence within the Locker. For example,
      ``raw/source1/evidence.json``.
    :param locker: evidence Locker object.
    :param fetcher: optional Python notation path to fetcher method.  If
      provided, this defines the fetcher that is added to the re-run list.
      Otherwise the execution stack is traversed to find the fetcher caller.

    :returns: the evidence object.
    """
    path = substitute_config(path)
    evidence = get_config().get_evidence(path)
    if evidence is None or evidence.content is None:
        try:
            evidence = locker.get_evidence(path)
        except (StaleEvidenceError, EvidenceNotFoundError):
            rerun = None
            if fetcher:
                module, clss, method = fetcher.rsplit(".", 2)
                rerun = {"module": module, "class": clss, "method": method}
            else:
                for frame_info in inspect.stack()[1:]:
                    if frame_info.function.startswith(FETCH_PREFIX):
                        frame = frame_info.frame
                        rerun = {
                            "module": inspect.getmodule(frame).__name__,
                            "class": frame.f_locals["self"].__class__.__name__,
                            "method": frame.f_code.co_name,
                        }
                        break
            if not rerun:
                raise DependencyFetcherNotFoundError(
                    f"Cannot re-run, no fetcher found for evidence {path}."
                )
            locker.dependency_rerun.append(rerun)
            raise DependencyUnavailableError(
                f"evidence dependency {path} is currently unavailable."
            )
    return evidence


def store_raw_evidence(evidence_path):
    """
    Decorate a typical ``fetcher_`` method fetching raw evidence.

    Use when retrieving raw evidence by a fetcher and the name of the evidence
    is static/known.  When the evidence name is dynamic use the
    raw_evidence context manager instead.

    The decorator expects that the decorated method returns the content to be
    stored in the locker.  The storing of the evidence is also handled by this
    decorator.

    :param path: relative path to the evidence within the Locker. For example,
      ``source1/evidence.json``.
    """

    def decorator(f):
        @wraps(f)  # required for preserving the function context
        def wrapper(self, *args, **kwargs):
            return _store_wrapper(self, evidence_path, f, "raw")

        return wrapper

    return decorator


def store_tmp_evidence(evidence_path):
    """
    Decorate a typical ``fetcher_`` method fetching temporary evidence.

    Use when retrieving temporary evidence by a fetcher and the name of the
    evidence is static/known.  When the evidence name is dynamic use the
    tmp_evidence context manager instead.

    :param path: relative path to the evidence within the Locker. For example,
      ``source1/evidence.json``.
    """

    def decorator(f):
        @wraps(f)  # required for preserving the function context
        def wrapper(self, *args, **kwargs):
            return _store_wrapper(self, evidence_path, f, "tmp")

        return wrapper

    return decorator


def store_derived_evidence(evidences, target):
    """
    Decorate a typical ``fetcher_`` method fetching derived evidence.

    Use when retrieving derived evidence by a fetcher and the name of the
    evidence is static/known.  When the evidence name is dynamic use the
    derived_evidence context manager instead.

    The decorator expects that the decorated method returns the content to be
    stored in the locker.  The storing of the evidence is also handled by this
    decorator.

    :param evidences: a list of relative paths to the evidences needed by
      the fetcher. They will be passed to the method call.
      For example, ``[raw/src/foo.json, derived/src/bar.json]``.
    :param target: relative path to the evidence to be stored in the Locker.
      For example, ``src/evidence.json``.
    """

    def decorator(f):
        @wraps(f)  # required for preserving the function context
        def wrapper(self, *args, **kwargs):
            target_path = target
            if not target_path.startswith("derived/"):
                target_path = f"derived/{target_path}"
            target_evidence = get_evidence_by_path(target_path)
            if self.locker.validate(target_evidence):
                return
            depends = [get_evidence_by_path(e, self.locker) for e in evidences]
            content = f(self, *depends)
            target_evidence.set_content(content)
            self.locker.add_evidence(target_evidence)

        return wrapper

    return decorator


def with_raw_evidences(*from_evidences):
    """
    Decorate a typical ``test_`` check method processing raw evidences.

    Use when processing raw evidence by a check and the name(s) of the
    evidence is/are static/known.  When the evidence names are dynamic use the
    ``evidences`` context manager instead.

    :param from_evidences: relative paths to evidences as strings or
      LazyLoader namedtuples that contain relative paths to evidences and
      evidence classes required by the check.
    """

    def decorator(f):
        return _with_evidence_decorator(from_evidences, f, "raw")

    return decorator


def with_external_evidences(*from_evidences):
    """
    Decorate a typical ``test_`` check method processing external evidences.

    Use when processing external evidence by a check and the name(s) of the
    evidence is/are static/known.  When the evidence names are dynamic use the
    ``evidences`` context manager instead.

    :param from_evidences: relative paths to evidences as strings or
      LazyLoader namedtuples that contain relative paths to evidences and
      evidence classes required by the check.
    """

    def decorator(f):
        return _with_evidence_decorator(from_evidences, f, "external")

    return decorator


def with_derived_evidences(*from_evidences):
    """
    Decorate a typical ``test_`` check method processing derived evidences.

    Use when processing derived evidence by a check and the name(s) of the
    evidence is/are static/known.  When the evidence names are dynamic use the
    ``evidences`` context manager instead.

    :param from_evidences: relative paths to evidences as strings or
      LazyLoader namedtuples that contain relative paths to evidences and
      evidence classes required by the check.
    """

    def decorator(f):
        return _with_evidence_decorator(from_evidences, f, "derived")

    return decorator


def with_tmp_evidences(*from_evidences):
    """
    Decorate a typical ``test_`` check method processing temporary evidences.

    Use when processing temporary evidence by a check and the name(s) of the
    evidence is/are static/known.  When the evidence names are dynamic use the
    ``evidences`` context manager instead.

    :param from_evidences: relative paths to evidences as strings or
      LazyLoader namedtuples that contain relative paths to evidences and
      evidence classes required by the check.
    """

    def decorator(f):
        return _with_evidence_decorator(from_evidences, f, "tmp")

    return decorator


def _store_wrapper(self, evidence_path, func, type_name):
    path = evidence_path
    if not path.startswith(f"{type_name}/"):
        path = f"{type_name}/{path}"
    evidence = get_evidence_by_path(path)
    if self.locker.validate(evidence):
        return
    content = func(self)
    evidence.set_content(content)
    self.locker.add_evidence(evidence)


def _with_evidence_decorator(from_evidences, f, type_str):
    from_evs = []
    for from_ev in from_evidences:
        path = from_ev
        # Default the evidence class to evidence of type type_str.
        # If from_ev is a LazyLoader and its evidence class is of the type
        # type_str then set the evidence class to the from_ev evidence class.
        ev_class = get_evidence_class(type_str)
        if isinstance(from_ev, LazyLoader):
            path = from_ev.path
            if issubclass(from_ev.ev_class, ev_class):
                ev_class = from_ev.ev_class
        # Ensure path is the full relative path.
        roots = [type_str, ComplianceAgent.AGENTS_DIR]
        if PurePath(path).parts[0] not in roots:
            path = str(PurePath(type_str, path))
        from_evs.append(LazyLoader(path, ev_class))

    if hasattr(f, "args"):
        f.args.extend(from_evs)
        return f

    @wraps(f)  # required for preserving the function context
    def wrapper(self, *args, **kwargs):
        return _evidence_wrapper(self, wrapper.args, f)

    wrapper.args = from_evs
    return wrapper


def _evidence_wrapper(self, from_evidences, func):
    evidences = []
    for fe in from_evidences:
        ev = get_evidence_by_path(fe.path, self.locker)
        if ev.__class__ in get_evidence_base_classes():
            # Only cast if evidence retrieved is a base evidence class object
            ev = fe.ev_class.from_evidence(ev)
        evidences.append(ev)
    for evidence in evidences:
        self.add_evidence_metadata(evidence.path, evidence_locker=evidence.locker)
    return func(self, *evidences)
