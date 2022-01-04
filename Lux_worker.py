# -*- coding: utf-8 -*-
"""
Luxbeam DMD commands encapulsated in worker object

Created on Wed Oct 14 10:02:27 2020

@author: Graham
"""

import socket
import struct
import numpy as np

import base64
import os
import PIL.Image

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

def arr_to_bmp(arr):
    """Convert array to 1 bit BMP, white wherever the array is nonzero, and return a
    bytestring of the BMP data"""
    binary_arr = 255 * (arr != 0).astype(np.uint8)
    im = PIL.Image.fromarray(binary_arr, mode='L').convert('1')
    f = BytesIO()
    im.save(f, "BMP")
    return f.getvalue()

WIDTH = 1920
HEIGHT = 1080

BLANK_BMP = arr_to_bmp(np.zeros((HEIGHT, WIDTH)))

#from labsript lighcrafter DMD

class LuxbeamrDMD(IntermediateDevice):
    description = 'Luxbeam DMD controller'
    allowed_children = [ImageSet]
    

    max_instructions = 96
    clock_limit = 4000
    width = WIDTH
    height = HEIGHT
    
    def __init__(self, name, parent_device, server = '192.168.1.100', port=21845):
        IntermediateDevice.__init__(self, name, parent_device)
        self.BLACS_connection = '%s:%d'%(server, port)
        
    def add_device(self, device):        
        # run checks
        
        # if the device passes the checks, call the parent class function to add it as a child
        Device.add_device(self, device)
        
        device.width = self.width
        device.height = self.height
                
    def generate_code(self, hdf5_file):
       
        if len(self.child_devices) > 1:
            raise LabscriptError("More than one set of images attached to the Luxbeam")
        output = self.child_devices[0]
        if len(output.raw_output) > self.max_instructions:
            raise LabscriptError("Too many images for the Luxbeam. Your shot contains %s images"%len(output.raw_output))
          
        # Apparently you should use np.void for binary data in a h5 file. Then on the way out, we need to use data.tostring() to decode again.
        out_table = np.void(output.raw_output)
        grp = self.init_device_group(hdf5_file)
        grp.create_dataset('IMAGE_TABLE',compression=config.compression,data=out_table)

class ImageSet(Output):
    description = 'A set of images to be displayed on an SLM or DMD'
    width = WIDTH
    height = HEIGHT
    # Set default value to be a black image. Here's a raw BMP!
    default_value = BLANK_BMP
    """bytes: A black image.
    Raw bitmap data hidden from docs.
    :meta hide-value:
    """
    
    def __init__(self, name, parent_device, connection = 'Mirror'):
        Output.__init__(self, name, parent_device, connection)
        
    def set_array(self, t, arr):
        self.set_image(t, raw=arr_to_bmp(arr))
         
    def set_image(self, t, path=None, raw=None):
        """set an image at the given time, either by a filepath to a bmp file,
        or by a bytestring of bmp data"""
        if raw is not None:
            raw_data = raw
        else:
            if not os.path.exists(path):
                raise LabscriptError('Cannot load the image for DMD output %s (path: %s)'%(self.name, path))
            # First rough check that the path leads to a .bmp file
            if len(path) < 5 or path[-4:] != '.bmp':
                raise LabscriptError('Error loading image for DMD output %s: The image does not appear to be in bmp format(path: %s) Length: %s, end: %s'%(self.name, path, len(path),path[-4:] ))
            with open(path, 'rb') as f:
                raw_data = f.read()
        # Check that the image is a BMP, first two bytes should be "BM"
        if raw_data[0:2] != b"BM":
            raise LabscriptError('Error loading image for DMD output %s: The image does not appear to be in bmp format(path: %s)'%(self.name, path))
        # Check the dimensions match the device, these are stored in bytes 18-21 and 22-25
        width = struct.unpack("<i",raw_data[18:22])[0]
        height = struct.unpack("<i",raw_data[22:26])[0]
        
        if width != self.width or height != self.height:
            raise LabscriptError('Image %s (for DMD output %s) has wrong dimensions. Image dimesions were %s x %s, expected %s x %s'%(path, self.name, width, height, self.width, self.height))
        
        bitdepth = struct.unpack("<h", raw_data[28:30])[0]
        if bitdepth != 1:
            raise LabscriptError("Your image %s is bitdepth %s, but it needs to be 1 for DMD output %s. Please re-save image in appropriate format."%(path,bitdepth,self.name))
        self.add_instruction(t, raw_data)
            
    def expand_timeseries(self,all_times):
        """We have to override the usual expand_timeseries, as it sees strings as iterables that need flattening!
        Luckily for us, we should only ever have individual data points, as we won't be ramping or anything,
        so this function is a lot simpler than the original, as we have more information about the output.
        
        Not 100% sure that this is enough to cover ramps on other devices sharing the clock, come here if there are issues!
        """
        
        self.raw_output = np.array(self.timeseries)
        return

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
    
    errors = {}

    def init(self):
        global socket; import socket
        global struct; import struct
        self.host, self.port = self.server.split(':')
        self.port = int(self.port)
        self.smart_cache = {'IMAGE_TABLE': ''}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host,self.port))
        # Initialise it to a static image display
        #self.send(self.send_packet_type['write'], self.command['display_mode'], self.display_mode['static'])
        
        # self.program_manual({"None" : base64.b64encode(blank_bmp)})
    
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
    
