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
"""Compliance automation evidence signing tests module."""

import unittest

try:
    from mock import Mock, create_autospec
except ImportError:
    from unittest.mock import Mock, create_autospec

from compliance.agent import ComplianceAgent
from compliance.evidence import RawEvidence
from compliance.locker import Locker
from compliance.utils.exceptions import EvidenceNotFoundError


class TestSigningEvidence(unittest.TestCase):
    """Test evidence signing logic."""

    def setUp(self):
        """Prepare the test fixture."""
        self.evidence = "This is my evidence."
        self.expected_digest = (
            "81ddd37cb8aba90077a717b7d6c067815add58e658bb2" "be0dea4d4d9301c762d"
        )
        self.binary_evidence = b"This is my binary evidence."
        self.expected_binary_digest = (
            "447c95ece8e82129ec767de76c6d98c35280036b364055248d217d8f73fd1082"
        )

        self.agent = ComplianceAgent(name="auditree.local")
        self.unknown_agent = ComplianceAgent(name="unknown.local")
        self.agent.private_key = self.unknown_agent.private_key = """
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
"""

        # Mock empty locker.
        self.mock_empty_locker = create_autospec(Locker)
        self.mock_empty_locker.get_evidence.side_effect = Mock(
            side_effect=EvidenceNotFoundError("Evidence not found in locker.")
        )

        # Mock locker containing public key evidence.
        mock_locker_evidence = create_autospec(RawEvidence)
        mock_locker_evidence.content_as_json = {self.agent.name: self.pub_key}
        self.mock_locker = create_autospec(Locker)
        self.mock_locker.get_evidence.return_value = mock_locker_evidence
        self.mock_locker.get_evidence_metadata.return_value = {
            "digest": self.expected_digest,
            "signature": (
                "jMKH9pWRc8g2ai0sSvXv+XRD6rptlOpU9wJHePuzIby4fmmk/ls"
                "0WKdxP4fKz1sPtMNsH1mLx7EhM9/vBDGRj85gkGDS2x+FFXkUte"
                "VNPUAaW9sJx+Fhd8YdRkuyxxKx3lmMQuwopzrnSA+SH0LX22b+d"
                "DtFxTwzg/r2kFenaqNPWlRHAd07T/RNq2DFA/+mdIY4mE8zz8bS"
                "B/IiJmKupLdTGxNBuu32wSJq4aGVZ7QXdkk4rzXcgKoS4PfooLS"
                "pmlive1T1ifbT6khMlTWC46Nx+fv8T+JoN2hB9Mf9PQ0ZCuuZeE"
                "8RYYyttqa+b/YExraesjIjY8X63wxM9FtNvQ=="
            ),
        }

    def test_evidence_sign(self):
        """Ensure evidence is correctly signed."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(self.evidence)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(self.evidence, evidence.content)
        self.assertEqual(self.expected_digest, evidence.digest)

    def test_binary_evidence_sign(self):
        """Ensure evidence is correctly signed."""
        evidence = RawEvidence(
            "evidence.txt", "test", agent=self.agent, binary_content=True
        )
        evidence.set_content(self.binary_evidence)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(self.binary_evidence, evidence.content)
        self.assertEqual(self.expected_binary_digest, evidence.digest)

    def test_evidence_no_sign(self):
        """Ensure evidence is not signed when `sign=False`."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(self.evidence, sign=False)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(self.evidence, evidence.content)
        self.assertEqual(None, evidence.digest)
        self.assertEqual(None, evidence.signature)

    def test_none_evidence_no_sign(self):
        """Ensure `None` evidence is not signed."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(None)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(None, evidence.content)
        self.assertEqual(None, evidence.digest)
        self.assertEqual(None, evidence.signature)

    def test_signed_evidence_verify_success(self):
        """Ensure valid, signed evidence can be verified."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(self.evidence)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(self.evidence, evidence.content)
        self.assertEqual(self.expected_digest, evidence.digest)
        self.assertTrue(evidence.is_signed(self.mock_locker))
        self.assertTrue(evidence.verify_signature(self.mock_locker))

    def test_none_evidence_verify_success(self):
        """Ensure `None` evidence can be verified."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(None)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(None, evidence.digest)
        self.assertEqual(None, evidence.signature)
        self.assertTrue(evidence.is_signed(self.mock_locker))
        self.assertTrue(evidence.verify_signature(self.mock_locker))

    def test_unsigned_evidence_verify_success(self):
        """Ensure unsigned evidence can be verified."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(self.evidence, sign=False)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(None, evidence.digest)
        self.assertEqual(None, evidence.signature)
        self.assertTrue(evidence.is_signed(self.mock_locker))
        self.assertTrue(evidence.verify_signature(self.mock_locker))

    def test_tampered_evidence_verify_failure(self):
        """Ensure invalid, signed evidence can not be verified."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(self.evidence)
        evidence._content += "foo"  # Tamper with evidence.

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(self.evidence + "foo", evidence.content)
        self.assertEqual(self.expected_digest, evidence.digest)
        self.assertTrue(evidence.is_signed(self.mock_locker))
        self.assertFalse(evidence.verify_signature(self.mock_locker))

    def test_unknown_signed_evidence_verify_failure(self):
        """Ensure evidence cannot be verified if the public key is unknown."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.unknown_agent)
        evidence.set_content(self.evidence)

        self.assertEqual(self.unknown_agent, evidence.agent)
        self.assertEqual(self.evidence, evidence.content)
        self.assertEqual(self.expected_digest, evidence.digest)
        self.assertTrue(evidence.is_signed(self.mock_locker))
        self.assertFalse(evidence.verify_signature(self.mock_locker))

    def test_signed_evidence_verify_failure_missing_public_keys(self):
        """Ensure evidence cannot be verified if public keys are missing."""
        evidence = RawEvidence("evidence.txt", "test", agent=self.agent)
        evidence.set_content(self.evidence)

        self.assertEqual(self.agent, evidence.agent)
        self.assertEqual(self.evidence, evidence.content)
        self.assertEqual(self.expected_digest, evidence.digest)
        self.assertTrue(evidence.is_signed(self.mock_locker))
        self.assertFalse(evidence.verify_signature(self.mock_empty_locker))
