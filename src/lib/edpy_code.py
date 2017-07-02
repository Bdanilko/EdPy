#!/usr/bin/env python2
# * **************************************************************** **
# File: edpy_code.py
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

"""Contains Ed.Py function python code. The compiler will compile
   this code as well to create a full program.
"""

# NOTE - to update comment out this line and the last one
# so that the code looks like normal python
CODE = """

# This is used to make the editor checking happy but is ignored
# by the EdPy parser!!
import Ed

# These routines will be accessed as if they were in the Ed module
# i.e. LeftLed() is accessed as Ed.LeftLed

# Some of the functions will be replaced in the compiler with direct
# code instead of calling the function -- basic inlining.


# Currently not used as the values are set in edpy_values
# def Ed_Init():
#     Ed.DistanceUnits = 0  # Ed.CM
#     Ed.Tempo = 1          # Ed.TEMPO_MEDIUM

# PYTHON (but not inline)

def abs(number):
    if (number < 0):
        return -number
    else:
        return number


# CONTROL

def Ed_LeftLed(value):
    value = value & 0x01
    Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_LED, Ed.REG_LED_OUTPUT_8, value)


def Ed_RightLed(value):
    value = value & 0x01
    Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_LED, Ed.REG_LED_OUTPUT_8, value)


def Ed_ObstacleDetectionBeam(value):
    value = (value << 1) & 0x02    # bit 1 has the action!
    Ed.WriteModuleRegister8Bit(Ed.MODULE_IR_TX, Ed.REG_IRTX_ACTION_8, value)


def Ed_LineTrackerLed(value):
    value = value & 0x01
    Ed.WriteModuleRegister8Bit(Ed.MODULE_LINE_TRACKER, Ed.REG_LT_POWER_8, value)


def Ed_SendIRData(data):
    Ed.WriteModuleRegister8Bit(Ed.MODULE_IR_TX, Ed.REG_IRTX_ACTION_8, 0x00)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_IR_TX, Ed.REG_IRTX_CHAR_8, data)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_IR_TX, Ed.REG_IRTX_ACTION_8, 0x01)


def Ed_StartCountDown(time, units):
    # use the one-shot timer in the timer module, as it doesn't
    # stop execution
    units &= 0x01
    if (units == Ed.TIME_SECONDS):
        time *= 100   # convert from seconds to hundredths
    else:
        time /= 10    # convert from ms to hundredths
    Ed.WriteModuleRegister16Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_ONE_SHOT_16, time)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_ACTION_8, 1)


def Ed_TimeWait(time, units):
    # use the pause timer in the timer module
    units &= 0x01
    if (units == Ed.TIME_SECONDS):
        time *= 100   # convert from seconds to hundredths
    else:
        time /= 10    # convert from ms to hundredths
    Ed.WriteModuleRegister16Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_PAUSE_16, time)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_ACTION_8, 2)


def Ed_ResetDistance():
    # \QUESTION Gather that both motors reset distance?
    Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, 0)
    Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, 0)


def Ed_ReadObstacleDetection():
    mask = Ed.ReadModuleRegister8Bit(Ed.MODULE_IR_RX, Ed.REG_IRRX_STATUS_8)
    if (mask & Ed.OBSTACLE_DETECTED):
        if (mask & Ed.OBSTACLE_AHEAD):
            data = Ed.OBSTACLE_AHEAD
        else:
            data = mask & 0x38
        mask = mask & Ed.OBSTACLE_OTHER_MASK
        Ed.WriteModuleRegister8Bit(Ed.MODULE_IR_RX, Ed.REG_IRRX_STATUS_8, mask)
    else:
        data = 0

    return data


# MUSIC


def Ed_PlayBeep():
    Ed.WriteModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_ACTION_8, 4)


def Ed_PlayMyBeep(freqCode):
    # doesn't use tempo - 50ms, so duration is 5
    Ed.WriteModuleRegister16Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_FREQ_16, freqCode)
    Ed.WriteModuleRegister16Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_DURATION_16, 5)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_ACTION_8, 2)


def Ed_PlayTone(freqCode, durationMs):
    durationMs /= 10    # convert from ms to hundredths

    # doesn't use tempo
    Ed.WriteModuleRegister16Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_FREQ_16, freqCode)
    Ed.WriteModuleRegister16Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_DURATION_16, durationMs)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_ACTION_8, 2)


def Ed_PlayTune(tuneString):
    addr = Ed.ObjectAddr(tuneString)

    # tempo has already been set
    Ed.WriteModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_TUNE_STRING_8, addr)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_ACTION_8, 8)


def Ed_ChangeTempo(newTempo):
    # set tempo first
    Ed.WriteModuleRegister16Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_TUNE_TEMPO_16, newTempo)

# MOVEMENT

# twoWheelArc = 226 # 36 * pi * 2
# oneWheelArc = 452 # 72 * pi * 2


def Ed_FinishDrive_SPACE(distance, left, right):
    while (distance > 0):
        distance = 0
        if (left != Ed.MOTOR_STOP_CODE):
            distance += Ed.ReadModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR,
                                                   Ed.REG_MOTOR_DISTANCE_16)
        if (right != Ed.MOTOR_STOP_CODE):
            distance += Ed.ReadModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR,
                                                   Ed.REG_MOTOR_DISTANCE_16)


def Ed_FinishDrive_TIME(distance, left, right):
    if (distance > 0):
        # set up pause timer - when it completes the distance will be done
        distance /= 10    # convert from ms to hundredths
        Ed.WriteModuleRegister16Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_PAUSE_16, distance)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_ACTION_8, 2)

        # turn off the motors
        if (left != Ed.MOTOR_STOP_CODE):
            Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8,
                                       Ed.MOTOR_STOP_CODE)
        if (right != Ed.MOTOR_STOP_CODE):
            Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8,
                                       Ed.MOTOR_STOP_CODE)


def Ed_Drive(direction, speed, distance):
    # placeholder
    pass


def Ed_Drive_CM(direction, speed, distance):
    if (direction < Ed.DIR_COMPLEX_START):
        Ed.DriveSimple_CM(direction, speed, distance, 1, 1)
    else:
        leftCtrl = Ed.MOTOR_STOP_CODE
        rightCtrl = Ed.MOTOR_STOP_CODE
        if (direction == Ed.FORWARD_RIGHT):
            leftCtrl = Ed.MOTOR_FOR_CODE
        elif (direction == Ed.BACKWARD_RIGHT):
            leftCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.FORWARD_LEFT):
            rightCtrl = Ed.MOTOR_FOR_CODE
        elif (direction == Ed.BACKWARD_LEFT):
            rightCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.SPIN_RIGHT):
            leftCtrl = Ed.MOTOR_FOR_CODE
            rightCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.SPIN_LEFT):
            leftCtrl = Ed.MOTOR_BACK_CODE
            rightCtrl = Ed.MOTOR_FOR_CODE

        # distance is the degrees to rotate - zero degrees means unlimited
        if (distance != 0):

            # Let the robot turn at most 1 complete circle
            distance = distance % 360

            # As distance > 0, then it now being zero means that it was a multiple
            # of 360. In that case do one complete revolution.
            if (distance == 0):
                distance = 360

            # Distance in motor ticks is roughly equivalent to distance in degrees
            # just small correction for larger degrees
            if (distance > 300):
                distance += 2
            elif (distance > 100):
                distance += 1

            if (direction >= Ed.DIR_SPIN_START):
                distance /= 2

            if (distance == 0):
                distance = 1

            Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
            Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)

            if (leftCtrl != Ed.MOTOR_STOP_CODE):
                leftCtrl |= Ed.MOTOR_DIST_CODE
            if (rightCtrl != Ed.MOTOR_STOP_CODE):
                rightCtrl |= Ed.MOTOR_DIST_CODE

        if (speed > Ed.SPEED_10):
            speed = Ed.SPEED_10

        Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, leftCtrl | speed)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, rightCtrl | speed)

        Ed.FinishDrive_SPACE(distance, leftCtrl, rightCtrl)


def Ed_Drive_INCH(direction, speed, distance):
    if (direction < Ed.DIR_COMPLEX_START):
        Ed.DriveSimple_INCH(direction, speed, distance, 1, 1)
    else:
        leftCtrl = Ed.MOTOR_STOP_CODE
        rightCtrl = Ed.MOTOR_STOP_CODE
        if (direction == Ed.FORWARD_RIGHT):
            leftCtrl = Ed.MOTOR_FOR_CODE
        elif (direction == Ed.BACKWARD_RIGHT):
            leftCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.FORWARD_LEFT):
            rightCtrl = Ed.MOTOR_FOR_CODE
        elif (direction == Ed.BACKWARD_LEFT):
            rightCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.SPIN_RIGHT):
            leftCtrl = Ed.MOTOR_FOR_CODE
            rightCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.SPIN_LEFT):
            leftCtrl = Ed.MOTOR_BACK_CODE
            rightCtrl = Ed.MOTOR_FOR_CODE

        # distance is the degrees to rotate - zero degrees means unlimited
        if (distance != 0):

            # Let the robot turn at most 1 complete circle
            distance = distance % 360

            # As distance > 0, then it now being zero means that it was a multiple
            # of 360. In that case do one complete revolution.
            if (distance == 0):
                distance = 360

            # Distance in motor ticks is roughly equivalent to distance in degrees
            # just small correction for larger degrees
            if (distance > 300):
                distance += 2
            elif (distance > 100):
                distance += 1

            if (direction >= Ed.DIR_SPIN_START):
                distance /= 2

            if (distance == 0):
                distance = 1

            Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
            Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)

            if (leftCtrl != Ed.MOTOR_STOP_CODE):
                leftCtrl |= Ed.MOTOR_DIST_CODE
            if (rightCtrl != Ed.MOTOR_STOP_CODE):
                rightCtrl |= Ed.MOTOR_DIST_CODE

        if (speed > Ed.SPEED_10):
            speed = Ed.SPEED_10

        Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, leftCtrl | speed)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, rightCtrl | speed)

        Ed.FinishDrive_SPACE(distance, leftCtrl, rightCtrl)


def Ed_Drive_TIME(direction, speed, distance):
    if (direction < Ed.DIR_COMPLEX_START):
        Ed.DriveSimple_TIME(direction, speed, distance, 1, 1)
    else:
        leftCtrl = Ed.MOTOR_STOP_CODE
        rightCtrl = Ed.MOTOR_STOP_CODE
        if (direction == Ed.FORWARD_RIGHT):
            leftCtrl = Ed.MOTOR_FOR_CODE
        elif (direction == Ed.BACKWARD_RIGHT):
            leftCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.FORWARD_LEFT):
            rightCtrl = Ed.MOTOR_FOR_CODE
        elif (direction == Ed.BACKWARD_LEFT):
            rightCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.SPIN_RIGHT):
            leftCtrl = Ed.MOTOR_FOR_CODE
            rightCtrl = Ed.MOTOR_BACK_CODE
        elif (direction == Ed.SPIN_LEFT):
            leftCtrl = Ed.MOTOR_BACK_CODE
            rightCtrl = Ed.MOTOR_FOR_CODE

        # for TIME, distance is the time in milliseconds

        if ((distance > 0) and (distance < 10)):
            # as distance is in milliseconds, but we convert to 1/100s of
            # of a second, if the distance is less then 10, we won't move at all
            return

        if (speed > Ed.SPEED_10):
            speed = Ed.SPEED_10

        Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, leftCtrl | speed)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, rightCtrl | speed)

        Ed.FinishDrive_TIME(distance, leftCtrl, rightCtrl)


def Ed_DriveLeftMotor(direction, speed, distance):
    # placeholder
    pass


def Ed_DriveLeftMotor_CM(direction, speed, distance):
    if (direction <= Ed.BACKWARD):
        Ed.DriveSimple_CM(direction, speed, distance, 1, 0)


def Ed_DriveLeftMotor_INCH(direction, speed, distance):
    if (direction <= Ed.BACKWARD):
        Ed.DriveSimple_INCH(direction, speed, distance, 1, 0)


def Ed_DriveLeftMotor_TIME(direction, speed, distance):
    if (direction <= Ed.BACKWARD):
        Ed.DriveSimple_TIME(direction, speed, distance, 1, 0)


def Ed_DriveRightMotor(direction, speed, distance):
    # placeholder
    pass


def Ed_DriveRightMotor_CM(direction, speed, distance):
    if (direction <= Ed.BACKWARD):
        Ed.DriveSimple_CM(direction, speed, distance, 0, 1)


def Ed_DriveRightMotor_INCH(direction, speed, distance):
    if (direction <= Ed.BACKWARD):
        Ed.DriveSimple_INCH(direction, speed, distance, 0, 1)


def Ed_DriveRightMotor_TIME(direction, speed, distance):
    if (direction <= Ed.BACKWARD):
        Ed.DriveSimple_TIME(direction, speed, distance, 0, 1)


def Ed_DriveSimple_CM(direction, speed, distance, left, right):
    control = 0
    if (speed > Ed.SPEED_10):
        speed = Ed.SPEED_10

    if (direction == Ed.STOP):
        control = Ed.MOTOR_STOP_CODE
        distance = 0
    else:
        if (direction == Ed.FORWARD):
            control = Ed.MOTOR_FOR_CODE | speed
        else:
            control = Ed.MOTOR_BACK_CODE | speed

        if (distance > 0):
            distance *= 8
            # account for inertia by subtracting a fudge factor
            distance -= speed
            control = control | Ed.MOTOR_DIST_CODE

    if (left):
        Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, control)

    if (right):
        Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, control)

    Ed.FinishDrive_SPACE(distance, left, right)


def Ed_DriveSimple_INCH(direction, speed, distance, left, right):
    control = 0
    if (speed > Ed.SPEED_10):
        speed = Ed.SPEED_10

    if (direction == Ed.STOP):
        control = Ed.MOTOR_STOP_CODE
        distance = 0
    else:
        if (direction == Ed.FORWARD):
            control = Ed.MOTOR_FOR_CODE | speed
        else:
            control = Ed.MOTOR_BACK_CODE | speed

        if (distance > 0):
            # multiple by 20.3 in two steps
            distance *= 203
            distance /= 10
            # account for inertia by subtracting a fudge factor
            distance -= speed
            control = control | Ed.MOTOR_DIST_CODE

    if (left):
        Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, control)

    if (right):
        Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
        Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, control)

    Ed.FinishDrive_SPACE(distance, left, right)


def Ed_DriveSimple_TIME(direction, speed, distance, left, right):
    control = 0
    if (speed > Ed.SPEED_10):
        speed = Ed.SPEED_10

    if (direction == Ed.STOP):
        control = Ed.MOTOR_STOP_CODE
        distance = 0
    else:
        if (direction == Ed.FORWARD):
            control = Ed.MOTOR_FOR_CODE | speed
        else:
            control = Ed.MOTOR_BACK_CODE | speed

        if ((distance > 0) and (distance < 10)):
            # as distance is in milliseconds, but we convert to 1/100s of
            # of a second, if the distance is less then 10, we won't move at all
            return

    if (left):
        Ed.WriteModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, control)

    if (right):
        Ed.WriteModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, control)

    Ed.FinishDrive_TIME(distance, left, right)


def Ed_SetDistance(which, distance):
    # placeholder
    pass


def Ed_SetDistance_CM(which, distance):
    if (distance > 0):
        distance *= 8

        if ((which & 0x01) == Ed.MOTOR_LEFT):
            Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
            # Turn on the 5th bit, which turns on distance checking
            Ed.SetModuleRegisterBit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, 5)
        else:
            Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
            # Turn on the 5th bit, which turns on distance checking
            Ed.SetModuleRegisterBit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, 5)


def Ed_SetDistance_INCH(which, distance):
    if (distance > 0):
        # multiple by 20.3 in two steps
        distance *= 203
        distance /= 10

        if ((which & 0x01) == Ed.MOTOR_LEFT):
            Ed.WriteModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
            # Turn on the 5th bit, which turns on distance checking
            Ed.SetModuleRegisterBit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_CONTROL_8, 5)
        else:
            Ed.WriteModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16, distance)
            # Turn on the 5th bit, which turns on distance checking
            Ed.SetModuleRegisterBit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_CONTROL_8, 5)


# READ DATA


def Ed_ReadKeypad():
    # TODO: Do we have to clear this register??
    button = Ed.ReadModuleRegister8Bit(Ed.MODULE_DEVICES, Ed.REG_DEV_BUTTON_8)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_DEVICES, Ed.REG_DEV_BUTTON_8, 0)
    return button & Ed.KEYPAD_MASK   # Assuming a bitmask


def Ed_ReadRandom():
    Ed.WriteModuleRegister8Bit(Ed.MODULE_DEVICES, Ed.REG_DEV_ACTION_8, 0x10)
    return Ed.ReadModuleRegister8Bit(Ed.MODULE_DEVICES, Ed.REG_DEV_RANDOM_8)


def Ed_ReadClapSensor():
    data = (Ed.ReadModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_STATUS_8) & Ed.CLAP_MASK)
    if data:
        Ed.ClearModuleRegisterBit(Ed.MODULE_BEEPER, Ed.REG_BEEP_STATUS_8, Ed.CLAP_DETECTED_BIT)
    return data


def Ed_ReadLineState():
    return (Ed.ReadModuleRegister8Bit(Ed.MODULE_LINE_TRACKER, Ed.REG_LT_STATUS_8) & Ed.LINE_MASK)


def Ed_ReadLineChange():
    change = Ed.ReadModuleRegister8Bit(Ed.MODULE_LINE_TRACKER, Ed.REG_LT_STATUS_8) & Ed.LINE_CHANGE_MASK
    if (change):
        Ed.ClearModuleRegisterBit(Ed.MODULE_LINE_TRACKER, Ed.REG_LT_STATUS_8, Ed.LINE_CHANGE_BIT)
        return 1
    else:
        return 0


def Ed_ReadRemote():
    if ((Ed.ReadModuleRegister8Bit(Ed.MODULE_IR_RX, Ed.REG_IRRX_STATUS_8) & 0x02) == 0):
        return Ed.REMOTE_CODE_NONE

    data = Ed.ReadModuleRegister8Bit(Ed.MODULE_IR_RX, Ed.REG_IRRX_MATCH_INDEX_8)
    Ed.ClearModuleRegisterBit(Ed.MODULE_IR_RX, Ed.REG_IRRX_STATUS_8, 1)
    return data


def Ed_ReadIRData():
    data = Ed.ReadModuleRegister8Bit(Ed.MODULE_IR_RX, Ed.REG_IRRX_RCV_CHAR_8)
    Ed.WriteModuleRegister8Bit(Ed.MODULE_IR_RX, Ed.REG_IRRX_RCV_CHAR_8, 0)
    Ed.ClearModuleRegisterBit(Ed.MODULE_IR_RX, Ed.REG_IRRX_STATUS_8, 0)
    return data


def Ed_ReadLeftLightLevel():
    return Ed.ReadModuleRegister16Bit(Ed.MODULE_LEFT_LED, Ed.REG_LED_LEVEL_16)


def Ed_ReadRightLightLevel():
    return Ed.ReadModuleRegister16Bit(Ed.MODULE_RIGHT_LED, Ed.REG_LED_LEVEL_16)


def Ed_ReadLineTracker():
    return Ed.ReadModuleRegister16Bit(Ed.MODULE_LINE_TRACKER, Ed.REG_LT_LEVEL_16)


def Ed_ReadCountDown(units):
    time = Ed.ReadModuleRegister16Bit(Ed.MODULE_TIMERS, Ed.REG_TIMER_ONE_SHOT_16)
    if ((units & 0x01) == Ed.TIME_SECONDS):
        time /= 100   # convert from hundredths to seconds
    else:
        time *= 10    # convert from hundredths to ms
    return time


def Ed_ReadMusicEnd():
    # end if tune done, tone done
    result = 0
    status = Ed.ReadModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_STATUS_8)
    # don't clear clap detected status or tune error
    if (status & 0x01):
        Ed.ClearModuleRegisterBit(Ed.MODULE_BEEPER, Ed.REG_BEEP_STATUS_8, 0)
        result = 1
    if (status & 0x02):
        Ed.ClearModuleRegisterBit(Ed.MODULE_BEEPER, Ed.REG_BEEP_STATUS_8, 1)
        result = 1
    return result

def Ed_ReadTuneError():
    # Don't clear anything, just return 1 if error bit set
    return ((Ed.ReadModuleRegister8Bit(Ed.MODULE_BEEPER, Ed.REG_BEEP_STATUS_8) & 8) != 0)


def Ed_ReadDriveLoad():
    # OR the values from both wheels
    value = (Ed.ReadModuleRegister8Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_STATUS_8) &
             Ed.DRIVE_STRAINED)
    value |= (Ed.ReadModuleRegister8Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_STATUS_8) &
              Ed.DRIVE_STRAINED)
    return value


def Ed_ReadDistance(which):
    # placeholder
    pass


def Ed_ReadDistance_CM(which):
    if ((which & 0x01) == Ed.MOTOR_LEFT):
        which = Ed.ReadModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16)
    else:
        which = Ed.ReadModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16)

    # Convert to the correct units - CM
    which /= 8

    return which


def Ed_ReadDistance_INCH(which):
    if ((which & 0x01) == Ed.MOTOR_LEFT):
        which = Ed.ReadModuleRegister16Bit(Ed.MODULE_LEFT_MOTOR, Ed.REG_MOTOR_DISTANCE_16)
    else:
        which = Ed.ReadModuleRegister16Bit(Ed.MODULE_RIGHT_MOTOR, Ed.REG_MOTOR_DISTANCE_16)

    # Convert to the correct units - inches
    which /= 20    # not 20.3, but this is close enough

    return which


def Ed_AndModuleRegister8Bit(mod, reg, value):
    temp = Ed_ReadModuleRegister8Bit(mod, reg)
    Ed_WriteModuleRegister8Bit(mod, reg, (temp & value))


# -------------------------------------------------------------

# FUNCTIONS IMPLEMENTED IN COMPILER
# Listed here so that can show the compiler whether the function returns a
# value or not

#
# Any updates to these functions need to be changed in:
# edpy_values.signatures, edpy_code.CODE,
# compiler.SPECIALLY_HANDLED_FUNCTIONS, compiler.HandleSpecialCall
#


# PYTHON FUNCTIONS

def ord(character):
    # IMPLEMENTED IN COMPILER
    return 0

def chr(number):
    # IMPLEMENTED IN COMPILER
    return 0


def len(array):
    # IMPLEMENTED IN COMPILER
    return 0



# SIMPLE MOTOR FUNCTIONS IMPLEMENTED IN COMPILER

def Ed_SimpleDriveForwardRight():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SimpleDriveForwardLeft():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SimpleDriveStop():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SimpleDriveForward():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SimpleDriveBackward():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SimpleDriveBackwardRight():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SimpleDriveBackwardLeft():
    # IMPLEMENTED IN COMPILER
    pass


def Ed_Drive_INLINE_UNLIMITED(a, b, c):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_DriveLeftMotor_INLINE_UNLIMITED(a, b, c):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_DriveRightMotor_INLINE_UNLIMITED(a, b, c):
    # IMPLEMENTED IN COMPILER
    pass


# INTERNAL FUNCTIONS

def Ed_List1(size):
    # IMPLEMENTED IN COMPILER
    return 0


def Ed_List2(size, initial):
    # IMPLEMENTED IN COMPILER
    return 0


def Ed_TuneString1(size):
    # IMPLEMENTED IN COMPILER
    return 0


def Ed_TuneString2(size, initial):
    # IMPLEMENTED IN COMPILER
    return 0


def Ed_CreateObject(name):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_RegisterEventHandler(event, function):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_WriteModuleRegister8Bit(mod, reg, value):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_WriteModuleRegister16Bit(mod, reg, value):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_ClearModuleRegisterBit(mod, reg, bit):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_SetModuleRegisterBit(mod, reg, bit):
    # IMPLEMENTED IN COMPILER
    pass


def Ed_ReadModuleRegister8Bit(mod, reg):
    # IMPLEMENTED IN COMPILER
    return 0


def Ed_ReadModuleRegister16Bit(mod, reg):
    # IMPLEMENTED IN COMPILER
    return 0


def Ed_ObjectAddr(obj):
    # IMPLEMENTED IN COMPILER
    return 0

"""
