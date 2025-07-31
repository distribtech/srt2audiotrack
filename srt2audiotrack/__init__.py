"""Core package for generating English audio tracks from subtitles."""

__all__ = ["SubtitlePipeline"]


def __getattr__(name):
    if name == "SubtitlePipeline":
        from .pipeline import SubtitlePipeline
        return SubtitlePipeline
    raise AttributeError(name)
