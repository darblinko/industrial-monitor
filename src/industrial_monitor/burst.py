"""Vibration burst frame: a block of raw radial acceleration samples from one sensor.

RAWv2 carries one acceleration sample per advertisement, which cannot resolve a vibration
spectrum. This frame is defined by this project; Ruuvi firmware does not emit it.
Layout, big-endian:

    byte 0       version (1)
    bytes 1-6    sensor MAC address
    bytes 7-8    sequence number, uint16
    bytes 9-10   sample rate in Hz, uint16
    bytes 11-12  sample count N, uint16
    bytes 13..   N samples, int16, milli-g
"""

import struct
from dataclasses import dataclass

import numpy as np

VERSION = 1
_HEADER = struct.Struct(">B6sHHH")


@dataclass(frozen=True)
class VibrationBurst:
    mac: str
    sequence: int
    sample_rate_hz: int
    samples_mg: np.ndarray

    @classmethod
    def from_g(
        cls, mac: str, sequence: int, sample_rate_hz: int, samples_g: np.ndarray
    ) -> "VibrationBurst":
        milli_g = np.clip(np.rint(np.asarray(samples_g) * 1000.0), -32767, 32767)
        return cls(mac, sequence, sample_rate_hz, milli_g.astype(np.int16))

    def samples_g(self) -> np.ndarray:
        return self.samples_mg.astype(np.float64) / 1000.0


def encode_burst(burst: VibrationBurst) -> bytes:
    samples = np.asarray(burst.samples_mg).astype(">i2")
    header = _HEADER.pack(
        VERSION,
        bytes.fromhex(burst.mac.replace(":", "")),
        burst.sequence % 65536,
        burst.sample_rate_hz,
        len(samples),
    )
    return header + samples.tobytes()


def decode_burst(frame: bytes) -> VibrationBurst:
    if len(frame) < _HEADER.size:
        raise ValueError(f"burst frame shorter than its {_HEADER.size}-byte header")
    version, mac, sequence, rate, count = _HEADER.unpack_from(frame)
    if version != VERSION:
        raise ValueError(f"unsupported burst frame version {version}")
    expected = _HEADER.size + 2 * count
    if len(frame) != expected:
        raise ValueError(f"burst frame declares {count} samples, needs {expected} bytes")
    samples = np.frombuffer(frame, dtype=">i2", offset=_HEADER.size).astype(np.int16)
    mac_text = ":".join(f"{byte:02X}" for byte in mac)
    return VibrationBurst(mac_text, sequence, rate, samples)
