import sys
import time
import json
import csv
import math
from pathlib import Path
from pyrpl import Pyrpl
from qtpy import QtCore, QtWidgets, QtGui

from qtpy.QtWidgets import QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QHLine
from functools import partial
import pyqtgraph as pg

class MainWindow(QMainWindow):
    """Main lockbox GUI class containing the different laser controls."""
    
    def __init__(self,lasers):
        super().__init__()

        # Set some main window's properties
        self.setWindowTitle('RedPitaya AutoRelocker')
        # self.resize(350, 950)
        # Set the central widget and the general layout
        self.main_layout = QVBoxLayout()
        self._centralWidget = QWidget(self)
        self.setCentralWidget(self._centralWidget)
        self._centralWidget.setLayout(self.main_layout)
        self._create_header()
        self.main_layout.addWidget(QHLine())
        self.lasers_layout = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(self.lasers_layout)
        self.lasers = {}
        index = 0
        self.lasers_layout.addWidget(QVLine())
        for laser in lasers:
            self.lasers[laser] = laser_controls(self,name=laser,index=index)
            self.lasers_layout.addWidget(QVLine())
            index += 1
        self.main_layout.addWidget(QHLine())
    
    def _create_header(self):
        """Creates overall header for the main gui."""
        header_layout = QtWidgets.QGridLayout()
        # pyrpl_gui_label = QtWidgets.QLabel("PyRPL GUI")
        self.pyrpl_gui_button = QtWidgets.QPushButton("PyRPL GUI")
        self.pyrpl_gui_button.setCheckable(True)
        # header_layout.addWidget(pyrpl_gui_label,0,0,1,3)
        header_layout.addWidget(self.pyrpl_gui_button,0,0)
        self.main_layout.addLayout(header_layout)
        

class laser_controls(QtWidgets.QMainWindow):
    """Seperate control widget for each laser."""
    
    def __init__(self,lockbox_gui,name,index):
        super().__init__()
        self.name = name
        self.index = index
        self.has_updated = False
        self.is_locked = False
        self.last_locked_time = None
        self.is_relocking = False
        self.has_relocked = False
        self.pid_controls_unlocked = False
        self.pid_enabled = False
        self.sweep_enabled = False
        self.relock_voltage = 0.5
        self.inittime = time.localtime()
        self._populate_parameters()
        self._create_log_dir()
        self.laser_layout = QtWidgets.QVBoxLayout()
        self._create_header()
        self._create_refresh_apply_buttons()
        self._create_inputoutput()
        self._create_horizontal_line()
        self._create_pid_control()
        self._create_horizontal_line()
        self._create_scope_graph()
        self._create_autoupdate_control()
        self._create_locking_status()
        self._create_autorelock_control()
        self._create_horizontal_line()
        self._create_additional_options()
        self._create_horizontal_line()
        self._create_sweep_controls()
        lockbox_gui.lasers_layout.addLayout(self.laser_layout)
        self._set_enabled(False)
        
    def _populate_parameters(self):
        """Loads a name.json file with the laser parameters from the wdir. If 
        this file doesn't exist then the default parameters are loaded. Will
        always default to having input/output off.
        """
        try:
            with open(self.name+'.json','r') as f:
                self.parameters = json.load(f)
        except:
            self.parameters = {}
        defaults = {
            "input": "off",
            "output": "off",
            "P": 0,
            "I [Hz]": 0,
            "setpoint [V]": 0,
            "integrator": 0,
            "autoupdate interval [s]": 10,
            "relock interval [s]": 1,
            "scope duration [s]": 1,
            "max voltage [V]": 1,
            "min voltage [V]": 0,
            "relock voltage [V]": 0.5,
            "relock setting": "centre",
            "sweep max [V]": 1,
            "sweep min [V]": 0,
            "sweep frequency [Hz]": 50
            }
        self.parameters = {**defaults, **self.parameters}
        self.parameters["input"] = "off"
        self.parameters["output"] = "off"
        if self.parameters["relock setting"] == "prev":
            self.parameters["relock setting"] = "centre"
        with open(self.name+'.json','w') as f:
            json.dump(self.parameters, f, sort_keys=True, indent=4)
    
    def _create_log_dir(self):
        """Creates a log directory used for saving the lockbox state if it 
        doesn't already exist."""
        self.log_dir = Path.cwd()/Path("logs/"+self.name+
                                       time.strftime("/%Y/%m/%d",time.localtime()))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = self.log_dir/(time.strftime("%H%M%S",self.inittime)+'.csv')
    
    def _create_header(self):
        header_layout = QtWidgets.QGridLayout()
        laser_label = QtWidgets.QLabel("<h1>"+self.name+"</h1>")
        self.enable_button = QtWidgets.QPushButton("enable")
        self.enable_button.setCheckable(True)
        header_layout.addWidget(laser_label,0,0,1,3)
        header_layout.addWidget(self.enable_button,0,3)
        self.laser_layout.addLayout(header_layout)
        
    def _create_inputoutput(self):
        layout = QtWidgets.QGridLayout()
        self.input_box = QtWidgets.QComboBox()
        self.input_box.addItems(["off","in1","in2"])
        input_label = QtWidgets.QLabel("Input:")
        input_label.setStyleSheet("color: #1f77b4")
        self.output_box = QtWidgets.QComboBox()
        self.output_box.addItems(["off","out1","out2"])
        output_label = QtWidgets.QLabel("Output:")
        output_label.setStyleSheet("color: #ff7f0e")
        layout.addWidget(input_label,0,0,1,1)
        layout.addWidget(self.input_box,0,1,1,3)
        layout.addWidget(output_label,1,0,1,1)
        layout.addWidget(self.output_box,1,1,1,3)
        self.laser_layout.addLayout(layout)

    def _create_pid_control(self):
        layout = QtWidgets.QGridLayout()
        pid_label = QtWidgets.QLabel("<h2>PI control</h2>")
        self.pid_button = QtWidgets.QPushButton("enable PI")
        self.pid_button.setCheckable(True)        
        self.pid_controls_button = QtWidgets.QPushButton("unlock controls")
        self.pid_controls_button.setCheckable(True)
        p_label = QtWidgets.QLabel("P:")
        i_label = QtWidgets.QLabel("I (unity-gain frequency) [Hz]:")
        setpoint_label = QtWidgets.QLabel("setpoint [V]:")
        integrator_label = QtWidgets.QLabel("integrator:")
        self.p_box = QtWidgets.QLineEdit()
        self.p_box.setValidator(QtGui.QDoubleValidator())
        self.i_box = QtWidgets.QLineEdit()
        self.i_box.setValidator(QtGui.QDoubleValidator())
        self.setpoint_box = QtWidgets.QLineEdit()
        self.setpoint_box.setValidator(QtGui.QDoubleValidator())
        self.integrator_box = QtWidgets.QLineEdit()
        self.integrator_box.setValidator(QtGui.QDoubleValidator())
        self.integrator_reset_button = QtWidgets.QPushButton("reset")
        layout.addWidget(pid_label,0,0,1,2)
        layout.addWidget(self.pid_controls_button,0,2,1,1)
        layout.addWidget(self.pid_button,0,3,1,1)
        layout.addWidget(p_label,1,0,1,1)
        layout.addWidget(self.p_box,1,1,1,3)
        layout.addWidget(i_label,2,0,1,1)
        layout.addWidget(self.i_box,2,1,1,3)
        layout.addWidget(setpoint_label,3,0,1,1)
        layout.addWidget(self.setpoint_box,3,1,1,3)
        layout.addWidget(integrator_label,4,0,1,1)
        layout.addWidget(self.integrator_box,4,1,1,2)
        layout.addWidget(self.integrator_reset_button,4,3,1,1)
        self.pid_widgets = [self.p_box,self.i_box,self.setpoint_box,
                            self.integrator_box,self.integrator_reset_button]
        self.laser_layout.addLayout(layout)
        
    def _create_refresh_apply_buttons(self):
        layout = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("refresh")
        self.apply_button = QtWidgets.QPushButton("apply")
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.apply_button)
        self.laser_layout.addLayout(layout)
        
    def _create_scope_graph(self):
        layout = QtWidgets.QVBoxLayout()
        self.time_label = QtWidgets.QLabel("")
        # self.graph_canvas = MplCanvas(self, width=4, height=2)#, dpi=100)
        # self.graph_canvas.axes.set_xlabel('time [s]')
        # self.graph_canvas.axes.plot(0,0)
        self.update_graph_button = QtWidgets.QPushButton("update")
        
        self.scope_plot = pg.plot(labels={'left': ('signal','V'), 'bottom': ('time','s')})
        self.scope_plot.setBackground(None)
        self.scope_plot.getAxis('left').setTextPen('k')
        self.scope_plot.getAxis('bottom').setTextPen('k')
        self.scope_plot.setRange(yRange=[-1,1])
        # y1 = [5, 5, 7, 10, 3, 8, 9, 1, 6, 2]
        # x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        # bargraph = pg.BarGraphItem(x = x, height = y1, width = 0.6, brush ='g')
        # scope_plot.addItem(bargraph)
        
        layout.addWidget(self.time_label)
        layout.addWidget(self.scope_plot)
        layout.addWidget(self.update_graph_button)
        self.laser_layout.addLayout(layout)
        
    def _create_autoupdate_control(self):
        layout = QtWidgets.QGridLayout()
        self.autoupdate_button = QtWidgets.QPushButton("autoupdate")
        self.autoupdate_button.setCheckable(True)
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.autoupdate_button,0,0,1,1)
        layout.addWidget(self.progress_bar,0,1,1,3)
        self.laser_layout.addLayout(layout)
        
    def _create_locking_status(self):
        layout = QtWidgets.QVBoxLayout()
        self.locked_label = QtWidgets.QLabel("<h2>Locked?</h2>")
        self.locked_label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
        self.locked_label.setStyleSheet("background: gray")
        layout.addWidget(self.locked_label)
        self.laser_layout.addLayout(layout)
    
    def _create_autorelock_control(self):
        layout = QtWidgets.QGridLayout()
        self.relock_button = QtWidgets.QPushButton("relock")
        self.autorelock_button = QtWidgets.QPushButton("autorelock")
        self.autorelock_button.setCheckable(True)
        self.relock_bar = QtWidgets.QProgressBar()
        relock_v_label = QtWidgets.QLabel("relock voltage")
        self.centre_relock_v_button = QtWidgets.QRadioButton("centre of voltage range")
        self.prev_relock_v_button = QtWidgets.QRadioButton("value at last lock")
        self.custom_relock_v_button = QtWidgets.QRadioButton("custom [V]")
        self.custom_relock_v_box = QtWidgets.QLineEdit()
        self.custom_relock_v_box.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(self.relock_button,0,0,1,4)
        layout.addWidget(self.autorelock_button,1,0,1,1)
        layout.addWidget(self.relock_bar,1,1,1,3)
        layout.addWidget(self.centre_relock_v_button,2,1,1,3)
        layout.addWidget(self.prev_relock_v_button,3,1,1,3)
        layout.addWidget(self.custom_relock_v_button,4,1,1,1)
        layout.addWidget(self.custom_relock_v_box,4,2,2,1)
        layout.addWidget(relock_v_label,2,0,3,1)
        self.laser_layout.addLayout(layout)
    
    def _create_additional_options(self):
        layout = QtWidgets.QFormLayout()
        self.autoupdate_duration_box = QtWidgets.QLineEdit()
        self.autoupdate_duration_box.setValidator(QtGui.QDoubleValidator())
        self.relock_duration_box = QtWidgets.QLineEdit()
        self.relock_duration_box.setValidator(QtGui.QDoubleValidator())
        self.scope_duration_box = QtWidgets.QLineEdit()
        self.scope_duration_box.setValidator(QtGui.QDoubleValidator())
        self.max_voltage_box = QtWidgets.QLineEdit()
        self.max_voltage_box.setValidator(QtGui.QDoubleValidator())
        self.min_voltage_box = QtWidgets.QLineEdit()
        self.min_voltage_box.setValidator(QtGui.QDoubleValidator())
        layout.addRow('autoupdate interval [s]:', self.autoupdate_duration_box)
        layout.addRow('relock interval [s]:', self.relock_duration_box)
        layout.addRow('scope duration [s]:', self.scope_duration_box)
        layout.addRow('max. voltage [V]:', self.max_voltage_box)
        layout.addRow('min. voltage [V]:', self.min_voltage_box)
        self.laser_layout.addLayout(layout)
    
    def _create_sweep_controls(self):
        layout = QtWidgets.QGridLayout()
        sweep_label = QtWidgets.QLabel("<h2>sweep control</h2>")
        self.sweep_button = QtWidgets.QPushButton("enable sweep")
        self.sweep_button.setCheckable(True)
        max_label = QtWidgets.QLabel("sweep max [V]:")
        min_label = QtWidgets.QLabel("sweep min [V]:")
        freq_label = QtWidgets.QLabel("frequency [Hz]:")
        self.sweep_max_box = QtWidgets.QLineEdit()
        self.sweep_max_box.setValidator(QtGui.QDoubleValidator())
        self.sweep_min_box = QtWidgets.QLineEdit()
        self.sweep_min_box.setValidator(QtGui.QDoubleValidator())
        self.sweep_freq_box = QtWidgets.QLineEdit()
        self.sweep_freq_box.setValidator(QtGui.QDoubleValidator())
        layout.addWidget(sweep_label,0,0,1,3)
        layout.addWidget(self.sweep_button,0,3,1,1)
        layout.addWidget(max_label,1,0,1,1)
        layout.addWidget(self.sweep_max_box,1,1,1,3)
        layout.addWidget(min_label,2,0,1,1)
        layout.addWidget(self.sweep_min_box,2,1,1,3)
        layout.addWidget(freq_label,3,0,1,1)
        layout.addWidget(self.sweep_freq_box,3,1,1,3)
        self.sweep_widgets = [self.sweep_max_box,self.sweep_min_box,
                            self.sweep_freq_box]
        self.laser_layout.addLayout(layout)
          
    def _create_horizontal_line(self):
        self.laser_layout.addWidget(QHLine())
        
    def _set_enabled(self,enabled):
        """Enables/Disables controller GUI elements."""
        if not enabled:
            self.autoupdate_button.setChecked(False)
            self._set_pid_enabled(False)
            self._set_pid_control_lock(False)
            self._set_sweep_enabled(False)
        else:
            self._set_pid_enabled()
            self._set_pid_control_lock()
            self._set_sweep_enabled()
            self.locked_label.setText("<h2>Locked?</h2>")
            self.locked_label.setStyleSheet("background: gray")
        for widget in [self.input_box,self.output_box,self.refresh_button,
                        self.apply_button,self.update_graph_button,
                        self.autoupdate_button,self.scope_duration_box,
                        self.max_voltage_box,self.min_voltage_box,
                        self.autoupdate_duration_box, self.relock_button,
                        self.autorelock_button,self.relock_duration_box,
                        self.centre_relock_v_button,self.prev_relock_v_button,
                        self.custom_relock_v_button,self.pid_controls_button]:
            widget.setEnabled(enabled)

        if self.parameters['relock setting'] != 'custom':
            self.custom_relock_v_box.setEnabled(False)
        else:
            self.custom_relock_v_box.setEnabled(True)
        if self.last_locked_time == None:
            self.prev_relock_v_button.setEnabled(False)
    
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
    
    def _set_sweep_enabled(self,override=None):
        if override != None:
            self.sweep_button.setEnabled(override)
            self.sweep_button.setChecked(override)
            for widget in self.sweep_widgets:
                widget.setEnabled(override)
        else:
            self.sweep_button.setEnabled(True)
            self.sweep_button.setChecked(self.sweep_enabled)
            for widget in self.sweep_widgets:
                widget.setEnabled(self.sweep_enabled)