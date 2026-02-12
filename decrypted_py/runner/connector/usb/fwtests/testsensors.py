
from fixtures import siftserial, jigserial

import unittest, time
from nose.tools import *
from testutil import *

TEST_ACCEL_CALIBRATION =            0x91
TEST_ACCEL_ORIENTATION =            0x92
TEST_ACCEL_RELATIVE_ORIENTATION =   0x93

TEST_INIT_BUTTON_MODE =             0x70
TEST_CANCEL_BUTTON_MODE =           0x71
TEST_BUTTON_PRESS_REPORT =          0x72

TEST_PGOOD =                        0x32
TEST_CHGS =                         0x33

ACCEL_ORIENTATION_NEUTRAL =         1
ACCEL_ORIENTATION_X_NORTH =         2
ACCEL_ORIENTATION_X_SOUTH =         3
ACCEL_ORIENTATION_Y_NORTH =         4
ACCEL_ORIENTATION_Y_SOUTH =         5

SUCCESS = 1

def accelOrientationToStr(orientation):
    s = {
      ACCEL_ORIENTATION_NEUTRAL: "neutral",
      ACCEL_ORIENTATION_X_NORTH: "x axis, north",
      ACCEL_ORIENTATION_X_SOUTH: "x axis, south",
      ACCEL_ORIENTATION_Y_NORTH: "y axis, north",
      ACCEL_ORIENTATION_Y_SOUTH: "y axis, south"
    }
    return s[orientation]

def checkAccelOrientation(ser, orientation):
    resp = sendTestMsg(ser, TEST_ACCEL_ORIENTATION, [orientation])
    eq_(len(resp), 4, "unexpected msg size back from orientation measurement")
    
    status, stored, measured, acceptable = resp[0], resp[1], resp[2], resp[3]
    eq_(status, SUCCESS, "Sift did not measure successful orientation: stored %d measured %d, acceptable %d" % (stored, measured, acceptable))
    # TODO - log values somehow
    
def doAccelCalibration(ser, orientation):
    getManualResponse("Accelerometer is in %s orientation?" % (accelOrientationToStr(orientation)))
    resp = sendTestMsg(ser, TEST_ACCEL_CALIBRATION, [orientation])
    eq_(len(resp), 1, "unexpected msg size back from calibration measurement")
    eq_(resp[0], orientation)
    # TODO - log values somehow
    
class TestSensors(unittest.TestCase):
    
    @classmethod
    def setupClass(self):
        """ gets run once for this entire class """
        print "sensors test setup"
        pass
    
    @classmethod
    def teardownClass(self):
        """ gets run once for this entire class """
        pass
        
    def setUp(self):
        """ called before each test method """
        # clear out any previous junk
        for ser in [siftserial, jigserial]:
            if ser.port != None:
                ser.flushInput()
                ser.flushOutput()
    
    def testAccelCalibrateNeutral(self):
        doAccelCalibration(siftserial, ACCEL_ORIENTATION_NEUTRAL)
        checkAccelOrientation(siftserial, ACCEL_ORIENTATION_NEUTRAL)
        
    def DONTtestAccelCalibrationSides(self):
        for orientation in [ACCEL_ORIENTATION_X_NORTH, ACCEL_ORIENTATION_X_SOUTH, ACCEL_ORIENTATION_Y_NORTH, ACCEL_ORIENTATION_Y_SOUTH]:
            doAccelCalibration(siftserial, orientation)
            checkAccelOrientation(siftserial, orientation)
        
    def DONTtestAccelRelativeOrientation(self):
        resp = sendTestMsg(siftserial, TEST_ACCEL_RELATIVE_ORIENTATION)
        eq_(len(resp), 3, "unexpected msg size back from relative orientation test")
        status, xdistance, ydistance = resp[0], resp[1], resp[2]
        eq_(status, SUCCESS, "Sift did not measure successful relative orientation: xdistance %d ydistance %d" % (xdistance, ydistance))
        # print "success %d xdistance %d ydistance %d" % (success, xdistance, ydistance)
        # TODO - log values
        
    def testButtonPress(self):
        sendTestMsg(siftserial, TEST_INIT_BUTTON_MODE)
        
        old_timeout = siftserial.timeout
        siftserial.timeout = 10
        print "please press the siftable button within the next 10 seconds..."
        
        resp = receiveTestMsg(siftserial, TEST_BUTTON_PRESS_REPORT)
        press = resp[0]
        
        resp = receiveTestMsg(siftserial, TEST_BUTTON_PRESS_REPORT)
        release = resp[0]
        
        sendTestMsg(siftserial, TEST_CANCEL_BUTTON_MODE)
        
        print "thank you." #, press, release
        siftserial.timeout = old_timeout
        eq_(press, 1, "got unexpected value for button press: %d" % (press))
        eq_(release, 0, "got unexpected value for button release: %d" % (release))
        
    def testPGood(self):
        resp = sendTestMsg(siftserial, TEST_PGOOD)
        eq_(resp[0], SUCCESS, "bad value back from pgood test: %d" % (resp[0]))
        
    def testChgS(self):
        resp = sendTestMsg(siftserial, TEST_CHGS)
        eq_(resp[0], SUCCESS, "bad value back from ChgS test: %d" % (resp[0]))

