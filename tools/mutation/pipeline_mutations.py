#!/usr/bin/env python3
"""Planted defects for the XNA Content Pipeline, and the tests that must catch them.

The same harness the other families use: each entry replaces one exact string in
one file, runs the suite, and puts the file back. A mutation that survives is a
test gap, not a curiosity -- every one of these is a defect a careless change
could really introduce, and most of them are shaped like a mistake that was
actually made while the code was written.

The pipeline needs no CNA library, so this runs anywhere.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]

MUTATIONS = [
    # --- image decoders ------------------------------------------------------
    ("png: undo the Sub filter against the wrong neighbour",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "                line[index] = (line[index] + line[index - channels]) & 0xFF",
     "                line[index] = (line[index] + line[index - 1]) & 0xFF",
     "tests.test_content_pipeline"),
    ("png: undo the Up filter against the row it is on",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "                line[index] = (line[index] + previous[index]) & 0xFF",
     "                line[index] = (line[index] + line[index]) & 0xFF",
     "tests.test_content_pipeline"),
    ("png: round the Average filter up instead of down",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF",
     "                line[index] = (line[index] + ((left + previous[index] + 1) >> 1)) & 0xFF",
     "tests.test_content_pipeline"),
    ("png: break the Paeth predictor's tie the other way",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "    if distance_left <= distance_above and distance_left <= distance_corner:\n"
     "        return left\n"
     "    return above if distance_above <= distance_corner else upper_left",
     "    if distance_left < distance_above and distance_left < distance_corner:\n"
     "        return left\n"
     "    return above if distance_above < distance_corner else upper_left",
     "tests.test_content_pipeline"),
    ("png: read a palette entry's alpha from the wrong index",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "                alpha = transparency[index] if index < len(transparency) else 255",
     "                alpha = 255",
     "tests.test_content_pipeline"),
    ("png: accept an interlaced file and read it as if it were not",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "    if interlace != 0:",
     "    if False:",
     "tests.test_content_pipeline"),
    ("bmp: read a bottom-up file top-down",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "        source = y if top_down else height - 1 - y",
     "        source = y",
     "tests.test_content_pipeline"),
    ("bmp: read the channels in the order they are stored",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "            blue, green, red = raw[pixel], raw[pixel + 1], raw[pixel + 2]",
     "            red, green, blue = raw[pixel], raw[pixel + 1], raw[pixel + 2]",
     "tests.test_content_pipeline"),
    ("tga: ignore the top-down bit in the descriptor",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "    if not descriptor & 0x20:\n        rows.reverse()",
     "    if False:\n        rows.reverse()",
     "tests.test_content_pipeline"),
    ("tga: run-length packets are one pixel shorter than they say",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "            count = (packet & 0x7F) + 1",
     "            count = (packet & 0x7F)",
     "tests.test_content_pipeline"),
    ("dds: scale a channel by shifting instead of replicating",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_images.py",
     "    return (raw_value * 255) // ((1 << width) - 1)",
     "    return raw_value << (8 - width)",
     "tests.test_content_pipeline"),

    # --- the DXT codec -------------------------------------------------------
    ("dxt: interpolate the palette one-third and two-thirds the other way",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "        return [zero + (255,), one + (255,),\n"
     "                _lerp(zero, one, 2, 3) + (255,), _lerp(zero, one, 1, 3) + (255,)]",
     "        return [zero + (255,), one + (255,),\n"
     "                _lerp(zero, one, 1, 3) + (255,), _lerp(zero, one, 2, 3) + (255,)]",
     "tests.test_content_pipeline"),
    ("dxt: decode 565 by shifting rather than replicating the high bits",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "    return ((red << 3) | (red >> 2), (green << 2) | (green >> 4),\n"
     "            (blue << 3) | (blue >> 2))",
     "    return (red << 3, green << 2, blue << 3)",
     "tests.test_content_pipeline"),
    ("dxt1: choose the endpoints along the widest channel only",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "    def projection(pixel: Color) -> int:\n"
     "        return pixel.R * axis[0] + pixel.G * axis[1] + pixel.B * axis[2]",
     "    def projection(pixel: Color) -> int:\n"
     "        return pixel.R",
     "tests.test_content_pipeline"),
    # Swapping two equal endpoints is a no-op, so ``first < second`` and
    # ``first <= second`` cannot be told apart. What a constant block is
    # actually vulnerable to is being *nudged* into the four-colour form, which
    # moves the one colour it has -- that is the defect planted here.
    ("dxt1: nudge a constant block into the four-colour form",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "    elif not transparent and first < second:\n        first, second = second, first",
     "    elif not transparent and first <= second:\n        first, second = second, first\n"
     "        if first == second:\n            second = max(0, second - 1)",
     "tests.test_content_pipeline"),
    ("dxt1: give a transparent pixel the nearest colour instead of slot three",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "        if transparent and pixel.A < 128:\n"
     "            indices |= 0x3 << (index * 2)\n"
     "            continue",
     "        if False:\n"
     "            indices |= 0x3 << (index * 2)\n"
     "            continue",
     "tests.test_content_pipeline"),
    ("dxt5: use the six-value alpha table where the eight-value one belongs",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "    if first > second:\n"
     "        return [first, second] + [\n"
     "            ((8 - index) * first + (index - 1) * second) // 7\n"
     "            for index in range(2, 8)]",
     "    if False:\n"
     "        return [first, second] + [\n"
     "            ((8 - index) * first + (index - 1) * second) // 7\n"
     "            for index in range(2, 8)]",
     "tests.test_content_pipeline"),
    ("dxt3: expand four-bit alpha by shifting instead of replicating",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "        return [(((packed >> (index * 4)) & 0xF) * 17) for index in range(16)]",
     "        return [(((packed >> (index * 4)) & 0xF) << 4) for index in range(16)]",
     "tests.test_content_pipeline"),
    ("dxt: pad a partial block with black instead of the edge pixel",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "                block = [\n"
     "                    pixels[min(block_y * 4 + row, self._height - 1)]\n"
     "                          [min(block_x * 4 + column, self._width - 1)]\n"
     "                    for row in range(4) for column in range(4)]",
     "                block = [\n"
     "                    pixels[min(block_y * 4 + row, self._height - 1)][0]\n"
     "                    for row in range(4) for column in range(4)]",
     "tests.test_content_pipeline"),

    # --- bitmaps and textures ------------------------------------------------
    ("resample: take the nearest source pixel instead of the box average",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_bitmap.py",
     "                value = _box(source, source_region, destination_region, x, y)",
     "                value = to_vector4(source.GetPixel(\n"
     "                    source_region.X + x * source_region.Width\n"
     "                    // destination_region.Width,\n"
     "                    source_region.Y + y * source_region.Height\n"
     "                    // destination_region.Height))",
     "tests.test_content_pipeline"),
    # Swapping the premultiply and the *resize* is equivalent and is not
    # planted: rounding up to a power of two makes every destination pixel
    # cover one source pixel, so the resize never averages. Moving the
    # premultiply past the *mipmaps* is the observable form of the same
    # mistake, and is what is planted here.
    ("texture: premultiply after building the mipmaps instead of before",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Processors/_texture_processors.py",
     "        if self.PremultiplyAlpha:\n"
     "            _premultiply(input)\n"
     "        if self.ResizeToPowerOfTwo:\n"
     "            _resize_to_power_of_two(input)\n"
     "        if self.GenerateMipmaps:\n"
     "            input.GenerateMipmaps(False)",
     "        if self.ResizeToPowerOfTwo:\n"
     "            _resize_to_power_of_two(input)\n"
     "        if self.GenerateMipmaps:\n"
     "            input.GenerateMipmaps(False)\n"
     "        if self.PremultiplyAlpha:\n"
     "            _premultiply(input)",
     "tests.test_content_pipeline"),
    ("texture: colour-key to transparent magenta instead of transparent black",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Processors/_texture_processors.py",
     "    clear = Color(0, 0, 0, 0)",
     "    clear = Color(255, 0, 255, 0)",
     "tests.test_content_pipeline"),
    ("texture: compress to DXT1 whatever the alpha is",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Processors/_texture_processors.py",
     "                Dxt5BitmapContent if _has_alpha(input) else Dxt1BitmapContent)",
     "                Dxt1BitmapContent)",
     "tests.test_content_pipeline"),
    ("texture: round a power of two down instead of up",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Processors/_texture_processors.py",
     "    result = 1\n    while result < value:\n        result *= 2\n    return result",
     "    result = 1\n    while result * 2 <= value:\n        result *= 2\n    return result",
     "tests.test_content_pipeline"),
    ("validate: allow a mipmap level that is not half the one above",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_texture.py",
     "            if bitmap.Width != width or bitmap.Height != height:",
     "            if False:",
     "tests.test_content_pipeline"),
    ("validate: give Reach the HiDef size limit",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_texture.py",
     "_PROFILE_LIMITS = {GraphicsProfile.Reach: 2048, GraphicsProfile.HiDef: 4096}",
     "_PROFILE_LIMITS = {GraphicsProfile.Reach: 4096, GraphicsProfile.HiDef: 4096}",
     "tests.test_content_pipeline"),
    ("volume: average within a slice instead of across two",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_texture.py",
     "                far = _as_pixels(source[min(index * 2 + 1, len(source) - 1)])",
     "                far = _as_pixels(source[min(index * 2, len(source) - 1)])",
     "tests.test_content_pipeline"),

    # --- meshes --------------------------------------------------------------
    ("normals: normalise each triangle before accumulating, losing the area weight",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "                weighted = Vector3.Cross(first, second)",
     "                weighted = _normalized(Vector3.Cross(first, second))",
     "tests.test_content_pipeline"),
    ("normals: overwrite an artist's normals whatever the caller asked",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "                if not overwriteExistingNormals:\n                    continue",
     "                pass",
     "tests.test_content_pipeline"),
    ("tangents: leave the tangent unorthogonalised against the normal",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "                tangents[index] = _orthogonalized(tangents[index], normal)",
     "                tangents[index] = _normalized(tangents[index])",
     "tests.test_content_pipeline"),
    ("winding: reverse the first two corners instead of the last two",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "                geometry.Indices.AddRange((first, third, second))",
     "                geometry.Indices.AddRange((second, first, third))",
     "tests.test_content_pipeline"),
    ("transform: put direction channels through the whole matrix",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "                            channel[index] = _normalized(\n"
     "                                Vector3.TransformNormal(channel[index], transform))",
     "                            channel[index] = _normalized(\n"
     "                                Vector3.Transform(channel[index], transform))",
     "tests.test_content_pipeline"),
    ("skeleton: flatten breadth-first instead of depth-first",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "            bone = pending.pop()",
     "            bone = pending.pop(0)",
     "tests.test_content_pipeline"),
    ("bone weights: keep the smallest influences instead of the largest",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_node.py",
     "        ordered = sorted(self._items, key=lambda weight: -weight.Weight)[:limit]",
     "        ordered = sorted(self._items, key=lambda weight: weight.Weight)[:limit]",
     "tests.test_content_pipeline"),
    ("bone weights: drop the small influences without rescaling what is left",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_node.py",
     "            self._items.append(BoneWeight(weight.BoneName, weight.Weight / total))",
     "            self._items.append(BoneWeight(weight.BoneName, weight.Weight))",
     "tests.test_content_pipeline"),
    ("mesh builder: merge two vertices that share a position but not a normal",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "            if all(channel[index] == value\n"
     "                   for channel, value in zip(geometry.Vertices.Channels, values)):\n"
     "                return index",
     "            return index",
     "tests.test_content_pipeline"),
    ("mesh builder: let a channel be declared after the first vertex",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_mesh.py",
     "        if self._started:\n"
     "            raise RuntimeError(",
     "        if False:\n"
     "            raise RuntimeError(",
     "tests.test_content_pipeline"),
    ("geometry: keep a private position list after joining a mesh",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Graphics/_node.py",
     "        self._vertices = moved",
     "        pass",
     "tests.test_content_pipeline"),
    ("child collection: let a node be stolen from its parent",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_collections.py",
     "        if existing is not None and existing is not self._parent:",
     "        if False:",
     "tests.test_content_pipeline"),

    # --- the .x reader -------------------------------------------------------
    ("x reader: index normals by position instead of by the normal face list",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_importers.py",
     "                    normal_index = normal_faces[face_index][corner] \\\n"
     "                        if face_index < len(normal_faces) else position",
     "                    normal_index = position",
     "tests.test_content_pipeline"),
    ("x reader: skip a closing brace as if it were a separator",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_importers.py",
     "                self._tokens[self._position] in (\";\", \",\"):",
     "                self._tokens[self._position] in (\";\", \",\", \"}\"):",
     "tests.test_content_pipeline"),
    ("x reader: read a binary file as if it were text",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_importers.py",
     "        if header[8:12] != \"txt \":",
     "        if False:",
     "tests.test_content_pipeline"),
    ("x reader: read the transform's rows as its columns",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_importers.py",
     "        values = [self._number() for _ in range(16)]\n        return Matrix(*values)",
     "        values = [self._number() for _ in range(16)]\n"
     "        return Matrix(*[values[column * 4 + row]\n"
     "                        for row in range(4) for column in range(4)])",
     "tests.test_content_pipeline"),
    ("font description: strip a character region bound before reading it",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_importers.py",
     "    return found.text if len(found.text) == 1 else found.text.strip()",
     "    return found.text.strip()",
     "tests.test_content_pipeline"),
    ("effect importer: record no dependency for an included header",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_importers.py",
     "            context.AddDependency(os.path.join(directory, match.group(1)))",
     "            pass",
     "tests.test_content_pipeline"),

    # --- audio ---------------------------------------------------------------
    ("wav: report the loop length one sample short",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Audio/_audio.py",
     "    return start, max(0, end - start + 1)",
     "    return start, max(0, end - start)",
     "tests.test_content_pipeline"),
    ("wav: skip the pad byte after an odd-sized chunk",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Audio/_audio.py",
     "        position += 8 + size + (size & 1)",
     "        position += 8 + size",
     "tests.test_content_pipeline"),
    ("wav: report the block align as the bytes per sample",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Audio/_audio.py",
     "    (tag, channels, rate, average, align, bits) = struct.unpack_from(\"<HHIIHH\", body, 0)",
     "    (tag, channels, rate, average, bits, align) = struct.unpack_from(\"<HHIIHH\", body, 0)",
     "tests.test_content_pipeline"),
    ("mp3: report the sample rate from the wrong MPEG version table",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Audio/_audio.py",
     "    rate = _MPEG_SAMPLE_RATES[version][rate_index]",
     "    rate = _MPEG_SAMPLE_RATES[2][rate_index]",
     "tests.test_content_pipeline"),
    ("mp3: answer sample data that is not there",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Audio/_audio.py",
     "            self._undecodable = \"MPEG audio\"",
     "            self._undecodable = None",
     "tests.test_content_pipeline"),
    ("mp3: ignore an ID3 tag's length and search from the start",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Audio/_audio.py",
     "        start = 10 + size",
     "        start = 0",
     "tests.test_content_pipeline"),

    # --- the XNB compiler ----------------------------------------------------
    ("xnb: count a string's characters instead of its bytes",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_binary_writer.py",
     "        encoded = value.encode(\"utf-8\")\n        self.Write7BitEncodedInt(len(encoded))",
     "        encoded = value.encode(\"utf-8\")\n        self.Write7BitEncodedInt(len(value))",
     "tests.test_content_pipeline"),
    ("xnb: write a 7-bit encoded int with the continuation bit on the wrong byte",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_binary_writer.py",
     "        while remaining >= 0x80:",
     "        while remaining > 0x80:",
     "tests.test_content_pipeline"),
    ("xnb: leave the header out of the declared file size",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "        total = len(header) + 4 + len(payload)",
     "        total = len(payload)",
     "tests.test_content_pipeline"),
    ("xnb: write every file as if it were for Windows",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "                        _PLATFORM_BYTES[platform], _FORMAT_VERSION, flags))",
     "                        _PLATFORM_BYTES[TargetPlatform.Windows],\n"
     "                        _FORMAT_VERSION, flags))",
     "tests.test_content_pipeline"),
    ("xnb: write XNA 3.1's format version",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "_FORMAT_VERSION = 5",
     "_FORMAT_VERSION = 4",
     "tests.test_content_pipeline"),
    ("xnb: leave the HiDef flag out of the header",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "        flags = _HIDEF_FLAG if profile is GraphicsProfile.HiDef else 0",
     "        flags = 0",
     "tests.test_content_pipeline"),
    ("xnb: index the reader table from zero, where zero means null",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "        for index, entry in enumerate(self._writers):\n"
     "            if entry is writer:\n"
     "                return index + 1",
     "        for index, entry in enumerate(self._writers):\n"
     "            if entry is writer:\n"
     "                return index",
     "tests.test_content_pipeline"),
    ("xnb: name a list reader after its element's reader",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "        return f\"{_PREFIX}ListReader`1[[{_runtime_name(self._element)}]]\"",
     "        return f\"{_PREFIX}ListReader`1[[{_PREFIX}Int32Reader]]\"",
     "tests.test_content_pipeline"),
    ("xnb: leave a list's element writer out of the reader table",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "        self._compiler._index_of(writer)",
     "        pass",
     "tests.test_content_pipeline"),
    ("xnb: share resources by equality instead of by identity",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "        key = id(value)\n        index = self._shared_indices.get(key)",
     "        key = repr(type(value))\n        index = self._shared_indices.get(key)",
     "tests.test_content_pipeline"),
    ("xnb: stop writing shared resources when the first pass ends",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "        while index < len(writer._shared_resources):",
     "        for index in range(len(writer._shared_resources)):",
     "tests.test_content_pipeline"),
    ("xnb: read a TimeSpan's ticks through a float",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "    ticks = ((value.days * 86_400 + value.seconds) * _TICKS_PER_SECOND\n"
     "             + value.microseconds * 10)",
     "    ticks = int(value.total_seconds() * _TICKS_PER_SECOND)",
     "tests.test_content_pipeline"),
    ("xnb: write a Color as four floats rather than four bytes",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "            self.WriteByte(value.R)\n"
     "            self.WriteByte(value.G)\n"
     "            self.WriteByte(value.B)\n"
     "            self.WriteByte(value.A)",
     "            self.WriteSingle(value.R)\n"
     "            self.WriteSingle(value.G)\n"
     "            self.WriteSingle(value.B)\n"
     "            self.WriteSingle(value.A)",
     "tests.test_content_pipeline"),
    ("xnb: write a matrix transposed",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_compiler.py",
     "            for row in range(1, 5):\n"
     "                for column in range(1, 5):\n"
     "                    self.WriteSingle(getattr(value, f\"M{row}{column}\"))",
     "            for row in range(1, 5):\n"
     "                for column in range(1, 5):\n"
     "                    self.WriteSingle(getattr(value, f\"M{column}{row}\"))",
     "tests.test_content_pipeline"),
    ("xnb: write a model's child count before its parent reference",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "        _write_bone_reference(output, len(bones), bone.Parent)\n"
     "        output.WriteUInt32(len(bone.Children))",
     "        output.WriteUInt32(len(bone.Children))\n"
     "        _write_bone_reference(output, len(bones), bone.Parent)",
     "tests.test_content_pipeline"),
    ("xnb: write a bone reference without the null offset",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "    index = 0 if bone is None else bone.Index + 1",
     "    index = 0 if bone is None else bone.Index",
     "tests.test_content_pipeline"),
    ("xnb: write a vertex declaration with a type index in front of it",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "    output.WriteRawObject(value.VertexDeclaration)",
     "    output.WriteObject(value.VertexDeclaration)",
     "tests.test_content_pipeline"),
    ("xnb: write 32-bit indices when 16 would do",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "    sixteen = all(0 <= index <= 0xFFFF for index in indices)",
     "    sixteen = False",
     "tests.test_content_pipeline"),
    ("xnb: write a texture's levels without their byte counts",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "        data = level.GetPixelData()\n        output.WriteUInt32(len(data))\n        output.WriteBytes(data)",
     "        data = level.GetPixelData()\n        output.WriteBytes(data)",
     "tests.test_content_pipeline"),
    ("xnb: give a BasicEffect an alpha of zero where the material says nothing",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Compiler/_writers.py",
     "    output.WriteSingle(1.0 if value.Alpha is None else value.Alpha)",
     "    output.WriteSingle(0.0 if value.Alpha is None else value.Alpha)",
     "tests.test_content_pipeline"),

    # --- the intermediate serializer ----------------------------------------
    ("intermediate: write a float rounded to six places",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Intermediate/_serializers.py",
     "    text = repr(float(value))",
     "    text = f\"{float(value):.6g}\"",
     "tests.test_content_pipeline"),
    ("intermediate: write opaque data in insertion order",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Intermediate/_intermediate.py",
     "        for key in sorted(data.Keys):",
     "        for key in data.Keys:",
     "tests.test_content_pipeline"),
    ("intermediate: write a property whose value the object does not carry",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Intermediate/_serializers.py",
     "            if entry is None:\n                continue",
     "            if entry is None:\n                entry = 0",
     "tests.test_content_pipeline"),
    ("intermediate: read a file into whatever type was asked for",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Intermediate/_intermediate.py",
     "        if value is not None and not isinstance(value, targetType):",
     "        if False:",
     "tests.test_content_pipeline"),
    ("intermediate: serialize a dictionary's derived Count and Keys as well",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Serialization/Intermediate/_serializers.py",
     "            if member.fset is None:\n"
     "                declared = _declared_type(target, member)\n"
     "                if declared is None or not issubclass(declared, readable_into):\n"
     "                    continue",
     "            if False:\n"
     "                declared = _declared_type(target, member)\n"
     "                if declared is None or not issubclass(declared, readable_into):\n"
     "                    continue",
     "tests.test_content_pipeline"),

    # --- the build tasks -----------------------------------------------------
    ("build: ignore a dependency's timestamp when deciding to rebuild",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Tasks/_tasks.py",
     "        for dependency in entry.get(\"dependencies\", ()):\n"
     "            if not os.path.exists(dependency) \\\n"
     "                    or os.path.getmtime(dependency) > built:\n"
     "                return False",
     "        pass",
     "tests.test_content_pipeline"),
    ("build: treat a newer source as up to date",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Tasks/_tasks.py",
     "        if not os.path.exists(source) or os.path.getmtime(source) > built:\n"
     "            return False",
     "        pass",
     "tests.test_content_pipeline"),
    ("build: report success when an asset failed",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Tasks/_tasks.py",
     "                succeeded = False\n"
     "                self._logger.LogWarning(\"\", None, \"{0}: {1}\", source, error)",
     "                self._logger.LogWarning(\"\", None, \"{0}: {1}\", source, error)",
     "tests.test_content_pipeline"),
    ("build: rebuild everything even when RebuildAll is off",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Tasks/_tasks.py",
     "            if not self.RebuildAll and self._is_current(source, target, entry):",
     "            if False:",
     "tests.test_content_pipeline"),
    ("build: honour the cache even when RebuildAll is on",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Tasks/_tasks.py",
     "            if not self.RebuildAll and self._is_current(source, target, entry):",
     "            if self._is_current(source, target, entry):",
     "tests.test_content_pipeline"),
    ("clean: delete every xnb under the output directory",
     "src/Microsoft/Xna/Framework/Content/Pipeline/Tasks/_tasks.py",
     "        for entry in cache.values():\n"
     "            for name in [entry.get(\"output\")] + list(entry.get(\"outputs\", ())):\n"
     "                if name and os.path.exists(name):\n"
     "                    os.remove(name)",
     "        import glob\n"
     "        for name in glob.glob(os.path.join(self.OutputDirectory, \"*.xnb\")):\n"
     "            os.remove(name)",
     "tests.test_content_pipeline"),
    ("scanner: let one broken module empty the whole scan",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_components.py",
     "            except Exception as error:  # noqa: BLE001 - reported, never raised\n"
     "                errors.append(f\"{name}: {error}\")\n"
     "                continue",
     "            except Exception as error:  # noqa: BLE001 - reported, never raised\n"
     "                errors.append(f\"{name}: {error}\")\n"
     "                return True",
     "tests.test_content_pipeline"),
    ("scanner: offer a processor's read-only settings as parameters",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_components.py",
     "        if member.fset is None:\n            continue",
     "        pass",
     "tests.test_content_pipeline"),
    ("scanner: report no change when the components changed",
     "src/Microsoft/Xna/Framework/Content/Pipeline/_components.py",
     "        return state != previous",
     "        return False",
     "tests.test_content_pipeline"),
]


#: The generated trees a mutation may need rebuilt before it means anything, and
#: the generator that rebuilds each. A defect in a *generator* only reaches the
#: code under test once the generator has run.
GENERATORS = {
    "tools/generate_xbox_profile.py": (
        "tools/generate_xbox_profile.py", "src/cna/profiles"),
}


def _regenerate(relative: str) -> dict[Path, str]:
    """Runs the generator a mutated file belongs to; answers what it overwrote."""
    entry = GENERATORS.get(relative)
    if entry is None:
        return {}
    generator, tree = entry
    root = ROOT / tree
    before = {path: path.read_text(encoding="utf-8")
              for path in root.rglob("*.py")}
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
    subprocess.run([sys.executable, generator], cwd=str(ROOT), env=environment,
                   capture_output=True, text=True, timeout=300)
    return before


def run(module: str) -> tuple[bool, str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = f"{ROOT / 'src'}{os.pathsep}{ROOT}"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=str(ROOT), env=environment, capture_output=True, text=True, timeout=1800)
    return completed.returncode == 0, completed.stderr


def main() -> int:
    killed, survived, inapplicable = [], [], []
    for label, relative, old, new, module in MUTATIONS:
        path = ROOT / relative
        original = path.read_text(encoding="utf-8")
        if original.count(old) != 1:
            inapplicable.append((label, f"anchor appears {original.count(old)} times"))
            continue
        path.write_text(original.replace(old, new), encoding="utf-8")
        generated = _regenerate(relative)
        try:
            for cache in ROOT.rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
            passed, stderr = run(module)
        finally:
            path.write_text(original, encoding="utf-8")
            for target, text in generated.items():
                target.write_text(text, encoding="utf-8")
            for cache in ROOT.rglob("__pycache__"):
                subprocess.run(["rm", "-rf", str(cache)], check=False)
        if passed:
            survived.append((label, module))
        else:
            names = [line.split(" ")[1] for line in stderr.splitlines()
                     if line.startswith(("FAIL: ", "ERROR: "))]
            killed.append((label, module, names[:3]))

    print(f"PLANTED={len(MUTATIONS)}")
    print(f"KILLED={len(killed)}")
    print(f"SURVIVED={len(survived)}")
    print(f"INAPPLICABLE={len(inapplicable)}")
    for label, module, names in killed:
        print(f"  KILLED  {label}")
        if names:
            print(f"            by {module}: {', '.join(names)}")
    for label, module in survived:
        print(f"  SURVIVED {label} (ran {module})")
    for label, reason in inapplicable:
        print(f"  SKIPPED  {label}: {reason}")
    return 1 if survived or inapplicable else 0




#: The Xbox 360 surface profile. Small, because most of the profile is
#: *generated* and the generator's own check is what guards it -- but the rules
#: that make the generation correct are not generated, and these plant them.
XBOX_MUTATIONS = [
    ("xbox: treat the two encodings of `where T : struct` as different",
     "tools/api_compat/verify.py",
     "    if \"struct\" in value.get(\"specialConstraints\", ()) \\\n"
     "            and \"System.ValueType\" in constraints:\n"
     "        constraints.remove(\"System.ValueType\")",
     "    pass",
     "tests.test_xbox360_profile"),
    ("xbox: let a removed member hide one the platform still has",
     "tools/verify_profile_separation.py",
     "                if any(projected_name(platform, value, rules) == member\n"
     "                       for value in platform[\"members\"]):\n"
     "                    unjustified.append(\n"
     "                        f\"{entry['member']}: the platform contract still has it\")",
     "                pass",
     "tests.test_xbox360_profile"),
    ("xbox: check only the namespace a Windows-only type came from",
     "tools/verify_profile_separation.py",
     "            if name in exported:",
     "            if False:",
     "tests.test_xbox360_profile"),
    ("xbox: stop comparing the default profile's counts",
     "tools/verify_profile_separation.py",
     "    if measured[\"TARGET_TYPES\"] != DEFAULT_TYPES:",
     "    if False:",
     "tests.test_xbox360_profile"),
    ("xbox: raise only when a removed member is called, not when it is read",
     "tools/generate_xbox_profile.py",
     "    def __get__(self, instance: object, owner: type | None = None):\n"
     "        raise AttributeError(f\"{self._name} is not declared on this platform: \"\n"
     "                             f\"{self._reason}\")",
     "    def __get__(self, instance: object, owner: type | None = None):\n"
     "        def refuse(*arguments: object) -> None:\n"
     "            raise AttributeError(self._name)\n"
     "        return refuse",
     "tests.test_xbox360_profile"),
    ("xbox: narrow a type without keeping it catchable as the Windows one",
     "tools/generate_xbox_profile.py",
     "        bases = [f\"_Windows{name}\"]\n"
     "        if name in base_of:\n"
     "            bases.append(base_of[name])",
     "        bases = [base_of[name]] if name in base_of else [\"Exception\"]",
     "tests.test_xbox360_profile"),
    ("xbox: export a type the Xbox assemblies do not declare",
     "tools/generate_xbox_profile.py",
     "        exports.setdefault(namespace, []).append(name)",
     "        exports.setdefault(namespace, []).append(name)\n"
     "        if namespace == \"Microsoft.Xna.Framework\":\n"
     "            exports[namespace].append(\"ColorConverter\")",
     "tests.test_xbox360_profile"),
]

MUTATIONS = MUTATIONS + XBOX_MUTATIONS

if __name__ == "__main__":
    raise SystemExit(main())
