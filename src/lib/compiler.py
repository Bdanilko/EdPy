#!/usr/bin/env python2
# * **************************************************************** **
# File: compiler.py
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

#
# Most messages should not be seen by the user, just during debugging,
# so most are not translated.
#

""" Module to take the IR structure and compile to assembler"""

from __future__ import print_function
from __future__ import absolute_import

import re

# from . import util
from . import io
from . import program
from . token_bits import *
from . import edpy_values

# When accessing variables on the stack, must go past the return frame
RETURN_FRAME_OFFSET = 3

VERBOSE = True

JUMP_OPT_RE = re.compile("bra (\:+\w+)\s*")
JUMP_TARGET_RE = re.compile("(\:+\w+)\s*")
STACK_WRITE_RE = re.compile("stwaw (\$?\w+)\s*")
STACK_READ_RE = re.compile("straw (\$?\w+)\s*")
STACK_CHANGE_RE = re.compile("st(inc|dec) \$(\d+)\s*")
STACK_ACCESS_RE = re.compile("st(w|r)aw \$(\d+)\s*")
RET_RE = re.compile("ret\s*")

def CompileError_NO_RET(number, internalError=None, line=0):
    if (internalError):
        io.Out.ErrorRaw(internalError)

    io.Out.Error(io.TS.CMP_INTERNAL_ERROR,
                 "file::: Compiler internal error {0}", number)
    raise program.CompileError

def CompileBadVariable_NO_RET  (variable, problem, line=0):
    io.Out.Error(io.TS.CMP_VAR_NOT_BOUND,
                     "file::: Syntax Error, Problem with variable {0} ({1})", variable, problem)
    raise program.CompileError


class CompileState(object):
    """Keeps the state of the compilation, the generated assembler,
       etc."""

    def __init__(self):
        self.statements = []
        self.nextLabel = 0
        self.globalVar = {}
        self.byteData = {}
        self.wordData = {}
        self.bytesUsed = 0
        self.wordsUsed = 0

        self.objectSize = {}
        self.eventHandler = {}
        self.classLayout = {}
        self.funArgLayout = {}
        self.funVarLayout = {}
        self.funVarInfo = {}
        self.funStackSize = {}
        self.funGlbAccess = {}
        self.funcReturnsValue = {}

        self.controlLabels = []

    def AddStatement(self, statement):
        self.statements.append(statement)

    def NextInternalLabel(self):
        label = ":_int_%04d" % (self.nextLabel)
        self.nextLabel += 1
        return label

    def RecordControlLabel(self, label):
        if (label not in self.controlLabels):
            self.controlLabels.append(label)

    def ForgetControlLabels(self):
        self.controlLabels = []

    def AddEventHandler(self, event, function):
        if (event.IsIntConst() and function.IsStrConst()):
            self.eventHandler[event.constant] = function.strConst

    def Dump(self):
        """Dump the internal state"""
        print("CompileState")
        print("\nGlobalVars:", self.globalVar)
        print("\nInternal labels used:", self.nextLabel)
        print("\nControl labels recorded:", self.controlLabels)
        print("\nEvent handlers:", self.eventHandler)
        print("\nByte Data: used:", self.bytesUsed, ", map:", self.byteData)
        print("\nWord Data: used:", self.wordsUsed, ", map:", self.wordData)
        print("\nObject size:", self.objectSize)
        print("\nClass Layout map:", self.classLayout)
        print("\nFunction Arg layout:", self.funArgLayout)
        print("\nFunction Var layout:", self.funVarLayout)
        print("\nFunction Var info:", self.funVarInfo)
        print("\nFunction Glb access:", self.funGlbAccess)
        print("\nFunction stack size:", self.funStackSize)
        print("\nStatements:")
        for s in self.statements:
            print(s)

    def OptimiseJumps(self):
        """Find instances of bra to a label and the label is the
           next executable statement"""
        saved = 0
        newList = []
        optPassList = []
        optFailList = []
        target = ""
        possibleOpt = False

        # print("Start OptimiseJumps")

        for l in self.statements:
            if (possibleOpt):
                if (l.startswith('#')):
                    optPassList.append(l)
                    optFailList.append(l)
                elif (l.startswith(':')):
                    m = JUMP_TARGET_RE.match(l)
                    if (m.group(1) == target):
                        # successfull optimisation
                        # print("OPT PASS - target", target, "found!")
                        newList.extend(optPassList)
                        newList.append(l)
                        optPassList = []
                        optFailList = []
                        saved += 1
                        possibleOpt = False
                    else:
                        optPassList.append(l)
                        optFailList.append(l)

                else:
                    # Opt failed as a non-label, non-comment was found
                    # before the target was found
                    # print("OPT FAIL - target", target, "not found")
                    newList.extend(optFailList)
                    newList.append(l)
                    optPassList = []
                    optFailList = []
                    possibleOpt = False
            else:
                m = JUMP_OPT_RE.match(l)
                if (m is not None):
                    possibleOpt = True
                    # print("Found", m.group(1))
                    target = m.group(1)
                    optPassList.append("# OPTIMISED OUT (JUMP): " + l)
                    optFailList.append(l)
                else:
                    newList.append(l)

        if (saved):
            self.statements = newList

        return saved

    def OptimiseReadsFromStack(self):
        """Find where there is a write from ACC to stack, and in the
           next executable statement, there is a read from the same
           location on the stack to the ACC. It was already there!"""
        saved = 0
        newList = []
        target = ""
        possibleOpt = False

        # print("Start OptimiseReadsFromStack")

        for l in self.statements:
            if (possibleOpt):
                if (l.startswith('#')):
                    newList.append(l)
                    continue
                else:
                    m = STACK_READ_RE.match(l)
                    if ((m is not None) and (m.group(1) == target)):
                        # successfull optimisation
                        # print("OPT PASS - target", target, "found!")
                        newList.append("# OPTIMISED OUT (STACK_READ): " + l)
                        saved += 1
                    else:
                        newList.append(l)

                    possibleOpt = False
            else:
                m = STACK_WRITE_RE.match(l)
                if (m is not None):
                    possibleOpt = True
                    # print("Found", m.group(1))
                    target = m.group(1)
                newList.append(l)

        if (saved):
            self.statements = newList

        return saved

    def OptimiseWritesToStack(self):
        """Find where there is a write from ACC to stack, and see
           if the value is ever read. If not then remove the write.
           Must not affect writes for function calls though!"""
        saved = 0
        newList = []
        fData = {}
        function = None

        # print("Start OptimiseWritesToStack")

        # scan to collect data
        for l in self.statements:
            if (l.startswith("::_fun_")):
                name = l[7:]
                # print("Function found:", l)
                function = l
                stackOffset = 0
                stackReads = set()
                stackWrites = set()
                if (self.funcReturnsValue[name]):
                    stackReads.add(3)

            elif (l.startswith(":_end_")):
                name = l[6:]
                # print("Function end found:", l)
                if (function is not None):
                    removeWrite = []
                    for w in stackWrites:
                        if (w not in stackReads):
                            removeWrite.append(w)

                    fData[function] = removeWrite
                    function = None

            else:
                if (function is None):
                    continue
                m = STACK_CHANGE_RE.match(l)
                if (m is not None):
                    if (m.group(1) == "inc"):
                        stackOffset += int(m.group(2))
                    else:
                        stackOffset -= int(m.group(2))
                    # print("New stack offset:", stackOffset)
                else:
                    m = STACK_ACCESS_RE.match(l)
                    if (m is not None):
                        stackLocation = int(m.group(2)) - stackOffset
                        if (stackLocation >= 0):
                            if (m.group(1) == 'r'):
                                stackReads.add(stackLocation)
                                # print("Stack read:", stackLocation)
                            else:
                                stackWrites.add(stackLocation)
                                # print("Stack write:", stackLocation)
                        else:
                            pass
                            # print("Stack out of range:", stackLocation)

        # do the optimisations
        # print(fData)

        for l in self.statements:
            if (l.startswith("::_fun_")):
                function = l
                newList.append(l)

            elif (l.startswith(":_end_")):
                function = None
                newList.append(l)

            else:
                if (function is None):
                    newList.append(l)
                    continue
                m = STACK_CHANGE_RE.match(l)
                if (m is not None):
                    if (m.group(1) == "inc"):
                        stackOffset += int(m.group(2))
                    else:
                        stackOffset -= int(m.group(2))
                    newList.append(l)
                else:
                    if (stackOffset != 0):
                        newList.append(l)
                        continue
                    m = STACK_ACCESS_RE.match(l)
                    if (m is not None):
                        stackLocation = int(m.group(2)) - stackOffset
                        if (stackLocation >= 0):
                            if (m.group(1) == 'w'):
                                # print("Stack write:", stackLocation)
                                if (stackLocation in fData[function]):
                                    newList.append("# OPTIMISED OUT (STACK_WRITE): " + l)
                                    saved += 1
                                    continue
                    newList.append(l)

        if (saved):
            self.statements = newList

        return saved

    def OptimiseDoubleReturns(self):
        """Find instances of two returns next to each other and remove one"""
        saved = 0
        newList = []
        lastWasReturn = False

        # print("Start OptimiseDoubleReturns")

        for l in self.statements:
            if (l.startswith(":")):
                lastWasReturn = False

            m = RET_RE.match(l)
            if (m != None):
                if (lastWasReturn):
                    l = "# OPTIMISED OUT (DBL-RET): " + l
                    saved += 1
                    # print("OPT PASS - found double return")
                else:
                    lastWasReturn = True

            newList.append(l)

        if (saved):
            self.statements = newList

        return saved

    def OptimiseUselessStackOps(self):
        """Find where there is a read from stack to ACC, and in the
           next executable statement, there is a write from the ACC to
           the same location on the stack. That sequence did NOTHING"""

        saved = 0
        newList = []
        optPassList = []
        optFailList = []

        target = ""
        possibleOpt = False

        # print("Start OptimiseUselessStackOps")

        for l in self.statements:
            if (possibleOpt):
                if (l.startswith('#')):
                    optPassList.append(l)
                    optFailList.append(l)
                    continue
                elif (l.startswith(":")):
                    # possible opt failed
                    newList.extend(optFailList)
                    newList.append(l)
                    optPassList = []
                    optFailList = []
                    possibleOpt = False

                else:
                    m = STACK_WRITE_RE.match(l)
                    if ((m is not None) and (m.group(1) == target)):
                        # successfull optimisation
                        # print("OPT PASS - target", target, "found!")
                        optPassList.append("# OPTIMISED OUT (USELESS_STACK_OP): " + l)
                        newList.extend(optPassList)
                        saved += 2
                    else:
                        newList.extend(optFailList)
                        newList.append(l)

                    optPassList = []
                    optFailList = []
                    possibleOpt = False
            else:
                m = STACK_READ_RE.match(l)
                if (m is not None):
                    possibleOpt = True
                    # print("Found", m.group(1))
                    target = m.group(1)

                    optPassList.append("# OPTIMISED OUT (USELESS_STACK_OP): " + l)
                    optFailList.append(l)

                else:
                    newList.append(l)

        if (saved):
            self.statements = newList

        return saved

    def Optimise(self):
        """Find common optimisations and apply them"""
        saved = 0
        saved += self.OptimiseJumps()
        saved += self.OptimiseReadsFromStack()
        saved += self.OptimiseWritesToStack()
        saved += self.OptimiseDoubleReturns()
        saved += self.OptimiseUselessStackOps()

        # print("Optimiser saved", saved, "tokens")


# ############ utility functions ########################################


def GetVariableInfo(funcName, varValue, compileState):
    """To write it's either global (in glbAccess) or local
    returns (type, name, offset, index_info) with:
    index_info = a constant (for GC, LC) or for LV,GV = (type, name, offset)
                 (type can only be L or G)
    Return code is one of:
    L - local variable (on the stack by definition) - ('L', varName, offset, None)
    G - global simple var - ('G', varName, 1, None)
    GV - global slice indexed by var  - ('GV', varName, SIZE, index_info)
    GC - global variable indexed by constant - ('GC', varName, SIZE, constant)
    LV - local slice ref indexed by var  - ('LV', varName, offset, index_info)
    LC - local slice ref indexed by constant - ('LC', varName, offset, constant)
    GO - global object ('GO',
    LO - local object ('LO',
    """
    # print("GetVariableInfo - ", funcName, varValue)
    if (type(varValue.name) is int):
        varName = MakeTempName(varValue.name)
    else:
        varName = varValue.name
    varLayout = compileState.funVarLayout[funcName]


    className, sep, methodName = funcName.partition('.')
    varClass, sep, varMember = varName.partition('.')

    if (varClass != "Ed" and varClass != "self" and varMember != ""):
        # An global object reference
        if (varClass not in compileState.globalVar):
            CompileBadVariable_NO_RET(varName, "unknown class")

        varInfo = compileState.globalVar[varClass]
        if (varInfo[1] != 'O'):
            CompileBadVariable_NO_RET(varName, "not an object")

        classData = compileState.classLayout[varInfo[2]]
        lclName = "self."+varMember
        if (lclName not in classData[1]):
            CompileBadVariable_NO_RET(varMember, "not in the class")

        # print("Found - ", varClass, varMember, varName, varInfo, classData)
        rtc = ("GO", varClass, classData[1][lclName], className)

        return rtc

    # print("**VarName**", varName, varLayout, className, sep, methodName)

    if ((methodName is not None) and varName.startswith("self.")):
        classData = compileState.classLayout[className]
        rtc = ("LO", varName, classData[1][varName], className)
        # print("Found class data class", rtc)
        return rtc

    if (varName in varLayout):
        # must be local - so on the stack -- sizes for slices are encoded in the variable
        # so tokens have to retrieve it if it's wanted

        if (not varValue.IsSlice()):
            return ("L", varName, varLayout[varName], None)
        else:
            # a slice, so the variable contains the (size << 8) | address
            if (varValue.indexConstant is not None):
                return ("LC", varName, varLayout[varName], varValue.indexConstant)

            elif (type(varValue.indexVariable) is int):
                tempName = MakeTempName(varValue.indexVariable)

                if (tempName not in varLayout):
                    CompileError_NO_RET(4, "Variable not local:" + tempName)

                offset = varLayout[tempName]
                return ("LV", varName, varLayout[varName], ("L", tempName, offset))
            else:
                if (varValue.indexVariable in compileState.globalVar):
                    return ("LV", varName, varLayout[varName], ("G", varValue.indexVariable, None))
                else:
                    # index must be local
                    if (varValue.indexVariable not in varLayout):
                        CompileBadVariable_NO_RET(varValue.indexVariable, "bad index")

                    offset = varLayout[varValue.indexVariable]
                    return ("LV", varName, varLayout[varName], ("L", varValue.indexVariable, offset))


    elif (varName in compileState.globalVar):
        if (not varValue.IsSlice()):
            return ("G", varName, 1, None)
        else:
            size = compileState.objectSize[varName]
            if (varValue.indexConstant is not None):
                return ("GC", varName, size, varValue.indexConstant)

            elif (type(varValue.indexVariable) is int):
                # Temp is the index, so local
                tempName = MakeTempName(varValue.indexVariable)

                if (tempName not in varLayout):
                    CompileError_NO_RET(1, "Variable not local:" + tempName)

                offset = varLayout[tempName]
                return ("GV", varName, size, ("L", tempName, offset))
            else:
                if (varValue.indexVariable in compileState.globalVar):
                    return ("GV", varName, size, ("G", varValue.indexVariable, None))
                else:
                    # must be local
                    if (varValue.indexVariable not in varLayout):
                        CompileBadVariable_NO_RET(varValue.indexVariable, "bad index")

                    offset = varLayout[varValue.indexVariable]
                    return ("GV", varName, size, ("L", varValue.indexVariable, offset))

    else:
        # error -- not global or local!
        CompileBadVariable_NO_RET(varName, "unknown variable")


def ReadWordSliceToWindow(sliceValue, compileState, functionName):
    if (functionName == "__main__"):
        sliceBase = sliceValue.name
        if (sliceBase in compileState.globalVar):
            if (sliceValue.indexConstant is not None):
                pass


def CheckSpecialUAdd(programIR, functionName, line, compileState):
    # check for the special case of assigning a char to a tune string element
    (tType, tName, tOffset, info) = GetVariableInfo(functionName, line.target, compileState)

    vInfo = None
    # Must be GV, GC, LV, or LC
    if (tType in ("GV", "GC")):
        vInfo = programIR.globalVar
    elif (tType in ("LV", "LC")):
        vInfo = compileState.funVarInfo[functionName]

    if (vInfo is not None):
        # print(functionName, vInfo)
        if (vInfo[tName][0] == 'T'):
            # assignment to a TUNE STRING -- must be from a StrConst or another tuneString
            if (line.operand.IsStrConst() and (len(line.operand.strConst) == 1)):
                compileState.AddStatement("movb ${} %_cpu:acc".format(ord(line.operand.strConst[0])))
                StoreAccIntoByteVariable(line.target, functionName, compileState)
                return True

            elif (line.operand.IsSlice()):
                if (vInfo[line.operand.name][0] == 'T'):
                    LoadByteVariableIntoAcc(line.operand, functionName, compileState)
                    StoreAccIntoByteVariable(line.target, functionName, compileState)
                    return True
                else:
                    CompileError_NO_RET(33, "1 character string constant or tune string element needed here")
            else:
                CompileError_NO_RET(31, "1 character string constant or tune string element needed here")
    return False


def CompileUassign(programIR, functionName, line, compileState):
    # tokens to do the unary operation. Operation can be
    # UAdd, USub, Invert, Notg
    if (VERBOSE):
        compileState.AddStatement("# UAssign:" + str(line))

    if (line.operation == "UAdd"):

        if (CheckSpecialUAdd(programIR, functionName, line, compileState)):
            return

        # see if can optimise
        (tType, tName, tOffset, info) = GetVariableInfo(functionName, line.target, compileState)
        if (tType == "G"):
            if (line.operand.IsIntConst()):
                compileState.AddStatement("movw ${} @{}".format(line.operand.constant, tName))
                return
            else:
                if (line.operand.IsSimpleVar()):
                    (oType, oName, oOffset, info) = GetVariableInfo(functionName, line.operand, compileState)
                    if (oType == "G"):
                        compileState.AddStatement("movw @{} @{}".format(oName, tName))
                        return

    if (line.operand.IsIntConst()):
        compileState.AddStatement("movw ${} %_cpu:acc".format(line.operand.constant))
    elif (line.operand.IsStrConst()):
        # Should have been handled in the CheckSpecialUAdd() function
        CompileError_NO_RET(32, "StrConstant not allowed here")
    else:
        LoadWordVariableIntoAcc(line.operand, functionName, compileState)

    # do operation in ACC
    if (line.operation == "UAdd"):
        # Nothing to do for UAdd
        pass
    elif (line.operation == "USub"):
        compileState.AddStatement("mulw $-1")
    elif (line.operation == "Not"):
        wasZeroLabel = compileState.NextInternalLabel()
        endLabel = compileState.NextInternalLabel()
        compileState.AddStatement("brz {}".format(wasZeroLabel))
        compileState.AddStatement("movw $0 %_cpu:acc")  # set to 0
        compileState.AddStatement("bra {}".format(endLabel))
        compileState.AddStatement("{}".format(wasZeroLabel))
        compileState.AddStatement("movw $1 %_cpu:acc")  # set to 1
        compileState.AddStatement("{}".format(endLabel))
    else:  # Invert
        compileState.AddStatement("notw %_cpu:acc")

    StoreAccIntoWordVariable(line.target, functionName, compileState)


def SetTempoAtStart(tempo, compileState):
    compileState.AddStatement("# Set intial tempo")
    compileState.AddStatement("movw ${} {}".format(tempo, "%68"))
    return


def CompileBassign(programIR, functionName, line, compileState):
    # tokens to do the binary operation. Operation can be
    # operator = Add | Sub | Mult | Div | Mod | Pow | LShift
    #                | RShift | BitOr | BitXor | BitAnd | FloorDiv
    #                | Eq | NotEq | Lt | LtE | Gt | GtE
    if (VERBOSE):
        compileState.AddStatement("# BAssign:" + str(line))

    if (line.right.IsIntConst()):
        if (line.left.IsIntConst()):
            compileState.AddStatement("movw ${} %_cpu:acc".format(line.left.constant))
        else:
            LoadWordVariableIntoAcc(line.left, functionName, compileState)

        if (line.operation == "Add"):
            compileState.AddStatement("addw ${}".format(line.right.constant))
        elif (line.operation == "Sub"):
            compileState.AddStatement("subw ${}".format(line.right.constant))
        elif (line.operation == "Mult"):
            compileState.AddStatement("mulw ${}".format(line.right.constant))
        elif (line.operation == "Div"):
            compileState.AddStatement("divw ${}".format(line.right.constant))
        elif (line.operation == "Mod"):
            compileState.AddStatement("modw ${}".format(line.right.constant))
        elif (line.operation == "Pow"):
            compileState.AddStatement("# IMPLEMENT POWER")
        elif (line.operation == "LShift"):
            compileState.AddStatement("shlw ${}".format(line.right.constant))
        elif (line.operation == "RShift"):
            compileState.AddStatement("shrw ${}".format(line.right.constant))
        elif (line.operation == "BitOr"):
            compileState.AddStatement("orw ${}".format(line.right.constant))
        elif (line.operation == "BitXor"):
            compileState.AddStatement("xorw ${}".format(line.right.constant))
        elif (line.operation == "BitAnd"):
            compileState.AddStatement("andw ${}".format(line.right.constant))
        elif (line.operation == "FloorDiv"):
            compileState.AddStatement("divw ${}".format(line.right.constant))

        elif (line.operation in ("Lt", "LtE", "Gt", "GtE", "Eq", "NotEq")):
            compileState.AddStatement("cmpw ${}".format(line.right.constant))
            FinishCompare(line.operation, compileState)

        else:
            CompileError_NO_RET(6, "Unknown binary op:"+line.operation)

    else:

        LoadWordVariableIntoAcc(line.right, functionName, compileState)
        compileState.AddStatement("movw %_cpu:acc @_CALC")

        if (line.left.IsIntConst()):
            compileState.AddStatement("movw ${} %_cpu:acc".format(line.left.constant))
        else:
            LoadWordVariableIntoAcc(line.left, functionName, compileState)

        # now left is in ACC, right is in @_CALC
        if (line.operation in ("Lt", "LtE", "Gt", "GtE", "Eq", "NotEq")):
            compileState.AddStatement("cmpw @_CALC")
            FinishCompare(line.operation, compileState)

        else:
            # do operation in ACC
            if (line.operation == "Add"):
                compileState.AddStatement("addw @_CALC")
            elif (line.operation == "Sub"):
                compileState.AddStatement("subw @_CALC")
            elif (line.operation == "Mult"):
                compileState.AddStatement("mulw @_CALC")
            elif (line.operation == "Div"):
                compileState.AddStatement("divw @_CALC")
            elif (line.operation == "Mod"):
                compileState.AddStatement("modw @_CALC")
            elif (line.operation == "Pow"):
                compileState.AddStatement("# IMPLEMENT POWER")
            elif (line.operation == "LShift"):
                compileState.AddStatement("shlw @_CALC")
            elif (line.operation == "RShift"):
                compileState.AddStatement("shrw @_CALC")
            elif (line.operation == "BitOr"):
                compileState.AddStatement("orw @_CALC")
            elif (line.operation == "BitXor"):
                compileState.AddStatement("xorw @_CALC")
            elif (line.operation == "BitAnd"):
                compileState.AddStatement("andw @_CALC")
            elif (line.operation == "FloorDiv"):
                compileState.AddStatement("divw @_CALC")

            elif (line.operation in ("Lt", "LtE", "Gt", "GtE", "Eq", "NotEq")):
                compileState.AddStatement("cmpw @_CALC")
                FinishCompare(line.operation, compileState)

            else:
                CompileError_NO_RET(7, "Unknown binary op:" + line.operation)

    StoreAccIntoWordVariable(line.target, functionName, compileState)


def FinishCompare(op, compileState):
    # compare has just been done, flags are set
    noLabel = compileState.NextInternalLabel()
    endLabel = compileState.NextInternalLabel()

    # Note that Python and token language are backwards from
    # the point of view of <, > compares. In python we have
    # lhs > rhs - means greater. In ed-tokens we have
    # rhs > lhs - means greater
    #
    # Op  Python Ed-tokens False-Ed-tokens  Op Python Ed-tokens False-Ed-tokens
    # LT  LT     GE        LE               GT GT     LE        GE
    # LE  LE     GT        LT               GE GE     LT        GT
    # other are same

    if (op == "Lt"):
        compileState.AddStatement("brle {}".format(noLabel))
    elif (op == "LtE"):
        compileState.AddStatement("brl {}".format(noLabel))
    elif (op == "Gt"):
        compileState.AddStatement("brge {}".format(noLabel))
    elif (op == "GtE"):
        compileState.AddStatement("brgr {}".format(noLabel))
    elif (op == "Eq"):
        compileState.AddStatement("brne {}".format(noLabel))
    elif (op == "NotEq"):
        compileState.AddStatement("bre {}".format(noLabel))

    compileState.AddStatement("movw $1 %_cpu:acc")
    compileState.AddStatement("bra {}".format(endLabel))
    compileState.AddStatement("{}".format(noLabel))
    compileState.AddStatement("movw $0 %_cpu:acc")
    compileState.AddStatement("{}".format(endLabel))


# INLINE FUNCTIONS!
#
# Any updates to these functions need to be changed in:
# edpy_values.signatures, edpy_code.CODE,
# compiler.SPECIALLY_HANDLED_FUNCTIONS, compiler.HandleSpecialCall
#

SPECIALLY_HANDLED_FUNCTIONS = ["Ed.List1", "Ed.List2", "Ed.TuneString1", "Ed.TuneString2",
                               "ord", "chr", "len",
                               "Ed.ReadModuleRegister8Bit", "Ed.ReadModuleRegister16Bit",
                               "Ed.WriteModuleRegister8Bit", "Ed.WriteModuleRegister16Bit",
                               "Ed.ClearModuleRegisterBit", "Ed.SetModuleRegisterBit",
                               "Ed.AndModuleRegisterBit", "Ed.ObjectAddr",
                               "Ed.CreateObject",
                               "Ed.RegisterEventHandler",
                               # New simple motor functions
                               "Ed.SimpleDriveForwardRight", "Ed.SimpleDriveForwardLeft",
                               "Ed.SimpleDriveForward", "Ed.SimpleDriveBackward",
                               "Ed.SimpleDriveBackwardRight", "Ed.SimpleDriveBackwardLeft",
                               "Ed.SimpleDriveStop",
                               # Optimised drive functions
                               "Ed.Drive_INLINE_UNLIMITED", "Ed.DriveLeftMotor_INLINE_UNLIMITED",
                               "Ed.DriveRightMotor_INLINE_UNLIMITED",
                              ]


def HandleSpecialCall(programIR, caller, callee, line, compileState):
    if (callee in ("Ed.List1", "Ed.List2", "Ed.TuneString1", "Ed.TuneString2")):
        return True

    # print("Called HandleSpecialCall with {}".format(callee))

    if (callee == "Ed.CreateObject"):
        # TODO - Clear the memory?
        return True

    elif (callee == "ord"):
        # move the single value directly to the return. The value is either
        # a string const or a ref to a tune string
        vTo = line.target
        if (vTo is not None):
            if (VERBOSE):
                compileState.AddStatement("# ORD:" + str(line))
            vFrom = line.args[0]
            LoadByteVariableIntoAcc(vFrom, caller, compileState)
            compileState.AddStatement("conv")
            StoreAccIntoWordVariable(vTo, caller, compileState)
        return True

    elif (callee == "chr"):
        # Convert an integer (w) into a char (b) -- only used when assigning to a tunestring
        vTo = line.target
        if (vTo is not None):
            if (VERBOSE):
                compileState.AddStatement("# CHR:" + str(line))

            vFrom = line.args[0]

            if (vFrom.IsIntConst()):
                compileState.AddStatement("movb ${} %_cpu:acc".format(vFrom.constant))
            else:
                LoadWordVariableIntoAcc(vFrom, caller, compileState)
                compileState.AddStatement("convl")
            StoreAccIntoByteVariable(vTo, caller, compileState)
        return True

    elif (callee == "len"):
        # find the length (stored in word variable)
        # \TODO - handle reference to TS and LIST, now just handles direct mention of globals
        vTo = line.target
        if (vTo is not None):
            if (VERBOSE):
                compileState.AddStatement("# LEN:" + str(line))
            vFrom = line.args[0]

            LoadWordVariableIntoAcc(vFrom, caller, compileState)
            compileState.AddStatement("shrw $8")
            StoreAccIntoWordVariable(vTo, caller, compileState)
        return True

    elif (callee == "Ed.ReadModuleRegister16Bit"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee,line))
        # Read from a module register
        vTo = line.target
        modRegHex = CreateModRegHex(line.args[0], line.args[1])
        if (vTo is not None):
            compileState.AddStatement("movw %{} %_cpu:acc".format(modRegHex))
            StoreAccIntoWordVariable(vTo, caller, compileState)
        return True

    elif (callee == "Ed.ReadModuleRegister8Bit"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee,line))
        # Read from a module register
        vTo = line.target
        modRegHex = CreateModRegHex(line.args[0], line.args[1])
        if (vTo is not None):
            compileState.AddStatement("movb %{} %_cpu:acc".format(modRegHex))
            compileState.AddStatement("conv")
            StoreAccIntoWordVariable(vTo, caller, compileState)
        return True

    elif (callee == "Ed.ClearModuleRegisterBit"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee,line))
        # Clear bit in a module register. Bit must be a constant
        modRegHex = CreateModRegHex(line.args[0], line.args[1])
        if (not line.args[2].IsIntConst()):
            CompileError_NO_RET(8, "Can only use constants when setting/clearing module reg bit")
        bit = line.args[2].constant
        if (bit < 0 or bit > 7):
            CompileError_NO_RET(9, "Bit constant is out of range")

        compileState.AddStatement("bitclr {} %{}".format(bit, modRegHex))
        return True

    elif (callee == "Ed.SetModuleRegisterBit"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee, line))
        # Set bit in a module register. Bit must be a constant
        modRegHex = CreateModRegHex(line.args[0], line.args[1])
        if (not line.args[2].IsIntConst()):
            CompileError_NO_RET(10, "Can only use constants when setting/clearing module reg bit")
        bit = line.args[2].constant
        if (bit < 0 or bit > 7):
            CompileError_NO_RET(11, "Bit constant is out of range")

        compileState.AddStatement("bitset {} %{}".format(bit, modRegHex))
        return True

    elif (callee == "Ed.WriteModuleRegister16Bit"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee, line))
        # Write to a module register
        modRegHex = CreateModRegHex(line.args[0], line.args[1])
        value = line.args[2]

        if (value.IsIntConst()):
            compileState.AddStatement("movw ${} %{}".format(value.constant, modRegHex))
        else:
            LoadWordVariableIntoAcc(value, caller, compileState)
            compileState.AddStatement("movw %_cpu:acc %{}".format(modRegHex))
        return True

    elif (callee == "Ed.WriteModuleRegister8Bit"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee, line))

        # Write to a module register
        modRegHex = CreateModRegHex(line.args[0], line.args[1])
        value = line.args[2]

        if (value.IsIntConst()):
            compileState.AddStatement("movb ${} %{}".format(value.constant, modRegHex))
        else:
            LoadWordVariableIntoAcc(value, caller, compileState)
            compileState.AddStatement("conv")
            compileState.AddStatement("movb %_cpu:acc %{}".format(modRegHex))
        return True

    elif (callee == "Ed.ObjectAddr"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee, line))

        vTo = line.target
        if (vTo is not None):
            vFrom = line.args[0]

            LoadWordVariableIntoAcc(vFrom, caller, compileState)
            compileState.AddStatement("andw $255")
            StoreAccIntoWordVariable(vTo, caller, compileState)
        return True

    elif (callee == "Ed.RegisterEventHandler"):
        if (VERBOSE):
            compileState.AddStatement("# {}:{}".format(callee, line))

        # The optimiser checks that the function exists and takes no parms
        compileState.AddEventHandler(line.args[0], line.args[1])

        return True

    elif (callee.startswith("Ed.SimpleDrive")):
        return AddSimpleDriveInlineFunction(callee, compileState, line)

    elif (callee.endswith("_INLINE_UNLIMITED")):
        return AddInlineFunction(callee, compileState, line)

    return False


def AddInlineFunction(callee, compileState, line):
    leftMotorControl = "%81"
    rightMotorControl = "%31"
    motorStop = edpy_values.constants["Ed.MOTOR_STOP_CODE"]
    motorForward = edpy_values.constants["Ed.MOTOR_FOR_CODE"]
    motorBackward = edpy_values.constants["Ed.MOTOR_BACK_CODE"]

    if (VERBOSE):
        compileState.AddStatement("# Inline function for {}:{}".format(callee, line))

    direction = line.args[0].constant

    speed = line.args[1].constant
    if (speed > 10):
        speed = 10
    elif speed < 0:
        speed = 0

    if (callee == "Ed.Drive_INLINE_UNLIMITED"):
        leftCtrl = motorStop
        rightCtrl = motorStop

        if (direction == edpy_values.constants["Ed.FORWARD"]):
            leftCtrl = motorForward | speed
            rightCtrl = motorForward | speed
        elif (direction == edpy_values.constants["Ed.BACKWARD"]):
            leftCtrl = motorBackward | speed
            rightCtrl = motorBackward | speed
        elif (direction == edpy_values.constants["Ed.FORWARD_RIGHT"]):
            leftCtrl = motorForward | speed
        elif (direction == edpy_values.constants["Ed.BACKWARD_RIGHT"]):
            leftCtrl = motorBackward | speed
        elif (direction == edpy_values.constants["Ed.FORWARD_LEFT"]):
            rightCtrl = motorForward | speed
        elif (direction == edpy_values.constants["Ed.BACKWARD_LEFT"]):
            rightCtrl = motorBackward | speed
        elif (direction == edpy_values.constants["Ed.SPIN_RIGHT"]):
            leftCtrl = motorForward | speed
            rightCtrl = motorBackward | speed
        elif (direction == edpy_values.constants["Ed.SPIN_LEFT"]):
            leftCtrl = motorBackward | speed
            rightCtrl = motorForward | speed

        compileState.AddStatement("movb ${} {}".format(leftCtrl, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(rightCtrl, rightMotorControl))

        return True

    elif (callee == "Ed.DriveLeftMotor_INLINE_UNLIMITED"):
        leftCtrl = motorStop
        if (direction == edpy_values.constants["Ed.FORWARD"]):
            leftCtrl = motorForward | speed
        elif (direction == edpy_values.constants["Ed.BACKWARD"]):
            leftCtrl = motorBackward | speed

        compileState.AddStatement("movb ${} {}".format(leftCtrl, leftMotorControl))
        return True

    elif (callee == "Ed.DriveRightMotor_INLINE_UNLIMITED"):
        rightCtrl = motorStop
        if (direction == edpy_values.constants["Ed.FORWARD"]):
            rightCtrl = motorForward | speed
        elif (direction == edpy_values.constants["Ed.BACKWARD"]):
            rightCtrl = motorBackward | speed

        compileState.AddStatement("movb ${} {}".format(rightCtrl, rightMotorControl))
        return True

    return False


def AddSimpleDriveInlineFunction(callee, compileState, line):
    leftMotorControl = "%81"
    leftMotorDistance = "%82"
    rightMotorControl = "%31"
    rightMotorDistance = "%32"
    motorStop = 0xc0
    motorForward = 0x81
    motorBackward = 0x41

    if (VERBOSE):
        compileState.AddStatement("# Inline function for {}:{}".format(callee, line))

    if (callee == "Ed.SimpleDriveStop"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorStop, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorStop, rightMotorControl))
        # M<ight not have to do the clearing of the distance depending on how the
        # firmware handles non-zero distances when not doing a distance limited drive.
        compileState.AddStatement("movw $0 {}".format(leftMotorDistance))
        compileState.AddStatement("movw $0 {}".format(rightMotorDistance))
        return True

    elif (callee == "Ed.SimpleDriveForward"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorForward, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorForward, rightMotorControl))
        return True

    elif (callee == "Ed.SimpleDriveForwardRight"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorForward, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorStop, rightMotorControl))
        return True

    elif (callee == "Ed.SimpleDriveForwardLeft"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorStop, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorForward, rightMotorControl))
        return True

    elif (callee == "Ed.SimpleDriveBackward"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorBackward, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorBackward, rightMotorControl))
        return True

    elif (callee == "Ed.SimpleDriveBackwardRight"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorBackward, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorStop, rightMotorControl))
        return True

    elif (callee == "Ed.SimpleDriveBackwardLeft"):
        compileState.AddStatement("# Inline version of {} on line:{}".format(callee, line))
        compileState.AddStatement("movb ${} {}".format(motorStop, leftMotorControl))
        compileState.AddStatement("movb ${} {}".format(motorBackward, rightMotorControl))
        return True

    return False


def CreateModRegHex(mod, reg):
    if ((not mod.IsIntConst()) or (not reg.IsIntConst())):
        CompileError_NO_RET(12, "Can only use constants when reading/writing to module regs")

    if ((mod.constant < 0) or (mod.constant > 15)):
        CompileError_NO_RET(13, "Module constant is out of range")

    if ((reg.constant < 0) or (reg.constant > 15)):
        CompileError_NO_RET(14, "Register constant is out of range")

    return "%02x" % ((mod.constant << 4) | (reg.constant),)


def LoadWordVariableIntoAcc(value, functionName, compileState, stackOffset=0):
    (vType, vName, vOffset, info) = GetVariableInfo(functionName, value, compileState)
    if (vType == "L"):
        # on the stack, get it from there
        compileState.AddStatement("straw ${:d}".format(vOffset + stackOffset))
    elif (vType == "G"):
        # a simple global
        compileState.AddStatement("movw @{} %_cpu:acc".format(vName))
    elif (vType == "GC"):
        # a slice with constant index - add the offset to the value of the name
        # (the name contains the address of the start of the slice)
        compileState.AddStatement("movw @{} %_cpu:acc".format(vName))
        if (info != 0):
            compileState.AddStatement("addw ${}".format(info))
        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_16BIT))
        compileState.AddStatement("movw %_index:16b1window %_cpu:acc")
    elif (vType == "GV"):
        # a slice with a variable index - first the variable index
        iType, iName, iOffset = info
        if (iType == "L"):
            # on the stack, get it from there
            compileState.AddStatement("straw ${:d}".format(iOffset + stackOffset))
        else:  # 'G' only
            compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
        # now the value of the INDEX is in the ACC
        compileState.AddStatement("addw @{}".format(vName))
        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_16BIT))
        compileState.AddStatement("movw %_index:16b1window %_cpu:acc")
    elif (vType == "LC"):
        # a slice with constant index - add the offset to the reference on the stack
        # (the name contains the address of the start of the slice)
        compileState.AddStatement("straw ${:d}".format(vOffset + stackOffset))
        if (info != 0):
            compileState.AddStatement("addw ${}".format(info))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_16BIT))
        compileState.AddStatement("movw %_index:16b1window %_cpu:acc")
    elif (vType == "LV"):
        # a slice reference on the stack with a variable index
        iType, iName, iOffset = info
        if (iType == "L"):
            # on the stack, get it from there
            compileState.AddStatement("straw ${:d}".format(iOffset + stackOffset))
        else:  # 'G' only
            compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
        # now the value of the INDEX is in the ACC - must store it
        compileState.AddStatement("movw %_cpu:acc  @_CALC")

        # now get the base address
        compileState.AddStatement("straw ${:d}".format(vOffset + stackOffset))

        # compute the actual address
        compileState.AddStatement("addw @_CALC")

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_16BIT))
        compileState.AddStatement("movw %_index:16b1window %_cpu:acc")

    elif (vType == "LO"):
        # object data refering to a local object
        # print ("**", functionName, vType, vName, vOffset, info)

        if (not vName.startswith("self.")):
            CompileError_NO_RET()

        classInfo = functionName.partition('.')
        if (classInfo[0] not in compileState.classLayout):
            CompileError_NO_RET()
        # have function name so can find where self is
        if ("self" not in compileState.funVarLayout[functionName]):
            CompileError_NO_RET()
        # get address from object and add offset to it

        # self is on the stack, get it's value from there. That is the address of the object
        selfOffset = compileState.funVarLayout[functionName]["self"]
        compileState.AddStatement("straw ${:d}".format(selfOffset + stackOffset))

        # Add the object offset in to get the ADDRESS of the data
        if (vOffset > 0):
            compileState.AddStatement("addw ${:d}".format(vOffset))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_16BIT))
        compileState.AddStatement("movw %_index:16b1window %_cpu:acc")

    elif (vType == "GO"):
        # object data referring to a global object
        # print ("**", functionName, vType, vName, vOffset, info)

        # a simple global for the object
        compileState.AddStatement("movw @{} %_cpu:acc".format(vName))

        # Add the object offset in to get the ADDRESS of the data
        if (vOffset > 0):
            compileState.AddStatement("addw ${:d}".format(vOffset))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")

        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_16BIT))
        compileState.AddStatement("movw %_index:16b1window %_cpu:acc")

    else:
        CompileError_NO_RET(15, "Invalid word variable to load into ACC" + vType)


def StoreAccIntoWordVariable(variable, functionName, compileState, stackOffset=0):
    (vType, vName, vOffset, info) = GetVariableInfo(functionName, variable, compileState)
    if (vType == "L"):
        # on the stack, write it to there
        compileState.AddStatement("stwaw ${:d}".format(vOffset + stackOffset))
    elif (vType == "G"):
        # a simple global
        compileState.AddStatement("movw %_cpu:acc @{}".format(vName))
    elif (vType == "GC"):
        # store the acc in the window for the write
        compileState.AddStatement("movw %_cpu:acc %_index:16b1window")

        # a slice with constant index - add the offset to the value of the name
        # (the name contains the address of the start of the slice)
        compileState.AddStatement("movw @{} %_cpu:acc".format(vName))
        if (info != 0):
            compileState.AddStatement("addw ${}".format(info))
        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_16BIT))
    elif (vType == "GV"):
        # store the acc in the window
        compileState.AddStatement("movw %_cpu:acc %_index:16b1window")

        # a slice with a variable index - first the variable index
        iType, iName, iOffset = info
        if (iType == "L"):
            # on the stack, get it from there
            compileState.AddStatement("straw ${:d}".format(iOffset + stackOffset))
        else:  # 'G' only
            compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
        # now the value of the INDEX is in the ACC
        compileState.AddStatement("addw @{}".format(vName))
        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_16BIT))
    elif (vType == "LC"):
        # store the acc in the window
        compileState.AddStatement("movw %_cpu:acc %_index:16b1window")

        # a slice with constant index - add the offset to the reference on the stack
        # (the name contains the address of the start of the slice)
        compileState.AddStatement("straw ${:d}".format(vOffset + stackOffset))
        if (info != 0):
            compileState.AddStatement("addw ${}".format(info))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_16BIT))
    elif (vType == "LV"):
        # store the acc in the window
        compileState.AddStatement("movw %_cpu:acc %_index:16b1window")

        # a slice reference on the stack with a variable index
        iType, iName, iOffset = info
        if (iType == "L"):
            # on the stack, get it from there
            compileState.AddStatement("straw ${:d}".format(iOffset + stackOffset))
        else:  # 'G' only
            compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
        # now the value of the INDEX is in the ACC - must store it
        compileState.AddStatement("movw %_cpu:acc  @_CALC")

        # now get the base address
        compileState.AddStatement("straw ${:d}".format(vOffset + stackOffset))

        # compute the actual address
        compileState.AddStatement("addw @_CALC")

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_16BIT))

    elif (vType == "LO"):
        # object data local to this object
        # print ("**", functionName, vType, vName, vOffset, info)

        # store the acc in the window
        compileState.AddStatement("movw %_cpu:acc %_index:16b1window")

        if (not vName.startswith("self.")):
            CompileError_NO_RET()

        classInfo = functionName.partition('.')
        if (classInfo[0] not in compileState.classLayout):
            CompileError_NO_RET()
        # have function name so can find where self is
        if ("self" not in compileState.funVarLayout[functionName]):
            CompileError_NO_RET()
        # get address from object and add offset to it

        # self is on the stack, get it's value from there. That is the address of the object
        selfOffset = compileState.funVarLayout[functionName]["self"]
        compileState.AddStatement("straw ${:d}".format(selfOffset + stackOffset))

        # Add the object offset in to get the ADDRESS of the data
        if (vOffset > 0):
            compileState.AddStatement("addw ${:d}".format(vOffset))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")

        # trigger writing window through cursor
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_16BIT))

    elif (vType == "GO"):
        # object data referring to a global object
        # print ("**", functionName, vType, vName, vOffset, info)

        # store the acc in the window
        compileState.AddStatement("movw %_cpu:acc %_index:16b1window")

        # a simple global for the object
        compileState.AddStatement("movw @{} %_cpu:acc".format(vName))

        # Add the object offset in to get the ADDRESS of the data
        if (vOffset > 0):
            compileState.AddStatement("addw ${:d}".format(vOffset))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:16b1cursor")

        # trigger writing window through cursor
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_16BIT))

    else:
        CompileError_NO_RET(16, "Invalid word variable to store ACC into:" + str(vType))


def LoadByteVariableIntoAcc(value, functionName, compileState):
    if (value.IsStrConst()):
        # put it in the accumulator
        compileState.AddStatement("movb ${} %_cpu:acc".format(ord(value.strConst[0])))
    else:  # must be a slice of a tune string - so will be a byte_count - either GC or GV
        (vType, vName, vOffset, info) = GetVariableInfo(functionName, value, compileState)
        if (vType == "GC"):
            # a slice with constant index - add the offset to the value of the name
            # (the name contains the address of the start of the slice)
            compileState.AddStatement("movw @{} %_cpu:acc".format(vName))
            if (info != 0):
                compileState.AddStatement("addw ${}".format(info))
            compileState.AddStatement("convl")
            compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
            compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_8BIT))
            compileState.AddStatement("movb %_index:8b1window %_cpu:acc")
        elif (vType == "GV"):
            # a slice with a variable index - first the variable index
            iType, iName, iOffset = info
            if (iType == "L"):
                # on the stack, get it from there
                compileState.AddStatement("straw {:d}".format(iOffset))
            else:  # 'G' only
                compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
            # now the value of the INDEX is in the ACC
            compileState.AddStatement("addw @{}".format(vName))
            compileState.AddStatement("convl")
            compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
            compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_8BIT))
            compileState.AddStatement("movb %_index:8b1window %_cpu:acc")
        elif (vType == "LC"):
            # a slice with constant index - add the offset to the reference on the stack
            # (the name contains the address of the start of the slice)
            compileState.AddStatement("straw ${:d}".format(vOffset))
            if (info != 0):
                compileState.AddStatement("addw ${}".format(info))

            compileState.AddStatement("convl")
            compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
            compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_8BIT))
            compileState.AddStatement("movw %_index:8b1window %_cpu:acc")

        elif (vType == "LV"):
            # a slice reference on the stack with a variable index
            iType, iName, iOffset = info
            if (iType == "L"):
                # on the stack, get it from there
                compileState.AddStatement("straw ${:d}".format(iOffset))
            else:  # 'G' only
                compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
            # now the value of the INDEX is in the ACC - must store it
            compileState.AddStatement("movw %_cpu:acc  @_CALC")

            # now get the base address
            compileState.AddStatement("straw ${:d}".format(vOffset))

            # compute the actual address
            compileState.AddStatement("addw @_CALC")

            compileState.AddStatement("convl")
            compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
            # trigger reading for cursor into window
            compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_READ_8BIT))
            compileState.AddStatement("movw %_index:8b1window %_cpu:acc")

        else:
            CompileError_NO_RET(17, "Invalid byte variable to load into ACC" + vType)


def StoreAccIntoByteVariable(variable, functionName, compileState):
    (vType, vName, vOffset, info) = GetVariableInfo(functionName, variable, compileState)
    if (vType == "L"):
        # on the stack, write it to there
        compileState.AddStatement("stwab ${:d}".format(vOffset))
    elif (vType == "G"):
        # a simple global
        compileState.AddStatement("movb %_cpu:acc @{}".format(vName))
    elif (vType == "GC"):
        # store the acc in the window for the write
        compileState.AddStatement("movb %_cpu:acc %_index:8b1window")

        # a slice with constant index - add the offset to the value of the name
        # (the name contains the address of the start of the slice)
        compileState.AddStatement("movw @{} %_cpu:acc".format(vName))
        if (info != 0):
            compileState.AddStatement("addw ${}".format(info))
        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_8BIT))
    elif (vType == "GV"):
        # store the acc in the window
        compileState.AddStatement("movb %_cpu:acc %_index:8b1window")

        # a slice with a variable index - first the variable index
        iType, iName, iOffset = info
        if (iType == "L"):
            # on the stack, get it from there
            compileState.AddStatement("straw ${:d}".format(iOffset))
        else:  # 'G' only
            compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
        # now the value of the INDEX is in the ACC
        compileState.AddStatement("addw @{}".format(vName))
        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_8BIT))
    elif (vType == "LC"):
        # store the acc in the window
        compileState.AddStatement("movb %_cpu:acc %_index:8b1window")

        # a slice with constant index - add the offset to the reference on the stack
        # (the name contains the address of the start of the slice)
        compileState.AddStatement("straw ${:d}".format(vOffset))
        if (info != 0):
            compileState.AddStatement("addw ${}".format(info))

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_8BIT))
    elif (vType == "LV"):
        # store the acc in the window
        compileState.AddStatement("movb %_cpu:acc %_index:8b1window")

        # a slice reference on the stack with a variable index
        iType, iName, iOffset = info
        if (iType == "L"):
            # on the stack, get it from there
            compileState.AddStatement("straw ${:d}".format(iOffset))
        else:  # 'G' only
            compileState.AddStatement("movw @{} %_cpu:acc".format(iName))
        # now the value of the INDEX is in the ACC - must store it
        compileState.AddStatement("movw %_cpu:acc  @_CALC")

        # now get the base address
        compileState.AddStatement("straw ${:d}".format(vOffset))

        # compute the actual address
        compileState.AddStatement("addw @_CALC")

        compileState.AddStatement("convl")
        compileState.AddStatement("movb %_cpu:acc %_index:8b1cursor")
        # trigger reading for cursor into window
        compileState.AddStatement("bitset ${} %_index:action".format(CONTROL_INDEX_WRITE_8BIT))

    else:
        CompileError_NO_RET(18, "Invalid byte variable to store ACC into:" + str(vType))


def CompileCall(programIR, functionName, line, compileState):
    """Setup stack for the callee, copy values to the args, call the function,
       then remove the stack and move the return to the target (if needed)."""

    callee = line.funcName

    # First see if it's a special. If so then it's already handled
    if (HandleSpecialCall(programIR, functionName, callee, line, compileState)):
        return

    if (VERBOSE):
        compileState.AddStatement("# CALL:" + str(line))

    calleeDepth = SetupFunctionStack(compileState, callee)
    # copy the args over -- sizes must match
    index = 0
    while index < len(line.args):
        vFrom = line.args[index]
        offset = compileState.funArgLayout[callee][index][1]
        # print(index, vFrom, offset)

        if (vFrom.IsIntConst()):
            compileState.AddStatement("movw ${} %_cpu:acc".format(vFrom.constant))
            compileState.AddStatement("stwaw ${}".format(offset))
        elif (vFrom.IsStrConst()):
            # must be a single character
            if (len(vFrom.strConst) != 1):
                CompileError_NO_RET(19, "String constant should have length of 1" + str(vFrom))
            else:
                compileState.AddStatement("movw ${} %_cpu:acc".format(vFrom.constant))
                compileState.AddStatement("stwaw ${}".format(offset))
        elif (vFrom.IsConstant()):
            CompileError_NO_RET(20, "Should not be a str/list constant here" + str(vFrom))
        else:
            # a variable of some
            LoadWordVariableIntoAcc(vFrom, functionName, compileState, calleeDepth)
            compileState.AddStatement("stwaw ${}".format(offset))
        index += 1

    # call the function
    compileState.AddStatement("suba {}".format(MakeFunctionLabel(callee)))

    # Get the return value
    if ((line.target is not None) and compileState.funcReturnsValue[callee]):
        compileState.AddStatement("straw ${}".format(0))
        StoreAccIntoWordVariable(line.target, functionName, compileState, calleeDepth)

    # remove the stack
    TakeDownFunctionStack(compileState, callee)


def CompileReturn(programIR, functionName, line, compileState):
    # Return, optionally with a value in the ACC
    if (VERBOSE):
        compileState.AddStatement("# RETURN:" + str(line))

    if (not line.IsVoidReturn()):
        if (line.returnValue.IsIntConst()):
            compileState.AddStatement("movw ${} %_cpu:acc".format(line.returnValue.constant))
        else:
            LoadWordVariableIntoAcc(line.returnValue, functionName, compileState)
        # move onto the stack to return to the caller
        # TODO what offset should be used
        compileState.AddStatement("stwaw ${}".format(3))

    compileState.AddStatement("ret")


def MakeControlLabel(num, op, type):
    # return (":_Control_{:d}_{}_{}".format(num, op, type))
    return (":_Control_{:d}_{}".format(num, type))


def CompileControlMarker(programIR, functionName, line, compileState):
    if (VERBOSE):
        compileState.AddStatement("# CTRL_MARKER:" + str(line))

    if (line.name in  ("While", "For") and line.end == "end"):
        compileState.AddStatement("bra {}".format(MakeControlLabel(line.num, line.name, "start")))

    if (line.end == "else"):
        # route code around the else
        compileState.AddStatement("bra {}".format(MakeControlLabel(line.num, line.name, "end")))

    elif (line.end == "end"):
        elseLabel = MakeControlLabel(line.num, line.name, "else")
        if (elseLabel not in compileState.controlLabels):
            compileState.RecordControlLabel(elseLabel)
            compileState.AddStatement(elseLabel)

    newLabel = MakeControlLabel(line.num, line.name, line.end)
    compileState.RecordControlLabel(newLabel)
    compileState.AddStatement(newLabel)


def CompileForControl(programIR, functionName, line, compileState):
    if (VERBOSE):
        compileState.AddStatement("# FOR_CTRL:" + str(line))

    if (line.IsArray()):
        # are we still in the array bounds?
        (vType, vName, vOffset, info) = GetVariableInfo(functionName, line.arrayValue, compileState)
        # know that the line.arrayValue is an indexed slice. And the index is a temp
        # Get the value of the temp
        if (vType == "GV"):
            compileState.AddStatement("straw ${:d}".format(info[2]))  # value of the index
            compileState.AddStatement("cmpw ${}".format(vOffset))      # vOffset is size for Globals
        else:  # must be "LV" - so size must be computed
            compileState.AddStatement("straw ${:d}".format(vOffset))  # get the base
            compileState.AddStatement("shrw $8")        # find the size of the slice
            compileState.AddStatement("movw %_cpu:acc @_CALC")
            compileState.AddStatement("straw ${:d}".format(info[2]))  # get the value of the index
            compileState.AddStatement("cmpw @_CALC")

        # Check if RHS (max) is LessOrEqual to LHS (ACC, index), then goto end
        # Check if (current_index) >= (limit), if so then goto end
        compileState.AddStatement("brle {}".format(MakeControlLabel(line.num, "For", "end")))

    else:  # Constant limit - is our variable below the constant?
        # know that the current variable is a temp, limit may be anything
        # So: load limit into ACC, store in window, load variable into ACC, cmp them

        if (line.constantLimit.IsIntConst()):
            compileState.AddStatement("movw ${} %_cpu:acc".format(line.constantLimit.constant))
        else:
            LoadWordVariableIntoAcc(line.constantLimit, functionName, compileState)

        (vType, vName, vOffset, info) = GetVariableInfo(functionName, line.currentValue, compileState)

        compileState.AddStatement("movw %_cpu:acc @_CALC")
        compileState.AddStatement("straw ${:d}".format(vOffset))
        compileState.AddStatement("cmpw @_CALC")

        # limit is in @_CALC, current value is in ACC. So
        # check if RHS (limit) is LessOrEqual to LHS (ACC, index), then goto end
        compileState.AddStatement("brle {}".format(MakeControlLabel(line.num, "For", "end")))


def CompileLoopControl(programIR, functionName, line, compileState):
    if (VERBOSE):
        compileState.AddStatement("# LOOP_CTRL:" + str(line))

    # see if line.test evaluates to 0
    if (line.test.IsIntConst()):
        compileState.AddStatement("movw ${} %_cpu:acc".format(line.test.constant))
    else:
        LoadWordVariableIntoAcc(line.test, functionName, compileState)
    compileState.AddStatement("brz {}".format(MakeControlLabel(line.num, line.name, "else")))


def CompileLoopModifier(programIR, functionName, line, compileState):
    if (VERBOSE):
        compileState.AddStatement("# LOOP_MOD:" + str(line))

    if (line.name == "Pass"):
        pass  # nothing to do :)
    elif (line.name == "Break"):
        compileState.AddStatement("bra {}".format(MakeControlLabel(line.num, line.name, "else")))
    elif (line.name == "Continue"):
        compileState.AddStatement("bra {}".format(MakeControlLabel(line.num, line.name, "start")))
    else:
        CompileError_NO_RET(22, "Invalid name for loop modifier" + str(line))


def CompileBoolCheck(programIR, functionName, line, compileState):
    if (VERBOSE):
        compileState.AddStatement("# BOOL_CHK:" + str(line))

    # value has a 0 or non-zero value. Load into acc
    if (line.value.IsIntConst()):
        compileState.AddStatement("movw ${} %_cpu:acc".format(line.value.constant))
    else:
        LoadWordVariableIntoAcc(line.value, functionName, compileState)

    # Is this DONE?
    if (line.op == "Done"):
        StoreAccIntoWordVariable(line.target, functionName, compileState)

    else:
        continueProcessingLabel = compileState.NextInternalLabel()

        # the E flag in flags will be set on moving value into ACC

        # Fix for a mistake in Or processing. This was found (and a correct fix suggested)
        # by Ales Jerabek <ales.jerabek@gmail.com> -- Thanks!

        if (line.op == "Or"):
            # FOR OR if ZERO, then we have to keep checking!
            compileState.AddStatement("brz {}".format(continueProcessingLabel))

            # The answer here is TRUE -- move that into the target
            compileState.AddStatement("movw $1 %_cpu:acc")
            StoreAccIntoWordVariable(line.target, functionName, compileState)
        else:
            # FOR AND if NON-ZERO, then we have to keep checking!
            compileState.AddStatement("brnz {}".format(continueProcessingLabel))

            # The answer here is FALSE -- move that into the target
            compileState.AddStatement("movw $0 %_cpu:acc")
            StoreAccIntoWordVariable(line.target, functionName, compileState)

        # short curcuit the rest of the processing
        compileState.AddStatement("bra {}".format(MakeControlLabel(line.num, line.op, "end")))

        compileState.AddStatement("{}".format(continueProcessingLabel))


def CompileFunction(programIR, functionName, compileState):
    """Compile a function and update the compilation state """
    function = programIR.Function[functionName]
    compileState.AddStatement("")
    if (VERBOSE):
        compileState.AddStatement("# FUNCTION:" + functionName)
    compileState.AddStatement(MakeFunctionLabel(functionName))

    # If __main__ then need to set the tempo
    if (functionName == "__main__"):
        SetTempoAtStart(programIR.EdVariables["Ed.Tempo"], compileState)

    # lineNo = 0
    for line in function.body:
        if (line.kind == "Marker"):
            # lineNo = line.line
            continue

        elif (line.kind == "UAssign"):
            CompileUassign(programIR, functionName, line, compileState)

        elif (line.kind == "BAssign"):
            CompileBassign(programIR, functionName, line, compileState)

        elif (line.kind == "Call"):
            CompileCall(programIR, functionName, line, compileState)

        elif (line.kind == "Return"):
            CompileReturn(programIR, functionName, line, compileState)

        elif (line.kind == "ControlMarker"):
            CompileControlMarker(programIR, functionName, line, compileState)

        elif (line.kind == "ForControl"):
            CompileForControl(programIR, functionName, line, compileState)

        elif (line.kind == "LoopControl"):
            CompileLoopControl(programIR, functionName, line, compileState)

        elif (line.kind == "LoopModifier"):
            CompileLoopModifier(programIR, functionName, line, compileState)

        elif (line.kind == "BoolCheck"):
            CompileBoolCheck(programIR, functionName, line, compileState)

        else:
          print("NOT HANDLED:", line)

    if (functionName == "__main__"):
        compileState.AddStatement("stop")
    else:
        compileState.AddStatement("ret")

    compileState.AddStatement(MakeFunctionEndLabel(functionName))

    return 0


def MakeFunctionLabel(functionName):
    return "::_fun_{}".format(functionName)


def MakeFunctionEndLabel(functionName):
    return ":_end_{}".format(functionName)


def MakeTempName(tempNumber):
    return "temp-{:d}".format(tempNumber)


def SetupFunctionStack(compileState, functionName):
    stackSize = compileState.funStackSize[functionName]
    if (stackSize > 0):
        compileState.AddStatement("stinc ${}".format(stackSize))
    return stackSize


def TakeDownFunctionStack(compileState, functionName):
    stackSize = compileState.funStackSize[functionName]
    if (stackSize > 0):
        compileState.AddStatement("stdec ${}".format(stackSize))


def FindFirstAssignmentToGlobal(programIR, name, typeInfo):
    """Look through the program source to find out what is assigned
       to a global variable"""
    main = programIR.Function["__main__"]

    for line in main.body:
        if ((line.kind == "Call") and
            (line.GetTarget() and (line.GetTarget().name == name))):
            # found it!
            if (typeInfo == 'L'):
                if (line.funcName == "Ed.List1"):
                    return (line.args[0], None)
                elif (line.funcName == "Ed.List2"):
                    if (line.args[1].IsListConst):
                        return (line.args[0], line.args[1])
                    else:
                        CompileError_NO_RET(23, "FirstAssignment search for type:{} found strange call arg:{}".
                                        format(typeInfo, line.args[1].Name))
                else:
                    CompileError_NO_RET(24, "FirstAssignment search for type:{} found strange call:{}".
                                    format(typeInfo, line.funcName))

            elif (typeInfo == 'T'):
                if (line.funcName == "Ed.TuneString1"):
                    return (line.args[0], None)
                elif (line.funcName == "Ed.TuneString2"):
                    if (line.args[1].IsStrConst):
                        return (line.args[0], line.args[1])
                    else:
                        CompileError_NO_RET(25, "FirstAssignment search for type:{} found strange call arg:{}".
                                        format(typeInfo, line.args[1].Name))

                else:
                    CompileError_NO_RET(26, "FirstAssignment search for type:{} found strange call:{}".
                                    format(typeInfo, line.funcName))

            elif (typeInfo == 'O'):
                if (line.funcName == "Ed.CreateObject"):
                    # need to return the name of the object so that space for it can be allocated
                    return (line.args[0], None)
                else:
                    CompileError_NO_RET(27, "FirstAssignment search for type:{} found strange call:{}".
                                    format(typeInfo, line.funcName))

    for line in main.body:
        if ((line.kind == "UAssign") and (line.GetValues()) and
            (line.GetTarget() and (line.GetTarget().name == name))):
            # found it -- basically it's an alias
            return FindFirstAssignmentToGlobal(programIR, line.operand.name, typeInfo)

    CompileError_NO_RET(28, "FirstAssignment search for name:{} failed!".format(name))


def LayoutClasses(programIR, compileState):
    for func in programIR.Function:
        className, sep, method = func.partition('.')
        if (method == "__init__"):
            # found a class
            function = programIR.Function[func]
            words = 0
            layout = {}
            types = {}
            for v in function.localVar:
                if (v == "self"):
                    continue
                if (v.startswith("self.")):
                    name = v[5:]
                    layout[v] = words
                    types[v] = function.localVar[v]
                    words += 1

            compileState.classLayout[className] = (words, layout, types)
            io.Out.DebugRaw("LayoutClasses - Class {} needs {} words".format(className, words))


def LayoutFunctionVars(programIR, compileState):
    for func in programIR.Function:

        if ((func in SPECIALLY_HANDLED_FUNCTIONS) or (func == "__main__")):
            return_frame_offset = 0
        else:
            return_frame_offset = RETURN_FRAME_OFFSET

        function = programIR.Function[func]
        argLayout = []
        varLayout = {}
        returnsValue = False
        offset = 0

        if (programIR.Function[func].returnsValue):
            returnsValue = True

        className, sep, method = func.partition('.')
        if ((method is not None) and (className in compileState.classLayout)):
            classData = compileState.classLayout[className][1]
        else:
            classData = None

        for a in function.args:
            # print("Arg:", func, a)
            argLayout.append((a, offset))
            varLayout[a] = offset + return_frame_offset
            offset += 1

        for v in function.localVar:
            if ((classData is not None) and
                (v in classData)):
                continue

            if (v not in function.args):
                if (type(v) is int):
                    varLayout[MakeTempName(v)] = offset + return_frame_offset
                else:
                    obj, sep, member = v.partition('.')
                    if (member != ""):
                        continue
                    varLayout[v] = offset + return_frame_offset
                offset += 1

        t = 0
        while (t < function.maxSimpleTemps):
            varLayout[MakeTempName(t)] = offset + return_frame_offset
            offset += 1
            t += 1

        # Is there a return, but nothing on the stack? Then make sure the stack
        # has 1 element for the return
        if ((offset == 0) and function.returnsValue):
            offset = 1

        compileState.funArgLayout[func] = argLayout
        compileState.funVarLayout[func] = varLayout
        compileState.funVarInfo[func] = function.localVar
        compileState.funStackSize[func] = offset
        compileState.funGlbAccess[func] = function.globalAccess
        compileState.funcReturnsValue[func] = returnsValue


def SetupGlobalVars(programIR, compileState):
    """Add the global vars into the assembler listing, and
       create a dictionary with the offsets into the byte and
       word data spaces"""

    # a Calculation variable
    compileState.AddStatement("DATW {} {} 1".format("_CALC", 0))
    compileState.wordsUsed = 1
    compileState.bytesUsed = 0

    for g in programIR.globalVar:
        # print("Global:",g)
        typeInfo, extra = programIR.globalVar[g]
        internalName = g + "-object"
        sizeName = g + "-size"

        if (typeInfo == 'I'):
            # Simple Integer
            compileState.globalVar[g] = (compileState.wordsUsed, typeInfo, extra)

            if (g in edpy_values.variables):
                # pass
                # Don't need these variables
                compileState.AddStatement("DATW {} {} 1 {:d}".format(g, compileState.wordsUsed, programIR.EdVariables[g]))
            else:
                compileState.AddStatement("DATW {} {} 1".format(g, compileState.wordsUsed))
            compileState.wordData[g] = (compileState.wordsUsed, 1)
            compileState.wordsUsed += 1


        elif (typeInfo == 'T'):
            # TuneString reference -- set-up the area to hold the TuneString
            # The calls to Ed.TuneString1 or Ed.TuneString2 will be removed from the program
            (sizeValue, init) = FindFirstAssignmentToGlobal(programIR, g, typeInfo)
            size = sizeValue.constant
            start = compileState.bytesUsed

            if (init is not None):
                compileState.AddStatement('DATB {}, {}, {}, "{}"'.format(internalName, start, size, init.strConst))
            else:
                compileState.AddStatement('DATB {}, {}, {}'.format(internalName, start, size))
            compileState.bytesUsed += size

            # Now the variable to hold the reference
            compileState.globalVar[g] = (compileState.wordsUsed, typeInfo, extra)

            compileState.AddStatement("DATW {}, {}, 1, {}".format(g, compileState.wordsUsed,
                                                                  (start + (size << 8))))
            compileState.wordData[g] = (compileState.wordsUsed, 1)
            compileState.wordsUsed += 1

            compileState.objectSize[g] = size

        elif (typeInfo == 'L'):
            # List reference -- set-up the area to hold the List
            # The calls to Ed.List1 or Ed.List2 will be removed from the program
            (sizeValue, init) = FindFirstAssignmentToGlobal(programIR, g, typeInfo)
            size = sizeValue.constant
            start = compileState.wordsUsed

            if (init is not None):
                values = ""
                for v in init.listConst:
                    values += "%d, " % (v,)
                if (len(values) > 2):
                    values = values[:-2]
                compileState.AddStatement('DATW {}, {}, {}, {}'.format(internalName, start, size,
                                                                       values))

            else:
                compileState.AddStatement('DATW {}, {}, {}'.format(internalName, start, size))
            compileState.wordsUsed += size

            # Now the variable to hold the reference
            compileState.globalVar[g] = (compileState.wordsUsed, typeInfo, extra)

            compileState.AddStatement("DATW {}, {}, 1, {}".format(g, compileState.wordsUsed,
                                                                  (start + (size << 8))))
            compileState.wordData[g] = (compileState.wordsUsed, 1)
            compileState.wordsUsed += 1

            compileState.objectSize[g] = size

        elif (typeInfo == 'O'):
            # Object reference -- set-up the area to hold the object
            # The calls to Ed.CreateObject will be removed from the program
            (classNameValue, init) = FindFirstAssignmentToGlobal(programIR, g, typeInfo)
            className = classNameValue.strConst

            if (className in compileState.classLayout):
                size = compileState.classLayout[className][0]
            else:
                compileState.classLayout[className] = (0, None)
                size = 1

            start = compileState.wordsUsed
            compileState.AddStatement('DATW {}, {}, {}'.format(internalName + "." + className, start, size))
            compileState.wordsUsed += size

            # Now the variable to hold the reference
            compileState.globalVar[g] = (compileState.wordsUsed, typeInfo, extra)

            compileState.AddStatement("DATW {}, {}, 1, {}".format(g, compileState.wordsUsed, start))
            compileState.wordData[g] = (compileState.wordsUsed, 1)
            compileState.wordsUsed += 1

            compileState.objectSize[g] = size

        else:
            # Can't be an 'S' or 'V' as they are only used in a call
            CompileError_NO_RET(29, "Impossible typeInfo - {}".format(typeInfo))

    return 0

    #  "Ed.EVENT_TIMER_FINISHED": 0,
    # "Ed.EVENT_REMOTE_CODE": 1,
    # "Ed.EVENT_IR_DATA": 2,
    # "Ed.EVENT_CLAP_DETECTED": 3,
    # "Ed.EVENT_OBSTACLE_ANY": 4,
    # "Ed.EVENT_OBSTACLE_LEFT": 5,
    # "Ed.EVENT_OBSTACLE_RIGHT": 6,
    # "Ed.EVENT_OBSTACLE_AHEAD": 7,
    # "Ed.EVENT_DRIVE_STRAIN": 8,
    # "Ed.EVENT_KEYPAD_TRIANGLE": 9,
    # "Ed.EVENT_KEYPAD_ROUND": 10,
    # "Ed.EVENT_LINE_TRACKER_ON_WHITE": 11,
    # "Ed.EVENT_LINE_TRACKER_ON_BLACK": 12,
    # "Ed.EVENT_LINE_TRACKER_SURFACE_CHANGE": 13,
    # "Ed.EVENT_TUNE_FINISHED": 14,


def StartEventCall(compileState, module, bit, overrideMask=None, overrideValue=None, leaveBitSet=False):
    mask = 1 << int(bit)
    value = mask

    if (overrideMask is not None):
        mask = overrideMask

    if (overrideValue is not None):
        value = overrideValue

    compileState.AddStatement("BEGIN EVENT %{}:status, {:d}, {:d}".format(module, mask, value))
    if (not leaveBitSet):
        compileState.AddStatement("bitclr ${:d} %{}:status".format(int(bit), module))


def FinishEventCall(compileState, label, stackElements):
    # note that nothing is returned from an event call
    compileState.AddStatement("pushw @_CALC")
    if (stackElements > 0):
        compileState.AddStatement("stinc ${:d}".format(stackElements))
    compileState.AddStatement("suba " + label)
    if (stackElements > 0):
        compileState.AddStatement("stdec ${:d}".format(stackElements))
    compileState.AddStatement("popw @_CALC")
    compileState.AddStatement("stop")
    compileState.AddStatement("END EVENT")


def AddInEventHandlerWrappers(compileState):
    # print("EventHandlers", compileState.eventHandler)
    for code in compileState.eventHandler:
        funName = compileState.eventHandler[code]
        funLabel = "::_fun_" + funName
        stackElements = compileState.funStackSize[funName]
        if (code == edpy_values.constants["Ed.EVENT_TIMER_FINISHED"]):
            StartEventCall(compileState, "_timers", 0)

        elif (code == edpy_values.constants["Ed.EVENT_REMOTE_CODE"]):
            # Don't clear this bit as the Ed_ReadRemote() will clear it
            # If they don't clear it then this routine will be called immediately!
            StartEventCall(compileState, "IR_RECEIVER1", 1, leaveBitSet=True)

        elif (code == edpy_values.constants["Ed.EVENT_IR_DATA"]):
            StartEventCall(compileState, "IR_RECEIVER1", 0)

        elif (code == edpy_values.constants["Ed.EVENT_CLAP_DETECTED"]):
            StartEventCall(compileState, "SOUNDER1", 2)

        elif (code == edpy_values.constants["Ed.EVENT_OBSTACLE_ANY"]):
            StartEventCall(compileState, "IR_RECEIVER1", 6)

        elif (code == edpy_values.constants["Ed.EVENT_OBSTACLE_LEFT"]):
            StartEventCall(compileState, "IR_RECEIVER1", 5)

        elif (code == edpy_values.constants["Ed.EVENT_OBSTACLE_RIGHT"]):
            StartEventCall(compileState, "IR_RECEIVER1", 3)

        elif (code == edpy_values.constants["Ed.EVENT_OBSTACLE_AHEAD"]):
            StartEventCall(compileState, "IR_RECEIVER1", 4)

        elif (code == edpy_values.constants["Ed.EVENT_DRIVE_STRAIN"]):
            StartEventCall(compileState, "Left_Motor", 0)
            FinishEventCall(compileState, funLabel, stackElements)
            StartEventCall(compileState, "Right_Motor", 0)

        elif (code == edpy_values.constants["Ed.EVENT_KEYPAD_TRIANGLE"]):
            StartEventCall(compileState, "_devices", 0)

        elif (code == edpy_values.constants["Ed.EVENT_KEYPAD_ROUND"]):
            StartEventCall(compileState, "_devices", 2)

        elif (code == edpy_values.constants["Ed.EVENT_LINE_TRACKER_ON_WHITE"]):
            StartEventCall(compileState, "LINE_TRACKER1", 1, overrideMask=3, overrideValue=3)

        elif (code == edpy_values.constants["Ed.EVENT_LINE_TRACKER_ON_BLACK"]):
            StartEventCall(compileState, "LINE_TRACKER1", 1, overrideMask=3, overrideValue=2)

        elif (code == edpy_values.constants["Ed.EVENT_LINE_TRACKER_SURFACE_CHANGE"]):
            StartEventCall(compileState, "LINE_TRACKER1", 1)

        elif (code == edpy_values.constants["Ed.EVENT_TUNE_FINISHED"]):
            StartEventCall(compileState, "SOUNDER1", 0)

        else:
            CompileError_NO_RET(30, "Invalid Event code {}".format(code))

        FinishEventCall(compileState, funLabel, stackElements)


def CompileProgram(programIR, compileState, doOpts):
    """Process the functions starting from main, building up
       the compileState."""

    bad = False

    compileState.AddStatement(edpy_values.versionStatement)

    LayoutClasses(programIR, compileState)
    LayoutFunctionVars(programIR, compileState)

    for ms in edpy_values.moduleStatements:
        compileState.AddStatement(ms)

    compileState.AddStatement("BEGIN MAIN")

    SetupGlobalVars(programIR, compileState)

    # setup stack for __main__. All other stacks are setup/taken_down by the caller
    depth = SetupFunctionStack(compileState, "__main__")

    if (CompileFunction(programIR, "__main__", compileState) != 0):
        bad = True

    # all the functions
    for fun in programIR.Function:
        if (bad):
            break

        if (fun == "__main__"):
            continue

        if (fun in SPECIALLY_HANDLED_FUNCTIONS):
            continue

        if (CompileFunction(programIR, fun, compileState) != 0):
            bad = True


    compileState.AddStatement("stop")
    compileState.AddStatement("END MAIN")

    AddInEventHandlerWrappers(compileState)

    compileState.AddStatement("FINISH")
    # print("Dumping compileState AFTER functions")
    # compileState.Dump()
    # print(programIR.globalVar)

    if (doOpts):
        compileState.Optimise()

    return (bad is not False)


def Compile(programIR, doOpts):
    """Take a program.Program object and produce an assembler output file"""

    io.Out.Top(io.TS.CMP_START, "Starting compiler passes")
    # programIR.Dump()

    rtc = 0
    compileState = CompileState()

    try:
        rtc = CompileProgram(programIR, compileState, doOpts)

    except program.EdPyError:
        rtc = 1
        # compileState.Dump()
        if (io.Out.IsReRaiseSet()):
            raise

    except:
        io.Out.Error(io.TS.CMP_INTERNAL_ERROR,
                     "file::: Compiler internal error {0}", 702)
        if (io.Out.IsReRaiseSet()):
            raise

    if (io.Out.GetInfoDumpMask() & io.DUMP.COMPILER):
        io.Out.DebugRaw("\nDump of internal representation after COMPILATION (rtc:{0}):".format(rtc))
        compileState.Dump()
        io.Out.DebugRaw("\n")

    if (rtc != 0):
        io.Out.DebugRaw("WARNING - COMPILER finished with an ERROR!!!\n")

    return rtc, compileState.statements

# Only to be used as a module
if __name__ == '__main__':
    io.Out.FatalRaw("This file is a module and can not be run as a script!")
