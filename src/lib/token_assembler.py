#!/usr/bin/env python


# * **************************************************************** **
#
# File: token_tool.py
# Desc: Assembler and dissassembler of tokens
# Note:
#
# Author: Brian Danilko, Likeable Software (brian@likeablesoftware.com)
#
# Copyright 2006, 2014, 2016, 2107 Microbric Pty Ltd.
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

from . import io

import os
import os.path

from . import tokens
from . import hl_parser
from . import program


ROW_LENGTH = 14
COL_LENGTH = 6

# File scope objects
token_stream = None
err = None


def reset_tokens():
    global token_stream
    token_stream = None


def AsmError_NO_RET(number, internalError=None, line=0):
    if (internalError):
        io.Out.ErrorRaw(internalError)

    io.Out.Error(io.TS.ASM_INTERNAL_ERROR, "file::: Assembler internal error {0}", number)
    raise program.AssemblerError


def assem_file(f_name, called_from=[], pass_err=None):
    io.Out.DebugRaw("Assem_file:%s" % (f_name))

    io.Out.SetErrorRawContext(2, "reading token file: %s" % (f_name))

    # open file
    if (not os.path.isfile(f_name) or not os.access(f_name, os.R_OK)):
        print("ERROR - file %s doesn't exist or isn't readable" % (f_name))
        if (called_from):
            print("  Insert history: ", end='')
            output = ""
            for f, l in called_from:
                if (output):
                    output += ", "
                output += "%s:%d" % (f, l)
            print(output)
        return False

    fh = file(f_name, 'rU')

    # get each line but insert a file if find 'INSERT TOKENS'
    line_num = 1
    for line in fh:
        # if 'INPUT TOKENS fname' push existing file
        insert_check = line.split()
        if ((len(insert_check) >= 3) and
            (insert_check[0] == 'INSERT') and
            (insert_check[1].lower() == 'tokens')):
            called_from.append((f_name, line_num))
            assem_file(insert_check[2], called_from)
            called_from.pop()
        else:
            assem_line(line)

        line_num += 1

    return True


def assem_lines(lines):
    io.Out.DebugRaw("Assem_lines - lines:" + str(len(lines)))

    io.Out.SetErrorRawContext(2, "Assem_lines - lines:" + str(len(lines)))

    # get each line but insert a file if find 'INSERT TOKENS'
    line_num = 1
    for line in lines:
        assem_line(line)
        line_num += 1

    return True


def assem_line(line):
    """First scan of the operator to see which function to call"""
    io.Out.SetErrorRawContext(3, line)

    words = hl_parser.chop_line(line)

    if (not words):
        return

    t1 = words[0]

    io.Out.SetErrorRawContext(4, hl_parser.format_word_list(words))

    if (t1.type() == "label"):
        assem_spec_label(t1, words[1:], line=line)

    elif (t1.type() == "op"):
        op = t1.val()
        words = words[1:]

        if (op.endswith('b') or op.endswith('w')):
            size = 0
            if (op.endswith('w')):
                size = 1

            op = op[:-1]
            if (op == "mov"):
                assem_move(size, words, "", line=line)
            elif (op == "mol"):
                assem_move(size, words, "mol", line=line)
            elif (op == "dat"):
                assem_data(size, words, line=line)
            elif (op in ["not", "dec", "inc"]):
                assem_uni_math(op, size, words, line=line)
            elif (op in ["add", "sub", "mul", "cmp"]):
                assem_basic_math(op, size, words, line=line)
            elif (op in ["shl", "shr", "div", "mod"]):
                assem_other_math(op, size, words, line=line)
            elif (op in ["push", "pop", "stra", "stwa"]):
                assem_stack(op, size, words, line=line)
            elif (op in ["or", "and", "xor"]):
                assem_other_math(op, size, words, line=line)
            elif (op == "out"):
                assem_debug_output(op, size, words, line=line)
            else:
                AsmError_NO_RET(1, "Unknown operator:%s" % (op))
        else:
            if (op == "mova"):
                assem_move(0, words, "lcd", line=line)
            elif (op == "movtime"):
                assem_move(1, words, "time", line=line)
            elif (op in ["conv", "convl", "convm", "cmptime"]):
                # conv 8->16, conv 16->8 lsb, conv 16->8 msb, cmp time
                assem_conv(op, words, line=line)
            elif (op in ["disable", "enable", "error"]):
                assem_event(op, words, line=line)
            elif (op in ["ret", "dbnz", "dsnz"]):
                assem_jump(op, "", words, line=line)
            elif (op in ["bra", "bre", "brne", "brgr", "brge", "brl", "brle", "brz", "brnz"]):
                assem_jump("branch", op[2:], words, line=line)
            elif (op in ["suba", "sube", "subne", "subgr", "subge", "subl", "suble", "subz", "subnz"]):
                assem_jump("sub", op[3:], words, line=line)
            elif (op in ["stop", "bitset", "bitclr"]):
                assem_misc(op, words, line=line)
            elif (op in ["or", "and", "xor"]):
                # if there is no size after the op (which is now depricated) then treat it like a 'b'
                assem_other_math(op, 0, words, line=line)
            elif (op in ["stinc", "stdec", "push"]):
                assem_stack_math(op, words, line=line)

            elif (op in ["DATB", "DATW"]):
                assem_spec_data(op[3], words, line=line)
            elif (op == "DATA"):
                assem_spec_data_lcd(op[3], words, line=line)
            elif (op in ["BINB"]):
                assem_spec_binary(op[3], words, line=line)
            elif (len(op) == 7 and op[:6] == "RESERV"):
                assem_spec_reserve(op[6], words, line=line)
            elif (op in ["BEGIN", "END"]):
                assem_spec_begin_end(op, words, line=line)
            elif (op == "VERSION"):
                assem_spec_version(words, line=line)
            elif (op == "LIMITS"):
                assem_spec_limits(words, line=line)
            elif (op == "DEVICE"):
                assem_spec_device(words, line=line)
            elif (op == "INSERT"):
                assem_spec_insert(words, line=line)
#           elif (op == "COMMS"):
#               assem_spec_comms(words, line=line)
            elif (op == "FINISH"):
                assem_spec_finish(words, line=line)
            else:
                AsmError_NO_RET(2, "Unknown operator:%s" % (op))


def assem_move(size, words, special, line):
    io.Out.DebugRaw("Move size:%d, words:%s" % (size, hl_parser.format_word_list(words)))
    if (len(words) != 2):
        AsmError_NO_RET(3, "Move needs 2 arguments")

    # check the special case of move from the accumulator
    elif ((special == "mol") or
          ((special == "") and (words[0].type() == "modreg") and (words[0].val() == 0xf0))):
        assem_move_from_acc(size, words, special, line)
    else:
        assem_move_not_from_acc(size, words, special, line)


def assem_move_from_acc(size, words, special, line):

    token = tokens.Token("misc", err, line)

    if (special == "mol"):
        if (size != 0):
            AsmError_NO_RET(4, "mol only has a byte variant (not word)")
        elif ((words[0].type() != "var") or
              (words[1].type() != "modreg")):
            AsmError_NO_RET(5, "Invalid arguments for molb")
        else:
            token.add_byte(0, 0x34)                     # op code
            token.add_byte(1, 0)                        # 16-bit var offset
            token.add_vname(1, 1, words[0].val())       # second 1 means 16-bit
            token.add_byte(2, words[1].val())           # modreg code

    else:
        token.add_bits(0, 4, 0xf, 0x3)  # top 4 bits = 0011

        # destination
        if (words[1].type() == "modreg"):
            if (size == 0):
                token.add_bits(0, 0, 0xf, 0x2)
            else:
                token.add_bits(0, 0, 0xf, 0x3)
            token.add_byte(1, words[1].val())

        elif (words[1].type() in ["var", "arg"]):
            if (size == 0):
                token.add_bits(0, 0, 0xf, 0x0)
            else:
                token.add_bits(0, 0, 0xf, 0x1)

            if (words[1].type() == "arg"):
                token.add_byte(1, words[1].num())
            else:
                token.add_byte(1, 0)
                token.add_vname(1, size, words[1].val())

        else:
            AsmError_NO_RET(6, "Destination must be a mod/reg or variable")

    token.finish(token_stream)


def assem_move_not_from_acc(size, words, special, line):

    token = tokens.Token("move", err, line)
    token.add_bits(0, 6, 3, 1)
    sdindex = 1

    # source
    if (words[0].type() == "const"):
        if (not special and words[0].val() >= 0 and words[0].val() <= 3):
            token.add_bits(0, 3, 0x3, words[0].val())
            token.add_bits(0, 2, 0x1, size)
        else:
            if (size == 0):
                token.add_bits(0, 2, 0xf, 0xa)
                token.add_byte(sdindex, words[0].val())
                sdindex += 1
            else:
                if (not special):
                    token.add_bits(0, 2, 0xf, 0xb)
                elif (special == "time"):
                    token.add_bits(0, 2, 0xf, 0xf)
                else:
                    AsmError_NO_RET(7, "Source for lcd moves must be byte sized")

                token.add_word(sdindex, words[0].val())
                sdindex += 2
    elif (words[0].type() == "modreg"):
        if (size == 0):
            token.add_bits(0, 2, 0xf, 0x8)
        else:
            token.add_bits(0, 2, 0xf, 0x9)
        token.add_byte(sdindex, words[0].val())
        sdindex += 1

    elif (words[0].type() in ["var", "arg"]):
        if (size == 0):
            token.add_bits(0, 2, 0xf, 0xc)
        else:
            if (not special):
                token.add_bits(0, 2, 0xf, 0xd)
            elif (special == "time"):
                token.add_bits(0, 2, 0xf, 0xe)
            else:
                AsmError_NO_RET(8, "Source for lcd moves must be byte sized")

        if (words[0].type() == "arg"):
            token.add_byte(sdindex, words[0].num())
        else:
            token.add_byte(sdindex, 0)
            token.add_vname(sdindex, size, words[0].val())
        sdindex += 1

    # if this is a time chkpt then the destination must be in 8bit space
    if (special == "time"):
        size = 0

    # destination
    if (words[1].type() == "modreg"):
        if (special):
            AsmError_NO_RET(9, "Destination for lcd and time moves can NOT be mod/reg")
        # ((words[0].type() == "modreg") and (words[0].val() == 0xf0))):

        # special processing for move to ACC
        if (words[1].val() == 0xf0) :
            token.add_bits(0, 0, 0x3, 0x3)
        else:
            token.add_bits(0, 0, 0x3, 0x0)
            token.add_byte(sdindex, words[1].val())
            sdindex += 1

    elif (words[1].type() in ["var", "arg"]):
        if (size == 0):
            if (special != "lcd"):
                token.add_bits(0, 0, 0x3, 0x1)
            else:
                token.add_bits(0, 0, 0x3, 0x3)
        else:
            if (special):
                AsmError_NO_RET(10, "Desination for lcd and time moves can not be in word variables")

            token.add_bits(0, 0, 0x3, 0x2)

        if (words[1].type() == "arg"):
            token.add_byte(sdindex, words[1].num())
        else:
            token.add_byte(sdindex, 0)
            if (special == "lcd"):
                token.add_vname(sdindex, 2, words[1].val())
            else:
                token.add_vname(sdindex, size, words[1].val())
        sdindex += 1

    io.Out.DebugDumpObjectRaw(token, "move")
    token.finish(token_stream)


def assem_data(size, words, line):
    io.Out.DebugRaw("data size:%s words:%s" % (size, hl_parser.format_word_list(words)))

    if (len(words) < 3):
        AsmError_NO_RET(11, "dat[bw] needs at least 3 arguments: var, len and value1")

    if (words[0].type() not in ["arg", "var"]):
        AsmError_NO_RET(12, "dat[bw] first argument must be a variable or location")
    elif (words[0].type() == "arg"):
        start = words[0].anum()
        name = '*'
    else:
        start = 0
        name = words[0].val()

    length = 1
    if (words[1].val() == '*'):
        length = -1
    else:
        length = words[1].anum()

    words = words[2:]
    values = []
    # now words are the values
    for w in words:
        if (w.type() not in ["arg", "string"]):
            AsmError_NO_RET(13, "Word should have been an argument or string!")
        else:
            if (w.type() == "string"):
                for c in w.val():
                    values.append(ord(c))
            else:
                values.append(w.anum())

    # Do space sanity checks
    if (length > 0 and len(values) > length):
        AsmError_NO_RET(14, "Data has length of %d but more values (%d) then length" % \
                                   (length, len(values)))

    # zero up to the named length
    if (length > len(values)):
        while (len(values) < length):
            values.append(0)

    # Make the tokens
    if (len(values)):

        tokens_to_create = (len(values) + 14) / 15
        last = len(values) % 15

        # print tokens_to_create, last
        val_index = 0
        for i in range(tokens_to_create):
            token = tokens.Token("data", err, line)
            token.add_bits(0, 4, 3, size + 1)
            if ((i < (tokens_to_create - 1)) or (last == 0)):
                val_count = 15
            else:
                val_count = last

            token.add_bits(0, 0, 0xf, val_count)

            # add the location
            if (name != '*'):
                token.add_byte(1, i * 15)
                token.add_vname(1, size, name)
            else:
                token.add_byte(1, start + (i * 15))

            token_index = 2
            # add the data
            if (size == 0):
                for j in range(val_count):
                    # print(val_index)
                    token.add_byte(token_index, values[val_index])
                    token_index += 1
                    val_index += 1
            else:
                for j in range(val_count):
                    # print(val_index)
                    token.add_word(token_index, values[val_index])
                    token_index += 2
                    val_index += 1

            token.finish(token_stream)


uni_assem_map = {"not": 0, "inc": 1, "dec": 2}


def assem_uni_math(op, size, words, line):
    io.Out.DebugRaw("Mathu %s size:%d, words:%s" % (op, size, hl_parser.format_word_list(words)))
    if (len(words) > 1):
        AsmError_NO_RET(15, "Unary Math has at most one argument")

    token = tokens.Token("uni-math", err, line)
    token.add_bits(0, 6, 3, 2)
    token.add_bits(0, 3, 1, size)
    token.add_bits(0, 0, 3, uni_assem_map[op])

    # if no argument or %_cpu:acc, then this is using the ACC
    if (not words or
        (words[0].type() == "modreg" and words[0].val() == 0xf0)):
        token.add_bits(0, 2, 1, 0)
        token.finish(token_stream)
    elif (words[0].type() in ["var", "arg"]):
        token.add_bits(0, 2, 1, 1)
        if (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            token.add_byte(1, 0)
            token.add_vname(1, size, words[0].val())
        token.finish(token_stream)
    else:
        AsmError_NO_RET(16, "Unary Math - invalid argument type")

basic_assem_map = {"add": 0, "sub": 1, "mul": 2, "cmp": 3}


def assem_basic_math(op, size, words, line):
    io.Out.DebugRaw("Mathb %s size:%s, words:%s" % (op, size, hl_parser.format_word_list(words)))
    if (len(words) != 1):
        AsmError_NO_RET(17, "Basic Math needs one argument")

    token = tokens.Token("basic-math", err, line)
    token.add_bits(0, 6, 3, 2)
    token.add_bits(0, 4, 3, 1)
    token.add_bits(0, 3, 1, size)
    token.add_bits(0, 0, 3, basic_assem_map[op])

    if (words[0].type() in ["var", "arg"]):
        # math with a variable
        token.add_bits(0, 2, 1, 0)
        if (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            token.add_byte(1, 0)
            token.add_vname(1, size, words[0].val())
        token.finish(token_stream)
    elif (words[0].type() == "const"):
        token.add_bits(0, 2, 1, 1)
        if (size == 0):
            token.add_byte(1, words[0].val())
        else:
            token.add_word(1, words[0].val())

        token.finish(token_stream)
    else:
        AsmError_NO_RET(18, "Basic Math - invalid argument type")

other1_assem_map = {"shl": 0, "shr": 1, "div": 2, "mod": 3}
other2_assem_map = {"or": 0, "and": 1, "xor": 2}


def assem_other_math(op, size, words, line):
    io.Out.DebugRaw("Matho %s size:%d, words:%s" % (op, size, hl_parser.format_word_list(words)))

    if (len(words) != 1):
        AsmError_NO_RET(19, "Logic Math needs one arguement")

    # if ((op in ("shl", "shr")) and (size == 1) and
    #     (words[0].type() == "const")):
    #     AsmError_NO_RET(20, "Shifts by constants only take 8-bit constants")

    token = tokens.Token("log-math", err, line)
    token.add_bits(0, 6, 3, 2)
    token.add_bits(0, 3, 1, size)

    if (op in other1_assem_map.keys()):
        token.add_bits(0, 4, 3, 2)
        token.add_bits(0, 0, 3, other1_assem_map[op])
    else:
        token.add_bits(0, 4, 3, 3)
        token.add_bits(0, 0, 3, other2_assem_map[op])

    if (words[0].type() in ["var", "arg"]):
        # math with a variable
        token.add_bits(0, 2, 1, 0)
        if (words[0].type() == "arg"):
            token.add_byte(1, words[0].val())
        else:
            token.add_byte(1, 0)
            token.add_vname(1, size, words[0].val())
        token.finish(token_stream)
    elif (words[0].type() == "const"):
        token.add_bits(0, 2, 1, 1)
        if ((size == 0) or (op in ("shl", "shr"))):
            # shl/shr only take one byte since it's value is at most 0-15
            token.add_byte(1, words[0].val())
        else:
            token.add_word(1, words[0].val())

        token.finish(token_stream)
    else:
        AsmError_NO_RET(21, "Logic Math - invalid argument type")


def assem_conv(op, words, line):
    io.Out.DebugRaw("Conv %s words:%s" % (op, hl_parser.format_word_list(words)))

    token = tokens.Token("conv", err, line)

    if (op == "cmptime"):
        if (len(words) != 1):
            AsmError_NO_RET(22, "Cmptime needs one arguement")
        else:
            token.add_bits(0, 6, 3, 2)
            token.add_bits(0, 3, 1, 0)
            token.add_bits(0, 0, 7, 7)
            if (words[0].type() == "arg"):
                token.add_byte(1, words[0].num())
            elif (words[0].type() == "var"):
                token.add_byte(1, 0)
                token.add_vname(1, 0, words[0].val())
            else:
                AsmError_NO_RET(23, "Cmptime takes a variable as it's argument")
    else:
        if (len(words) != 0):
            AsmError_NO_RET(24, "Conversions don't that arguments")
        else:
            token.add_bits(0, 6, 3, 2)
            token.add_bits(0, 0, 7, 3)
            if (op == "convm"):
                token.add_bits(0, 3, 1, 1)

    token.finish(token_stream)


def assem_stack(op, size, words, line):
    io.Out.DebugRaw("Stack %s size:%d, words:%s" % (op, size, hl_parser.format_word_list(words)))
    # op in ['push', 'pop', 'stra', 'stwa'], size in [0, 1], one word
    if (len(words) != 1):
        AsmError_NO_RET(25, "Stack ops need 1 argument")

    token = tokens.Token("stack", err, line)
    token.add_bits(0, 6, 3, 3)
    token.add_bits(0, 5, 1, 1)
    token.add_bits(0, 4, 1, size)

    if (op == "push"):
        if (words[0].type() == 'const'):
            if (size == 0):
                token.add_byte(1, words[0].val())
            else:
                token.add_word(1, words[0].val())
        elif (words[0].type() == 'modreg'):
            # don't do special ACC here, as the size [b,w] was used.
            token.add_bits(0, 0, 0xf, 2)
            token.add_byte(1, words[0].val())
        elif (words[0].type() in ["var", "arg"]):
            token.add_bits(0, 0, 0xf, 1)
            if (words[0].type() == "arg"):
                token.add_byte(1, words[0].num())
            else:
                token.add_byte(1, 0)
                token.add_vname(1, size, words[0].val())
        else:
            AsmError_NO_RET(26, "Push - invalid operand: %s" % (words[0].type()))

    elif (op == "pop"):
        if (words[0].type() == 'modreg'):
            if (words[0].val() == 0xf0):  # ACC
                token.add_bits(0, 0, 0xf, 0x4)
            else:
                token.add_bits(0, 0, 0xf, 6)
                token.add_byte(1, words[0].val())
        elif (words[0].type() in ["var", "arg"]):
            token.add_bits(0, 0, 0xf, 5)
            if (words[0].type() == "arg"):
                token.add_byte(1, words[0].num())
            else:
                token.add_byte(1, 0)
                token.add_vname(1, size, words[0].val())
        else:
            AsmError_NO_RET(27, "Pop - invalid operand: %s" % (words[0].type()))

    elif (op == "stra"):  # read from stack into acc
        token.add_bits(0, 0, 0xf, 9)
        if (words[0].type() == "const"):
            token.add_byte(1, words[0].val())
        elif (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            AsmError_NO_RET(28, "Stra - invalid operand: %s" % (words[0].type()))

    else:  # (op == "stwa"):  # write from acc into stack
        token.add_bits(0, 0, 0xf, 0xc)
        if (words[0].type() == "const"):
            token.add_byte(1, words[0].val())
        elif (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            AsmError_NO_RET(29, "Strw - invalid operand: %s" % (words[0].type()))

    token.finish(token_stream)


def assem_debug_output(op, size, words, line):
    io.Out.DebugRaw("Debug output %s size:%d, words:%s" % (op, size, hl_parser.format_word_list(words)))
    # op in ['out'], size in [0, 1], one word
    if (len(words) != 1):
        AsmError_NO_RET(30, "Debug output needs 1 argument")

    if (words[0].type() != "var"):
        AsmError_NO_RET(31, "Error - Debug output only handles variables - invalid operand: %s" % (words[0].type()))

    token = tokens.Token("output", err, line)
    token.add_bits(0, 6, 3, 3)
    token.add_bits(0, 5, 1, 1)
    token.add_bits(0, 4, 1, size)
    token.add_bits(0, 0, 0x0f, 0x0e)

    # this is a variable - checked above
    token.add_byte(1, 0)
    token.add_vname(1, size, words[0].val())

    token.finish(token_stream)


def assem_stack_math(op, words, line):
    io.Out.DebugRaw("Stack math %s words:%s" % (op, hl_parser.format_word_list(words)))
    # op in ['stinc', 'stdec', 'push'], one word
    if (len(words) != 1):
        AsmError_NO_RET(32, "Stack ops need 1 argument")

    token = tokens.Token("stack", err, line)
    token.add_bits(0, 4, 0xf, 0xe)    # top 3 bits set

    if (op == "push"):
        if (words[0].type() == 'modreg'):
            if (words[0].val() == 0xf0):  # ACC
                token.add_bits(0, 0, 0xf, 0x3)
            else:
                AsmError_NO_RET(33, "Push with no size - invalid operand: %s" % (words[0].type()))
        else:
            AsmError_NO_RET(34, "Push with no size - invalid operand: %s" % (words[0].type()))

    elif (op == "stinc"):
        token.add_bits(0, 0, 0xf, 0xa)
        if (words[0].type() == "const"):
            token.add_byte(1, words[0].val())
        elif (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            AsmError_NO_RET(35, "Stinc - invalid operand: %s" % (words[0].type()))
    else:  # stdec
        token.add_bits(0, 0, 0xf, 0xb)
        if (words[0].type() == "const"):
            token.add_byte(1, words[0].val())
        elif (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            AsmError_NO_RET(36, "Stdec - invalid operand: %s" % (words[0].type()))

    token.finish(token_stream)


def assem_event(op, words, line):
    io.Out.DebugRaw("Event %s words:%s" % (op, hl_parser.format_word_list(words)))

    token = tokens.Token("event", err, line)

    if (op == "error"):
        if (len(words) != 1):
            AsmError_NO_RET(37, "Error needs 1 argument")
        token.add_byte(0, 0xef)

        if (words[0].type() == "const"):
            token.add_byte(1, words[0].val())
        elif (words[0].type() == "arg"):
            token.add_byte(1, words[0].num())
        else:
            AsmError_NO_RET(38, "Error - invalid operand: %s" % (words[0].type()))

    else:
        # op is one of: enable, disable, no words
        if (len(words) != 0):
            AsmError_NO_RET(39, "Enable/disable don't take arguments")

        token.add_bits(0, 6, 3, 2)
        token.add_bits(0, 4, 3, 3)
        token.add_bits(0, 0, 3, 3)

        if (op == 'enable'):
            token.add_bits(0, 2, 1, 1)
        else:  # (op == 'disable')
            token.add_bits(0, 2, 1, 0)

    token.finish(token_stream)


jcond_assem_map = {'a': 0, 'e': 1, 'ne': 2, 'gr': 3, 'ge': 4, 'l': 5, 'le': 6, 'z': 1, 'nz': 2}


def assem_jump(op, cond, words, line):
    io.Out.DebugRaw("Jump %s cond:%s, words:%s" % (op, cond, hl_parser.format_word_list(words)))
    # ops is one of: branch, sub, ret, dbnz, dsnz
    # cond is one of: a, e, ne, g, l, le, lg or empty for ret, d?nz
    token = tokens.Token("jump", err, line)
    token.add_bits(0, 6, 3, 3)

    if (op == "ret"):
        if (len(words) != 0):
            AsmError_NO_RET(40, "Ret don't take an argument")
        else:
            token.add_bits(0, 0, 0x3f, 0x28)
    elif (len(words) != 1):
        AsmError_NO_RET(41, "Jumps need a target to jump to")
    else:
        if (op[:2] in ['su', 'ds']):
            # a call to a subroutine - push a frame
            token.add_bits(0, 3, 1, 1)
        else:
            token.add_bits(0, 3, 1, 0)

        if (not cond):
            # one of dbnz or dsnz
            token.add_bits(0, 0, 7, 7)
        else:
            token.add_bits(0, 0, 7, jcond_assem_map[cond])

        # now the target
        if (words[0].type() == "const"):
            offset = words[0].val()
            if (offset >= tokens.MIN_SBYTE and offset <= tokens.MAX_SBYTE):
                if (offset < 0):
                    # convert to a signed offset
                    offset += 256
                token.add_byte(1, offset)
            elif (offset >= tokens.MIN_WORD and offsec <= tokens.MAX_WORD):
                token.add_bits(0, 4, 1, 1)
                token.add_word(1, offset)

        elif (words[0].type() == "label"):
            if (words[0].val().startswith(':')):
                # globals are always long jumps
                token.add_bits(0, 4, 1, 1)
                token.set_jump_label(1, words[0].val(), True)
                token.add_word(1, 0)    # A placeholder
            else:
                token.set_jump_label(1, words[0].val())
                token.add_byte(1, 0)    # A placeholder

        else:
            AsmError_NO_RET(42, "Jumps need either a constant or a label as argument, not a: " + words[0].type())

    token.finish(token_stream)


def assem_misc(op, words, line):
    io.Out.DebugRaw("Misc op:%s words:%s" % (op, hl_parser.format_word_list(words)))
    if (op == "stop"):
        if (len(words) != 0):
            AsmError_NO_RET(43, "Stop doesn't take arguments")

        token = tokens.Token("misc", err, line)
        token.add_bits(0, 0, 0xff, 0xff)
        token.finish(token_stream)

    elif (op in ["bitset", "bitclr"]):
        if (len(words) != 2):
            AsmError_NO_RET(44, "Bitset/bitclr needs 2 arguments: bit and mod/reg")

        bit = words[0].anum()
        if (bit < 0 or bit > 7):
            AsmError_NO_RET(45, "Bitset/bitclr bit must be between 0 and 7 (not %d)" % (bit))

        modreg = words[1].amodreg()

        token = tokens.Token("misc", err, line)
        token.add_bits(0, 4, 0x0f, 0x00)
        if (op == "bitset"):
            token.add_bits(0, 3, 0x1, 0x1)
        else:
            token.add_bits(0, 3, 0x1, 0x0)

        token.add_bits(0, 0, 0x7, bit)
        token.add_byte(1, modreg)
        token.finish(token_stream)

    else:
        AsmError_NO_RET(46, "Unknown misc operator: " + op)

# ********* SPECIALS (in caps) ********************************************


def assem_spec_label(label, words, line):
    io.Out.DebugRaw("Spec_label:%s" % (label.val()))
    if (len(words) != 0):
        AsmError_NO_RET(47, "A label doesn't take any arguments")

    token_stream.add_label(label.val())


def assem_spec_data(which, words, line):
    io.Out.DebugRaw("Spec_data which:%s words:%s" % (which, hl_parser.format_word_list(words)))

    if (len(words) < 2):
        AsmError_NO_RET(48, "DAT[BW] needs at least 2 arguments: name, start")

    space = tokens.space_types[which]

    if (words[0].val() == '*'):
        name = '*'
    else:
        name = words[0].astr()

    if (words[1].val() == '*'):
        start = -1
        if (name == '*'):
            AsmError_NO_RET(49, "DAT[BW] both name and loc can't both be '*'")
    else:
        start = words[1].anum()

    words = words[2:]

    length = 1
    if (len(words) >= 1):
        if (words[0].val() == '*'):
            length = -1
        else:
            length = words[0].anum()
        words = words[1:]

    values = []
    # now words are the values
    for w in words:
        if (w.type() not in ["arg", "string"]):
            AsmError_NO_RET(50, "Word should have been an argument or string!")
        else:
            if (w.type() == "string"):
                for c in w.val():
                    values.append(ord(c))
            else:
                values.append(w.anum())

    # Do space sanity checks
    if (length > 0 and len(values) > length):
        AsmError_NO_RET(51, "Data has length of %d but more values (%d) then length" %
                         (length, len(values)))

    if (length > 0):
        real_length = length
    else:
        real_length = len(values)

    if (start > 0):
        test = start + real_length
    else:
        # don't know where it will start so can't know if it will fit yet
        test = real_length

    if (test <= 0):
        AsmError_NO_RET(52, "There is no data for the space")
    elif (test >= 255):
        io.Out.Error(io.TS.ASM_MEM_OVERFLOW,
                     "file::: Overflowed {0} memory", which)
        raise program.AssemblerError

    # special case where we have an UNNAMED area with a length - zero beyond the values up to length
    if ((name == '*') and (length > 0) and (length > len(values))):
        while (len(values) < length):
            values.append(0)
        # print(values)

    # Make the tokens
    if (len(values)):

        tokens_to_create = (len(values) + 14) // 15
        last = len(values) % 15

        # print(tokens_to_create, last)
        val_index = 0
        for i in range(tokens_to_create):
            token = tokens.Token("data", err, line)
            token.add_bits(0, 4, 3, space + 1)
            if ((i < (tokens_to_create - 1)) or (last == 0)):
                val_count = 15
            else:
                val_count = last

            token.add_bits(0, 0, 0xf, val_count)

            # add the location
            if (name != '*'):
                token.add_byte(1, i * 15)
                token.add_vname(1, space, name)
            else:
                token.add_byte(1, start + (i * 15))

            token_index = 2
            # add the data
            if (which == "B"):
                for j in range(val_count):
                    # print(val_index)
                    token.add_byte(token_index, values[val_index])
                    token_index += 1
                    val_index += 1
            else:
                for j in range(val_count):
                    # print(val_index)
                    if (values[val_index] > tokens.MAX_WORD):
                        token.add_uword(token_index, values[val_index])
                    else:
                        token.add_word(token_index, values[val_index])
                    token_index += 2
                    val_index += 1

            token.finish(token_stream)

    # Add the info about the variable to the token_stream
    if (name != '*'):
        token_stream.add_variable(space, name, start, real_length)


def assem_spec_data_lcd(which, words, line):
    io.Out.DebugRaw("Spec_data_lcd which:%s words:%s" % (which, hl_parser.format_word_list(words)))

    if (len(words) < 4):
        AsmError_NO_RET(53, "DATA needs at least 4 arguments: row, col, len, val1")

    if (words[0].val() == '*'):
        AsmError_NO_RET(54, "DATA needs a real row")
    else:
        row = words[0].anum()

    if (words[1].val() == '*'):
        AsmError_NO_RET(55, "DATA needs a real column")
    else:
        column = words[1].anum()

    start = row * ROW_LENGTH + column

    if (words[2].val() == '*'):
        length = -1
    else:
        length = words[2].anum()

    words = words[3:]

    values = []
    # now words are the values
    for w in words:
        if (w.type() not in ["arg", "string"]):
            AsmError_NO_RET(56, "Word should have been an argument or string!")
        else:
            if (w.type() == "string"):
                for c in w.val():
                    values.append(ord(c))
            else:
                values.append(w.anum())

    # Do space sanity checks
    if (length > 0 and len(values) > length):
        AsmError_NO_RET(57, "Data has length of %d but more values (%d) then length" %
                         (length, len(values)))

    if (length > 0):
        real_length = length
    else:
        real_length = len(values)

    if (start + real_length > ROW_LENGTH * COL_LENGTH):
        io.Out.Error(io.TS.ASM_MEM_OVERFLOW,
                     "file::: Overflowed {0} memory", which)
        raise program.AssemblerError

    # Add spaces if needed
    if ((length > 0) and (length > len(values))):
        while (len(values) < length):
            values.append(' ')

    # Make the tokens
    if (len(values)):

        tokens_to_create = (len(values) + 14) / 15
        last = len(values) % 15

        # print(tokens_to_create, last)
        val_index = 0
        for i in range(tokens_to_create):
            token = tokens.Token("data", err, line)
            token.add_bits(0, 4, 3, 3)
            if ((i < (tokens_to_create - 1)) or (last == 0)):
                val_count = 15
            else:
                val_count = last

            token.add_bits(0, 0, 0xf, val_count)

            # add the row/column
            loc = start + i * 15
            token.add_byte(1, loc / ROW_LENGTH)
            token.add_byte(2, loc % ROW_LENGTH)

            token_index = 3
            # add the data
            for j in range(val_count):
                # print(val_index)
                token.add_byte(token_index, values[val_index])
                token_index += 1
                val_index += 1

            token.finish(token_stream)


def assem_spec_binary(which, words, line):
    io.Out.DebugRaw("Spec_binary which:%s words:%s" % (which, hl_parser.format_word_list(words)))

    token = tokens.Token("binary", err, line)
    token_index = 0

    # now words are the values
    for w in words:
        if (w.type() not in ["arg", "string", "const"]):
            AsmError_NO_RET(58, "Word should have been an argument or string!")
        else:

            if (w.type() == "string"):
                for c in w.val():
                    token.add_byte(token_index, ord(c))
                    token_index += 1
            else:
                token.add_byte(token_index, w.anum())
                token_index += 1

    token.finish(token_stream)


def assem_spec_reserve(which, words, line):
    io.Out.DebugRaw("Spec_reserve which:%s words:%s" % (which, hl_parser.format_word_list(words)))
    if (len(words) != 2):
        AsmError_NO_RET(59, "RESERV[ABW] needs 2 arguments: start, length")

    token_stream.reserve_name_space(tokens.space_types[which], words[0].anum(), words[1].anum())


def assem_spec_version(words, line):
    io.Out.DebugRaw("Spec_version words:%s" % (hl_parser.format_word_list(words)))
    if (len(words) != 2):
        AsmError_NO_RET(60, "VERSION needs 2 arguments: major, minor")
    major = words[0].anum()
    minor = words[1].anum()

    if (major < 0 or major > 15):
        AsmError_NO_RET(61, "major version must be between 0 and 15 (not %d)" % major)

    if (minor < 0 or minor > 15):
        AsmError_NO_RET(62, "minor version must be between 0 and 15 (not %d)" % major)

    token_stream.add_version(major, minor)


def assem_spec_begin_end(op, words, line):
    io.Out.DebugRaw("Spec_begin_end op:%s words:%s" % (op, hl_parser.format_word_list(words)))
    if (len(words) < 1):
        AsmError_NO_RET(63, "BEGIN/END need a type argument")

    if (words[0].astr() == "FIRMWARE"):
        if (op == "BEGIN"):
            if (len(words) != 1):
                AsmError_NO_RET(64, "FIRMWARE doesn't take any arguments.")
            token_stream.add_begin("firmware")
        else:
            # END MAIN
            token_stream.add_end("firmware")
    elif (words[0].astr() == "EVENT"):
        if (op == "BEGIN"):
            if (len(words) != 4):
                AsmError_NO_RET(65, "EVENT needs 3 arguments: mod/reg, mask, value")
            modreg = words[1].amodreg()
            mask = words[2].anum()
            value = words[3].anum()
            token_stream.add_begin("event", modreg, mask, value)
        else:
            # END EVENT
            token_stream.add_end("event")

    elif (words[0].astr() == "MAIN"):
        if (op == "BEGIN"):
            if (len(words) != 1):
                AsmError_NO_RET(66, "MAIN doesn't take any arguments.")
            token_stream.add_begin("main")
        else:
            # END MAIN
            token_stream.add_end("main")

    else:
        AsmError_NO_RET(67, "BEGIN/END needs one of: MAIN, EVENT, FIRMWARE")


def assem_spec_limits(words, line):
    io.Out.DebugRaw("Spec_limits words:%s" % (hl_parser.format_word_list(words)))
    if (len(words) != 5):
        AsmError_NO_RET(68, "LIMITS needs exactly 5 arguments")

    b_limit = words[0].anum()
    w_limit = words[1].anum()
    # In this token stream there is no LCD
    # l_limit = words[2].anum()
    l_limit = 0
    e_handlers = words[3].anum()
    t_bytes_limit = words[4].anum()

    token_stream.set_limits(b_limit, w_limit, l_limit, e_handlers, t_bytes_limit)


def assem_spec_device(words, line):
    io.Out.DebugRaw("Spec_device words:%s" % (hl_parser.format_word_list(words)))
    if (len(words) == 2):
        name = ""
    elif (len(words) == 3):
        name = words[2].astr()
    else:
        AsmError_NO_RET(69, "DEVICE needs 2 or 3 arguments")

    device_type = words[0].astr()
    location = words[1].anum()

    # error checking is done in the hl_parser
    # add the device to the high_level parser for parsing of subsequent names
    if (hl_parser.add_device(location, device_type, name)):
        token_stream.add_device(hl_parser.device_types[device_type], location,
                                hl_parser.device_storage[device_type])


def assem_spec_insert(words, line):
    io.Out.DebugRaw("Spec_insert words:%s" % (hl_parser.format_word_list(words)))
    if (len(words) != 2):
        AsmError_NO_RET(70, "INSERT needs type and filename arguments")

    type = words[0].astr()
    f_name = words[1].astr()

    if (type.lower() not in ['tokens', 'binary']):
        AsmError_NO_RET(71, "INSERT type must be one of: 'tokens', 'binary'")

    if (type.lower() == 'tokens'):
        AsmError_NO_RET(72, "INSERT TOKENS should have been consumed higher up! Eek!")

    # we have an insert binary special to deal with
    if (not os.path.isfile(f_name) or not os.access(f_name, os.R_OK)):
        AsmError_NO_RET(73, "INSERT BINARY file:%s doesn't exist or isn't readable")

    token = tokens.Token("binary", err, line)
    token.add_binary_file(f_name)
    token.finish(token_stream)


def assem_spec_comms(words, line):
    io.Out.DebugRaw("Spec_comms words:%s" % (hl_parser.format_word_list(words)))
    if (len(words) != 1):
        AsmError_NO_RET(74, "COMMS needs exactly 1 argument")

    token = tokens.Token("comms", err, line)
    token.add_bits(0, 0, 0xf, 0x8)

    token.add_uword(1, words[0].anum())
    token.finish(token_stream)

    token_stream.set_comms(words[0].anum())


def assem_spec_finish(words, line):
    io.Out.DebugRaw("Spec_finish words:%s" % (hl_parser.format_word_list(words)))
    if (len(words) != 0):
        AsmError_NO_RET(75, "FINISH doesn't have any arguments")

    token_stream.finish_tokens()


# *********** Sequencing the assembly *********************************

def assemble_file(srcPath, debug):
    global token_stream

    io.Out.Top(io.TS.ASM_START, "Starting assembler")
    ok = True

    try:
        # setup the token stream
        token_stream = tokens.TokenStream()
        token_stream.clear()
        ok = assem_file(srcPath, [])

    except program.EdPyError:
        ok = False
        if (io.Out.IsReRaiseSet()):
            raise

    except:
        ok = False
        io.Out.Error(io.TS.CMP_INTERNAL_ERROR,
                     "file::: Compiler internal error {0}", 703)
        if (io.Out.IsReRaiseSet()):
            raise

    if (not ok):
        # print("ERROR when assembling!")
        return [], "", "", (0, 0)

    # print (len(lines), lines[0])
    return finish_assembley(srcPath, debug)


def assemble_lines(lines, debug):
    global token_stream

    io.Out.Top(io.TS.ASM_START, "Starting assembler")
    ok = True

    try:
        # setup the token stream
        token_stream = tokens.TokenStream()
        token_stream.clear()
        ok = assem_lines(lines)

    except program.EdPyError:
        ok = False
        if (io.Out.IsReRaiseSet()):
            raise

    except:
        ok = False
        io.Out.Error(io.TS.CMP_INTERNAL_ERROR,
                     "file::: Compiler internal error {0}", 704)
        if (io.Out.IsReRaiseSet()):
            raise

    if (not ok):
        # print("ERROR when assembling!")
        return [], "", "", (0, 0)

    # print (len(lines), lines[0])
    return finish_assembley("internal", debug)


def finish_assembley(source, debug):
    ok = True
    try:
        token_analysis = tokens.TokenAnalyser(token_stream)
        token_analysis.map_all_variables()

        if (debug and not io.Out.WasErrorRaised()):
            hl_parser.dump_devices()
            token_analysis.dump_variable_map()

        token_analysis.fixup_jumps()

        if (debug and not io.Out.WasErrorRaised()):
            token_stream.dump_tokens(source)
            token_analysis.dump_extras()

        download_type, version, header, added_bytes = token_analysis.create_header()
        # print(download_type, version, header)

    except:
        ok = False
        if (io.Out.IsReRaiseSet()):
            raise

    if (not ok):
        # print("ERROR when assembling!")
        return [], "", "", (0, 0)

    # get the token bytes
    download_str = ""
    download_bytes = []
    for t in header:
        download_bytes.append(t)
        download_str += chr(t)

    for t in token_stream.token_stream:
        bytes = t.get_token_bits()
        download_bytes.extend(bytes)
        for b in bytes:
            download_str += chr(b)

    if (added_bytes > 0):
        extra_bytes = [0xff] * added_bytes
        download_bytes.extend(extra_bytes)
        for b in extra_bytes:
            download_str += chr(b)

    return download_bytes, download_str, download_type, version


# ********* Main and tests ********************************************


def test():
    global token_stream
    global err

    test_simp = ["incb %acc", "movb 12,@lil_count", "decw 1001/2", " # a comment line",
                  "   addb  $12 #do some adding",
                  "movb $'a', %acc", "branch :label1", "decw", "mulw 44", "subb $1000", "subw $-3000",
                  "movb $0, @big_count", "movw @last_reading, @store_reading"]

    test_jump = ["brne :f1", "bra $-1", "ret", ":f1", "dbnz :f2", "dsnz $10", "suba $10", ":f2"]
    test_stack = ["pushb $32", "pushw @count", "popb %acc", "popw 0x39", "pushw 43"]

    test_data = ["DATA home, 0", "DATB *, 0, 20, 'a'", ":start", "DATW intensity, *, *, -20",
                 'DATA buffer, *, 32, "This is an \"interesting\" string"']

    test_spec = ["LIMITS -1, -1, -1, 0, 0", "LIMITS 30, 10, 64, 0, 200",
                 "RESERVA 0, 16", "RESERVB 31,1", "RESERVW 0, 1"]

    test_device = ["DEVICE bad, 1", "DEVICE motor, 0", "DEVICE motor 13", "DEVICE motor 1 **",
                   "DEVICE digin, 1", "DEVICE motor 2, left_wheel", "DEVICE motor 4 right_wheel",
                   "DEVICE digout, 5", "DEVICE analogin 6"]
    test_begin_end = ["BEGIN WTF", "BEGIN PROGRAM 1", "BEGIN CONFIG", "BEGIN EVENT 34, 43,44",
                      "END PROGRAM CONFIG 0 0",
                      "BEGIN CONFIG 0,0", "BEGIN PROGRAM", "BEGIN EVENT %acc 0xfe 20/16"]

    test_other = ["stop 1", "COMMS", "COMMS 1 2", "FINISH 2",
                  ":start1", ":start2",
                  "stop", "FINISH", "COMMS 1024", "COMMS 400/16", "COMMS 0x400"]

    test_prog1 = ["COMMS 0x400", "LIMITS 20, 10, 64, 0, 200", 'RESERVB 0, 3', 'RESERVB 6, 2',
                  'RESERVW 0, 2', 'RESERVW 4,1', 'RESERVA 0, 5',
                  "BEGIN CONFIG 0,0", "BEGIN PROGRAM", "DATB count *", "DATB buffer *, 10",
                  "DATW temps *, 5", 'DATA message * * "This is fun but long - will it work?"',
                  "movb 5, @count", ":b1", "movb @count, %acc", "cmpb 0",
                  "bre :f1", "decb @count", "bra :b1",
                  ":f1", "movb 0, %acc", "END PROGRAM", "END CONFIG", "FINISH"]


    test_prog1 = ["COMMS 0x400", "LIMITS 200, 10, 64, 0, 200", 'RESERVB 0, 3', 'RESERVB 6, 2',
                  'RESERVW 0, 2', 'RESERVW 4,1', 'RESERVA 0, 5', 'DEVICE motor 1', 'DEVICE digin 2',
                  "BEGIN CONFIG 0,0", "BEGIN MAIN", "DATB count *", "DATB buffer *, 10",
                  "DATW temps *, 5", 'DATA message * * "This is fun but long - will it work?"',
                  '::top', 'DATB *, 0, 200',
                  "movb $5, @count", ":b1", "movb @count, %acc", "cmpb 0",
                  "bre :f1", "decb @count", "bra :b1",
                  ":f1", "movb 0, %acc", 'bra ::top',
                  "END MAIN",
                  "BEGIN EVENT %2C 1 1", ":f1", 'movw $-150, @temps', 'brne :f1',
                  'INSERT BINARY email.sig', 'bra :f1', 'END EVENT',
                  "END CONFIG", "FINISH"]

    test_prog2 = ['BEGIN FIRMWARE 0, 0, 0', 'BINB 0x10 20/16 255', 'BINB "Copyright"',
                  'INSERT BINARY email.sig', 'END FIRMWARE', 'FINISH']

    test_new_bad = ['bitset', 'bitset 3', 'bitset 3 2', 'bitset 29, f3'] # Bads
    test_new_good = ['BEGIN CONFIG 0,0', 'BEGIN MAIN',
                     'bitset 3 f3', 'bitset 0 ff',
                     'END MAIN', 'END CONFIG', 'FINISH']

    io.Out.DebugRaw("Starting test")

    token_stream = tokens.TokenStream()
    token_stream.clear()

    test_lines = []

    #test_lines.extend(test_simp)
    #test_lines.extend(test_jump)
    #test_lines.extend(test_stack)
    #test_lines.extend(test_data)
    #test_lines.extend(test_spec)
    #test_lines.extend(test_device)
    #test_lines.extend(test_begin_end)
    #test_lines.extend(test_other)
    #test_lines.extend(test_prog2)
    test_lines.extend(test_new_good)

    for t in test_lines:
        assem_line(t)

    token_stream.dump_tokens()
    io.Out.DebugDumpObjectRaw(token_stream, "TokenStream")

    token_analysis = tokens.TokenAnalyser(token_stream)
    token_analysis.map_all_variables()
    token_analysis.dump_variable_map()
    token_analysis.fixup_jumps()
    #token_analysis.fixup_sections()     # Add section headers including lengths
    token_analysis.fixup_jumps()        # Fixup globals which may change because of section headers
    token_analysis.fixup_crcs()         # Finally the crcs -- nothing will change now

    token_stream.dump_tokens()
    io.Out.DebugDumpObjectRaw(token_analysis, "Token_analyser")
