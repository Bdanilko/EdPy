#!/usr/bin/env python2
# * **************************************************************** **
# File: io.py
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

""" Module providing input/output support including an interface to translated strings. """

from __future__ import print_function
from __future__ import absolute_import

import json
import re
import sys
import traceback
import types

from . import util

# Translation string enumeration - returns a number
TS = util.Enum("ELPY_SPECIAL_FAIL",
               "TOP_PREFIX", "ERROR_PREFIX", "WARN_PREFIX", "INFO_PREFIX", "VERBOSE_PREFIX", "DEBUG_PREFIX",
               "FILE_OPEN_ERROR", "BAD_INPUT_CHARS",

               "PARSE_START", "PARSE_ERROR", "PARSE_NAME_REUSED",
               "PARSE_INVALID_STATEMENT", "PARSE_GLOBAL_ORDER",
               "PARSE_IMPORT_NOT_ED", "PARSE_IMPORT_ORDER",
               "PARSE_SYNTAX_ERROR", "PARSE_NOT_SUPPORTED", "PARSE_TOO_COMPLEX",
               "PARSE_NOT_IN_LOOP", "PARSE_CLASS_ARG0_NOT_SELF",
               "PARSE_MIXED_RETURNS", "PARSE_CLASS_ALL_STATEMENTS_IN_FUNCTIONS",
               "PARSE_CLASS_NO_BASES_ALLOWED", "PARSE_CONST_NOT_INT",
               "OPT_START", "OPT_RESERVED_NAME",
               "OPT_INCORRECT_ARG_USE", "OPT_INCORRECT_ARG_DEFINE",
               "OPT_VAR_NOT_BOUND", "OPT_VAR_NOT_INT", "OPT_VAR_TYPE_CHANGED",
               "OPT_STRING_NOT_ALLOWED", "OPT_LIST_NOT_ALLOWED",
               "OPT_CLASS_INIT_ERROR", "OPT_CLASS_DATA_ERROR",
               "OPT_NOT_CLASS_REF", "OPT_NOT_ASSIGNABLE",
               "OPT_SLICE_NOT_ALLOWED", "OPT_LCL_HIDES_GLB",
               "OPT_NOT_A_GLOBAL_VAR", "OPT_WRITE_TO_ED_PY_CONSTANT",
               "OPT_FUNCTION_NOT_DEFINED", "OPT_NOT_SUPPORTED",
               "OPT_VAR_MUST_BE_TS_OR_LIST", "OPT_ONLY_AT_TOP_LEVEL",
               "OPT_SELF_NOT_IN_METHOD",
               "OPT_UNKNOWN_FUNCTION", "OPT_UNKNOWN_ED_FUNCTION",
               "OPT_MISSING_ED_IMPORT",
               "OPT_CONSTANT_TOO_NEGATIVE", "OPT_CONSTANT_TOO_POSITIVE",
               "OPT_ED_ASSIGN_NOT_CONSTANT", "OPT_ED_ASSIGN_AGAIN",
               "OPT_ED_ASSIGN_BAD_VALUE", "OPT_ED_ASSIGN_NOT_SET",
               "OPT_ED_ASSIGN_IN_FUNCTION", "OPT_ED_FUNCTION_NOT_AVAILABLE",
               "OPT_ED_FUNCTION_NOT_USEFUL", "OPT_ED_WARN_TUNESTRING_END",
               "OPT_ED_LIST_TOO_LONG", "OPT_BAD_EVENT_NUMBER",

               "CMP_START", "CMP_INTERNAL_ERROR", "CMP_VAR_NOT_BOUND",
               "ASM_START", "ASM_MEM_OVERFLOW", "ASM_INTERNAL_ERROR",
)

# Output level
LEVEL = util.Enum("ERROR", "WARN", "TOP", "INFO", "VERBOSE", "DEBUG")

# SINK.CONSOLE is to stdout/stderr, SINK.JSON is to the JSON object,
# SINK.TEST outputs the number instead of the text to make comparisons easier
SINK = util.Enum("CONSOLE", "JSON", "BOTH", "TEST")

# DUMP mask to signal that different datastructures should be dumped
DUMP = util.Mask("PARSER", "OPTIMISER", "COMPILER", "ASSEMBLY", "BINARY")

# ############ Json output class ###############################################


class JsonOutput(object):
    """Accumulate output for the JSON output sink."""

    def __init__(self):
        self.error = False
        self.messages = []
        self.wavFilename = None

    def Out(self, level, message):
        if (level == LEVEL.ERROR):
            self.error = True
        self.messages.append(message)  # message already has the level encoded in it

    def ForceError(self, error):
        self.error = error

    def SetWavFilename(self, wavFilename):
        self.wavFilename = wavFilename

    def Convert(self):
        structure = {
            "error": self.error,
            "messages": self.messages,
            "wavFilename": self.wavFilename
        }
        return json.JSONEncoder().encode(structure)


# ############ Output class ###############################################


class OutClass(object):
    def __init__(self):
        self.outputSink = SINK.CONSOLE
        self.maxOutputLevel = LEVEL.VERBOSE
        self.reRaise = False
        self.dumpMask = 0
        self.langFileHandle = None
        self.jsonOutput = JsonOutput()
        self.errorRaised = False
        self.outputString = ""

        self.errorRawContextLevel = 0
        self.errorRawContext = ["", "", "", "", "", "", "", "", "", ""]

        self.rawPrefix = [
            (TS.ERROR_PREFIX, "ERR"),
            (TS.WARN_PREFIX, "WARN"),
            (TS.TOP_PREFIX, "TOP"),
            (TS.INFO_PREFIX, "INFO"),
            (TS.VERBOSE_PREFIX, "VERB"),
            (TS.DEBUG_PREFIX, "DBG")
        ]

        self.transPrefix = []
        for num, msg in self.rawPrefix:
            # TODO: Do the actual translation
            self.transPrefix.append(msg)

    def SetSink(self, sink):
        if (SINK.isValid(sink)):
            self.outputSink = sink
        else:
            self.FatalRaw("Invalid util.Enum SINK constant")

    def SetMaxLevel(self, level):
        if (LEVEL.isValid(level)):
            self.maxOutputLevel = level
        else:
            self.FatalRaw("Invalid util.Enum LEVEL constant")

    def SetLangFileHandle(self, langFileHandle):
        self.langFileHandle = langFileHandle

    def SetReRaise(self, reRaise):
        self.reRaise = reRaise

    def IsReRaiseSet(self):
        return self.reRaise

    def WasErrorRaised(self):
        return self.errorRaised

    def GetOutputAsString(self):
        return self.outputString

    def SetInfoDumpMask(self, dumpMask):
        if (DUMP.isValid(dumpMask)):
            self.dumpMask = dumpMask
        else:
            self.FatalRaw("Invalid util.Mask DUMP mask")

    def GetInfoDumpMask(self):
        return self.dumpMask

    def ForceJsonError(self, error):
        self.jsonOutput.ForceError(error)

    def SetWavFilename(self, wavFilename):
        self.jsonOutput.SetWavFilename(wavFilename)

    def Flush(self):
        if (self.outputSink == SINK.BOTH or self.outputSink == SINK.JSON):
            print(self.jsonOutput.Convert())

    def FatalRaw(self, rawText):
        """Output a fatal error without translation (so it can
           be used on translation errors!) to the stderr AND configured sync.
        """
        print("FATAL: " + rawText, file=sys.stderr)
        print("----------------\nStack Trace:")
        stack = traceback.format_stack()
        for l in stack[:-1]:
            print(repr(l))
        sys.exit(1)

    def DebugRaw(self, rawText, *args):
        """Output debug information without translation if the sink is CONSOLE.
        """
        if ((self.maxOutputLevel >= LEVEL.DEBUG) and
            (self.outputSink == SINK.CONSOLE or self.outputSink == SINK.BOTH)):
            if (not args):
                print("**DebugRaw**:", rawText)
            else:
                print("**DebugRaw**:", rawText, *args)

    def SetErrorRawContext(self, level, rawText):
        if (level > 0 and level < 10):
            self.errorRawContextLevel = level
            self.errorRawContext[level - 1] = rawText

    def ErrorRaw(self, rawText, *args):
        """Output error information without translation if the sink is CONSOLE.
        """
        self.errorRaised = True
        if ((self.maxOutputLevel >= LEVEL.ERROR) and
            (self.outputSink == SINK.CONSOLE or self.outputSink == SINK.BOTH)):

            for level in range(self.errorRawContextLevel):
                print("**ErrorRaw** - Context:", level, self.errorRawContext[level])

            if (not args):
                print("**ErrorRaw**:", rawText)
            else:
                print("**ErrorRaw**:", rawText, *args)

    def Top(self, stringNumber, rawText, *args):
        self.__Out(LEVEL.TOP, stringNumber, rawText, args)

    def Error(self, stringNumber, rawText, *args):
        self.errorRaised = True
        self.__Out(LEVEL.ERROR, stringNumber, rawText, args)

    def Warning(self, stringNumber, rawText, *args):
        self.__Out(LEVEL.WARN, stringNumber, rawText, args)

    def Info(self, stringNumber, rawText, *args):
        self.__Out(LEVEL.INFO, stringNumber, rawText, args)

    def Verbose(self, stringNumber, rawText, *args):
        self.__Out(LEVEL.VERBOSE, stringNumber, rawText, args)

    def __Out(self, outputLevel, stringNumber, rawText, args):
        """Output to sink, after translation, of text - replacing
           args (w/o translation) if they exist.
           Args in the text are denoted by {number[!.*][:.*]} as per the python
           Formatter syntax.
        """

        # Is this level desired to be output?
        if (outputLevel > self.maxOutputLevel):
            return

        # self.DebugRaw(outputLevel, stringNumber, rawText, len(args), args)

        # Count the number of pos arguments in the rawText. This must
        # equal the args (and the pos arguments in the translated text).
        potentialsRe = re.compile("\{(?!\{).*?\}")  # potential format markers
        potentials = re.findall(potentialsRe, rawText)
        # self.DebugRaw("potentials = {}".format(potentials))
        posCount = 0
        if (len(potentials) > 0):
            found = []
            pArgsRe = re.compile("\{(\d+)(?:[:!].*)?\}")

            for pot in potentials:
                match = re.match(pArgsRe, pot)
                # if match is None:
                #    self.FatalRaw("Bad syntax for translation string positional arguments.")

                # group 1 is the decimal pos number
                pos = int(match.group(1))
                # self.DebugRaw("match = {}".format(match.group(0)))
                if (pos not in found):
                    found.append(pos)

            # Ensure that there are no gaps in the positional arguments
            while len(found):
                if (posCount not in found):
                    self.FatalRaw("TransString positional arguments are not contiguous.")
                found.remove(posCount)
                posCount += 1

        # posCount is the number of positional arguments, so must match the length of args
        # self.DebugRaw("posCount = {}".format(posCount))
        if (posCount != len(args)):
            self.FatalRaw("TransString pos count {0} doesn't match the number of args {1}".format(posCount, len(args)))

        # TODO: Do the actual translation. For now just skipping that bit
        transText = self.transPrefix[outputLevel] + ": " + rawText
        # self.DebugRaw(transText + str(args))
        if (posCount):
            outText = transText.format(*args)
        else:
            outText = transText

        if (len(self.outputString) > 0):
            self.outputString += "{:s}|".format(outText)
        else:
            self.outputString = "|{:s}|".format(outText)

        if (self.outputSink == SINK.CONSOLE or self.outputSink == SINK.BOTH):
            print(outText)

        if (self.outputSink == SINK.JSON or self.outputSink == SINK.BOTH):
            self.jsonOutput.Out(outputLevel, outText)

        if (self.outputSink == SINK.TEST):
            print(outputLevel, ',', stringNumber, sep='', end='')
            if (posCount):
                for a in args:
                    print(',', a, sep='', end='')
                print()

    def DebugDumpObjectRaw(self, obj, name=''):

        if ((self.maxOutputLevel >= LEVEL.DEBUG) and
            (self.outputSink == SINK.CONSOLE or self.outputSink == SINK.BOTH)):

            filt = [types.MethodType]
            print("**DebugDump**: object %s (%r)" % (name, obj))
            dir_data = dir(obj)
            data = {}

            for d in dir_data:
                if ((d in ("__module__", "__doc__")) or
                    (not d.startswith("__"))):

                    temp = getattr(obj, d, None)
                    filter_out = False
                    if (temp is not None):
                        filter_out = False
                        for f in filt:
                            if (type(temp) is f):
                                filter_out = True
                                break

                        if (not filter_out):
                            data[d] = temp

            print("**DebugDump** -- %s" % (data))


# the singleton which everyone will use
Out = OutClass()
