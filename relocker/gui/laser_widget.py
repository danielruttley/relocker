import os
import time
import json
import csv
import math
import pickle
from pathlib import Path
from datetime import datetime
from pyrpl import Pyrpl
from qtpy import QtCore, QtWidgets, QtGui

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QMainWindow,QHBoxLayout,QVBoxLayout,QWidget,
                            QAction,QListWidget,QFormLayout,QComboBox,QLineEdit,
                            QTextEdit,QPushButton,QFileDialog,QAbstractItemView,
                            QListWidget,QLabel)
from functools import partial
import pyqtgraph as pg

from .helpers import QVLine, QHLine, counter_thread
from ..redpitaya import RedPitaya

class laser(QWidget):
    """Seperate control widget for each laser."""
    
    def __init__(self,main_gui,name):
        super().__init__()
        self.main_gui = main_gui

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.name = name
        self.pid_enabled = False
        self.sweep_enabled = False
        self.autorelock = False

        self.asg_trace = None
        self.input_trace = None

        self.is_locked = False
        self.is_relocking = False
        self.has_just_relocked = False
        self.last_locked_time = None

        self.prev_lock_point = None

        self.times = None
        self.asg_trace = None
        self.input_trace = None
        
        self.load_settings_from_file()
        self.ip = self.settings['ip']

        self.rp = RedPitaya(self,self.ip)

        self._create_header()
        self._create_on_off_buttons()
        self._create_horizontal_line()
        self._create_scope_graph()
        self._create_autoupdate_control()
        self._create_horizontal_line()
        self._create_locking_status()
        self._create_autorelock_control()
        self._create_horizontal_line()

        self.PISettingsButton = QPushButton("PI settings")
        self.layout.addWidget(self.PISettingsButton)

        self.sweepSettingsButton = QPushButton("Sweep settings")
        self.layout.addWidget(self.sweepSettingsButton)

        self.relockSettingsButton = QPushButton("Relock settings")
        self.layout.addWidget(self.relockSettingsButton)

        self.IOSettingsButton = QPushButton("I/O settings")
        self.layout.addWidget(self.IOSettingsButton)

        self._createActions()
        self._connectActions()

        self.set_settings()
    
    def _createActions(self):
        self.openPISettingsAction = QAction(self)
        self.openPISettingsAction.setText("Open PI settings")
        self.openSweepSettingsAction = QAction(self)
        self.openSweepSettingsAction.setText("Open sweep settings")
        self.openRelockSettingsAction = QAction(self)
        self.openRelockSettingsAction.setText("Open relock settings")
        self.openIOSettingsAction = QAction(self)
        self.openIOSettingsAction.setText("Open IO settings")

    def _connectActions(self):
        self.pid_button.clicked.connect(self.manual_set_pid_state)
        self.sweep_button.clicked.connect(self.set_sweep_state)
        self.update_graph_button.clicked.connect(self.get_scope_trace)
        self.offset_line.sigPositionChangeFinished.connect(self.update_offset_point_from_graph)
        self.offset_box.returnPressed.connect(self.update_offset_point_from_box)
        self.autoupdate_button.clicked.connect(self.set_autoupdate)
        self.relock_button.clicked.connect(self.relock)
        self.autorelock_button.clicked.connect(self.set_autorelock)
        self.PISettingsButton.clicked.connect(self.openPISettingsAction.trigger)
        self.openPISettingsAction.triggered.connect(self.open_pi_settings_window)
        self.sweepSettingsButton.clicked.connect(self.openSweepSettingsAction.trigger)
        self.openSweepSettingsAction.triggered.connect(self.open_sweep_settings_window)
        self.relockSettingsButton.clicked.connect(self.openRelockSettingsAction.trigger)
        self.openRelockSettingsAction.triggered.connect(self.open_relock_settings_window)
        self.IOSettingsButton.clicked.connect(self.openIOSettingsAction.trigger)
        self.openIOSettingsAction.triggered.connect(self.open_io_settings_window)

    def _create_log_dir(self):
        """Creates a log directory used for saving the lockbox state if it 
        doesn't already exist."""
        self.log_dir = Path.cwd()/Path("logs/"+self.name+
                                       time.strftime("/%Y/%m/%d",time.localtime()))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.log_dir/(time.strftime("%H%M%S",self.inittime)+'.csv')
    
    def _create_header(self):
        header_layout = QtWidgets.QVBoxLayout()
        laser_label = QtWidgets.QLabel("<h1>"+self.name+"</h1>")
        header_layout.addWidget(laser_label)
        self.layout.addLayout(header_layout)
        
    def _create_on_off_buttons(self):
        layout = QtWidgets.QHBoxLayout()
        self.pid_button = QtWidgets.QPushButton("PI on/off")
        self.pid_button.setCheckable(True)
        self.sweep_button = QtWidgets.QPushButton("Sweep on/off")
        self.sweep_button.setCheckable(True)
        layout.addWidget(self.pid_button)
        layout.addWidget(self.sweep_button)
        self.layout.addLayout(layout)
        
    def _create_scope_graph(self):
        layout = QtWidgets.QVBoxLayout()
        self.time_label = QtWidgets.QLabel("")
        self.update_graph_button = QtWidgets.QPushButton("update")
        self.save_trace_on_update_button = QtWidgets.QPushButton("save trace on update")
        self.save_trace_on_update_button.setCheckable(True)
        
        self.scope_plot = pg.plot(labels={'left': ('input','V'), 'bottom': ('output','V')})
        self.scope_plot.setBackground(None)
        self.scope_plot.getAxis('left').setTextPen('k')
        self.scope_plot.getAxis('bottom').setTextPen('k')
        self.scope_plot.setRange(xRange=[-1,1],yRange=[-1,1])

        self.offset_line = pg.InfiniteLine(pos=0,angle=90)
        self.offset_line.setMovable(True)
        self.offset_line.setBounds((-1,1))
        self.offset_line.setPen({'color': "#FF0000", 'width': 2})
        self.scope_plot.addItem(self.offset_line)
        
        self.last_lock_line = pg.InfiniteLine(pos=0,angle=90)
        self.last_lock_line.setMovable(False)
        self.last_lock_line.setPen({'color': "#0000FF", 'width': 2})
        self.scope_plot.addItem(self.last_lock_line)

        offset_layout = QFormLayout()
        self.offset_box = QLineEdit()
        offset_layout.addRow('manual lock point [V]', self.offset_box)
        self.offset_box.setStyleSheet("color: #ff0000")
        self.offset_box.setText(str(0))
        self.previous_lock_box = QLineEdit()
        self.previous_lock_box.setReadOnly(True)
        offset_layout.addRow('last lock point [V]', self.previous_lock_box)
        self.previous_lock_box.setStyleSheet("color: #0000ff")
        self.previous_lock_box.setText(str(0))
        
        layout.addWidget(self.time_label)
        layout.addWidget(self.scope_plot)
        layout.addWidget(self.update_graph_button)
        layout.addWidget(self.save_trace_on_update_button)
        layout.addLayout(offset_layout)
        self.layout.addLayout(layout)
        
    def _create_autoupdate_control(self):
        layout = QtWidgets.QGridLayout()
        self.autoupdate_button = QtWidgets.QPushButton("autoupdate")
        self.autoupdate_button.setCheckable(True)
        self.autoupdate_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.autoupdate_button,0,0,1,1)
        layout.addWidget(self.autoupdate_bar,0,1,1,3)
        self.layout.addLayout(layout)
        
    def _create_locking_status(self):
        layout = QtWidgets.QVBoxLayout()
        self.locked_label = QtWidgets.QLabel("<h2>Locked?</h2>")
        self.locked_label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.locked_label.setStyleSheet("background: gray")
        layout.addWidget(self.locked_label)
        self.layout.addLayout(layout)

    def _create_autorelock_control(self):
        layout = QtWidgets.QGridLayout()
        self.relock_button = QtWidgets.QPushButton("relock")
        self.autorelock_button = QtWidgets.QPushButton("autorelock")
        self.autorelock_button.setCheckable(True)
        self.relock_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.autorelock_button,0,0,1,4)
        layout.addWidget(self.relock_button,1,0,1,1)
        layout.addWidget(self.relock_bar,1,1,1,3)
        self.layout.addLayout(layout)
          
    def _create_horizontal_line(self):
        self.layout.addWidget(QHLine())

    def load_settings_from_file(self):
        """Loads a name.json file with the laser parameters from the wdir. If 
        this file doesn't exist then the default parameters are loaded. Will
        always default to having input/output off.
        """
        try:
            with open(self.name+'.json','r') as f:
                self.settings = json.load(f)
        except:
            self.settings = {}
        self.settings['name'] = self.name
        defaults = {
            "ip": "_FAKE_",
            "pid_index": 0,
            "asg_index": 0,
            "input": "off",
            "output": "off",
            "P": 0,
            "I [Hz]": 0,
            "setpoint [V]": 0,
            "offset [V]": 0,
            "integrator": 0,
            "autoupdate interval [s]": 1,
            "relock interval [s]": 1,
            "scope duration [s]": 1,
            "max voltage [V]": 1,
            "min voltage [V]": -1,
            "last lock voltage [V]": 0,
            "relock setting": "manual",
            "sweep max [V]": 1,
            "sweep min [V]": -1,
            "sweep frequency [Hz]": 50
            }
        self.settings = {**defaults, **self.settings}
        # self.settings["input"] = "off"
        # self.settings["output"] = "off"
        # if self.settings["relock setting"] == "prev":
        #     self.settings["relock setting"] = "centre"
        self.write_settings_to_file()

    def write_settings_to_file(self):
        with open(self.name+'.json','w') as f:
            json.dump(self.settings, f, sort_keys=True, indent=4)

    def open_pi_settings_window(self):
        self.pi_settings_window = PISettingsWindow(self)
        self.pi_settings_window.setWindowModality(Qt.ApplicationModal)
        self.pi_settings_window.show()  

    def open_sweep_settings_window(self):
        self.sweep_settings_window = SweepSettingsWindow(self)
        self.sweep_settings_window.setWindowModality(Qt.ApplicationModal)
        self.sweep_settings_window.show()

    def open_relock_settings_window(self):
        self.relock_settings_window = RelockSettingsWindow(self)
        self.relock_settings_window.setWindowModality(Qt.ApplicationModal)
        self.relock_settings_window.show()

    def open_io_settings_window(self):
        self.io_settings_window = IOSettingsWindow(self)
        self.io_settings_window.setWindowModality(Qt.ApplicationModal)
        self.io_settings_window.show()

    def update_io(self):
        self.io_settings_window = None
        if self.settings['ip'] != self.ip:
            self.rp = RedPitaya(self,self.settings['ip'])
        self.ip = self.settings['ip']
        self.set_settings()

    def set_settings(self,offset_override=None):
        """Gets parameters from the dictionary and refreshes 
        them in case PyRPL has invoked a value limit.
        """
        self.pi_settings_window = None
        self.sweep_settings_window = None
        self.relock_settings_window = None
        for setting in ['input','P','I [Hz]','setpoint [V]','integrator']:
            value = self.settings[setting]
            self.rp.set_pid_value(self.settings['pid_index'],setting,value)
        if self.pid_enabled:
            if offset_override is None:
                offset = self.settings['offset [V]']
            self.rp.set_asg_value(self.settings['asg_index'],'output','off')
            self.rp.set_asg_value(self.settings['asg_index'],'waveform','dc')
            self.rp.set_asg_value(self.settings['asg_index'],'offset',offset)
            self.rp.set_asg_value(self.settings['asg_index'],'amplitude',0)
            self.rp.set_asg_value(self.settings['asg_index'],'frequency',0)
            self.rp.set_asg_value(self.settings['asg_index'],'trigger','immediately')
            self.rp.set_pid_value(self.settings['pid_index'],'max',self.settings['max voltage [V]']-offset)
            self.rp.set_pid_value(self.settings['pid_index'],'min',self.settings['min voltage [V]']-offset)
            self.rp.set_asg_value(self.settings['asg_index'],'output',self.settings['output'])
            self.rp.set_pid_value(self.settings['pid_index'],'output',self.settings['output'])
        elif self.sweep_enabled:
            self.rp.set_pid_value(self.settings['pid_index'],'output','off')
            self.rp.set_asg_value(self.settings['asg_index'],'output','off')
            asg_max = min(self.settings['sweep max [V]'],self.settings['max voltage [V]'])
            asg_min = max(self.settings['sweep min [V]'],self.settings['min voltage [V]'])
            asg_offset = (asg_max+asg_min)/2
            asg_amp = abs(asg_max-asg_min)/2
            self.rp.set_asg_value(self.settings['asg_index'],'waveform','ramp')
            self.rp.set_asg_value(self.settings['asg_index'],'offset',asg_offset)
            self.rp.set_asg_value(self.settings['asg_index'],'amplitude',asg_amp)
            self.rp.set_asg_value(self.settings['asg_index'],'frequency',self.settings['sweep frequency [Hz]'])
            self.rp.set_asg_value(self.settings['asg_index'],'trigger','immediately')
            self.rp.set_asg_value(self.settings['asg_index'],'output',self.settings['output'])
        else:
            self.rp.set_pid_value(self.settings['pid_index'],'output','off')
            self.rp.set_asg_value(self.settings['asg_index'],'output','off')
        self.get_settings()
        self.write_settings_to_file()
        
    def get_settings(self):
        for setting in ['input','P','I [Hz]','setpoint [V]','integrator']:
            self.settings[setting] = self.rp.get_pid_value(self.settings['pid_index'],setting)
        if self.pid_enabled:
            self.settings['offset [V]'] = self.rp.get_asg_value(self.settings['asg_index'],'offset')
        elif self.sweep_enabled:
            self.rp.set_pid_value(self.settings['pid_index'],'output','off')
            asg_offset = self.rp.get_asg_value(self.settings['asg_index'],'offset')
            asg_amp = self.rp.get_asg_value(self.settings['asg_index'],'amplitude')
            asg_max = asg_offset + abs(asg_amp)
            asg_min = asg_offset - abs(asg_amp)
            self.settings['sweep max [V]'] = asg_max
            self.settings['sweep min [V]'] = asg_min
            self.settings['frequency [Hz]'] = self.rp.get_asg_value(self.settings['asg_index'],'frequency')

    def _set_pid_enabled(self,override=None):
        if override != None:
            self.pid_button.setEnabled(override)
            self.pid_button.setChecked(override)
            # for widget in self.pid_widgets:
            #     widget.setEnabled(override)
        else:
            self.pid_button.setEnabled(True)
            self.pid_button.setChecked(self.pid_enabled)
            # for widget in self.pid_widgets:
            #     widget.setEnabled(self.pid_enabled)
    
    def _set_pid_control_lock(self,override=None):
        if override != None:
            for widget in self.pid_widgets:
                widget.setEnabled(override)
        else:
            for widget in self.pid_widgets:
                widget.setEnabled(self.pid_controls_unlocked)
    
    def set_sweep_state(self,state=None):
        print('sweep state {}'.format(self.settings['output']))
        if state is None:
            state = self.sweep_button.isChecked()
        else:
            self.sweep_button.setChecked(state)
        if state:
            self.pid_enabled = False
            self.pid_button.setChecked(self.pid_enabled)
            self.pid_button.setEnabled(False)
        else:
            self.pid_button.setEnabled(True)
            self.pid_button.setChecked(self.pid_enabled)
        self.sweep_enabled = state
        self.set_settings()
        if state:
            self.get_scope_trace()
    
    def manual_set_pid_state(self):
        self.set_pid_state(manual_trig=True)

    def set_pid_state(self,state=None,offset_override=None,manual_trig=False):
        print('pid state, {}'.format(state))
        if state == None:
            state = self.pid_button.isChecked()
        else:
            self.pid_button.setChecked(state)
        print('output',self.settings['output'])
        if state:
            print('predump, {}'.format(manual_trig))
            self.sweep_enabled = False
            self.sweep_button.setChecked(self.sweep_enabled)
            self.sweep_button.setEnabled(False)
            self.offset_line.setMovable(False)
            self.offset_box.setReadOnly(True)
            # TODO: INSERT SOMETHING HERE TO SAVE TRACE BEFORE MANUAL LOCK WITH LOCK POINT TO TRAIN PATTERN RECOGNITION
            if manual_trig:
                print('dump')
                dump = [self.times,self.asg_trace,self.input_trace,self.settings]
                now = datetime.now() # current date and time
                filename = r'.\trace dumps\{}\manual pid enabling\{}.pickle'.format(self.name,now.strftime("%Y.%m.%d.%H.%M.%S.%f"))
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'wb') as file:
                    pickle.dump(dump,file)
        else:
            self.sweep_button.setEnabled(True)
            self.sweep_button.setChecked(self.sweep_enabled)
            self.offset_line.setMovable(True)
            self.offset_box.setReadOnly(False)
        self.pid_enabled = state
        self.set_settings(offset_override)
        self.get_scope_trace()

    def set_autorelock(self,state=None):
        if state is None:
            state = self.autorelock_button.isChecked()
        else:
            self.autorelock_button.setChecked(state)
        self.autorelock = state

    def relock(self):
        """Triggers a single relock event. Relock event will only trigger iff 
        the laser is currently not locked or relocking.
        """
        if not self.is_relocking:
            self.set_pid_state(state=False)
            self.pid_button.setEnabled(False)
            self.sweep_button.setEnabled(False)
            self.relock_thread = counter_thread(refresh_time=self.settings['relock interval [s]'])
            self.relock_thread.signal.connect(self.refresh_relock_bar)
            self.relock_thread.start()
            
    def _finish_relock(self):
        """Triggers a single relock event regardless of the locked status, but 
        will still not allow triggering if a relocking event is currently in 
        progress.
        """
        if (self.settings['relock setting'] == 'prev') and (self.prev_lock_point is not None):
            self.set_pid_state(state=True,offset_override=self.prev_lock_point)
        else:
            self.set_pid_state(state=True)
        self.pid_button.setEnabled(True)
        self.sweep_button.setEnabled(self.sweep_enabled)

    def refresh_relock_bar(self, msg):
        """Controlling function for the progress bar. When complete, progress
        bar checks that the autoupdate button is still pressed, and iff it is
        then it updates the graph.
        """
        self.relock_bar.setValue(int(msg))
        if self.relock_bar.value() >= 100:
            self.relock_bar.setValue(0)
            self._finish_relock()

    def get_scope_trace(self):
        duration = 0.1
        self.rp.queue_scope_trace(self.settings['output'],self.settings['input'],duration)

    def update_scope_trace(self,times,datas,duration):
        self.scope_plot.clear()
        self.times = times
        self.asg_trace = datas[0]
        self.input_trace = datas[1]
        self.scope_plot.plot(datas[0],datas[1], pen=pg.mkPen(color=(0,0,0),width=2))
        self.scope_plot.addItem(self.offset_line)
        self.scope_plot.addItem(self.last_lock_line)
        if self.save_trace_on_update_button.isChecked():
                dump = [self.times,self.asg_trace,self.input_trace,self.settings]
                now = datetime.now() # current date and time
                filename = r'.\trace dumps\{}\update dumps\{}.pickle'.format(self.name,now.strftime("%Y.%m.%d.%H.%M.%S.%f"))
                os.makedirs(os.path.dirname(filename), exist_ok=True)
                with open(filename, 'wb') as file:
                    pickle.dump(dump,file)
        self.check_if_locked()
        if self.pid_enabled and self.autorelock and (not self.is_locked) and (not self.is_relocking):
            self.relock()
    
    def update_offset_point_from_graph(self):
        self.settings['offset [V]'] = self.offset_line.value()
        self.offset_box.setText(str(self.settings['offset [V]']))

    def update_offset_point_from_box(self):
        self.offset_line.setValue(float(self.offset_box.text()))
        self.update_offset_point_from_graph()

    def set_autoupdate(self):
        """Controlling function for the autoupdate button. Begins the progress
        bar counting iff it does not already exist and is counting.
        """
        if self.autoupdate_button.isChecked() and self.autoupdate_bar.value() <= 0:
            self.autoupdate_thread = counter_thread(refresh_time=self.settings['autoupdate interval [s]'])
            self.autoupdate_thread.signal.connect(self.refresh_autoupdate_bar)
            self.autoupdate_thread.start()

    def refresh_autoupdate_bar(self, msg):
        """Controlling function for the progress bar. When complete, progress
        bar checks that the autoupdate button is still pressed, and iff it is
        then it updates the graph.
        """
        self.autoupdate_bar.setValue(int(msg))
        if self.autoupdate_bar.value() >= 100:
            self.autoupdate_bar.setValue(0)
            if self.autoupdate_button.isChecked():
                self.get_scope_trace()
                self.autoupdate_thread.start()

    def check_if_locked(self):
        """Attempts to determine whether the laser is locked by seeing if the 
        the mean of the output signal is within a threshold value of the 
        maximum or minimum voltage.
        """
        if not self.pid_enabled:
            self.is_locked = False
        elif (not self.is_relocking) and (not self.has_just_relocked):
            output = self.asg_trace
            output = [value for value in output if not math.isnan(value)]
            mean_voltage = sum(output)/len(output)
            max_voltage = self.settings['max voltage [V]']
            min_voltage = self.settings['min voltage [V]']
            threshold = 0.05
            #threshold = 10
            if ((abs(mean_voltage - max_voltage) < threshold) or 
                (abs(mean_voltage - min_voltage) < threshold)):
                self.is_locked = False
            else:
                self.is_locked = True
                self.last_locked_time = time.localtime()
                self.settings['last locked voltage [V]'] = mean_voltage
                self.previous_lock_box.setText(str(mean_voltage))
                self.last_lock_line.setValue(mean_voltage)
        self.update_locked_display()

    def update_locked_display(self):
        if self.is_relocking:
            self.locked_label.setText("<h2>Relocking</h2>")
            self.locked_label.setStyleSheet("background: yellow")
        elif self.has_just_relocked:
            self.locked_label.setText("<h2>Locked?</h2>")
            self.locked_label.setStyleSheet("background: gray")
            self.has_just_relocked = False
        elif self.is_locked:
            self.locked_label.setText("<h2>Locked</h2>")
            self.locked_label.setStyleSheet("background: green")
        else:
            self.locked_label.setText("<h2>Not locked</h2>")
            self.locked_label.setStyleSheet("background: red")    

class IOSettingsWindow(QWidget):
    def __init__(self,laser):
        super().__init__()

        self.laser = laser
        name = self.laser.settings['name']
        self.setWindowTitle(name+" IO settings")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self._create_inputoutput()

        self.saveButton = QPushButton("Update")
        self.layout.addWidget(self.saveButton)

        self._createActions()
        self._connectActions()

    def _create_inputoutput(self):
        layout = QtWidgets.QGridLayout()
        ip_label = QtWidgets.QLabel("IP:")
        self.ip_box = QtWidgets.QComboBox()
        self.ip_box.addItems(self.laser.main_gui.rps)
        self.input_box = QtWidgets.QComboBox()
        self.input_box.addItems(["off","in1","in2"])
        input_label = QtWidgets.QLabel("Input:")
        input_label.setStyleSheet("color: #1f77b4")
        self.output_box = QtWidgets.QComboBox()
        self.output_box.addItems(["off","out1","out2"])
        output_label = QtWidgets.QLabel("Output:")
        output_label.setStyleSheet("color: #ff7f0e")
        pid_index_label = QtWidgets.QLabel("PID index:")
        self.pid_index_box = QtWidgets.QComboBox()
        self.pid_index_box.addItems(['0','1','2'])
        asg_index_label = QtWidgets.QLabel("ASG index:")
        self.asg_index_box = QtWidgets.QComboBox()
        self.asg_index_box.addItems(['0','1'])

        max_label = QtWidgets.QLabel("max voltage [V]:")
        min_label = QtWidgets.QLabel("min voltage [V]:")
        self.max_box = QtWidgets.QLineEdit()
        self.max_box.setValidator(QtGui.QDoubleValidator())
        self.min_box = QtWidgets.QLineEdit()
        self.min_box.setValidator(QtGui.QDoubleValidator())

        layout.addWidget(ip_label,0,0,1,1)
        layout.addWidget(self.ip_box,0,1,1,3)
        layout.addWidget(input_label,1,0,1,1)
        layout.addWidget(self.input_box,1,1,1,3)
        layout.addWidget(output_label,2,0,1,1)
        layout.addWidget(self.output_box,2,1,1,3)
        layout.addWidget(pid_index_label,3,0,1,1)
        layout.addWidget(self.pid_index_box,3,1,1,3)
        layout.addWidget(asg_index_label,4,0,1,1)
        layout.addWidget(self.asg_index_box,4,1,1,3)
        layout.addWidget(max_label,5,0,1,1)
        layout.addWidget(self.max_box,5,1,1,3)
        layout.addWidget(min_label,6,0,1,1)
        layout.addWidget(self.min_box,6,1,1,3)
        self.layout.addLayout(layout)

        self.ip_box.setCurrentText(self.laser.settings['ip'])
        self.input_box.setCurrentText(self.laser.settings['input'])
        self.output_box.setCurrentText(self.laser.settings['output'])
        self.pid_index_box.setCurrentText(str(self.laser.settings['pid_index']))
        self.asg_index_box.setCurrentText(str(self.laser.settings['asg_index']))
        self.max_box.setText(str(self.laser.settings['max voltage [V]']))
        self.min_box.setText(str(self.laser.settings['min voltage [V]']))

    def _createActions(self):
        self.saveAction = QAction(self)
        self.saveAction.setText("Update")

    def _connectActions(self):
        self.saveButton.clicked.connect(self.saveAction.trigger)
        self.saveAction.triggered.connect(self.save_io_settings)
    
    def save_io_settings(self):
        self.laser.settings['ip'] = self.ip_box.currentText()
        self.laser.settings['input'] = self.input_box.currentText()
        self.laser.settings['output'] = self.output_box.currentText()
        self.laser.settings['pid_index'] = int(self.pid_index_box.currentText())
        self.laser.settings['asg_index'] = int(self.asg_index_box.currentText())
        self.laser.settings['max voltage [V]'] = float(self.max_box.text())
        self.laser.settings['min voltage [V]'] = float(self.min_box.text())
        self.laser.update_io()

class SweepSettingsWindow(QWidget):
    def __init__(self,laser):
        super().__init__()

        self.laser = laser
        name = self.laser.settings['name']
        self.setWindowTitle(name+" sweep settings")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self._create_sweep_controls()

        self.saveButton = QPushButton("Update")
        self.layout.addWidget(self.saveButton)

        self._createActions()
        self._connectActions()

    def _create_sweep_controls(self):
        layout = QtWidgets.QGridLayout()
        max_label = QtWidgets.QLabel("sweep max [V]:")
        min_label = QtWidgets.QLabel("sweep min [V]:")
        freq_label = QtWidgets.QLabel("frequency [Hz]:")
        self.sweep_max_box = QtWidgets.QLineEdit()
        self.sweep_max_box.setValidator(QtGui.QDoubleValidator())
        self.sweep_min_box = QtWidgets.QLineEdit()
        self.sweep_min_box.setValidator(QtGui.QDoubleValidator())
        self.sweep_freq_box = QtWidgets.QLineEdit()
        self.sweep_freq_box.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(max_label,0,0,1,1)
        layout.addWidget(self.sweep_max_box,0,1,1,3)
        layout.addWidget(min_label,1,0,1,1)
        layout.addWidget(self.sweep_min_box,1,1,1,3)
        layout.addWidget(freq_label,2,0,1,1)
        layout.addWidget(self.sweep_freq_box,2,1,1,3)
        self.layout.addLayout(layout)

        self.sweep_max_box.setText(str(self.laser.settings['sweep max [V]']))
        self.sweep_min_box.setText(str(self.laser.settings['sweep min [V]']))
        self.sweep_freq_box.setText(str(self.laser.settings['sweep frequency [Hz]']))

    def _createActions(self):
        self.saveAction = QAction(self)
        self.saveAction.setText("Update")

    def _connectActions(self):
        self.saveButton.clicked.connect(self.saveAction.trigger)
        self.saveAction.triggered.connect(self.save_settings)
    
    def save_settings(self):
        self.laser.settings['sweep max [V]'] = float(self.sweep_max_box.text())
        self.laser.settings['sweep min [V]'] = float(self.sweep_min_box.text())
        self.laser.settings['sweep frequency [Hz]'] = float(self.sweep_freq_box.text())
        self.laser.set_settings()

class RelockSettingsWindow(QWidget):
    def __init__(self,laser):
        super().__init__()

        self.laser = laser
        name = self.laser.settings['name']
        self.setWindowTitle(name+" relock settings")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self._create_relock_controls()
        self._create_additional_options()

        self.saveButton = QPushButton("Update")
        self.layout.addWidget(self.saveButton)

        self._createActions()
        self._connectActions()

    def _create_relock_controls(self):
        layout = QtWidgets.QGridLayout()
        relock_v_label = QtWidgets.QLabel("relock voltage")
        self.initial_relock_v_button = QtWidgets.QRadioButton("manual lock point")
        self.prev_relock_v_button = QtWidgets.QRadioButton("value at last lock")
        # self.custom_relock_v_button = QtWidgets.QRadioButton("custom [V]")
        # self.custom_relock_v_box = QtWidgets.QLineEdit()
        # self.custom_relock_v_box.setValidator(QtGui.QDoubleValidator())
        self.initial_relock_v_button.setStyleSheet("color: #ff0000")
        self.prev_relock_v_button.setStyleSheet("color: #0000ff")
        layout.addWidget(self.initial_relock_v_button,0,1,1,3)
        layout.addWidget(self.prev_relock_v_button,1,1,1,3)
        # layout.addWidget(self.custom_relock_v_button,2,1,1,1)
        # layout.addWidget(self.custom_relock_v_box,2,2,2,1)
        layout.addWidget(relock_v_label,0,0,2,1)
        self.layout.addLayout(layout)

        if self.laser.settings['relock setting'] == 'manual':
            self.initial_relock_v_button.setChecked(True)
        else:
            self.prev_relock_v_button.setChecked(True)

    def _create_additional_options(self):
        layout = QtWidgets.QFormLayout()
        self.autoupdate_duration_box = QtWidgets.QLineEdit()
        self.autoupdate_duration_box.setValidator(QtGui.QDoubleValidator())
        self.relock_duration_box = QtWidgets.QLineEdit()
        self.relock_duration_box.setValidator(QtGui.QDoubleValidator())
        self.scope_duration_box = QtWidgets.QLineEdit()
        self.scope_duration_box.setValidator(QtGui.QDoubleValidator())
        layout.addRow('autoupdate interval [s]:', self.autoupdate_duration_box)
        layout.addRow('relock interval [s]:', self.relock_duration_box)
        layout.addRow('scope duration [s]:', self.scope_duration_box)
        self.layout.addLayout(layout)

        self.autoupdate_duration_box.setText(str(self.laser.settings['autoupdate interval [s]']))
        self.relock_duration_box.setText(str(self.laser.settings['relock interval [s]']))
        self.scope_duration_box.setText(str(self.laser.settings['scope duration [s]']))

    def _createActions(self):
        self.saveAction = QAction(self)
        self.saveAction.setText("Update")

    def _connectActions(self):
        self.saveButton.clicked.connect(self.saveAction.trigger)
        self.saveAction.triggered.connect(self.save_settings)
    
    def save_settings(self):
        if self.initial_relock_v_button.isChecked():
            self.laser.settings['relock setting'] = 'manual'
        else:
            self.laser.settings['relock setting'] = 'prev'

        self.laser.settings['autoupdate interval [s]'] = float(self.autoupdate_duration_box.text())
        try:
            self.laser.autoupdate_thread.refresh_time = float(self.autoupdate_duration_box.text())
        except:
            pass
        self.laser.settings['relock interval [s]'] = float(self.relock_duration_box.text())
        self.laser.settings['scope duration [s]'] = float(self.scope_duration_box.text())
        self.laser.set_settings()

class PISettingsWindow(QWidget):
    def __init__(self,laser):
        super().__init__()

        self.laser = laser
        name = self.laser.settings['name']
        self.setWindowTitle(name+" PI settings")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self._create_pi_controls()

        self.saveButton = QPushButton("Update")
        self.layout.addWidget(self.saveButton)

        self._createActions()
        self._connectActions()

    def _create_pi_controls(self):
        layout = QtWidgets.QGridLayout()
        p_label = QtWidgets.QLabel("P:")
        i_label = QtWidgets.QLabel("I [Hz]:")
        setpoint_label = QtWidgets.QLabel("setpoint [V]:")
        int_label = QtWidgets.QLabel("integrator:")
        self.p_box = QtWidgets.QLineEdit()
        self.p_box.setValidator(QtGui.QDoubleValidator())
        self.i_box = QtWidgets.QLineEdit()
        self.i_box.setValidator(QtGui.QDoubleValidator())
        self.setpoint_box = QtWidgets.QLineEdit()
        self.setpoint_box.setValidator(QtGui.QDoubleValidator())
        self.int_box = QtWidgets.QLineEdit()
        self.int_box.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(p_label,0,0,1,1)
        layout.addWidget(self.p_box,0,1,1,3)
        layout.addWidget(i_label,1,0,1,1)
        layout.addWidget(self.i_box,1,1,1,3)
        layout.addWidget(setpoint_label,2,0,1,1)
        layout.addWidget(self.setpoint_box,2,1,1,3)
        layout.addWidget(int_label,3,0,1,1)
        layout.addWidget(self.int_box,3,1,1,3)
        self.layout.addLayout(layout)

        self.p_box.setText(str(self.laser.settings['P']))
        self.i_box.setText(str(self.laser.settings['I [Hz]']))
        self.setpoint_box.setText(str(self.laser.settings['setpoint [V]']))
        self.int_box.setText(str(self.laser.settings['integrator']))

    def _createActions(self):
        self.saveAction = QAction(self)
        self.saveAction.setText("Update")

    def _connectActions(self):
        self.saveButton.clicked.connect(self.saveAction.trigger)
        self.saveAction.triggered.connect(self.save_settings)
    
    def save_settings(self):
        self.laser.settings['P'] = float(self.p_box.text())
        self.laser.settings['I [Hz]'] = float(self.i_box.text())
        self.laser.settings['setpoint [V]'] = float(self.setpoint_box.text())
        self.laser.settings['integrator'] = float(self.int_box.text())
        self.laser.set_settings()

