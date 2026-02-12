# !/usr/bin/env python2.6
#  dongle.py
#  Copyright (c) 2010 Sifteo. All rights reserved.

from uart_dongle import UART_Dongle
import os, sys, re, time, random
from datetime import datetime, timedelta
from radio_asset_uploadr import uploadAsset, fourByteIfy, twoByteIfy

TEST_IMG = "gems2_empty.siftimg" # assumed to be located within the same dir as this script

APP_INVENTORY_REQ = 61
APP_REMOVE = 58
ASSETTYPE_IMG = 0

# the last 4 bytes of the files should be the CRC
# return as a list of ints, so it's easy to compare against the RF packets
def getSiftImgCrc(filename):
    size = os.path.getsize(filename)
    crc = []
    with open(filename, "rb") as fd:
        fd.seek(size - 4)
        while len(crc) < 4:
            crc.append(ord(fd.read(1)))
    return crc

def sendDongleMsg(d, m):
    while len(m) < 16:
        m.append(0)
    res = d.write_msg(m)
    if res[4] != 0:
        print "msg didn't make it to sift, bailing.  ", res
        return False
    else:
        return True

def runAssetTests(port, sift_id):
    d = UART_Dongle(port)
    asset_id = random.randrange((2 ** 16) - 1)
    checksum = getSiftImgCrc(TEST_IMG)
    uploadAsset(image_path = TEST_IMG, appid = 0, assetid = asset_id, assettype = ASSETTYPE_IMG, siftid = sift_id, dongle = d)
    
    # get a list of the assets for app 0
    msg = [siftid, APP_INVENTORY_REQ, 0, 0, 0, 0, 255, 0]
    sendDongleMsg(d, msg)
    
    # verify the asset we just uploaded is included - gotta match the asset ID and the checksum
    matched_assetid = False
    matched_crc = False
    id_match = twoByteIfy(asset_id)
    evt = 1
    while evt is not None:
        evt = d.get_event(1)
        if evt is not None and evt[1] == 138:
            if evt[8:10] == id_match:
                matched_assetid = True
            if evt[11:15] == checksum:
                matched_crc = True
    assert matched_assetid == True
    assert matched_crc == True
    print "matched_assetid", matched_assetid, "matched_crc", matched_crc
    
    # delete all assets for app 0
    msg = [siftid, APP_REMOVE, 0, 0, 0, 0]
    sendDongleMsg(d, msg)
    
    # ask for a list of the assets for app 0
    msg = [siftid, APP_INVENTORY_REQ, 0, 0, 0, 0, 255, 0]
    sendDongleMsg(d, msg)
    
    # verify there are none...wait a little longer just to be sure
    assert d.get_event(5)[1] == 139
    
if __name__ == '__main__':
    
    siftid = 0
    port = 3
    if (len(sys.argv) > 2):
        siftid = int(sys.argv[2])
        port = int(sys.argv[1])-1
    
    try:
        print "running asset tests on port %d, sift id %d" % (port+1, siftid)
        runAssetTests(port, siftid)
    except Exception, e:
        print e
        sys.exit(1)
      
    
    

