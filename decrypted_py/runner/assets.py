
import time
import sys, os, traceback

import connector.usb.dongle
from connector.usb.helpers import dongle_helper
from connector.message import Message
from connector.usb.helpers import asset_helper
from connector.usb_connector import USBConnector
import app
import link
# from sift import _AssetSet
import sift
import sift.util.timers

# TODO - these should be dynamic as well. 
# but no support for displaying by app ID yet
APP_ID = 0
ASSET_TYPE = 0
NUM_ATTEMPTS = 10

_current = 0
_sift_mark = 0
_current_sift = None

MARK_AT = 10


def siftimg_to_response(app_id, siftimg):
    return tuple(dongle_helper._intToFourByte(app_id) + \
                 dongle_helper._intToTwoByte(siftimg.index) + \
                 [0] + \
                 siftimg.read_crc())

def _print_dot(*args):
    global _current, _sift_mark 
    sys.stdout.write(".")
    _current += 1
    sys.stdout.flush()

def inventory(app_id, siftable, dongle):
    app_id_bytes = dongle_helper._intToFourByte(app_id)
    siftable._send("APP_ASSET_INVENTORY_REQUEST", *app_id_bytes)
    responses = list()
    while 1:
        response = dongle.get_event(4)
        if response is None:
            return responses
        else:
            response = response[0:14]
            m = Message.construct(*response)
            if m.address == siftable.id and m.op and m.op.name == \
                                            "APP_ASSET_INVENTORY_RESPONSE":
                responses.append(tuple(m.payload))
    return responses
    
def asset_exists(asset_id, app_id, siftable, dongle):
    found = asset_list(app_id, siftable, dongle)
    print "Found assets %s on %s" % (str(found), siftable)
    return asset_id in found
    
def upload_all(sift_set, siftimages, dongle, app_id):
    for s in sift_set:        
        print "\nUploading to", s
        while(1):
            responses = inventory(app_id, s, dongle)
            still_to_load = [i for i in siftimages if   
                (siftimg_to_response(app_id, i) not in responses)]
            num_loaded = len(siftimages) - len(still_to_load)
            print "%s/%s loaded." % (num_loaded, len(siftimages)),
            if(len(still_to_load) == 0):
                print "DONE"
                break
            else:
                print "%s to go!" % len(still_to_load)
                for siftimg in still_to_load:
                    print siftimg.filename
                    asset_helper.uploadAsset(
                        dongle,
                        s.id,
                        app_id,
                        siftimg.index,
                        ASSET_TYPE,
                        siftimg.path,
                        verbose=False,
                        progress_callback=_print_dot)
                    sys.stdout.write("\n")

def parse_args(args):
    from optparse import OptionParser
    usage = "Usage: %prog [options] path/to/app (--help for help)"
    parser = OptionParser(usage)
    parser.add_option("-l", "--list", dest="list", action="store_true", default=False, help="List the assets available")
    # parser.add_option("-a", "--all", dest="all",
    #                   help="All apps. Used only for list.",
    #                   action="store_true",
    #                   default=False)
    parser.add_option("-s", "--sift_id", dest="ids",
                      help="Specific sift ID(s) you want to target.", 
                      action="append",
                      metavar="ID")
    parser.add_option("-d", "--delete", dest="delete",
                      help="Delete assets for the given app", 
                      action="store_true",
                      default=False)
    parser.add_option("-i", "--app_id", dest="app",
                      help="Specify a particular app_id. Defaults to %s" % APP_ID, 
                      action="store",
                      default=APP_ID,
                      metavar="APP_ID")
    return parser.parse_args()
    

# --- MAIN -----------------------------------------------------------------

def main(args):

    options, args = parse_args(args)

    # Set up dongle, connector, and link objects
    dongle = connector.usb.dongle.Dongle()
    cnx = USBConnector()
    cnx.connect(dongle)
    siftLink = link.Link(cnx)

    # Create SiftSet
    if options.ids:
        sift_ids = [int(s) for s in options.ids]
    else:
        msg = siftLink.writeAndReadToLink(sift.opcodes.lookup("SIFT_IDS"), [])
        num_ids = msg.payload[0]
        sift_ids = msg.payload[1:1+num_ids]
    if len(sift_ids) == 0:
        print "No sifts to upload to"
        return
    sift_set = sift.sift_set.SiftSet(sift_ids, 
                                     siftLink.writeAndReadToSiftable)
        
    # Determine app_id
    app_id = int(options.app)
    
    app_ids = [app_id]

    # List siftables
    if options.list:
        # if options.all:
        #     app_id = 0xFFFFFFFF
        #     print "All apps"
        # else:
        print "App %s" % app_id
        for siftable in sift_set:
            print "-> %s:" % siftable,
            responses = inventory(app_id, siftable, dongle)
            print len(responses)
            for i in responses:
                print " ", i
    # Delete assets for a given app
    elif options.delete:
        for siftable in sift_set:
            params = dongle_helper._intToFourByte(app_id)
            siftable._send("REMOVE_APP",*params)
    
    # Upload to siftables
    else:
        if len(args) < 1:
            print "Please provide a path to an application"
            exit(1)
        config = app.Config(args[0])
        if len(config.image_set) == 0:
            print "Nothing to upload!"
            return
        upload_all(sift_set, config.image_set, dongle, app_id)
        
            
if __name__ == '__main__':
    import sys
    main(sys.argv)
