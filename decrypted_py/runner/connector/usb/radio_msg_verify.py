# !/usr/bin/env python2.6

# note: the block must be paired as sift ID 0 before running this script

from uart_dongle import UART_Dongle
from dongle import Dongle
from helpers.dongle_helper import *
from datetime import datetime, timedelta

print "Preparing to run the radio message verification test."
print "Please make sure that the test block is paired as sift 0"
print "and that DEFAULT_COM is set properly.\n"

start = datetime.now()

DEFAULT_COM = 10 # COM11
RESP_TIMEOUT = 100
RADIO_MSG_SIZE = 34
TEST_LENGTH = 1 # minutes
TEST_LOGFILE_NAME = "log_actual_%s_%s.txt" % (str(start.date()), start.strftime("%H%M%S"))
TEST_CHECKFILE_NAME = "log_expected_%s_%s.txt" % (str(start.date()), start.strftime("%H%M%S"))

logfile = open(TEST_LOGFILE_NAME, 'w')
checkfile = open(TEST_CHECKFILE_NAME, 'w')
u = UART_Dongle(DEFAULT_COM)
u.setTXMode(0) # let the block receive radio messages
d = Dongle()

timeout = TEST_LENGTH * 60
length = 1
count = 0

def UART_to_radio_format(data):
  partial = [RADIO_MSG_SIZE, 0] + data
  return partial + [0]*(RADIO_MSG_SIZE - len(partial))

def get_next_msg(payloadlen, cnt):
  msg = [0, 163, payloadlen] + [255]*(payloadlen-1) + [cnt]
  if cnt == 255:
    cnt = 0
    if payloadlen + 5 == RADIO_MSG_SIZE:
      payloadlen = 1
    else:
      payloadlen += 1
  else:
    cnt += 1
  return (msg, payloadlen, cnt)

# msg = [0, 163, 3, 1, 2, 3]
# d.write_msg(UART_to_radio_format(msg))
# resp = u.get_event(RESP_TIMEOUT) # give some time for the radio message to get there

# if (resp == msg):
  # print "booyah!"
# else:
  # print "oh noes!"

print "starting radio message verification for %d minutes" % TEST_LENGTH
while( (datetime.now() - start).seconds < timeout ):
  # send and check messages
  (msg, length, count) = get_next_msg(length, count)
  checkfile.write(str(msg) + '\n')
  d.write_msg(UART_to_radio_format(msg))
  resp = u.get_event() # try to keep the queue from filling up too much
  if (resp is not None):
    logfile.write(str(resp) + '\n')

print "done sending messages, now clearing out the queue..."
# empty out the queue
resp = u.get_event(RESP_TIMEOUT)
while (resp is not None):
  logfile.write(str(resp) + '\n')
  resp = u.get_event(RESP_TIMEOUT)

checkfile.close()
logfile.close()
u.close()
d.close()
