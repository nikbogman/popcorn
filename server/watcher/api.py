from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Api(BaseModel):
    """A request or response body. Fields are snake_case here and camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def iso(d: datetime):
    """A UTC ISO timestamp to the millisecond, e.g. 2026-01-01T00:00:00.000Z."""
    return d.astimezone(UTC).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
