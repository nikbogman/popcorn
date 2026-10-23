from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Api(BaseModel):
    """A request or response body. Fields are snake_case here and camelCase on the wire."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
