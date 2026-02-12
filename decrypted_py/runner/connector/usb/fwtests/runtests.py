

import sys, nose

# Kick off nose
# we want to pass our own non-nose params on the command line to specify
# which serial ports to use, etc, so pass nose its own set of args here
nose_argv=["", "--nocapture"]

# pass any arguments beyond the first 2 (reserved for sift and jig com ports) straight to nose
if len(sys.argv) >= 4:
    extras = sys.argv[3:]
    nose_argv.extend(extras)

# TODO - get the block's UID so we can name the test output file accordingly
    
nose.main(argv=nose_argv)
