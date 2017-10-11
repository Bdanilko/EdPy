#!/usr/bin/env python2
# * **************************************************************** **
# File: edpy_values.py
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

"""Contains Ed.Py function signatures and constants used in
   parsing , optimising and compiling.
"""

# function signatures - note Ed is a module not a class!
# sig types: I - int, S - string const, V - integer list constant (vector)
#          : T - tunestr ref, L - list ref, O - object ref

# Spec version 1.4

signatures = {
    # Control
    "Ed.LeftLed": [('I', None)],
    "Ed.RightLed": [('I', None)],
    "Ed.ObstacleDetectionBeam": [('I', None)],
    "Ed.LineTrackerLed": [('I', None)],
    "Ed.SendIRData": [('I', None)],
    "Ed.StartCountDown": [('I', None), ('I', None)],   # time, units
    "Ed.TimeWait": [('I', None), ('I', None)],         # time, units
    "Ed.ResetDistance": [],

    # Music
    "Ed.PlayBeep": [],
    "Ed.PlayMyBeep": [('I', None)],                    # frequency
    "Ed.PlayTone": [('I', None), ('I', None)],         # frequency code, duration
    "Ed.PlayTune": [('T', None)],
    "Ed.ChangeTempo": [('I', None)],                  # new tempo

    # Movement
    "Ed.Drive": [('I', None), ('I', None), ('I', None)],       # direction, speed, distance
    "Ed.DriveLeftMotor": [('I', None), ('I', None), ('I', None)],
    "Ed.DriveRightMotor": [('I', None), ('I', None), ('I', None)],
    "Ed.SetDistance": [('I', None), ('I', None)],

    # Read data - return an int
    "Ed.ReadObstacleDetection": [],
    "Ed.ReadKeypad": [],
    "Ed.ReadClapSensor": [],
    "Ed.ReadLineState": [],
    "Ed.ReadLineChange": [],
    "Ed.ReadRemote": [],
    "Ed.ReadIRData": [],
    "Ed.ReadLeftLightLevel": [],
    "Ed.ReadRightLightLevel": [],
    "Ed.ReadLineTracker": [],
    "Ed.ReadCountDown": [('I', None)],
    "Ed.ReadMusicEnd": [],

    "Ed.ReadDriveLoad": [],               # OR of both sides
    "Ed.ReadDistance": [('I', None)],     # side - converts to inch or cm

    # NEW functions
    "Ed.ReadRandom": [],
    "Ed.ReadTuneError": [],

    #
    # -------------------------------------------------------------------------
    #
    # INLINE FUNCTIONS!
    #
    # NOTE -- some inline functions are created by the optimiser (and not the user)
    # They are still listed here so that the arguement types can be checked,
    # and return or not can be recorded.
    # That means that they could be used directly (by the user) -- that's not a bad thing, I think
    #
    # Any updates to these functions need to be changed in:
    # edpy_values.signatures, edpy_code.CODE,
    # compiler.SPECIALLY_HANDLED_FUNCTIONS, compiler.HandleSpecialCall
    #

    # Python normal functions
    "ord": [('S', 1)],
    "chr": [('I', None)],
    "len": [("VSTL", None)],    # can handle ListConst, StrConst, or TuneString/List refs
    "abs": [('I', None)],

    # Create special variables and objects. Also register event handlers
    "Ed.List1": [('I', None)],
    "Ed.List2": [('I', None), ('V', None)],
    "Ed.TuneString1": [('I', None)],
    "Ed.TuneString2": [('I', None), ('S', None)],
    "Ed.CreateObject": [('S', None)],
    "Ed.RegisterEventHandler": [('I', None), ('S', None)],

    # Low level access function
    "Ed.Init": [],
    "Ed.WriteModuleRegister8Bit": [('I', None), ('I', None), ('I', None)],
    "Ed.ReadModuleRegister8Bit": [('I', None), ('I', None)],
    "Ed.WriteModuleRegister16Bit": [('I', None), ('I', None), ('I', None)],
    "Ed.ReadModuleRegister16Bit": [('I', None), ('I', None)],

    "Ed.ClearModuleRegisterBit": [('I', None), ('I', None), ('I', None)],
    "Ed.SetModuleRegisterBit": [('I', None), ('I', None), ('I', None)],
    "Ed.AndModuleRegister8Bit": [('I', None), ('I', None), ('I', None)],
    "Ed.ObjectAddr": [('T', None)],

    # NEW simple motor functions (implemented in compiler)
    "Ed.SimpleDriveForwardRight": [],
    "Ed.SimpleDriveForwardLeft": [],
    "Ed.SimpleDriveStop": [],

    "Ed.SimpleDriveForward": [],
    "Ed.SimpleDriveBackward": [],
    "Ed.SimpleDriveBackwardRight": [],
    "Ed.SimpleDriveBackwardLeft": [],

    # optimisations of drive functions, all args constants and
    # unlimited distance set_comms
    "Ed.Drive_INLINE_UNLIMITED": [('I', None), ('I', None), ('I', None)],       # direction, speed, distance
    "Ed.DriveLeftMotor_INLINE_UNLIMITED": [('I', None), ('I', None), ('I', None)],
    "Ed.DriveRightMotor_INLINE_UNLIMITED": [('I', None), ('I', None), ('I', None)],
}


versionStatement = "VERSION 6, 0"

moduleStatements = [
    "DEVICE tracker, 0, LINE_TRACKER1",
    "DEVICE led, 1, Right_LED",
    "DEVICE motor-a, 3, Right_Motor",
    "DEVICE irrx, 5, IR_RECEIVER1",
    "DEVICE beeper, 6, SOUNDER1",
    "DEVICE irtx, 7, IR_TRANSMITTER1",
    "DEVICE motor-b, 8, Left_Motor",
    "DEVICE led, 11, Left_LED",
    ]

constants = {
    "Ed.ON": 1,
    "Ed.OFF": 0,

    "Ed.V1": 1,
    "Ed.V2": 2,

    "Ed.NOTE_A_6": 18181,        # 1760 Hz, 18181 count
    "Ed.NOTE_A_SHARP_6": 17167,  # 1864 Hz, 17167 count
    "Ed.NOTE_B_SHARP_6": 17167,  # 1864 Hz, 17167 count, NAME KEPT FOR COMPATIBILITY
    "Ed.NOTE_B_6": 16202,        # 1975 Hz, 16202 count
    "Ed.NOTE_C_7": 15289,        # 2093 Hz, 15289 count
    "Ed.NOTE_C_SHARP_7": 14433,  # 2217 Hz, 14433 count
    "Ed.NOTE_D_7": 13622,        # 2349 Hz, 13622 count
    "Ed.NOTE_D_SHARP_7": 12856,  # 2489 Hz, 12856 count
    "Ed.NOTE_E_7": 12135,        # 2637 Hz, 12135 count
    "Ed.NOTE_E_SHARP_7": 12135,  # 2637 Hz, 12135 count, NAME KEPT FOR COMPATIBILITY
    "Ed.NOTE_F_7": 11457,        # 2793 Hz, 11457 count
    "Ed.NOTE_F_SHARP_7": 10814,  # 2959 Hz, 10814 count
    "Ed.NOTE_G_7": 10207,        # 3135 Hz, 10207 count
    "Ed.NOTE_G_SHARP_7": 9632,   # 3322 Hz, 9632 count
    "Ed.NOTE_A_7": 9090,         # 3520 Hz, 9090 count
    "Ed.NOTE_A_SHARP_7": 8581,   # 3729 Hz, 8581 count
    "Ed.NOTE_B_SHARP_7": 8581,   # 3729 Hz, 8581 count, NAME KEPT FOR COMPATIBILITY
    "Ed.NOTE_B_7": 8099,         # 3951 Hz, 8099 count
    "Ed.NOTE_C_8": 7644,         # 4186 Hz, 7644 count
    "Ed.NOTE_REST": 0,

    # In milliseconds, using a whole note as 2 second
    "Ed.NOTE_SIXTEENTH": 125,
    "Ed.NOTE_EIGHT":     250,
    "Ed.NOTE_QUARTER":   500,
    "Ed.NOTE_HALF":      1000,
    "Ed.NOTE_WHOLE":     2000,

    "Ed.TEMPO_VERY_SLOW": 1000,
    "Ed.TEMPO_SLOW":      500,
    "Ed.TEMPO_MEDIUM":    250,
    "Ed.TEMPO_FAST":      70,
    "Ed.TEMPO_VERY_FAST": 1,


    # Motor directions
    "Ed.STOP": 0,

    # with distance
    "Ed.FORWARD": 1,
    "Ed.BACKWARD": 2,

    "Ed.DIR_COMPLEX_START": 3,

    # with degrees
    "Ed.FORWARD_RIGHT": 3,
    "Ed.BACKWARD_RIGHT": 4,
    "Ed.FORWARD_LEFT": 5,
    "Ed.BACKWARD_LEFT": 6,

    "Ed.DIR_SPIN_START": 7,

    "Ed.SPIN_RIGHT": 7,
    "Ed.SPIN_LEFT": 8,

    "Ed.SPEED_FULL": 0,
    "Ed.SPEED_1": 1,
    "Ed.SPEED_2": 2,
    "Ed.SPEED_3": 3,
    "Ed.SPEED_4": 4,
    "Ed.SPEED_5": 5,
    "Ed.SPEED_6": 6,
    "Ed.SPEED_7": 7,
    "Ed.SPEED_8": 8,
    "Ed.SPEED_9": 9,
    "Ed.SPEED_10": 10,

    "Ed.DISTANCE_UNLIMITED": 0,

    "Ed.MOTOR_LEFT":     0x00,
    "Ed.MOTOR_RIGHT":    0x01,

    # Internal values
    "Ed.MOTOR_FOR_CODE":     0x80,
    "Ed.MOTOR_BACK_CODE":    0x40,
    "Ed.MOTOR_DIST_CODE":    0x20,
    "Ed.MOTOR_FOR_DIST_CODE":  0xa0,
    "Ed.MOTOR_BACK_DIST_CODE": 0x60,
    "Ed.MOTOR_STOP_CODE":    0xc0,

    "Ed.OBSTACLE_NONE":     0x00,
    "Ed.OBSTACLE_DETECTED": 0x40,
    "Ed.OBSTACLE_LEFT":     0x20,
    "Ed.OBSTACLE_AHEAD":    0x10,
    "Ed.OBSTACLE_RIGHT":    0x08,
    "Ed.OBSTACLE_MASK":     0x78,
    "Ed.OBSTACLE_OTHER_MASK": 0x07,

    "Ed.LINE_ON_BLACK":      0x01,
    "Ed.LINE_ON_WHITE":      0x00,
    "Ed.LINE_MASK":          0x01,
    "Ed.LINE_CHANGE_MASK":   0x02,
    "Ed.LINE_CHANGE_BIT":    1,
    "Ed.LINE_CHANGE_MASK":   0x02,

    "Ed.KEYPAD_NONE":        0x00,
    "Ed.KEYPAD_TRIANGLE":    0x01,
    "Ed.KEYPAD_ROUND":       0x04,
    "Ed.KEYPAD_MASK":        0x0f,

    "Ed.CLAP_NOT_DETECTED":  0x00,
    "Ed.CLAP_DETECTED":      0x04,
    "Ed.CLAP_MASK":          0x04,
    "Ed.CLAP_DETECTED_BIT":  2,
    "Ed.DRIVE_STRAINED":     0x01,
    "Ed.DRIVE_NO_STRAIN":    0x00,
    "Ed.MUSIC_FINISHED":     0x01,
    "Ed.MUSIC_NOT_FINISHED": 0x00,
    "Ed.TUNE_NO_ERROR":      0x00,
    "Ed.TUNE_ERROR":         0x01,

    "Ed.REMOTE_CODE_0": 0,
    "Ed.REMOTE_CODE_1": 1,
    "Ed.REMOTE_CODE_2": 2,
    "Ed.REMOTE_CODE_3": 3,
    "Ed.REMOTE_CODE_4": 4,
    "Ed.REMOTE_CODE_5": 5,
    "Ed.REMOTE_CODE_6": 6,
    "Ed.REMOTE_CODE_7": 7,

    "Ed.REMOTE_CODE_NONE" : 255,

    "Ed.EVENT_TIMER_FINISHED": 0,
    "Ed.EVENT_REMOTE_CODE": 1,
    "Ed.EVENT_IR_DATA": 2,
    "Ed.EVENT_CLAP_DETECTED": 3,
    "Ed.EVENT_OBSTACLE_ANY": 4,
    "Ed.EVENT_OBSTACLE_LEFT": 5,
    "Ed.EVENT_OBSTACLE_RIGHT": 6,
    "Ed.EVENT_OBSTACLE_AHEAD": 7,
    "Ed.EVENT_DRIVE_STRAIN": 8,
    "Ed.EVENT_KEYPAD_TRIANGLE": 9,
    "Ed.EVENT_KEYPAD_ROUND": 10,
    "Ed.EVENT_LINE_TRACKER_ON_WHITE": 11,
    "Ed.EVENT_LINE_TRACKER_ON_BLACK": 12,
    "Ed.EVENT_LINE_TRACKER_SURFACE_CHANGE": 13,
    "Ed.EVENT_TUNE_FINISHED": 14,

    "Ed.EVENT_LAST_EVENT" : 14,

    "Ed.CM":     0x00,
    "Ed.INCH":   0x01,
    "Ed.TIME":   0x02,

    "Ed.TIME_SECONDS":       0x00,
    "Ed.TIME_MILLISECONDS":  0x01,


    # Used for the Ed.Py functions and low level access

    "Ed.MODULE_LINE_TRACKER": 0,
    "Ed.MODULE_RIGHT_LED": 1,
    "Ed.MODULE_RIGHT_MOTOR": 3,
    "Ed.MODULE_IR_RX": 5,
    "Ed.MODULE_BEEPER": 6,
    "Ed.MODULE_IR_TX": 7,
    "Ed.MODULE_LEFT_MOTOR": 8,
    "Ed.MODULE_LEFT_LED": 11,

    "Ed.MODULE_INDEX": 12,
    "Ed.MODULE_DEVICES": 13,
    "Ed.MODULE_TIMERS": 14,
    "Ed.MODULE_CPU": 15,

    # Line Tracker
    "Ed.REG_LT_STATUS_8": 0,
    "Ed.REG_LT_POWER_8": 1,
    "Ed.REG_LT_LEVEL_16": 2,

    # LEDs
    "Ed.REG_LED_STATUS_8": 0,
    "Ed.REG_LED_OUTPUT_8": 1,
    "Ed.REG_LED_LEVEL_16": 2,

    # Motors
    "Ed.REG_MOTOR_STATUS_8": 0,
    "Ed.REG_MOTOR_CONTROL_8": 1,
    "Ed.REG_MOTOR_DISTANCE_16": 2,

    # IR RX
    "Ed.REG_IRRX_STATUS_8": 0,
    "Ed.REG_IRRX_ACTION_8": 1,
    "Ed.REG_IRRX_CHECK_INDEX_8": 2,
    "Ed.REG_IRRX_MATCH_INDEX_8": 3,
    "Ed.REG_IRRX_RCV_CHAR_8": 4,

    # BEEPER
    "Ed.REG_BEEP_STATUS_8": 0,
    "Ed.REG_BEEP_ACTION_8": 1,
    "Ed.REG_BEEP_FREQ_16": 2,
    "Ed.REG_BEEP_DURATION_16": 4,
    "Ed.REG_BEEP_TUNE_CODE_8": 6,
    "Ed.REG_BEEP_TUNE_STRING_8": 7,
    "Ed.REG_BEEP_TUNE_TEMPO_16": 8,

    # IR TX
    "Ed.REG_IRTX_ACTION_8": 0,
    "Ed.REG_IRTX_CHAR_8": 1,

    # INDEX

    # DEVICES
    "Ed.REG_DEV_STATUS_8": 0,
    "Ed.REG_DEV_ACTION_8": 1,
    "Ed.REG_DEV_RANDOM_8": 0x0c,
    "Ed.REG_DEV_BUTTON_8": 0x0d,

    # TIMERS
    "Ed.REG_TIMER_STATUS_8": 0,
    "Ed.REG_TIMER_ACTION_8": 1,
    "Ed.REG_TIMER_PAUSE_16": 2,
    "Ed.REG_TIMER_ONE_SHOT_16": 4,
    "Ed.REG_TIMER_SYS_TIME_16": 6,

    # CPU
}

# Values MUST be set and can only be set once! Must be in the main code (not a function).
variables = {
    # name : tuple of allowed values
    "Ed.EdisonVersion": (constants["Ed.V1"], constants["Ed.V2"]),
    "Ed.DistanceUnits": (constants["Ed.CM"], constants["Ed.INCH"],
                         constants["Ed.TIME"]),
    "Ed.Tempo": (constants["Ed.TEMPO_VERY_SLOW"], constants["Ed.TEMPO_SLOW"],
                 constants["Ed.TEMPO_MEDIUM"], constants["Ed.TEMPO_FAST"],
                 constants["Ed.TEMPO_VERY_FAST"]),
}

notAvailableFunctions = {
    1: ("Ed.ResetDistance", "Ed.SetDistance", "Ed.ReadDistance"),   # Ed.V1
    2: (),                                                          # Ed.V2
}

# QUESTIONS FOR BILL
#
# 1. Does the Devices.button register have to be cleared? Does it have a bitmask? Can more then
#    one button be pressed? What are the values and how do they compare to the shapes?
#
