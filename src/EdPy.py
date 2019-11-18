#!/usr/bin/env python2
# * **************************************************************** **
# File: EdPy.py
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

""" Script to sequence all components of the Ed.Py compilation process. """

import sys
import argparse
import os
import os.path
import re

from lib import io, util, audio
from lib import parser, program
from lib import optimiser, compiler
from lib import token_assembler
from lib import hl_parser

# To disable the log output, put use=False as the only parameter
LOG = util.SimpleLog(use=True)

INT_ERROR_RE = re.compile("internal error")

def main(args):

    # Do the parsing first
    p = program.Program()
    rtc = parser.Parse(args.srcPath.name, p)
    # LOG.log("PAR rtc:{:d}".format(rtc))

    if (rtc == 0):
        rtc = optimiser.Optimise(p)
        # LOG.log("OPT rtc:{:d}".format(rtc))
        if (rtc == 0):
            rtc, statements = compiler.Compile(p, args.compilerOpt)
            # LOG.log("COM rtc:{:d}".format(rtc))

            if (args.listing is not None):
                for s in statements:
                    args.listing.write(s + "\n")
                args.listing.close()

    if (rtc == 0):

        # clear global memory
        hl_parser.reset_devices_and_locations()
        token_assembler.reset_tokens()

        # print(statements)
        dBytes, dString, dType, version = token_assembler.assemble_lines(statements, False)
        # print("Size:", len(dBytes), len(dString), dType, version)
        if (len(dBytes) == 0 or dType == 0 or version == 0):
            rtc = 1
        elif (not args.checkOnly) and (not args.nowav):
            versionNumber = (version[0] << 4) + version[1]
            versionString = chr(versionNumber) + chr(255 - versionNumber)
            # print(versionNumber, ord(versionString[0]), ord(versionString[1]), download_type)

            if (not args.nowav):
                absSrcPath = os.path.abspath(args.srcPath.name)
                path = os.path.dirname(absSrcPath)
                a = audio.Output(path)

                io.Out.DebugRaw("WavPath:", a.GetWavPath())
                io.Out.SetWavFilename(a.GetWavPath())

                full_download_str = versionString + dString
                full_download_bytes = [versionNumber, 255 - versionNumber]
                full_download_bytes.extend(dBytes)
                # print(len(full_download_bytes))

                LOG.log("WAV size:{:d} ver:{:d} name:{:s}".format(len(full_download_bytes),
                                                                      versionNumber,
                                                                      a.GetWavPath()))

                a.WriteWav(full_download_bytes)

                if (args.binary is not None):
                    args.binary.write(full_download_str)
                    args.binary.close()

    return rtc


def ProcessCommandArgs(args):
    """Handle the command args and display usage if needed.
       Note that the usage is in English as we don't necessarily
       have the language file to use. Also, this will be run in
       the server, which shouldn't make mistakes."""

    # shenanigans to ensure order of the elements for help text
    outputChoices = (("json", io.SINK.JSON), ("console", io.SINK.CONSOLE),
                     ("both", io.SINK.BOTH), ("test", io.SINK.TEST))

    levelChoices = (("error", io.LEVEL.ERROR), ("warn", io.LEVEL.WARN),
                    ("top", io.LEVEL.TOP), ("info", io.LEVEL.INFO),
                    ("verbose", io.LEVEL.VERBOSE,), ("debug", io.LEVEL.DEBUG))

    testChoices = ("pass", "fail")

    version = "1.2.11"
    parser = argparse.ArgumentParser(prog="EdPy.py", description="Full Ed.Py compiler, version %s - from source to wav file." % (version,))
    parser.add_argument("langPath", metavar="LANG", type=argparse.FileType('r'),
                        help="Path to a language file")
    parser.add_argument("srcPath", metavar="SRC", type=argparse.FileType('r'),
                        help="Path to the source to be compiled")
    parser.add_argument("-v", action="version", version="%(prog)s " + version)

    parser.add_argument("-c", dest="checkOnly", action="store_true",
                        help="Check syntax only, don't generate the WAV file")

    parser.add_argument("-r", dest="reraise", action="store_true",
                        help="Reraise exceptions after being caught. Used for testing/debugging")

    parser.add_argument("-s", dest="compilerOpt", action="store_false",
                        help="Disable compiler optimisations (and make downloads slower)")

    parser.add_argument("-d", dest="dump", type=int, default=0,
                        help="Debug info dumps at different times. Mask - " +
                        "0x01 after parse, 0x02 after optimiser, 0x04 after compiler, " +
                        "0x08 assembly list, 0x10 final binary")

    # parser.add_argument("-a", dest="saveAssembly", action="store_true",
    #                     help="save the assembly file and stop (no WAV file)")

    parser.add_argument("-a", dest="listing", metavar="LISTING", type=argparse.FileType('w'),
                        help="save the assembly list file")

    parser.add_argument("-b", dest="binary", metavar="BINARY", type=argparse.FileType('w'),
                        help="save the final binary file")

    parser.add_argument("-w", dest="nowav", action="store_true",
                        help="don't output the wav file")

    # TODO: Change defaults back to normal ones for web app
    parser.add_argument("-o", type=util.LowerStr, default="json",  # default="console",
                        choices=list(zip(*outputChoices))[0],
                        help="Output location (default:%(default)s)")
    parser.add_argument("-l", type=util.LowerStr,
                        choices=list(zip(*levelChoices))[0], default="warn",  # default="debug",
                        help="Output level (default:%(default)s). " +
                        "\nAll output from previous levels and this one will be generated")

    parser.add_argument("-x", type=util.LowerStr,
                        choices=testChoices, help="Special tests. " +
                        "INSTEAD of doing normal processing, do the special test")

    # print("Args:",  args)
    parsed = parser.parse_args(args)

    sinkNumber = [x[1] for x in outputChoices if x[0] == parsed.o][0]
    outputLevel = [x[1] for x in levelChoices if x[0] == parsed.l][0]

    io.Out.SetLangFileHandle(parsed.langPath)
    io.Out.SetSink(sinkNumber)
    io.Out.SetMaxLevel(outputLevel)
    io.Out.SetReRaise(parsed.reraise)
    io.Out.SetInfoDumpMask(parsed.dump)

    return parsed


if __name__ == '__main__':

    LOG.log("START - Cmd line:{}".format(sys.argv[1:]))

    rtc = 1
    # Console so that debugging can work while we do the parsing
    io.Out.SetSink(io.SINK.CONSOLE)

    io.Out.DebugRaw("Command line args", sys.argv[1:])
    parsed = ProcessCommandArgs(sys.argv[1:])
    io.Out.DebugRaw("Command line args", parsed)

    if parsed.x:
        if parsed.x == "pass":
            # want to output a wav file and json which has error = False
            absSrcPath = os.path.abspath(parsed.srcPath.name)
            path = os.path.dirname(absSrcPath)
            a = audio.Output(path)

            io.Out.DebugRaw("WavPath:", a.GetWavPath())
            io.Out.SetWavFilename(a.GetWavPath())
            io.Out.ForceJsonError(False)

            a.CreateDebugWav()

            rtc = 0

        elif parsed.x == "fail":
            # want to output NO wav file and json which has error = True
            io.Out.Error(io.TS.ELPY_SPECIAL_FAIL, "Debug Error")

        else:
            io.Out.FatalRaw("Invalid special option: {}".format(parsed.x))

    else:
        # normal processing
        rtc = main(parsed)

    totalOutput = ""
    totalProgram = []
    m = None
    MAX_OUT_BYTES = 500-3
    MAX_PRG_BYTES = 5000-3

    try:
        output = io.Out.GetOutputAsString()
        # print(output)
        m = INT_ERROR_RE.search(output)

        # limit the output sizes
        if (len(output) > MAX_OUT_BYTES):
            totalOutput = "..." + output[-MAX_OUT_BYTES:]
        else:
            totalOutput = output

        if (m is not None):
            parsed.srcPath.seek(0)
            program = parsed.srcPath.readlines()
            print("Program", program)
            prevBytes = 0
            for line in program:
                if (len(line.strip())==0 or line.strip().startswith('#')):
                    totalProgram.append("")
                    # limiting the output so a bad program doesn't screw the log up
                    prevBytes += 5
                else:
                    testLine = line.rstrip()
                    testLen = len(testLine)+prevBytes
                    if (testLen > MAX_PRG_BYTES):
                        allowedBytes = MAX_PRG_BYTES-testLen
                        totalProgram.append(testLine[0:allowedBytes]+"...")
                        break
                    else:
                        totalProgram.append(testLine)
                        prevBytes += len(testLine)
                #print("Bytes:", prevBytes, len(totalProgram[-1]))

    except Exception as e:
        # if we fail, that's ok - but not good
        totalOutput += "LOG EXC:{:s}".format(e)


    if (m is not None):
        LOG.log("END rtc:{:d} INTERNAL ERROR output:|{:s}|\n".format(rtc, totalOutput))
        LOG.log("PRG {:s}".format(totalProgram))
    else:
        LOG.log("END rtc:{:d} output:|{:s}|\n".format(rtc, totalOutput))
    LOG.close()

    io.Out.Flush()

    sys.exit(rtc)

else:
    io.Out.FatalRaw("This file is a script and can not be imported!")
