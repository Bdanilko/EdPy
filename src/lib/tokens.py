#!/usr/bin/env python

# * **************************************************************** **
#
# File: tokens.py
# Desc: Operation on token data structures
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

#
# Modified for the EdPy.py versions - starting at 0x60
#
# Token Version handled - (Major/Minor) = 0x6/0x0
# Firmware Version handled - (Major/Minor) = 0xe/0x0, 0x20/0x0
#

from __future__ import print_function
from __future__ import absolute_import

from . import io
from . import program

MIN_BYTE = 0
MAX_BYTE = 0xff
MIN_WORD = -0x7fff
MAX_WORD = 0x7fff
MAX_UWORD = 0xffff

MIN_SBYTE = -0x7f
MAX_SBYTE = 0x7f

# The firmware has a problem correctly computing the CRC when the size is a
# multiple of 256. This function finds all of the 'BAD' lengths so that
# the code can pad up by a byte and get around the firmware problem
def is_bad_length_for_crc(data_len):
    return (data_len >= 254) and ((data_len - 254) % 256 == 0)

# print("Test 254:", is_bad_length_for_crc(254))
# print("Test 255:", is_bad_length_for_crc(255))
# print("Test 509:", is_bad_length_for_crc(509))
# print("Test 510:", is_bad_length_for_crc(510))
# print("Test 511:", is_bad_length_for_crc(511))
# print("Test 765:", is_bad_length_for_crc(765))
# print("Test 766:", is_bad_length_for_crc(766))
# print("Test 767:", is_bad_length_for_crc(767))

# No LCD,  so lcd limit == 0
LIMIT_NAMES = ("Bytes", "Words", "LCD chars", "Event handlers", "Token bytes")
MAX_LIMITS = (256, 256, 0, 16, 4096)


space_types = {'b': 0, 'B': 0, 'w': 1, 'W': 1, 'a': 2, 'A': 2}
space_names = ("Byte", "Word", "LCD")


def AsmError_NO_RET(number, internalError=None, line=0):
    if (internalError):
        io.Out.ErrorRaw(internalError)

    io.Out.Error(io.TS.ASM_INTERNAL_ERROR, "file::: Assembler internal error {0}", number)
    raise program.AssemblerError


def calculate_crc(bytes):
    crc = 0xffff
    for i in range(len(bytes)):
        crc = crc ^ (bytes[i] << 8)
        for j in range(8):
            if (crc & 0x8000 != 0):
                crc = ((crc << 1) ^ 0x1021)
            else:
                crc = crc << 1

    return crc & 0xffff


def word_to_bytes(word):
    word = word & 0xffff
    return (((word >> 8) & 0xff), (word & 0xff))


class TokenStream(object):
    def __init__(self):
        self.clear()

    def clear(self):
        self.token_stream = []          # list of tokens in order
        self.sector_size = -1           # Whether to ack/nak and when
        self.limits = list(MAX_LIMITS)  # limits for the namespaces and tokens
        self.name_space = [[], [], []]  # Variables requested in namespaces
        self.devices = {}               # Devices indexed on location
        self.labels = {}                # Labels that we can jump to
        self.current_sections = []      # The section(s) that we are currently in
        self.section_breaks = []        # Recording where sections start and stop
        self.section_args = []          # ... and the args that were passed with it
        self.section_count = 0          # The number of the current section
        self.version = None             # The version number as (major, minor)
        self.download_type = None       # Can only have one type per download

    def add_token(self, token, explicit_placement=-1):
        spec_type = token.get_type()
        if (spec_type == "finish"):
            if (len(self.current_sections) > 0):
                AsmError_NO_RET(100, "FINISH must be after all sections.")
        elif (spec_type == "data"):
            if ((len(self.current_sections) == 0) or
                (self.current_sections[-1] not in ["main", "event"])):
                AsmError_NO_RET(101, "DATA must be in a 'main' or 'event' section.")

        elif (spec_type == "binary"):
            if ((len(self.current_sections) == 0) or
                (self.current_sections[-1] not in ["firmware"])):
                AsmError_NO_RET(102, "INSERT BINARY must be in a 'firmware' section.")
        else:
            if ((len(self.current_sections) == 0) or
                (self.current_sections[-1] not in ["main", "event"])):
                AsmError_NO_RET(103, "Tokens must be in a 'main' or 'event' section.")

        # Make jump labels local to the section
        jump = token.get_jump_label()
        if (jump):
            if (not jump[1].startswith(':')):
                # a local jump
                token.set_jump_label(jump[0], jump[1] + "_%d" % (self.section_count), jump[2])

        if (explicit_placement < 0):
            self.token_stream.append(token)
        else:
            if (explicit_placement >= len(self.token_stream)):
                AsmError_NO_RET(104, "Explicitly placing a token after the end of the stream.")
            else:
                self.token_stream.insert(explicit_placement, token)

    def add_token_in_fixups(self, token, explicit_placement):
        if (explicit_placement >= len(self.token_stream)):
            AsmError_NO_RET(105, "Explicitly placing a token after the end of the stream.")
        else:
            self.token_stream.insert(explicit_placement, token)

    def add_label(self, name):
        if ((len(self.current_sections) == 0) or
            (self.current_sections[-1] not in ["main", "event"])):
            AsmError_NO_RET(106, "Labels must be in a 'main' or 'event' section.")

        # Make the labels local to the section unless they start with '::'
        # (one ':' has been stripped off)
        if (name.startswith(':')):
            new_name = name
        else:
            new_name = "%s_%d" % (name, self.section_count)

        if (new_name in self.labels):
            AsmError_NO_RET(107, "Label %s defined twice in the same section." % (name))

        self.labels[new_name] = self.stream_marker()

    def stream_marker(self):
        return len(self.token_stream)

    # Define tighter limits on the name spaces
    # ARGS all numbers, ranges NOT checked
    def set_limits(self, b_lim, w_lim, l_lim, e_handlers, t_lim):
        if (self.section_count > 0):
            AsmError_NO_RET(108, "LIMITS must be before all sections.")

        new_limits = [b_lim, w_lim, l_lim, e_handlers, t_lim]
        for i in range(5):
            if (new_limits[i] < 0):
                AsmError_NO_RET(109, "Limit %s can't be less then 0." % (LIMIT_NAMES[i]))
            elif (new_limits[i] > MAX_LIMITS[i]):
                AsmError_NO_RET(110, "Limit %s too large." % (LIMIT_NAMES[i], MAX_LIMITS[i]))

        self.limits = new_limits

    def set_comms(self, sector_size):
        if (sector_size < 0):
            AsmError_NO_RET(111, "Comms sector_size can't be less then 0.")

        self.sector_size = sector_size

    def finish_tokens(self):
        """Absolute last token"""
        pass
        # io.Out.ErrorRaw("IMPLEMENT THIS FUNCTION.")

    # reserve space in the variable name spaces
    # ARGS: space 0-2, start & length are numbers
    def reserve_name_space(self, space, start, length):
        if (self.section_count > 0):
            AsmError_NO_RET(112, "RESERV must be before all sections.")

        if (start < 0 or length <= 0):
            AsmError_NO_RET(113, "Negative start or length is not allowed")

        if ((start + length) > self.limits[space]):
            io.Out.ErrorRaw("Reserve space extends beyond the max for %s space." % (space_names[space]))
            io.Out.Error(io.TS.ASM_MEM_OVERFLOW,
                         "file::: Overflowed {0} memory", space_names[space])
            raise program.AssemblerError


        self.name_space[space].append(("rsvd", "", start, length))

    def add_variable(self, space, name, start, length=0):
        io.Out.DebugRaw("Add_variable space:%s, name:%s, start:%d, length:%d" %
                        (space_names[space], name, start, length))

        if (name == '*'):
            name = ""

        if (length < 0):
            AsmError_NO_RET(114, "Negative length of data is not allowed")

        self.name_space[space].append(("data", name, start, length))

    # Add a device, location and optional name
    # ARGS_CHECKED: type is 0 to 15, location is 0 to 11, size is a byte
    def add_device(self, type, location, size):
        io.Out.DebugRaw("Add_device type:%d, loc:%d, size:%d" % (type, location, size))

        if (self.section_count > 0):
            AsmError_NO_RET(115, "DEVICE must be before all sections.")

        self.devices[location] = (type, size)

    def add_version(self, major, minor):
        io.Out.DebugRaw("Add_version major:%d, minor:%d" % (major, minor))

        if (self.section_count > 0):
            AsmError_NO_RET(116, "VERSION must be before all sections.")

        self.version = (major, minor)

    def add_begin(self, type, arg1=-1, arg2=-1, arg3=-1):
        """Start of a new section"""
        io.Out.DebugRaw("Add_begin type:%s, arg1:%d, arg2:%d, arg3:%d" % (type, arg1, arg2, arg3))

        # do checks to see if this start is OK
        if (type in ["firmware", "main", "event"]):
            if (len(self.current_sections) > 0):
                AsmError_NO_RET(117, "This section %s must be the first section" % (type))

            if (self.download_type):
                if (self.download_type[0] in ["main", "event"] and type in ["firmware"]):
                    AsmError_NO_RET(118, "Can't mix 'firmware' and 'main'/'event' sections")
                elif (self.download_type[0] == "firmware"):
                    AsmError_NO_RET(119, "Can't mix 'firmware' and 'main'/'event' sections " +
                                          "or have multiple 'firmware' sections")
                elif (type == "main" and 'main' in self.download_type):
                    AsmError_NO_RET(120, "Can't have multiple 'main' sections")
                self.download_type.append(type)
            else:
                self.download_type = [type]

        # add the section
        self.current_sections.append(type)
        self.section_breaks.append((type, self.stream_marker(), -1))
        self.section_args.append((arg1, arg2, arg3))
        self.section_count += 1

    def add_end(self, type):
        io.Out.DebugRaw("Add_end type:%s" % (type))

        # check if we are actually in the section?
        if (type not in self.current_sections):
            AsmError_NO_RET(121, "Not in section %s, so can't end it" % (type))

        # add the ending index into the beginning bit
        i = 0
        while i < len(self.section_breaks):
            s_type, start, end = self.section_breaks[i]
            if (s_type == type):
                self.section_breaks[i] = ((s_type, start, self.stream_marker()))
                break
            i += 1
        self.current_sections.remove(type)

    # Output function
    def dump_tokens(self, inc_src=False):
        print("Dumping tokens\n")
        i = 0
        for t in self.token_stream:
            # is this a start of a section?
            for name, start, end in self.section_breaks:
                if (start == i):
                    print(" ****** SECTION START " + name + " *****\n")
                    break

            # Is there a label for this index?
            for name in self.labels:
                if (self.labels[name] == i):
                    if (name.startswith(":")):
                        print("===== FUNCTION :" + name + " =====")
                    else:
                        print(":" + name)
                    break

            if (inc_src and t.source_line):
                print(t.source_line)
            print("%3d: " % (i), end='')
            t.print_token()
            print("")
            i += 1


class TokenAnalyser(object):
    def __init__(self, token_stream):
        self.token_stream = token_stream
        self.name_space_map = [{}, {}, {}]
        self.name_space_max = [0, 0, 0]

    def verify(self):
        return True

    def map_all_variables(self):
        io.Out.SetErrorRawContext(2, "Mapping all variables")
        self.name_space_map = [{}, {}, {}]
        for i in range(3):
            self.map_variables_in_space(i, self.name_space_map[i])

        # self.dump_variable_map()

        # They all fit, now fixup the tokens
        io.Out.SetErrorRawContext(2, "Fixing up variable references")
        for t in self.token_stream.token_stream:
            for index, space, name in t.var_info:
                if (name not in self.name_space_map[space]):
                    AsmError_NO_RET(122, "Variable %s not declared in %s space." % (name, space_names[space]))
                t.fixup_var_byte(index, self.name_space_map[space][name][0])

    def dump_variable_map(self):
        print("\nDumping variable maps:\n")
        for i in range(2):                    # skip LCD
            print("Space:", space_names[i])
            for name in self.name_space_map[i]:
                start, length = self.name_space_map[i][name]
                if (length == 1):
                    print("%10s at %d" % (name, start))
                else:
                    print("%10s at %d-%d" % (name, start, start + length - 1))

            print

    def map_variables_in_space(self, space, v_map):
        # create a map for the variables and fit them in
        io.Out.SetErrorRawContext(2, "Mapping variables in %s space" % (space_names[space]))
        limit = self.token_stream.limits[space]
        variables = self.token_stream.name_space[space]

        fixed_v_free = [(0, limit, limit)]

        # fit in the reserved and fixed variables
        for type, name, start, length in variables:
            if (type == 'data' and start < 0):
                # don't handle unfixed data here
                continue

            end = start + length
            copy_to_end = False
            v_free = fixed_v_free
            fixed_v_free = []

            # print("v_free", v_free)
            # print("v_map", v_map)

            for f_start, f_length, f_end in v_free:
                if (copy_to_end):
                    fixed_v_free.append((f_start, f_length, f_end))
                    continue

                if (start >= f_start and start < f_end):
                    # this is the block
                    if (end <= f_end):
                        # and it fits!
                        if (type == "data"):
                            if (name in v_map):
                                if (v_map[name][0] != start or v_map[name][1] != length):
                                    # the name is already used and the declarations are different!
                                    AsmError_NO_RET(123, "Data variable %s declared twice and differently!" % (name))
                            else:
                                v_map[name] = (start, length)

                        if (start == f_start):
                            if (end == f_end):
                                # just remove this entry from the free list
                                pass
                            else:
                                # remove the front end of the free block
                                fixed_v_free.append((end, f_length - length, f_end))

                        elif (end == f_end):
                            # remove the back end of the free block
                            fixed_v_free.append((f_start, f_length - length, start))
                        else:
                            # in the middle, create two smaller free blocks
                            fixed_v_free.append((f_start, start - f_start, start))
                            fixed_v_free.append((end, f_end - end, f_end))

                        # found the data, copy the rest to the end
                        copy_to_end = True

                    else:
                        if (type == "data"):
                            io.Out.ErrorRaw("Fixed data variable %s at %d didn't fit!" % (name, start))
                            io.Out.Error(io.TS.ASM_MEM_OVERFLOW,
                                         "file::: Overflowed {0} memory", "fixed")
                            raise program.AssemblerError
                        else:
                            io.Out.ErrorRaw("No room for Reserved data space at %d" % (start))
                            io.Out.Error(io.TS.ASM_MEM_OVERFLOW,
                                         "file::: Overflowed {0} memory", "rsvd")
                            raise program.AssemblerError

        # Now try to fit in the floating variables. Use a best-fit strategy where the smallest
        # hole is used for each request. Also the block sizes are tried largest to smallest
        floats = [(x[1], x[3]) for x in variables if x[0] == "data" if x[2] < 0]
        floats.sort(key=lambda x: x[1], reverse=True)
        v_free = fixed_v_free

        for name, length in floats:

            # find the best fit!
            i = 0
            best_index = -1
            for i in range(len(v_free)):
                f_length = v_free[i][1]
                if (f_length >= length):
                    if (f_length == length):
                        # perfect fit!
                        best_index = i
                        break

                    elif (best_index == -1):
                        best_index = i
                    else:
                        if (f_length < v_free[best_index][1]):
                            best_index = i

            # best_index == -1 if nothing fit
            if (best_index == -1):
                AsmError_NO_RET(124, "Float data variable %s (len:%d) didn't fit!" % (name, length))

            # Add to the map and adjust free spaces
            f_start, f_length, f_end = v_free[best_index]
            if (name in v_map):
                # the name is already used!
                AsmError_NO_RET(125, "Data variable %s declared twice!" % (name))
            else:
                v_map[name] = (f_start, length)

            if (length == f_length):
                # just remove this entry from the free list
                del v_free[best_index]

            else:
                # put it at the start
                v_free[best_index] = (f_start + length, f_length - length, f_end)

            # print("v_free", v_free)
            # print("v_map", v_map)

        # Write the max index for this space
        max = 0
        for n in v_map:
            maybe_max = v_map[n][0] + v_map[n][1]
            if (maybe_max > max):
                max = maybe_max

        self.name_space_max[space] = max

        return True

    def calc_cumulative_lengths(self, c_lengths):
        # i = 0
        # calculate cumulative lengths
        cumulative_length = 0
        for t in self.token_stream.token_stream:
            c_lengths.append(cumulative_length)
            cumulative_length += t.get_byte_len()
        c_lengths.append(cumulative_length)
        # print(c_lengths)

    def fixup_jumps(self):
        # fixup the jumps
        io.Out.SetErrorRawContext(2, "Fixing up jumps")
        # print(self.token_stream.labels)

        # First get a cumulative byte length for each index
        c_lengths = []
        self.calc_cumulative_lengths(c_lengths)

        # Verify that the labels exist
        for t in self.token_stream.token_stream:
            if (t.has_jump_label()):
                index, name, big = t.get_jump_label()
                if (name not in self.token_stream.labels):
                    AsmError_NO_RET(126, "Reference to an unknown label:%s" % (name))

        # do multiple passes until all jumps can be satisfied (start with byte)
        while (1):
            c_lengths = []
            self.calc_cumulative_lengths(c_lengths)

            #
            i = 0
            while (i < len(self.token_stream.token_stream)):
                t = self.token_stream.token_stream[i]
                if (t.has_jump_label()):
                    index, name, big = t.get_jump_label()
                    my_address = c_lengths[i + 1]  # The PC is pointing to start of next token
                    target_address = c_lengths[self.token_stream.labels[name]]
                    offset = target_address - my_address

                    # does it fit?
                    if (not big):
                        if ((offset > MAX_SBYTE) or (offset < MIN_SBYTE)):
                            # must become big now - will have to re-compute everyone
                            t.fixup_jump(True, offset)
                            break
                        else:
                            # small is OK
                            t.fixup_jump(False, offset)
                    else:
                        # keep it big as the size never gets smaller
                        t.fixup_jump(True, offset)
                i += 1

            if (i >= len(self.token_stream.token_stream)):
                # no more fixups needed
                break

        return True

    def get_max_location(self):
        keys = self.token_stream.devices.keys()
        if (keys):
            maxl = max(keys)
        else:
            maxl = -1
        return maxl

    def get_loc_type_and_size(self, loc):
        if (loc in self.token_stream.devices):
            return self.token_stream.devices[loc]
        else:
            return (0, 0)

    def create_header(self):
        # print(self.token_stream.download_type)
        io.Out.SetErrorRawContext(2, "Creating download header")
        if (not self.token_stream.version):
            AsmError_NO_RET(127, "Version wasn't set")

        else:
            if (self.token_stream.download_type[0] == "firmware"):
                if ((self.token_stream.version[0] != 0xe) and
                    (self.token_stream.version[0] != 0x2)):
                    AsmError_NO_RET(128, "This assembler only handles firmware " +
                                    "major versions 0xe or 0x2 (not 0x%x)" %
                                    (self.token_stream.version[0]))
            else:
                if (self.token_stream.version[0] != 0x6):
                    AsmError_NO_RET(129, "This assembler only handles token " +
                                    "major versions 0x6 (not 0x%x)" % (self.token_stream.version[0]))

        header_list = []
        added_bytes = 0
        if (self.token_stream.download_type[0] == "firmware"):
            # header is just size and crc
            bytes = []
            for t in self.token_stream.token_stream:
                bytes.extend(t.get_token_bits())

            # skip bad crc lengths
            if (is_bad_length_for_crc(len(bytes))):
                print("Warning - skipping bad CRC length at {} bytes.".format(len(bytes)))
                added_bytes = 1
                bytes.extend([0xff])

            header_list.extend([0, 0, 0, 0])
            header_list[0], header_list[1] = word_to_bytes(len(bytes))
            crc = calculate_crc(bytes)
            header_list[2], header_list[3] = word_to_bytes(crc)
            return ("firmware", self.token_stream.version, header_list, added_bytes)

        else:
            bytes = []
            for t in self.token_stream.token_stream:
                bytes.extend(t.get_token_bits())


            # # TEST CODE - get to a bad crc length
            # print("Token bytes:", len(bytes))
            # if (len(bytes) < 760):
            #     added_bytes = 760-len(bytes)
            #     print("Added", added_bytes, "bytes")
            #     bytes.extend([0xff] * added_bytes)
            #     print("Bytes now:", len(bytes))

            # data_bytes(2), data_crc(2), 8-bit vars, 16-bit vars, program_offset(2)
            header_list.extend([0, 0, 0, 0, 0, 0, 0, 0])
            event_list = []
            main_offset = 0

            # put in the name_space maxes
            header_list[4] = self.name_space_max[0]
            header_list[5] = self.name_space_max[1]

            # need locations for event and program offsets
            c_lengths = []
            self.calc_cumulative_lengths(c_lengths)

            # build the event list but first with offsets from start of code tokens
            for i in range(len(self.token_stream.section_breaks)):
                stype, start_token, stop_token = self.token_stream.section_breaks[i]
                if (stype == "main"):
                    main_offset = c_lengths[start_token]
                else:
                    modreg, mask, value = self.token_stream.section_args[i]
                    event_list.append((c_lengths[start_token], modreg, mask, value))

            final_header_bytes = len(header_list) + len(event_list) * 5 + 2

            # fixup main offset
            header_list[6], header_list[7] = word_to_bytes(main_offset + final_header_bytes)

            # append the event list to the current header
            for (offset, modreg, mask, value) in event_list:
                work = [0, 0, modreg, mask, value]
                work[0], work[1] = word_to_bytes(offset + final_header_bytes)
                header_list.extend(work)

            # mark end of events
            header_list.extend([0, 0])

            # finally update the length and crc
            new_bytes = header_list[4:] + bytes

            # skip bad crc lengths
            if (is_bad_length_for_crc(len(new_bytes))):
                print("Warning - skipping bad CRC length at {} bytes.".format(len(new_bytes)))
                added_bytes += 1
                new_bytes.extend([0xff])

            header_list[0], header_list[1] = word_to_bytes(len(new_bytes))
            crc = calculate_crc(new_bytes)
            header_list[2], header_list[3] = word_to_bytes(crc)

            return ("program", self.token_stream.version, header_list, added_bytes)

    def dump_extras(self):
        print("Section breaks:", self.token_stream.section_breaks)
        print("Jump labels:", self.token_stream.labels)


class Token(object):
    def __init__(self, type, err_reporter=None, src=None):
        self.valid = True
        self.token_info = []
        self.var_info = []
        self.jump_label = None
        self.type = type
        self.cached_bits = []
        self.binary_file = None

        if (src and src.endswith('\n')):
            self.source_line = src[:-1]
        else:
            self.source_line = src

    def mark_invalid(self):
        self.valid = False

    def invalidate_cache(self):
        self.cached_bits = []

    def get_type(self):
        return self.type

    def add_byte(self, index, value):
        # print("DEBUG - add_byte() - index:%s, value:%s" % (index, value))
        if (value < MIN_BYTE or value > MAX_BYTE):
            self.mark_invalid()
            AsmError_NO_RET(130, "Out of range for a byte: %d" % (value))
        else:
            self.token_info.append((index, 0, 0xff, value))

        self.invalidate_cache()

    def find_index(self, index):
        found = -1
        for i in range(len(self.token_info)):
            if (self.token_info[i][0] == index):
                found = i
                break
        if (found == -1):
            self.mark_invalid()
            AsmError_NO_RET(131, "Variable index: %d invalid" % (index))
        return found

    def fixup_crc(self, size, index, value):
        if (size == 8):
            if (value < 0 or value > MAX_BYTE):
                self.mark_invalid()
                AsmError_NO_RET(132, "Out of range for byte: %d" % (value))
            else:
                del self.token_info[self.find_index(index)]
                self.token_info.append((index, 0, 0xff, value))

        else:
            if (value < 0 or value > MAX_UWORD):
                self.mark_invalid()
                AsmError_NO_RET(133, "Out of range for an unsigned word: %d" % (value))
            else:
                del self.token_info[self.find_index(index)]
                del self.token_info[self.find_index(index + 1)]
                self.token_info.append((index, 0, 0xff, (value >> 8) & 255))
                self.token_info.append((index + 1, 0, 0xff, value & 255))

        self.invalidate_cache()

    def fixup_var_byte(self, index, value):
        i = self.find_index(index)
        new_number = self.token_info[i][3] + value
        if (new_number < MIN_BYTE or new_number > MAX_BYTE):
            self.mark_invalid()
            AsmError_NO_RET(134, "Out of range for a byte: %d" % (new_number))

        self.token_info[i] = (index, 0, 0xff, new_number)
        self.invalidate_cache()

    def fixup_jump(self, big, offset):
        j_index, j_name, j_big = self.jump_label
        if (big != j_big):
            if (not big):
                self.mark_invalid()
                AsmError_NO_RET(135, "Impossible - the jump size got SMALLER")

            # make the small into big
            del self.token_info[self.find_index(j_index)]
            self.add_bits(0, 4, 1, 1)
            self.add_word(j_index, offset)
            self.jump_label = (j_index, j_name, big)

        elif (big):
            # update the big one
            del self.token_info[self.find_index(j_index)]
            del self.token_info[self.find_index(j_index + 1)]
            self.add_word(j_index, offset)
        else:
            # update the small one
            del self.token_info[self.find_index(j_index)]
            if (offset < 0):
                # convert to a signed offset
                offset += 256
            self.add_byte(j_index, offset)
            self.token_info.append((j_index, 0, 0xff, offset))

        self.invalidate_cache()

    def add_word(self, index, value):
        if (value < MIN_WORD or value > MAX_WORD):
            self.mark_invalid()
            AsmError_NO_RET(136, "Out of range for a word: %d" % (value))
        else:
            self.token_info.append((index, 0, 0xff, (value >> 8) & 255))
            self.token_info.append((index + 1, 0, 0xff, value & 255))

        self.invalidate_cache()

    def add_uword(self, index, value):
        if (value < 0 or value > MAX_UWORD):
            self.mark_invalid()
            AsmError_NO_RET(137, "Out of range for an unsigned word: %d" % (value))
        else:
            self.token_info.append((index, 0, 0xff, (value >> 8) & 255))
            self.token_info.append((index + 1, 0, 0xff, value & 255))

        self.invalidate_cache()

    def add_bits(self, index, shift, mask, value):
        self.token_info.append((index, shift, mask, value))
        self.invalidate_cache()

    # Adds a name reference to the token[index]. The address of the name is added to the
    # value of the byte at that index.
    def add_vname(self, index, space, name):
        self.var_info.append((index, space, name))
        self.invalidate_cache()

    def clear_vnames(self):
        self.var_info = []

    def set_jump_label(self, index, name, big=False):
        # start off with a small jump
        self.jump_label = (index, name, big)
        self.invalidate_cache()

    def get_jump_label(self):
        return self.jump_label

    def has_jump_label(self):
        return self.jump_label is not None

    def clear_jump_label(self):
        self.jump_label = None

    def finish(self, token_stream, explicit_placement=-1):
        # add the token to the token stream for post-processing
        if (self.valid):
            token_stream.add_token(self, explicit_placement)
        else:
            io.Out.DebugRaw("Dropping invalid token")

    def get_byte_len(self):
        if (len(self.cached_bits) == 0):
            self.get_token_bits()

        return len(self.cached_bits)

    def get_token_bits(self):
        if (len(self.cached_bits) == 0):
            if (self.binary_file):
                fh = file(self.binary_file, 'rb')
                tmp_ascii = fh.read()
                for t in tmp_ascii:
                    self.cached_bits.append(ord(t))

                fh.close()
            else:
                length = 1
                self.cached_bits = [0]
                for index, shift, mask, value in self.token_info:
                    while (index + 1 > length):
                        self.cached_bits.append(0)
                        length += 1

                    work = self.cached_bits[index]
                    work = work & ~(mask << shift)
                    work = work | ((value & mask) << shift)
                    self.cached_bits[index] = work

        return self.cached_bits

    def add_binary_file(self, f_name):
        # save the file_name and bring it out when we get length or bits
        self.binary_file = f_name

    def print_token(self):
        length = self.get_byte_len()
        bits = self.get_token_bits()

        if (self.binary_file):
            print("Inserted %d binary bytes from %s:\n   [" % (length, self.binary_file), end='')

        for i in range(length):
            print("%02x " % (bits[i]), end='')
            if (((i + 1) % 20) == 0):
                print("\n    ")

        if (self.binary_file):
            print("]")

        elif (self.var_info):
            print("(var_refs:", end='')
            info = ""
            for i, s, n in self.var_info:
                if (info):
                    info += ", "
                info += "%s/%d/%s" % (n, i, space_names[s])
            print("%s)" % (info))

        elif (self.jump_label):
            print("(jump_ref to %s, big? %d)" % (self.jump_label[1], self.jump_label[2]))

        else:
            print()
