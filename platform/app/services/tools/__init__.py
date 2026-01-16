"""
FIP Tool Calling Module

This module provides tool definitions and execution for the LLM to autonomously
call external APIs and services.
"""

from .football_tools import FootballTools

__all__ = ["FootballTools"]
