# !/usr/bin/env python2.6
#
#  connector.base
#
#  Copyright (c) 2010 Sifteo. All rights reserved.
#

import usb.dongle
import sys
from message import Message
from error import ConnectorError

class USBConnector():
    '''Abstracted connector. Takes a handler object as argument'''

    def __init__(self):
        self.connected = False

    def connect(self, dongle=None):
        '''
        Connect to the dongle. Spawns another process.
        '''
        try:
            if dongle:
                self.dongle = dongle
            else:
                self.dongle = usb.dongle.Dongle()
            self.connected = True
        except Exception, msg:
            self.connected = False
        return self.connected

    def is_connected(self):
        return self.connected and self.dongle.is_open()

    def disconnect(self):
        """
        Tells the send/receive process to stop, then waits for it.
        """
        self.dongle.close()

    def receive(self):
        """
        Pulls from the queue regular receive queue
        """
        m = self.dongle.get_event()
        if m:
            return Message.construct(*m)

    def send(self, op_id, address, *args):
        """
        Inserts into the send queue to await dispatch.
        """
        cmd = [op_id, address, 0] + list(args)
        while (len(cmd) < usb.dongle.USB_MSG_LEN):
            cmd.append(0)
        ret = self.dongle.write_msg(cmd)
        if type(ret) is list:
            return Message.construct(*ret)
        
    def send_and_receive(self, op_id, address, *args):
        return self.send(op_id, address, *args)
        
    def flush(self):
        """
        Empties out the send queue
        """
        pass

        
def main(dongleid): # pragma: no cover

    print "dongle loop........."    
    c = USBConnector()
    c.connect()
    d = c.dongle
    color = 0

    def inc(val):
        val = val + 1
        if val > 255:
            val = 0
        return val

    while (c.is_open()):
        try:
            # print type(c.send_and_receive(1, 0))
            color = inc(color)
            f = [83, 1, 0, 1, color, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            c.send(83, 1, color)
            c.send(81, 1)

            evt = c.receive()
            if evt:
                print evt.op_id

        except(KeyboardInterrupt):
            print "closing!"
            c.disconnect()
            sys.exit(0)


if __name__ == '__main__': # pragma: no cover
    id = 1
    if (len(sys.argv) > 1):
        id = int(sys.argv[1])
    print "starting with dongle: " + str(id)
    main(id)
