# -*- mode:python; coding:utf-8 -*-
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
"""Compliance automation agent tests module."""

import unittest
try:
    from mock import Mock, create_autospec, mock_open, patch
except ImportError:
    from unittest.mock import Mock, create_autospec, mock_open, patch

from compliance.agent import ComplianceAgent
from compliance.evidence import RawEvidence
from compliance.locker import Locker
from compliance.utils.exceptions import EvidenceNotFoundError


class TestSigningEvidence(unittest.TestCase):
    """Test evidence signing logic."""

    def setUp(self):
        """Prepare the test fixture."""
        self.name = 'auditree.local'
        self.evidence = b'This is my evidence.'
        self.expected_digest = (
            '81ddd37cb8aba90077a717b7d6c067815add58e658bb2'
            'be0dea4d4d9301c762d'
        )
        self.priv_key = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAxYosRYnahnSuH3SmNupnzQhxJsDEhqChKjrcyN19L8+vcjUU
iMSaKRoAHuUKp5Pfwkoylryd4AyXIU9UnXZgdIOl2+r5xzXqfdLwi+PAU/eEWPLA
QfCpIodqKqBLCyzpMoJHv9GDqg8XJkY/2i8j7oiqLR7vibIgRAJXqF95KdNvbW7G
vu8JHigN4aoGdbQSPp/jJ30wBvy7hHOSrMWFiQUt7H25YbvOZGWQeC8HZ2EXruzG
+FV2rkW52FaTn31lX1EEc2Yz8AI7/yF/8C5jSSL/pmzxBzh/P4zGDNlm2habpwAI
QpHnJJ8XeXYS//RXuOYNObeRwfhm82TB9+nSlQIDAQABAoIBAEkaSintyxXpBisT
4xL9ii5hSmZ5/gCIXzwejmgzN0nDRP0x0YiPoTFGsva78kZzveHLzY7k/FPWtPMZ
xYmELkvQEEgjXA4x0LaBoo1SWnF4btzv8OA2LJFfpZVivoLDOwV7GwxMf7omXX3H
j4ex3E1A/CE4ipLdfX1NlJz1wAQO2Q/kiw6tZV8axYwYjT8+z1MANIsx6Mtjzfku
YtrfMcPuvXjXHeoOKdD3Fn1PdAaj6RXWCm8NkED/k6JOaAeTTaO4o6t8VvhtHYG8
4jCzbWdc07OAUuwyynbuVypAWp+PDz1/0ID+WKW4FHN7HT0iEWtG34pc3ls2Hlu/
/QZEDiECgYEA8g/tEwa97H1m8j3jzMoi6NOfceENYUGxLiSu9dtY8QAlz+G12LJi
39x1Fcpi4sPTB2ITdy3vp1EAVVePCjVLxPv3vV474bIFQSqW/IoRCSYQCOOt2IkS
RL9NhZoMyWbpBx1OlOKDPzoJLRUho1EF/JRwJ1YebfYssq4ce1fjAxkCgYEA0On4
sYryVp/jJGmlC8m713/ioNgV+zzGn9M4GUjY7LPZSH4Pgll9LisK13+z32pl7KWQ
zcdg/lcpSZaIn4HohzPg0Lv43Up0BjXjrOrqhtoUwfWMoDgV7IqwPFYNLFQjUo+N
A2/x1+6hlotjrmPr09REo02aCj2ZVp/i3K2MFt0CgYEAtRUK8nfRrs/lKoT4HGR/
FxPxLJ0CiGY/aNiSdmQANlI49znP8usIIpXmlUWREjkSbmyFSVv4838aM73LyQQz
yYoBPA352A539dcpmoSi1+g8iJninKF2JC3EjZS/yg8NdoALIEAPlUYSRUKQpn9f
biORfyvimbpWl9i+f9swfUkCgYAkVWzhQ+8dzbTtcko4IJ/AvQcnPi2kgk9xIIUT
MK45jJXvm60K2JGC5A2AqT8ZTiHn5GuovlJKKdKOb9XXF/re+NDSvL5tjjNbmSe9
vSWIyojtqs0IWHjHqN85vyWPXhq+kyTNQjzndyM3UYrGm646KyK83BQ8T7ZJcIk+
JBjHKQKBgQDwxwhFKfgq9n420Vz5QIgZCT3pcmEvqQzAsxLfeOz7RYNHqECMl6FY
p6u8/fRZssZdelNwkUQMMw1gTdhV91Xd/3lbfoWQ72KnaITItUqYgP3Th9AQOFyO
YLmlUVKZU7mt43D8aj8l4l11jWDBkvOba/wJ7CjTQ15ik4ntl9TRzg==
-----END RSA PRIVATE KEY-----
""".encode()

        self.pub_key = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxYosRYnahnSuH3SmNupn
zQhxJsDEhqChKjrcyN19L8+vcjUUiMSaKRoAHuUKp5Pfwkoylryd4AyXIU9UnXZg
dIOl2+r5xzXqfdLwi+PAU/eEWPLAQfCpIodqKqBLCyzpMoJHv9GDqg8XJkY/2i8j
7oiqLR7vibIgRAJXqF95KdNvbW7Gvu8JHigN4aoGdbQSPp/jJ30wBvy7hHOSrMWF
iQUt7H25YbvOZGWQeC8HZ2EXruzG+FV2rkW52FaTn31lX1EEc2Yz8AI7/yF/8C5j
SSL/pmzxBzh/P4zGDNlm2habpwAIQpHnJJ8XeXYS//RXuOYNObeRwfhm82TB9+nS
lQIDAQAB
-----END PUBLIC KEY-----
""".encode()

        # Mock empty locker.
        self.mock_empty_locker = create_autospec(Locker)
        self.mock_empty_locker.get_evidence.side_effect = Mock(
            side_effect=EvidenceNotFoundError('Evidence not found in locker.')
        )

        # Mock locker containing public key evidence.
        mock_locker_evidence = create_autospec(RawEvidence)
        mock_locker_evidence.content_as_json = {
            self.name: self.pub_key.decode()
        }
        self.mock_locker = create_autospec(Locker)
        self.mock_locker.get_evidence.return_value = mock_locker_evidence

    @patch('compliance.agent.get_config')
    def test_empty_agent_from_config(self, get_config_mock):
        """Test load empty agent from configuration."""
        get_config_mock.return_value = {}

        agent = ComplianceAgent.from_config()

        self.assertIsNone(agent.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertFalse(agent.verifiable())

    @patch('compliance.agent.get_config')
    def test_agent_from_config_no_key(self, get_config_mock):
        """Test load agent with no key from configuration."""
        get_config_mock.return_value = {'agent_name': self.name}

        agent = ComplianceAgent.from_config()

        self.assertEqual(agent.name, self.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertFalse(agent.verifiable())

    @patch('compliance.agent.get_config')
    def test_agent_from_config(self, get_config_mock):
        """Test load agent from configuration."""
        get_config_mock.return_value = {
            'agent_name': self.name, 'agent_private_key': '/path/to/key'
        }

        with patch('builtins.open', mock_open(read_data=self.priv_key)):
            agent = ComplianceAgent.from_config()

        self.assertEqual(agent.name, self.name)
        self.assertIsNotNone(agent.private_key)
        self.assertIsNotNone(agent.public_key)
        self.assertTrue(agent.signable())
        self.assertTrue(agent.verifiable())

    def test_empty_agent(self):
        """Test init empty agent."""
        agent = ComplianceAgent()

        self.assertIsNone(agent.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertFalse(agent.verifiable())

    def test_agent_no_keys(self):
        """Test init agent with no keys."""
        agent = ComplianceAgent(name=self.name)

        self.assertEqual(agent.name, self.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertFalse(agent.verifiable())

    def test_agent_private_key(self):
        """Test init agent with private key."""
        agent = ComplianceAgent(name=self.name)
        agent.private_key = self.priv_key

        self.assertEqual(agent.name, self.name)
        self.assertIsNotNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertTrue(agent.signable())
        self.assertFalse(agent.verifiable())

    def test_agent_public_key(self):
        """Test init agent with public key."""
        agent = ComplianceAgent(name=self.name)
        agent.public_key = self.pub_key

        self.assertEqual(agent.name, self.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNotNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertTrue(agent.verifiable())

    def test_agent_both_keys(self):
        """Test init agent."""
        agent = ComplianceAgent(name=self.name)
        agent.private_key = self.priv_key
        agent.public_key = self.pub_key

        self.assertEqual(agent.name, self.name)
        self.assertIsNotNone(agent.private_key)
        self.assertIsNotNone(agent.public_key)
        self.assertTrue(agent.signable())
        self.assertTrue(agent.verifiable())

    def test_agent_load_public_key(self):
        """Test load public key from locker."""
        agent = ComplianceAgent(name=self.name)
        agent.load_public_key_from_locker(self.mock_locker)

        self.assertEqual(agent.name, self.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNotNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertTrue(agent.verifiable())

    def test_empty_agent_load_public_key(self):
        """Test load public key from locker for empty agent."""
        agent = ComplianceAgent()
        agent.load_public_key_from_locker(self.mock_empty_locker)

        self.assertIsNone(agent.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertFalse(agent.verifiable())

    def test_agent_load_public_key_missing(self):
        """Test load missing public key from locker."""
        agent = ComplianceAgent(name=self.name)
        agent.load_public_key_from_locker(self.mock_empty_locker)

        self.assertEqual(agent.name, self.name)
        self.assertIsNone(agent.private_key)
        self.assertIsNone(agent.public_key)
        self.assertFalse(agent.signable())
        self.assertFalse(agent.verifiable())

    def test_agent_sign_failure(self):
        """Test agent sign for missing key."""
        agent = ComplianceAgent(name=self.name)

        self.assertEqual(agent.name, self.name)
        self.assertFalse(agent.signable())
        self.assertEqual((None, None), agent.hash_and_sign(self.evidence))

    def test_agent_sign_success(self):
        """Test agent sign success."""
        agent = ComplianceAgent(name=self.name)
        agent.private_key = self.priv_key
        digest, signature = agent.hash_and_sign(self.evidence)

        self.assertEqual(agent.name, self.name)
        self.assertTrue(agent.signable())
        self.assertEqual(self.expected_digest, digest)
        self.assertIsNotNone(signature)

    def test_agent_verify_failure_missing_key(self):
        """Test agent verify failure for missing key."""
        agent = ComplianceAgent(name=self.name)
        agent.private_key = self.priv_key
        digest, signature = agent.hash_and_sign(self.evidence)

        self.assertEqual(agent.name, self.name)
        self.assertTrue(agent.signable())
        self.assertFalse(agent.verifiable())
        self.assertFalse(agent.verify(self.evidence, signature))

    def test_agent_verify_failure_tamper(self):
        """Test agent verify failure for tampered evidence."""
        agent = ComplianceAgent(name=self.name)
        agent.private_key = self.priv_key
        agent.public_key = self.pub_key
        _digest, signature = agent.hash_and_sign(self.evidence)

        self.evidence += b'foo'  # Tamper with evidence.

        self.assertEqual(agent.name, self.name)
        self.assertTrue(agent.signable())
        self.assertTrue(agent.verifiable())
        self.assertFalse(agent.verify(self.evidence, signature))

    def test_agent_verify_success(self):
        """Test agent verify success."""
        agent = ComplianceAgent(name=self.name)
        agent.private_key = self.priv_key
        agent.public_key = self.pub_key
        _digest, signature = agent.hash_and_sign(self.evidence)

        self.assertEqual(agent.name, self.name)
        self.assertTrue(agent.signable())
        self.assertTrue(agent.verifiable())
        self.assertTrue(agent.verify(self.evidence, signature))
