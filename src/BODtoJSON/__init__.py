"""
BODtoJSON: A high-performance OAGIS BOD to Flattened JSON converter.
"""

__version__ = "1.0.0"

# Expose main functionality at the top level
from .mapper import convert, BODConverter

__all__ = ["convert", "BODConverter"]