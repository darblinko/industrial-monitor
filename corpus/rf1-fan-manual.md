# RF-1 Centrifugal Fan: Operation and Maintenance Manual

This manual is synthetic. It was written for the industrial-monitor project to give the maintenance assistant a corpus with known answers. The RF-1 fan is not a real product. The limits and procedures are illustrative and are not to be applied to real equipment.

## [RF-1.1] Equipment description

The RF-1 is a single-inlet centrifugal fan with a backward-curved impeller, driven directly through a flexible coupling by a six-pole induction motor. Rated speed is 990 rpm, a shaft frequency of 16.5 Hz. The impeller is overhung on the fan shaft, which runs in two grease-lubricated pillow-block ball bearings. The condition monitoring sensor is mounted on the drive-end pillow block, horizontal and radial to the shaft. The fan handles ambient air that can carry dust, so blade deposits are the most frequent cause of high vibration on this machine.

## [RF-2.1] Vibration limits

Vibration severity is judged on the RMS velocity measured radially at the drive-end pillow block over the band 10 to 600 Hz. The alert limit is 4.5 mm/s RMS and the trip limit is 7.1 mm/s RMS. Above the alert limit, plan an inspection within seven days. Above the trip limit, stop the fan at the next safe opportunity and do not return it to service until the cause is corrected, since sustained operation above the trip limit damages the bearings and the impeller hub. On this fan a high velocity at shaft frequency is most often imbalance; see RF-4.1.

## [RF-2.2] Bearing temperature limits

The bearing temperature alert applies when the drive-end pillow block runs 15 C or more above its normal running temperature, or exceeds 65 C, whichever comes first. The trip limit is 80 C. Normal running temperature is the median of the first week after commissioning or after a bearing change. Pillow blocks are exposed to the airflow, so compare against the ambient air temperature before acting on a slow seasonal rise. Follow RF-5.1 for the checks.

## [RF-3.1] Bearing data and defect frequencies

The drive-end pillow block holds a ball bearing with 8 balls of 10.0 mm diameter on a pitch diameter of 50.0 mm, contact angle 0 degrees. Its defect frequencies as multiples of shaft speed are: outer race (BPFO) 3.2, inner race (BPFI) 4.8, ball spin (BSF) 2.4 and cage (FTF) 0.4. At the rated 990 rpm these are BPFO 52.8 Hz, BPFI 79.2 Hz, BSF 39.6 Hz and FTF 6.6 Hz. An outer race defect produces envelope spectrum peaks at 52.8 Hz and its harmonics at 105.6 Hz and 158.4 Hz.

## [RF-3.2] Responding to a bearing defect indication

For an envelope indication at a bearing defect frequency on the RF-1, first confirm the sensor reading under VG-7. Then check the pillow-block grease condition and the lubrication record under RF-3.3. Check that the bearing locking collar and its set screws are tight, since a loose collar lets the inner ring creep on the shaft and wears the race. Increase monitoring to daily and trend the envelope level. Replace the bearing at the next planned stop if the indication grows over three consecutive days or the velocity passes the alert limit.

## [RF-3.3] Bearing lubrication

Grease each pillow block every 4000 running hours with 10 g of lithium complex grease, NLGI grade 2. Clean the nipple before greasing and add grease slowly while the fan runs, if it can be done safely through the extended grease lines. Over-greasing a pillow block raises its temperature for one to two days. Dusty air shortens grease life; halve the interval when the inlet filter is removed or damaged.

## [RF-4.1] Imbalance

Imbalance on the RF-1 shows as high radial vibration at shaft frequency (1x, 16.5 Hz). The most common cause is uneven dust or product build-up on the impeller blades. Other causes are blade erosion, a lost balance weight, and a cracked or distorted blade. To check: isolate the fan under RF-6.1, open the inspection door, and inspect the blades for deposits, erosion, cracks and missing balance weights. Clean the blades evenly, including the back plate. If vibration stays above the alert limit after cleaning, field balance the impeller under RF-4.2. A fan above the 7.1 mm/s trip limit is stopped before it is inspected.

## [RF-4.2] Field balancing

Field balancing the RF-1 is a single-plane correction on the impeller back plate. It needs a phase reference, a once-per-revolution tachometer signal, which the fixed monitoring sensor does not provide, so a portable balancing instrument is used. Record the 1x amplitude and phase, fit a trial weight of 10 to 20 g at a marked blade, and record again. The instrument computes the correction mass and angle from the two readings. Fit the correction weight by welding or bolting, remove the trial weight, and confirm the residual velocity is below 2.8 mm/s RMS.

## [RF-5.1] Elevated bearing temperature

When the drive-end pillow block exceeds the alert in RF-2.2, check: recent greasing or missed greasing against the record in RF-3.3; the ambient and inlet air temperature; coupling condition and alignment after any recent work; and the fan duty, since a closed outlet damper or a blocked filter changes the bearing load. A temperature rise together with a bearing envelope indication suggests bearing damage; follow RF-3.2. Stop the fan if the temperature reaches the 80 C trip limit.

## [RF-6.1] Isolation before work

Before opening the inspection door or touching the impeller, lock out and tag out the motor supply at the local isolator. Close the inlet damper. The impeller can freewheel from natural draft through the ductwork after the motor stops, so wait until it is stationary and then block it against rotation. Verify the motor cannot start from the local control station. Remove the blocking and refit the inspection door before releasing the isolation.
