#!/usr/bin/env python2
# * **************************************************************** **
# File: program.py
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

""" Module contains Objects that represent the Ed.Py program """

from __future__ import print_function
from __future__ import absolute_import


class EdPyError(Exception):
    def __init__(self):
        pass


class ParseError(EdPyError):
    def __init__(self, rawmsg=""):
        self.rawmsg = rawmsg


class OptError(EdPyError):
    def __init__(self, rawmsg=""):
        self.rawmsg = rawmsg


class CompileError(EdPyError):
    def __init__(self, rawmsg=""):
        self.rawmsg = rawmsg


class AssemblerError(EdPyError):
    def __init__(self, rawmsg=""):
        self.rawmsg = rawmsg


class UnclassifiedError(Exception):
    def __init__(self, rawmsg):
        self.rawmsg = rawmsg


class Marker(object):
    """Mark each source line (but not worrying about column number)"""

    def __init__(self, line, col=None):
        self.kind = "Marker"
        self.line = line
        self.col = col

    def GetValues(self):
        return []

    def GetTarget(self):
        return None

    def __repr__(self):
        return "<program.Marker source line:{0}>".format(self.line)


class ControlMarker(object):
    """Marks start/else/end of If structures, While loops, For loops
       and Boolean Checks (for short-circuit evaluation). This marks a
       series of locations that tests can jump to."""

    def __init__(self, markerNumber, name, end="start"):
        self.kind = "ControlMarker"
        self.num = markerNumber
        self.name = name     # string - type of loop: "If", "While", "For", "Or", "And"
        self.end = end       # a string - one of "start", "else", "end"
        self.CheckData()

    def GetNumber(self):
        return self.num

    def CheckData(self):
        if (self.name not in ("If", "While", "For", "Or", "And")):
            raise UnclassifiedError("Invalid program.ControlMarker() name.")

        if (self.end not in ("start", "else", "end")):
            raise UnclassifiedError("Invalid program.ControlMarker() end.")

    def GetValues(self):
        return []

    def GetTarget(self):
        return None

    def __repr__(self):
        msg = "<program.ControlMarker marker:{0} {1} {2}>".format(self.num, self.name, self.end)
        return msg


class LoopControl(object):
    """Used at the top of If and While loops (where a test needs to be evaluated).
       The markerNumber is the same as used in ControlMarkers, so jumps to locations
       marked by the corresponding ControlMarker will be done."""

    def __init__(self, markerNumber, name=None, test=None):
        self.kind = "LoopControl"
        self.num = markerNumber
        self.name = name    # a string "If", "While"
        self.test = test    # a Value object. if evaluates to 0 then False, else True

    def GetValues(self):
        return [self.test]

    def GetTarget(self):
        return None

    def __repr__(self):
        msg = "<program.LoopControl {0}, name:{1}, test:{2}>".format(
            self.num, self.name, self.test)
        return msg


class LoopModifier(object):
    """Mark, inside ControlMarkers, Breaks and Continues. As the markerNumber
       is the same as the corresponding ControlMarker markerNumber, jumps to the
       "start" or "end" is easy."""

    def __init__(self, markerNumber, name=None):
        self.kind = "LoopModifier"
        self.num = markerNumber
        self.name = name    # a string "Pass", "Break", "Continue"

    def GetValues(self):
        return []

    def GetTarget(self):
        return None

    def __repr__(self):
        msg = "<program.LoopModifier {0}, name:{1}>".format(
            self.num, self.name)
        return msg


class ForControl(object):
    """In a for loop, this will check that arrayValue is still inside
       the array. If not a jump to the "end" of the corresponding ControlMarker
       will be made."""

    def __init__(self, markerNumber, arrayValue=None,
                 constantLimit=None, currentValue=None):
        self.kind = "ForControl"
        self.num = markerNumber
        self.arrayValue = arrayValue        # a value with name and iVariable
        self.constantLimit = constantLimit  # a value
        self.currentValue = currentValue    # a value

        if ((self.arrayValue is None and self.constantLimit is None) or
            (self.arrayValue is not None and self.constantLimit is not None) or
            (self.currentValue is None and self.constantLimit is not None) or
            (self.currentValue is not None and self.constantLimit is None)):
            raise UnclassifiedError("Invalid program.ForControl() condition.")

    def IsRange(self):
        return self.constantLimit is not None

    def IsArray(self):
        return self.arrayValue is not None

    def GetValues(self):
        if (self.IsArray()):
            return [self.arrayValue]
        else:
            return [self.constantLimit, self.currentValue]

    def GetTarget(self):
        return None

    def __repr__(self):
        msg = "<program.ForControl {0}, ".format(self.num)

        if (self.IsArray()):
            msg += "arrayValue:{0}>".format(self.arrayValue)
        else:
            msg += "constantLimit:{0}, currentValue:{1}>".format(self.constantLimit, self.currentValue)

        return msg


class BoolCheck(object):
    """In a BoolOp, there is a need to short-curcuit evaluation on pass (or) or
       failure (and). This object is used in each location where a value is
       checked, and possible short-curcuit eval. may require a jump to the
       "end" of the corresponding ControlMarker"""

    def __init__(self, markerNumber, op=None, value=None, target=None):
        """An binary operation on constants or variables, assigned to a variable"""
        self.kind = "BoolCheck"
        self.num = markerNumber
        self.op = op          # a string - the boolean op ("Or", "And", "Done")
                              # Done signifies to put the non-shortcircuit value in target
        self.value = value    # a Value object which has the left result of the op
        self.target = target  # a Value object which gets the result on short-circuit

    def GetValues(self):
        return [self.value]

    def GetTarget(self):
        return self.target

    def __repr__(self):
        return "<program.BoolCheck {0} {1} check:{2}, target{3}>".format(
            self.num, self.op, self.value, self.target)


class Value(object):
    """Stores an integer variable or constant or string constant, and depending on where it is used
       in the other objects, can represent a STORE or a LOAD. Note that for a
       STORE, this object can not represent a constant"""

    def __init__(self, constant=None, name=None, iConstant=None, iVariable=None,
                 strConst=None, listConst=None,
                 tsRef=None, listRef=None, objectRef=None):
        self.kind = "Value"
        self.name = name                # The name of the variable
        self.indexConstant = iConstant  # if not None, then the value is a slice at this index
        self.indexVariable = iVariable
        self.constant = constant        # if not None, then this is the value (integer)
        self.strConst = strConst          # if not None, then a string
        self.listConst = listConst        # if not None, then a list
        self.tsRef = tsRef              # if not None, then a reference to a tunestring variable
        self.listRef = listRef          # if not None, then a reference to a list variable
        self.objectRef = objectRef      # if not None, then a reference to an object variable

        self.loopTempStart = 9999       # All temps above this number are loop control temps

        # check that the object has been created consistently
        if (((self.IsIntConst()) and
             ((self.name is not None) or self.IsSlice() or
              self.IsStrConst() or self.IsListConst() or self.IsRef())) or

            ((self.IsStrConst()) and
             ((self.name is not None) or self.IsSlice() or self.IsRef() or
              self.IsListConst() or self.IsIntConst())) or

            ((self.IsListConst()) and
             ((self.name is not None) or self.IsSlice() or self.IsRef() or
              self.IsStrConst() or self.IsIntConst())) or

            (self.IsRef() and
             ((self.name is not None) or self.IsSlice() or
              self.IsStrConst() or self.IsListConst() or self.IsIntConst())) or

            ((self.indexConstant is not None) and (self.indexVariable is not None)) or
            ((self.indexConstant is not None) and (self.name is None)) or
            ((self.indexVariable is not None) and (self.name is None)) or

            ((self.tsRef is not None) and
             ((self.listRef is not None) or (self.objectRef is not None))) or
            ((self.listRef is not None) and
             ((self.tsRef is not None) or (self.objectRef is not None))) or
            ((self.objectRef is not None) and
             ((self.listRef is not None) or (self.tsRef is not None)))):

            raise UnclassifiedError("Invalid program.Value() constructor arguments")

    def IsIntConst(self):
        return self.constant is not None

    def IsStrConst(self):
        return (self.strConst is not None)

    def IsListConst(self):
        return (self.listConst is not None)

    def IsTSRef(self):
        return self.tsRef is not None

    def IsListRef(self):
        return self.listRef is not None

    def IsObjRef(self):
        return self.objectRef is not None

    def IsRef(self):
        return self.IsTSRef() or self.IsListRef() or self.IsObjRef()

    def IsConstant(self):
        return self.IsIntConst() or self.IsStrConst() or self.IsListConst()

    def IsSimpleVar(self):
        return (not (self.IsConstant() or self.IsSlice() or self.IsRef()))

    def IsSlice(self):
        return self.indexConstant is not None or self.indexVariable is not None

    def IsDotted(self):
        if (not self.IsTemp()):
            left, sep, right = self.name.partition(self.name)
            if (right != ""):
                return True
        return False

    def IsTemp(self):
        if self.IsSimpleVar():
            if type(self.name) is int:
                return True
        return False

    def IsSimpleTemp(self):
        return self.IsTemp() and (self.name < self.loopTempStart)

    def IsSliceWithSimpleTempIndex(self):
        return (self.IsSlice() and self.indexVariable is not None and
                type(self.indexVariable) is int and (self.indexVariable < self.loopTempStart))

    def IsSliceWithVarIndex(self):
        return self.IsSlice() and self.indexVariable is not None and type(self.indexVariable) is not int

    def IsAssignable(self):
        return not (self.IsRef() or self.IsConstant())

    def UsesValue(self, otherValue):
        if (otherValue.IsSimpleVar()):
            if ((self.IsSimpleVar() and self.name == otherValue.name) or
                (self.IsSlice() and self.indexVariable == otherValue.name)):
                return True
        elif (otherValue.IsSlice()):
            return self == otherValue

        return False

    def Name(self):
        if self.IsConstant():
            return "????"
        elif not self.IsSlice():
            if type(self.name) is int:
                return "TEMP-" + str(self.name)
            else:
                return self.name
        elif self.indexConstant is not None:
            return self.name + "[" + str(self.indexConstant) + "]"
        elif type(self.indexVariable) is int:
            return self.name + "[TEMP-" + str(self.indexVariable) + "]"
        else:
            return self.name + "[" + self.indexVariable + "]"

    def __eq__(self, rhs):
        return ((self.kind == rhs.kind) and
                (self.name == rhs.name) and
                (self.indexConstant == rhs.indexConstant) and
                (self.indexVariable == rhs.indexVariable) and
                (self.constant == rhs.constant) and
                (self.strConst == rhs.strConst) and
                (self.listConst == rhs.listConst) and
                (self.tsRef == rhs.tsRef) and
                (self.listRef == rhs.listRef) and
                (self.objectRef == rhs.objectRef))

    def GetValues(self):
        return [self]

    def GetTarget(self):
        return None

    def __repr__(self):
        if self.constant is not None:
            return "<program.Value const:{0}>".format(self.constant)
        elif self.IsStrConst():
            return "<program.Value const:\"{0}\">".format(self.strConst)
        elif self.IsListConst():
            return "<program.Value const:{0}>".format(self.listConst)
        elif self.IsTSRef():
            return "<program.Value T_Ref:{0}>".format(self.tsRef)
        elif self.IsListRef():
            return "<program.Value L_Ref:{0}>".format(self.listRef)
        elif self.IsObjRef():
            return "<program.Value O_Ref:{0}>".format(self.objectRef)
        else:
            return "<program.Value name:{0}>".format(self.Name())


class UAssign(object):
    """Represent an Unary Op with assignment to a variable (target)"""

    def __init__(self, target=None, op=None, operand=None):
        """A unary operation on constants or variables, assigned to a variable"""
        self.kind = "UAssign"
        self.target = target    # a value object
        self.operation = op     # a unary operation (could be UAdd for identity
        self.operand = operand  # (used for binary op or unary op) if used then a Value object

    def GetValues(self):
        if (self.operand is None):
            return []
        else:
            return [self.operand]

    def GetTarget(self):
        return self.target

    def __repr__(self):
        msg = "<program.UAssign {0} = ".format(self.target)
        msg += "{0} {1}>".format(self.operation, self.operand)

        return msg


class BAssign(object):
    """Represent a Binary Op (including logical tests) with assignment to
       a variable (target)"""

    def __init__(self, target=None, left=None, op=None, right=None):
        """An binary operation on constants or variables, assigned to a variable"""
        self.kind = "BAssign"
        self.target = target  # a value object
        self.left = left      # a Value object
        self.operation = op   # binary operation
        self.right = right    # a Value object

    def GetValues(self):
        return [self.left, self.right]

    def GetTarget(self):
        return self.target

    def __repr__(self):
        msg = "<program.BAssign {0} = ".format(self.target)
        msg += "{0} {1} {2}>".format(self.left, self.operation, self.right)
        return msg


class Call(object):
    """Calling a function, optionally assigning the result to a variable
       (if self.target is not None)."""
    def __init__(self, target=None, funcName=None, args=[]):
        self.kind = "Call"
        self.target = target      # a Value object OR CAN BE NONE!
        self.funcName = funcName  # a String
        self.args = args          # each arg is a Value object

    def GetValues(self):
        return self.args

    def GetTarget(self):
        if (self.target is None):
            return None
        else:
            return self.target

    def __repr__(self):
        msg = "<program.Call "
        if (self.target is not None):
            msg += "{0} = ".format(self.target)
        msg += "name:{0} with args:{1}>".format(self.funcName, self.args)
        return msg


class Return(object):
    """Return an explicit value (an int) or nothing from the function"""
    def __init__(self, returnValue=None):
        self.kind = "Return"
        self.returnValue = returnValue

    def IsVoidReturn(self):
        return self.returnValue is None

    def GetValues(self):
        if self.returnValue is None:
            return []
        else:
            return [self.returnValue]

    def GetTarget(self):
        return None

    def __repr__(self):
        return "<program.Return {0}>".format(self.returnValue)


# ######## Top level objects ##############################


class Function(object):
    def __init__(self, name, internalFunc = False):
        self.kind = "Function"
        self.name = name
        self.docString = ""
        self.internalFunction = internalFunc

        self.globalAccess = []  # Global variable names can write too
        self.localVar = {}      # local variable types (including temps)
        self.args = []

        self.callsTo = []       # functions called from this function

        self.maxSimpleTemps = 0  # Number of integer temps needed,
                                 # they will be from 0 - (maxSimpleTemps - 1).

        self.body = []  # contains objects of type 'Op', 'Call'
        self.returnsValue = False # explicit return with a value
        self.returnsNone = False  # explicit return but with no value

    def __repr__(self):
        msg = "<program.Function name:{0}, doc:|{1}|, ".format(
            self.name, self.docString)

        msg += "args:{0}, lclVars:{1}, glbWriteVars:{2}, maxSimpleTemps:{3}, internal:{4}".format(
            self.args, self.localVar, self.globalAccess, self.maxSimpleTemps, self.internalFunction)

        return msg + "returnsValue:{0}, calls:{1}, body:{2}>".format(
            self.returnsValue, self.callsTo, self.body)

    def IsInternalFunction(self):
        return self.internalFunction


class Class(object):
    def __init__(self, name):
        self.kind = "Class"
        self.name = name
        self.docString = ""
        self.funcNames = []

    def __repr__(self):
        return "<program.Class name:{}, doc:|{}|, funcNames:{}>".format(
            self.name, self.docString, self.funcNames)


class Program(object):
    def __init__(self):
        self.kind = "Program"
        self.EdVariables = {}
        self.Import = []
        mainFunction = Function("__main__")
        self.Function = {"__main__": mainFunction}
        self.FunctionSigDict = {}
        self.EventHandlers = {}
        self.globalVar = {}
        self.GlobalTypeDict = {}
        self.Class = {}

        self.indent = 0

    def __repr__(self):
        return "<program.Program Import:{}, Global:{}, Function:{}, Class:{}>".format(
            self.Import, self.globalVar, self.Function, self.Class)

    def Print(self, prefix="", *vars):
        if (prefix == "" and len(vars) == 0):
            print()
        else:
            if (prefix.startswith('\n')):
                print()
                prefix = prefix[1:]

            indentSpaces = " " * (self.indent)
            if (prefix):
                print(indentSpaces, prefix, sep='', end='')
            else:
                print(indentSpaces, end='')

            for v in vars:
                print(' ', v, sep='', end='')
            print()

    def Dump(self, filterOutInternals=True):
        """Dump the full program"""
        self.Print("Program")
        self.Print("\Edison variables:", self.EdVariables)
        self.Print("\nImports:", self.Import)
        self.Print("\nGlobals:", self.globalVar)
        self.Print("\nClasses:", self.Class)
        self.Print("\nFunctions:", self.Function.keys())
        self.Print("\nFunction Sigs:", self.FunctionSigDict)
        self.Print("\nEvent Handlers:", self.EventHandlers)
        self.Print("\nFunction Details:")
        self.indent += 2
        sigsPrinted = []
        for i in self.Function:
            if (filterOutInternals and self.Function[i].IsInternalFunction()):
                continue
            self.Print()
            f = self.Function[i]
            if (f.IsInternalFunction()):
                name = "{}-internal".format(i)
            else:
                name = i
            self.Print("", name)
            self.indent += 2
            self.Print("Args:", f.args)
            if (i in self.FunctionSigDict):
                sigsPrinted.append(i)
                self.Print("Signature:", self.FunctionSigDict[i])
            self.Print("Globals can write:", f.globalAccess)
            self.Print("Local vars:", f.localVar)
            self.Print("Max simple temps:", f.maxSimpleTemps)
            self.Print("Functions called:", f.callsTo)

            self.indent += 2
            for l in f.body:
                if (l.kind == "Marker"):
                    self.Print()
                self.Print("", l)
            self.indent -= 4
        self.indent -= 2


        # header = "\nExternal functions:"
        # for i in self.FunctionSigDict:
        #     if (i not in sigsPrinted):
        #         if header:
        #             self.Print(header)
        #             header = None
        #         self.Print("External function:", i)
        #         self.indent += 2
        #         self.Print("Signature:", self.FunctionSigDict[i])
        #         self.indent -= 2
