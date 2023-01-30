# Copyright (c) 2022 IBM Corp. All rights reserved.
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
"""Compliance check automation module."""

import base64
import hashlib
from pathlib import PurePath

from compliance.config import get_config

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed


class ComplianceAgent:
    """Compliance agent class."""

    AGENTS_DIR = "agents"
    PUBLIC_KEYS_EVIDENCE_PATH = "raw/auditree/agent_public_keys.json"

    def __init__(self, name=None, use_agent_dir=True):
        """Construct and initialize the agent object."""
        self._name = name
        self._private_key = self._public_key = None
        self._use_agent_dir = use_agent_dir

    @property
    def name(self):
        """Get agent name."""
        return self._name

    @property
    def private_key(self):
        """Get agent private key."""
        return self._private_key

    @private_key.setter
    def private_key(self, data_bytes):
        """
        Set agent private key.

        :param data_bytes: The PEM encoded key data as `bytes`.
        """
        self._private_key = serialization.load_pem_private_key(
            data_bytes, None, default_backend()
        )

    @property
    def public_key(self):
        """Get agent public key."""
        return self._public_key

    @public_key.setter
    def public_key(self, data_bytes):
        """
        Set agent public key.

        :param data_bytes: The PEM encoded key data as `bytes`.
        """
        if self.name:
            self._public_key = serialization.load_pem_public_key(data_bytes)

    def get_path(self, path):
        """
        Get the full evidence path.

        :param path: The relative evidence path as a string.

        :returns: The full evidence path as a string.
        """
        if self.name and self._use_agent_dir:
            if PurePath(path).parts[0] != self.AGENTS_DIR:
                return str(PurePath(self.AGENTS_DIR, self.name, path))
        return path

    def signable(self):
        """Determine if the agent can sign evidence."""
        return all([self.name, self.private_key])

    def verifiable(self):
        """Determine if the agent can verify evidence."""
        return all([self.name, self.public_key])

    def load_public_key_from_locker(self, locker):
        """
        Load agent public key from locker.

        :param locker: A locker of type :class:`compliance.locker.Locker`.
        """
        if not self.name:
            return
        try:
            public_keys = locker.get_evidence(self.PUBLIC_KEYS_EVIDENCE_PATH)
            public_key_str = public_keys.content_as_json[self.name]
            self.public_key = public_key_str.encode()
        except Exception:
            self._public_key = None  # Missing public key evidence.

    def hash_and_sign(self, data_bytes):
        """
        Hash and sign evidence using the agent private key.

        :param data_bytes: The data to sign as `bytes`.

        :returns: A `tuple` containing the hexadecimal digest string and the
          base64 encoded signature string. Returns tuple `(None, None)` if the
          agent is not configured to sign evidence.
        """
        if not self.signable():
            return None, None
        hashed = hashlib.sha256(data_bytes)
        signature = self.private_key.sign(
            hashed.digest(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH
            ),
            Prehashed(hashes.SHA256()),
        )
        return hashed.hexdigest(), base64.b64encode(signature).decode()

    def verify(self, data_bytes, signature_b64):
        """
        Verify evidence using the agent public key.

        :param data_bytes: The data to verify as `bytes`.
        :param signature_b64: The base64 encoded signature string.

        :returns: `True` if data can be verified, else `False`.
        """
        if not self.verifiable():
            return False
        try:
            self.public_key.verify(
                base64.b64decode(signature_b64),
                data_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return True
        except InvalidSignature:
            return False

    @classmethod
    def from_config(cls):
        """Load agent from configuration."""
        config = get_config()
        agent = cls(
            name=config.get("agent_name"),
            use_agent_dir=config.get("use_agent_dir", True),
        )
        private_key_path = config.get("agent_private_key")
        public_key_path = config.get("agent_public_key")
        if private_key_path:
            with open(private_key_path, "rb") as key_file:
                agent.private_key = key_file.read()
            agent.public_key = agent.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        elif public_key_path:
            with open(public_key_path, "rb") as key_file:
                agent.public_key = key_file.read()
        return agent
