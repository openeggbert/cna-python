#!/usr/bin/env python3
"""Execute the normalized pure XNA-derived behavior corpus."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from Microsoft.Xna.Framework import (  # noqa: E402
    BoundingBox, BoundingFrustum, BoundingSphere, Color, ContainmentType,
    Curve, CurveContinuity, CurveKey, CurveLoopType, CurveTangent, MathHelper,
    Matrix, Plane, Point, Quaternion, Ray, Rectangle, Vector2, Vector3, Vector4,
)
from Microsoft.Xna.Framework.Graphics import (  # noqa: E402
    BlendState, DepthStencilState, EffectParameterClass, EffectParameterType,
    Model, ModelBone, ModelMesh, ModelMeshPart, PresentationParameters, RasterizerState,
    SamplerState, SurfaceFormat, VertexPositionColor,
    VertexPositionColorTexture, VertexPositionNormalTexture,
    VertexPositionTexture, Viewport,
)
from Microsoft.Xna.Framework._numeric import f32  # noqa: E402
from Microsoft.Xna.Framework.Content import (  # noqa: E402
    ContentLoadException, ContentManager, ContentReader, ContentSerializerAttribute,
    ContentTypeReaderOfT, ResourceContentManager,
)
from Microsoft.Xna.Framework.Content._content import _register_content_type_reader  # noqa: E402
from Microsoft.Xna.Framework.Audio import (  # noqa: E402
    AudioCategory, AudioChannels, AudioEmitter, AudioListener, AudioStopOptions,
    MicrophoneState, RendererDetail, SoundEffect, SoundState,
)
from Microsoft.Xna.Framework.Graphics.PackedVector import (  # noqa: E402
    Alpha8, Bgr565, Bgra4444, Bgra5551, Byte4, HalfSingle, HalfVector2,
    HalfVector4, NormalizedByte2, NormalizedByte4, NormalizedShort2,
    NormalizedShort4, Rg32, Rgba1010102, Rgba64, Short2, Short4,
)
from Microsoft.Xna.Framework.Design import (  # noqa: E402
    BoundingBoxConverter, BoundingSphereConverter, ColorConverter,
    MathTypeConverter, MatrixConverter, PlaneConverter, PointConverter,
    QuaternionConverter, RayConverter, RectangleConverter, Vector2Converter,
    Vector3Converter, Vector4Converter,
)
from Microsoft.Xna.Framework.Input.Touch import (  # noqa: E402
    GestureSample, GestureType, TouchCollection, TouchLocation,
    TouchLocationState,
)


def vector2(value): return Vector2(*value)
def vector3(value): return Vector3(*value)
def vector4(value): return Vector4(*value)
def box(value): return BoundingBox(vector3(value[0]), vector3(value[1]))
def sphere(value): return BoundingSphere(vector3(value[0]), value[1])
def hex32(value): return f"{struct.unpack('=I', struct.pack('=f', value))[0]:08X}"
def hex_values(value): return [hex32(component) for component in value]
def float_from_bits(value): return struct.unpack('=f', struct.pack('=I', value))[0]


_PACKED_CORPUS = {
    "Alpha8": (Alpha8, (0.5,), (1.0,), (math.inf,), 0x5A),
    "Bgr565": (Bgr565, (0.25, 0.5, 0.75), (1.0, 1.0, 1.0), (-1.0, 2.0, math.inf), 0x1234),
    "Bgra4444": (Bgra4444, (0.25, 0.5, 0.75, 1.0), (1.0, 1.0, 1.0, 1.0), (-1.0, 2.0, math.nan, math.inf), 0x1234),
    "Bgra5551": (Bgra5551, (0.25, 0.5, 0.75, 1.0), (1.0, 1.0, 1.0, 1.0), (-1.0, 2.0, math.nan, math.inf), 0x9234),
    "Byte4": (Byte4, (1.5, 2.5, 3.5, 4.5), (255.0, 255.0, 255.0, 255.0), (-1.0, 256.0, math.nan, math.inf), 0x12345678),
    "HalfSingle": (HalfSingle, (1.5,), (131008.0,), (math.inf,), 0x3555),
    "HalfVector2": (HalfVector2, (1.0, -2.0), (131008.0, -131008.0), (math.inf, math.nan), 0x3555B555),
    "HalfVector4": (HalfVector4, (1.0, -2.0, 0.5, 4.0), (131008.0, -131008.0, 0.0, -0.0), (math.inf, -math.inf, math.nan, 2.0 ** -24), 0x3555B55500018000),
    "NormalizedByte2": (NormalizedByte2, (0.25, -0.75), (1.0, -1.0), (-2.0, 2.0), 0x817F),
    "NormalizedByte4": (NormalizedByte4, (0.25, -0.75, 0.5, -0.5), (1.0, -1.0, 1.0, -1.0), (-2.0, 2.0, math.nan, math.inf), 0x7F00817F),
    "NormalizedShort2": (NormalizedShort2, (0.25, -0.75), (1.0, -1.0), (-2.0, 2.0), 0x80017FFF),
    "NormalizedShort4": (NormalizedShort4, (0.25, -0.75, 0.5, -0.5), (1.0, -1.0, 1.0, -1.0), (-2.0, 2.0, math.nan, math.inf), 0x7FFF00007FFF8001),
    "Rg32": (Rg32, (0.25, 0.75), (1.0, 1.0), (-1.0, math.inf), 0x12345678),
    "Rgba1010102": (Rgba1010102, (0.25, 0.5, 0.75, 1.0), (1.0, 1.0, 1.0, 1.0), (-1.0, 2.0, math.nan, math.inf), 0xC1234567),
    "Rgba64": (Rgba64, (0.25, 0.5, 0.75, 1.0), (1.0, 1.0, 1.0, 1.0), (-1.0, 2.0, math.nan, math.inf), 0x123456789ABCDEF0),
    "Short2": (Short2, (1.5, -2.5), (32767.0, -32768.0), (-40000.0, 40000.0), 0x80007FFF),
    "Short4": (Short4, (1.5, -2.5, 3.5, -4.5), (32767.0, -32768.0, 32767.0, -32768.0), (-40000.0, 40000.0, math.nan, math.inf), 0xFFFF800000017FFF),
}

_DESIGN_CONVERTERS = {
    value.__name__: value for value in (
        MathTypeConverter, BoundingBoxConverter, BoundingSphereConverter,
        ColorConverter, MatrixConverter, PlaneConverter, PointConverter,
        QuaternionConverter, RayConverter, RectangleConverter, Vector2Converter,
        Vector3Converter, Vector4Converter,
    )
}

_DESIGN_VALUES = {
    "BoundingBoxConverter": BoundingBox(Vector3(1), Vector3(2)),
    "BoundingSphereConverter": BoundingSphere(Vector3(1), 2.0),
    "ColorConverter": Color(10, 20, 30, 40),
    "MatrixConverter": Matrix.Identity,
    "PlaneConverter": Plane(Vector3(1), 2.0),
    "PointConverter": Point(1, 2),
    "QuaternionConverter": Quaternion(1, 2, 3, 4),
    "RayConverter": Ray(Vector3(1), Vector3(2)),
    "RectangleConverter": Rectangle(1, 2, 3, 4),
    "Vector2Converter": Vector2(1, 2),
    "Vector3Converter": Vector3(1, 2, 3),
    "Vector4Converter": Vector4(1, 2, 3, 4),
}


def seven(value: int) -> bytes:
    result = bytearray()
    while value >= 0x80:
        result.append((value & 0x7f) | 0x80); value >>= 7
    result.append(value)
    return bytes(result)


def binary_string(value: str) -> bytes:
    encoded = value.encode("utf-8"); return seven(len(encoded)) + encoded


def content_xnb(readers, body: bytes, shared: int = 0) -> bytes:
    payload = bytearray(seven(len(readers)))
    for reader, version in readers:
        payload.extend(binary_string(reader)); payload.extend(struct.pack("<i", version))
    payload.extend(seven(shared)); payload.extend(body)
    return b"XNBw\x05\x00" + struct.pack("<I", len(payload) + 10) + payload


_STRING_READER = "Microsoft.Xna.Framework.Content.StringReader"


class _CorpusShared:
    def __init__(self): self.values = []


class _CorpusSharedReader(ContentTypeReaderOfT[_CorpusShared]):
    def Read(self, input, existingInstance):
        result = _CorpusShared()
        input.ReadSharedResource(lambda value: result.values.append("first:" + value))
        input.ReadSharedResource(lambda value: result.values.append("second:" + value))
        return result


class _CorpusExternalReader(ContentTypeReaderOfT[_CorpusShared]):
    def Read(self, input, existingInstance):
        result = _CorpusShared(); result.values.append(input.ReadExternalReference()); return result


def observe(operation: str, args: list[object]) -> object:
    if operation == "Touch.GestureValues":
        sample = GestureSample()
        return [[int(value) for value in GestureType], int(GestureType.Tap | GestureType.PinchComplete),
                int(sample.GestureType), sample.Timestamp.total_seconds(),
                list(sample.Position), list(sample.Position2), list(sample.Delta), list(sample.Delta2)]
    if operation == "Touch.LocationValue":
        value = TouchLocation(7, TouchLocationState.Moved, Vector2(8, 9),
                              TouchLocationState.Pressed, Vector2(2.5, -3))
        other = TouchLocation(7, TouchLocationState.Released, Vector2(8, 9),
                              TouchLocationState.Moved, Vector2(2.5, -3))
        found, previous = value.TryGetPreviousLocation()
        missing, sentinel = TouchLocation(
            4, TouchLocationState.Pressed, Vector2.One).TryGetPreviousLocation()
        return [value.Equals(other), value == other, value.GetHashCode(), value.ToString(),
                found, previous.Id, int(previous.State), list(previous.Position),
                missing, sentinel.Id, int(sentinel.State), list(sentinel.Position)]
    if operation == "Touch.CollectionValue":
        first = TouchLocation(1, TouchLocationState.Pressed, Vector2(1, 2))
        second = TouchLocation(2, TouchLocationState.Moved, Vector2(3, 4))
        default, values = TouchCollection(), TouchCollection([first, second])
        destination = [TouchLocation(), TouchLocation(), TouchLocation()]
        values.CopyTo(destination, 1)
        readonly = []
        for action in (lambda: values.Add(first), lambda: values.Clear(),
                       lambda: values.Insert(0, first), lambda: values.RemoveAt(0),
                       lambda: values.Remove(first)):
            try: action()
            except TypeError: readonly.append(True)
            else: readonly.append(False)
        found, located = values.FindById(2)
        return [default.Count, default.IsConnected, values.Count, values.IsConnected,
                values.IsReadOnly, values.IndexOf(second), values.Contains(first),
                found, located.Id, [item.Id for item in destination], readonly]
    if operation == "Touch.EnumeratorValue":
        values = TouchCollection([
            TouchLocation(1, TouchLocationState.Pressed, Vector2(1, 2)),
            TouchLocation(2, TouchLocationState.Moved, Vector2(3, 4)),
        ])
        enumerator = values.GetEnumerator()
        before = False
        try: _ = enumerator.Current
        except IndexError: before = True
        first = enumerator.MoveNext(); first_id = enumerator.Current.Id
        second = enumerator.MoveNext(); second_id = enumerator.Current.Id
        ended = enumerator.MoveNext(); after = False
        try: _ = enumerator.Current
        except IndexError: after = True
        enumerator.Dispose()
        return [before, first, first_id, second, second_id, ended, after,
                [item.Id for item in values]]
    if operation == "Packed.Format":
        packed_type, ordinary_args, boundary_args, clamp_args, identity = _PACKED_CORPUS[args[0]]
        ordinary = packed_type(*ordinary_args)
        boundary = packed_type(*boundary_args)
        clamped = packed_type(*clamp_args)
        round_trip = packed_type(); round_trip.PackFromVector4(ordinary.ToVector4())
        assigned = packed_type(); assigned.PackedValue = identity
        result = [packed_type().PackedValue, ordinary.PackedValue, boundary.PackedValue,
                  clamped.PackedValue, round_trip.PackedValue,
                  assigned.PackedValue, assigned.Equals(assigned.__copy__())]
        if packed_type is HalfSingle:
            exponent31 = HalfSingle(); exponent31.PackedValue = 0x7C00
            result.extend([HalfSingle(2.0 ** -24).PackedValue,
                           HalfSingle(math.inf).PackedValue,
                           HalfSingle(math.nan).PackedValue,
                           hex32(exponent31.ToSingle())])
        return result
    if operation == "Curve.Defaults":
        value=Curve();return [int(value.PreLoop),int(value.PostLoop),value.IsConstant,hex32(value.Evaluate(5))]
    if operation == "Curve.KeyOrdering":
        value=Curve();a=CurveKey(1,10);b=CurveKey(1,20)
        value.Keys.Add(CurveKey(2,30));value.Keys.Add(a);value.Keys.Add(CurveKey(0,0));value.Keys.Add(b)
        return [[key.Position for key in value.Keys],[key.Value for key in value.Keys],value.Keys[1] is a,value.Keys[2] is b]
    if operation == "Curve.Clone":
        value=Curve();value.Keys.Add(CurveKey(0,1));clone=value.Clone();clone.Keys[0].Value=42
        return [clone is not value,clone.Keys is not value.Keys,clone.Keys[0] is value.Keys[0],value.Keys[0].Value]
    if operation == "Curve.Evaluate":
        ordinary=Curve();ordinary.Keys.Add(CurveKey(0,0));ordinary.Keys.Add(CurveKey(1,10))
        asymmetric=Curve();asymmetric.Keys.Add(CurveKey(0,0,99,4));asymmetric.Keys.Add(CurveKey(2,10,-2,77))
        return [hex32(ordinary.Evaluate(.25)),hex32(asymmetric.Evaluate(1))]
    if operation == "Curve.Step":
        value=Curve();value.Keys.Add(CurveKey(0,2,0,0,CurveContinuity.Step));value.Keys.Add(CurveKey(1,9))
        return [hex32(value.Evaluate(.999)),hex32(value.Evaluate(1))]
    if operation == "Curve.Tangents":
        value=Curve();[value.Keys.Add(CurveKey(*item)) for item in ((0,0),(1,10),(3,30))]
        value.ComputeTangents(CurveTangent.Smooth)
        return [hex32(value.Keys[0].TangentIn),hex32(value.Keys[1].TangentIn),hex32(value.Keys[1].TangentOut),hex32(value.Keys[2].TangentOut)]
    if operation == "Curve.Loops":
        results=[]
        for mode in CurveLoopType:
            value=Curve();value.Keys.Add(CurveKey(5,0));value.Keys.Add(CurveKey(7,10))
            value.Keys[0].TangentIn=2;value.Keys[1].TangentOut=3;value.PreLoop=mode;value.PostLoop=mode
            results.extend((hex32(value.Evaluate(4)),hex32(value.Evaluate(8))))
        return results
    if operation == "Curve.NegativeCycles":
        results=[]
        for mode in (CurveLoopType.Cycle,CurveLoopType.CycleOffset,CurveLoopType.Oscillate):
            value=Curve();value.Keys.Add(CurveKey(5,0));value.Keys.Add(CurveKey(7,10));value.PreLoop=mode
            results.append(hex32(value.Evaluate(3)))
        return results
    if operation == "Curve.Duplicates":
        value=Curve();value.Keys.Add(CurveKey(1,10));value.Keys.Add(CurveKey(1,20));value.PreLoop=CurveLoopType.Cycle;value.PostLoop=CurveLoopType.Oscillate
        return [hex32(value.Evaluate(0)),hex32(value.Evaluate(1)),hex32(value.Evaluate(2))]
    if operation == "Curve.KeyNaN":
        a=CurveKey(math.nan,1);b=CurveKey(math.nan,1);return [a.CompareTo(b),a.Equals(b)]
    if operation == "Design.Base":
        value=MathTypeConverter();return [value.CanConvertFrom(str),value.CanConvertFrom(int),value.CanConvertTo(str),value.CanConvertTo(tuple),value.GetCreateInstanceSupported(),value.GetPropertiesSupported()]
    if operation == "Design.Properties":
        name=args[0];converter=_DESIGN_CONVERTERS[name]()
        if name=="MathTypeConverter":return [list(converter.propertyDescriptions),list(converter.GetProperties(object()))]
        value=_DESIGN_VALUES[name];properties=converter.GetProperties(value)
        return [list(properties),[kind.__name__ for kind in converter.propertyDescriptions.values()]]
    if operation == "Design.Support":
        return [[name,converter().CanConvertFrom(str),converter().CanConvertTo(str),converter().CanConvertTo(tuple)] for name,converter in _DESIGN_CONVERTERS.items()]
    if operation == "Design.Culture":
        vector=Vector3(1.25,-2.5,3.75);special=Vector4(math.nan,math.inf,-math.inf,-0.0)
        return [Vector3Converter().ConvertTo(None,vector,str),Vector3Converter().ConvertTo('de-DE',vector,str),Vector4Converter().ConvertTo(None,special,str),Vector4Converter().ConvertTo('de-DE',special,str),Vector2Converter().ConvertTo(None,Vector2(1e-30,3.40282347e38),str)]
    if operation == "Design.Parse":
        point=PointConverter().ConvertFrom(None,'2147483647, -2147483648');vector=Vector3Converter().ConvertFrom(None,'-0, 1e-30, 3.40282347E+38');german=Vector3Converter().ConvertFrom('de-DE','1,5; -2,25; 3,75');color=ColorConverter().ConvertFrom(None,'0,255,10,40')
        return [point.X,point.Y,*hex_values(vector),*hex_values(german),*color]
    if operation == "Design.Create":
        value=Vector3Converter().CreateInstance({'X':1.0,'Y':2.0,'Z':3.0,'Extra':4.0});matrix=MatrixConverter().CreateInstance({name:float(index) for index,name in enumerate(Matrix._names,1)})
        return [*value,matrix.M11,matrix.M24,matrix.M41,matrix.M44]
    if operation == "Design.Descriptors":
        result=[]
        for name,value in _DESIGN_VALUES.items():
            constructor,arguments=_DESIGN_CONVERTERS[name]().ConvertTo(None,value,tuple)
            result.append([constructor.__name__,len(arguments),constructor(*arguments)==value])
        return result
    if operation == "Design.Fallback":
        rectangle=Rectangle(1,2,3,4);matrix=Matrix.Identity
        return [RectangleConverter().ConvertTo('de-DE',rectangle,str),MatrixConverter().ConvertTo('de-DE',matrix,str)]
    if operation == "Design.Invalid":
        failures=[]
        for action in (lambda:Vector3Converter().ConvertFrom(None,'1,2'),lambda:Vector3Converter().ConvertFrom('de-DE','1.5;2.5;3.5'),lambda:ColorConverter().ConvertFrom(None,'256,0,0,0'),lambda:Vector3Converter().CreateInstance({'X':1.0,'Y':2.0})):
            try:action()
            except (TypeError,ValueError):failures.append(True)
            else:failures.append(False)
        return failures
    if operation == "Audio.EnumValues":
        return [[int(value) for value in enum] for enum in (
            AudioChannels, AudioStopOptions, SoundState, MicrophoneState)]
    if operation == "Audio.ListenerEmitterDefaults":
        listener=AudioListener();emitter=AudioEmitter()
        return [*listener.Position,*listener.Velocity,*listener.Forward,*listener.Up,
                emitter.DopplerScale]
    if operation == "Audio.VectorCopyBoundaries":
        listener=AudioListener();source=Vector3(1,2,3);listener.Position=source;source.X=9
        result=listener.Position;result.Y=8
        return [listener.Position==Vector3(1,2,3),result is not listener.Position]
    if operation == "Audio.EmitterDopplerNaN":
        value=AudioEmitter();value.DopplerScale=math.nan
        try:value.DopplerScale=-1.0
        except ValueError:negative=True
        else:negative=False
        return [math.isnan(value.DopplerScale),negative]
    if operation == "Audio.SampleDuration":
        return [int(SoundEffect.GetSampleDuration(size,rate,AudioChannels(channels)).total_seconds()*1_000_000)
                for size,rate,channels in args]
    if operation == "Audio.SampleSize":
        return [SoundEffect.GetSampleSizeInBytes(
            __import__("datetime").timedelta(microseconds=microseconds),rate,AudioChannels(channels))
            for microseconds,rate,channels in args]
    if operation == "Audio.RendererDefault":
        value=RendererDetail();copy=value.__copy__()
        return [value.FriendlyName,value.RendererId,value.GetHashCode(),value==copy,value.ToString()]
    if operation == "Audio.CategoryDefault":
        value=AudioCategory();return [value.ToString(),value==AudioCategory(),value.GetHashCode()]
    if operation == "Content.SerializerDefaults":
        value=ContentSerializerAttribute()
        return [value.ElementName,value.FlattenContent,value.Optional,value.AllowNull,value.SharedResource,value.CollectionItemName,value.HasCollectionItemName]
    if operation == "Content.SerializerClone":
        value=ContentSerializerAttribute();value.ElementName="Original";value.CollectionItemName="Entry";clone=value.Clone();clone.ElementName="Clone";clone.CollectionItemName="Child"
        return [value.ElementName,clone.ElementName,value.CollectionItemName,clone.CollectionItemName,value is not clone]
    if operation == "Content.RootDirectory":
        service=object();value=ContentManager(service,"First");before=[value.RootDirectory,value.ServiceProvider is service];value.RootDirectory="Nested/Second";before.append(value.RootDirectory);value.Dispose();before.append(value.RootDirectory);return before
    if operation == "Content.ReaderPrimitives":
        data=(b"\x01\xfe"+struct.pack("<bhiIqQfd",-2,-1234,-123456,4000000000,-1234567890123,1234567890123456789,1.25,-2.5)+"Ž".encode("utf-8")+binary_string("xnb"))
        reader=ContentReader._create(ContentManager(object()),data,"primitive",None)
        return [reader.ReadBoolean(),reader.ReadByte(),reader.ReadSByte(),reader.ReadInt16(),reader.ReadInt32(),reader.ReadUInt32(),reader.ReadInt64(),reader.ReadUInt64(),reader.ReadSingle(),reader.ReadDouble(),reader.ReadChar(),reader.ReadString()]
    if operation == "Content.ReaderValues":
        reader=ContentReader._create(ContentManager(object()),struct.pack("<9f4B",1,2,3,4,5,6,7,8,9,10,20,30,40),"values",None)
        return [*reader.ReadVector2(),*reader.ReadVector3(),*reader.ReadQuaternion(),*reader.ReadColor()]
    if operation == "Content.CacheIdentity":
        asset=content_xnb([(_STRING_READER,0)],seven(1)+binary_string("asset"));manager=ResourceContentManager(object(),{"name":asset});first=manager.Load("name");second=manager.Load("NAME");manager.Unload();third=manager.Load("name");manager.Dispose();return [first,first is second,third]
    if operation == "Content.ReaderVersionFailure":
        asset=content_xnb([(_STRING_READER,1)],seven(1)+binary_string("bad"));manager=ResourceContentManager(object(),{"bad":asset})
        try: manager.Load("bad")
        except ContentLoadException as error: return ["version mismatch" in str(error),manager._loaded_assets=={}]
        return [False,False]
    if operation == "Content.SharedFixupOrder":
        identity="CnaPython.Corpus.SharedReader";unregister=_register_content_type_reader(identity,_CorpusSharedReader)
        try:
            body=seven(1)+seven(1)+seven(1)+seven(2)+binary_string("resource");asset=content_xnb([(identity,0),(_STRING_READER,0)],body,1);manager=ResourceContentManager(object(),{"shared":asset});return manager.Load("shared").values
        finally: unregister()
    if operation == "Content.ExternalNormalization":
        identity="CnaPython.Corpus.ExternalReader";unregister=_register_content_type_reader(identity,_CorpusExternalReader)
        try:
            parent=content_xnb([(identity,0)],seven(1)+binary_string("../target"));target=content_xnb([(_STRING_READER,0)],seven(1)+binary_string("external"));manager=ResourceContentManager(object(),{"folder/nested/root":parent,"folder/target":target});value=manager.Load("folder/nested/root");return [value.values[0],value.values[0] is manager.Load("folder/target")]
        finally: unregister()
    if operation == "Content.DisposedBehavior":
        value=ContentManager(object(),"Content");value.Dispose()
        try: value.Load("asset")
        except RuntimeError as error: return [value.RootDirectory,"disposed" in str(error)]
        return [value.RootDirectory,False]
    if operation == "Graphics.SurfaceFormatValues":
        return [int(value) for value in SurfaceFormat]
    if operation == "Graphics.ViewportProject":
        viewport=Viewport(10,20,640,480);viewport.MinDepth=0.2;viewport.MaxDepth=0.8
        return hex_values(viewport.Project(Vector3(0.25,-0.5,0.4),Matrix.Identity,Matrix.Identity,Matrix.Identity))
    if operation == "Graphics.ViewportRoundTrip":
        viewport=Viewport(10,20,640,480);viewport.MinDepth=0.2;viewport.MaxDepth=0.8
        source=Vector3(0.25,-0.5,0.4);projected=viewport.Project(source,Matrix.Identity,Matrix.Identity,Matrix.Identity)
        return hex_values(viewport.Unproject(projected,Matrix.Identity,Matrix.Identity,Matrix.Identity))
    if operation == "Graphics.PresentationDefaults":
        value=PresentationParameters();clone=value.Clone()
        return [value.BackBufferWidth,value.BackBufferHeight,int(value.BackBufferFormat),int(value.DepthStencilFormat),value.MultiSampleCount,int(value.DisplayOrientation),int(value.PresentationInterval),int(value.RenderTargetUsage),value.DeviceWindowHandle,value.IsFullScreen,clone is not value]
    if operation == "Graphics.StateDefaults":
        blend=BlendState();depth=DepthStencilState();raster=RasterizerState();sampler=SamplerState()
        return [int(blend.ColorSourceBlend),int(blend.ColorDestinationBlend),int(blend.ColorBlendFunction),depth.DepthBufferEnable,depth.DepthBufferWriteEnable,int(depth.DepthBufferFunction),int(raster.CullMode),int(raster.FillMode),raster.MultiSampleAntiAlias,int(sampler.Filter),sampler.MaxAnisotropy,sampler.MaxMipLevel]
    if operation == "Graphics.VertexStrides":
        return [VertexPositionColor.VertexDeclaration.VertexStride,VertexPositionColorTexture.VertexDeclaration.VertexStride,VertexPositionNormalTexture.VertexDeclaration.VertexStride,VertexPositionTexture.VertexDeclaration.VertexStride]
    if operation == "Graphics.EffectEnumValues":
        return [[int(value) for value in EffectParameterClass],[int(value) for value in EffectParameterType]]
    if operation == "Model.CollectionIdentity":
        root=ModelBone("Root",0);child=ModelBone("Child",1);root._add_child(child)
        parts=[ModelMeshPart(),ModelMeshPart()];mesh=ModelMesh("Mesh",child,parts);model=Model([root,child],[mesh])
        found,bone=model.Bones.TryGetValue("Child");missing,missing_bone=model.Bones.TryGetValue("Missing")
        return [model.Bones.Count,model.Meshes.Count,model.Root.Name,child.Parent is root,
                root.Children[0] is child,model.Meshes["Mesh"] is mesh,mesh.MeshParts.Count,
                mesh.MeshParts[0] is parts[0],found,bone.Name,missing,missing_bone is None]
    if operation == "Model.BoneTransformCopies":
        root=ModelBone("Root",0,Matrix.CreateTranslation(1,0,0));child=ModelBone("Child",1,Matrix.CreateTranslation(2,0,0));root._add_child(child);model=Model([root,child],[])
        absolute=[Matrix.Identity,Matrix.Identity];local=[Matrix.Identity,Matrix.Identity]
        model.CopyAbsoluteBoneTransformsTo(absolute);model.CopyBoneTransformsTo(local);local[1].M41=99
        return [absolute[0].M41,absolute[1].M41,child.Transform.M41,local[1].M41]
    if operation == "Golden.Vector2NormalizeZero": return hex_values(Vector2.Normalize(Vector2.Zero))
    if operation == "Golden.Vector3NormalizeZero": return hex_values(Vector3.Normalize(Vector3.Zero))
    if operation == "Golden.Vector4NormalizeZero": return hex_values(Vector4.Normalize(Vector4.Zero))
    if operation == "Golden.VectorDivide": return hex_values(((Vector2(3)/7).X,(Vector3(7)/3).X,(Vector4(12345.67)/3).X,(Matrix.Identity/3).M11))
    if operation == "Golden.QuaternionZero": return hex_values([*Quaternion.Normalize(Quaternion()),*Quaternion.Inverse(Quaternion())])
    if operation == "Golden.QuaternionProducts":
        yaw=Quaternion.CreateFromAxisAngle(Vector3.Up,0.7);pitch=Quaternion.CreateFromAxisAngle(Vector3.Right,-0.4)
        grouped=Quaternion(45889.05859375,-42412.4453125,96034.96875,-76386.84375)*Quaternion(-16375.435546875,51428.1875,-69603.09375,-2207.3798828125)
        return hex_values([*(yaw*pitch),*grouped,*Quaternion.Concatenate(yaw,pitch),*Vector3.Transform(Vector3(1.25,-2.5,3.75),yaw*pitch)])
    if operation == "Golden.MatrixTransforms":
        matrix=Matrix.CreateScale(2,3,4)*Matrix.CreateRotationY(0.25)*Matrix.CreateTranslation(5,6,7)
        return hex_values([*Vector2.Transform(Vector2(1.5,-2),matrix),*Vector3.Transform(Vector3(1.5,-2,0.25),matrix),*Vector4.Transform(Vector4(1.5,-2,0.25,1),matrix)])
    if operation == "Golden.ColorNonfinite": return [f"{Color(0.5,math.nan,math.inf,-math.inf).PackedValue:08X}",f"{Color.FromNonPremultiplied(2147483647,2147483647,2147483647,2147483647).PackedValue:08X}"]
    if operation == "Golden.PlaneTransform":
        value=Plane.Transform(Plane(Vector3.Up,-2),Matrix.CreateTranslation(0,5,0));return hex_values([*value.Normal,value.D])
    if operation == "Golden.NaNEquality":
        vector=Vector2(math.nan,0);matrix=Matrix.Identity;matrix.M11=math.nan
        return [vector.Equals(vector),vector==vector,matrix.Equals(matrix),matrix==matrix]
    if operation == "Golden.HashCodes": return [Vector3(1,2,3).GetHashCode(),Matrix.Identity.GetHashCode(),Point(1,2).GetHashCode(),Rectangle(1,2,3,4).GetHashCode()]
    if operation == "Golden.MathEdges": return [hex32(MathHelper.Clamp(0,2,1)),hex32(MathHelper.WrapAngle(123456.789)),hex32(MathHelper.CatmullRom(-10,-10,-10,-7,0.3)),hex32(MathHelper.Hermite(-10,-10,-10,-10,1.1)),math.isnan(MathHelper.Hermite(1,math.inf,2,0,0))]
    if operation == "Golden.VectorEdges":
        nan=float_from_bits(0xFFC00000);minimum=Vector3.Min(Vector3(nan,1,nan),Vector3(7,nan,nan));clamped=Vector3.Clamp(Vector3.Zero,Vector3(2),Vector3(1))
        return hex_values([*minimum,*clamped])
    if operation == "Golden.QuaternionEdges":
        yaw=Quaternion.CreateFromAxisAngle(Vector3.Up,0.7);pitch=Quaternion.CreateFromAxisAngle(Vector3.Right,-0.4)
        return hex_values([*Quaternion.Slerp(yaw,pitch,0.37),*Quaternion.CreateFromAxisAngle(Vector3.Up,123456.789),*Quaternion.CreateFromRotationMatrix(Matrix.CreateRotationY(0.7))])
    if operation == "Golden.MatrixEdges":
        large=Matrix.CreateRotationY(123456.789);perspective=Matrix.CreatePerspective(4,3,0.1,math.inf)
        mirrored=Matrix.CreateScale(-2,3,4)*Matrix.CreateRotationY(0.25)*Matrix.CreateTranslation(5,6,7);ok,scale,rotation,translation=mirrored.Decompose()
        return [hex32(large.M11),hex32(large.M31),hex32(perspective.M33),hex32(perspective.M43),ok,*hex_values([*scale,*rotation,*translation]),*hex_values([(-Vector4.Zero).X,(-Quaternion()).X,(-Matrix()).M11])]
    if operation == "Golden.MatrixDegenerate":
        billboard=Matrix.CreateConstrainedBillboard(Vector3(0,10,0),Vector3.Zero,Vector3(0,2,0),None,None)
        shadow=Matrix.CreateShadow(Vector3.Forward,Plane(Vector3.Zero,0));plane=Plane(Vector3(2,0,0),4);reflection=Matrix.CreateReflection(plane)
        look=Matrix.CreateLookAt(Vector3.Zero,Vector3.Zero,Vector3.Up)
        return [*hex_values([billboard.M11,billboard.M22,billboard.M33]),math.isnan(shadow.M11),math.isnan(shadow.M44),*hex_values([plane.Normal.X,plane.D,reflection.M11,reflection.M41]),*hex_values(look)]
    if operation == "Golden.PlaneEdges":
        degenerate=Plane(Vector3.Zero,Vector3.Zero,Vector3.Zero);near=Plane.Normalize(Plane(Vector3(0.6,0.79999995,0),2));coplanar=Plane(Vector3.Zero,0).Intersects(BoundingBox(Vector3(-1),Vector3(1)))
        return [*hex_values([*degenerate.Normal,degenerate.D,*near.Normal,near.D]),int(coplanar)]
    if operation == "Golden.GeometryEdges":
        volume=BoundingBox(Vector3(-1),Vector3(1));nan_box=BoundingBox(Vector3(math.nan,-1,-1),Vector3(math.nan,1,1));unit=BoundingSphere(Vector3.Zero,1)
        return [int(volume.Contains(Vector3(math.nan,0,0))),volume.Intersects(nan_box),int(unit.Contains(Vector3.UnitX)),unit.Intersects(BoundingSphere(Vector3(2,0,0),1)),Ray(Vector3(2,0,0),Vector3(-5e-7,0,0)).Intersects(volume),Ray(Vector3.Zero,Vector3(5e-6,1,0)).Intersects(Plane(Vector3.UnitX,-1))]
    if operation == "Golden.FrustumPlanesCorners":
        projection=Matrix.CreatePerspectiveFieldOfView(MathHelper.PiOver4,4/3,1,10);frustum=BoundingFrustum(Matrix.CreateLookAt(Vector3(0,0,5),Vector3.Zero,Vector3.Up)*projection);corners=frustum.GetCorners()
        return hex_values([*frustum.Near.Normal,frustum.Near.D,*frustum.Top.Normal,frustum.Top.D,*corners[0],*corners[6]])
    if operation == "Golden.FrustumRelations":
        projection=Matrix.CreatePerspectiveFieldOfView(MathHelper.PiOver4,4/3,1,10);frustum=BoundingFrustum(Matrix.CreateLookAt(Vector3(0,0,5),Vector3.Zero,Vector3.Up)*projection);distant=BoundingFrustum(Matrix.CreateLookAt(Vector3(100,0,5),Vector3(100,0,0),Vector3.Up)*projection)
        return [int(frustum.Contains(Vector3.Zero)),int(frustum.Contains(Vector3(0,0,6))),int(frustum.Contains(BoundingBox(Vector3(-0.5),Vector3(0.5)))),int(frustum.Contains(BoundingSphere(Vector3.Zero,0.5))),frustum.Intersects(BoundingBox(Vector3(-0.5),Vector3(0.5))),frustum.Intersects(BoundingBox(Vector3(100),Vector3(101))),frustum.Intersects(BoundingSphere(Vector3.Zero,0.5)),frustum.Intersects(BoundingSphere(Vector3(100),0.5)),frustum.Intersects(distant),hex32(frustum.Intersects(Ray(Vector3(0,0,20),Vector3.Forward)))]
    if operation == "MathHelper.Clamp": return MathHelper.Clamp(*args)
    if operation == "MathHelper.Lerp": return MathHelper.Lerp(*args)
    if operation == "MathHelper.Barycentric": return MathHelper.Barycentric(*args)
    if operation == "MathHelper.CatmullRom": return MathHelper.CatmullRom(*args)
    if operation == "MathHelper.Hermite": return MathHelper.Hermite(*args)
    if operation == "MathHelper.SmoothStep": return MathHelper.SmoothStep(*args)
    if operation == "MathHelper.WrapAngle": return MathHelper.WrapAngle(*args)
    if operation == "MathHelper.ToDegrees": return MathHelper.ToDegrees(*args)
    if operation == "Vector2.Add": return list(Vector2.Add(vector2(args[0]), vector2(args[1])))
    if operation == "Vector2.Dot": return Vector2.Dot(vector2(args[0]), vector2(args[1]))
    if operation == "Vector2.Normalize": return list(Vector2.Normalize(vector2(args[0])))
    if operation == "Vector2.Reflect": return list(Vector2.Reflect(vector2(args[0]), vector2(args[1])))
    if operation == "Vector2.Barycentric": return list(Vector2.Barycentric(vector2(args[0]), vector2(args[1]), vector2(args[2]), args[3], args[4]))
    if operation == "Vector2.Transform": return list(Vector2.Transform(vector2(args[0]), Matrix.CreateTranslation(*args[1])))
    if operation == "Vector2.ZeroFresh": return Vector2.Zero is not Vector2.Zero
    if operation == "Vector3.Cross": return list(Vector3.Cross(vector3(args[0]), vector3(args[1])))
    if operation == "Vector3.Distance": return Vector3.Distance(vector3(args[0]), vector3(args[1]))
    if operation == "Vector3.Reflect": return list(Vector3.Reflect(vector3(args[0]), vector3(args[1])))
    if operation == "Vector3.TransformNormal": return list(Vector3.TransformNormal(vector3(args[0]), Matrix.CreateScale(*args[1])))
    if operation == "Vector3.SmoothStep": return list(Vector3.SmoothStep(vector3(args[0]), vector3(args[1]), args[2]))
    if operation == "Vector4.Dot": return Vector4.Dot(vector4(args[0]), vector4(args[1]))
    if operation == "Vector4.Hermite": return list(Vector4.Hermite(vector4(args[0]), vector4(args[1]), vector4(args[2]), vector4(args[3]), args[4]))
    if operation == "Vector4.Transform": return list(Vector4.Transform(vector4(args[0]), Matrix.CreateTranslation(*args[1])))
    if operation == "Quaternion.AxisAngleZero": return list(Quaternion.CreateFromAxisAngle(Vector3.UnitY, 0.0))
    if operation == "Quaternion.YawPitchRoll": return list(Quaternion.CreateFromYawPitchRoll(*args))
    if operation == "Quaternion.Concatenate": return list(Quaternion.Concatenate(Quaternion.CreateFromAxisAngle(Vector3.UnitX,args[0]),Quaternion.CreateFromAxisAngle(Vector3.UnitY,args[1])))
    if operation == "Quaternion.SlerpIdentity": return list(Quaternion.Slerp(Quaternion.Identity,Quaternion.CreateFromAxisAngle(Vector3.UnitY,args[0]),args[1]))
    if operation == "Quaternion.FromMatrix": return list(Quaternion.CreateFromRotationMatrix(Matrix.CreateRotationY(args[0])))
    if operation == "Matrix.Translation":
        value = Matrix.CreateTranslation(*args)
        return [value.M41, value.M42, value.M43, value.M44]
    if operation == "Matrix.MultiplyTranslations":
        value = Matrix.CreateTranslation(1, 2, 3) * Matrix.CreateTranslation(4, 5, 6)
        return [value.M41, value.M42, value.M43, value.M44]
    if operation == "Matrix.InverseProduct":
        value=Matrix.CreateScale(*args[0])*Matrix.CreateTranslation(*args[1]);return list(value*Matrix.Invert(value))
    if operation == "Matrix.SingularInverseNaN": return all(math.isnan(value) for value in Matrix.Invert(Matrix()))
    if operation == "Matrix.RotationY":
        value=Matrix.CreateRotationY(args[0]);return [value.M11,value.M13,value.M31,value.M33]
    if operation == "Matrix.PerspectiveInfinity":
        value=Matrix.CreatePerspective(args[0],args[1],args[2],math.inf);return [math.isnan(value.M33),math.isnan(value.M43)]
    if operation == "Matrix.Decompose":
        value=Matrix.CreateScale(*args[0])*Matrix.CreateTranslation(*args[1]);success,scale,rotation,translation=value.Decompose();return [success,*scale,*rotation,*translation]
    if operation == "Matrix.Billboard":
        value=Matrix.CreateBillboard(vector3(args[0]),vector3(args[1]),vector3(args[2]),None);return [value.M11,value.M22,value.M33,*value.Translation]
    if operation == "Matrix.Orthographic":
        value=Matrix.CreateOrthographic(*args);return [value.M11,value.M22,value.M33,value.M43,value.M44]
    if operation == "Color.Bytes": return list(Color(*args))
    if operation == "Color.Normalized": return list(Color(*args))
    if operation == "Color.Packed": return Color(*args).PackedValue
    if operation == "Color.Lerp": return list(Color.Lerp(Color(*args[0]),Color(*args[1]),args[2]))
    if operation == "Color.Multiply": return list(Color.Multiply(Color(*args[0]),args[1]))
    if operation == "Color.NonPremultiplied": return list(Color.FromNonPremultiplied(*args))
    if operation == "Color.ToVector4": return list(Color(*args).ToVector4())
    if operation == "Rectangle.Contains": return Rectangle(*args[:4]).Contains(Point(*args[4:]))
    if operation == "Rectangle.Intersect": return list(Rectangle.Intersect(Rectangle(*args[0]),Rectangle(*args[1])))
    if operation == "Rectangle.Union": return list(Rectangle.Union(Rectangle(*args[0]),Rectangle(*args[1])))
    if operation == "Rectangle.Inflate":
        value=Rectangle(*args[0]);value.Inflate(*args[1]);return list(value)
    if operation == "Rectangle.Offset":
        value=Rectangle(*args[0]);value.Offset(*args[1]);return list(value)
    if operation == "Point.Equal": return Point(*args[:2]) == Point(*args[2:])
    if operation == "Point.ZeroFresh": return Point.Zero is not Point.Zero
    if operation == "Plane.Normalize":
        value=Plane(vector3(args[0]),args[1]);return [*Plane.Normalize(value).Normal,Plane.Normalize(value).D]
    if operation == "Plane.DotCoordinate": return Plane(vector3(args[0]),args[1]).DotCoordinate(vector3(args[2]))
    if operation == "Plane.Box": return int(Plane(vector3(args[0]),args[1]).Intersects(box(args[2])))
    if operation == "Plane.Sphere": return int(Plane(vector3(args[0]),args[1]).Intersects(sphere(args[2])))
    if operation == "Ray.Box": return Ray(vector3(args[0]),vector3(args[1])).Intersects(box(args[2]))
    if operation == "Ray.Sphere": return Ray(vector3(args[0]),vector3(args[1])).Intersects(sphere(args[2]))
    if operation == "Ray.Plane": return Ray(vector3(args[0]),vector3(args[1])).Intersects(Plane(vector3(args[2]),args[3]))
    if operation == "BoundingBox.ContainsPoint": return int(box(args[0]).Contains(vector3(args[1])))
    if operation == "BoundingBox.ContainsSphere": return int(box(args[0]).Contains(sphere(args[1])))
    if operation == "BoundingBox.Merge":
        value=BoundingBox.CreateMerged(box(args[0]),box(args[1]));return [*value.Min,*value.Max]
    if operation == "BoundingSphere.ContainsPoint": return int(sphere(args[0]).Contains(vector3(args[1])))
    if operation == "BoundingSphere.Merge":
        value=BoundingSphere.CreateMerged(sphere(args[0]),sphere(args[1]));return [*value.Center,value.Radius]
    if operation == "BoundingSphere.Transform":
        value=sphere(args[0]).Transform(Matrix.CreateScale(*args[1])*Matrix.CreateTranslation(*args[2]));return [*value.Center,value.Radius]
    if operation.startswith("Frustum."):
        frustum=BoundingFrustum(Matrix.CreatePerspectiveFieldOfView(MathHelper.PiOver2,1,1,10))
        if operation == "Frustum.ContainsPoint": return int(frustum.Contains(vector3(args[0])))
        if operation == "Frustum.ContainsBox": return int(frustum.Contains(box(args[0])))
        if operation == "Frustum.IntersectsSphere": return frustum.Intersects(sphere(args[0]))
        if operation == "Frustum.Ray": return frustum.Intersects(Ray(vector3(args[0]),vector3(args[1])))
        if operation == "Frustum.Corners": return [len(frustum.GetCorners()),frustum.GetCorners()[0].Z,frustum.GetCorners()[4].Z]
    if operation == "Float32.NegativeZero": return math.copysign(1.0, f32(-0.0)) < 0.0
    raise ValueError(f"unknown corpus operation {operation}")


def scalar_assertions(value: object) -> int:
    if isinstance(value, list):
        return sum(scalar_assertions(item) for item in value)
    return 1


def equal(actual: object, expected: object) -> bool:
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            equal(left, right) for left, right in zip(actual, expected)
        )
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-7)
    return actual == expected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default=str(ROOT / "behavior/xna40-pure-values.json"))
    parser.add_argument("--output")
    args = parser.parse_args()
    corpus = json.loads(Path(args.corpus).read_text())
    results, failures, assertions = [], 0, 0
    for item in corpus["observations"]:
        actual = observe(item["operation"], item["args"])
        passed = equal(actual, item["expected"])
        assertions += scalar_assertions(item["expected"])
        failures += not passed
        results.append({"id": item["id"], "passed": passed,
                        "expected": item["expected"], "actual": actual})
    report = {
        "schemaVersion": 1,
        "profile": corpus["profile"],
        "provenance": corpus["provenance"],
        "category": corpus["category"],
        "summary": {"OBSERVATIONS": len(results), "ASSERTIONS": assertions, "FAILURES": failures},
        "results": results,
    }
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n")
    for name, value in report["summary"].items():
        print(f"{name}={value}")
    print(f"PROVENANCE={report['provenance']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
