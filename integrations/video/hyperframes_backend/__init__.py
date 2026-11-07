"""HyperFrames visual-render backend for Simba's existing video pipeline."""

from .adapter import HyperFramesRenderError, render

__all__ = ["HyperFramesRenderError", "render"]
