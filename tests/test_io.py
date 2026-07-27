from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from indusbench.io import CorpusFormatError, read_json, read_jsonl


class StrictJsonTests(unittest.TestCase):
    def test_json_document_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "input.json"
            for raw in (
                '{"source_id":"allowed","source_id":"blocked"}\n',
                '{"value":NaN}\n',
                '{"value":Infinity}\n',
                '{"value":1e999}\n',
            ):
                with self.subTest(raw=raw):
                    source.write_text(raw, encoding="utf-8")
                    with self.assertRaises(CorpusFormatError):
                        read_json(source)

    def test_jsonl_rejects_duplicate_keys_and_nonfinite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "input.jsonl"
            for raw in (
                '{"artifact_id":"first","artifact_id":"shadow"}\n',
                '{"artifact_id":"first","value":-Infinity}\n',
                '{"artifact_id":"first","value":1e999}\n',
            ):
                with self.subTest(raw=raw):
                    source.write_text(raw, encoding="utf-8")
                    with self.assertRaises(CorpusFormatError):
                        read_jsonl(source)


if __name__ == "__main__":
    unittest.main()
