#!/usr/bin/env python2
# * **************************************************************** **
# File: TranStrings.py
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

"""Script to ensure that all uses of Translatable Strings (TS)
   are consistent"""

from __future__ import print_function
from __future__ import absolute_import

import sys
import argparse
import os
import os.path
import re

from lib import io

# TS1_RE = re.compile("io.TS.\(\w+\),\s*\(.*\)\s*,")
TS1_RE = re.compile(r"io\.TS\.([_a-zA-Z0-9-]+?)\s*,\s*([\'\"])(.*?)\2\s*[,)]")
IO_FILE_RE = re.compile(r"TS\.([_a-zA-Z0-9-]+?)\s*,\s*([\'\"])(.*?)\2\s*[,)]")


def main(args):
    """Search in the all files in base dirs and below"""
    uses = {}
    fileList = findPythonFiles(args.baseDir, args.s)
    errors = findTSUsages(fileList, uses, args)

    if (args.v > 0):
        print("\nTS strings:")
        for k in uses:
            total = 0
            for i in uses[k][2]:
                total += int(i)
            if (args.v > 1):
                print()
            print("    {0:>25}  |{1}|  (total uses:{2})".format(k, uses[k][0], total))
            if (args.v > 1):
                for i in range(len(uses[k][1])):
                    print(" "*30, "used {1} times in file {0}".format(uses[k][1][i], uses[k][2][i]))

    # check if any of io.TS are not used, or they are bad values
    ts = io.TS.__dict__
    notUsed = ts.keys()

    for k in uses:
        if (k not in ts):
            print("\nERROR - key {0} not in io.TS enumeration!".format(k))
            errors += 1
        else:
            if (k in notUsed):
                notUsed.remove(k)

    if notUsed:
        print("\nWARN - io.TS enumerations that were not used:")
        for k in notUsed:
            print("    {0}".format(k))

    if (args.v > 0):
        if (errors == 0):
            print("\nNo inconsistent use of translation strings found")
    return errors

def findTSUsages(fileList, uses, args):
    errorList = []
    for f in fileList:
        if (args.v > 2):
            print("Searching file:", f)
        fh = open(f, 'rb')
        lines = fh.readlines()
        fh.close()

        fileData = ""

        for l in lines:
            line = l.strip(' \t\r\n\v')
            fileData += line
        # print(fileData)

        if f.endswith("lib/io.py"):
            regExp = IO_FILE_RE
        else:
            regExp = TS1_RE

        for m in regExp.finditer(fileData):
            key = m.group(1)
            value = m.group(3)
            # print("Found:", key, value)
            if (key not in uses):
                uses[key] = (value, [f], [1])
            else:
                if (uses[key][0] != value):
                    print("ERROR - string is not consistent for key:", key)
                    print("     First value:|{0}|, file:{1}".format(uses[key][0], uses[key][1][0]))
                    if (uses[key][1][0] == f):
                        print("     This value: |{0}|, same file".format(value))
                    else:
                        print("     This value: |{0}|, file:{1}".format(value, f))
                    print()
                    if (key not in errorList):
                        errorList.append(key)
                else:
                    files = uses[key][1]
                    times = uses[key][2]
                    found = False
                    for i in range(len(files)):
                        if files[i] == f:
                            found = True
                            times[i] += 1
                            break
                    if (not found):
                        files.append(f)
                        times.append(1)

                    uses[key] = (value, files, times)

    return len(errorList)


def findPythonFiles(baseDirs, skipDirs):
    pythonFiles = []

    skipAbsDirs = []
    skipAbsFiles = []
    for s in skipDirs:
        absPath = os.path.abspath(s)
        if os.path.isfile(absPath):
            skipAbsFiles.append(absPath)
        else:
            skipAbsDirs.append(absPath)

    for b in baseDirs:
        # print(b)
        if os.path.isfile(b):
            pythonFiles.append(os.path.abspath(b))
            continue

        if not os.path.isdir(b):
            print("ERROR - problem with directory:", b, "- aborting!")
            sys.exit(1)

        path = os.path.abspath(b)
        for root, dirs, files in os.walk(path):
            absRoot = os.path.abspath(root)

            # check if this directory is a subdirectory of a skip one
            skipRoot = False
            for check in skipAbsDirs:
                common = os.path.commonprefix([absRoot, check])
                # print(absRoot, check, common, len(check), len(common))
                if (len(common) == len(check)):
                    skipRoot = True
                    break
            if skipRoot:
                continue

            # print(root, dirs, files)
            for f in files:
                absFile = os.path.normpath(os.path.join(root, f))
                if (absFile in skipAbsFiles):
                    continue
                if os.path.splitext(absFile)[1] == ".py":
                    pythonFiles.append(absFile)

    # get rid of duplicates -- order is not important
    # print(pythonFiles)
    reducedFiles = []
    while pythonFiles:
        testFile = pythonFiles[0]
        pythonFiles = pythonFiles[1:]

        for comp in pythonFiles:
            if os.path.samefile(testFile, comp):
                continue

        reducedFiles.append(testFile)

    return reducedFiles


def ProcessCommandArgs(args):
    """Handle the command args and display usage if needed.
       Note that the usage is in English as we don't necessarily
       have the language file to use. Also, this will be run in
       the server, which shouldn't make mistakes."""

    parser = argparse.ArgumentParser(prog="TransStrings.py",
                                     description="Utility to ensure consistent use of translatable strings (TS).")
    parser.add_argument("--version", action="version", version="%(prog)s 0.5")
    parser.add_argument("-v", action="count", default=0,
                        help="More verbose output (can be used multiple times)")

    parser.add_argument("-s", action="append", default=[],
                        help="Directories to be skipped")

    parser.add_argument("baseDir", nargs='*', default=["."],
                        help="Base dir(s) to recursively look in for python files")

    parsed = parser.parse_args(args)

    return parsed


if __name__ == '__main__':
    # print("Command line args - before parse:", sys.argv[1:])
    parsed = ProcessCommandArgs(sys.argv[1:])
    # print("Command line args - after parse:", parsed)
    errors = main(parsed)
    sys.exit(errors)

else:
    print("ERROR - This file is a script and can not be imported!")
