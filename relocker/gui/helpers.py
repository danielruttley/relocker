"""
30/03/21 Dan Ruttley
*   UI helper objects used throughout the project.
"""

from qtpy import QtWidgets
from qtpy.QtCore import QThread, Signal

import time

class QHLine(QtWidgets.QFrame):
    "Horizontal line class used in the GUI"
    def __init__(self):
        super(QHLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.HLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)
        
class QVLine(QtWidgets.QFrame):
    "Vertical line class used in the GUI"
    def __init__(self):
        super(QVLine, self).__init__()
        self.setFrameShape(QtWidgets.QFrame.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Sunken)

class counter_thread(QThread):
    """External counter object to prevent GUI freezing before counter has 
    reached max. value.
    """
    signal = Signal(int)
    def __init__(self,refresh_time=10):
        super(counter_thread, self).__init__()
        self.refresh_time = refresh_time

    def __del__(self):
        self.wait()

    def run(self):
        for i in range(101):
            time.sleep(self.refresh_time/101)
            self.signal.emit(i)