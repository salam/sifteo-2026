#!/usr/bin/env python
# encoding: utf-8
"""
Decorators for Python code.

This package contains decorators and other miscellaneous
helpers for application programmers.

Examples:
@deprecated
def my_func():
    pass

@other_decorators_must_be_upper
@deprecated
def my_func():
    pass

via http://wiki.python.org/moin/PythonDecoratorLibrary

"""

import sys
# import os
import warnings
import functools

def deprecated(func):
    """
    This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.
    """

    @functools.wraps(func)
    def new_func(*args, **kwargs):
        warnings.warn_explicit(
            "Call to deprecated function %(funcname)s." % {
                'funcname': func.__name__,
            },
            category=DeprecationWarning,
            filename=func.func_code.co_filename,
            lineno=func.func_code.co_firstlineno + 1
        )
        return func(*args, **kwargs)
    return new_func


class LogPrinter:
    """
    LogPrinter class which serves to emulates a file object
    and logs whatever it gets sent to a Logger object at the
    INFO level.
    """
    def __init__(self):
        import logging
        """Grabs the specific logger to use for logprinting."""
        self.ilogger = logging.getLogger('logprinter')
        il = self.ilogger
        logging.basicConfig()
        il.setLevel(logging.INFO)
        
    def flush(self):
        pass

    def write(self, text):
        """Logs written output to a specific logger"""
        self.ilogger.info(text)

def print2log(func):
    """
    Wraps a method so that any calls made to print get
    logged instead.
    """
    def pwrapper(*arg):
        stdobak = sys.stdout
        lpinstance = LogPrinter()
        sys.stdout = lpinstance
        try:
            return func(*arg)
        finally:
            sys.stdout = stdobak
    return pwrapper

