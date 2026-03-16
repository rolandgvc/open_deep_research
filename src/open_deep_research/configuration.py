import os
import json
from enum import Enum
from dataclasses import dataclass, fields
from typing import Any, Optional, Dict, get_origin, get_args

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

DEFAULT_REPORT_STRUCTURE = """Use this structure to create a report on the user-provided topic:

1. Introduction (no research needed)
   - Brief overview of the topic area

2. Main Body Sections:
   - Each section should focus on a sub-topic of the user-provided topic
   
3. Conclusion
   - Aim for 1 structural element (either a list of table) that distills the main body sections 
   - Provide a concise summary of the report"""

class SearchAPI(Enum):
    PERPLEXITY = "perplexity"
    TAVILY = "tavily"
    EXA = "exa"
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    LINKUP = "linkup"
    DUCKDUCKGO = "duckduckgo"
    GOOGLESEARCH = "googlesearch"

def _coerce_value(value: Any, field_type: type) -> Any:
    """Coerce a raw config/env value to the expected field type.

    Environment variables arrive as strings; ``configurable`` dict values may
    already have the correct type.  This helper bridges the gap so that
    ``Configuration`` fields are always stored with their declared type.
    """
    if value is None:
        return value

    # Unwrap Optional[X] → X
    origin = get_origin(field_type)
    if origin is type(None):
        return value
    # Optional is Union[X, None]
    args = get_args(field_type)
    if args and type(None) in args:
        inner_types = [a for a in args if a is not type(None)]
        if inner_types:
            field_type = inner_types[0]
            origin = get_origin(field_type)

    # Already the right type – nothing to do
    if isinstance(value, field_type) if not origin else False:
        return value

    # Enum fields: accept the enum's *value* as a string
    if isinstance(field_type, type) and issubclass(field_type, Enum):
        if isinstance(value, field_type):
            return value
        return field_type(value)

    # int / float fields coming from env vars as strings
    if field_type is int and isinstance(value, str):
        return int(value)
    if field_type is float and isinstance(value, str):
        return float(value)

    # Dict fields encoded as JSON strings in env vars
    if (origin is dict or field_type is dict) and isinstance(value, str):
        return json.loads(value)

    return value

@dataclass(kw_only=True)
class Configuration:
    """The configurable fields for the chatbot."""
    # Common configuration
    report_structure: str = DEFAULT_REPORT_STRUCTURE # Defaults to the default report structure
    search_api: SearchAPI = SearchAPI.TAVILY # Default to TAVILY
    search_api_config: Optional[Dict[str, Any]] = None
    
    # Graph-specific configuration
    number_of_queries: int = 2 # Number of search queries to generate per iteration
    max_search_depth: int = 2 # Maximum number of reflection + search iterations
    planner_provider: str = "anthropic"  # Defaults to Anthropic as provider
    planner_model: str = "claude-3-7-sonnet-latest" # Defaults to claude-3-7-sonnet-latest
    planner_model_kwargs: Optional[Dict[str, Any]] = None # kwargs for planner_model
    writer_provider: str = "anthropic" # Defaults to Anthropic as provider
    writer_model: str = "claude-3-5-sonnet-latest" # Defaults to claude-3-5-sonnet-latest
    writer_model_kwargs: Optional[Dict[str, Any]] = None # kwargs for writer_model
    
    # Multi-agent specific configuration
    supervisor_model: str = "openai:gpt-4.1" # Model for supervisor agent in multi-agent setup
    researcher_model: str = "openai:gpt-4.1" # Model for research agents in multi-agent setup 

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values: dict[str, Any] = {}
        for f in fields(cls):
            if not f.init:
                continue
            raw = os.environ.get(f.name.upper(), configurable.get(f.name))
            if raw is not None:
                values[f.name] = _coerce_value(raw, f.type)
        return cls(**values)
