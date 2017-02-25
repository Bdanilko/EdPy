#!/usr/bin/env python2
# * **************************************************************** **
# File: token_bits.py
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

"""Contains definitions for bits in the token modules. Typically
   STATUS bits are masks, and CONTROL bits are bit numbers (to be
   used with setbit)
"""
STATUS_LINE_OVER_LINE = 1
STATUS_LINE_CHANGED = 2
CONTROL_LINE_POWER = 1

CONTROL_LED_POWER = 1

STATUS_MOTOR_STRAIN = 1
STATUS_MOTOR_DISTANCE = 2
CONTROL_MOTOR_SPEED_MASK = 0x0f
CONTROL_MOTOR_REMAIN_GOING = 4
CONTROL_MOTOR_CMD_MASK = 0xe0

STATUS_IRX_BILL_RECEIVED = 0x01
STATUS_IRX_MATCHED =       0x02
STATUX_IRX_CHECK_VALID =   0x04
STATUS_IRX_OBS_RIGHT =     0x08
STATUS_IRX_OBS_CENTRE =    0x10
STATUS_IRX_OBS_LEFT =      0x20
STATUS_IRX_OBS_DETECTED =  0x40
CONTROL_IRX_DO_CHECK = 0

STATUS_BEEP_TUNE_DONE =    0x01
STATUS_BEEP_TONE_DONE =    0x02
STATUS_BEEP_CLAP_DETECTED = 0x04
STATUS_BEEP_TS_ERROR =     0x08
CONTROL_BEEP_PLAY_CODED_TUNE =   0
CONTROL_BEEP_PLAY_TONE =         1
CONTROL_BEEP_PLAY_BEEP =         2
CONTROL_BEEP_PLAY_STRING_TUNE =  3

CONTROL_ITX_TRANSMIT_CHAR =      0
CONTROL_ITX_DO_OBSTACLE_DETECT = 1

CONTROL_INDEX_WRITE_16BIT = 1
CONTROL_INDEX_READ_16BIT =  2
CONTROL_INDEX_WRITE_8BIT =  5
CONTROL_INDEX_READ_8BIT =   6

STATUS_DEVICE_BUTTON_1 = 0x08
STATUS_DEVICE_BUTTON_2 = 0x04
STATUS_DEVICE_BUTTON_3 = 0x02
STATUS_DEVICE_BUTTON_4 = 0x01

STATUS_TIMER_ONE_SHOT_EXPIRED = 0x01
STATUS_TIMER_ONE_SHOT_RUNNING = 0x02

CONTROL_TIMER_TRIGGER_ONE_SHOT = 0
CONTROL_TIMER_TRIGGER_PAUSE =    1
CONTROL_TIMER_ENABLE_SLEEP =     2
