"""Configuration and execution of streaming runs."""

from ocelescope_module_streaming.runs.config import BufferSetting, RunConfig, StreamSettings
from ocelescope_module_streaming.runs.factory import InvalidRunConfig, PreparedRun, prepare_run
from ocelescope_module_streaming.runs.presets import PRESETS, Preset
from ocelescope_module_streaming.runs.summary import RunProgress, RunResult, RunSummary
from ocelescope_module_streaming.runs.task import StreamingRunTask

__all__ = [
    "PRESETS",
    "BufferSetting",
    "InvalidRunConfig",
    "PreparedRun",
    "Preset",
    "RunConfig",
    "RunProgress",
    "RunResult",
    "RunSummary",
    "StreamSettings",
    "StreamingRunTask",
    "prepare_run",
]
