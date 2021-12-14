# -*- coding: utf-8 -*-
"""
Luxbeam DMD commands encapulsated in worker object

Created on Wed Oct 14 10:02:27 2020

@author: Graham
"""

import socket
import struct
import numpy as np

# LABSCRIPT_DEVICES IMPORTS
from labscript_devices import labscript_device, BLACS_tab, BLACS_worker, runviewer_parser

# LABSCRIPT IMPORTS
from labscript import Device, IntermediateDevice, LabscriptError, Output, config

# BLACS IMPORTS
from blacs.tab_base_classes import Worker, define_state
from blacs.tab_base_classes import MODE_MANUAL, MODE_TRANSITION_TO_BUFFERED, MODE_TRANSITION_TO_MANUAL, MODE_BUFFERED  

from blacs.device_base_class import DeviceTab

from qtutils.qt.QtCore import *
from qtutils.qt.QtGui import *
from qtutils.qt.QtCore import pyqtSignal as Signal

#If debug mode is true, the program will print DMD replies and error messages
DEBUG = True

LocalIP = "127.0.0.1"
DMDIP = "192.168.0.10"
IP = DMDIP
#IP = LocalIP
g_nPortControl = 52985
g_nPortImage = 52986
buffersize = 1024

'''
@BLACS_tab
class LightCrafterTab(DeviceTab):
'''
class LightCrafterWorker(Worker):
    command = {'start_seq' :             b'\x01\x00',
                    'stop_seq':         b'\x01\x01',
                    'reset_seq':         b'\x01\x05',
                    'request_seq_label': struct.pack('! H H H',6, 404, 0),
                    'set_active_seq': struct.pack('! H H c', 5, 171, b'\x00'),
                    'request_seq_no_error':struct.pack('! H H', 4, 311),
                    'check_active_seq':struct.pack('! H H', 4, 371),
                    
                    }
    
    errors = {
        
        
        
        }
    
    #From seq_writer
    
    def LoopSequence(self, total_num, delay):
        seq = 'Label	start	1\n'
        seq = seq + 'AssignVar	Inum	0	1\n'
        for n in range (0, total_num):
            seq =  seq + 'LoadGlobal	Inum	140\n'
            seq = seq + 'ResetGlobal	1\n'
            seq = seq + 'Wait	' + str(delay) + '\n'
            seq = seq + 'Add	Inum	1	1\n'
        seq = seq + 'Jump	start	1'
        return(seq)
    
    def ClearSequence(self, wait_time):
        seq ='''Label	start	100
        ClearGlobal	100
        ResetGlobal	40
        Wait	''' +str(wait_time)+ '''\nJump	start	100'''
        return seq
    
    def DispSequence (self, num, wait_time=10000000):
        seq = 'Label	start	1\n'
        seq = seq + 'AssignVar	Inum	%d	1\n' %num
        seq =  seq + 'LoadGlobal	Inum	140\n'
        seq = seq + 'ResetGlobal	1\n'
        seq = seq + 'Wait	'+str(wait_time)+'\n'
        seq = seq + 'Jump	start	1\n'
        return seq
    
    #sequencer commands
    
    def SequencerStart(self):
        buf = b'\x00\x06\x00j\x01\x01'
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        if DEBUG:
            data, server = g_nSocket.recvfrom(1024)
            print('reply: %s' % data)
        
    def SequencerStop(self):
        buf = b'\x00\x06\x00j\x01\x00'
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        if DEBUG:
            data, server = g_nSocket.recvfrom(1024)
            print('reply: %s' % data)
            
    def RequestSeqLabel(self):
        buf = struct.pack('! H H H',6, 404, 0)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Sequence Label Reply: %s' % data)
        return(struct.unpack('! H H H H', data))
        
    def RequestSeqNoError(self):
        buf = struct.pack('! H H', 4, 311)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Sequence Error Num: %s' % data)
        return(struct.unpack('! H H c H', data))
    
    def SetActiveSeq(self):
        buf = struct.pack('! H H c', 5, 171, b'\x00')
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Active Sequence Reply: %s' % data)
        return(struct.unpack('! H H', data))
    
    def CheckActiveSeq(self):
        buf = struct.pack('! H H', 4, 371)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Active Sequence Reply: %s' % data)
        return(struct.unpack('! H H c', data))
    
    #misc commands
    
    def SetImType (self):
        buf = struct.pack('! H H H', 6, 67, 1)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Im Type Reply: %s' % data)
    
    def ResetNum (self):
        buf = struct.pack('! H H', 4, 112)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Reset Reply: %s' % data)
    
    def DisableSeq (self):
        buf = struct.pack('!HHH', 6, 106, 256)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Disable Reply: %s' % data)
        
    def SeqReset (self):
        buf = struct.pack('!HHH', 6, 106, 513)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Stop Reply: %s' % data)
    
    def AskBlock (self):
        buf = struct.pack('! H H', 4, 311)
        g_nSocket.sendto(buf, (DMDIP, g_nPortControl))
        data, server = g_nSocket.recvfrom(1024)
        print('Image Block Reply: %s' % data)
        return data
    
    #image handling
    
    def ImageUpload (self, arr):
        ResetNum()
        for i in range(0,180):
            #send 1440 bytes= 6 lines of image data to DMD
            g_nSocket.sendto(ImageData(i+1, 0 ,int(i*6),arr), (IP, g_nPortImage))
        struct.unpack('! H H I', AskBlock())
    
