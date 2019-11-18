#!/usr/bin/env python

# * **************************************************************** **
#
# File: EdAsm.py
# Desc: Front-end for the token assembler
# Note:
#
# Author: Brian Danilko, Likeable Software (brian@likeablesoftware.com)
#
# Copyright 2006, 2014, 2016, 2017 Microbric Pty Ltd.
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

from __future__ import print_function
from __future__ import absolute_import

import sys
import argparse

from lib import token_assembler
from lib import hl_parser
from lib import io
from lib import util
from lib import audio


def assemble(options):

    download_bytes, download_str, download_type, version = \
        token_assembler.assemble_file(options.srcPath, options.debug)

    if (len(download_bytes) == 0):
        print("ERROR - No output produced")
        return

    # some sort of output
    print("Assembly completed of %s type file: %s -- created %d bytes of tokens and header" %
          (download_type, options.srcPath, len(download_str)))

    versionNumber = (version[0] << 4) + version[1]
    versionString = chr(versionNumber) + chr(255 - versionNumber)
    # print(versionNumber, ord(versionString[0]), ord(versionString[1]), download_type)

    full_download_str = versionString + download_str
    full_download_bytes = [versionNumber, 255 - versionNumber]
    full_download_bytes.extend(download_bytes)
    print(len(full_download_bytes))

    if (options.binFile is not None):
        if (options.preamble):
            download_str = full_download_str
        print("Writing %d bytes to file: %s" % (len(download_str), options.binFile.name))
        options.binFile.write(download_str)
        options.binFile.close()

    if (options.wavFilename is not None):
        audioFile = audio.Output(".", options.wavFilename)
        audioFile.WriteWav(full_download_bytes)


def ProcessCommandArgs(args):
    """Handle the command args and display usage if needed.
       Note that the usage is in English as we don't necessarily
       have the language file to use. Also, this will be run in
       the server, which shouldn't make mistakes."""

    # shenanigans to ensure order of the elements for help text
    levelChoices = (("error", io.LEVEL.ERROR), ("top", io.LEVEL.TOP),
                    ("warn", io.LEVEL.WARN), ("info", io.LEVEL.INFO),
                    ("verbose", io.LEVEL.VERBOSE,), ("debug", io.LEVEL.DEBUG))

    version = "1.2.11"
    parser = argparse.ArgumentParser(prog="EdAsm.py",
                                     description="Token assembler for Edison and Ed.Py, version %s" % (version,))

    parser.add_argument("-v", action="version", version="%(prog)s " + version)

    parser.add_argument("-r", "--reghelp", action="store_true", dest="reghelp",
                        help="Output all of the device types, locations and registers")

    parser.add_argument("-d", "--debug", action="store_true", dest="debug",
                        help="Output parsing information.")

    parser.add_argument("-s", "--source", action="store_true", dest="source",
                        help="Output source info with debug info.")

    parser.add_argument("-w", "--wav",
                        dest="wavFilename", default=None,
                        help="Output a wav file of the assembled code.")

    parser.add_argument("-b", "--bin", type=argparse.FileType('wb', 0),
                        dest="binFile", default=None,
                        help="Output a binary file of the assembled code.")

    parser.add_argument("-p", "--preamble", action="store_true", dest="preamble",
                        help="Add preamble to the binary file written.")

    parser.add_argument("-l", type=util.LowerStr,
                        choices=list(zip(*levelChoices))[0], default="error",  # default="debug",
                        help="Output level (default:%(default)s). " +
                        "\nAll output from previous levels and this one will be generated")

    parser.add_argument("srcPath", metavar="SRC", nargs='?', default=None,
                        help="Path to the source to be assembled")

    parsed = parser.parse_args(args)

    outputLevel = [x[1] for x in levelChoices if x[0] == parsed.l][0]

    if (outputLevel >= 0):
        # setup output
        io.Out.SetSink(io.SINK.CONSOLE)
        io.Out.SetMaxLevel(outputLevel)
        # io.Out.SetReRaise(parsed.reraise)

    if (parsed.source and not parsed.debug):
        print("Warning: --source (or -s) makes no sense without --debug (or -d).")

    if (parsed.preamble and parsed.binFile is None):
        print("Warning: --preamble (or -p) makes no sense without --bin (or -b).")

    if (parsed.reghelp):
        print("Device type, locations and register help")
        print("----------------------------------------")
        hl_parser.dump_reg_help()
        sys.exit(0)

    if (parsed.srcPath is None):
        print("Error -- missing source path")
        sys.exit(0)

    return parsed


def main(args):
    # clear global memory
    hl_parser.reset_devices_and_locations()
    token_assembler.reset_tokens()

    pargs = ProcessCommandArgs(args)

    assemble(pargs)


#####################################
if __name__ == "__main__":
    main(sys.argv[1:])
