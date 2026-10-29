# Vibration Diagnosis Field Guide for the Plant Monitor

This guide is synthetic. It was written for the industrial-monitor project. It describes how to read the alarms of this project's monitor and gives general vibration diagnosis practice for the RP-1 pumps and RF-1 fans in the demo plant. It is not a substitute for a qualified analyst or the equipment manufacturer's instructions.

## [VG-1] Reading a monitor alarm

The monitor learns a baseline for each machine from its first 40 acquisition windows and then scores every new window against it. Each channel produces a z-score: the deviation from the baseline median divided by the scaled median absolute deviation. The channels and the fault hypothesis each one indicates are: 1x amplitude for imbalance, bearing envelope for bearing wear, housing temperature for temperature drift, and kurtosis for an unclassified impulsive fault. When several channels exceed the threshold, a specific channel takes precedence over kurtosis. The hypothesis names the most likely fault class. It is a starting point for inspection and does not replace a diagnosis.

## [VG-2] Envelope analysis for bearing defects

A defect on a bearing race produces a short impact each time a rolling element passes it. Each impact rings the structure at its resonance, several hundred hertz on these machines, and the ringing repeats at the defect frequency. Envelope analysis band-pass filters the signal around the resonance, takes the envelope of the filtered signal, and computes its spectrum. Peaks in the envelope spectrum at the outer race frequency (BPFO) and its harmonics indicate an outer race defect. The bearing envelope channel of the monitor is the sum of the first three BPFO harmonics divided by the median envelope level.

## [VG-3] Velocity and envelope in early bearing damage

Vibration velocity RMS measures overall severity and is dominated by low-frequency energy such as imbalance. Early bearing damage adds high-frequency impacts with little energy, so the velocity can stay well below the alert limit while the bearing envelope channel is far above its baseline. A velocity below the alert limit therefore does not clear a bearing alarm. Treat an envelope alarm as a bearing defect indication and follow the equipment manual. Velocity usually rises only once the damage has spread, which is late in the failure progression.

## [VG-4] Unclassified impulsive alarms

An unclassified alarm means the kurtosis channel exceeded the threshold while no specific channel did. Kurtosis rises when the signal contains impulses. Single impulses come from process events such as valve operation, cavitation bursts, a pump start on a shared header, or a knock on the machine. Check the process log for the alarm time and listen for cavitation or loose parts. An unclassified alarm that clears within a few windows needs no action. If it persists for a day, take a portable measurement, because a bearing defect can show as impulsiveness before its envelope peaks are distinct.

## [VG-5] Imbalance, misalignment and looseness

The three common running-speed faults differ in their spectra. Imbalance produces a dominant radial peak at 1x shaft speed, with amplitude that grows with the square of speed. Misalignment produces a strong 2x peak and high axial vibration, often with 1x as well. Mechanical looseness produces a series of harmonics of shaft speed, sometimes with half-order components, and readings that change with sensor position. The monitor tracks the 1x amplitude only, so it can raise an imbalance hypothesis but cannot separate misalignment or looseness. Confirm with a portable instrument that measures in three directions.

## [VG-6] Alarm persistence and false alarms

A single window above the threshold does not raise an alarm. The monitor raises an alarm when at least 2 of the last 3 windows exceed the threshold, and clears it when fewer than 2 of the last 3 do. The persistence rule suppresses isolated process transients. The threshold is calibrated on simulated healthy machines so that about 1 window in 100 raises an alarm on a healthy machine. The cost of the persistence rule is delay: a fault that is slightly above the threshold takes at least two windows to alarm, and an intermittent one may not alarm at all.

## [VG-7] Sensor checks before maintenance action

Before opening a machine on the strength of a monitor alarm, confirm the sensor is trustworthy. Check that the sensor is fixed to the bearing housing and has not moved or worked loose, since a loose sensor produces impulsive readings. Check the battery voltage in the sensor status message; replace the battery below 2.4 V. Check the sensor sequence number advances without gaps, which shows that messages are arriving. Compare the reading with a portable instrument if the alarm is the only evidence of a fault.

## [VG-8] Temperature drift alarms

The temperature channel compares the housing temperature with the machine's own baseline, so it detects a rise long before an absolute limit is reached. A temperature drift alarm with no vibration channel above threshold points to lubrication, load, alignment or cooling rather than an established bearing defect. Compare the reading with the equipment manual limits, which combine a rise over normal running temperature with an absolute value. A rise together with a bearing envelope alarm suggests bearing damage and is treated as a bearing defect.
