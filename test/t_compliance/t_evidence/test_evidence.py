import unittest
from unittest.mock import MagicMock, create_autospec

from compliance.evidence import store_derived_evidence
from compliance.locker import Locker
from compliance.utils.exceptions import DependencyUnavailableError, StaleEvidenceError


class TestEvidence(unittest.TestCase):

    def test_store_derived_evidence_adds_to_rerun(self):
        """
        Ensure that when running a fetcher that stores derived evidence
        that it is re-run if one of the dependant evidence is not available.
        """
        self.locker = create_autospec(Locker)
        self.locker.dependency_rerun = []
        self.locker.validate.side_effect = [False, StaleEvidenceError]
        self.locker.repo_url = "https://my.locker.url"
        self.locker.get_evidence_metadata = MagicMock()
        self.locker.get_evidence_metadata.return_value = None
        self.locker.get_evidence.side_effect = StaleEvidenceError

        with self.assertRaises(DependencyUnavailableError):
            self.fetch_some_derived_evidence()

        self.assertEquals(1, len(self.locker.dependency_rerun))
        f = self.fetch_some_derived_evidence
        self.assertDictEqual(
            self.locker.dependency_rerun[0],
            {
                "module": f.__module__,
                "class": self.__class__.__name__,
                "method": f.__name__,
            },
        )

    @store_derived_evidence(["raw/cos/cos_bucket_metadata.json"], target="cos/bar.json")
    def fetch_some_derived_evidence(self, cos_metadata):
        return "{}"
