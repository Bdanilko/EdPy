#!/usr/bin/env python2
# * **************************************************************** **
# File: audio.py
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

""" Module providing conversions to, and analysis of, wav files """

from __future__ import print_function
from __future__ import absolute_import

import wave
import tempfile
import os.path
import sys

DOWNLOAD_BYTES_BETWEEN_PAUSES = 1536
DOWNLOAD_PAUSE_MSECS = 2000

WAVE_SAMPLE_RATE_HZ = 44100

# A ramping function between two different samples - the
# values are the percent of the change to apply in each sample.
# values supplied by Brenton (24/Jan/16)
RAMP = (1, 3, 7, 16, 50, 84, 93, 97, 99)

# A quanta is a 1/2 a microsecond. As the sample rate is in
# Hz, we have to divide it by 2000 to get samples per 0.5ms.
SAMPLES_PER_QUANTA = WAVE_SAMPLE_RATE_HZ / 2000

PULSE_AUDIO = True

# ############ main audio creator class ###############################################

# i2b is function for converting int to byte
if sys.version_info[0] == 2:
    i2b = chr
else:
    i2b = lambda x: bytes([x])

class Output(object):
    """Create a wav file"""

    def __init__(self, dir, nameOverride=None):
        """Create an audio file within a directory (typically creating a new name)"""
        self.directory = dir
        if nameOverride:
            self.filename = nameOverride
            self.fileHandle = open(self.filename, "wb")
        else:
            self.fileHandle = tempfile.NamedTemporaryFile(mode="wb",
                                                          prefix="tok", suffix=".wav",
                                                          dir=self.directory, delete=False)
            self.filename = self.fileHandle.name

        self.sampleRate = 44100
        self.samplesPerQuanta = self.sampleRate / 2000
        self.lastLeft = 128
        self.lastRight = 128
        self.downloadBytesBetweenPauses = 1536
        self.downloadPauseMsecs = 2000

        if (PULSE_AUDIO):
            self.audio_func = self.createAudioWithPulses
            self.silence_func = self.createSilenceWithPulses
        else:
            self.audio_func = self.createAudioRamping
            self.silence_func = self.createSilenceRamping


    def SetSampleRate(self, sampleRate):
        self.sampleRate = sampleRate
        self.samplesPerQuanta = self.sampleRate / 2000

    def GetWavPath(self):
        return os.path.join(self.directory, self.filename)

    def CreateDebugWav(self):
        waveWriter = wave.open(self.fileHandle)
        waveWriter.setnchannels(2)
        waveWriter.setsampwidth(1)
        waveWriter.setframerate(self.sampleRate)
        waveWriter.setcomptype("NONE", "")

        # now generate the test file
        data = chr(255) + chr(0) + \
            chr(128) + chr(128) + \
            chr(0) + chr(255) + \
            chr(128) + chr(128)
        count = 2000
        while count > 0:
            waveWriter.writeframes(data)
            count -= 1

        waveWriter.close()

    # def WriteProgramWav(self, binaryString):
    #     self.WriteWav(TOKEN_DOWNLOAD_STR + TOKEN_VERSION_STR + binaryString)

    # def WriteFirmwareWav(self, binaryString):
    #     self.WriteWav(FIRMWARE_DOWNLOAD_STR + FIRMWARE_VERSION_STR + binaryString)

    def WriteWav(self, binaryData):
        waveWriter = wave.open(self.fileHandle)
        waveWriter.setnchannels(2)
        waveWriter.setsampwidth(1)
        waveWriter.setframerate(self.sampleRate)
        waveWriter.setcomptype("NONE", "")

        self.lastLeft = 128
        self.lastRight = 128
        self.ConvertWithPause(binaryData, waveWriter)
        waveWriter.close()

    def ConvertWithPause(self, binString, waveWriter):
        index = 0
        preamble = 0
        pauseCount = 0

        # 500 milliseconds (1000 midQuantas) of silence at the beginning
        waveWriter.writeframes(self.silence_func(1000, self.sampleRate))

        preamble = 0
        while (preamble < self.samplesPerQuanta):
            waveWriter.writeframes(self.audio_func(0, self.sampleRate))
            preamble += 1

        while (index < len(binString)):
            if (pauseCount == self.downloadBytesBetweenPauses):
                preamble = 0
                while (preamble < self.downloadPauseMsecs):
                    waveWriter.writeframes(self.audio_func(0, self.sampleRate))
                    preamble += 1
                pauseCount = 0

            data = binString[index]

            # start
            waveWriter.writeframes(self.audio_func(6, self.sampleRate))

            # now the actual data -- big endian or little endian
            mask = 1
            ones = 0
            while (mask <= 0x80):
                if (data & mask):
                    waveWriter.writeframes(self.audio_func(2, self.sampleRate))
                    ones += 1
                else:
                    waveWriter.writeframes(self.audio_func(0, self.sampleRate))
                mask <<= 1

            # add stop - BBB Changed to 8 - differs from start
            waveWriter.writeframes(self.audio_func(8, self.sampleRate))

            index += 1
            pauseCount += 1

        # added to end as well - to ensure entire data is played. - ## BBB
        preamble = 0
        while (preamble < self.samplesPerQuanta):
            waveWriter.writeframes(self.audio_func(0, self.sampleRate))
            preamble += 1

        # 500 milliseconds (1000 midQuantas) of silence at the end
        waveWriter.writeframes(self.silence_func(1000, self.sampleRate))

    def createAudioRamping(self, midQuantas, sample_rate):
        data = b""
        samples_per_quanta = sample_rate / 2000

        # write fars
        data += self.ramp(255, 0, samples_per_quanta)

        # write nears
        data += self.ramp(0, 255, samples_per_quanta)

        if (midQuantas > 0):
            data += self.ramp(128, 128, midQuantas * samples_per_quanta)

        return data

    def createAudioWithPulses(self, midQuantas, sample_rate):
        data = b""
        samples_per_quanta = sample_rate / 2000
        total_samples = 2 * samples_per_quanta + (midQuantas * samples_per_quanta)

        # write far
        data += i2b(255) + i2b(0)
        # write near
        data += i2b(0) + i2b(255)

        count = 2
        while count < total_samples:
            data += i2b(128) + i2b(128)
            count += 1

        return data

    def createSilenceRamping(self, midQuantas, sample_rate):
        samples_per_quanta = sample_rate / 2000
        return self.ramp(128, 128, midQuantas * samples_per_quanta)

    def createSilenceWithPulses(self, midQuantas, sample_rate):
        data = b""
        samples_per_quanta = sample_rate / 2000
        total_samples = midQuantas * samples_per_quanta

        count = 0
        while count < total_samples:
            data += i2b(128) + i2b(128)
            count += 1

        return data

    def ramp(self, newLeft, newRight, samples):
        # print "ramp", samples
        data = b""

        if (samples < len(RAMP)):
            print("ERROR - audio transition is smaller then the ramp size")
            sys.exit(1)

        diffLeft = newLeft - self.lastLeft
        diffRight = newRight - self.lastRight
        count = 0

        while (count < len(RAMP)):
            left = int(self.lastLeft + (diffLeft * RAMP[count] / 100))
            right = int(self.lastRight + (diffRight * RAMP[count] / 100))
            # print "Ramp %d/%d" % (left, right)
            data += i2b(left) + i2b(right)

            count += 1

        while (count < samples):
            # print "Stable %d/%d" % (newLeft, newRight)
            data += i2b(newLeft) + i2b(newRight)
            count += 1

        self.lastLeft = newLeft
        self.lastRight = newRight
        return data
