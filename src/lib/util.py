#!/usr/bin/env python2
# * **************************************************************** **
# File: util.py
# Requires: Python 2.7+ (but not Python 3.0+)
# Note: For history, changes and dates for this file, consult git.
# Author: Brian Danilko, Likeable Software (brian@likeablesoftware.com)
# Copyright 2015-2017 Microbric Pty Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License (in the doc/licenses directory)
# for more details.
#
# * **************************************************************** */

""" Module providing utility functions. """

from __future__ import print_function
from __future__ import absolute_import

import sys
import datetime
import os
import os.path


class Enum(object):
    """ Provides a 'C'-like enumeration for python
        e.g. ERRORS = Enum("OVERFLOW", "DIV_BY_ZERO")
    """

    def __init__(self, *keys):
        self.__dict__.update(zip(keys, range(len(keys))))

    def len(self):
        return len(self.__dict__.keys())

    def isValid(self, value):
        return (value >= 0) and (value < self.len())


class Mask(object):
    """ Provides a 'C'-like enumeration of mask values for python
        (so values are powers of 2, so they can be orred together)
        e.g. DUMP = Mask("PARSER", "OPTIMISER")
    """

    def __init__(self, *keys):
        values = [2**i for i in range(len(keys))]
        self.__dict__.update(zip(keys, values))

    def len(self):
        return len(self.__dict__.keys())

    def isValid(self, value):
        """value can be an 'or' of possible keys"""
        return (value >= 0) and (value < (2 ** self.len()))


class SimpleLog(object):
    """ Provide a VERY SIMPLE log of execution. Just start, and end with timestamps. So
        if something crashes then should be able to see that it happened."""

    def __init__(self, use=True, fileName="EdPy.log", maxBytes=2000000):
        self.fh = None
        self.use = use
        self.start = datetime.datetime.now()
        self.fileName = fileName
        self.maxBytes = maxBytes

    def formatTimestamp(self, ts=None):
        if (ts is None):
            return datetime.datetime.now.isoformat(' ')
        else:
            return ts.isoformat(' ')

    def formatDelta(self, delta):
        return "+{:d}.{:06d}s".format(delta.seconds, delta.microseconds)

    def open(self):
        if (not self.use):
            return

        # try to rename if it's too large. But if there is an error then just
        # continue on.
        try:
            # if there is an existing file then see if it's too large
            if (os.path.exists(self.fileName)):
                bytes = os.path.getsize(self.fileName)
                if (bytes >= self.maxBytes):
                    os.rename(self.fileName, self.fileName + ".old")
        except:
            pass

        try:
            # Non-buffered appending log
            self.fh = open(self.fileName, "a", buffering=0)
        except:
            self.fh = None

    def log(self, line):
        if (not self.use):
            return

        if (self.fh is None):
            self.open()

        if (self.fh is not None):
            now = datetime.datetime.now()
            delta = now - self.start
            print("{:s} dur:{:s} pid:{} msg:{:s}".format(self.formatTimestamp(now),
                                                         self.formatDelta(delta),
                                                         os.getpid(), line), file=self.fh)
            self.fh.flush()

    def close(self):
        if (not self.use):
            return

        if (self.fh is not None):
            self.fh.close()
            self.fh = None


def LowerStr(inString):
    """Returns a lower case string from any string. Useful for argparse types"""
    return inString.lower()


def CheckPythonVersion():
    ver = sys.version_info

    # Using version 2.0 access to version (instead of assuming 2.7 here)
    if (ver < (2,7)):
        rawText = "Python version must be 2.7 or greater,"
        rawText += " this Python version is %d.%d." % (ver[0], ver[1])
        print("FATAL: " + rawText, file=sys.stderr)
        sys.exit(1)

# do this check on every import of util!
CheckPythonVersion()
