from __future__ import annotations

import unittest

from indusbench.manifest import build_manifest, corpus_digest
from tests.test_validation import valid_artifact


class ManifestTests(unittest.TestCase):
    def test_corpus_hash_is_independent_of_row_order(self) -> None:
        first = valid_artifact("SYN:A001")
        second = valid_artifact("SYN:A002")
        self.assertEqual(corpus_digest([first, second]), corpus_digest([second, first]))

    def test_manifest_counts_nested_lines_and_tokens(self) -> None:
        manifest = build_manifest(
            [valid_artifact()],
            schema_version="0.1.0",
            source_registry={"sources": []},
        )
        self.assertEqual(1, manifest["counts"]["artifacts"])
        self.assertEqual(1, manifest["counts"]["lines"])
        self.assertEqual(2, manifest["counts"]["tokens"])
        self.assertEqual(64, len(manifest["corpus_sha256"]))
        self.assertEqual(64, len(manifest["source_registry_sha256"]))


if __name__ == "__main__":
    unittest.main()
