# !/usr/bin/env python2.6
#  asset_helper.py
#  Copyright (c) 2010 Sifteo. All rights reserved.

import os, re, time
from datetime import datetime, timedelta
import dongle_helper
from graphics_helper import changeFeedbackMode

# Message Constants

ASSET_TYPE_IMAGE = 0
ASSET_TYPE_SOUND = 1

# Message Opcodes

ASSET_UPLOAD = 56
ASSET_UPLOAD_HEADER = 68
ASSET_UPLOAD_RESULT = 73
ASSET_DUMP_REQUEST = 160
ASSET_DOWNLOAD_HEADER = 161
ASSET_DOWNLOAD = 162

ASSET_VERIFY_CRC_REQUEST = 153
ASSET_VERIFY_CRC_RESPONSE = 154
ASSET_DELETE_COMPLETE = 74
ASSET_INVENTORY_REQUEST = 61
ASSET_INVENTORY_RESPONSE = 138

APP_DELETE_ASSET = 59
APP_DELETE_ALL_ASSETS = 58
APP_INFO_REQUEST = 60
APP_INVENTORY_RESPONSE = 138
APP_INFO_RESPONSE = 139
APP_LIST_REQUEST = 70
APP_LIST_RESPONSE_HEADER = 71
APP_LIST_RESPONSE_ITEM = 72

# Message Offsets (within payload)

ASSET_UPLOAD_RESULT_IDX  = 6    # opcode  74 (ASSET_UPLOAD_RESULT)
ASSET_DL_SIZE_IDX = 0           # opcode 161 (ASSET_DOWNLOAD_HEADER)
ASSET_DL_CRC_IDX = 4            # opcode 161 (ASSET_DOWNLOAD_HEADER)
ASSET_TYPE_IMAGE_IDX = 4        # opcode 139 (APP_INFO_RESPONSE)
ASSET_TYPE_SOUND_IDX = 6        # opcode 139 (APP_INFO_RESPONSE)
ASSET_TYPE_BYTES_IDX = 8        # opcode 139 (APP_INFO_RESPONSE)
ASSET_INFO_ASSET_ID_IDX = 4     # opcode 138 (ASSET_INVENTORY_RESPONSE)
ASSET_INFO_ASSET_TYPE_IDX = 6   # opcode 138 (ASSET_INVENTORY_RESPONSE)
ASSET_VERIFY_CRC_ORIG_IDX = 7   # opcode 153 (ASSET_VERIFY_CRC_RESPONSE)
ASSET_VERIFY_CRC_CALC_IDX = 11  # opcode 153 (ASSET_VERIFY_CRC_RESPONSE)
APP_LIST_APP_ID_IDX = 0         # opcode  72 (APP_LIST_RESPONSE_ITEM)

BYTES_PER_PACKET_IDX = 0        # for variable length packet types

def _print_progress(sent, size, percentdone):
  print "%d of %d bytes done - %d%%" % (sent, size, percentdone)

def uploadAsset(dongle, siftid, appid, assetid, assettype, file_path, verbose=False, progress_callback=_print_progress):
  
  size = os.path.getsize(file_path)
  file_bytes_left = size
  if verbose:
    print "sending image " + file_path + " of " + str(size) + " bytes"
  FILE = open(file_path,"rb")
  start = datetime.now()
  percentdone = -1
  seqid = 0
  
  # send header packet
  msg = dongle_helper.createDongleMessage(ASSET_UPLOAD_HEADER, siftid)
  dongle_helper.appendUInt32ToMsg(msg, size)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  dongle_helper.appendUInt16ToMsg(msg, assetid)
  dongle_helper.appendUInt8ToMsg(msg, assettype)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  
  time.sleep(3) # header receipt is sloooooooooow
  
  # send file packets
  while file_bytes_left > 0:
    msg = dongle_helper.createDongleMessage(ASSET_UPLOAD, siftid)
    # send [len]: typical case where we will either send all of the remaining bytes, or the max allowed payload size
    # on the last packet, we  might not have enough bytes to fill it completely
    bytes_to_send = min(file_bytes_left, dongle_helper.MSG_PAYLOAD_LENGTH-2)
    dongle_helper.appendUInt8ToMsg(msg, int(bytes_to_send)+1)
    
    # write the bytes to the serial port
    pkt = str(FILE.read(bytes_to_send))
    dongle_helper.appendBytesToMsg(msg, pkt)
    dongle_helper.appendUInt8ToMsg(msg, seqid)
    seqid += 1
    if seqid == 256:
        seqid = 0
    if not dongle_helper.sendDongleMsg(dongle, msg):
      break
    
        # print "send pkt size %d" % (bytes_to_send)
    file_bytes_left = file_bytes_left - bytes_to_send
    sent = size - file_bytes_left
    if percentdone != (sent * 100 / size):
      percentdone = (sent * 100 / size)
      if progress_callback and verbose:
        progress_callback(sent, size, percentdone)
  
  # clean up
  elapsed = (datetime.now() - start).seconds
  if elapsed == 0: elapsed = 1
  
  rc = True
  if verbose and file_bytes_left == 0:
    print "upload complete - %d bytes/sec" % ((size - file_bytes_left) / elapsed)
  elif file_bytes_left > 0:
    rc = False
    print "uh oh - %d bytes remaining.  something must have gone wrong...sorry bout that." % (file_bytes_left)
    print "make sure siftlord/skullmaster are not pinging, and nobody else has an active dongle!"
    
  if rc is True:
    rply = dongle_helper.recvDongleMsg(dongle, ASSET_UPLOAD_RESULT)
    if not rply:
      rc = False
    else:
      upload_status = dongle_helper.getUInt8AtOffet( rply, ASSET_UPLOAD_RESULT_IDX )
      if upload_status == 2:
        print "ERROR: sift reported CRC failure"
      elif upload_status == 3:
        print "ERROR: sift reported Disk Space failure"
      elif upload_status == 4:
        print "ERROR: sift reported misalingment failure"
      rc = (upload_status == 1)
  
  FILE.close()
  changeFeedbackMode(dongle, siftid, 0)
  return rc

def downloadAssetData(dongle, siftid, appid, assetid, assettype):
  msg = dongle_helper.createDongleMessage(ASSET_DUMP_REQUEST, siftid)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  dongle_helper.appendUInt16ToMsg(msg, assetid)
  dongle_helper.appendUInt8ToMsg(msg, assettype)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  header = dongle_helper.recvDongleMsg(dongle, ASSET_DOWNLOAD_HEADER)
  if not header: return False
  
  byte_count = dongle_helper.getUInt32AtOffet( header, ASSET_DL_SIZE_IDX )
  file_crc   = dongle_helper.getUInt32AtOffet( header, ASSET_DL_CRC_IDX  )
  
  file_buffer = []
  while byte_count > 0:
    packet = dongle_helper.recvDongleMsg(dongle, ASSET_DOWNLOAD)
    if packet is False:
      return False
    len = dongle_helper.getUInt8AtOffet( packet, BYTES_PER_PACKET_IDX )
    offset = dongle_helper.MSG_HEADER_LENGTH+1
    file_buffer += packet[offset:len+offset]
    byte_count -= len
  
  rcvd_crc = dongle_helper.getUInt32AtOffet( file_buffer[-4:], 0, 0 )
  if file_crc != rcvd_crc: return False
  
  return file_buffer

def queryAssetCount(dongle, siftid, appid):
  msg = dongle_helper.createDongleMessage(APP_INFO_REQUEST, siftid)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  rply = dongle_helper.recvDongleMsg(dongle, APP_INFO_RESPONSE)
  if not rply: return False
  return [dongle_helper.getUInt16AtOffet( rply, ASSET_TYPE_IMAGE_IDX ), 
      dongle_helper.getUInt16AtOffet( rply, ASSET_TYPE_SOUND_IDX ),
      dongle_helper.getUInt32AtOffet( rply, ASSET_TYPE_BYTES_IDX )]

def queryAssetList(dongle, siftid, appid):
  msg = dongle_helper.createDongleMessage(ASSET_INVENTORY_REQUEST, siftid)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  counts = queryAssetCount(dongle, siftid, appid)
  if not counts: return False
  dongle_helper.appendUInt16ToMsg(msg, counts[0]) # workaround for expected asset count
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  result = []
  while True:
    rply = dongle_helper.recvDongleMsg(dongle, ASSET_INVENTORY_RESPONSE)
    if not rply: break
    result.append( "%d:%d" % (dongle_helper.getUInt16AtOffet( rply, ASSET_INFO_ASSET_ID_IDX  ),
                  dongle_helper.getUInt8AtOffet(  rply, ASSET_INFO_ASSET_TYPE_IDX)) )
  return result

def verifyAsset(dongle, siftid, appid, assetid, assettype):
  msg = dongle_helper.createDongleMessage(ASSET_VERIFY_CRC_REQUEST, siftid)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  dongle_helper.appendUInt16ToMsg(msg, assetid)
  dongle_helper.appendUInt8ToMsg(msg, assettype)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  rply = dongle_helper.recvDongleMsg(dongle, ASSET_VERIFY_CRC_RESPONSE)
  if not rply: return False
  return [dongle_helper.getUInt32AtOffet( rply, ASSET_VERIFY_CRC_ORIG_IDX ), 
      dongle_helper.getUInt32AtOffet( rply, ASSET_VERIFY_CRC_CALC_IDX )]

def deleteAsset(dongle, siftid, appid, assetid, assettype):
  msg = dongle_helper.createDongleMessage(APP_DELETE_ASSET, siftid)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  dongle_helper.appendUInt16ToMsg(msg, assetid)
  dongle_helper.appendUInt8ToMsg(msg, assettype)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  rply = dongle_helper.recvDongleMsg(dongle, ASSET_DELETE_COMPLETE)
  if not rply: return False
  return True

def deleteAllAssets(dongle, siftid, appid):
  msg = dongle_helper.createDongleMessage(APP_DELETE_ALL_ASSETS, siftid)
  dongle_helper.appendUInt32ToMsg(msg, appid)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    print "failed to send deletion request"
    return False
  rply = dongle_helper.recvDongleMsg(dongle, ASSET_DELETE_COMPLETE, 20)  #this might take a while if there are a lot of assets
  if not rply: return False
  return True

def queryAppList(dongle, siftid):
  msg = dongle_helper.createDongleMessage(APP_LIST_REQUEST, siftid)
  if not dongle_helper.sendDongleMsg(dongle, msg):
    return False
  result = []
  while True:
    rply = dongle_helper.recvDongleMsg(dongle, APP_LIST_RESPONSE_ITEM)
    if not rply: break
    result.append( dongle_helper.getUInt32AtOffet( rply, APP_LIST_APP_ID_IDX ) )
  return result   