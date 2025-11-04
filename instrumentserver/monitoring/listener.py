import zmq
import ruamel.yaml
import logging
from pathlib import Path

import datetime
import pandas as pd
import argparse
import os.path

from instrumentserver.base import recvMultipart
from instrumentserver import QtCore
from instrumentserver.blueprints import ParameterBroadcastBluePrint

from abc import ABC, abstractmethod


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Listener(ABC):
    def __init__(self, addr):
        self.addr = addr     

    def run(self):
        # creates zmq subscriber at specified address
        logger.info(f"Connecting to {self.addr}")
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(self.addr)

        # listen for everything
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        logger.info("Listener Connected")
        listen = True
        try:
            while listen:
                try:
                    # parses string message and decodes into ParameterBroadcastBluePrint
                    message = recvMultipart(socket)
                    self.listenerEvent(message[1])
                except (KeyboardInterrupt, SystemExit):
                    # exit if keyboard interrupt
                    logger.info("Program Stopped Manually")
                    raise
        finally:
            socket.close()

    @abstractmethod
    def listenerEvent(self, message: ParameterBroadcastBluePrint):
        pass

class DFListener(Listener):
    def __init__(self, addr, paramList, path):
        super().__init__(addr)
        self.addr = addr

        # checks if data file already exists
        # if it does, reads the file to make the appropriate dataframe
        if os.path.isfile(path):
            self.df = pd.read_csv(path)
            self.df = self.df.drop("Unnamed: 0", axis=1)
        else:
            self.df = pd.DataFrame(columns=["time","name","value","unit"])

        self.paramList = paramList
        self.path = path

    def run(self):
        super().run()

    def listenerEvent(self, message: ParameterBroadcastBluePrint):
        
        # listens only for parameters in the list, if it is empty, it listens to everything
        if not self.paramList:
            logger.info(f"Writing data [{message.name},{message.value},{message.unit}]")
            self.df.loc[len(self.df)]=[datetime.datetime.now(),message.name,message.value,message.unit]
            self.df.to_csv(self.path)
        elif message.name in self.paramList:
            logger.info(f"Writing data [{message.name},{message.value},{message.unit}]")
            self.df.loc[len(self.df)]=[datetime.datetime.now(),message.name,message.value,message.unit]
            self.df.to_csv(self.path)


class QtListener(QtCore.QObject):
    finished = QtCore.Signal()
    serverSignal = QtCore.Signal(object)

    def __init__(self, addr, parent=None):
        """
        Listener for server broadcast of parameter changes.
        Rewritten based on monitoring.listener.Listener without ABC for use with Qt
        :param addr: address to listen to, by default, should be main server address with port + 1
        :param parent:
        """
        super().__init__(parent)
        self.addr = addr
        self._stop = False
        self._ctx = None
        self._sock = None

    @QtCore.Slot()
    def run(self):
        logger.info(f"Connecting to {self.addr}")
        self._ctx = zmq.Context.instance()
        self._sock = self._ctx.socket(zmq.SUB)
        try:
            self._sock.connect(self.addr)
            self._sock.setsockopt_string(zmq.SUBSCRIBE, "")
            # Make recv interruptible so we can stop gracefully
            self._sock.setsockopt(zmq.RCVTIMEO, 200)  # ms
            logger.info("Listener Connected")

            while not self._stop:
                try:
                    parts = recvMultipart(self._sock)  # e.g. [topic, payload, ...]
                    payload = parts[1] if len(parts) > 1 else parts[0]
                    self.listenerEvent(payload)
                except zmq.Again:
                    # timeout -> loop to check _stop
                    continue
                except (KeyboardInterrupt, SystemExit):
                    logger.info("Program Stopped Manually")
                    break
        finally:
            try:
                if self._sock is not None:
                    self._sock.close(linger=0)
            finally:
                self._sock = None
            self.finished.emit()

    @QtCore.Slot()
    def stop(self):
        self._stop = True

    def listenerEvent(self, message: ParameterBroadcastBluePrint):
        self.serverSignal.emit(message)


def loadConfig(path):

    # load config file contents into data
    path = Path(path)
    yaml = ruamel.yaml.YAML(typ='safe')
    data = yaml.load(path)

    # extract address from data
    if 'address' in data:
        addr = data.get('address')
    if 'params' in data:
        paramList = data.get('params')
    if 'csv_path' in data:
        csvPath = data.get('csv_path')
    if 'listener_type' in data:
        type = data.get('listener_type')

    return addr, paramList, csvPath, type
    
def startListener():

    parser = argparse.ArgumentParser(description='Starting the listener')
    parser.add_argument("-c", "--config")
    args = parser.parse_args()

    configPath = Path(args.config)

    # Load variables from config file
    if configPath != '' and configPath is not None:
        addr, paramList, csvPath, type = loadConfig(configPath)
    else:
        logger.info("please enter a valid path for the config file")
        return 0

    #start listener that writes to CSV
    if type == "CSV":
        if addr is not None and paramList is not None and csvPath is not None:
            CSVListener = DFListener(addr, paramList, csvPath)
            CSVListener.run()
        else:
            logger.info("Make sure to fill out all fields in config file")
    else:
        logger.info(f"Type {type} not supported")