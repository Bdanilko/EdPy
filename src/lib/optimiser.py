#!/usr/bin/env python2
# * **************************************************************** **
# File: optimiser.py
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

""" Module to optimise the IR structure, before it's passed to the compiler"""

from __future__ import print_function
from __future__ import absolute_import

# from . import util
from . import io
from . import program
from . import edpy_values

# ############ utility functions ########################################


def UpdateRewrite(rewriteList, target, newValue):
    found = False
    for i in range(len(rewriteList)):
        if (rewriteList[i][0] == target):
            found = True
            rewriteList[i] = (target, newValue)
            break

    if not found:
        rewriteList.append((target, newValue))


def DeleteRewrite(rewriteList, target):
    for i in range(len(rewriteList)):
        if (rewriteList[i][0] == target):
            del rewriteList[i]
            break


def GetRewriteValue(rewriteList, target):
    value = None
    for i in range(len(rewriteList)):
        if (rewriteList[i][0] == target):
            value = rewriteList[i][1]
            break

    return value


def ClearSimpleTemps(rewriteList):
    newList = []
    for i in range(len(rewriteList)):
        if (not IsSimpleTemp(rewriteList[i][0])):
            newList.append(rewriteList[i])
    return newList


def UAssignWithConstant(uassign, programIR, line):
    if (not uassign.operand.IsIntConst()):
        if (uassign.operation != "UAdd"):
            if (uassign.operand.IsStrConst()):
                io.Out.Error(io.TS.OPT_STRING_NOT_ALLOWED,
                             "file:{0}:: Syntax Error, String not allowed here", line)
                raise program.OptError
            else:  # List constant
                io.Out.Error(io.TS.OPT_LIST_NOT_ALLOWED,
                             "file:{0}:: Syntax Error, List not allowed here", line)
                raise program.OptError

        return uassign.operand

    value = uassign.operand.constant
    if (uassign.operation == "UAdd"):
        pass
    elif (uassign.operation == "USub"):
        value = -value
    elif (uassign.operation == "Invert"):
        value = -(1 + value)
    elif (uassign.operation == "Not"):
        if (value):
            value = 0
        else:
            value = 1
    else:
        programIR.Dump()
        io.Out.FatalRaw("Unknown UAssign operation:{}".format(uassign.operation))

    return program.Value(constant=int(value))


def BAssignWithConstants(bassign, programIR):
    value = bassign.left.constant
    if (bassign.operation == "Add"):
        value += bassign.right.constant
    elif (bassign.operation == "Mult"):
        value *= bassign.right.constant
    elif (bassign.operation == "Sub"):
        value -= bassign.right.constant
    elif (bassign.operation == "Div"):
        value /= bassign.right.constant
    elif (bassign.operation == "FloorDiv"):
        value /= bassign.right.constant
    elif (bassign.operation == "Mod"):
        value %= bassign.right.constant
    elif (bassign.operation == "LShift"):
        value <<= bassign.right.constant
    elif (bassign.operation == "RShift"):
        value >>= bassign.right.constant
    elif (bassign.operation == "BitOr"):
        value |= bassign.right.constant
    elif (bassign.operation == "BitAnd"):
        value &= bassign.right.constant
    elif (bassign.operation == "BitXor"):
        value ^= bassign.right.constant

    # Comparisons
    elif (bassign.operation == "Eq"):
        value = (value == bassign.right.constant)
    elif (bassign.operation == "NotEq"):
        value = (value != bassign.right.constant)
    elif (bassign.operation == "Lt"):
        value = (value < bassign.right.constant)
    elif (bassign.operation == "LtE"):
        value = (value <= bassign.right.constant)
    elif (bassign.operation == "Gt"):
        value = (value > bassign.right.constant)
    elif (bassign.operation == "GtE"):
        value = (value >= bassign.right.constant)

    else:
        programIR.Dump()
        io.Out.FatalRaw("Unknown BAssign operation:{}".format(bassign.operation))

    return program.Value(constant=int(value))


# def ScanForVarUsed(body, i, target):
#     """Look at the ops in the body (starting from i+1) and see if target
#        is read before it is assigned again."""
#     totalOps = len(body)
#     i += 1
#     while i < totalOps:
#         op = body[i]

#         # is it read?
#         if (op.kind == "UAssign"):
#             if op.operand.UsesValue(target):
#                 return True
#         elif (op.kind == "BAssign"):
#             if (op.left.UsesValue(target) or op.right.UsesValue(target)):
#                 return True
#         elif (op.kind in ("LoopControl", "For")):
#             if (op.test.UsesValue(target)):
#                 return True
#         elif (op.kind == "BoolCheck"):
#             if (op.value.UsesValue(target)):
#                 return True
#         elif (op.kind == "Call"):
#             for a in op.args:
#                 if (a.UsesValue(target)):
#                     return True
#         elif (op.kind == "Return"):
#             if (op.returnValue.UsesValue(target)):
#                 return True

#         # is it assigned
#         if op.kind in ("UAssign", "BAssign"):
#             if (op.target == target):
#                 # assigned again, therefore previous assign wasn't useful
#                 break

#         i += 1

#     return False


def IsSimpleTemp(value):
    return (value and (value.kind == "Value") and value.IsTemp() and
            (value.name < value.loopTempStart))


# def CheckOrAddVarInfo(varDict, value, typeInfo, line):
#     if (not value.IsAssignable()):
#         io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
#                      "file:{0}:: Syntax Error, no assignable variable",
#                      line)
#         raise program.OptError

#     name = value.name
#     if (name in varDict):
#         ok = True
#         if (varDict[name][0] == 'T'):
#             if (typeInfo != ('S', 1)):
#                 ok = False
#         elif (varDict[name][0] == 'L'):
#             if (typeInfo[0] != 'I'):
#                 ok = False
#         else:
#             if (typeInfo != varDict[name]):
#                 ok = False

#         if (not ok):
#             io.Out.Error(io.TS.OPT_VAR_TYPE_CHANGED,
#                          "file:{0}:: Syntax Error, Variable {1} changed it's type",
#                          line, name)
#             raise program.OptError

#     else:
#         io.Out.DebugRaw("Adding", typeInfo, "for name:", name)
#         varDict[name] = typeInfo


# def OldVerifyValueTypeIsInt(varDict, value, line):
#     """Check that the value variable is an int constant, or known and
#        evaluates to an int"""
#     if (value.IsIntConst() or value.IsTemp()):
#         return

#     if ((value.name is not None) and (value.name not in varDict)):
#         io.Out.Error(io.TS.OPT_VAR_NOT_BOUND,
#                      "file:{0}:: Syntax Error, Variable {1} doesn't have a value yet",
#                      line, value.name)
#         raise program.OptError

#     if (varDict[value.name] != ('I', None)):
#         io.Out.Error(io.TS.OPT_VAR_NOT_INT,
#                      "file:{0}:: Syntax Error, Variable {1} is not an integer value",
#                      line, value.name)
#         raise program.OptError


def GetReadVarType(name, localVar, globalVar, line):
    """Search in local first, then global and return the type of
       the variable (None if not found) """
    if (name in localVar):
        return ("local", localVar[name])
    if (name in globalVar):
        return ("global", globalVar[name])

    obj, sep, member = name.partition('.')
    if (member != ""):
        if (obj in localVar):
            className = localVar[obj][1]
            return ("local", ('I', className))
        if (obj in globalVar):
            className = globalVar[obj][1]
            return ("global", ('I', className))

    io.Out.Error(io.TS.OPT_VAR_NOT_BOUND,
                 "file:{0}:: Syntax Error, Variable {1} doesn't have a value yet",
                 line, name)
    raise program.OptError


def VerifyValueTypeIsInt(value, localVar, globalVar, line):
    """Check that the value variable is an int constant, or known and
       evaluates to an int"""
    if (value.IsIntConst() or value.IsTemp()):
        return

    if (value.name is not None):
        scope, typeInfo = GetReadVarType(value.name, localVar, globalVar, line)

        if (typeInfo[0] != 'I'):
            # print("ERROR", value.name, localVar, globalVar, scope, typeInfo)
            io.Out.Error(io.TS.OPT_VAR_NOT_INT,
                         "file:{0}:: Syntax Error, Variable {1} is not an integer value",
                         line, value.name)
            raise program.OptError


def VerifyTargetIsTuneStringElement(value, localVar, globalVar, globalWriteAccess, line):
    if (not value.IsAssignable()):
        io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                     "file:{0}:: Syntax Error, no assignable variable",
                     line)
        raise program.OptError

    if (not IsTuneStringElement(value, localVar, globalVar, globalWriteAccess, line)):
        io.Out.Error(io.TS.OPT_VAR_TYPE_CHANGED,
                     "file:{0}:: Syntax Error, Variable {1} changed it's type",
                     line, value.name)
        raise program.OptError


def IsTuneStringElement(value, localVar, globalVar, globalWriteAccess, line):
    if ((value.name is None) or value.IsTemp()):
        return False

    name = value.name

    # is it an Ed. name or object name
    className, sep, dataName = name.partition('.')
    if (len(dataName) > 0):
        return False

    existingTypeInfo = None
    if (name in localVar):
        existingTypeInfo = localVar[name]
    else:
        if (name in globalVar):
            if name in globalWriteAccess:
                existingTypeInfo = globalVar[name]
            else:
                return False

    if (existingTypeInfo):
        if (existingTypeInfo[0] == 'T'):
            return True
        else:
            return False
    else:
        return False


def CheckWriteVarTypeAddIfMissing(value, typeInfo, localVar, globalVar, globalWriteAccess, inFunc, line):
    """Search in local, if found then verify correct type (if incorrect throw).
       If not found, search in globalVar. If found but not in globalWriteList
       then throw (local var hides global var). If in globalWriteList then
       verify correct type.
       If not found in local or global, then add to localVar"""

    if (not value.IsAssignable()):
        io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                     "file:{0}:: Syntax Error, no assignable variable",
                     line)
        raise program.OptError

    name = value.name

    if (not value.IsTemp()):
        # is it an Ed. name or object name
        className, sep, dataName = name.partition('.')
        if (len(dataName) > 0):
            # className is the main variable name
            if (className == "Ed"):
                if (name in edpy_values.variables):
                    # a known Ed variable
                    if (typeInfo[0] != 'I'):
                        io.Out.Error(io.TS.OPT_VAR_TYPE_CHANGED,
                                     "file:{0}:: Syntax Error, Variable {1} changed it's type",
                                     line, name)
                        raise program.OptError
                    else:
                        pass
                else:
                    io.Out.Error(io.TS.OPT_RESERVED_NAME,
                                 "file:{0}:: Syntax Error, {1} is a reserved name",
                                 line, name)
                    raise program.OptError
                return

            else:
                # this must be an OBJECT
                classTypeInfo = None
                if (className in localVar):
                    classTypeInfo = localVar[className]
                elif (className in globalVar):
                    if name in globalWriteAccess:
                        classTypeInfo = globalVar[name]
                    else:
                        io.Out.Error(io.TS.OPT_LCL_HIDES_GLB,
                                     "file:{0}:: Syntax Error, Variable {1} hides a global variable",
                                     line, name)
                        raise program.OptError
                else:
                    # \TODO -- put correct error code here
                    io.Out.Error(io.TS.OPT_LCL_HIDES_GLB,
                                 "file:{0}:: Syntax Error, Variable {1} hides a global variable",
                                 line, name)
                    raise program.OptError

                if (classTypeInfo[0] == 'O'):
                    # \TODO have a correct class object. Now is the variable correct
                    # print("**** Found object -- ", className, classTypeInfo, dataName, typeInfo)
                    pass

                else:
                    # \TODO -- put correct error code here
                    io.Out.Error(io.TS.OPT_LCL_HIDES_GLB,
                                 "file:{0}:: Syntax Error, Variable {1} hides a global variable",
                                 line, name)
                    raise program.OptError


    existingTypeInfo = None
    if (name in localVar):
        existingTypeInfo = localVar[name]
    else:
        if (name in globalVar):
            if name in globalWriteAccess:
                existingTypeInfo = globalVar[name]
            elif (not inFunc):
                # if an internal function then don't do this check. It will use the locals
                # before the globals anyway
                io.Out.Error(io.TS.OPT_LCL_HIDES_GLB,
                             "file:{0}:: Syntax Error, Variable {1} hides a global variable",
                             line, name)
                raise program.OptError

    if (existingTypeInfo):
        if ((typeInfo == existingTypeInfo) or
            ((existingTypeInfo[0] == 'T') and (typeInfo == ('S', 1))) or
            ((existingTypeInfo[0] == 'L') and (typeInfo[0] != 'L'))):
            pass
        else:
            io.Out.Error(io.TS.OPT_VAR_TYPE_CHANGED,
                         "file:{0}:: Syntax Error, Variable {1} changed it's type",
                         line, name)
            raise program.OptError

    else:
        # Make sure that it's not a slice!
        if (not value.IsSimpleVar()):
            io.Out.Error(io.TS.OPT_VAR_NOT_BOUND,
                         "file:{0}:: Syntax Error, Variable {1} doesn't have a value yet",
                         line, value.name)
            raise program.OptError
        io.Out.DebugRaw("Adding", typeInfo, "for name:", name)
        localVar[name] = typeInfo


def ClearSimpleTempsFromVars(lclVar):
    newDict = {}
    simpleTempsFound = False
    # print(lclVar)
    for name in lclVar:
        if ((type(name) is int) and (name < program.Value().loopTempStart)):
            # print ("Removing temp", name)
            simpleTempsFound = True
        else:
            newDict[name] = lclVar[name]
    return newDict, simpleTempsFound


def VerifySignature(newArgList, oldArgList, callName, line):
    if (len(newArgList) != len(oldArgList)):
        io.Out.DebugRaw("Incorrect arg count on line:", line, "expected:", len(oldArgList),
                        "found:", len(newArgList))
        io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                     "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                     line, callName)
        raise program.OptError

    for i in range(len(newArgList)):
        oldArg = oldArgList[i]
        newArg = newArgList[i]

        if (len(newArg[0]) != 1):
            io.Out.FatalRaw("New argument should only have 1 type. It was {}.".format(newArg))

        if (len(oldArg[0]) == 1):
            if (oldArg[1] == None):
                result = (oldArg[0] == newArg[0])
                # print("Just elt:0 - ", oldArg[0], newArg[0], result)
            else:
                result = (oldArg == newArg)
                # print("Both elts - ", oldArg, newArg, result)

            if (not result):
                io.Out.DebugRaw("Changed call line:", line, "name:", callName, "sig:", newArgList,
                                "oldSig:", oldArgList)

                io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                             "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                             line, callName)
                raise program.OptError

        else:
            if (newArg[0] not in oldArg[0]):
                io.Out.DebugRaw("Changed call line:", line, "name:", callName, "sig:", newArgList,
                                "oldSig:", oldArgList)

                io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                             "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                             line, callName)
                raise program.OptError

# ############ optimisation passes ########################################


def CheckAndReplaceListIndex(value, rewriteList, line, opStr):
    if (value):
        if (value.IsSliceWithSimpleTempIndex()):
            v = GetRewriteValue(rewriteList, program.Value(name=value.indexVariable))
            if (v is not None):
                if (v.IsIntConst()):
                    io.Out.DebugRaw("{0}-{1}: replacing slice temp index {2} with constant {3}".
                                    format(opStr, line, value.name, v.constant))
                    return program.Value(name=value.name, iConstant=v.constant)
                if (v.IsSimpleVar()):
                    io.Out.DebugRaw("{0}-{1}: replacing slice temp index {2} with variable {3}".
                                    format(opStr, line, value.name, v.name))
                    return program.Value(name=value.name, iVariable=v.name)

        # Separated in case want to disable one of these
        elif (value.IsSliceWithVarIndex()):
            v = GetRewriteValue(rewriteList, program.Value(name=value.indexVariable))
            if (v is not None):
                if (v.IsIntConst()):
                    io.Out.DebugRaw("{0}-{1}: replacing slice index {2} with constant {3}".
                                    format(opStr, line, value.name, v.constant))
                    return program.Value(name=value.name, iConstant=v.constant)
                if (v.IsSimpleVar()):
                    io.Out.DebugRaw("{0}-{1}: replacing slice index {2} with variable {3}".
                                    format(opStr, line, value.name, v.name))
                    return program.Value(name=value.name, iVariable=v.name)
    return None


def ConstantRemoval(programIR):
    """Replace reads of variables with equivalent constant. This means removing variables that
       hold constants, and just using the constants directly in the code.
       Also replace operations on constants with the result of the operation.
       Also replace unary UAdd assignments that add nothing.
       So, if we have V1 <- UAdd V2, then replace uses of V1 with V2 and remove the useless op.
    """

    io.Out.DebugRaw("CR-0 start pass ****************")
    change = False
    for f in programIR.Function:
        # print("Function:", f)
        body = programIR.Function[f].body
        newBody = []

        # contains tuples of (targetValue, constant). Added when a constant
        # assigned to targetValue, and removed on the next assignment to targetValue
        rewriteList = []
        line = 0
        controlLevel = 0

        for i in range(len(body)):
            op = body[i]

            if op.kind == "Marker":
                line = op.line
                newBody.append(op)
                rewriteList = ClearSimpleTemps(rewriteList)

            elif op.kind == "ControlMarker":
                if (op.end == "start"):
                    controlLevel += 1
                elif (op.end == "end"):
                    controlLevel -= 1
                newBody.append(op)

            elif op.kind == "UAssign":

                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "CR")
                if (newValue):
                    op.target = newValue
                newValue = CheckAndReplaceListIndex(op.operand, rewriteList, line, "CR")
                if (newValue):
                    op.operand = newValue

                target = op.target
                if op.operand.IsConstant():
                    # check that either simple temp or NOT in a control structure
                    # if ((IsSimpleTemp(target) or (controlLevel == 0)) and
                    #     not target.IsSlice()):
                    if (target.IsSimpleTemp()):
                        # if (IsSimpleTemp(target) and (controlLevel == 0)):
                        # a UAssign with a constant on the right.
                        # Can replace use of this variable with the constant
                        # until it is written to again
                        value = UAssignWithConstant(op, programIR, line)
                        UpdateRewrite(rewriteList, target, value)
                        # print("CR-1 new replacment: {0} == {1}".format(target, value))

                    else:
                        # used in a control structure with an assignment -- remove from rewriteList
                        # as we don't know the execution path -- will this be executed or not
                        DeleteRewrite(rewriteList, target)

                    if (not IsSimpleTemp(target)):
                        # leave the expr as "DeadRemoval" will get it
                        newBody.append(op)
                    else:
                        io.Out.DebugRaw("Removed assignment in line:", line, op)
                        # print("Removed assignment in line:", line, op)

                # Failed opt -- remove in different pass
                # elif (op.operation == "UAdd"):
                #    # Value is passed unchanged -- replace uses of target with operand
                #    UpdateRewrite(rewriteList, target, op.operand)
                #     io.Out.DebugRaw("CR-{0} remove useless assignment {1}".format(line, op))

                #     # delete by not writing op to newBody
                #     change = True

                else:
                    # now apply a rewrite rule if the operand is there - even if
                    # inside a control structure. But remove the target from rewriteList
                    # as now the execution path is not known
                    v = GetRewriteValue(rewriteList, op.operand)
                    if v is not None:
                        # YES replace it!
                        msg = "CR-{0} rewrite simple assign from {1}".format(line, op)
                        op.operand = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True

                    # a variable is used, so remove a rewriteRule if it exists
                    DeleteRewrite(rewriteList, target)

                    newBody.append(op)

            elif op.kind == "BAssign":

                if (op.left.IsStrConst() or op.right.IsStrConst()):
                    io.Out.Error(io.TS.OPT_STRING_NOT_ALLOWED,
                                 "file:{0}:: Syntax Error, String not allowed here",
                                 line)
                    raise program.OptError

                if (op.left.IsListConst() or op.right.IsListConst()):
                    io.Out.Error(io.TS.OPT_LIST_NOT_ALLOWED,
                                 "file:{0}:: Syntax Error, List not allowed here",
                                 line)
                    raise program.OptError

                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "CR")
                if (newValue):
                    op.target = newValue
                newValue = CheckAndReplaceListIndex(op.left, rewriteList, line, "CR")
                if (newValue):
                    op.left = newValue
                newValue = CheckAndReplaceListIndex(op.right, rewriteList, line, "CR")
                if (newValue):
                    op.right = newValue

                target = op.target
                if (op.left.IsConstant() and op.right.IsConstant()):

                    value = BAssignWithConstants(op, programIR)

                    # check that either simple temp or NOT in a control structure
                    if (IsSimpleTemp(target) or (controlLevel == 0)):

                        # a BAssign with constant on the right!
                        UpdateRewrite(rewriteList, target, value)

                    else:
                        # used in a control structure with an assignment -- remove from rewriteList
                        # as we don't know the execution path -- will this be executed or not
                        DeleteRewrite(rewriteList, target)

                    if (not IsSimpleTemp(target)):
                        # replace with equivalent UAssign
                        newBody.append(program.UAssign(target=op.target, op="UAdd", operand=value))
                    else:
                        io.Out.DebugRaw("Removed assignment in line:", line, op)

                else:
                    # now apply a rewrite rule if left/right is there - even if
                    # inside a control structure. But remove the target from rewriteList
                    # as now the execution path is not known

                    # check left and right
                    msg = "CR-{0} rewrite binary arg(s) from {1}".format(line, op)
                    argChange = False

                    v = GetRewriteValue(rewriteList, op.left)
                    if v is not None:
                        # YES replace it!
                        op.left = v
                        argChange = True

                    v = GetRewriteValue(rewriteList, op.right)
                    if v is not None:
                        # YES replace it!
                        op.right = v
                        argChange = True

                    # a variable is used, so remove a rewriteRule if it exists
                    DeleteRewrite(rewriteList, target)

                    if (argChange):
                        change = True
                        io.Out.DebugRaw(msg)
                        io.Out.DebugRaw("CR-{0}                         to {1}".format(line, op))
                    newBody.append(op)

            elif op.kind == "BoolCheck":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "CR")
                if (newValue):
                    op.target = newValue
                newValue = CheckAndReplaceListIndex(op.value, rewriteList, line, "CR")
                if (newValue):
                    op.value = newValue

                # no assignment, so just need to see if it's value needs to
                # be rewritten
                if not op.value.IsConstant():
                    v = GetRewriteValue(rewriteList, op.value)
                    if v is not None:
                        # YES replace it!
                        msg = "CR-{0} rewrite BoolCheck from {1}".format(line, op)
                        op.value = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True
                newBody.append(op)

            elif op.kind == "Call":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "CR")
                if (newValue):
                    op.target = newValue
                    argChange = True

                # need to see if it's arg values need to be rewritten
                # and check the assignment to the target

                msg = "CR-{0} rewrite Call args from {1}".format(line, op)
                # if (op.funcName == "Ed.RegisterEventHandler"):
                #     print("C", msg)
                #     print("C", rewriteList)

                argChange = False
                for i in range(len(op.args)):

                    newValue = CheckAndReplaceListIndex(op.args[i], rewriteList, line, "CR")
                    if (newValue):
                        op.args[i] = newValue
                        argChange = True
                        # if (op.funcName == "Ed.RegisterEventHandler"):
                        #     print("C1", op)

                    if not op.args[i].IsConstant():
                        v = GetRewriteValue(rewriteList, op.args[i])
                        if v is not None:
                            # YES replace it!
                            op.args[i] = v
                            argChange = True
                            # if (op.funcName == "Ed.RegisterEventHandler"):
                            #     print("C2", op)

                if (op.target is not None):
                    # a variable is used, so remove a rewriteRule if it exists
                    DeleteRewrite(rewriteList, op.target)
                    # print ("Removing", target, "from rewriteList")

                if (argChange):
                    change = True
                    io.Out.DebugRaw(msg + " to {0}".format(op))
                newBody.append(op)

            elif op.kind == "LoopControl" or op.kind == "For":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.test, rewriteList, line, "CR")
                if (newValue):
                    op.test = newValue
                    argChange = True

                # no assignment, so just need to see if it's value needs to
                # be rewritten
                if not op.test.IsConstant():
                    v = GetRewriteValue(rewriteList, op.test)
                    if v is not None:
                        # YES replace it!
                        msg = "CR-{0} rewrite LoopCtl/For from {1}".format(line, op)
                        op.test = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True
                newBody.append(op)


            elif ((op.kind == "Return") and (not op.IsVoidReturn())):
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.returnValue, rewriteList, line, "CR")
                if (newValue):
                    op.returnValue = newValue
                    argChange = True

                # no assignment, so just need to see if it's value needs to
                # be rewritten
                if not op.returnValue.IsConstant():
                    v = GetRewriteValue(rewriteList, op.returnValue)
                    if v is not None:
                        # YES replace it!
                        msg = "CR-{0} rewrite Return from {1}".format(line, op)
                        op.returnValue = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True

                newBody.append(op)

            else:
                newBody.append(op)

            # print(newBody[-1])
            i += 1

        programIR.Function[f].body = newBody

    # if (change):
    #     programIR.Dump()

    return programIR, change


def SimpleVarRemoval(programIR):
    """Find simple writes to variables (UAssign with UAdd), and use the rhs of that
       statement later where the lhs is accessed.
    """

    io.Out.DebugRaw("SVR-0 start pass ***************")
    change = False
    for f in programIR.Function:
        # print("Function:", f)
        body = programIR.Function[f].body
        newBody = []

        # contains tuples of (targetValue, constant). Added when a constant
        # assigned to targetValue, and removed on the next assignment to targetValue
        rewriteList = []
        line = 0
        controlLevel = 0

        for i in range(len(body)):
            op = body[i]

            if op.kind == "Marker":
                line = op.line
                newBody.append(op)
                # rewriteList = ClearSimpleTemps(rewriteList)

            elif op.kind == "ControlMarker":
                if (op.end == "start"):
                    controlLevel += 1
                elif (op.end == "end"):
                    controlLevel -= 1
                newBody.append(op)

            elif op.kind == "UAssign":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "SVR")
                if (newValue):
                    op.target = newValue
                newValue = CheckAndReplaceListIndex(op.operand, rewriteList, line, "SVR")
                if (newValue):
                    op.operand = newValue

                target = op.target

                if (target.IsSliceWithSimpleTempIndex()):
                    # print("SVR-1:", line, op)
                    sliceIndex = program.Value(name=target.indexVariable)
                    v = GetRewriteValue(rewriteList, sliceIndex)
                    if v is not None:
                        # YES replace it!
                        msg = "SVR-{0} rewrite simple assign from {1}".format(line, op)
                        target.indexVariable = v.name
                        target.indexConstant = None
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True
                        # print("SVR-1-AFTER:", op, sliceIndex, v)

                if (not op.operand.IsConstant()):
                    # now apply a rewrite rule if the operand is there - even if
                    # inside a control structure. But remove the target from rewriteList
                    # as now the execution path is not known
                    v = GetRewriteValue(rewriteList, op.operand)
                    if v is not None:
                        # YES replace it!
                        msg = "SVR-{0} rewrite simple assign from {1}".format(line, op)
                        op.operand = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True

                    # looking for UAssign with UAdd. Need to be to a simple temp, or
                    # not in a control structure. Also need the rhs to be a non-temp
                    # unless the lhs is a simple temp too.
                    if ((op.operation == "UAdd") and
                        (IsSimpleTemp(target) or (controlLevel == 0)) and
                        (IsSimpleTemp(target) or not IsSimpleTemp(op.operand))):

                        # Add/update the rewrite rule for the new value
                        UpdateRewrite(rewriteList, target, op.operand)

                        if (not IsSimpleTemp(target)):
                            # leave the expr as "DeadRemoval" will get it
                            newBody.append(op)
                        else:
                            io.Out.DebugRaw("Removed assignment in line:", line, op)
                            # print("Removed assignment in line:", line, op)
                    else:
                        newBody.append(op)

                        # a variable is used, so remove a rewriteRule if it exists
                        DeleteRewrite(rewriteList, target)
                else:
                    newBody.append(op)

            elif op.kind == "BAssign":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "SVR")
                if (newValue):
                    op.target = newValue
                newValue = CheckAndReplaceListIndex(op.left, rewriteList, line, "SVR")
                if (newValue):
                    op.left = newValue
                newValue = CheckAndReplaceListIndex(op.right, rewriteList, line, "SVR")
                if (newValue):
                    op.right = newValue

                target = op.target
                # now apply a rewrite rule if left/right is there - even if
                # inside a control structure. But remove the target from rewriteList
                # as now the execution path is not known

                # check left and right
                msg = "SVR-{0} rewrite binary arg(s) from {1}".format(line, op)
                argChange = False

                v = GetRewriteValue(rewriteList, op.left)
                if v is not None:
                    # YES replace it!
                    op.left = v
                    argChange = True

                v = GetRewriteValue(rewriteList, op.right)
                if v is not None:
                    # YES replace it!
                    op.right = v
                    argChange = True

                # a variable is used, so remove a rewriteRule if it exists
                DeleteRewrite(rewriteList, target)

                if (argChange):
                    change = True
                    io.Out.DebugRaw(msg)
                    io.Out.DebugRaw("SVR-{0}                         to {1}".format(line, op))
                newBody.append(op)

            elif op.kind == "BoolCheck":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "SVR")
                if (newValue):
                    op.target = newValue
                newValue = CheckAndReplaceListIndex(op.value, rewriteList, line, "SVR")
                if (newValue):
                    op.value = newValue

                # no assignment, so just need to see if it's value needs to
                # be rewritten
                if not op.value.IsConstant():
                    v = GetRewriteValue(rewriteList, op.value)
                    if v is not None:
                        # YES replace it!
                        msg = "SVR-{0} rewrite BoolCheck from {1}".format(line, op)
                        op.value = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True
                newBody.append(op)

            elif op.kind == "Call":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.target, rewriteList, line, "SVR")
                if (newValue):
                    op.target = newValue
                    argChange = True

                # need to see if it's arg values need to be rewritten
                # and check the assignment to the target

                msg = "SVR-{0} rewrite Call args from {1}".format(line, op)
                # if (op.funcName == "Ed.RegisterEventHandler"):
                #     print("V", msg)
                #     print("V", rewriteList)
                argChange = False
                for i in range(len(op.args)):

                    newValue = CheckAndReplaceListIndex(op.args[i], rewriteList, line, "SVR")
                    if (newValue):
                        op.args[i] = newValue
                        argChange = True
                        # if (op.funcName == "Ed.RegisterEventHandler"):
                        #     print("V1", op)

                    if not op.args[i].IsConstant():
                        v = GetRewriteValue(rewriteList, op.args[i])
                        if v is not None:
                            # YES replace it!
                            op.args[i] = v
                            argChange = True
                            # if (op.funcName == "Ed.RegisterEventHandler"):
                            #     print("V2", op)


                if (op.target is not None):
                    # a variable is used, so remove a rewriteRule if it exists
                    DeleteRewrite(rewriteList, op.target)
                    # print ("Removing", target, "from rewriteList")

                if (argChange):
                    change = True
                    io.Out.DebugRaw(msg + " to {0}".format(op))
                newBody.append(op)

            elif op.kind == "LoopControl" or op.kind == "For":
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.test, rewriteList, line, "SVR")
                if (newValue):
                    op.test = newValue
                    argChange = True

                # no assignment, so just need to see if it's value needs to
                # be rewritten
                if not op.test.IsConstant():
                    v = GetRewriteValue(rewriteList, op.test)
                    if v is not None:
                        # YES replace it!
                        msg = "SVR-{0} rewrite LoopCtl/For from {1}".format(line, op)
                        op.test = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True
                newBody.append(op)

            elif ((op.kind == "Return") and (not op.IsVoidReturn())):
                # handle list indicies
                newValue = CheckAndReplaceListIndex(op.returnValue, rewriteList, line, "SVR")
                if (newValue):
                    op.returnValue = newValue
                    argChange = True

                # no assignment, so just need to see if it's value needs to
                # be rewritten
                if not op.returnValue.IsConstant():
                    v = GetRewriteValue(rewriteList, op.returnValue)
                    if v is not None:
                        # YES replace it!
                        msg = "SVR-{0} rewrite Return from {1}".format(line, op)
                        op.returnValue = v
                        io.Out.DebugRaw(msg + " to {0}".format(op))
                        change = True

                newBody.append(op)

            else:
                newBody.append(op)

            # print(newBody[-1])
            i += 1

        programIR.Function[f].body = newBody

    # if (change):
    #     programIR.Dump()

    return programIR, change


def SimpleCallCollapse(programIR):
    """Find simple writes to variables (UAssign with UAdd), and use the rhs of that
       statement later where the lhs is accessed.
    """

    io.Out.DebugRaw("SCC-0 start pass ***************")
    # programIR.Dump()
    change = False
    for f in programIR.Function:
        # print("Function:", f)
        body = programIR.Function[f].body
        newBody = []

        line = 0
        msg = ""
        skipNextUAssign = False

        for i in range(len(body)):
            op = body[i]
            # print (line, op)

            if op.kind == "Marker":
                line = op.line
                newBody.append(op)

            elif op.kind == "UAssign":
                if (skipNextUAssign):
                    io.Out.DebugRaw(msg)
                    skipNextUAssign = False
                    # print("Removed in line:", line)
                else:
                    # print ("Adding:", op)
                    newBody.append(op)

            elif op.kind == "Call":
                # need to see if it's arg values need to be rewritten
                # and check the assignment to the target
                if (op.target and IsSimpleTemp(op.target)):
                    if ((i < (len(body) - 1)) and
                        (body[i + 1].kind == "UAssign") and
                        (body[i + 1].operation == "UAdd") and
                        (body[i + 1].operand == op.target)):

                        skipNextUAssign = True
                        change = True
                        op.target = body[i + 1].target
                        msg = "SCC-{0} Collapse Call {1} to skip temp assignment".format(
                            line, op.funcName)

                newBody.append(op)

            else:

                newBody.append(op)

            i += 1

        # print ("newBody:", newBody)
        programIR.Function[f].body = newBody

    # if (change):
    #     programIR.Dump()

    return programIR, change


#
# Routines to support reducing total count of temporaries in each function
#

def NewSimpleTemp(value, newTempNameDict, line):
    if (value is None):
        return value

    if value.IsSimpleTemp():
        tempNumber = value.name
        return program.Value(name=newTempNameDict[tempNumber])
    elif value.IsSliceWithSimpleTempIndex():
        tempNumber = value.indexVariable
        return program.Value(name=value.name, iVariable=newTempNameDict[tempNumber])
    return value


def ReduceSimpleTempsInOneLine(lineBuffer, line):
    """Go through the line buffer of all the generated code for 1 line of source,
       and reuse temps if possible and compress the numbers toward 0."""
    newLineBuffer = []
    tempCount = 0
    newTempNames = {}
    for op in lineBuffer:
        for v in op.GetValues():
            if (v.IsSimpleTemp()):
                if (v.name not in newTempNames):
                    newTempNames[v.name] = tempCount
                    if (v.name != tempCount):
                        io.Out.DebugRaw("TEC-{0} renaming simple temp value:{1} to {2}".format(line, v.name, newTempNames[v.name]))
                    tempCount += 1
            elif (v.IsSliceWithSimpleTempIndex()):
                if (v.indexVariable not in newTempNames):
                    newTempNames[v.indexVariable] = tempCount
                    if (v.name != tempCount):
                        io.Out.DebugRaw("TEC-{0} renaming simple temp index:{1} to {2}".format(line, v.indexVariable, newTempNames[v.name]))
                    tempCount += 1

        t = op.GetTarget()
        if (t is not None):
            if t.IsSimpleTemp():
                if (t.name not in newTempNames):
                    newTempNames[t.name] = tempCount
                    if (t.name != tempCount):
                        io.Out.DebugRaw("TEC-{0} renaming simple temp target:{1} to {2}".format(line, t.name, newTempNames[t.name]))
                    tempCount += 1

            elif (t.IsSliceWithSimpleTempIndex()):
                if (t.indexVariable not in newTempNames):
                    newTempNames[t.indexVariable] = tempCount
                    if (t.name != tempCount):
                        io.Out.DebugRaw("TEC-{0} renaming simple temp target:{1} to {2}".format(line, t.indexVariable, newTempNames[t.name]))
                    tempCount += 1


    if (tempCount == 0):
        newLineBuffer = lineBuffer
    else:
        # print("RSTIOL:", tempCount, lineBuffer)
        # now have to replace the variable names
        for op in lineBuffer:
            if (op.kind == "LoopControl"):
                newOp = program.LoopControl(op.num, op.name, NewSimpleTemp(op.test, newTempNames, line))

            elif (op.kind == "ForControl"):
                newOp = program.ForControl(op.num, NewSimpleTemp(op.arrayValue, newTempNames, line),
                                           NewSimpleTemp(op.constantLimit, newTempNames, line),
                                           NewSimpleTemp(op.currentValue, newTempNames, line))

            elif (op.kind == "BoolCheck"):
                newOp = program.BoolCheck(op.num, op.op, NewSimpleTemp(op.value, newTempNames, line),
                                          NewSimpleTemp(op.target, newTempNames, line))

            elif (op.kind == "UAssign"):
                newOp = program.UAssign(NewSimpleTemp(op.target, newTempNames, line), op.operation,
                                        NewSimpleTemp(op.operand, newTempNames, line))

            elif (op.kind == "BAssign"):
                newOp = program.BAssign(NewSimpleTemp(op.target, newTempNames, line),
                                        NewSimpleTemp(op.left, newTempNames, line),
                                        op.operation,
                                        NewSimpleTemp(op.right, newTempNames, line))

            elif (op.kind == "Call"):
                args = []
                for a in op.args:
                    args.append(NewSimpleTemp(a, newTempNames, line))

                newOp = program.Call(NewSimpleTemp(op.target, newTempNames, line),
                                     op.funcName,
                                     args)

            elif ((op.kind == "Return") and (not op.IsVoidReturn())):
                newOp = program.Return(NewSimpleTemp(op.returnValue, newTempNames, line))

            else:
                newOp = op

            newLineBuffer.append(newOp)

    return newLineBuffer, len(newTempNames)


def TempCollapsing(programIR):
    """Where temps don't overlap, reuse the first temp where the second temp was used."""
    io.Out.DebugRaw("TEC-0 start pass ***************")

    usedFunctions = programIR.Function.keys()
    for f in usedFunctions:
        function = programIR.Function[f]
        if (function.maxSimpleTemps > 0):

            # This function has some temps -- try to collapse the simple ones
            body = function.body
            newBody = []
            maxTempsUsed = 0

            line = 0
            lastLine = 0
            lineBuffer = []

            for i in range(len(body)):
                op = body[i]
                # print (line, op)

                if op.kind == "Marker":
                    line = op.line

                    if (len(lineBuffer) > 0):
                        lineBuffer, maxTemps = ReduceSimpleTempsInOneLine(lineBuffer, lastLine)
                        if (maxTemps > maxTempsUsed):
                            maxTempsUsed = maxTemps

                        for l in lineBuffer:
                            newBody.append(l)
                        lineBuffer = []

                    newBody.append(op)

                    lastLine = line
                else:
                    lineBuffer.append(op)

                i += 1

            if (len(lineBuffer) > 0):
                lineBuffer, maxTemps = ReduceSimpleTempsInOneLine(lineBuffer, line)
                if (maxTemps > maxTempsUsed):
                    maxTempsUsed = maxTemps

                for l in lineBuffer:
                    newBody.append(l)

            # print ("newBody:", newBody)
            # print ("maxTemps:", maxTempsUsed)

            programIR.Function[f].body = newBody
            programIR.Function[f].maxSimpleTemps = maxTempsUsed

    return programIR


def QueryEdPyConstantUse(value, constants, line):

    if (value and value.IsSimpleVar() and (not value.IsTemp()) and
        (value.name == "None")):
        io.Out.Error(io.TS.OPT_NOT_SUPPORTED,
                     "file:{0}:: Syntax Error, {1} not supported in Ed.py",
                     line, value.name)
        raise program.OptError

    if (value and value.IsSimpleVar() and (not value.IsTemp()) and
        (value.name in constants)):
        io.Out.DebugRaw("EPC-{0} replacing var {1} with constant {2}".format(line, value.name, constants[value.name]))
        return program.Value(constant=constants[value.name])

    return None


def EdPyConstantReplacement(programIR):
    """Replace the names of EdPy constants with their values"""

    io.Out.DebugRaw("EPC-0 start pass ***************")

    if ("Ed" in programIR.Import):
        constants = edpy_values.constants
    else:
        constants = {}

    constants["True"] = 1
    constants["False"] = 0

    for f in programIR.Function:
        function = programIR.Function[f]
        body = function.body
        line = 0
        # newBody = []

        for op in body:
            target = op.GetTarget()
            if (target and target.IsSimpleVar() and (target.name in constants)):
                io.Out.Error(io.TS.OPT_WRITE_TO_ED_PY_CONSTANT,
                             "file:{0}:: Syntax Error, Ed.Py constant {1} can not be written",
                             line, target.name)
                raise program.OptError

            if op.kind == "Marker":
                line = op.line
                # newBody.append(op)

            if (op.kind == "LoopControl"):
                newValue = QueryEdPyConstantUse(op.test, constants, line)
                if (newValue):
                    op.test = newValue
                # newBody.append(op)

            elif (op.kind == "ForControl"):
                if (op.IsArray):
                    newValue = QueryEdPyConstantUse(op.arrayValue, constants, line)
                    if (newValue):
                        op.arrayValue = newValue
                else:
                    newValue = QueryEdPyConstantUse(op.constantLimit, constants, line)
                    if (newValue):
                        op.constantLimit = newValue
                    newValue = QueryEdPyConstantUse(op.currentValue, constants, line)
                    if (newValue):
                        op.currentValue = newValue

            elif (op.kind == "BoolCheck"):
                newValue = QueryEdPyConstantUse(op.value, constants, line)
                if (newValue):
                    op.value = newValue

            elif (op.kind == "UAssign"):
                newValue = QueryEdPyConstantUse(op.operand, constants, line)
                if (newValue):
                    op.operand = newValue

            elif (op.kind == "BAssign"):
                newValue = QueryEdPyConstantUse(op.left, constants, line)
                if (newValue):
                    op.left = newValue
                newValue = QueryEdPyConstantUse(op.right, constants, line)
                if (newValue):
                    op.right = newValue

            elif (op.kind == "Call"):
                newArgs = []
                change = False
                for a in op.args:
                    newValue = QueryEdPyConstantUse(a, constants, line)
                    if (newValue):
                        change = True
                        newArgs.append(newValue)
                    else:
                        newArgs.append(a)

                if (change):
                    op.args = newArgs

            elif ((op.kind == "Return") and (not op.IsVoidReturn())):
                newValue = QueryEdPyConstantUse(op.returnValue, constants, line)
                if (newValue):
                    op.returnValue = newValue

        # function.body = newBody

    return programIR


def RemoveUncalledFunctions(programIR):
    """If a function is not called then remove it"""

    io.Out.DebugRaw("RUF-0 start pass ***************")

    allFunctions = programIR.Function.keys()
    callList = ["__main__"]
    processedFuncs = []         # functions that have already been processed
    oldCallListLen = 0

    while (len(callList) > oldCallListLen):
        oldCallList = callList
        oldCallListLen = len(oldCallList)
        # there are more functions to process

        # io.Out.DebugRaw("CallList before:", oldCallList)
        for funcName in oldCallList:
            if funcName in processedFuncs:
                continue

            if (funcName in programIR.Function):
                for maybeNew in programIR.Function[funcName].callsTo:
                    if (maybeNew not in callList):
                        callList.append(maybeNew)
            else:
                io.Out.Error(io.TS.OPT_FUNCTION_NOT_DEFINED,
                             "file::: Syntax Error, called function {0} not defined",
                             funcName)
                raise program.OptError

            processedFuncs.append(funcName)

    # remove any functions not used

    removeFunctions = []
    for a in allFunctions:
        if (a not in callList):
            io.Out.DebugRaw("RUF-{0} remove un-called function".format(a))
            removeFunctions.append(a)

    for r in removeFunctions:
        del programIR.Function[r]

    return programIR


def RemoveUselessMarkers(programIR):
    """If a line has been optimised out, then remove it's Marker"""

    io.Out.DebugRaw("RUM-0 start pass ***************")
    change = False
    for f in programIR.Function:
        # print("Function:", f)
        body = programIR.Function[f].body
        newBody = []
        opCount = len(body)

        for i in range(opCount):
            skip = False
            # only do the test if there is another op after this one
            if i < (opCount - 1):
                if ((body[i].kind == "Marker") and
                    (body[i + 1].kind == "Marker")):
                    skip = True
                    io.Out.DebugRaw("RUM-{0} remove unused line marker".format(
                        body[i].line))

            if (not skip):
                newBody.append(body[i])
                change = True

        if (change):
            programIR.Function[f].body = newBody

    return programIR, change


def VerifyClassData(programIR):
    """Verify that all class data is created in the Class.init function.
       This makes it easier to get rid of methods that aren't being called.
    """
    io.Out.DebugRaw("VCD-0 verifying class data pass ******")
    for className in programIR.Class:
        io.Out.DebugRaw("...Verifying Class {}".format(className))
        cls = programIR.Class[className]
        if ("__init__" not in cls.funcNames):
            io.Out.Error(io.TS.OPT_CLASS_INIT_ERROR,
                         "file:0:: SyntaxError, Class {0} missing __init__ method",
                         className)
            raise program.OptError

        vars = programIR.Function[className + ".__init__"].localVar.keys()
        okSelfVars = [x for x in vars if x.startswith("self.")]

        for f in cls.funcNames:
            if (f == "__init__"):
                continue
            vars = programIR.Function[className + "." + f].localVar.keys()
            selfVars = [x for x in vars if x.startswith("self.")]
            for sv in selfVars:
                if (sv not in okSelfVars):
                    io.Out.Error(io.TS.OPT_CLASS_DATA_ERROR,
                                 "file:0:: SyntaxError, Function {0}.{1} " +
                                 "used {2} which was not created in {0}.__init__",
                                 className, f, sv)
                    raise program.OptError

    io.Out.DebugRaw("VCD-1 verifying class data pass ******")
    # check that all dotted names are Ed, self, or global objects
    for funcName in programIR.Function:
        vars = programIR.Function[funcName].localVar.keys()
        for v in vars:
            if (type(v) is int):
                continue
            obj, sep, name = v.partition('.')
            if (name != ""):
                if (obj == "Ed"):
                    # ok -- this is checked elsewhere
                    pass
                elif (obj == "self"):
                    # must be in a method (just to encourage good style)
                    cls, sep2, name2 = funcName.partition('.')
                    if (name2 == ""):
                        io.Out.Error(io.TS.OPT_SELF_NOT_IN_METHOD,
                                     "file:0:: SyntaxError, Function {0} " +
                                     "not a method so can't use self in {1}",
                                     funcName, v)
                        raise program.OptError
                else:
                    # must be a global object
                    if (obj not in programIR.globalVar):
                        io.Out.Error(io.TS.OPT_NOT_CLASS_REF,
                                     "file:{0}:: Syntax Error, Variable {1} does not refer to a class",
                                     0, v)
                        raise program.OptError


def VerifyConstantRange(programIR):
    """Verify that all constants are within -32768 and 32767.
    """
    io.Out.DebugRaw("VCR-0 verifying constant range pass ******")

    for f in programIR.Function:
        function = programIR.Function[f]
        body = function.body
        line = 0

        for op in body:
            if op.kind == "Marker":
                line = op.line

            else:
                values = op.GetValues()
                for v in values:
                    if (v.IsIntConst()):
                        # print("Constant - value:", v.constant)
                        if (v.constant < -32767):
                            io.Out.Error(io.TS.OPT_CONSTANT_TOO_NEGATIVE,
                                         "file:{0}:: Syntax Error, constant {1} is out of range",
                                         line, v.constant)
                            raise program.OptError

                        elif (v.constant > 32767):
                            io.Out.Error(io.TS.OPT_CONSTANT_TOO_POSITIVE,
                                         "file:{0}:: Syntax Error, constant {1} is out of range",
                                         line, v.constant)
                            raise program.OptError

                        else:
                            io.Out.DebugRaw("VCR-{0} constant {1} is ok, value {2}".format(
                                line, v.Name(), v.constant))


def VerifyEdisonVariables(programIR):
    """
    """
    io.Out.DebugRaw("VEV-0 verifying Edison variables pass ******")

    varNames = edpy_values.variables.keys()
    varValues = {}
    varLines = {}


    # Make sure they are set in __main__
    newMain = []
    body = programIR.Function["__main__"].body
    line = 0
    for op in body:
        if op.kind == "Marker":
            line = op.line
            newMain.append(op)
        else:
            t = op.GetTarget()
            if (t is not None):
                if (t.Name() in varNames):
                    if (t.Name() in varValues):
                        # set a second time
                        io.Out.Error(io.TS.OPT_ED_ASSIGN_AGAIN,
                                     "file:{0}:: Syntax Error, {1} can only be set once. It was already set.",
                                     line, t.Name())
                        raise program.OptError
                    if ((op.kind != "UAssign") or (op.operand.IsIntConst() == False)):
                        # Not a constant
                        io.Out.Error(io.TS.OPT_ED_ASSIGN_NOT_CONSTANT,
                                     "file:{0}:: Syntax Error, {1} can only be set to an integer constant",
                                     line, t.Name())
                        raise program.OptError

                    # check that the values is allowed
                    if (op.operand.constant not in edpy_values.variables[t.Name()]):
                        io.Out.Error(io.TS.OPT_ED_ASSIGN_BAD_VALUE,
                                     "file:{0}:: Syntax Error, set {1} to an invalid value",
                                     line, t.Name())
                        raise program.OptError

                    # A valid set -- record it and discard the operation
                    varValues[t.Name()] = op.operand.constant
                    varLines[t.Name()] = line
                    continue

        newMain.append(op)

    programIR.Function["__main__"].body = newMain

    # verify that all Ed.variables were set
    for n in varNames:
        if (n not in varValues):
            io.Out.Error(io.TS.OPT_ED_ASSIGN_NOT_SET,
                         "file:{0}:: Syntax Error, {1} was not set in __main__",
                         0, n)
            raise program.OptError

    version = varValues["Ed.EdisonVersion"]
    distance = varValues["Ed.DistanceUnits"]

    # check that Ed.DistanceUnits are valid for the version
    if (version == edpy_values.constants["Ed.V1"] and
        distance != edpy_values.constants["Ed.TIME"]):
        io.Out.Error(io.TS.OPT_ED_FUNCTION_NOT_AVAILABLE,
                     "file:{0}:: Syntax Error, {1} is not available in Edison Version {2}",
                     varLines["Ed.DistanceUnits"], "drive by distance", version)
        raise program.OptError

    io.Out.DebugRaw("VEV-0 Found all Ed variables: {}".format(varValues))

    # verify that not set in other functions
    for f in programIR.Function:
        if (f == "__main__"):
            continue

        function = programIR.Function[f]
        body = function.body
        line = 0

        for op in body:
            if op.kind == "Marker":
                line = op.line
            else:
                t = op.GetTarget()
                if ((t is not None) and (t.Name() in varNames)):
                    io.Out.Error(io.TS.OPT_ED_ASSIGN_IN_FUNCTION,
                                 "file:{0}:: Syntax Error, {1} can only be set in __main__",
                                 line, t.Name())
                    raise program.OptError

    programIR.EdVariables = varValues
    badFunctions = edpy_values.notAvailableFunctions[version]
    notUsedWithTime = ("Ed.ResetDistance", "Ed.SetDistance", "Ed.ReadDistance")

    functionSuffix = {0: "_CM", 1: "_INCH", 2: "_TIME"}[distance]
    possibleInlineFunctions = ("Ed.Drive", "Ed.DriveLeftMotor", "Ed.DriveRightMotor")
    rewriteFunctions = ("Ed.Drive", "Ed.DriveLeftMotor", "Ed.DriveRightMotor", "Ed.SetDistance",
                        "Ed.ReadDistance")

    # Now we know the values, update the Drive calls to the correct variant
    # and check that encoder functions are not used for V1
    for f in programIR.Function:
        function = programIR.Function[f]
        body = function.body
        line = 0
        newBody = []

        for op in body:
            if op.kind == "Marker":
                line = op.line
                newBody.append(op)
            else:
                if (op.kind == "Call"):
                    if (op.funcName in badFunctions):
                        io.Out.Error(io.TS.OPT_ED_FUNCTION_NOT_AVAILABLE,
                                     "file:{0}:: Syntax Error, {1} is not available in Edison Version {2}",
                                     line, op.funcName, version)
                        raise program.OptError

                    if ((varValues["Ed.DistanceUnits"] == edpy_values.constants["Ed.TIME"]) and
                        (op.funcName in notUsedWithTime)):
                        io.Out.Error(io.TS.OPT_ED_FUNCTION_NOT_USEFUL,
                                     "file:{0}:: Syntax Error, {1} is not useful with setting {2}",
                                     line, op.funcName, "Ed.TIME")
                        raise program.OptError

                    if (op.funcName in possibleInlineFunctions):
                        # if all args are constants and distance is unlimited, then
                        # change the name to an inline one
                        changeToInline = False
                        for i in range(len(op.args)):
                            if (not op.args[i].IsIntConst()):
                                break
                            if (i == 2):
                                # check if this constant is the unlimited one
                                if ((op.args[i].constant == edpy_values.constants["Ed.DISTANCE_UNLIMITED"]) and
                                    (len(op.args) == 3)):
                                    changeToInline = True
                                # check if this is a STOP -- distance is not important then
                                elif ((op.args[0].constant == edpy_values.constants["Ed.STOP"]) and
                                      (len(op.args) == 3)):
                                    changeToInline = True

                        if (changeToInline):
                            op.funcName += "_INLINE_UNLIMITED"
                            io.Out.DebugRaw("VEV-{0} Added suffix to function - now: {1}".format(
                                line, op.funcName))
                            # print("VEV-{0} Added suffix to function - now: {1}".format(
                            #       line, op.funcName))

                    if (op.funcName in rewriteFunctions):
                        op.funcName += functionSuffix
                        io.Out.DebugRaw("VEV-{0} Added suffix to function - now: {1}".format(
                            line, op.funcName))

                newBody.append(op)

        function.body = newBody

    return programIR


def FixUpCalls(programIR):
    """Fix up calls to objects (so .__init__ is called), calls to Ed.List and Ed.TuneString
       to handle 1 or 2 args, Ed function signatures, and object calls with self.name.
    """

    sigDict = programIR.FunctionSigDict
    sigDict["__main__"] = []

    # Check if Ed is imported
    if ("Ed" in programIR.Import):
        # are any classes called Ed?
        if ("Ed" in programIR.Class):
            io.Out.Error(io.TS.OPT_RESERVED_NAME,
                         "file:{0}:: Syntax Error, {1} is a reserved name",
                         0, "Ed")
            raise program.OptError

        # add in the function signatures - note Ed is a module not a class!
        # sig types: I - int, S - string const, V - integer list constant (vector)
        #          : T - tunestr ref, L - list ref, O - object ref

        # print("Ed.py signatures:", edpy_values.signatures)
        for k in edpy_values.signatures:
            sigDict[k] = edpy_values.signatures[k]
        # print("Added Ed.py signatures:", sigDict)

    # Calls to objects and to Ed.List/Ed.TuneString is only allowed in __main__
    function = programIR.Function["__main__"]
    body = function.body
    line = 0
    newBody = []

    # Just using defines for now. Uncomment if it's needed
    # if ("Ed" in programIR.Import):
    #     newBody.append(program.Call(None, "Ed.Init", []))

    for op in body:
        if op.kind == "Marker":
            line = op.line
            newBody.append(op)

        elif op.kind == "UAssign":
            # check that not a list or string constant (as only valid in certain calls)
            # if (op.operand.IsStrConst()):
            #     io.Out.Error(io.TS.OPT_STRING_NOT_ALLOWED,
            #                  "file:{0}:: Syntax Error, String not allowed here",
            #                  line)
            #     raise program.OptError
            if (op.operand.IsListConst()):
                io.Out.Error(io.TS.OPT_LIST_NOT_ALLOWED,
                             "file:{0}:: Syntax Error, List not allowed here",
                             line)
                raise program.OptError

            # the types of these targets can be different if they are shadowing
            # results from calls
            newBody.append(op)

        elif op.kind == "BAssign":
            # the types of these target are always integers
            newBody.append(op)

        elif op.kind == "Call":
            if (op.funcName == "Ed.List"):
                if (len(op.args) == 1):
                    op.funcName = "Ed.List1"
                elif (len(op.args) == 2):
                    op.funcName = "Ed.List2"
                    # arg types are checked elsewhere but also need to check that the string
                    # constant is in range, so have to check here too. Will constrain the
                    # values to constants
                    if (not op.args[0].IsIntConst() or not op.args[1].IsListConst()):
                        io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                                     "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                                     line, "Ed.List")
                        raise program.OptError

                    if (len(op.args[1].listConst) > op.args[0].constant):
                        io.Out.Error(io.TS.OPT_ED_LIST_TOO_LONG,
                                     "file:{0}:: Syntax Error, {1} initial value larger then first argument {2}",
                                     line, "Ed.List", op.args[0].constant)
                        raise program.OptError

                else:
                    io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                                 "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                                 line, "Ed.List")
                    raise program.OptError

                if ((op.target is None) or (not op.target.IsSimpleVar())):
                    io.Out.Error(io.TS.PARSE_SYNTAX_ERROR,
                                 "file:{0}:{1}: Syntax error",
                                 line, "")

            elif (op.funcName == "Ed.TuneString"):
                if (len(op.args) == 1):
                    op.funcName = "Ed.TuneString1"

                elif (len(op.args) == 2):
                    op.funcName = "Ed.TuneString2"
                    # arg types are checked elsewhere but also need to check that the string
                    # constant is in range, so have to check here too. Will constrain the
                    # values to constants
                    if (not op.args[0].IsIntConst() or not op.args[1].IsStrConst()):
                        io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                                     "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                                     line, "Ed.TuneString")
                        raise program.OptError

                    #print(len(op.args[1].strConst), op.args[0].constant)
                    if (len(op.args[1].strConst) > op.args[0].constant):
                        io.Out.Error(io.TS.OPT_ED_LIST_TOO_LONG,
                                     "file:{0}:: Syntax Error, {1} initial value larger then first argument {2}",
                                     line, "Ed.TuneString", op.args[0].constant)
                        raise program.OptError

                    elif (len(op.args[1].strConst)>0 and op.args[1].strConst[-1] != 'z'):
                        io.Out.Warning(io.TS.OPT_ED_WARN_TUNESTRING_END,
                                    "file:{0}:: Warning, TuneString doesn't end with 'z'",
                                    line,)
                        # no raise here as it's just a warning

                else:
                    io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                                 "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                                 line, "Ed.TuneString")
                    raise program.OptError

                if ((op.target is None) or (not op.target.IsSimpleVar())):
                    io.Out.Error(io.TS.PARSE_SYNTAX_ERROR,
                                 "file:{0}:{1}: Syntax error",
                                 line, "")

            elif (op.funcName in programIR.Class):
                # print("Class - ", op.funcName)
                if ((op.target is None) or (not op.target.IsSimpleVar())):
                    io.Out.Error(io.TS.PARSE_SYNTAX_ERROR,
                                 "file:{0}:{1}: Syntax error",
                                 line, "")

                # add a function call to create the object
                args = [program.Value(strConst=op.funcName)]
                newBody.append(program.Call(op.target, "Ed.CreateObject", args))

                op.funcName += ".__init__"
                op.args.insert(0, op.target)
                op.target = None

            # verify that all Ed. functions are known ones
            if (op.funcName.startswith("Ed.")):
                if ("Ed" not in programIR.Import):
                    io.Out.Error(io.TS.OPT_MISSING_ED_IMPORT,
                                 "file:{0}:: Syntax Error, Ed function {1} not known. Are you missing 'import Ed'?",
                                 line, op.funcName)
                    raise program.OptError
                elif (op.funcName not in edpy_values.signatures):
                    io.Out.Error(io.TS.OPT_UNKNOWN_ED_FUNCTION,
                                 "file:{0}:: Syntax Error, Unknown Ed function {1}",
                                 0, op.funcName)
                    raise program.OptError

            newBody.append(op)

        else:
            newBody.append(op)

    function.body = newBody

    return programIR


def VerifyValidSliceTarget(target, funcName, glbVar, lclVar, line):
    if (target is None):
        return

    if (target.IsSlice()):
        n = target.name
        # print(glbVar, lclVar)
        if ((n not in glbVar) and (n not in lclVar)):
            io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                         "file:{0}:: Syntax Error, no assignable variable",
                         line)
            raise program.OptError
        if ((n in lclVar) and (lclVar[n][0] not in ('T', 'L'))):
            io.Out.Error(io.TS.OPT_VAR_MUST_BE_TS_OR_LIST,
                         "file:{0}:: Syntax Error, variable {1} not a tunestring or list",
                         line, n)
            raise program.OptError
        if ((n in glbVar) and (glbVar[n][0] not in ('T', 'L'))):
            io.Out.Error(io.TS.OPT_VAR_MUST_BE_TS_OR_LIST,
                         "file:{0}:: Syntax Error, variable {1} not a tunestring or list",
                         line, n)
            raise program.OptError


def TypeVariablesByFunc(programIR, funcName, callList):
    """Find the types of all variables in a function, verify that it has the
       correct number of args, and deduce (or check) signatures of functions it calls"""

    if (funcName not in programIR.Function):
        io.Out.DebugRaw("Function {0} must be external -- later though will have to be supplied!".format(funcName))
        io.Out.Error(io.TS.OPT_UNKNOWN_FUNCTION,
                     "file:{0}:: Syntax Error, Unknown function {1}",
                     0, funcName)
        raise program.OptError

    sigDict = programIR.FunctionSigDict
    glbVar = programIR.globalVar
    function = programIR.Function[funcName]
    lclVar = {}
    glbAccess = function.globalAccess
    simpleTempsUsed = False
    io.Out.DebugRaw("TYPING Function:", function)
    body = function.body
    line = 0
    inFunc = function.IsInternalFunction()

    # Check that have the right number of arguments (information from the callers)
    if (len(function.args) != len(sigDict[funcName])):
        io.Out.Error(io.TS.OPT_INCORRECT_ARG_DEFINE,
                     "file:{0}:: Syntax Error, in function {1} argument definition doesn't match callers use",
                     line, funcName)
        raise program.OptError

    # Check that globalAccess refers to a real global variable
    for i in glbAccess:
        if (i not in glbVar):
            io.Out.Error(io.TS.OPT_NOT_A_GLOBAL_VAR,
                         "file:{0}:: Syntax Error, {1} is not a global variable",
                         line, i)
            raise program.OptError

    # Seed the var Dict with the arguments
    for i in range(len(function.args)):
        lclVar[function.args[i]] = sigDict[funcName][i]

    # print ("Variable info:", varTypeDict)
    # print ()
    for op in body:

        if op.kind == "Marker":
            line = op.line
            lclVar, simpleTempsUsedInLine = ClearSimpleTempsFromVars(lclVar)
            if (simpleTempsUsedInLine):
                simpleTempsUsed = True

        elif op.kind == "UAssign":
            target = op.GetTarget()
            if ((target is None) or (not target.IsAssignable())):
                io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                             "file:{0}:: Syntax Error, no assignable variable",
                             line)
                raise program.OptError

            VerifyValidSliceTarget(target, funcName, glbVar, lclVar, line)

            if (op.operand.IsStrConst()):
                # only allowed in Ed.TuneString call (already handled) or when assigning
                # to a tunestring ELEMENT
                if ((len(op.operand.strConst) == 1) and target.IsSlice()):
                    # now the slice name has to refer to a tune string
                    VerifyTargetIsTuneStringElement(target, lclVar, glbVar,
                                                    glbAccess, line)

                else:
                    io.Out.Error(io.TS.OPT_STRING_NOT_ALLOWED,
                                 "file:{0}:: Syntax Error, String not allowed here",
                                 line)
                    raise program.OptError

            elif (IsTuneStringElement(op.operand, lclVar, glbVar, glbAccess, line)):
                # only allowed in Ed.TuneString call (already handled) or when assigning
                # to a tunestring ELEMENT
                if (target.IsSlice()):
                    # now the slice name has to refer to a tune string
                    VerifyTargetIsTuneStringElement(target, lclVar, glbVar,
                                                    glbAccess, line)

                else:
                    io.Out.Error(io.TS.OPT_STRING_NOT_ALLOWED,
                                 "file:{0}:: Syntax Error, String not allowed here",
                                 line)
                    raise program.OptError

            else:
                if (op.operand.IsListConst()):
                    io.Out.Error(io.TS.OPT_LIST_NOT_ALLOWED,
                                 "file:{0}:: Syntax Error, List not allowed here",
                                 line)
                    raise program.OptError

                # TODO: Add ability to assign T, L, O
                if (op.operand.IsTSRef()):
                    CheckWriteVarTypeAddIfMissing(target, ('T', None), lclVar, glbVar,
                                                  glbAccess, inFunc, line)

                elif (op.operand.IsListRef()):
                    CheckWriteVarTypeAddIfMissing(target, ('L', None), lclVar, glbVar,
                                                  glbAccess, inFunc, line)

                elif (op.operand.IsObjRef()):
                    # TODO: Need class name
                    CheckWriteVarTypeAddIfMissing(target, ('O', None), lclVar, glbVar,
                                                  glbAccess, inFunc, line)

                elif (op.operand.IsSimpleVar()):
                    scope, typeInfo = GetReadVarType(op.operand.name, lclVar, glbVar, line)
                    # Just copy it through (so allow none integers)
                    CheckWriteVarTypeAddIfMissing(target, typeInfo, lclVar, glbVar,
                                                  glbAccess, inFunc, line)

                else:
                    CheckWriteVarTypeAddIfMissing(target, ('I', None), lclVar, glbVar,
                                                  glbAccess, inFunc, line)

        elif op.kind == "BAssign":
            target = op.GetTarget()
            if ((target is None) or (not target.IsAssignable())):
                io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                             "file:{0}:: Syntax Error, no assignable variable",
                             line)
                raise program.OptError

            VerifyValidSliceTarget(target, funcName, glbVar, lclVar, line)

            if (op.left.IsSimpleVar()):
                VerifyValueTypeIsInt(op.left, lclVar, glbVar, line)

            if (op.right.IsSimpleVar()):
                VerifyValueTypeIsInt(op.right, lclVar, glbVar, line)

            CheckWriteVarTypeAddIfMissing(target, ('I', None), lclVar,
                                          glbVar, glbAccess, inFunc, line)

        elif op.kind == "BoolCheck":
            target = op.GetTarget()
            if ((target is None) or (not target.IsAssignable())):
                io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                             "file:{0}:: Syntax Error, no assignable variable",
                             line)
                raise program.OptError

            VerifyValidSliceTarget(target, funcName, glbVar, lclVar, line)

        elif op.kind == "LoopControl":
            # verify that the variable is known
            if (op.test.IsSimpleVar() and not op.test.IsTemp()):
                scope, typeInfo = GetReadVarType(op.test.name, lclVar, glbVar, line)


        elif op.kind == "ForControl":
            # Verify that the variables are of the right type
            if (op.IsArray()):
                # check that op.arrayValue is a real T or S
                scope, typeInfo = GetReadVarType(op.arrayValue.name, lclVar, glbVar, line)

                if (typeInfo[0] not in ('T', 'L')):
                    io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                                 "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                                 line, "range")
                    raise program.OptError

            else:
                VerifyValueTypeIsInt(op.currentValue, lclVar, glbVar, line)
                VerifyValueTypeIsInt(op.constantLimit, lclVar, glbVar, line)

        elif op.kind == "Call":
            target = op.GetTarget()
            # print("CALL", op)
            if ((target is not None) and (not target.IsAssignable())):
                io.Out.Error(io.TS.OPT_NOT_ASSIGNABLE,
                             "file:{0}:: Syntax Error, no assignable variable",
                             line)
                raise program.OptError

            VerifyValidSliceTarget(target, funcName, glbVar, lclVar, line)

            argList = []
            callName = op.funcName
            io.Out.DebugRaw("Call:", op)

            # Check if this is calling a method on a variable
            var, sep, method = callName.partition('.')
            # io.Out.DebugRaw("..split", var, method)

            # Looking at a variable of type object
            if ((var != "Ed") and (len(method) > 0) and (var not in programIR.Class)):
                scope, typeInfo = GetReadVarType(var, lclVar, glbVar, line)
                # print("**Call-method**", var, method, scope, typeInfo)
                if (typeInfo[0] == 'O'):
                    # io.Out.DebugRaw("..method call", var, varTypeDict[var])
                    # change var.method(args) to class.method(var, args)
                    cls = typeInfo[1]
                    # io.Out.DebugRaw("....Class", cls)
                    callName = cls + "." + method
                    op.funcName = callName
                    io.Out.DebugRaw("....Func", op.funcName)
                    newArgs = [program.Value(name=var)]
                    newArgs.extend(op.args)
                    io.Out.DebugRaw("....New args", newArgs)
                    op.args = newArgs
                    # io.DebugRaw("..Rewrote method call:", op)
                else:
                    io.Out.Error(io.TS.OPT_NOT_CLASS_REF,
                                 "file:{0}:: Syntax Error, Variable {1} does not refer to a class",
                                 line, var)
                    raise program.OptError

            for a in op.args:
                io.Out.DebugRaw("...Arg:", a)
                if (a.IsSimpleVar()):
                    scope, typeInfo = GetReadVarType(a.name, lclVar, glbVar, line)
                    argList.append(typeInfo)

                elif (a.IsStrConst()):
                    argList.append(('S', len(a.strConst)))
                elif (a.IsListConst()):
                    argList.append(('V', None))  # V for Vector
                elif (a.IsTSRef()):
                    argList.append(('T', None))
                elif (a.IsListRef()):
                    argList.append(('L', None))
                elif (a.IsObjRef()):
                    # print("**** Object ref:", a)
                    argList.append(('O', None))  # TODO: class name should be here
                elif (a.IsSlice()):
                    # print("***", a)
                    # print("***", varTypeDict)
                    scope, typeInfo = GetReadVarType(a.name, lclVar, glbVar, line)
                    if (typeInfo[0] == 'L'):
                        argList.append(('I', None))
                    elif (typeInfo[0] == 'T'):
                        argList.append(('S', 1))
                    else:
                        io.Out.Error(io.TS.OPT_SLICE_NOT_ALLOWED,
                                     "file:{0}:: Syntax Error, Variable {1} can't be sliced",
                                     line, a.name)
                        raise program.OptError
                else:
                    argList.append(('I', None))

            # print("Call args processed:", callName, argList)
            if (callName not in sigDict):
                sigDict[callName] = argList
            else:
                VerifySignature(argList, sigDict[callName], callName, line)

            io.Out.DebugRaw("Adding call to callList:", funcName, callName)
            callList.append((funcName, callName))
            # print("Adding call", funcName, callName)

            if (callName not in function.callsTo):
                function.callsTo.append(callName)

            # Already been verified (above) so will have two args, with the
            # second being the name of the function
            if (callName == "Ed.RegisterEventHandler"):
                eventCallName = op.args[1].strConst
                io.Out.DebugRaw("Adding call to callList:", funcName, eventCallName)
                callList.append((funcName, eventCallName))

                if (eventCallName not in function.callsTo):
                    function.callsTo.append(eventCallName)

                # check later that the signatures are all good
                # programIR.EventHandlers.append((eventCallName, line))
                if (not op.args[0].IsIntConst() or
                    (op.args[0].constant < 0) or
                    (op.args[0].constant > edpy_values.constants["Ed.EVENT_LAST_EVENT"])):
                        io.Out.Error(io.TS.OPT_BAD_EVENT_NUMBER,
                                     "file:{0}:: Syntax Error, event not a constant or out of range",
                                     line)
                        raise program.OptError

                programIR.EventHandlers[eventCallName] = int(op.args[0].constant)

                # also add or verify the type of the new function - it takes no
                # args!
                if (eventCallName not in sigDict):
                    sigDict[eventCallName] = []
                else:
                    VerifySignature([], sigDict[eventCallName], eventCallName, line)

            # TODO: Check all Ed.xxxx even if they aren't assigned to a variable

            if (op.target is not None):
                # already partitioned into var, sep, method
                if (var in programIR.Class):
                    if (method == "__init__"):
                        if ((funcName != "__main__") or (op.target is None) or
                            (op.target.IsTemp()) or (not op.target.IsSimpleVar())):
                            io.Out.Error(io.TS.OPT_ONLY_AT_TOP_LEVEL,
                                         "file:{0}:: Syntax Error, {1} only allowed at the top level",
                                         0, callName)
                            raise program.OptError
                        else:
                            CheckWriteVarTypeAddIfMissing(op.target, ('O', var), lclVar,
                                                          glbVar, glbAccess, inFunc, line)
                    else:
                        # all methods return I or nothing
                        CheckWriteVarTypeAddIfMissing(op.target, ('I', None), lclVar,
                                                      glbVar, glbAccess, inFunc, line)

                elif (callName.startswith("Ed.List")):
                    if ((funcName != "__main__") or (op.target is None) or
                        (op.target.IsTemp()) or (not op.target.IsSimpleVar())):
                        io.Out.Error(io.TS.OPT_ONLY_AT_TOP_LEVEL,
                                     "file:{0}:: Syntax Error, {1} only allowed at the top level",
                                     0, callName)
                        raise program.OptError
                    else:
                        CheckWriteVarTypeAddIfMissing(op.target, ('L', None), lclVar,
                                                      glbVar, glbAccess, inFunc, line)

                elif (callName.startswith("Ed.TuneString")):
                    if ((funcName != "__main__") or (op.target is None) or
                        (op.target.IsTemp()) or (not op.target.IsSimpleVar())):
                        io.Out.Error(io.TS.OPT_ONLY_AT_TOP_LEVEL,
                                     "file:{0}:: Syntax Error, {1} only allowed at the top level",
                                     0, callName)
                        raise program.OptError
                    else:
                        CheckWriteVarTypeAddIfMissing(op.target, ('T', None), lclVar,
                                                      glbVar, glbAccess, inFunc, line)

                elif (callName == "Ed.CreateObject"):
                    if ((funcName != "__main__") or (op.target is None) or
                        (op.target.IsTemp()) or (not op.target.IsSimpleVar())):
                        io.Out.Error(io.TS.OPT_ONLY_AT_TOP_LEVEL,
                                     "file:{0}:: Syntax Error, {1} only allowed at the top level",
                                     0, callName)
                        raise program.OptError
                    else:
                        CheckWriteVarTypeAddIfMissing(op.target, ('O', op.args[0].strConst),
                                                      lclVar, glbVar, glbAccess, inFunc, line)

                elif (callName == "Ed.RegisterEventHandler"):
                    if ((funcName != "__main__")):
                        io.Out.Error(io.TS.OPT_ONLY_AT_TOP_LEVEL,
                                     "file:{0}:: Syntax Error, {1} only allowed at the top level",
                                     0, callName)
                        raise program.OptError

                elif (callName == "chr"):
                    # the result of an chr() is a ('S', 1)
                    CheckWriteVarTypeAddIfMissing(op.target, ('S', 1),
                                                  lclVar, glbVar, glbAccess, inFunc, line)

                else:
                    CheckWriteVarTypeAddIfMissing(op.target, ('I', None),
                                                  lclVar, glbVar, glbAccess, inFunc, line)

    lclVar, simpleTempsUsedInLine = ClearSimpleTempsFromVars(lclVar)
    if (simpleTempsUsedInLine):
        simpleTempsUsed = True

    # print("Local var from", funcName, lclVar)
    function.localVar = lclVar
    function.maxSimpleTemps = simpleTempsUsed

    # io.Out.DebugRaw("\nFINISHED TYPING Function:", function, sigDict)

    return programIR, False


def CleanOutObjectVariables(programIR, funcName):
    """Find the types of all variables in a function, verify that it has the
       correct number of args, and deduce (or check) signatures of functions it calls"""
    if (funcName not in programIR.Function):
        io.Out.DebugRaw("Function {0} must be external -- later though will have to be supplied!".format(funcName))
        io.Out.Error(io.TS.OPT_UNKNOWN_FUNCTION,
                     "file:{0}:: Syntax Error, Unknown function {1}",
                     0, funcName)
        raise program.OptError

    glbs = programIR.globalVar
    newLocals = {}
    oldLocals = programIR.Function[funcName].localVar

    for name in oldLocals:
        if (type(name) is int):
            newLocals[name] = oldLocals[name]
        else:
            obj, sep, member = name.partition('.')
            if (member != ""):
                # print("CLEAN", obj, member, newLocals)
                if (obj in oldLocals or obj in glbs):
                    pass
                else:
                    newLocals[name] = oldLocals[name]
            else:
                newLocals[name] = oldLocals[name]

    programIR.Function[funcName].localVar = newLocals


def MoveMainLocalsToGlobals(programIR):
    newMainLocals = {}
    oldMainLocals = programIR.Function["__main__"].localVar
    glbs = programIR.globalVar

    for name in oldMainLocals:
        if (type(name) is int):
            # a temp (simple or loop control)
            newMainLocals[name] = oldMainLocals[name]
        else:
            glbs[name] = oldMainLocals[name]

    programIR.Function["__main__"].localVar = newMainLocals

    for name in glbs:
        programIR.Function["__main__"].globalAccess.append(name)


def TypeVariables(programIR):
    """Find the type of all variables, and which functions are used"""

    callList = []               # List of what functions call each other
    processedFuncs = []         # functions that have already been processed

    # start from __main__
    oldCallListLen = len(callList)
    programIR.FunctionSigDict["__main__"] = []
    programIR.globalVar = {}

    # Add in the Ed variables to the global context
    if ("Ed" in programIR.Import):
        for edVar in edpy_values.variables:
            programIR.globalVar[edVar] = ('I', None)

    TypeVariablesByFunc(programIR, "__main__", callList)
    processedFuncs.append("__main__")

    CleanOutObjectVariables(programIR, "__main__")

    # Add the none-temp local vars from __main__ to globalVar
    # and add them to global access for __main__
    MoveMainLocalsToGlobals(programIR)

    # print("**", callList)

    # Do the __init__ functions first
    for m, l in callList:
        if (l.endswith(".__init__")):
            TypeVariablesByFunc(programIR, l, callList)
            processedFuncs.append(l)

    # Now do all other functions, possibly expanding the number
    while (len(callList) > oldCallListLen):
        oldCallList = callList
        oldCallListLen = len(oldCallList)
        # there are more functions to process

        # io.Out.DebugRaw("CallList before:", oldCallList)
        for _, funcName in oldCallList:
            if funcName in processedFuncs:
                continue

            TypeVariablesByFunc(programIR, funcName, callList)
            processedFuncs.append(funcName)

        # io.Out.DebugRaw("CallList after:", callList)
    # now we should have all of the variables, types and functions called

    # check all event handlers
    for e in programIR.EventHandlers:
        if (e not in programIR.Function):
            io.Out.Error(io.TS.OPT_INCORRECT_ARG_USE,
                         "file:{0}:: Syntax Error, incorrect arguments used in {1} call",
                         0, "Ed.RegisterEventHandler")
            raise program.OptError
        VerifySignature([], programIR.FunctionSigDict[e], e, programIR.EventHandlers[e])


    # print(callList, programIR.globalVar, programIR.FunctionSigDict)
    # programIR.Dump()
    # raise Exception

    return programIR, False


def CheckEdAndObjectVariables(programIR):
    """Check all of the object variables and make sure that Ed variables are allowed ones,
       and others are data members in classes"""
    pass


# ############ Controlling routines ########################################

# TODO: More optimisation passes (this should be the complete list, remove
#       them as they are added:
# DONE-1. Allow var assignments (and therefore type assignment) of TS, L, O to
#    other vars. This will be needed for storing these higher level types
#    in objects, so might as well allow it everywhere. As the data is just
#    an integer to refer to these higher types, it is really just assigning
#    or passing an integer -- therefore a reference. This is just UAssign-UAdd
#    though
# DONE-2. Allow full CONSTANT strings to be stored, and CONSTANT arrays too. Constant
#    strings have been added to Value, but need constant arrays, and need the parser
#    to allow them through. Later in the optimiser will make sure that the type
#    (i.e. string of length 1) is correct, not the parser.
# DONE 2.1. Convert calls to class methods from var.method(args) to class.method(var, args)
# DONE-3. Check that class data is only created in __init__. This will allow for
#    unused methods to be removed (__init__ is always used), without affecting
#    the data in an object. Store the class data info in ProgramIR for the class.
# DONE 4. Handle global read/only scope correctly. Basically on the right side (but not
#    as a target), if the var is not arg/global/local then see if it is a global
#    variable.
# DONE 5. Make sure that all values are the correct type for operations. May need special
#    checks for ord()-string is on length 1, len()-takes either TS or L, chr()-return
#    value is used for a slice assignment (and only that!). Make sure that all slice
#    operations are correct (so Value name must refer to a TS or L) as well as For.
# DONE 6. Identify the event handlers and add them to the used-function list
# DONE 7. Remove functions that are not called, including class methods.
# 8. Remove in functions (not __main__ or classes)
#    variable writes that are not used after writing (though not writes to globals, or in a control
#    structure). Then remove in classes, variable writes that are not used after writing
#    (but not in control structures, globals or class data).
# 9. Remove variable writes in __main__, but first analysis to see what values are written
#    AND/OR READ in all other code first. So any writes not used later in main, that are not
#    accessed in any remaining functions.
# 10. Analyse the maximum temps needed per function. Do this by looking at each line and making
#     sure (i.e. rewriting the function) that simple temps number from 0 with no gaps. Find the
#     largest one, say n, in the function. Then for all loop control temps in the function,
#     scale them back to n+1, n+2, etc. Should be able to just subtract
#     (first-loop-temp-number - n - 1) from all loop control temps.
# DONE 11. Partition the variable use in each function -- args, temps, locals, globals. Args, temps
#     and locals will be on the stack. Store this info in the ProgramIR

def Optimise(programIR):
    """Take a program.Program object and modify it by running it through the optimiser
       passes."""

    io.Out.Top(io.TS.OPT_START, "Starting optimisation passes")
    rtc = 0

    try:
        programIR = EdPyConstantReplacement(programIR)
        #programIR.Dump()
        changed = True

        while changed:
            changed = False

            programIR, changes = ConstantRemoval(programIR)
            changed = changed or changes

            programIR, changes = SimpleVarRemoval(programIR)
            changed = changed or changes

        programIR, changes = RemoveUselessMarkers(programIR)

        programIR, changes = SimpleCallCollapse(programIR)

        # Fixup calls to Ed.List, Ed.TuneString, creating objects and self calls inside classes
        # This stage uses the edpy_values.signatures. After this stage it's not used again.
        programIR = FixUpCalls(programIR)

        # Verify that Ed.variables are only allowed ones, and that exactly one
        # value is written for each variable
        # Then when Ed.EdisonDistance units are know, rewrite ALL drive functions (other
        # then possible inline ones -- where all args are constant and they match a
        # particular pattern) to have the correct suffixes (_CM, _INCH, _TIME).
        # These do not have to be in edpy_values.signatures as FixupCalls is the only user of it.
        programIR = VerifyEdisonVariables(programIR)

        TypeVariables(programIR)

        VerifyClassData(programIR)

        VerifyConstantRange(programIR)

        programIR = RemoveUncalledFunctions(programIR)

        programIR = TempCollapsing(programIR)

    except program.EdPyError:
        rtc = 1
        # print("Exception")
        if (io.Out.IsReRaiseSet()):
            raise

    except:
        rtc = 1
        io.Out.Error(io.TS.CMP_INTERNAL_ERROR,
                     "file::: Compiler internal error {0}", 700)
        if (io.Out.IsReRaiseSet()):
            raise

    if (io.Out.GetInfoDumpMask() & io.DUMP.OPTIMISER):
        io.Out.DebugRaw("\nDump of internal representation after OPTIMISATION (rtc:{0}):".format(rtc))
        programIR.Dump()
        io.Out.DebugRaw("\n")

    if (rtc != 0):
        io.Out.DebugRaw("WARNING - OPTIMISER finished with an ERROR!!!\n")

    return rtc


def OptimiseFromFile(filename):
    pass

# Only to be used as a module
if __name__ == '__main__':
    io.Out.FatalRaw("This file is a module and can not be run as a script!")
