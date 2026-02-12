# !/usr/bin/env python2.6
#  dongle.py
#  Copyright (c) 2010 Sifteo. All rights reserved.

import os, sys, platform
import time
import struct
import ctypes
import threading, Queue

VENDOR_ID  = 0x22FA
PRODUCT_ID = 0x0101
MAX_RX_Q_SIZE = 5000

USB_DONGLE_ADDRESS = 0xff
USB_MSG_LEN = 33
MAX_SEND_ATTEMPTS = 10


if (sys.platform.startswith("win")):
    INFINITE = -1
    REL_LIB_PATH = "sifthid"
else:
    REL_LIB_PATH = "sift_dongle_lib.so"
    INFINITE = 10000

SIFT_USB_LIBRARY = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath( __file__ )), REL_LIB_PATH))
SIFTLIB = ctypes.CDLL(SIFT_USB_LIBRARY)


class SiftHidDevice(threading.Thread):

    def __init__(self, parent, siftlib):
        threading.Thread.__init__(self)
        self.parent = parent
        self.devidx = -1
        self.daemon = True
        self.siftlib = siftlib
        
    def open(self, vid, pid):
        if self.is_open():
            return True
        d = self.siftlib.sift_hid_open(1, vid, pid, 0x0, 0x0)
        if (d == 1):
            self.devidx = d - 1
            return True
        else:
            return False
            
    def is_open(self):
        return (self.devidx >= 0)
    
    def close(self):
        if self.is_open():
            self.siftlib.sift_hid_close(self.devidx)
            self.devidx = -1
            
    def cancel(self):
        self.siftlib.sift_hid_cancel(self.devidx)
        
    def write(self, msg):
        return (self.siftlib.sift_hid_send(self.devidx, msg, len(msg), INFINITE) > 0)
        
    def txPacketSize(self):
        return self.siftlib.sift_hid_tx_packet_size(self.devidx)
        
    def rxPacketSize(self):
        return self.siftlib.sift_hid_rx_packet_size(self.devidx)
    
    def run(self):
        buf = ctypes.create_string_buffer(chr(0) * USB_MSG_LEN)
        while (1):
            if self.is_open():
                resp = self.siftlib.sift_hid_recv(self.devidx, buf, USB_MSG_LEN, INFINITE)
                if resp > 0:
                    data = [ord(r) for r in buf]
                    if data[1] == USB_DONGLE_ADDRESS: 
                        # message response from dongle
                        # print "rsp", data
                        self.parent.resq.put(data)
                    else:            
                        # event from siftable
                        # print "rcv", data
                        self.parent.eventq.put(data)
                elif resp < 0:
                    # print "read failed"
                    # TODO - figure out why first read fails
                    self.close()
                # else:
                #     print "timeout"

class Dongle(object):
    
    def __init__(self, vid = VENDOR_ID, pid = PRODUCT_ID, siftlib = SIFTLIB, eventq=Queue.Queue(MAX_RX_Q_SIZE)):
        """
        Creates a dongle object, already connected. Throws a
        ConnectionError if it can't connect.

        Keyword arguments:
        eventq -- optional Queue object for incoming events to be stored in.

        """
        self.resq = Queue.Queue(MAX_RX_Q_SIZE)
        self.eventq = eventq
        self._hid = SiftHidDevice(self, siftlib)
        if self._hid.open(vid, pid):
            self._hid.start()
        else:
            raise ConnectionError("Could not open dongle")
            
    def close(self):
        """Closes the dongle connection."""
        self._hid.close()
        
    def cancel(self):
        """
        Cancels the dongle
        TODO - please document further?
        """
        self._hid.cancel()
    
    def is_open(self):
        """Reports the current state of the dongle connection."""

        return self._hid.is_open()
        
    def txPacketSize(self):
        return self._hid.txPacketSize()
        
    def rxPacketSize(self):
        return self._hid.rxPacketSize()

    def get_event(self, timeout=False):
        """
        Gets the next event message from the dongle's internal queue.
        
        Keyword arguments:
        timeout -- time to block waiting for event. Defaults to False, meaning
                   returns immediately.
        
        """
        try:
            if timeout is not False:
                return self.eventq.get(True, timeout)
            else:
                return self.eventq.get(timeout)
        except Queue.Empty:
            return None
    
    def write_msg(self, data, sync=20):
        """
        Writes a message to a connected dongle. 
        
        Keyword arguments:
        data -- iterable array of numbers [msglen, msgid, |addr, op, payload|, padding],
                where msglen is the length of the message to be sent (inner pipes),
                and padding is to 32 bytes.

        """
        # print "snd", data
        msg = "".join([chr(x) for x in data])
        return self.__write(msg, sync)

    def __get_response(self, timeout):
        """
        Reads the next dongle response from the queue. Optional timeout
        """
        
        try:
            return self.resq.get(True, timeout)
        except Queue.Empty:
            print "timed out waiting for write response!"
            return None

    def __write(self, msg, sync):
        if msg.__class__ is not str:
            print "not writing"
            return False
        v = self._hid.write(msg)
        if sync is not None:
            response = self.__get_response(sync)
            if not response:
                return False
            elif response[1] == USB_DONGLE_ADDRESS:
                return response
            elif response[4] != 0:
                raise WriteError("Message write failed", response)
            return True
        else:
            return (v > 0)

class DongleError(Exception):
    pass

class ConnectionError(DongleError):
    pass

class CommunicationError(DongleError):
    
    def __init__(self, msg, data):
        DongleError.__init__(self, msg)
        self.data = data

class WriteError(CommunicationError):
    pass

class ReadError(CommunicationError):
    pass

