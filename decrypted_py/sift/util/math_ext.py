#!/usr/bin/env python
# encoding: utf-8
"""
Numeric utility functions.

Miscellaneous functions for common math that are not covered
by the standard math library.

For convenience, these functions are added on import to the
math module (except for coinflip(), which is added to
random).
"""

import sys
import os
import unittest
import warnings
import random
import math

def coinflip():
    """ Return either -1 or +1. """
    return random.choice((-1,+1))

def sign(n):
    """
    Return -1 or 1 depending on the sign of n, or 0 if the
    input value is 0.
    """
    if n == 0:
        return 0
    elif n < 0:
        return -1
    else:
        return 1

def lerp(t, a, b):
    """
    Linearly interpolate between a and b, returning the
    number at point t, where t is between 0.0 and 1.0.
    """
    return a + t * (b-a)

def triangular(n):
    """
    Return the nth number in the triangluar series: 1, 3, 6,
    10, 15, 21, 28, etc.
    """
    return reduce(lambda i,j: i+j, range(n+1))

def clamp(v, a, b):
    """
    Return v clamped between a and b.
    """
    return max(min(a,b), min(max(a,b), v))

def limit(num, minimum=None, maximum=None, warn=True):
    """
    Returns the given number, but limited to within minimum
    and maximum provided. Warning is raised if warn is True.
    """
    if (None not in (minimum, maximum)) and minimum > maximum:
        raise Error("Minimum must be less than or equal to maximum", minimum, maximum)
    new_num = num    
    if maximum != None:
        new_num = min(maximum, new_num)
    if minimum != None:
        new_num = max(minimum, new_num)
    if new_num != num and warn:
        warnings.warn("%s out of bounds (%s to %s)" % (num, minimum, maximum))
    return new_num


class Error(Exception):
    def __init__(self, message, *args):
        self.message = message
        self.args = args
        

# Inject functions into the modules you wish they were in in the first place.
math.sign = sign
math.lerp = lerp
math.triangular = triangular
math.clamp = clamp
random.coinflip = coinflip

