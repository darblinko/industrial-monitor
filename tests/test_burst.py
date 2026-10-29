import numpy as np
import pytest

from industrial_monitor.burst import VibrationBurst, decode_burst, encode_burst


def test_round_trip_preserves_header_and_samples():
    samples = np.array([0, 1, -1, 32767, -32767, 250], dtype=np.int16)
    burst = VibrationBurst(
        mac="AA:BB:CC:00:00:03", sequence=513, sample_rate_hz=1344, samples_mg=samples
    )

    decoded = decode_burst(encode_burst(burst))

    assert decoded.mac == "AA:BB:CC:00:00:03"
    assert decoded.sequence == 513
    assert decoded.sample_rate_hz == 1344
    assert decoded.samples_mg.tolist() == [0, 1, -1, 32767, -32767, 250]


def test_frame_layout_is_big_endian_with_13_byte_header():
    burst = VibrationBurst(
        mac="01:02:03:04:05:06", sequence=2, sample_rate_hz=1344, samples_mg=np.array([1, -2])
    )
    frame = encode_burst(burst)
    assert frame.hex() == "01" + "010203040506" + "0002" + "0540" + "0002" + "0001" + "fffe"


def test_from_g_converts_and_clamps_to_int16_milli_g():
    burst = VibrationBurst.from_g("01:02:03:04:05:06", 0, 1344, np.array([0.0015, -0.25, 40.0]))
    assert burst.samples_mg.tolist() == [2, -250, 32767]


def test_rejects_truncated_frame():
    frame = encode_burst(
        VibrationBurst(
            mac="01:02:03:04:05:06", sequence=0, sample_rate_hz=1344, samples_mg=np.zeros(8)
        )
    )
    with pytest.raises(ValueError):
        decode_burst(frame[:-1])


def test_rejects_unknown_version():
    frame = bytearray(
        encode_burst(
            VibrationBurst(
                mac="01:02:03:04:05:06", sequence=0, sample_rate_hz=1344, samples_mg=np.zeros(2)
            )
        )
    )
    frame[0] = 9
    with pytest.raises(ValueError):
        decode_burst(bytes(frame))
