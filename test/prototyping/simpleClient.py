import os
import argparse
import logging

from instrumentserver import setupLogging, logger, QtWidgets
from instrumentserver.log import LogWidget
from instrumentserver.client import QtClient
from instrumentserver.client.application import InstrumentClientMainWindow
from instrumentserver.gui.instruments import ParameterManagerGui

if __name__ == "__main__":
    cli = QtClient()
    dac1 = cli.get_instrument("dac1")


