"""
30/03/21 Dan Ruttley
*   Python package to interface with a RedPitaya using PyRPL. This package
    handles any reads or writes to the state of the RedPitaya.
"""

import time
import queue
from pyrpl import Pyrpl
from qtpy import QtCore, QtTest

class RedPitaya():
    """Wrapper class to make PyRPL functions easily accessible"""
    
    def __init__(self,laser,hostname,config='relocker',gui=False):
        self.laser = laser
        self.p = Pyrpl(hostname=hostname,config=config,gui=gui)#,modules=[])
        # self.p.hide_gui()
        self.rp = self.p.rp
        self.scope = self.rp.scope
        
        self.scope_queue = queue.Queue()
        self.scope_queue_wait = QtCore.QWaitCondition()
        self.scope_queue_mutex = QtCore.QMutex()
        self.scope_queuer = ScopeQueuer(self.scope_queue,self.scope_queue_wait,self.scope_queue_mutex)
        self.scope_queuer.start()
        #self.scope_queuer.signal.connect(partial(self.set_scope_duration))
        self.scope_queuer.signal.connect(self.get_scope_trace) 
        #self.relock_thread.start()
    
    def hide_gui(self):
        self.p.hide_gui()
    
    def show_gui(self):
        self.p.show_gui()
    
    def get_pid_value(self,index,setting):
        """Passes a pid value from PyRPL."""
        print('index',index)
        if index == 0:
            pid = self.rp.pid0
        elif index == 1:
            pid = self.rp.pid1
        elif index == 2:
            pid = self.rp.pid2
        else:
            print("RP does not support pid > 2")
        if setting == 'P':
            return pid.p
        elif setting == 'I [Hz]':
            return pid.i
        elif setting == 'setpoint [V]':
            return pid.setpoint
        elif setting == 'integrator':
            return pid.ival
        elif setting == 'input':
            return pid.input
        elif setting == 'output':
            return pid.output_direct
        elif setting == 'max':
            return pid.max_voltage
        elif setting == 'min':
            return pid.min_voltage
    
    def set_pid_value(self,index,setting,value):
        """Passes a pid value to PyRPL, then requests the value back before
        returning it (in case PyRPL has rounded it etc.)
        """
        print('index',index)
        if index == 0:
            pid = self.rp.pid0
        elif index == 1:
            pid = self.rp.pid1
        elif index == 2:
            pid = self.rp.pid2
        else:
            print("RP does not support pid > 2")
        if setting == 'P':
            pid.p = value
        elif setting == 'I [Hz]':
            pid.i = value
        elif setting == 'setpoint [V]':
            pid.setpoint = value
        elif setting == 'integrator':
            pid.ival = value
        elif setting == 'input':
            pid.input = value
        elif setting == 'output':
            pid.output_direct = value
        elif setting == 'max':
            pid.max_voltage = value
        elif setting == 'min':
            pid.min_voltage = value
        elif setting == 'trigger':
            pid.trigger_source = value
        return self.get_pid_value(index,setting)
    
    def get_asg_value(self,index,setting):
        """Passes a pid value from PyRPL."""
        if index == 0:
            asg = self.rp.asg0
        elif index == 1:
            asg = self.rp.asg1
        else:
            print("RP does not support asg > 1")
        if setting == 'offset':
            return asg.offset
        elif setting == 'amplitude':
            return asg.amplitude
        elif setting == 'frequency':
            return asg.frequency
        elif setting == 'waveform':
            return asg.waveform
        elif setting == 'output':
            return asg.output_direct
        elif setting == 'trigger':
            return asg.trigger_source
    
    def set_asg_value(self,index,setting,value):
        """Passes a pid value to PyRPL, then requests the value back before
        returning it (in case PyRPL has rounded it etc.)
        """
        if index == 0:
            asg = self.rp.asg0
        elif index == 1:
            asg = self.rp.asg1
        else:
            print("RP does not support asg > 1")
        if setting == 'offset':
            asg.offset = value
        elif setting == 'amplitude':
            asg.amplitude = value
        elif setting == 'frequency':
            asg.frequency = value
        elif setting == 'waveform':
            asg.waveform = value
        elif setting == 'output':
            asg.output_direct = value
        return self.get_asg_value(index,setting)

    def queue_scope_trace(self,input1,input2,duration,mode='rolling',trigger='immediately'):
        """Adds a scope trace request to the scope_getter worker queue.
        scope_parameters = []"""
        scope_parameters = [input1,input2,duration,mode,trigger]
        print('requesting scope trace',scope_parameters)
        self.scope_queue.put(scope_parameters)
        
    def get_scope_trace(self,scope_parameters):
        input1,input2,duration,mode,trigger = scope_parameters
        self.scope.input1 = input1
        self.scope.input2 = input2
        self.scope.duration = duration
        duration = self.scope.duration
        self.scope.trigger = trigger
        if mode == 'rolling':
            QtTest.QTest.qWait(duration*1000)
            times, datas = self.scope._get_rolling_curve()
            print('delivering scope trace',scope_parameters)
            self.laser.update_scope_trace(times,datas,duration)
        self.scope_queue_wait.wakeAll()
        #TODO Add other scope mode functionality

class ScopeQueuer(QtCore.QThread):
    """Worker that handles scope requests by reading from a queue 
    and then requesting that the main thread updates the scope parameters. 
    It then blocks until a signal is recieved for it to proceed.
    """
    signal = QtCore.Signal(object)
    def __init__(self,queue,wait_condition,mutex):
        super().__init__()
        self.queue = queue
        self.wait_condition = wait_condition
        self.mutex = mutex

    def __del__(self):
        self.wait()

    def run(self):
        while True:
            scope_parameters = self.queue.get()
            input1,input2,duration,mode,trigger = scope_parameters
            self.signal.emit(scope_parameters)
            self.mutex.lock()
            self.wait_condition.wait(self.mutex)
            self.mutex.unlock()
            self.queue.task_done()
            
if __name__ == "__main__":
    pass
