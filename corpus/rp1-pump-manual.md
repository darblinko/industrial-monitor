# RP-1 Centrifugal Pump: Operation and Maintenance Manual

This manual is synthetic. It was written for the industrial-monitor project to give the maintenance assistant a corpus with known answers. The RP-1 pump is not a real product. The limits and procedures are illustrative and are not to be applied to real equipment.

## [RP-1.1] Equipment description

The RP-1 is an end-suction centrifugal pump driven through a flexible coupling by a four-pole induction motor. Rated speed is 1485 rpm, which is a shaft frequency of 24.75 Hz. The impeller is overhung on the pump shaft and supported by two rolling-element bearings in a grease-lubricated bearing housing. The drive-end bearing carries the radial load and is the bearing nearest the coupling. The condition monitoring sensor is mounted on the drive-end bearing housing, horizontal and radial to the shaft. Readings from any other location are not comparable with the limits in section RP-2.

## [RP-2.1] Vibration limits

Vibration severity is judged on the RMS velocity measured radially at the drive-end bearing housing over the band 10 to 600 Hz. The alert limit is 4.5 mm/s RMS. The trip limit is 7.1 mm/s RMS. Above the alert limit, increase monitoring to once per shift and plan an inspection within seven days. Above the trip limit, stop the pump at the next safe opportunity and do not restart it until the cause is found and corrected. A velocity reading below the alert limit does not clear a bearing defect indication; see RP-3.2.

## [RP-2.2] Bearing housing temperature limits

The housing temperature alert applies when the drive-end housing runs 15 C or more above its normal running temperature for the same duty, or exceeds 70 C, whichever comes first. The trip limit is 85 C. Normal running temperature is the median of the first week of operation after commissioning or after a bearing change. A steady rise over hours points to lubrication or load; a step change after maintenance points to over-greasing or a fit problem. Follow RP-5.1 for the checks.

## [RP-3.1] Bearing data and defect frequencies

The drive-end bearing is a deep groove ball bearing with 9 balls of 12.7 mm diameter on a pitch diameter of 50.8 mm, contact angle 0 degrees. Its defect frequencies as multiples of shaft speed are: outer race (BPFO) 3.375, inner race (BPFI) 5.625, ball spin (BSF) 1.875 and cage (FTF) 0.375. At the rated 1485 rpm these are BPFO 83.5 Hz, BPFI 139.2 Hz, BSF 46.4 Hz and FTF 9.3 Hz. An outer race defect produces envelope spectrum peaks at 83.5 Hz and its harmonics at 167 Hz and 250.6 Hz.

## [RP-3.2] Responding to a bearing defect indication

A bearing defect indication means the envelope spectrum shows peaks at a bearing defect frequency and its harmonics above the baseline. For an outer race indication at BPFO, take these steps. First, confirm the sensor is mounted and reading; see VG-7. Second, check the lubrication record and the grease condition at the purge port; see RP-3.3. Third, listen to the housing with a stethoscope for a rough or knocking tone. Fourth, increase monitoring to daily and trend the envelope level. If the indication grows over three consecutive days, or vibration velocity passes the alert limit, plan a bearing replacement under RP-3.4 at the next planned stop.

## [RP-3.3] Bearing lubrication

Grease the drive-end bearing every 2000 running hours with 15 g of lithium complex grease, NLGI grade 2. Use a grease gun with a known output per stroke, clean the nipple first, and open the purge port so old grease can escape. Do not add grease to silence a noisy bearing. Over-greasing causes churning, which raises the housing temperature by 10 to 20 C within hours and usually settles after one to two days of running with the purge port open. Under-lubrication shows as a slow temperature rise and increasing high-frequency noise.

## [RP-3.4] Bearing replacement

Isolate the pump under RP-6.1 before starting. Remove the coupling guard and coupling spacer, then the bearing housing end cover. Withdraw the shaft assembly and remove the old bearing with a puller that bears on the inner ring. Never strike a bearing or its rings with a hammer. Mount the new bearing by heating it on an induction heater to 110 C; do not exceed 125 C. Slide it onto the shaft against the shoulder and hold it in place until it cools. Check the shaft seat diameter before mounting. After reassembly, check coupling alignment under RP-4.2 and record a new temperature and vibration baseline.

## [RP-4.1] Imbalance

Imbalance shows as a high radial vibration at the shaft frequency (1x, 24.75 Hz) with little energy at other orders. On the RP-1 the common causes are deposits or fouling on the impeller, erosion of the impeller vanes, and damage from solids in the pumped liquid. To check: confirm the 1x amplitude has risen against the baseline, isolate the pump under RP-6.1, remove the casing cover, and inspect and clean the impeller. Replace an eroded or damaged impeller. A replacement or repaired impeller is balanced to grade G6.3 before fitting. Imbalance does not raise the bearing envelope level unless it has been severe for long enough to damage the bearing.

## [RP-4.2] Coupling alignment and misalignment

Misalignment between the motor and pump shafts produces vibration at twice shaft frequency (2x, 49.5 Hz) and high axial vibration, often with a 1x component as well. Check alignment with a laser or dial indicator system after any bearing, coupling or motor work. The tolerances for the RP-1 at 1485 rpm are 0.05 mm parallel offset and 0.05 mm per 100 mm angularity. Check for soft foot before final alignment: no foot may move more than 0.05 mm when its bolt is released. The single radial sensor on this pump cannot measure axial vibration, so a misalignment suspicion is confirmed with a portable instrument.

## [RP-5.1] Elevated bearing housing temperature

When the housing temperature exceeds the alert in RP-2.2, check in this order. One, recent greasing: over-greasing raises temperature within hours; see RP-3.3. Two, missed greasing: compare running hours with the lubrication record. Three, load: compare discharge pressure and motor current with normal duty, since operation far from the best efficiency point raises bearing load. Four, alignment: misalignment heats the drive-end bearing; see RP-4.2. Five, cooling: check that the housing is not lagged or blocked and that ambient temperature is normal. If the temperature reaches the 85 C trip limit, stop the pump.

## [RP-5.2] Cavitation and process transients

Cavitation occurs when suction pressure falls below the vapour pressure of the liquid. It produces broadband, random noise and short impulsive bursts in the vibration signal, often with a crackling sound at the pump inlet. It does not produce peaks at bearing defect frequencies. Process events such as valve operation, pump starts on a shared header, and air entrainment also cause single impulsive transients. Check suction pressure, suction strainer condition and tank level. Short isolated transients that do not repeat need no action.

## [RP-6.1] Isolation before work

Before any inspection inside the pump or bearing housing, isolate the pump. Lock out and tag out the motor supply at the local isolator, close and lock the suction and discharge valves, and drain and vent the casing. Verify the motor cannot start by attempting a start at the local control station. Allow the housing to cool below 50 C before handling bearing parts. Release the isolation only after all guards are refitted.
