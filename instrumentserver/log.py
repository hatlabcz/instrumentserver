"""
instrumentserver.log : Logging tools and defaults for instrumentserver.
"""

import sys
import logging
from enum import Enum, auto, unique
from html import escape

from . import QtGui, QtWidgets


@unique
class LogLevels(Enum):
    error = auto()
    warn = auto()
    info = auto()
    debug = auto()


class QLogHandler(logging.Handler):
    """A simple log handler that supports logging in TextEdit"""

    COLORS = {
        logging.ERROR: QtGui.QColor('red'),
        logging.WARNING: QtGui.QColor('orange'),
        logging.INFO: QtGui.QColor('green'),
        logging.DEBUG: QtGui.QColor('gray'),
    }

    def __init__(self, parent):
        super().__init__()
        self.widget = QtWidgets.QTextEdit(parent)
        self.widget.setReadOnly(True)
        self._transform = None

    def set_transform(self, fn):
        """fn(record, msg) -> str | {'html': str} | None"""
        self._transform = fn

    def emit(self, record):
        formatted = self.format(record)  # prefix + message
        raw_msg = record.getMessage()  # message only

        # Color for prefix (log level)
        clr = self.COLORS.get(record.levelno, QtGui.QColor('black')).name()

        if self._transform is not None:
            html_fragment = self._transform(record, raw_msg)
            if html_fragment:
                i = formatted.rfind(raw_msg)
                if i >= 0:
                    prefix = formatted[:i]
                    suffix = formatted[i + len(raw_msg):]
                else:
                    prefix, suffix = "", ""

                # Build HTML line
                html = (
                    f"<span style='color:{clr}'>{escape(prefix)}</span>"
                    f"{html_fragment}"
                    f"{escape(suffix)}"
                )
                self.widget.append(html)

                # reset char format so bold/italics don’t bleed
                self.widget.setCurrentCharFormat(QtGui.QTextCharFormat())
                self.widget.verticalScrollBar().setValue(
                    self.widget.verticalScrollBar().maximum()
                )
                return

        # fallback: original plain text path
        msg = formatted
        clr = self.COLORS.get(record.levelno, QtGui.QColor('black'))
        self.widget.setTextColor(clr)
        self.widget.append(msg)
        self.widget.verticalScrollBar().setValue(
            self.widget.verticalScrollBar().maximum()
        )


class LogWidget(QtWidgets.QWidget):
    """
    A simple logger widget. Uses QLogHandler as handler.
    The handler has the actual widget that is used to display the logs.
    """
    def __init__(self, parent=None, level=logging.INFO):
        super().__init__(parent)

        # set up the graphical handler
        fmt = logging.Formatter(
            "[%(asctime)s] [%(name)s: %(levelname)s] %(message)s",
            datefmt='%m-%d %H:%M:%S',
        )
        logTextBox = QLogHandler(self)
        logTextBox.setFormatter(fmt)
        logTextBox.setLevel(level)
        self.handler = logTextBox

        # make the widget
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(logTextBox.widget)
        self.setLayout(layout)

        # configure the logger
        self.logger = logging.getLogger('instrumentserver')

        # delete old graphical handler. however, that would allow only one
        # graphical handler per kernel. not sure i want that...?
        # for h in self.logger.handlers:
        #     if isinstance(h, QLogHandler):
        #         self.logger.removeHandler(h)
        #         h.widget.deleteLater()
        #         del h

        self.logger.addHandler(logTextBox)


def setupLogging(addStreamHandler=True, logFile=None,
                 name='instrumentserver',
                 streamHandlerLevel=logging.INFO):
    """Setting up logging, including adding a custom handler."""

    logger = logging.getLogger(name)

    for h in logger.handlers:
        logger.removeHandler(h)
        del h

    if logFile is not None:
        fmt = logging.Formatter(
            "%(asctime)s\t: %(name)s\t: %(levelname)s\t: %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        fh = logging.FileHandler(logFile)
        fh.setFormatter(fmt)
        fh.setLevel(logging.DEBUG)
        logger.addHandler(fh)

    if addStreamHandler:
        fmt = logging.Formatter(
            "[%(asctime)s] [%(name)s: %(levelname)s] %(message)s",
            datefmt='%m/%d %H:%M',
        )
        streamHandler = logging.StreamHandler(sys.stderr)
        streamHandler.setFormatter(fmt)
        streamHandler.setLevel(streamHandlerLevel)
        logger.addHandler(streamHandler)

    logger.info(f"Logging set up for {name}.")


def logger(name='instrumentserver'):
    """Get the (root) logger for the package."""
    return logging.getLogger(name)


def log(logger, message, level):
    """Simple wrapper to log messages.

    Useful when the log level is a variable.
    """
    logFuncs = {
        LogLevels.error: logger.error,
        LogLevels.warn: logger.warning,
        LogLevels.info: logger.info,
        LogLevels.debug: logger.debug,
    }
    logFuncs[level](message)
