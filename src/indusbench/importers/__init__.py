"""Rights-aware importers for externally managed corpora."""

from indusbench.importers.mayig import (
    MayigImportError,
    import_mayig_artifact,
    import_mayig_corpus,
)

__all__ = [
    "MayigImportError",
    "import_mayig_artifact",
    "import_mayig_corpus",
]
