

from nose.tools import *

TEST_PREFIX = 0xBF

####################################################################################################
##                GENERAL TEST HELPERS
####################################################################################################

def receiveTestMsg(ser, opcode):
    prefix = ord(ser.read())
    eq_(TEST_PREFIX, prefix, "test prefix didn't match, expected %d (0x%X) != received %d (0x%X)" % (TEST_PREFIX, TEST_PREFIX, prefix, prefix))
    length = ord(ser.read())
    op = ord(ser.read())
    eq_(opcode, op, "opcode didn't match, expected %d (0x%X) != received %d (0x%X)" % (opcode, opcode, op, op))
    
    rv = ser.read(length - 1) # already slurped out the opcode
    rlist = [ord(c) for c in rv]
    # print "rlist", rlist
    return  rlist

def sendTestMsg(ser, opcode, payload = []):
    msg = [TEST_PREFIX, len(payload) + 1, opcode]
    msg.extend(payload)
    for c in msg:
        ser.write(chr(c))
    return receiveTestMsg(ser, opcode)
    
def getManualResponse(msg):
    res = raw_input(msg + " (y/n) ")
    return res.lower().startswith("y")
