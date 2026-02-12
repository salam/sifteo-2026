# !/usr/bin/env python2.6

# note: the block must be running the radio-to-uart version of the firmware

from uart_dongle import UART_Dongle
from helpers.dongle_helper import *
from datetime import datetime, timedelta
import sys

print "Preparing to run the radio message listener test."
print "Please make sure the block is running the radio-to-uart firmware"
start = datetime.now()
print "Ding - the time is now %s" % str(start)

UART_COM = 10 # COM11
if len(sys.argv) == 1:
  print "using default com %d" % (UART_COM+1)
else:
  UART_COM = int(sys.argv[1]) - 1

RESP_TIMEOUT = 100
RADIO_MSG_SIZE = 34
TEST_LENGTH = 120 # minutes
TEST_LOGFILE_NAME = "log_received_com%d_%s_%s.txt" % (UART_COM+1, str(start.date()), start.strftime("%H%M%S"))

logfile = open(TEST_LOGFILE_NAME, 'w')
u = UART_Dongle(UART_COM)
u.setTXMode(0) # let the block receive radio messages

timeout = TEST_LENGTH * 60
length = 1
count = 0

print "starting radio message listener for %d minutes" % TEST_LENGTH
while( (datetime.now() - start).seconds < timeout ):
  resp = u.get_event(RESP_TIMEOUT)
  if (resp is not None):
    print "got message: %s   time: %s" % (str(resp), str(datetime.now()))
    logfile.write(str(resp) + "  " + str(datetime.now()) + '\n')

print "time's up, clearing out the queue..."
# empty out the queue
resp = u.get_event(RESP_TIMEOUT)
while (resp is not None):
  logfile.write(str(resp) + '\n')
  resp = u.get_event(RESP_TIMEOUT)

logfile.close()
u.close()
