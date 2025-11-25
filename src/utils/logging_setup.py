"""Logging configuration utilities."""

import logging as std_logging

import colorlog


def setup_colored_logging() -> None:
  """Configure colored logging output for the application."""
  handler = colorlog.StreamHandler()
  handler.setFormatter(
    colorlog.ColoredFormatter(
      "%(log_color)s%(levelname).1s%(asctime)s.%(msecs)03d %(process)d [%(filename)s:%(lineno)d]%(reset)s %(message)s",
      datefmt="%m%d %H:%M:%S",
      log_colors={
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red,bg_white",
      },
    )
  )

  logger = std_logging.getLogger()
  logger.handlers = []
  logger.addHandler(handler)
  logger.setLevel(std_logging.INFO)
