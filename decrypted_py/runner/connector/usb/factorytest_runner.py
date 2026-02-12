# !/usr/bin/env python2.6
#  dongle.py
#  Copyright (c) 2010 Sifteo. All rights reserved.

import serial
from dongle import Dongle
import os, sys, time
import csv
from datetime import datetime, timedelta


####################################################################################################
##
##                FACTORY TEST RUNNER
##
##    Overview:
##      Each test is a method on the test runner class.
##      The return value of each test method (must be either bool or list) is written 
##      to the CSV log of test results.
##
####################################################################################################


TESTRUNNER_VERSION = 100

COUNT       = 0
FAILS       = 1
TEST_PREFIX = 0xBF
RF_CHANNEL  = 40
RF_PIPE     = 0
RF_POWER    = 3 # this is max power for nordics
RF_RETRIES  = 5

DUMMY_MSGID           = 0
HEADER_PACKET_SIZE    = 11
INBOX_PAYLOAD_LENGTH  = 28
TOTAL_PACKET_SIZE     = 32
DNGL_RESPONSE_IDX     = 3

TEST_RF_SETUP =      0x50
TEST_RF_TX =         0x51
TEST_RF_RX =         0x52
TEST_RF_RX_CANCEL =  0x53

TEST_RF_TX_MAX_TIME = 10 * 1000

NEIGHBOR_DEPARTED_ID = 254

ACCEL_ORIENTATION_NEUTRAL = 1
ACCEL_ORIENTATION_X_NORTH = 2
ACCEL_ORIENTATION_X_SOUTH = 3
ACCEL_ORIENTATION_Y_NORTH = 4
ACCEL_ORIENTATION_Y_SOUTH = 5

RED =   200
GREEN = 121
BLUE =  111

def sendDongleMsg(d, m):
    while len(m) < TOTAL_PACKET_SIZE:
        m.append(0)
    d.write_msg(m, False)
    return d.get_event()

def startSiftTxTest(d, iterations):
    return sendDongleMsg(d, [TEST_PREFIX, 2, TEST_RF_TX, iterations])
    
def stopSiftTxTest(d):
    return sendDongleMsg(d, [TEST_PREFIX, 1, TEST_RF_RX_CANCEL])
    
def startSiftRxTest(d, iterations):
    return sendDongleMsg(d, [TEST_PREFIX, 2, TEST_RF_RX, iterations])
        
def dongleSetupRadioTests(d):
    return sendDongleMsg(d, [TEST_PREFIX, 5, TEST_RF_SETUP, RF_CHANNEL, RF_PIPE, RF_POWER, RF_RETRIES])

def getManualResponse(msg):
    res = raw_input(msg + "(y/n) ")
    return res.lower().startswith("y")
    
class TestRunner(object):
    
    def __init__(self, comport, neighborjig_comport):
        self.ser = serial.Serial(port = comport, baudrate = 115200, timeout = 5)
        
        try:
            self.ser_jig = serial.Serial(port = neighborjig_comport, baudrate = 115200, timeout = 5)
        except:
            self.ser_jig = None
            print "could not open serial port to neighbor jig"
            
        try:
            print "trying dongle"
            self.dongle = Dongle()
        except:
            print "did not find the dongle!"
            self.dongle = None
        
        self.stats = [0, 0]
        
        UID_OPCODE = 0x24
        self.ser.write(chr(TEST_PREFIX))  # always the first byte of any test
        self.ser.write(chr(1))            # msg length (including opcode)
        self.ser.write(chr(UID_OPCODE))   # opcode
        uid = self.uniqueIDTest(UID_OPCODE)
        
        self.filename = "%s-%s.csv" % (uid, datetime.now().strftime("%d-%m-%Y_%H-%M"))
        self.csvlog = csv.writer(open(self.filename, "w"))
        self.csvlog.writerow(["TESTRUNNER_VERSION", str(TESTRUNNER_VERSION)])
        self.csvlog.writerow(["DATE", str(datetime.now())])
        self.csvlog.writerow(["uniqueIDTest", uid])
    
    def run(self, test, serial, opcode, length, *args):
        self.stats[COUNT] = self.stats[COUNT] + 1
        for c in [TEST_PREFIX, length, opcode]: # send the header
            serial.write(chr(c))
        
        # run the test, if we don't get a list back, turn it into a list
        # the first element in the results must be a bool for success
        # insert the test's name into the results and write it to our CSV log
        results = test(opcode, *args)
        if type(results) != list:
            results = [results]
        if results[0] is not True:
            self.stats[FAILS] = self.stats[FAILS] + 1
            print "failed opcode: 0x%X" % (opcode)
        results.insert(0, test.__name__)
        self.csvlog.writerow(results)
        self.ser.flushInput() # make sure any bad tests don't screw up subsequent runs
            
    def done(self):
        print "all done!, ran %d tests, with %d fail(s)" % (self.stats[COUNT], self.stats[FAILS])
        print "wrote results to", self.filename
    
    def getResponseHeader(self, opcode, serial = None):
        if serial is None:
            serial = self.ser
        tcode = ord(serial.read())  # meta test opcode
        length = ord(serial.read())    # length
        op = ord(serial.read())        # opcode
        if op != opcode or tcode != TEST_PREFIX:
            print "unexpected header - tcode: 0x%X length: %d op: 0x%X (expected 0x%X)" % (tcode, length, op, opcode)
            return -1
        else:
            return length - 1 # we already slurped out the opcode
        
    
    def runTests(self):
        
        self.run(self.serialCommsTest,       self.ser, 0x20, 2)
        self.run(self.nrfCommsTest,          self.ser, 0x21, 1)
        self.run(self.flashCommsTest,        self.ser, 0x22, 1)
        self.run(self.accelCommsTest,        self.ser, 0x23, 1)
        self.run(self.lcdBorderTest,         self.ser, 0x40, 2)
        self.run(self.lcdEvenRowTest,        self.ser, 0x41, 1)
        self.run(self.lcdOddRowTest,         self.ser, 0x42, 1)
        self.run(self.lcdEvenColumnTest,     self.ser, 0x43, 1)
        self.run(self.lcdOddColumnTest,      self.ser, 0x44, 1)
        self.run(self.lcdFillTest,           self.ser, 0x45, 2, GREEN)
        self.run(self.lcdFillTest,           self.ser, 0x45, 2, RED)
        self.run(self.lcdFillTest,           self.ser, 0x45, 2, BLUE)
        self.run(self.lcdBacklightOffTest,   self.ser, 0x47, 1)
        self.run(self.lcdBacklightOnTest,    self.ser, 0x46, 1)
        self.run(self.accelValuesTest,       self.ser, 0x90, 1)
        self.run(self.pgoodTest,             self.ser, 0x32, 1)
        self.run(self.chgSTest,              self.ser, 0x33, 1)
        self.run(self.accelCalibrateTest,    self.ser, 0x91, 2, ACCEL_ORIENTATION_NEUTRAL)
        for orientation in [ACCEL_ORIENTATION_X_NORTH, ACCEL_ORIENTATION_X_SOUTH, ACCEL_ORIENTATION_Y_NORTH, ACCEL_ORIENTATION_Y_SOUTH]:
            self.run(self.accelCalibrateTest,    self.ser, 0x91, 2, orientation)
            self.run(self.accelOrientationTest,  self.ser, 0x92, 2, orientation)
        self.run(self.accelRelativeOrientationTest, self.ser, 0x93, 1)

        self.run(self.initButtonTestMode,    self.ser, 0x70, 1)
        self.waitForButtonPress()
        time.sleep(0.5)
        self.ser.flush() # sometimes we get spurious button pushes
        self.run(self.cancelButtonTestMode,  self.ser, 0x71, 1)
        
        oldtimeout = self.ser.timeout
        self.ser.timeout = 30 # we have to set this pretty high because the SPI flash sector erases take FOREVER
        print "running flash read/write test, takes a while..."
        self.run(self.flashReadWrite,         self.ser, 0xB0, 1)
        self.ser.timeout = oldtimeout
        
        ############################
        ## BLOCK NEIGHBOR TX TEST ##
        ############################
        # SIFT_NBR_ID = 2
        # JIG_NBR_ID  = 1
        # self.run(self.neighborsSetID,               self.ser,     0x82, 2, self.ser, JIG_NBR_ID)
        # self.run(self.neighborsSetID,               self.ser_jig, 0x82, 2, self.ser_jig, SIFT_NBR_ID)
        # # make sure TX is off, then turn on rx and make sure it notices the arrival
        # self.run(self.neighborsDisableTx,           self.ser,     0x80, 1, self.ser)
        # self.run(self.neighborsDisableTx,           self.ser_jig, 0x80, 1, self.ser_jig)
        # time.sleep(0.5) # make sure it's fully disabled before turning on reporting
        # self.run(self.neighborsEnableEvtReport,     self.ser_jig, 0x83, 1, self.ser_jig)
        # self.run(self.neighborsEnableTx,            self.ser,     0x81, 1, self.ser)
        # # TODO - need a way to know which sides are matched up with which
        # for i in xrange(4):
            # self.waitForNeighborEvt(self.ser_jig, SIFT_NBR_ID)
            
        # print "waiting to make sure we don't get spurious events while connected"
        # time.sleep(5)
        # avail = self.ser_jig.inWaiting()
        # if avail > 0:
            # msg = self.ser_jig.read(avail)
            # print "received data when we didn't expected it:", [ord(x) for x in msg]
        
        # # turn off TX and make sure it notices the departure
        # self.run(self.neighborsDisableTx,           self.ser,     0x80, 1, self.ser)
        # time.sleep(0.5)
        # for i in xrange(4):
            # self.waitForNeighborEvt(self.ser_jig, NEIGHBOR_DEPARTED_ID)
        # easiest to leave disabled, in case the script gets run multiple times in succession
        # self.run(self.neighborsEnableTx,            self.ser,     0x81, 1, self.ser)
        
        ############################
        ## BLOCK NEIGHBOR RX TEST ##
        ############################
        # JIG_NBR_ID = 2
        # self.run(self.neighborsSetID,               self.ser_jig,     0x82, 2, self.ser_jig, JIG_NBR_ID)
        # # make sure TX is off, then turn on rx and make sure it notices the arrival
        # self.run(self.neighborsDisableTx,           self.ser_jig,     0x80, 1, self.ser_jig)
        # self.run(self.neighborsEnableEvtReport,     self.ser,         0x83, 1, self.ser)
        # self.run(self.neighborsEnableTx,            self.ser_jig,     0x81, 1, self.ser_jig)
        # # TODO - need a way to know which sides are matched up with which
        # for i in xrange(4):
            # self.waitForNeighborEvt(self.ser)
        
        # # turn off TX and make sure it notices the departure
        # self.run(self.neighborsDisableTx,           self.ser_jig,     0x80, 1, self.ser_jig)
        # self.waitForNeighborEvt(self.ser)
        # # easiest to leave disabled, in case the script gets run multiple times in succession
        # # self.run(self.neighborsEnableTx,            self.ser,     0x81, 1, self.ser)
        
        #########################
        ## BLOCK RADIO TX TEST ##
        #########################
        self.run(self.siftRadioTestSetup,     self.ser, 0x50, 5)
        dongleSetupRadioTests(self.dongle)
        print "starting tx test"
        self.run(self.siftRadioTxTest,        self.ser, 0x51, 2)
        stopSiftTxTest(self.dongle)
        
        #########################
        ## BLOCK RADIO RX TEST ##
        #########################
        print "starting rx test"
        self.run(self.siftRadioRxTest,        self.ser, 0x52, 2)
        self.run(self.siftCancelRadioRxTest,  self.ser, 0x53, 1)
        
        self.run(self.shutDownTest,           self.ser, 0x34, 1)
        self.run(self.powerUpTest,            self.ser, 0x30, 1)
        
        self.done()
    

####################################################################################################
##                COMMS TESTS
####################################################################################################

    def serialCommsTest(self, opcode):
        SERIAL_CHARTEST = 0xAA
        self.ser.write(chr(SERIAL_CHARTEST))
        len = self.getResponseHeader(opcode)
        if len < 1:
            return False
        return ord(self.ser.read()) == SERIAL_CHARTEST
        
    def nrfCommsTest(self, opcode):
        len = self.getResponseHeader(opcode)
        if len < 1:
            return False
        return ord(self.ser.read()) == 1

    def flashCommsTest(self, opcode):
        len = self.getResponseHeader(opcode)
        if len < 1:
            return False
        return ord(self.ser.read()) == 1
        
    def accelCommsTest(self, opcode):
        len = self.getResponseHeader(opcode)
        if len < 1:
            return False
        return ord(self.ser.read()) == 1
        
    # this guy is special since we need to get the UID first in order to name the log file
    def uniqueIDTest(self, opcode):
        length = self.getResponseHeader(opcode)
        uid = self.ser.read(length)
        return "".join(["%02X" % ord(x) for x in uid])
        
####################################################################################################
##                DISPLAY
####################################################################################################
        
    def lcdBorderTest(self, opcode):
        BORDER_WIDTH = 2
        self.ser.write(chr(BORDER_WIDTH))
        return getManualResponse("Confirm black screen with white pixel border?")

    def lcdEvenRowTest(self, opcode):
        return getManualResponse("Confirm white rows even?")

    def lcdOddRowTest(self, opcode):
        return getManualResponse("Confirm white rows odd?")

    def lcdEvenColumnTest(self, opcode):
        return getManualResponse("Confirm white columns even?")
        
    def lcdOddColumnTest(self, opcode):
        return getManualResponse("Confirm white columns odd?")
        
    def lcdColorsToStr(self, color):
        s = {
          GREEN: "green",
          BLUE:  "blue",
          RED:   "red"
        }
        return s[color]
        
    def lcdFillTest(self, opcode, color):
        self.ser.write(chr(color))
        return getManualResponse("Confirm display is filled %s?" % (self.lcdColorsToStr(color)))
        
    def lcdBacklightOffTest(self, opcode):
        return getManualResponse("Confirm display backlight is off?")
        
    def lcdBacklightOnTest(self, opcode):
        return getManualResponse("Confirm display backlight is on?")
        
####################################################################################################
##                SENSORS
####################################################################################################
    
    def accelValuesTest(self, opcode):
        len = self.getResponseHeader(opcode)
        if len < 0:
            return False
        x = ord(self.ser.read())
        y = ord(self.ser.read())
        z = ord(self.ser.read())
        print "accel values - x: %d y: %d z: %d" % (x, y, z)
        success = True # todo - verify these fall within a given range
        return [success, x, y, z]

    def accelOrientationToStr(self, orientation):
        s = {
          ACCEL_ORIENTATION_NEUTRAL: "neutral",
          ACCEL_ORIENTATION_X_NORTH: "x axis, north",
          ACCEL_ORIENTATION_X_SOUTH: "x axis, south",
          ACCEL_ORIENTATION_Y_NORTH: "y axis, north",
          ACCEL_ORIENTATION_Y_SOUTH: "y axis, south"
        }
        return s[orientation]
    
    def accelCalibrateTest(self, opcode, orientation):
        getManualResponse("Accelerometer is in %s orientation?" % (self.accelOrientationToStr(orientation)))
        self.ser.write(chr(orientation))
        length = self.getResponseHeader(opcode)
        o = ord(self.ser.read())
        success = length == 1 and o == orientation
        return [success, o]
        
    def accelOrientationTest(self, opcode, orientation):
        self.ser.write(chr(orientation))
        length = self.getResponseHeader(opcode)
        if length != 4:
            return False
        success = ord(self.ser.read()) == 1
        stored = ord(self.ser.read())
        measured = ord(self.ser.read())
        acceptable = ord(self.ser.read())
        if acceptable == 0:
            success = 0
        print "success %d stored %d measured %d acceptable %d" % (success, stored, measured, acceptable)
        return [success, stored, measured]
        
    def accelRelativeOrientationTest(self, opcode):
        length = self.getResponseHeader(opcode)
        if length != 3:
            return False
        success = ord(self.ser.read()) == 1
        xdistance = ord(self.ser.read())
        ydistance = ord(self.ser.read())
        print "success %d xdistance %d ydistance %d" % (success, xdistance, ydistance)
        return [success, xdistance, ydistance]
        
    def initButtonTestMode(self, opcode):
        length = self.getResponseHeader(opcode)
        success = length >= 0
        return success
        
    def cancelButtonTestMode(self, opcode):
        length = self.getResponseHeader(opcode)
        success = length >= 0
        return success
        
    def waitForButtonPress(self):
        print "please press the siftable button within the next 10 seconds..."
        # old_timeout = ser.timeout
        # ser.timeout = 10
        OPCODE = 0x72
        
        length1 = self.getResponseHeader(OPCODE)
        press = ord(self.ser.read())
        
        length2 = self.getResponseHeader(OPCODE)
        release = ord(self.ser.read())
        
        print "thank you." #, length1, length2, press, release
        # ser.timeout = old_timeout
        success = press == 1 and release == 0
        return success
        
    def flashReadWrite(self, opcode):
        len = self.getResponseHeader(opcode)
        if len != 1:
            return False
        success = ord(self.ser.read())
        return success != 0
        
    def shutDownTest(self, opcode):
        length = self.getResponseHeader(opcode)
        return length >= 0
        
    def powerUpTest(self, opcode):
        length = self.getResponseHeader(opcode)
        return length >= 0
        
    def pgoodTest(self, opcode):
        length = self.getResponseHeader(opcode)
        if length != 1:
            return False
        pgood = ord(self.ser.read())
        success = pgood == 1 or pgood == 0 # TODO - not totally sure what we should be testing for
        return success
        
    def chgSTest(self, opcode):
        length = self.getResponseHeader(opcode)
        if length != 1:
            return False
        chg_s = ord(self.ser.read())
        success = chg_s == 1 or chg_s == 0 # TODO - not totally sure what we should be testing for
        return success

####################################################################################################
##                RADIO
####################################################################################################
        
    def siftRadioTestSetup(self, opcode):
        self.ser.write(chr(RF_CHANNEL))
        self.ser.write(chr(RF_PIPE))
        self.ser.write(chr(RF_POWER))
        self.ser.write(chr(RF_RETRIES))
        
        len = self.getResponseHeader(opcode)
        if len < 0:
            return False
        
        rfchan = ord(self.ser.read())
        rfpipe = ord(self.ser.read())
        rfpower = ord(self.ser.read())
        rfretries = ord(self.ser.read())
        success = rfchan == RF_CHANNEL and rfpipe == RF_PIPE and rfpower == RF_POWER and rfretries == RF_RETRIES
        return [success, rfchan, rfpipe, rfpower, rfretries]
        
    def siftRadioTxTest(self, opcode):
        ITERATIONS = 50
        NO_ERRORS = 0
        evt = startSiftTxTest(self.dongle, ITERATIONS)
        self.ser.write(chr(ITERATIONS))
        
        start = datetime.now()
        evt = self.dongle.get_event(5)
        elapsed = (datetime.now() - start).microseconds / 1000
        
        length = self.getResponseHeader(opcode)
        
        tries = ord(self.ser.read())
        # print "tries", tries, "length", length, "evt", evt
        withinthresh = ord(self.ser.read())
        success = evt is not None and evt[0] == NO_ERRORS
        return [success, tries, elapsed]
        
    def siftRadioRxTest(self, opcode):
        ITERATIONS = 100
        NO_ERRORS = 0
        self.ser.write(chr(ITERATIONS))
        startSiftRxTest(self.dongle, ITERATIONS)
        
        start = datetime.now()
        evt = self.dongle.get_event(5)
        elapsed = (datetime.now() - start).microseconds / 1000
        
        length = self.getResponseHeader(opcode)
        
        # TODO - this is a response to the cancel (aka complete) opcode, which can be triggered automatically by the firmware...organize better to represent this
        length = self.getResponseHeader(0x53)
        
        failures = ord(self.ser.read())
        completed = ord(self.ser.read())
        print "failures: %d completed: %d" % (failures, completed)
        success = completed == 1 and failures == 0 and evt is not None
        return [success, completed, success]
        
    def siftCancelRadioRxTest(self, opcode):
        length = self.getResponseHeader(opcode)
        return length >= 0
        
####################################################################################################
##                NEIGHBORS
####################################################################################################

    def neighborsSetID(self, opcode, serial, id):
        serial.write(chr(id))
        length = self.getResponseHeader(opcode, serial)
        # id is echoed
        id_echo = ord(serial.read())
        success = length == 1 and id_echo == id
        return [success, id]
        
    def neighborsDisableTx(self, opcode, serial):
        length = self.getResponseHeader(opcode, serial)
        success = length >= 0
        return success
        
    def neighborsEnableTx(self, opcode, serial):
        length = self.getResponseHeader(opcode, serial)
        success = length >= 0
        return success
        
    def neighborsEnableEvtReport(self, opcode, serial):
        length = self.getResponseHeader(opcode, serial)
        success = length >= 0
        return success
        
    def neighborsDisableEvtReport(self, opcode, serial):
        length = self.getResponseHeader(opcode, serial)
        success = length >= 0
        return success
        
    def waitForNeighborEvt(self, serial, id_to_match):
        OPCODE = 0x85
        
        resp = [ord(c) for c in serial.read(4 + 2)]
        print "resp", resp
        prefix, length, op = resp[0], resp[1], resp[2]
        id, neighborside, myside = resp[3], resp[4], resp[5]
        success = (length == 4 and prefix == TEST_PREFIX and op == OPCODE and id == id_to_match)
        print "id %d, neighborside %d, myside %d success %d" % (id, neighborside, myside, success)
        
        # TODO - verify these values correspond with what we're telling neighbor jig to do
        return [success, id, neighborside, myside]
    
if __name__ == '__main__':

    sift_port = 2
    neighborjig_port = 4
    if len(sys.argv) >= 2:
        sift_port = int(sys.argv[1]) - 1
    else:
        print "error, not enough arguments!"
        print "usage: python factorytest_runner.py <sift-comport> <neighborjig-comport>"
        print "note: comports passed as numbers, for instance for COM3 pass 3"
        sys.exit(0)
    if len(sys.argv) >= 3:
        neighborjig_port = int(sys.argv[2]) - 1

    print "running factory tests with block on COM" + str(sift_port + 1) + ", neighbor jig on COM" + str(neighborjig_port + 1)
    
    testrunner = TestRunner(sift_port, neighborjig_port)
    testrunner.runTests()
    sys.exit(0)
   