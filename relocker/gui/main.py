import sys
import os
import threading
os.system("color")
import inspect

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QMainWindow,QHBoxLayout,QVBoxLayout,QWidget,
                            QAction,QListWidget,QFormLayout,QComboBox,QLineEdit,
                            QTextEdit,QPushButton,QFileDialog,QAbstractItemView,
                            QListWidget,QLabel)
from qtpy.QtGui import QIcon,QIntValidator,QDoubleValidator,QColor

from .laser_widget import laser
from .strtypes import error, warning, info

# Subclass QMainWindow to customize your application's main window
class MainWindow(QMainWindow):
    def __init__(self,dev_mode=False):
        super().__init__()

        self.setWindowTitle("Lockbox control")
        
        self.laser_layout = QHBoxLayout()
        centralWidget = QWidget(self)
        self.setCentralWidget(centralWidget)
        centralWidget.setLayout(self.laser_layout)

        self.lasers = []
        self.rps = ['_FAKE_']

        self.last_state_folder = '.'

        self._createActions()
        self._createMenuBar()
        self._connectActions()

        self.load_state('./default_state.txt')

    def _createActions(self):
        self.saveState = QAction(self)
        self.saveState.setText("Save state")

        self.loadState = QAction(self)
        self.loadState.setText("Load state")

        self.addRedPitaya = QAction(self)
        self.addRedPitaya.setText("Add Red Pitaya")

        self.removeRedPitayas = QAction(self)
        self.removeRedPitayas.setText("Remove Red Pitayas")
        
        self.addLaser = QAction(self)
        self.addLaser.setText("Add laser")

        self.removeLasers = QAction(self)
        self.removeLasers.setText("Remove lasers")

    def _createMenuBar(self):
        menuBar = self.menuBar()

        stateMenu = menuBar.addMenu("State")
        stateMenu.addAction(self.saveState)
        stateMenu.addAction(self.loadState)

        redPitayaMenu = menuBar.addMenu("Red Pitayas")
        redPitayaMenu.addAction(self.addRedPitaya)
        redPitayaMenu.addAction(self.removeRedPitayas)

        laserMenu = menuBar.addMenu("Lasers")
        laserMenu.addAction(self.addLaser)
        laserMenu.addAction(self.removeLasers)

    def _connectActions(self):
        self.saveState.triggered.connect(self.save_state_dialogue)
        self.loadState.triggered.connect(self.load_state_dialogue)

        self.addRedPitaya.triggered.connect(self.open_add_rp_window)
        self.removeRedPitayas.triggered.connect(self.open_remove_rps_window)
        
        self.addLaser.triggered.connect(self.open_add_laser_window)
        self.removeLasers.triggered.connect(self.open_remove_lasers_window)

    def open_add_laser_window(self):
        self.add_laser_window = AddLaserWindow(self)
        self.add_laser_window.setWindowModality(Qt.ApplicationModal)
        self.add_laser_window.show()

    def open_remove_lasers_window(self):
        self.remove_laser_window = RemoveLasersWindow(self)
        self.remove_laser_window.setWindowModality(Qt.ApplicationModal)
        self.remove_laser_window.show()

    def open_add_rp_window(self):
        self.add_rp_window = AddRPWindow(self)
        self.add_rp_window.setWindowModality(Qt.ApplicationModal)
        self.add_rp_window.show()

    def open_remove_rps_window(self):
        self.remove_rp_window = RemoveRPWindow(self)
        self.remove_rp_window.setWindowModality(Qt.ApplicationModal)
        self.remove_rp_window.show()

    def add_laser(self,name):
        self.add_laser_window = None
        new_laser = laser(self,name)
        self.lasers.append(new_laser)
        self.laser_layout.addWidget(new_laser)

    def remove_lasers(self,indices_to_delete):
        self.remove_laser_window = None
        indices_to_delete.sort(reverse=True)
        for i in indices_to_delete:
            self.lasers[i].setParent(None)
            del self.lasers[i]

    def add_rp(self,ip):
        self.add_rp_window = None
        if ip not in self.rps:
            self.rps.append(ip)

    def remove_rps(self,indices_to_delete):
        self.remove_rp_window = None
        indices_to_delete.sort(reverse=True)
        for i in indices_to_delete:
            if self.rps[i] != '_FAKE_':
                del self.rps[i]

    def save_state_dialogue(self):
        filename = QFileDialog.getSaveFileName(self, 'Save state',self.last_state_folder,"Text documents (*.txt)")[0]
        if filename != '':
            self.save_state(filename)
            self.last_state_folder = os.path.dirname(filename)
            print(self.last_state_folder)

    def load_state_dialogue(self):
        filename = QFileDialog.getOpenFileName(self, 'Load state',self.last_state_folder,"Text documents (*.txt)")[0]
        if filename != '':
            self.load_state(filename)
            self.last_state_folder = os.path.dirname(filename)

    def save_state(self,filename):
        laser_names = [x.name for x in self.lasers]
        print(laser_names)
        msg = [self.rps,laser_names]
        with open(filename, 'w') as f:
            f.write(str(msg))
        info('State saved to "{}"'.format(filename))

    def load_state(self,filename):
        try:
            with open(filename, 'r') as f:
                msg = f.read()
        except FileNotFoundError:
            error('"{}" does not exist'.format(filename))
            return
        try:
            msg = eval(msg)
            self.remove_lasers(list(range(len(self.lasers)))) 
            self.rps = msg[0]
            laser_names = msg[1]
            for name in laser_names:
                self.add_laser(name)
            info('State loaded from "{}"'.format(filename))
        except (SyntaxError, IndexError) as e:
            error('Failed to evaluate file "{}". Is the format correct?'.format(filename),e)

class AddRPWindow(QWidget):
    def __init__(self,main_window):
        super().__init__()

        self.main_window = main_window
        self.setWindowTitle("Add RedPitaya")

        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel()
        label.setText("IP:")
        layout.addWidget(label)

        self.ip_box = QLineEdit()
        self.ip_box.setText('_FAKE_')
        layout.addWidget(self.ip_box)

        self.addButton = QPushButton("Add")
        layout.addWidget(self.addButton)

        self._createActions()
        self._connectActions()
    
    def _createActions(self):
        self.addAction = QAction(self)
        self.addAction.setText("Add")

    def _connectActions(self):
        self.addButton.clicked.connect(self.addAction.trigger)
        self.addAction.triggered.connect(self.add_rp)
    
    def add_rp(self):
        ip = self.ip_box.text()
        if ip != '':
            self.main_window.add_rp(ip)

class RemoveRPWindow(QWidget):
    def __init__(self,main_window):
        super().__init__()

        self.main_window = main_window
        rps = self.main_window.rps
        self.setWindowTitle("Remove RedPitaya")

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.laser_list = QListWidget()
        self.laser_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.laser_list)

        names = []
        self.laser_list.addItems(rps)

        self.removeButton = QPushButton("Remove")
        layout.addWidget(self.removeButton)

        self._createActions()
        self._connectActions()

    def _createActions(self):
        self.removeAction = QAction(self)
        self.removeAction.setText("Remove")

    def _connectActions(self):
        self.removeButton.clicked.connect(self.removeAction.trigger)
        self.removeAction.triggered.connect(self.remove_lasers)
    
    def remove_lasers(self):
        selected_rows = [x.row() for x in self.laser_list.selectedIndexes()]
        print(selected_rows)
        self.main_window.remove_rps(selected_rows)

class AddLaserWindow(QWidget):
    def __init__(self,main_window):
        super().__init__()

        self.main_window = main_window
        self.setWindowTitle("Add laser")

        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel()
        label.setText("Laser name:")
        layout.addWidget(label)

        self.laser_name_box = QLineEdit()
        self.laser_name_box.setText('New laser')
        layout.addWidget(self.laser_name_box)

        self.addButton = QPushButton("Add")
        layout.addWidget(self.addButton)

        self._createActions()
        self._connectActions()
    
    def _createActions(self):
        self.addAction = QAction(self)
        self.addAction.setText("Add")

    def _connectActions(self):
        self.addButton.clicked.connect(self.addAction.trigger)
        self.addAction.triggered.connect(self.add_laser)
    
    def add_laser(self):
        name = self.laser_name_box.text()
        if name != '':
            self.main_window.add_laser(name)

class RemoveLasersWindow(QWidget):
    def __init__(self,main_window):
        super().__init__()

        self.main_window = main_window
        lasers = self.main_window.lasers
        self.setWindowTitle("Remove laser")

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.laser_list = QListWidget()
        self.laser_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.laser_list)

        names = []
        for laser in lasers:
            settings = laser.get_settings()
            names.append(settings['name'])
        print(names)
        self.laser_list.addItems(names)

        self.removeButton = QPushButton("Remove")
        layout.addWidget(self.removeButton)

        self._createActions()
        self._connectActions()

    def _createActions(self):
        self.removeAction = QAction(self)
        self.removeAction.setText("Remove")

    def _connectActions(self):
        self.removeButton.clicked.connect(self.removeAction.trigger)
        self.removeAction.triggered.connect(self.remove_lasers)
    
    def remove_lasers(self):
        selected_rows = [x.row() for x in self.laser_list.selectedIndexes()]
        print(selected_rows)
        self.main_window.remove_lasers(selected_rows)