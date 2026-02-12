"""
DEPRECATED. Utility functions.
"""

@deprecated
def frame(num, _min, _max):
    """
    Deprecated. Use sift.util.math_ext.clamp() or sift.util.math_ext.limit().
    """
    return max(_min, min(_max, num))

