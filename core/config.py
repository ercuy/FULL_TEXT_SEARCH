# =====================================================================
# BEGIN file: core/config.py
# =====================================================================
import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any


CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "config",
    "settings.json"
)


@dataclass
class PathsConfig:
    root_locations: List[str]
    scanned_folder: str
    index_db: str
    log_folder: str


@dataclass
class FileHandlingConfig:
    allowed_extensions: List[str]
    min_text_length: int
    detect_scanned_pdf: Dict[str, bool]


@dataclass
class TagsConfig:
    vocabulary: List[str]
    synonyms: Dict[str, str]
    max_tags_per_document: int


@dataclass
class PatternsConfig:
    project_code: str
    sample_id: str
    date: str


@dataclass
class SummariesConfig:
    enabled: bool
    max_sentences: int
    use_ai_compression: bool
    language_detection: bool


@dataclass
class IndexingConfig:
    batch_size: int
    fts5_enabled: bool
    update_existing: bool


@dataclass
class UiConfig:
    type: str
    preview_enabled: bool
    filters_enabled: bool
    max_results: int


@dataclass
class Settings:
    version: str
    paths: PathsConfig
    file_handling: FileHandlingConfig
    tags: TagsConfig
    patterns: PatternsConfig
    summaries: SummariesConfig
    indexing: IndexingConfig
    ui: UiConfig


def _load_raw_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_settings(path: str = CONFIG_PATH) -> Settings:
    raw = _load_raw_config(path)

    paths = PathsConfig(
        root_locations=raw["paths"]["root_locations"],
        scanned_folder=raw["paths"]["scanned_folder"],
        index_db=os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            raw["paths"]["index_db"]
        ),
        log_folder=os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            raw["paths"]["log_folder"]
        ),
    )

    file_handling = FileHandlingConfig(
        allowed_extensions=raw["file_handling"]["allowed_extensions"],
        min_text_length=raw["file_handling"]["min_text_length"],
        detect_scanned_pdf=raw["file_handling"]["detect_scanned_pdf"],
    )

    tags = TagsConfig(
        vocabulary=raw["tags"]["vocabulary"],
        synonyms=raw["tags"]["synonyms"],
        max_tags_per_document=raw["tags"]["max_tags_per_document"],
    )

    patterns = PatternsConfig(
        project_code=raw["patterns"]["project_code"],
        sample_id=raw["patterns"]["sample_id"],
        date=raw["patterns"]["date"],
    )

    summaries = SummariesConfig(
        enabled=raw["summaries"]["enabled"],
        max_sentences=raw["summaries"]["max_sentences"],
        use_ai_compression=raw["summaries"]["use_ai_compression"],
        language_detection=raw["summaries"]["language_detection"],
    )

    indexing = IndexingConfig(
        batch_size=raw["indexing"]["batch_size"],
        fts5_enabled=raw["indexing"]["fts5_enabled"],
        update_existing=raw["indexing"]["update_existing"],
    )

    ui = UiConfig(
        type=raw["ui"]["type"],
        preview_enabled=raw["ui"]["preview_enabled"],
        filters_enabled=raw["ui"]["filters_enabled"],
        max_results=raw["ui"]["max_results"],
    )

    return Settings(
        version=raw["version"],
        paths=paths,
        file_handling=file_handling,
        tags=tags,
        patterns=patterns,
        summaries=summaries,
        indexing=indexing,
        ui=ui,
    )