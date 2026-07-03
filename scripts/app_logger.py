"""Shared application logger with selectable print or logging backends."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Literal

LogMode = Literal["print", "logger"]
LOG_MODE_CHOICES: tuple[LogMode, LogMode] = ("print", "logger")


class AppLogger:
  """Route user-facing log messages through print or the logging module."""

  def __init__(self, name: str, mode: LogMode = "print") -> None:
    """Initialize the app logger.

    Args:
      name: Logger name to use in logging mode.
      mode: Output backend to use for log messages.
    """
    self.name = name
    self.mode = mode
    self._logger = logging.getLogger(name)

    if mode == "logger":
      self._configure_logger()

  def set_mode(self, mode: LogMode) -> None:
    """Switch the logger backend mode in place.

    Args:
      mode: Output backend to use for subsequent log messages.
    """
    self.mode = mode
    if mode == "logger":
      self._configure_logger()

  def _configure_logger(self) -> None:
    """Configure the standard library logger once per logger name."""
    if not self._logger.handlers:
      handler = logging.StreamHandler(sys.stderr)
      handler.setFormatter(logging.Formatter("%(message)s"))
      self._logger.addHandler(handler)

    self._logger.setLevel(logging.INFO)
    self._logger.propagate = False

  def _emit(
    self,
    message: str,
    *,
    level: int,
    stderr: bool = False,
  ) -> None:
    """Emit a message with the configured backend.

    Args:
      message: Message text to emit.
      level: Logging level for logger mode.
      stderr: Whether print mode should write to stderr.
    """
    if self.mode == "print":
      print(message, file=sys.stderr if stderr else sys.stdout)
      return

    self._logger.log(level, message)

  def info(self, message: str, *, stderr: bool = False) -> None:
    """Emit an informational message."""
    self._emit(message, level=logging.INFO, stderr=stderr)

  def warning(self, message: str, *, stderr: bool = True) -> None:
    """Emit a warning message."""
    self._emit(message, level=logging.WARNING, stderr=stderr)

  def error(self, message: str, *, stderr: bool = True) -> None:
    """Emit an error message."""
    self._emit(message, level=logging.ERROR, stderr=stderr)


def build_app_logger(name: str, mode: LogMode = "print") -> AppLogger:
  """Build an application logger instance.

  Args:
    name: Logger name to use in logging mode.
    mode: Output backend to use for log messages.

  Returns:
    Configured application logger.
  """
  return AppLogger(name=name, mode=mode)


def add_log_mode_argument(parser: argparse.ArgumentParser) -> None:
  """Add the shared log mode argument to a parser.

  Args:
    parser: Parser to augment.
  """
  parser.add_argument(
    "--log-mode",
    choices=LOG_MODE_CHOICES,
    default="print",
    help=(
      "How to emit script log messages: 'print' uses print statements, "
      "'logger' uses the Python logging module (default: print)"
    ),
  )
