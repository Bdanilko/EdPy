#!/usr/bin/env python2
# * **************************************************************** **
# File: parser.py
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

""" Module to use python ast to parse an Ed.Py program, error check,
    and convert to an internal program representation. """

from __future__ import print_function
from __future__ import absolute_import

import ast
import re

# from . import util
from . import io
from . import program
from . import edpy_code

# ############ utility functions ########################################


def Name(node):
    className = str(node.__class__)
    match = re.match("\<class '_ast.([a-zA-Z]*)'\>.*", className)
    if match is None:
        io.Out.FatalRaw("ERROR - bad re")

    return match.group(1)


# def CheckTarget(node):
#     if ((Name(node) == "Name") or
#        ((Name(node) == "Attribute") and (Name(node.value) == "Name") and
#         (node.value.id == "self")) or CheckSlice(node)):
#         return
#     else:
#         io.Out.Error(io.TS.PARSE_SYNTAX_ERROR, "file:{0}:{1}: Syntax error",
#                      node.lineno, node.col_offset)
#         raise program.ParseError


def CheckCall(node):
    if (Name(node) != "Call"):
        raise RuntimeError("CheckCall() called with wrong argument")

    if ((len(node.keywords) == 0) and     # no keywords
        (getattr(node, "starargs", None) is None) and  # no starargs Py2
        (getattr(node, "kwargs", None) is None) and     # no kwargs Py2
        # TODO: check for Py3 starargs and kwargs
        GetVarName(node.func)):
        return GetVarName(node.func)
    else:
        io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                     "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                     node.lineno, node.col_offset, "CALL")
        raise program.ParseError


def GetVarName(node, noException=None):
    if (Name(node) == "Name"):
        return node.id
    elif ((Name(node) == "Attribute") and
          (Name(node.value) == "Name")):
        return node.value.id + "." + node.attr
    else:
        if noException is not None:
            return None
        else:
            io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                         "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                         node.lineno, node.col_offset, "CALL")
            raise program.ParseError


def CheckSlice(node):
    """Return True if a simple Subscript. If complex Subscript then throw."""
    nodeName = Name(node)
    if (nodeName == "Subscript"):
        # is it simple enough?
        if ((Name(node.value) != "Name") or     # only support a name for the slice variable
            (Name(node.slice) != "Index")):     # only support a simple index for the slice
                                                # though Index can be an expression

            io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                         "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                         node.lineno, node.col_offset, "ARRAY")
            raise program.ParseError
        return True
    return False


def CheckCompare(node):
    if (Name(node) != "Compare"):
        raise RuntimeError("CheckCompare() called with wrong argument")

    if ((len(node.ops) != 1) or     # no keywords
        (len(node.comparators) != 1)):

        io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                     "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                     node.lineno, node.col_offset, "COMPARE")
        raise program.ParseError

    if (Name(node.ops[0]) in ("In", "NotIn", "Is", "NotIs")):
        io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                     "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                     node.lineno, node.col_offset, "In/Is ")
        raise program.ParseError


def CheckWhile(node):
    # While(expr test, stmt* body, stmt* orelse)
    # Don't handle the orelse which is a 'else' clause
    if (Name(node) != "While"):
        raise RuntimeError("CheckWhile() called with wrong argument")

    if ((len(node.orelse) > 0)):             # no orelse
        io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                     "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                     node.lineno, node.col_offset, "WHILE")
        raise program.ParseError


def CheckFor(node):
    # For(expr target, expr iter, stmt* body, stmt* orelse)
    # target is the variable, iter is the array to be iterated over.
    # orelse is an 'else' clause which we don't handle
    if (Name(node) != "For"):
        raise RuntimeError("CheckFor() called with wrong argument")

    if ((len(node.orelse) > 0) or               # no orelse
        (Name(node.target) not in ("Name"))):  # want simple name

        io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                     "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                     node.lineno, node.col_offset, "FOR")
        raise program.ParseError

    if (Name(node.iter) == "Name"):
        return "Name"

    if ((Name(node.iter) != "Call") or (CheckCall(node.iter) != "range") or
        (len(node.iter.args) != 1) or
        ((Name(node.iter.args[0]) != "Num") and GetVarName(node.iter.args[0], False) is None)):
        io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                     "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                     node.lineno, node.col_offset, "FOR")
        raise program.ParseError

    return "Range"


def CheckNum(node):
    # verify that this is an integer
    if (Name(node) != "Num"):
        raise RuntimeError("CheckNum() called with wrong argument")

    # print("CheckNum with node:", node, "node.n:", node.n)

    if (isinstance(node.n, int) == False):
        io.Out.Error(io.TS.PARSE_CONST_NOT_INT,
                     "file:{0}:{1}: Syntax Error, constant {2} must be an integer value",
                     node.lineno, node.col_offset, node.n)
        raise program.ParseError

    # return them actual integer number
    return node.n


# ############ Class to convert from python ast to programIR  ################


class Converter(object):

    def __init__(self, programIR):
        self.program = programIR
        self.returnCode = 0
        self.ctlMarker = -1     # this value is pre-incremented before use
        self.loopStack = []     # used to associate break/continue with the enclosing while/for
        self.forIndex = 10000   # temp var used in for loops. Stay out of normal temp var way

    def WalkProgram(self, node):
        """Want to see a module node"""
        if (Name(node) != "Module"):
            io.Out.FatalRaw("Program needs to start with a Module node")

        # parse statements (and expressions for the doc strings)
        for s in node.body:
            name = Name(s)
            if (name == "FunctionDef"):
                # add a new function
                self.AddFunction(s)
            elif (name == "Import"):
                self.AddImport(s)
            elif (name == "ClassDef"):
                self.AddClass(s)
            else:
                self.AddFunctionStatement(self.program.Function["__main__"], s)

        return self.returnCode

    def WalkEdRoutines(self, node):
        """Walk the code for the Ed routines and add Ed. infront of the function names"""
        if (Name(node) != "Module"):
            io.Out.FatalRaw("Program needs to start with a Module node")

        # parse statements (and expressions for the doc strings)
        for s in node.body:
            name = Name(s)
            if (name == "FunctionDef"):
                # add a new function
                self.AddEdFunction(s)
            elif (name == "Import"):
                # ignore imports - so can have import Ed in code file
                pass
            elif (name == "ClassDef"):
                # ignore
                io.Out.FatalRaw("Ed internal functions must not have classes")
            else:
                # ignore anything not in a function
                pass

        return self.returnCode

    def AddEdFunction(self, node):
        """Add an Ed function to the program"""

        className = ""
        if (node.name.startswith("Ed_")):
            nodeName = "Ed." + node.name[3:]
        else:
            nodeName = node.name

        io.Out.DebugRaw("Adding Ed. function:", nodeName, node.__dict__)

        if (nodeName in self.program.Function):
            io.Out.Error(io.TS.PARSE_NAME_REUSED,
                         "file:{0}:{1}: Syntax Error, two {2} with the same name",
                         node.lineno, node.col_offset, "FUNCTIONS")
            raise program.ParseError

        if (len(node.decorator_list) > 0):
            io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                         "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                         node.lineno, node.col_offset, "DECORATORS ")
            raise program.ParseError

        try:
            paramNames = CheckGetParamNames(node)
        except:
            io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                         "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                         node.lineno, node.col_offset, "FUNCTION")
            raise program.ParseError
            
        
        # get all of the stuff in the function!
        newFunction = program.Function(nodeName, True)
        newFunction.args.extend(paramNames)

        # Enforce that all class methods first arg is always 'self'. Basically
        # good style and makes parsing and optimising easier.
        if (len(className) > 0):
            if ((len(newFunction.args) == 0) or (newFunction.args[0] != "self")):
                io.Out.Error(io.TS.PARSE_CLASS_ARG0_NOT_SELF,
                             "file:{0}:{1}: Syntax Error, first method arg must be 'self'",
                             node.lineno, node.col_offset)
                raise program.ParseError

        self.loopStack = []
        for s in node.body:
            self.AddFunctionStatement(newFunction, s)

        self.program.Function[nodeName] = newFunction

    def AddFunction(self, node, className=""):
        """Add a function to the program"""
        if (len(className) > 0):
            nodeName = className + "." + node.name
        else:
            nodeName = node.name

        io.Out.DebugRaw("Adding function:", nodeName, node.__dict__)

        if (nodeName in self.program.Function):
            io.Out.Error(io.TS.PARSE_NAME_REUSED,
                         "file:{0}:{1}: Syntax Error, two {2} with the same name",
                         node.lineno, node.col_offset, "FUNCTIONS")
            raise program.ParseError

        if (len(node.decorator_list) > 0):
            io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                         "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                         node.lineno, node.col_offset, "DECORATORS ")
            raise program.ParseError

        try:
            paramNames = CheckGetParamNames(node)
        except:
            io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                         "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                         node.lineno, node.col_offset, "FUNCTION")
            raise program.ParseError
        
        # get all of the stuff in the function!
        newFunction = program.Function(nodeName)
        newFunction.args.extend(paramNames)

        # Enforce that all class methods first arg is always 'self'. Basically
        # good style and makes parsing and optimising easier.
        if (len(className) > 0):
            if ((len(newFunction.args) == 0) or (newFunction.args[0] != "self")):
                io.Out.Error(io.TS.PARSE_CLASS_ARG0_NOT_SELF,
                             "file:{0}:{1}: Syntax Error, first method arg must be 'self'",
                             node.lineno, node.col_offset)
                raise program.ParseError

        self.loopStack = []
        for s in node.body:
            self.AddFunctionStatement(newFunction, s)

        self.program.Function[nodeName] = newFunction

    def AddFunctionStatement(self, function, node):
        name = Name(node)
        if (name in ("Assign", "AugAssign")):
            self.AddAssignStatement(function, node)
        elif (name == "Expr") and Name(node.value) == "Call":
            self.AddCallStatement(function, node.value)
        elif (name in ("While", "If")):
            # While(expr test, stmt* body, stmt* orelse)
            # If(expr test, stmt* body, stmt* orelse)

            if (name == "While"):
                CheckWhile(node)

            # line marker here to encompass the ControlMarker
            function.body.append(program.Marker(node.lineno, node.col_offset))

            # Create a control marker for this loop construct
            self.ctlMarker += 1
            markerNumber = self.ctlMarker

            # whileStack allows us to associate break/continue with the correct
            if (name == "While"):
                self.loopStack.append((name, markerNumber),)
                # print("LoopStack:", self.loopStack)

            function.body.append(program.ControlMarker(markerNumber, name, "start"))
            self.AddControlStatement(function, node, markerNumber)
            if (len(node.body) > 0):
                for l in node.body:
                    self.AddFunctionStatement(function, l)
            if (len(node.orelse) > 0):
                function.body.append(program.ControlMarker(markerNumber, name, "else"))
                for l in node.orelse:
                    self.AddFunctionStatement(function, l)
            function.body.append(program.ControlMarker(markerNumber, name, "end"))

            if (name == "While"):
                self.loopStack.pop()
                # print("LoopStack:", self.loopStack)

        elif (name in ("For")):
            # For(expr target, expr iter, stmt* body, stmt* orelse)
            # This is like a while loop but with assignment to an iterator
            # Only handle "for i in list" right now
            forType = CheckFor(node)

            # line marker here to encompass the ControlMarker
            function.body.append(program.Marker(node.lineno, node.col_offset))

            # Create a control marker for this loop construct
            self.ctlMarker += 1
            markerNumber = self.ctlMarker
            self.loopStack.append((name, markerNumber),)

            self.forIndex += 1
            forIndexTempNumber = self.forIndex
            forIndexValue = program.Value(name=forIndexTempNumber)

            # create a control value starting at -1 as we will preincrement

            function.body.append(program.UAssign(forIndexValue, "UAdd", program.Value(constant=-1)))

            function.body.append(program.ControlMarker(markerNumber, name, "start"))

            # increment forIndex
            function.body.append(program.BAssign(forIndexValue, forIndexValue, "Add",
                                                 program.Value(constant=1)))

            if (forType == "Range"):

                varName = GetVarName(node.iter.args[0], False)
                if (varName is not None):
                    limit = program.Value(name=varName)
                else:
                    limit = program.Value(constant=node.iter.args[0].n)

                # check that forIndexValue is in range of arrayName. If not then goto
                # the end control marker
                function.body.append(program.ForControl(markerNumber,
                                                        constantLimit=limit,
                                                        currentValue=forIndexValue))

                # set the value of the iterator
                function.body.append(program.UAssign(program.Value(name=node.target.id), "UAdd",
                                                     forIndexValue))

            else:
                arrayName = node.iter.id

                # check that forIndexValue is in range of arrayName. If not then goto
                # the end control marker
                function.body.append(program.ForControl(markerNumber,
                                                        arrayValue=program.Value(name=arrayName,
                                                                                 iVariable=forIndexTempNumber)))

                # set the value of the iterator
                function.body.append(program.UAssign(program.Value(name=node.target.id), "UAdd",
                                                     program.Value(name=arrayName,
                                                                   iVariable=forIndexTempNumber)))

            # the body of the for loop
            if (len(node.body) > 0):
                for l in node.body:
                    self.AddFunctionStatement(function, l)

            # This "for-end" will jump back to "for-start" with the same markerNumber
            function.body.append(program.ControlMarker(markerNumber, name, "end"))

            self.loopStack.pop()

        elif (name == "Global"):
            # Global has to be before any other executable statements in
            # the function (so easier for the students, and the compiler)!
            ok = (function.name != "__main__")
            if ok:
                for op in function.body:
                    if (op not in ("Marker", "Global")):
                        ok = False
                        break

            if not ok:
                io.Out.Error(io.TS.PARSE_GLOBAL_ORDER,
                             "file:{0}:{1}: Syntax error, globals must be first in functions",
                             node.lineno, node.col_offset)
                raise program.ParseError

            self.AddSimpleStatement(function, node)

        elif (name == "Return"):
            self.AddSimpleStatement(function, node)

        elif (name in ("Pass", "Break", "Continue")):
            if (name == "Pass"):
                pass   # drop "Pass" as it doesn't do anything
            else:
                # Simple program objects with the last while/for loop ctlMarker
                # to denote which control structure it modifies
                if (self.loopStack):
                    self.AddControlModifier(function, node, self.loopStack[-1][1])
                else:
                    io.Out.Error(io.TS.PARSE_NOT_IN_LOOP,
                                 "file:{0}:{1}: Syntax error, statement must be inside a loop",
                                 node.lineno, node.col_offset)
                    raise program.ParseError

        elif (name == "Expr") and Name(node.value) == "Str":
            function.docString = node.value.s
            io.Out.DebugRaw("Doc string:", node.value.s, function)
        else:
            io.Out.Error(io.TS.PARSE_INVALID_STATEMENT,
                         "file:{0}:{1}: Syntax error, statement not valid here",
                         node.lineno, node.col_offset)
            io.Out.DebugRaw("Invalid statement type:", name, node.__dict__)
            raise program.ParseError

    def AddAssignStatement(self, function, node):
        """Handle an assign or augmented assign, by reducing the ast
           embedded nodes to a list of assignments to temp variables."""

        line = node.lineno
        function.body.append(program.Marker(line, node.col_offset))
        name = Name(node)
        io.Out.DebugRaw("ASSIGN Statement:", name, node.__dict__)

        tempCount = 0
        statementList = []

        augOp = None
        if (name == "AugAssign"):
            augOp = Name(node.op)
            io.Out.DebugRaw("AugOp:", augOp)
            targetExpr = node.target
        elif (name == "Assign"):
            if (len(node.targets) != 1):
                io.Out.Error(io.TS.PARSE_SYNTAX_ERROR, "file:{0}:{1}: Syntax error",
                             node.lineno, node.offset)
                raise program.ParseError
            targetExpr = node.targets[0]

        # Evaluate the right hand side (the value)
        tempCount = self.HandleExpr(node.value, statementList, tempCount, line)
        # result of the right side of the = is now assigned to temp:0
        rhsStatements = len(statementList)

        # Evaluate the left hand side (the target) -- in case there is subscripting to be evaluated
        # The result of HandleExpr will be an UAssign() -- the operand of that will be the target
        tempCount = self.HandleExpr(targetExpr, statementList, tempCount, line)

        if ((len(statementList) == rhsStatements) or        # Make sure that evaluating target made
                                                            # a statement,
            (statementList[-1].kind != "UAssign") or        # and it is as expected.
            (statementList[-1].operation != "UAdd") or
            (statementList[-1].operand.IsConstant())):

            io.Out.Error(io.TS.PARSE_SYNTAX_ERROR, "file:{0}:{1}: Syntax error",
                         node.lineno, node.offset)
            raise program.ParseError

        target = statementList[-1].operand

        if (augOp is not None):
            # unrolling the AugAssign into a binary operation
            statementList[-1] = program.BAssign(target, target, augOp, program.Value(name=0))
        else:
            statementList[-1] = program.UAssign(target, "UAdd", program.Value(name=0))

        # Add the statementList to the function body
        for l in statementList:
            function.body.append(l)
            io.Out.DebugRaw("\t", l)

    def AddSimpleStatement(self, function, node):
        """Handle a return or a global"""

        line = node.lineno
        function.body.append(program.Marker(line, node.col_offset))
        name = Name(node)
        io.Out.DebugRaw("SIMPLE Statement:", name, node.__dict__)

        tempCount = 0
        statementList = []

        if (name == "Return"):
            if (node.value is None):
                if (function.returnsValue):
                    io.Out.Error(io.TS.PARSE_MIXED_RETURNS,
                                 "file:{0}:{1}: Syntax Error, all returns in a function must return a value or return nothing",
                         node.lineno, node.col_offset)
                    raise program.ParseError
                function.body.append(program.Return())
                function.returnsNone = True
            else:
                if (function.returnsNone):
                    io.Out.Error(io.TS.PARSE_MIXED_RETURNS,
                                 "file:{0}:{1}: Syntax Error, all returns in a function must return a value or return nothing",
                         node.lineno, node.col_offset)
                    raise program.ParseError
                returnTemp = tempCount
                self.HandleExpr(node.value, statementList, tempCount, line)

                for l in statementList:
                    function.body.append(l)
                    io.Out.DebugRaw("\t", l)

                function.body.append(program.Return(program.Value(name=returnTemp)))
                function.returnsValue = True
        else:
            # Add the global names directly into the function as it's before
            # any other statements in the function, order doesn't matter
            for n in node.names:
                if (n not in function.globalAccess):
                    function.globalAccess.append(n)

    def AddCallStatement(self, function, node):
        """Handle a 'call' by reducing the ast
           embedded nodes to a list of assignments to temp variables.
           Call is added here as it can be assigned to null if it is called
           outside a normal assign."""

        line = node.lineno
        function.body.append(program.Marker(line, node.col_offset))
        io.Out.DebugRaw("CALL Statement:", Name(node), node.__dict__)
        CheckCall(node)

        tempCount = 0
        statementList = []

        self.HandleExpr(node, statementList, tempCount, line)

        # the last line will be the call, assigned to variable:0. Remove the assignment

        if ((len(statementList) == 0) or                    # Make sure that evaluating target made
                                                            # a statement,
            (statementList[-1].kind != "Call")):            # and it is as expected.

            io.Out.Error(io.TS.PARSE_SYNTAX_ERROR, "file:{0}:{1}: Syntax error",
                         node.lineno, node.offset)
            raise program.ParseError

        statementList[-1].target = None

        for l in statementList:
            function.body.append(l)
            io.Out.DebugRaw("\t", l)

        # No need to add the final call as modified the last in the list

    def AddControlStatement(self, function, node, ctlMarker):
        """Handle an if or while statement - self.ctlMarker holds the  current loop"""

        line = node.lineno
        # line Marker was added by the caller

        name = Name(node)
        io.Out.DebugRaw("CONTROL Statement:", name, node.__dict__)

        tempCount = 0
        statementList = []

        # evaluate the test into a single variable
        tempCount = self.HandleExpr(node.test, statementList, tempCount, line)

        for l in statementList:
            function.body.append(l)
            io.Out.DebugRaw("\t", l)

        # add in the actual test code which uses the statements from the expression handler
        function.body.append(program.LoopControl(ctlMarker, name, program.Value(name=0)))

    def AddControlModifier(self, function, node, ctlMarker):
        """Handle a pass/break/continue statement - self.ctlMarker holds the  current loop"""

        line = node.lineno
        function.body.append(program.Marker(line, node.col_offset))
        name = Name(node)
        io.Out.DebugRaw("CONTROL Statement:", name, node.__dict__)

        function.body.append(program.LoopModifier(ctlMarker, name))

    def HandleExpr(self, node, statementList, tempCount, lineNo=None):
        """Convert expressions to assignments to tempCount in the statementList.
           Return the new tempCount"""

        # io.Out.DebugRaw("HandleExpr:{0}, list:{1}, tempCount:{2}".format(
        #     node, statementList, tempCount))

        nodeName = Name(node)
        target = program.Value(name=tempCount)  # Simple target to a temporary

        io.Out.DebugRaw("Value:", nodeName, node.__dict__)

        # Handle all terminals first

        if (nodeName == "Num"):
            CheckNum(node)
            # assign this to tempCount and return
            operand = program.Value(constant=node.n)
            statementList.append(program.UAssign(target, "UAdd", operand))
        elif (nodeName == "Name"):
            # assign this to tempCount and return
            operand = program.Value(name=node.id)
            statementList.append(program.UAssign(target, "UAdd", operand))
        elif (nodeName == "NameConstant"):
            # These nodes exist in Python 3
            operand = program.Value(name=str(node.value))
            statementList.append(program.UAssign(target, "UAdd", operand))
        elif (nodeName == "Attribute"):
            if (Name(node.value) == "Name"):
                operand = program.Value(name=node.value.id + "." + node.attr)
                statementList.append(program.UAssign(target, "UAdd", operand))
            else:
                io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                             "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                             lineNo, 0, "nested classes ")
                raise program.ParseError

        elif (nodeName == "Str"):
            # Only valid in Ed.TuneString() or ord() -- that error will be caught in the optimiser

            # if (len(node.s) != 1):
            #     io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
            #                  "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
            #                  lineNo, 0, "STRINGS ")
            #     raise program.ParseError

            # take the ord of the string, and assign this to tempCount and return
            operand = program.Value(strConst=node.s)
            statementList.append(program.UAssign(target, "UAdd", operand))

        elif (nodeName == "List"):
            # Only valid in Ed.List() -- that error will be caught in the optimiser

            # all of the elts must be just numbers! Should be able to handled vars, slices, functions,
            # etc. but too hard. Code can be written to initialise each value if the programmer wants.
            listInit = []
            for e in node.elts:
                if (Name(e) != "Num"):
                    io.Out.Error(io.TS.PARSE_TOO_COMPLEX,
                                 "file:{0}:{1}: Syntax Error, {2} code too complex for Ed.Py",
                                 node.lineno, node.col_offset, "LIST INIT")
                    raise program.ParseError

                CheckNum(e)
                listInit.append(e.n)

            operand = program.Value(listConst=listInit)
            statementList.append(program.UAssign(target, "UAdd", operand))

        elif (nodeName == "Subscript"):
            CheckSlice(node)
            # now know that the Name(node.value) == "Name" and Name(node.slice) == "Index"
            tempCount += 1
            operand = program.Value(name=node.value.id, iVariable=tempCount)
            # make another 1 or more assignment, return the next possible tempCount
            tempCount = self.HandleExpr(node.slice.value, statementList, tempCount, lineNo)
            statementList.append(program.UAssign(target, "UAdd", operand))

        elif (nodeName == "UnaryOp"):
            tempCount += 1
            operand = program.Value(name=tempCount)
            tempCount = self.HandleExpr(node.operand, statementList, tempCount, lineNo)
            statementList.append(program.UAssign(target, Name(node.op), operand))

        elif (nodeName == "BinOp"):
            op = Name(node.op)

            # do we support this operation?
            if (op in ("Pow")):
                io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                             "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                             lineNo, 0, "POWER ")
                raise program.ParseError

            # TODO: Evaluating left before right. Do we have to be more intelligent here?
            tempCount += 1
            left = program.Value(name=tempCount)
            tempCount = self.HandleExpr(node.left, statementList, tempCount, lineNo)
            tempCount += 1
            right = program.Value(name=tempCount)
            tempCount = self.HandleExpr(node.right, statementList, tempCount, lineNo)
            statementList.append(program.BAssign(target, left, op, right))

        elif (nodeName == "BoolOp"):
            # BoolOp(boolop op, expr* values)
            # BoolOp is strange as it can have a chain (more then 2) values,
            # including other BoolOps. So a or b or c and d has op OR, with values
            # (a, b, BoolOp(AND, (c, d)). Also it has short-circuit evaluation!

            # Algorithm: for values (a, b, c) and op OP:
            # 1. Bookmark this code with start and end markers with a nesting number
            # 2. Evaluate a
            # 3. Check if evaluation can be shortcircuited. If so set value and goto end
            # 4. Do 2 and 3 for all values
            # 5. If No shortcircuit, then set value to False for OR, True for AND, Done

            op = Name(node.op)
            self.ctlMarker += 1
            marker = self.ctlMarker

            resultTemp = tempCount

            # Mark start of BoolOp - name will be "And" or "Or"
            statementList.append(program.ControlMarker(marker, op, "start"))

            for v in node.values:
                tempCount += 1
                check = program.BoolCheck(marker, op, program.Value(name=tempCount),
                                          program.Value(name=resultTemp))
                tempCount = self.HandleExpr(v, statementList, tempCount, lineNo)
                statementList.append(check)

            if (op == "Or"):
                resultValue = program.Value(constant=0)
            else:
                resultValue = program.Value(constant=1)

            statementList.append(program.BoolCheck(marker, "Done", resultValue,
                                                   program.Value(name=resultTemp)))

            statementList.append(program.ControlMarker(marker, op, "end"))

        elif (nodeName == "Call"):
            # Call(expr func, expr* args, keyword* keywords, expr? starargs, expr? kwargs)
            # only func and args are valid
            funcName = CheckCall(node)
            # print (funcName)

            # Each arg can reuse temps -- in optimisation will check locality of
            # temps in a line and use the same temp if it doesn't overlap. But for
            # now, use different temps to keep the code simple
            args = []
            for a in node.args:
                tempCount += 1
                args.append(program.Value(name=tempCount))
                tempCount = self.HandleExpr(a, statementList, tempCount, lineNo)
            statementList.append(program.Call(target, funcName, args))

        elif (nodeName == "Compare"):
            # Compare(expr left, compop* ops, expr* comparators)
            CheckCompare(node)

            op = Name(node.ops[0])
            rhs = node.comparators[0]

            # TODO: Evaluating left before right. Do we have to be more intelligent here?
            tempCount += 1
            left = program.Value(name=tempCount)
            tempCount = self.HandleExpr(node.left, statementList, tempCount, lineNo)
            tempCount += 1
            right = program.Value(name=tempCount)
            tempCount = self.HandleExpr(rhs, statementList, tempCount, lineNo)
            statementList.append(program.BAssign(target, left, op, right))

        else:
            io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                         "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                         lineNo, 0, nodeName + " expr ")
            raise program.ParseError

        return tempCount

    def AddClass(self, node):
        """Add a function to the program"""
        io.Out.DebugRaw("Adding class:", node.name, node.__dict__)

        if (node.name in self.program.Class):
            io.Out.Error(io.TS.PARSE_NAME_REUSED,
                         "file:{0}:{1}: Syntax Error, two {2} with the same name",
                         node.lineno, node.col_offset, "CLASSES")

        if (len(node.decorator_list) > 0):
            io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                         "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                         node.lineno, node.col_offset, "DECORATORS ")
            raise program.ParseError

        if (len(node.bases) > 0):
            io.Out.Error(io.TS.PARSE_CLASS_NO_BASES_ALLOWED,
                         "file:{0}:{1}: Syntax Error, base classes are not allowed in Ed.Py",
                         node.lineno, node.col_offset)
            raise program.ParseError

        # Checks for using Ed as both a class and import is done in Opt
        newClass = program.Class(node.name)

        for e in node.body:
            name = Name(e)
            if (name == "FunctionDef"):
                # add a new function
                self.AddFunction(e, node.name)
                newClass.funcNames.append(e.name)
            elif (name == "Expr") and Name(e.value) == "Str":
                newClass.docString = e.value.s
                io.Out.DebugRaw("Doc string:", e.value.s, newClass)
            else:
                # only allow functions in class defintions
                io.Out.Error(io.TS.PARSE_CLASS_ALL_STATEMENTS_IN_FUNCTIONS,
                             "file:{0}:{1}: Syntax Error, in classes all statements must be in methods",
                             e.lineno, e.col_offset)
                raise program.ParseError

        self.program.Class[node.name] = newClass

    def AddImport(self, node):
        io.Out.DebugRaw("Adding import:", node.__dict__)
        if ((len(node.names) != 1) or (Name(node.names[0]) != "alias") or
            (node.names[0].asname is not None)):
            io.Out.Error(io.TS.PARSE_NOT_SUPPORTED,
                         "file:{0}:{1}: Syntax Error, {2}not supported in Ed.Py",
                         node.lineno, node.col_offset, "AS ")
            raise program.ParseError

        if ((len(self.program.Function) > 0 and "__main__" not in self.program.Function) or
            (len(self.program.Function) > 1) or (len(self.program.Class) > 0)):
            io.Out.Error(io.TS.PARSE_IMPORT_ORDER,
                         "file:{0}:{1}: Syntax error, imports must be before functions and classes",
                         node.lineno, node.col_offset)
            raise program.ParseError

        if (node.names[0].name != "Ed"):
            io.Out.Error(io.TS.PARSE_IMPORT_NOT_ED,
                         "file:{0}:{1}: Syntax error, only the Ed module can be imported",
                         node.lineno, node.col_offset)
            raise program.ParseError

        importName = node.names[0].name
        self.program.Import.append(importName)


def ConvertToIR(topNode, programIR, internalAst):
    c = Converter(programIR)

    try:
        rtc = c.WalkProgram(topNode)
        if (rtc == 0):
            # pass
            rtc = c.WalkEdRoutines(internalAst)

    except program.EdPyError:
        # Error was already raised
        rtc = 1
        if (io.Out.IsReRaiseSet()):
            raise

    except :
        rtc = 1
        io.Out.Error(io.TS.CMP_INTERNAL_ERROR,
                     "file::: Compiler internal error {0}", 701)
        if (io.Out.IsReRaiseSet()):
            raise

    return rtc


def Parse(filename, programIR):
    """Take a filename and a program IR and fill the program IR"""

    io.Out.Top(io.TS.PARSE_START, "Starting parse of file:{0}", filename)

    try:
        fh = open(filename, "rb")
        src = b"".join(fh.readlines())
        fh.close()
    except Exception:
        io.Out.Error(io.TS.FILE_OPEN_ERROR, "file:0: Could not access file {0}", filename)
        if (io.Out.IsReRaiseSet()):
            raise

        return 1

    return ParseString(src, filename, programIR)


def NormalPythonParse(programString, filename):
    """ Run python parser on the program to come up with an AST"""

    try:
        a = ast.parse(programString, filename)
    except SyntaxError as s:
        io.Out.Error(io.TS.PARSE_SYNTAX_ERROR, "file:{0}:{1}: Syntax error",
                     s.lineno, s.offset)
        if (io.Out.IsReRaiseSet()):
            raise
        return 2, None
    except TypeError:
        io.Out.Error(io.TS.BAD_INPUT_CHARS, "file:0: Illegal character in {0}", filename)
        if (io.Out.IsReRaiseSet()):
            raise
        return 2, None

    except Exception:
        io.Out.Error(io.TS.PARSE_ERROR, "file:0: There was an error parsing {0}", filename)
        if (io.Out.IsReRaiseSet()):
            raise
        return 2, None

    return 0, a


def ParseString(programString, filename, programIR):
    """Take programString (which is source lines ending in '\n'
       concatenated together) convert to the internal rep (IR)"""

    # First do the normal python parse of user's program
    error, ast = NormalPythonParse(programString, filename)
    if (error):
        return error

    # Now do the extra EdPy code which implements the Ed. functions
    src = edpy_code.CODE

    error, internalAst = NormalPythonParse(src, "INTERNAL_CODE")
    if (error):
        return error

    rtc = ConvertToIR(ast, programIR, internalAst)
    # io.Out.DebugRaw("Parse rtc:{}, ProgramIR:{}\n".format(rtc, programIR))

    if (io.Out.GetInfoDumpMask() & io.DUMP.PARSER):
        io.Out.DebugRaw("\nDump of internal representation after parsing (rtc:{0}):".format(rtc))
        programIR.Dump()
        io.Out.DebugRaw("\n")

    if (rtc != 0):
        io.Out.DebugRaw("WARNING - PARSER finished with an ERROR!!!\n")

    return rtc

def CheckGetParamNames(node):
    assert node.args.vararg == None
    assert node.args.kwarg == None
    assert len(node.args.defaults) == 0
    
    result = []
    for arg in node.args.args:
        if isinstance(arg, ast.Name): # Py2
            result.append(arg.id)
        elif isinstance(getattr(arg, "arg", None), str): # Py3
            result.append(arg.arg)
        else:
            raise Exception("Only simple parameters are supported")
    
    return result
    

# Only to be used as a module
if __name__ == '__main__':
    io.Out.FatalRaw("This file is a module and can not be run as a script!")
