"""Lossless source-relative edits to PS1 BS v2 quantized coefficients.

No decoded pixels or complete target bitstreams are stored in an edit record.
The original disc supplies every source block. Integer coefficient edits avoid
the rounding and image-quality changes of decoding/re-encoding RGB images.
"""
from __future__ import annotations

import struct


def signed10(value):
    return value - 1024 if value & 512 else value


def parse(data, vlc, blocks=1800):
    if len(data) < 8 or struct.unpack_from('<H', data, 6)[0] != 2:
        raise ValueError('Expected a BS v2 stream')
    bits = ''.join(f'{v[0]:016b}' for v in struct.iter_unpack('<H', data[8:len(data) & ~1]))
    reverse = {v: k for k, v in vlc.items()}
    cursor = 0
    result = []
    for block in range(blocks):
        start = cursor
        coeff = [0] * 64
        coeff[0] = signed10(int(bits[cursor:cursor+10], 2))
        cursor += 10
        index = 0
        while True:
            prefix = ''
            while True:
                if cursor >= len(bits):
                    raise ValueError('Truncated MDEC data')
                prefix += bits[cursor]
                cursor += 1
                if prefix == '10':
                    code = None
                    break
                if prefix == '000001':
                    code = int(bits[cursor:cursor+16], 2)
                    cursor += 16
                    break
                if prefix in reverse:
                    code = reverse[prefix]
                    break
                if len(prefix) > 24:
                    raise ValueError('Invalid MDEC VLC')
            if code is None:
                break
            index += (code >> 10) + 1
            if index >= 64:
                raise ValueError('MDEC coefficient overflow')
            coeff[index] = signed10(code & 1023)
        result.append((coeff, bits[start:cursor]))
    return result, bits, cursor


def encode_block(coeff, vlc):
    bits = [f'{coeff[0] & 1023:010b}']
    zeros = 0
    for level in coeff[1:]:
        if level == 0:
            zeros += 1
            continue
        if not -512 <= level <= 511:
            raise ValueError('Invalid coefficient')
        code = (zeros << 10) | (level & 1023)
        bits.append(vlc.get(code, '000001' + f'{code:016b}'))
        zeros = 0
    bits.append('10')
    return ''.join(bits)


def make_edit(source, target, vlc, blocks=1800):
    old, _, _ = parse(source, vlc, blocks)
    new, bits, end = parse(target, vlc, blocks)
    edits = []
    stats = {'blocks': blocks, 'copy_blocks': 0, 'edited_blocks': 0,
             'coefficient_changes': 0, 'same_nonzero_coefficients': 0}
    for (a, abits), (b, bbits) in zip(old, new):
        stats['same_nonzero_coefficients'] += sum(x == y and x != 0 for x, y in zip(a, b))
        if abits == bbits:
            edits.append(None)
            stats['copy_blocks'] += 1
        else:
            if encode_block(b, vlc) != bbits:
                raise ValueError('Noncanonical edited target block; do not replace with a target literal')
            changes = [(i, y - x) for i, (x, y) in enumerate(zip(a, b)) if x != y]
            edits.append(changes)
            stats['coefficient_changes'] += len(changes)
            stats['edited_blocks'] += 1
    # A video declares its exact stream length. Graphics use the canonical
    # ten-bit end marker followed by 32-bit alignment; allocation padding is
    # handled separately by byte edits, never included as image literals.
    used = 8 + ((end + 10 + 31) // 32) * 4
    if used > len(target):
        used = len(target)
    tail = bits[end:(used - 8) * 8]
    edit = {'header_edits': [(i, b) for i, (a, b) in enumerate(zip(source[:8], target[:8])) if a != b],
            'edits': edits, 'tail': tail, 'stream_length': used}
    rebuilt = apply_edit(source, edit, vlc, blocks)
    if rebuilt != target[:used]:
        raise AssertionError('Source-relative coefficient round trip failed')
    return edit, stats


def apply_edit(source, edit, vlc, blocks=1800):
    original, _, _ = parse(source, vlc, blocks)
    header = bytearray(source[:8])
    for i, value in edit['header_edits']:
        header[i] = value
    pieces = []
    for (coeff, raw), changes in zip(original, edit['edits']):
        if changes is None:
            pieces.append(raw)
        else:
            for index, difference in changes:
                coeff[index] += difference
            pieces.append(encode_block(coeff, vlc))
    bits = ''.join(pieces) + edit['tail']
    if len(bits) % 16:
        raise ValueError('Unaligned MDEC result')
    result = bytes(header) + b''.join(struct.pack('<H', int(bits[i:i+16], 2)) for i in range(0, len(bits), 16))
    if len(result) != edit['stream_length']:
        raise ValueError('MDEC result length mismatch')
    return result
