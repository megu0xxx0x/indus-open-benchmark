"""Full JSON Schema Draft 2020-12 validation."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from indusbench.io import read_json
from indusbench.issues import Issue


class SchemaDependencyMissing(RuntimeError):
    """Raised when the declared JSON Schema validator is unavailable."""


def _validator_types() -> tuple[Any, Any]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ModuleNotFoundError as error:
        raise SchemaDependencyMissing(
            "the declared jsonschema runtime dependency is missing; reinstall the package"
        ) from error
    return Draft202012Validator, FormatChecker


def _json_path(parts: Iterable[object]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def validate_schema_instance(
    instance: Any,
    schema: Mapping[str, Any] | str | Path,
    *,
    path_prefix: str = "$",
) -> list[Issue]:
    """Validate one instance and return every Draft 2020-12 error."""

    validator = compile_schema_validator(schema)
    return validator(instance, path_prefix)


def compile_schema_validator(
    schema: Mapping[str, Any] | str | Path,
) -> Callable[[Any, str], list[Issue]]:
    """Compile one immutable schema for repeated instance validation."""

    schema_value = read_json(schema) if isinstance(schema, (str, Path)) else dict(schema)
    draft_validator, format_checker = _validator_types()
    draft_validator.check_schema(schema_value)
    validator = draft_validator(schema_value, format_checker=format_checker())

    def validate(instance: Any, path_prefix: str = "$") -> list[Issue]:
        issues: list[Issue] = []
        errors = sorted(
            validator.iter_errors(instance),
            key=lambda error: (list(error.absolute_path), error.message),
        )
        for error in errors:
            suffix = _json_path(error.absolute_path)
            issue_path = path_prefix + suffix.removeprefix("$")
            issues.append(Issue("json_schema", issue_path, error.message))
        return issues

    return validate


def validate_artifact_rows(
    rows: Iterable[Mapping[str, Any]],
    schema: Mapping[str, Any] | str | Path,
) -> list[Issue]:
    """Validate a sequence of artifact objects against the artifact schema."""

    issues: list[Issue] = []
    for index, row in enumerate(rows):
        issues.extend(validate_schema_instance(row, schema, path_prefix=f"$[{index}]"))
    return issues
