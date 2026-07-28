"""Post-result V3 development interfaces.

V2 parser, protocol, evaluator, and result code remain outside this package
and unchanged.  V3 callers receive only the narrow contracts exported here.
"""

from indusbench.v3dev.contracts import (
    MTAAC_TRAINING_GATEWAY_VERSION,
    V3_STRUCTURAL_STATES,
    MTAACTrainingBundle,
    MTAACTrainingDocument,
    MTAACTrainingLine,
    MTAACTrainingRegime,
    MTAACTrainingToken,
    MTAACTrainingView,
    V3ContractError,
    V3ObservationLine,
    V3ObservationToken,
    V3ReportedDirection,
    V3StructuralState,
)
from indusbench.v3dev.mtaac_training import (
    MTAAC_V2_FREEZE_COMMIT,
    MTAAC_V2_HOLDOUT_FAMILY_COUNT,
    MTAAC_V2_SPLIT_MANIFEST_SHA256,
    MTAAC_V2_SPLIT_SEED,
    MTAAC_V2_TEST_FRACTION,
    MTAAC_V2_TRAINING_FAMILY_COUNT,
    MTAACTrainingGatewayError,
    build_mtaac_v2_training_bundle,
)

__all__ = [
    "MTAAC_TRAINING_GATEWAY_VERSION",
    "MTAAC_V2_FREEZE_COMMIT",
    "MTAAC_V2_HOLDOUT_FAMILY_COUNT",
    "MTAAC_V2_SPLIT_MANIFEST_SHA256",
    "MTAAC_V2_SPLIT_SEED",
    "MTAAC_V2_TEST_FRACTION",
    "MTAAC_V2_TRAINING_FAMILY_COUNT",
    "V3_STRUCTURAL_STATES",
    "MTAACTrainingBundle",
    "MTAACTrainingDocument",
    "MTAACTrainingGatewayError",
    "MTAACTrainingLine",
    "MTAACTrainingRegime",
    "MTAACTrainingToken",
    "MTAACTrainingView",
    "V3ContractError",
    "V3ObservationLine",
    "V3ObservationToken",
    "V3ReportedDirection",
    "V3StructuralState",
    "build_mtaac_v2_training_bundle",
]
