"""XNA XNB LZX frame and stream decoder.

This is a managed implementation of the public LZX bitstream algorithm and XNA's
frame envelope.  It deliberately has no native or third-party binary dependency.
"""

from __future__ import annotations

from ._content import ContentLoadException


_FRAME = 0x8000
_MAX_OUTPUT = 256 * 1024 * 1024
_WINDOW_BITS = 16
_WINDOW_SIZE = 1 << _WINDOW_BITS
_LITERAL_COUNT = 256
_PRETREE_COUNT = 20
_ALIGNED_COUNT = 8
_LENGTH_COUNT = 249
_PRIMARY_LENGTHS = 7
_MIN_MATCH = 2
_VERBATIM = 1
_ALIGNED = 2
_UNCOMPRESSED = 3


def _slot_extra_bits() -> tuple[int, ...]:
    result: list[int] = []
    value = 0
    for slot in range(52):
        result.append(value)
        if slot % 2 == 1 and slot != 1 and value < 17:
            value += 1
    return tuple(result)


_EXTRA = _slot_extra_bits()
_POSITION_BASE: tuple[int, ...]
_bases: list[int] = []
_next_base = 0
for _bits in _EXTRA[:51]:
    _bases.append(_next_base)
    _next_base += 1 << _bits
_POSITION_BASE = tuple(_bases)
del _bases, _next_base, _bits


class _DecoderError(Exception):
    pass


class _ByteCursor:
    __slots__ = ("data", "position", "failed")

    def __init__(self, data: bytes, position: int) -> None:
        self.data = data
        self.position = position
        self.failed = False

    def byte(self) -> int:
        if self.position >= len(self.data):
            self.failed = True
            return -1
        value = self.data[self.position]
        self.position += 1
        return value

    def u32le(self) -> int:
        values = [self.byte() for _ in range(4)]
        if any(value < 0 for value in values):
            self.failed = True
            return 0
        return sum(value << (8 * index) for index, value in enumerate(values))

    def copy(self, destination: bytearray, offset: int, count: int, limit: int) -> None:
        end = self.position + count
        if count < 0 or end > len(self.data) or end > limit or offset < 0 or offset + count > len(destination):
            self.failed = True
            raise _DecoderError("uncompressed block exceeds its frame")
        destination[offset:offset + count] = self.data[self.position:end]
        self.position = end

    def move(self, delta: int) -> None:
        position = self.position + delta
        if position < 0 or position > len(self.data):
            self.failed = True
            raise _DecoderError("invalid compressed input alignment")
        self.position = position


class _BitWords:
    """LZX's MSB-first bits stored as little-endian 16-bit input words."""

    __slots__ = ("source", "value", "count")

    def __init__(self, source: _ByteCursor) -> None:
        self.source = source
        self.value = 0
        self.count = 0

    def reset(self) -> None:
        self.value = 0
        self.count = 0

    def ensure(self, count: int) -> None:
        while self.count < count:
            low = self.source.byte()
            high = self.source.byte()
            low = 0xFF if low < 0 else low
            high = 0xFF if high < 0 else high
            self.value = (self.value | (((high << 8) | low) << (16 - self.count))) & 0xFFFFFFFF
            self.count += 16

    def peek(self, count: int) -> int:
        return self.value >> (32 - count)

    def discard(self, count: int) -> None:
        if count > self.count:
            raise _DecoderError("Huffman code exceeds buffered input")
        self.value = (self.value << count) & 0xFFFFFFFF
        self.count -= count

    def read(self, count: int) -> int:
        if count == 0:
            return 0
        self.ensure(count)
        result = self.peek(count)
        self.discard(count)
        return result


class _Huffman:
    __slots__ = ("symbol_count", "table_bits", "lengths", "table")

    def __init__(self, symbol_count: int, table_bits: int, length_capacity: int | None = None) -> None:
        self.symbol_count = symbol_count
        self.table_bits = table_bits
        self.lengths = [0] * (symbol_count if length_capacity is None else length_capacity)
        self.table = [0] * ((1 << table_bits) + symbol_count * 2)

    def rebuild(self) -> None:
        width = self.table_bits
        bit_length = 1
        position = 0
        table_limit = 1 << width
        spread = table_limit >> 1
        next_node = spread

        while bit_length <= width:
            for symbol in range(self.symbol_count):
                if self.lengths[symbol] != bit_length:
                    continue
                end = position + spread
                if end > table_limit:
                    raise _DecoderError("oversubscribed Huffman table")
                self.table[position:end] = [symbol] * spread
                position = end
            spread >>= 1
            bit_length += 1

        if position != table_limit:
            self.table[position:table_limit] = [0] * (table_limit - position)
            position <<= 16
            table_limit <<= 16
            spread = 1 << 15
            while bit_length <= 16:
                for symbol in range(self.symbol_count):
                    if self.lengths[symbol] != bit_length:
                        continue
                    leaf = position >> 16
                    for branch_index in range(bit_length - width):
                        if leaf >= len(self.table) or (next_node << 1) + 1 >= len(self.table):
                            raise _DecoderError("Huffman tree exceeds its decode table")
                        if self.table[leaf] == 0:
                            self.table[next_node << 1] = 0
                            self.table[(next_node << 1) + 1] = 0
                            self.table[leaf] = next_node
                            next_node += 1
                        leaf = self.table[leaf] << 1
                        if position & (1 << (15 - branch_index)):
                            leaf += 1
                    if leaf >= len(self.table):
                        raise _DecoderError("invalid Huffman leaf")
                    self.table[leaf] = symbol
                    position += spread
                    if position > table_limit:
                        raise _DecoderError("oversubscribed Huffman tree")
                spread >>= 1
                bit_length += 1

        if position != table_limit and any(self.lengths[:self.symbol_count]):
            raise _DecoderError("incomplete nonempty Huffman tree")

    def symbol(self, bits: _BitWords) -> int:
        bits.ensure(16)
        index = bits.peek(self.table_bits)
        if index >= len(self.table):
            raise _DecoderError("invalid Huffman prefix")
        symbol = self.table[index]
        if symbol >= self.symbol_count:
            mask = 1 << (32 - self.table_bits)
            while symbol >= self.symbol_count:
                mask >>= 1
                if mask == 0:
                    raise _DecoderError("unterminated Huffman code")
                index = (symbol << 1) | (1 if bits.value & mask else 0)
                if index >= len(self.table):
                    raise _DecoderError("Huffman branch is outside the table")
                symbol = self.table[index]
        if symbol >= len(self.lengths):
            raise _DecoderError("Huffman symbol is outside the length table")
        length = self.lengths[symbol]
        if length == 0 or length > bits.count:
            raise _DecoderError("invalid zero-length Huffman symbol")
        bits.discard(length)
        return symbol


class _LzxStream:
    __slots__ = (
        "window", "window_position", "r0", "r1", "r2", "header_read",
        "block_kind", "block_length", "block_remaining", "main_elements",
        "pretree", "main", "lengths", "aligned", "intel_file_size",
        "intel_started", "frame_count",
    )

    def __init__(self) -> None:
        self.window = bytearray([0xDC]) * _WINDOW_SIZE
        self.window_position = 0
        self.r0 = self.r1 = self.r2 = 1
        self.header_read = False
        self.block_kind = 0
        self.block_length = 0
        self.block_remaining = 0
        self.main_elements = _LITERAL_COUNT + ((_WINDOW_BITS << 1) << 3)
        self.pretree = _Huffman(_PRETREE_COUNT, 6, _PRETREE_COUNT + 64)
        self.main = _Huffman(_LITERAL_COUNT + 50 * 8, 12, _LITERAL_COUNT + 50 * 8 + 64)
        self.lengths = _Huffman(_LENGTH_COUNT + 1, 12, _LENGTH_COUNT + 1 + 64)
        self.aligned = _Huffman(_ALIGNED_COUNT, 7, _ALIGNED_COUNT + 64)
        self.intel_file_size = 0
        self.intel_started = False
        self.frame_count = 0

    def _read_code_lengths(self, target: _Huffman, first: int, last: int, bits: _BitWords) -> None:
        for index in range(_PRETREE_COUNT):
            self.pretree.lengths[index] = bits.read(4)
        self.pretree.rebuild()
        index = first
        while index < last:
            command = self.pretree.symbol(bits)
            if command in (17, 18):
                count = bits.read(4 if command == 17 else 5) + (4 if command == 17 else 20)
                if count > last - index:
                    raise _DecoderError("code-length zero run exceeds the tree")
                target.lengths[index:index + count] = [0] * count
                index += count
            elif command == 19:
                count = bits.read(1) + 4
                delta = self.pretree.symbol(bits)
                if count > last - index:
                    raise _DecoderError("repeated code-length run exceeds the tree")
                value = (target.lengths[index] + 17 - delta) % 17
                target.lengths[index:index + count] = [value] * count
                index += count
            else:
                target.lengths[index] = (target.lengths[index] + 17 - command) % 17
                index += 1

    def _read_main_trees(self, bits: _BitWords) -> None:
        self._read_code_lengths(self.main, 0, _LITERAL_COUNT, bits)
        self._read_code_lengths(self.main, _LITERAL_COUNT, self.main_elements, bits)
        self.main.rebuild()
        if self.main.lengths[0xE8]:
            self.intel_started = True
        self._read_code_lengths(self.lengths, 0, _LENGTH_COUNT, bits)
        self.lengths.rebuild()

    def _copy_matches(self, count: int, aligned: bool, bits: _BitWords,
                      position: int, repeated: tuple[int, int, int]) -> tuple[int, tuple[int, int, int]]:
        r0, r1, r2 = repeated
        remaining = count
        while remaining:
            code = self.main.symbol(bits)
            if code < _LITERAL_COUNT:
                if position >= _WINDOW_SIZE:
                    raise _DecoderError("literal crosses the LZX window")
                self.window[position] = code
                position += 1
                remaining -= 1
                continue

            match = code - _LITERAL_COUNT
            length = match & _PRIMARY_LENGTHS
            if length == _PRIMARY_LENGTHS:
                length += self.lengths.symbol(bits)
            length += _MIN_MATCH
            if length > remaining:
                raise _DecoderError("match extends beyond the requested output run")
            original_length = length
            slot = match >> 3

            if slot == 0:
                offset = r0
            elif slot == 1:
                offset = r1
                r1, r0 = r0, r1
            elif slot == 2:
                offset = r2
                r2, r0 = r0, r2
            else:
                if slot >= len(_POSITION_BASE):
                    raise _DecoderError("invalid LZX position slot")
                extra = _EXTRA[slot]
                offset = _POSITION_BASE[slot] - 2
                if aligned:
                    if extra > 3:
                        offset += (bits.read(extra - 3) << 3) + self.aligned.symbol(bits)
                    elif extra == 3:
                        offset += self.aligned.symbol(bits)
                    elif extra:
                        offset += bits.read(extra)
                    else:
                        offset = 1
                elif slot == 3:
                    offset = 1
                else:
                    offset += bits.read(extra)
                r2, r1, r0 = r1, r0, offset

            if offset <= 0 or offset > _WINDOW_SIZE:
                raise _DecoderError("invalid LZX match offset")
            source = position - offset
            if source < 0:
                source += _WINDOW_SIZE
            for _ in range(length):
                if position >= _WINDOW_SIZE or source >= _WINDOW_SIZE:
                    raise _DecoderError("match crosses an unsupported window boundary")
                self.window[position] = self.window[source]
                position += 1
                source += 1
                if source == _WINDOW_SIZE:
                    source = 0
            remaining -= original_length
        return position, (r0, r1, r2)

    def decode_frame(self, data: bytes, start: int, compressed_count: int,
                     output: bytearray, output_start: int, output_count: int) -> None:
        source = _ByteCursor(data, start)
        bits = _BitWords(source)
        limit = start + compressed_count
        position = self.window_position
        repeated = (self.r0, self.r1, self.r2)
        remaining = output_count

        if not self.header_read:
            if bits.read(1):
                self.intel_file_size = (bits.read(16) << 16) | bits.read(16)
            self.header_read = True

        while remaining:
            if self.block_remaining == 0:
                if self.block_kind == _UNCOMPRESSED:
                    if self.block_length & 1:
                        source.byte()
                    bits.reset()
                self.block_kind = bits.read(3)
                self.block_length = (bits.read(16) << 8) | bits.read(8)
                self.block_remaining = self.block_length
                if self.block_length == 0:
                    raise _DecoderError("zero-length LZX block")
                if self.block_kind == _ALIGNED:
                    for index in range(_ALIGNED_COUNT):
                        self.aligned.lengths[index] = bits.read(3)
                    self.aligned.rebuild()
                    self._read_main_trees(bits)
                elif self.block_kind == _VERBATIM:
                    self._read_main_trees(bits)
                elif self.block_kind == _UNCOMPRESSED:
                    self.intel_started = True
                    bits.ensure(16)
                    if bits.count > 16:
                        source.move(-2)
                    repeated = (source.u32le(), source.u32le(), source.u32le())
                    if source.failed:
                        raise _DecoderError("truncated uncompressed LZX block header")
                else:
                    raise _DecoderError(f"invalid LZX block type {self.block_kind}")

            if source.position > limit and (source.position > limit + 2 or bits.count < 16):
                raise _DecoderError("compressed block consumed beyond its frame")
            run = min(self.block_remaining, remaining)
            remaining -= run
            self.block_remaining -= run
            position &= _WINDOW_SIZE - 1
            if position + run > _WINDOW_SIZE:
                raise _DecoderError("output run crosses the LZX window boundary")
            if self.block_kind in (_VERBATIM, _ALIGNED):
                position, repeated = self._copy_matches(
                    run, self.block_kind == _ALIGNED, bits, position, repeated
                )
            else:
                source.copy(self.window, position, run, limit)
                position += run

        copy_start = (_WINDOW_SIZE if position == 0 else position) - output_count
        if copy_start < 0 or copy_start + output_count > _WINDOW_SIZE:
            raise _DecoderError("decoded frame is outside the LZX window")
        output[output_start:output_start + output_count] = self.window[
            copy_start:copy_start + output_count
        ]
        self.window_position = position
        self.r0, self.r1, self.r2 = repeated
        reject_intel = self.frame_count < 32768 and self.intel_file_size != 0
        self.frame_count += 1
        if reject_intel:
            raise _DecoderError("XNB LZX stream advertises the unsupported Intel E8 transform")


def _failure(asset_name: str, detail: str) -> ContentLoadException:
    return ContentLoadException(
        f"Error loading '{asset_name}'. Invalid LZX stream: {detail}"
    )


def _decompress_xnb_lzx(compressed: bytes, decompressed_size: int, asset_name: str) -> bytes:
    if not isinstance(compressed, bytes):
        raise _failure(asset_name, "compressed payload is not bytes")
    if type(decompressed_size) is not int or decompressed_size < 0 or decompressed_size > _MAX_OUTPUT:
        raise _failure(asset_name, f"invalid decompressed size {decompressed_size}")
    decoder = _LzxStream()
    output = bytearray(decompressed_size)
    source_position = 0
    output_position = 0

    try:
        while source_position < len(compressed):
            remaining = len(compressed) - source_position
            if remaining < 2:
                raise _DecoderError("truncated frame header")
            first, second = compressed[source_position:source_position + 2]
            if first == 0xFF:
                if remaining < 5:
                    raise _DecoderError("truncated extended frame header")
                frame_size = (second << 8) | compressed[source_position + 2]
                block_size = (compressed[source_position + 3] << 8) | compressed[source_position + 4]
                header_size = 5
            else:
                frame_size = _FRAME
                block_size = (first << 8) | second
                header_size = 2

            if frame_size == 0 or block_size == 0:
                if output_position != decompressed_size:
                    raise _DecoderError(
                        "invalid zero frame size" if frame_size == 0 else "invalid zero block size"
                    )
                if any(compressed[source_position:]):
                    raise _DecoderError("nonzero data follows the LZX end marker")
                source_position = len(compressed)
                break
            if frame_size > _FRAME:
                raise _DecoderError(f"frame size {frame_size} exceeds {_FRAME}")
            if frame_size > decompressed_size - output_position:
                raise _DecoderError("frame exceeds the declared decompressed size")
            block_start = source_position + header_size
            if block_size > len(compressed) - block_start:
                raise _DecoderError("truncated compressed frame payload")
            decoder.decode_frame(
                compressed, block_start, block_size,
                output, output_position, frame_size,
            )
            output_position += frame_size
            source_position = block_start + block_size
    except _DecoderError as error:
        raise _failure(asset_name, str(error)) from error

    if output_position != decompressed_size:
        raise _failure(
            asset_name,
            f"decoded {output_position} bytes; expected {decompressed_size}",
        )
    return bytes(output)

