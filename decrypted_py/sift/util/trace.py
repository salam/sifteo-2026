"""
trace.py

Copyright (c) 2011 Sifteo. All rights reserved.
"""

import sys, traceback

# ======================================================================
# Class: SiftTraceException
#        An exception that isn't really an exception.
#        This class is to help with manually obtaining stack traces
# ======================================================================

class SiftTraceException(Exception):
    def __init__(self, value):
        self.parameter = value
        
    def __str__(self):
        return repr(self.parameter)

def printStackTrace(limit=None, file=None):
    """
    A work-around for getting full stack traces with .epy files
    """
    raise SiftTraceException("Grabbing stack trace...")
