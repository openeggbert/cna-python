"""Native-backed XNA Effect graph and stock effects.

Reflection children are deliberately parent-owned Python views.  The stock
constructors below create the real CNA Effect handle; no detached shader or
pass facade is used for execution.
"""
from __future__ import annotations
import ctypes as c
from enum import IntEnum
from typing import Iterable
from _cna_native import abi
from _cna_native.loader import get_library
from .._math import Matrix, Quaternion, Vector2, Vector3, Vector4
from .._numeric import f32, int32
from ._device import CompareFunction, GraphicsDevice
from ._resources import GraphicsResource, Texture, Texture2D, _release
from ._texture_volume import TextureCube
from . import _effect_codec as codec

class EffectParameterClass(IntEnum):
    Scalar=0; Vector=1; Matrix=2; Object=3; Struct=4
class EffectParameterType(IntEnum):
    Void=0; Bool=1; Int32=2; Single=3; String=4; Texture=5; Texture1D=6; Texture2D=7; Texture3D=8; TextureCube=9

class _ViewCollection:
    def __init__(self, owner, values=(), handle=0, destroy_operation=None, find_operation=None):
        self._owner=owner; self._effect=owner._effect if hasattr(owner,"_effect") else owner
        self._values=tuple(values); self._handle=int(handle); self._find_operation=find_operation
        if self._handle:
            self._effect._register_view(self,destroy_operation,1)
    def _check(self): self._owner._check()
    def _invalidate(self, operation):
        handle,self._handle=self._handle,0
        if handle and operation:
            get_library().check(getattr(get_library(),operation)(handle),operation)
    @property
    def Count(self): self._check(); return len(self._values)
    def __iter__(self): self._check(); return iter(self._values)
    def __getitem__(self, key):
        self._check()
        if isinstance(key,str):
            cached=next((value for value in self._values if getattr(value,"Name",None)==key),None)
            if self._handle and self._find_operation:
                encoded=key.encode("utf-8",errors="strict");found=c.c_uint8();view=c.c_uint64();lib=get_library()
                operation=self._find_operation
                lib.check(getattr(lib,operation)(self._handle,abi.CNA_StringView(encoded,len(encoded)),c.byref(found),c.byref(view)),operation)
                if view.value:
                    destroy="cna_effect_annotation_destroy" if "annotation" in operation else "cna_effect_parameter_destroy"
                    lib.check(getattr(lib,destroy)(view.value),destroy)
                if bool(found.value)!=(cached is not None): raise RuntimeError("native Effect collection identity disagrees with cached reflection")
            if cached is not None:return cached
            raise KeyError(key)
        return self._values[key]

class DirectionalLight:
    def __init__(self, parent=None, index=0):
        if parent is None:raise TypeError("DirectionalLight instances are supplied by a stock Effect")
        parent._check();self._parent=parent;self._effect=parent;self._index=index;output=c.c_uint64();lib=get_library()
        lib.check(lib.cna_effect_lights_get_directional_light(parent._require_handle(),index,c.byref(output)),"cna_effect_lights_get_directional_light")
        self._handle=int(output.value);parent._register_view(self,"cna_directional_light_destroy",0)
    def _check(self):
        self._parent._check()
        if not self._handle:raise RuntimeError("DirectionalLight is invalid because its parent Effect is disposed")
    def _invalidate(self,operation):
        handle,self._handle=self._handle,0
        if handle:get_library().check(getattr(get_library(),operation)(handle),operation)
    def _vector(name):
        def get(self):
            self._check();value=abi.CNA_Vector3();op=f"cna_directional_light_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._handle,c.byref(value)),op);return Vector3(value.x,value.y,value.z)
        def set(self,value):
            self._check()
            if not isinstance(value,Vector3):raise TypeError(f"{name} must be Vector3")
            op=f"cna_directional_light_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._handle,abi.CNA_Vector3(*tuple(value))),op)
        return property(get,set)
    Direction=_vector("direction");DiffuseColor=_vector("diffuse_color");SpecularColor=_vector("specular_color")
    @property
    def Enabled(self):
        self._check();value=c.c_uint8();lib=get_library();lib.check(lib.cna_directional_light_get_enabled(self._handle,c.byref(value)),"cna_directional_light_get_enabled");return bool(value.value)
    @Enabled.setter
    def Enabled(self,value):
        if type(value) is not bool:raise TypeError("Enabled must be bool")
        self._check();lib=get_library();lib.check(lib.cna_directional_light_set_enabled(self._handle,value),"cna_directional_light_set_enabled")

class _NativeView:
    _destroy_operation=""
    def _init_view(self,parent,handle):
        self._parent=parent;self._effect=parent._effect if hasattr(parent,"_effect") else parent
        self._handle=int(handle);self._effect._register_view(self,self._destroy_operation,0)
    def _check(self):
        self._effect._check()
        if not self._handle:raise RuntimeError(f"{type(self).__name__} is invalid because its parent Effect is disposed")
    def _invalidate(self,operation):
        handle,self._handle=self._handle,0
        if handle:get_library().check(getattr(get_library(),operation)(handle),operation)

class EffectAnnotation(_NativeView):
    _destroy_operation="cna_effect_annotation_destroy"
    def __init__(self,parent,handle):
        self._init_view(parent,handle);info=abi.CNA_EffectAnnotationInfo();info.struct_size,info.struct_version=c.sizeof(info),1
        lib=get_library();lib.check(lib.cna_effect_annotation_get_info(handle,c.byref(info)),"cna_effect_annotation_get_info")
        self._info=info
        self._name=codec.copy_utf8(handle,"cna_effect_annotation_get_name_byte_count","cna_effect_annotation_copy_name")
        self._semantic=codec.copy_utf8(handle,"cna_effect_annotation_get_semantic_byte_count","cna_effect_annotation_copy_semantic")
    def _check(self):
        _NativeView._check(self)
    Name=property(lambda s:(s._check(),s._name)[1]); Semantic=property(lambda s:(s._check(),s._semantic)[1])
    ParameterType=property(lambda s:(s._check(),EffectParameterType(s._info.parameter_type))[1]); ParameterClass=property(lambda s:(s._check(),EffectParameterClass(s._info.parameter_class))[1])
    ColumnCount=property(lambda s:(s._check(),int(s._info.column_count))[1]); RowCount=property(lambda s:(s._check(),int(s._info.row_count))[1])
    def _validate(self,parameter_type,parameter_class,dimension=None):
        self._check()
        if self.ParameterType!=parameter_type or self.ParameterClass!=parameter_class:raise TypeError(f"annotation {self._name!r} metadata ({self.ParameterClass.name}, {self.ParameterType.name}) does not support the requested typed value")
        if dimension is not None and max(self.RowCount,self.ColumnCount)!=dimension:raise TypeError(f"annotation {self._name!r} vector dimension does not match")
    def GetValueBoolean(self):self._validate(EffectParameterType.Bool,EffectParameterClass.Scalar);return codec.annotation_scalar(self._handle,"boolean",c.c_uint8,lambda v:bool(v.value))
    def GetValueInt32(self):self._validate(EffectParameterType.Int32,EffectParameterClass.Scalar);return codec.annotation_scalar(self._handle,"int32",c.c_int32,lambda v:int(v.value))
    def GetValueSingle(self):self._validate(EffectParameterType.Single,EffectParameterClass.Scalar);return codec.annotation_scalar(self._handle,"single",c.c_float,lambda v:float(v.value))
    def GetValueVector2(self):self._validate(EffectParameterType.Single,EffectParameterClass.Vector,2);return codec.annotation_vector(self._handle,"vector2",abi.CNA_Vector2,lambda v:Vector2(v.x,v.y))
    def GetValueVector3(self):self._validate(EffectParameterType.Single,EffectParameterClass.Vector,3);return codec.annotation_vector(self._handle,"vector3",abi.CNA_Vector3,lambda v:Vector3(v.x,v.y,v.z))
    def GetValueVector4(self):self._validate(EffectParameterType.Single,EffectParameterClass.Vector,4);return codec.annotation_vector(self._handle,"vector4",abi.CNA_Vector4,lambda v:Vector4(v.x,v.y,v.z,v.w))
    def GetValueMatrix(self):
        self._validate(EffectParameterType.Single,EffectParameterClass.Matrix)
        if self.RowCount!=4 or self.ColumnCount!=4:raise TypeError(f"annotation {self._name!r} is not a 4x4 Matrix")
        return codec.annotation_matrix(self._handle)
    def GetValueString(self):self._validate(EffectParameterType.String,EffectParameterClass.Object);return codec.annotation_string(self._handle)
class EffectAnnotationCollection(_ViewCollection):
    def GetEnumerator(self): return iter(self)

class EffectParameter(_NativeView):
    _destroy_operation="cna_effect_parameter_destroy"
    def __init__(self,parent,handle):
        self._init_view(parent,handle);info=abi.CNA_EffectParameterInfo();info.struct_size,info.struct_version=c.sizeof(info),1
        lib=get_library();lib.check(lib.cna_effect_parameter_get_info(handle,c.byref(info)),"cna_effect_parameter_get_info")
        self._info=info
        self._name=codec.copy_utf8(handle,"cna_effect_parameter_get_name_byte_count","cna_effect_parameter_copy_name")
        self._semantic=codec.copy_utf8(handle,"cna_effect_parameter_get_semantic_byte_count","cna_effect_parameter_copy_semantic")
        self._elements=self._structure_members=self._annotations=None;self._retained_texture=None
    Name=property(lambda s:(s._check(),s._name)[1]); Semantic=property(lambda s:(s._check(),s._semantic)[1])
    ParameterType=property(lambda s:(s._check(),EffectParameterType(s._info.parameter_type))[1]); ParameterClass=property(lambda s:(s._check(),EffectParameterClass(s._info.parameter_class))[1])
    ColumnCount=property(lambda s:(s._check(),int(s._info.column_count))[1]); RowCount=property(lambda s:(s._check(),int(s._info.row_count))[1])
    def _children(self,attribute,operation,annotation=False):
        self._check();cached=getattr(self,attribute)
        if cached is None:
            handle=c.c_uint64();lib=get_library();lib.check(getattr(lib,operation)(self._handle,c.byref(handle)),operation)
            cached=_load_annotation_collection(self,handle.value) if annotation else _load_parameter_collection(self,handle.value)
            setattr(self,attribute,cached)
        return cached
    Elements=property(lambda s:s._children("_elements","cna_effect_parameter_get_elements"))
    StructureMembers=property(lambda s:s._children("_structure_members","cna_effect_parameter_get_structure_members"))
    Annotations=property(lambda s:s._children("_annotations","cna_effect_parameter_get_annotations",True))
    def _validate_tag(self,tag):
        actual_type=EffectParameterType(self._info.parameter_type);actual_class=EffectParameterClass(self._info.parameter_class)
        expected={codec.BOOLEAN:(EffectParameterType.Bool,EffectParameterClass.Scalar,None),codec.INT32:(EffectParameterType.Int32,EffectParameterClass.Scalar,None),codec.SINGLE:(EffectParameterType.Single,EffectParameterClass.Scalar,None),codec.VECTOR2:(EffectParameterType.Single,EffectParameterClass.Vector,2),codec.VECTOR3:(EffectParameterType.Single,EffectParameterClass.Vector,3),codec.VECTOR4:(EffectParameterType.Single,EffectParameterClass.Vector,4),codec.QUATERNION:(EffectParameterType.Single,EffectParameterClass.Vector,4),codec.MATRIX:(EffectParameterType.Single,EffectParameterClass.Matrix,None),codec.MATRIX_TRANSPOSE:(EffectParameterType.Single,EffectParameterClass.Matrix,None)}[tag]
        if actual_type!=expected[0] or actual_class!=expected[1]:raise TypeError(f"parameter {self._name!r} metadata does not support the requested typed value")
        if expected[2] is not None and max(self._info.row_count,self._info.column_count)!=expected[2]:raise TypeError(f"parameter {self._name!r} vector dimension does not match")
        if tag in (codec.MATRIX,codec.MATRIX_TRANSPOSE) and (self._info.row_count!=4 or self._info.column_count!=4):raise TypeError(f"parameter {self._name!r} is not a 4x4 Matrix")
    def SetValue(self,value):
        self._check();kind,tag,copied=codec.dispatch_value(value)
        if kind=="string":
            if self.ParameterType!=EffectParameterType.String:raise TypeError(f"parameter {self._name!r} is not String")
            codec.set_parameter_string(self._handle,copied);return
        if kind=="texture":self._set_texture(copied);return
        self._validate_tag(tag)
        if kind=="scalar":codec.set_parameter_value(self._handle,tag,copied);return
        codec.set_parameter_values(self._handle,tag,copied)
    def SetValueTranspose(self,value):
        self._check();kind,tag,copied=codec.dispatch_value(value,transpose=True)
        if kind not in ("scalar","array") or tag!=codec.MATRIX_TRANSPOSE:raise TypeError("SetValueTranspose accepts Matrix or a Matrix sequence")
        self._validate_tag(tag)
        (codec.set_parameter_value if kind=="scalar" else codec.set_parameter_values)(self._handle,tag,copied)
    def _set_texture(self,value):
        from ._texture_volume import Texture3D,TextureCube
        if self.ParameterClass!=EffectParameterClass.Object or self.ParameterType not in (EffectParameterType.Texture,EffectParameterType.Texture2D,EffectParameterType.Texture3D,EffectParameterType.TextureCube):raise TypeError(f"parameter {self._name!r} is not a texture parameter")
        if value.IsDisposed:raise RuntimeError("texture is disposed")
        if value.GraphicsDevice is not self._effect.GraphicsDevice:raise ValueError("texture belongs to a different GraphicsDevice")
        tag=codec.TEXTURE_2D if isinstance(value,Texture2D) else codec.TEXTURE_3D if isinstance(value,Texture3D) else codec.TEXTURE_CUBE if isinstance(value,TextureCube) else codec.TEXTURE_BASE
        lib=get_library();lib.check(lib.cna_effect_parameter_set_value_texture(self._handle,tag,value._require_handle()),"cna_effect_parameter_set_value_texture")
        self._retained_texture=value
    def _get_texture(self,tag,expected):
        self._check();handle=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_parameter_get_value_texture(self._handle,tag,c.byref(handle)),"cna_effect_parameter_get_value_texture")
        if not handle.value:return None
        value=self._retained_texture
        if value is None or not isinstance(value,expected) or value._require_handle()!=handle.value:raise RuntimeError("native Effect texture was not assigned through this owning Python facade")
        return value
    def _one(self,tag):self._check();self._validate_tag(tag);return codec.get_parameter_value(self._handle,tag)
    def _many(self,tag,count):self._check();self._validate_tag(tag);return codec.get_parameter_values(self._handle,tag,count)
    GetValueBoolean=lambda s:s._one(codec.BOOLEAN); GetValueInt32=lambda s:s._one(codec.INT32); GetValueSingle=lambda s:s._one(codec.SINGLE)
    GetValueVector2=lambda s:s._one(codec.VECTOR2); GetValueVector3=lambda s:s._one(codec.VECTOR3); GetValueVector4=lambda s:s._one(codec.VECTOR4)
    GetValueQuaternion=lambda s:s._one(codec.QUATERNION); GetValueMatrix=lambda s:s._one(codec.MATRIX)
    def GetValueString(self):
        self._check()
        if self.ParameterType!=EffectParameterType.String:raise TypeError(f"parameter {self._name!r} is not String")
        return codec.get_parameter_string(self._handle)
    GetValueBooleanArray=lambda s,n:s._many(codec.BOOLEAN,n); GetValueInt32Array=lambda s,n:s._many(codec.INT32,n); GetValueSingleArray=lambda s,n:s._many(codec.SINGLE,n)
    GetValueVector2Array=lambda s,n:s._many(codec.VECTOR2,n); GetValueVector3Array=lambda s,n:s._many(codec.VECTOR3,n); GetValueVector4Array=lambda s,n:s._many(codec.VECTOR4,n)
    GetValueQuaternionArray=lambda s,n:s._many(codec.QUATERNION,n); GetValueMatrixArray=lambda s,n:s._many(codec.MATRIX,n)
    GetValueMatrixTranspose=lambda s:s._one(codec.MATRIX_TRANSPOSE); GetValueMatrixTransposeArray=lambda s,n:s._many(codec.MATRIX_TRANSPOSE,n)
    def GetValueTexture2D(self):return self._get_texture(codec.TEXTURE_2D,Texture2D)
    def GetValueTexture3D(self):
        from ._texture_volume import Texture3D
        return self._get_texture(codec.TEXTURE_3D,Texture3D)
    def GetValueTextureCube(self):
        from ._texture_volume import TextureCube
        return self._get_texture(codec.TEXTURE_CUBE,TextureCube)
class EffectParameterCollection(_ViewCollection):
    def GetParameterBySemantic(self,semantic):
        self._check()
        cached=next((p for p in self._values if p.Semantic==semantic),None)
        if self._handle:
            encoded=semantic.encode("utf-8",errors="strict");found=c.c_uint8();view=c.c_uint64();lib=get_library();op="cna_effect_parameter_collection_find_semantic"
            lib.check(lib.cna_effect_parameter_collection_find_semantic(self._handle,abi.CNA_StringView(encoded,len(encoded)),c.byref(found),c.byref(view)),op)
            if view.value:lib.check(lib.cna_effect_parameter_destroy(view.value),"cna_effect_parameter_destroy")
            if bool(found.value)!=(cached is not None):raise RuntimeError("native Effect semantic identity disagrees with cached reflection")
        return cached
    def GetEnumerator(self): return iter(self)

class EffectPass(_NativeView):
    _destroy_operation="cna_effect_pass_destroy"
    def __init__(self,parent,handle): self._init_view(parent,handle);self._name=_native_name(handle,"pass");self._annotations=None
    Name=property(lambda s:(s._check(),s._name)[1])
    @property
    def Annotations(self):
        self._check()
        if self._annotations is None:
            out=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_pass_get_annotations(self._handle,c.byref(out)),"cna_effect_pass_get_annotations");self._annotations=_load_annotation_collection(self,out.value)
        return self._annotations
    def Apply(self):
        self._check();get_library().check(get_library().cna_effect_pass_apply(self._handle),"cna_effect_pass_apply")
class EffectPassCollection(_ViewCollection): pass
EffectPassCollection.GetEnumerator=lambda self: iter(self)
class EffectTechnique(_NativeView):
    _destroy_operation="cna_effect_technique_destroy"
    def __init__(self,parent,handle):
        self._init_view(parent,handle);self._name=_native_name(handle,"technique");self._annotations=None
        out=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_technique_get_passes(handle,c.byref(out)),"cna_effect_technique_get_passes")
        count=c.c_uint64();lib.check(lib.cna_effect_pass_collection_get_count(out.value,c.byref(count)),"cna_effect_pass_collection_get_count")
        collection=EffectPassCollection(self,(),out.value,"cna_effect_pass_collection_destroy")
        values=[]
        for i in range(count.value):
            child=c.c_uint64();lib.check(lib.cna_effect_pass_collection_get_at(out.value,i,c.byref(child)),"cna_effect_pass_collection_get_at");values.append(EffectPass(self,child.value))
        collection._values=tuple(values);self._passes=collection
    Name=property(lambda s:(s._check(),s._name)[1]); Passes=property(lambda s:(s._check(),s._passes)[1])
    @property
    def Annotations(self):
        self._check()
        if self._annotations is None:
            out=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_technique_get_annotations(self._handle,c.byref(out)),"cna_effect_technique_get_annotations");self._annotations=_load_annotation_collection(self,out.value)
        return self._annotations
class EffectTechniqueCollection(_ViewCollection): pass
EffectTechniqueCollection.GetEnumerator=lambda self: iter(self)

def _native_name(handle, kind):
    return codec.copy_utf8(handle,f"cna_effect_{kind}_get_name_byte_count",f"cna_effect_{kind}_copy_name")

def _load_parameter_collection(parent,handle):
    lib=get_library();count=c.c_uint64();lib.check(lib.cna_effect_parameter_collection_get_count(handle,c.byref(count)),"cna_effect_parameter_collection_get_count")
    collection=EffectParameterCollection(parent,(),handle,"cna_effect_parameter_collection_destroy","cna_effect_parameter_collection_find_name")
    values=[]
    for index in range(count.value):
        child=c.c_uint64();lib.check(lib.cna_effect_parameter_collection_get_at(handle,index,c.byref(child)),"cna_effect_parameter_collection_get_at");values.append(EffectParameter(parent,child.value))
    collection._values=tuple(values);return collection

def _load_annotation_collection(parent,handle):
    lib=get_library();count=c.c_uint64();lib.check(lib.cna_effect_annotation_collection_get_count(handle,c.byref(count)),"cna_effect_annotation_collection_get_count")
    collection=EffectAnnotationCollection(parent,(),handle,"cna_effect_annotation_collection_destroy","cna_effect_annotation_collection_find")
    values=[]
    for index in range(count.value):
        child=c.c_uint64();lib.check(lib.cna_effect_annotation_collection_get_at(handle,index,c.byref(child)),"cna_effect_annotation_collection_get_at");values.append(EffectAnnotation(parent,child.value))
    collection._values=tuple(values);return collection

def _create_native_parameter_for_tests(effect,name,semantic,parameter_class,parameter_type,rows=1,columns=1):
    """Create a real parameter in an Effect's native reflection collection."""
    effect._check();name_bytes=name.encode("utf-8");semantic_bytes=semantic.encode("utf-8")
    info=abi.CNA_EffectParameterCreateInfo();info.struct_size,info.struct_version=c.sizeof(info),1
    info.name=abi.CNA_StringView(name_bytes,len(name_bytes));info.semantic=abi.CNA_StringView(semantic_bytes,len(semantic_bytes))
    info.row_count,info.column_count=int32(rows,name="rows"),int32(columns,name="columns")
    info.parameter_class,info.parameter_type=int(parameter_class),int(parameter_type)
    output=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_parameter_collection_add_create(effect._parameters._handle,c.byref(info),c.byref(output)),"cna_effect_parameter_collection_add_create")
    parameter=EffectParameter(effect,output.value);effect._parameters._values=(*effect._parameters._values,parameter);return parameter

def _add_native_annotation_for_tests(parameter,name,semantic,parameter_class,parameter_type,data=(),string=""):
    """Append a copied real ABI annotation to a real parameter collection."""
    parameter._check();name_bytes=name.encode("utf-8");semantic_bytes=semantic.encode("utf-8");string_bytes=string.encode("utf-8")
    if parameter_type in (EffectParameterType.Bool,EffectParameterType.Int32):
        native_storage=(c.c_int32*len(data))(*(int(value) for value in data))
        native_data=c.cast(native_storage,c.POINTER(c.c_float))
    else:
        native_storage=(c.c_float*len(data))(*data)
        native_data=c.cast(native_storage,c.POINTER(c.c_float))
    info=abi.CNA_EffectAnnotationCreateInfo();info.struct_size,info.struct_version=c.sizeof(info),1
    info.name=abi.CNA_StringView(name_bytes,len(name_bytes));info.semantic=abi.CNA_StringView(semantic_bytes,len(semantic_bytes))
    if parameter_class==EffectParameterClass.Matrix and len(data)==16:info.row_count,info.column_count=4,4
    else:info.row_count,info.column_count=1,max(1,len(data))
    info.parameter_class,info.parameter_type=int(parameter_class),int(parameter_type)
    info.data=None if not data else native_data;info.data_count=len(data);info.cached_string=abi.CNA_StringView(string_bytes,len(string_bytes))
    lib=get_library();annotation=c.c_uint64();collection=c.c_uint64()
    lib.check(lib.cna_effect_annotation_create(c.byref(info),c.byref(annotation)),"cna_effect_annotation_create")
    try:
        lib.check(lib.cna_effect_parameter_get_annotations(parameter._handle,c.byref(collection)),"cna_effect_parameter_get_annotations")
        try:lib.check(lib.cna_effect_annotation_collection_add(collection.value,annotation.value),"cna_effect_annotation_collection_add")
        finally:lib.check(lib.cna_effect_annotation_collection_destroy(collection.value),"cna_effect_annotation_collection_destroy")
    finally:lib.check(lib.cna_effect_annotation_destroy(annotation.value),"cna_effect_annotation_destroy")

def _copy(v): return v.__copy__() if hasattr(v,"__copy__") else list(v) if isinstance(v,(list,tuple)) else v

class Effect(GraphicsResource):
    def __init__(self, graphicsDevice=None, bytecode=None, _kind="empty", _clone_of=None):
        if _clone_of is None and bytecode is None and isinstance(graphicsDevice,Effect):
            _clone_of=graphicsDevice;graphicsDevice=_clone_of.GraphicsDevice
        if not isinstance(graphicsDevice,GraphicsDevice): raise TypeError("graphicsDevice must be GraphicsDevice")
        output=c.c_uint64(); lib=get_library()
        if _clone_of is not None: op="cna_effect_clone"; result=lib.cna_effect_clone(_clone_of._require_handle(),c.byref(output))
        elif bytecode is not None:
            data=bytes(bytecode); buf=(c.c_uint8*len(data)).from_buffer_copy(data); result=lib.cna_effect_create_compiled(graphicsDevice._require_handle(),buf,len(data),c.byref(output)); op="cna_effect_create_compiled"
        else: op="cna_effect_create_empty"; result=lib.cna_effect_create_empty(graphicsDevice._require_handle(),c.byref(output))
        lib.check(result,op);self._initialize_native(graphicsDevice,int(output.value))
    def _initialize_native(self,graphicsDevice,handle):
        self._init_resource(graphicsDevice,handle,_release("cna_effect_destroy"));self._effect=self;self._view_registry=[];self._state={};lib=get_library()
        parameters=c.c_uint64();lib.check(lib.cna_effect_get_parameters(handle,c.byref(parameters)),"cna_effect_get_parameters");self._parameters=_load_parameter_collection(self,parameters.value)
        collection=c.c_uint64(); lib.check(lib.cna_effect_get_techniques(handle,c.byref(collection)),"cna_effect_get_techniques")
        count=c.c_uint64(); lib.check(lib.cna_effect_technique_collection_get_count(collection.value,c.byref(count)),"cna_effect_technique_collection_get_count")
        techniques=EffectTechniqueCollection(self,(),collection.value,"cna_effect_technique_collection_destroy")
        values=[]
        for i in range(count.value):
            th=c.c_uint64();lib.check(lib.cna_effect_technique_collection_get_at(collection.value,i,c.byref(th)),"cna_effect_technique_collection_get_at");values.append(EffectTechnique(self,th.value))
        techniques._values=tuple(values);self._techniques=techniques
        current=c.c_uint64();lib.check(lib.cna_effect_get_current_technique(handle,c.byref(current)),"cna_effect_get_current_technique")
        if current.value:
            current_name=_native_name(current.value,"technique");self._current=next((x for x in values if x.Name==current_name),None);lib.check(lib.cna_effect_technique_destroy(current.value),"cna_effect_technique_destroy")
        else:self._current=None
    def _register_view(self,view,operation,priority):self._view_registry.append((priority,view,operation))
    def _check(self): self._require_handle()
    Parameters=property(lambda s:(s._check(),s._parameters)[1]); Techniques=property(lambda s:(s._check(),s._techniques)[1])
    @property
    def CurrentTechnique(self):self._check();return self._current
    @CurrentTechnique.setter
    def CurrentTechnique(self,value):
        self._check()
        if not isinstance(value,EffectTechnique) or value._effect is not self:raise ValueError("CurrentTechnique must belong to this Effect")
        get_library().check(get_library().cna_effect_set_current_technique(self._require_handle(),value._handle),"cna_effect_set_current_technique");self._current=value
    def Clone(self): return type(self)(self.GraphicsDevice,_clone_of=self)
    def OnApply(self): self._check(); get_library().check(get_library().cna_effect_apply(self._require_handle()),"cna_effect_apply")
    def _before_dispose(self):
        first=None
        for _,view,operation in sorted(self._view_registry,key=lambda item:item[0]):
            try:view._invalidate(operation)
            except BaseException as error:
                if first is None:first=error
        self._view_registry.clear()
        if first is not None:self._dispose_error=first
    def _set(self,name,value): self._check(); self._state[name]=_copy(value)
    def _get(self,name,default): self._check(); return _copy(self._state.get(name,default))

def _interface_property(writable=True):
    def get(self): raise NotImplementedError
    def set(self,value): raise NotImplementedError
    return property(get,set if writable else None)
class IEffectFog:
    FogEnabled=_interface_property(); FogStart=_interface_property(); FogEnd=_interface_property(); FogColor=_interface_property()
class IEffectLights:
    AmbientLightColor=_interface_property(); DirectionalLight0=_interface_property(False); DirectionalLight1=_interface_property(False); DirectionalLight2=_interface_property(False); LightingEnabled=_interface_property()
    def EnableDefaultLighting(self): raise NotImplementedError
class IEffectMatrices:
    World=_interface_property(); View=_interface_property(); Projection=_interface_property()

def _native_matrix(value):
    if not isinstance(value,Matrix):raise TypeError("value must be Matrix")
    return abi.CNA_Matrix(*tuple(value))

def _python_matrix(value):
    return Matrix(*(getattr(value,f"m{row}{column}") for row in range(1,5) for column in range(1,5)))

def _matrix_property(name):
    def get(self):
        self._check();value=abi.CNA_Matrix();op=f"cna_effect_matrices_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),c.byref(value)),op);return _python_matrix(value)
    def set(self,value):
        native=_native_matrix(value);self._check();op=f"cna_effect_matrices_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),native),op)
    return property(get,set)

def _bool_property(prefix,name):
    def get(self):
        self._check();value=c.c_uint8();op=f"cna_{prefix}_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),c.byref(value)),op);return bool(value.value)
    def set(self,value):
        if type(value) is not bool:raise TypeError(f"{name} must be bool")
        self._check();op=f"cna_{prefix}_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),value),op)
    return property(get,set)

def _float_property(prefix,name):
    def get(self):
        self._check();value=c.c_float();op=f"cna_{prefix}_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),c.byref(value)),op);return float(value.value)
    def set(self,value):
        value=f32(value);self._check();op=f"cna_{prefix}_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),value),op)
    return property(get,set)

def _int_property(prefix,name,convert=lambda value:value):
    def get(self):
        self._check();value=c.c_int32();op=f"cna_{prefix}_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),c.byref(value)),op);return convert(value.value)
    def set(self,value):
        value=int32(value,name=name);self._check();op=f"cna_{prefix}_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),value),op)
    return property(get,set)

def _enum_property(prefix,name,enum_type):
    def get(self):
        self._check();value=c.c_uint32();op=f"cna_{prefix}_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),c.byref(value)),op);return enum_type(value.value)
    def set(self,value):
        if not isinstance(value,enum_type):raise TypeError(f"{name} must be {enum_type.__name__}")
        self._check();op=f"cna_{prefix}_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),int(value)),op)
    return property(get,set)

def _vector3_property(prefix,name):
    def get(self):
        self._check();value=abi.CNA_Vector3();op=f"cna_{prefix}_get_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),c.byref(value)),op);return Vector3(value.x,value.y,value.z)
    def set(self,value):
        if not isinstance(value,Vector3):raise TypeError(f"{name} must be Vector3")
        self._check();op=f"cna_{prefix}_set_{name}";lib=get_library();lib.check(getattr(lib,op)(self._require_handle(),abi.CNA_Vector3(*tuple(value))),op)
    return property(get,set)

def _texture_property(prefix,name,expected_type,index=None):
    key=f"{prefix}:{name}:{index}"
    def get(self):
        self._check();present=c.c_uint8();handle=c.c_uint64();op=f"cna_{prefix}_get_{name}";lib=get_library()
        args=(self._require_handle(),c.byref(present),c.byref(handle)) if index is None else (self._require_handle(),index,c.byref(present),c.byref(handle))
        lib.check(getattr(lib,op)(*args),op)
        if not present.value:return None
        value=self._state.get(key)
        if value is None or not isinstance(value,expected_type) or value._require_handle()!=handle.value:raise RuntimeError("native stock Effect texture identity is not retained by this Python owner")
        return value
    def set(self,value):
        if value is not None:
            if not isinstance(value,expected_type):raise TypeError(f"{name} must be {expected_type.__name__} or None")
            if value.IsDisposed:raise RuntimeError("texture is disposed")
            if value.GraphicsDevice is not self.GraphicsDevice:raise ValueError("texture belongs to a different GraphicsDevice")
        self._check();handle=0 if value is None else value._require_handle();op=f"cna_{prefix}_set_{name}";lib=get_library()
        args=(self._require_handle(),handle) if index is None else (self._require_handle(),index,handle)
        lib.check(getattr(lib,op)(*args),op);self._state[key]=value
    return property(get,set)

def _stock_route(self,allowed):
    prefix=self._native_constructor.removeprefix("cna_").removesuffix("_create")
    if prefix not in allowed:raise AttributeError("this stock Effect does not expose that property")
    return prefix

def _stock_property(factory,name,allowed):
    descriptors={prefix:factory(prefix,name) for prefix in allowed}
    return property(lambda self:descriptors[_stock_route(self,allowed)].fget(self),lambda self,value:descriptors[_stock_route(self,allowed)].fset(self,value))

def _stock_texture_property(name,allowed,indexes=None):
    indexes={} if indexes is None else indexes
    descriptors={prefix:_texture_property(prefix,name,Texture2D,indexes.get(prefix)) for prefix in allowed}
    return property(lambda self:descriptors[_stock_route(self,allowed)].fget(self),lambda self,value:descriptors[_stock_route(self,allowed)].fset(self,value))

class _StockEffect:
    _native_constructor="cna_basic_effect_create"
    def __init__(self, graphicsDevice, _clone_of=None):
        if _clone_of is None and isinstance(graphicsDevice,type(self)):
            _clone_of=graphicsDevice;graphicsDevice=_clone_of.GraphicsDevice
        if _clone_of is not None:
            if not isinstance(graphicsDevice,GraphicsDevice):raise TypeError("graphicsDevice must be GraphicsDevice")
            out=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_clone(_clone_of._require_handle(),c.byref(out)),"cna_effect_clone");self._initialize_native(graphicsDevice,int(out.value));self._state={name:_copy(value) for name,value in _clone_of._state.items() if not name.startswith("light")};return
        if not isinstance(graphicsDevice,GraphicsDevice):raise TypeError("graphicsDevice must be GraphicsDevice")
        out=c.c_uint64();lib=get_library();op=self._native_constructor;lib.check(getattr(lib,op)(graphicsDevice._require_handle(),c.byref(out)),op);self._initialize_native(graphicsDevice,int(out.value))
    def Clone(self): return type(self)(self.GraphicsDevice,_clone_of=self)
    def EnableDefaultLighting(self):
        self._check();get_library().check(get_library().cna_effect_lights_enable_default(self._require_handle()),"cna_effect_lights_enable_default")
    World=_matrix_property("world"); View=_matrix_property("view"); Projection=_matrix_property("projection")
    FogEnabled=_bool_property("effect_fog","enabled"); FogStart=_float_property("effect_fog","start"); FogEnd=_float_property("effect_fog","end"); FogColor=_vector3_property("effect_fog","color")
    LightingEnabled=_bool_property("effect_lights","enabled"); AmbientLightColor=_vector3_property("effect_lights","ambient_color")
    DiffuseColor=_stock_property(_vector3_property,"diffuse_color",("basic_effect","alpha_test_effect","dual_texture_effect","environment_map_effect","skinned_effect"))
    EmissiveColor=_stock_property(_vector3_property,"emissive_color",("basic_effect","environment_map_effect","skinned_effect"))
    SpecularColor=_stock_property(_vector3_property,"specular_color",("basic_effect","skinned_effect")); SpecularPower=_stock_property(_float_property,"specular_power",("basic_effect","skinned_effect"))
    Alpha=_stock_property(_float_property,"alpha",("basic_effect","alpha_test_effect","dual_texture_effect","environment_map_effect","skinned_effect"))
    Texture=_stock_texture_property("texture",("basic_effect","alpha_test_effect","dual_texture_effect","environment_map_effect","skinned_effect"),{"dual_texture_effect":0})
    TextureEnabled=_stock_property(_bool_property,"texture_enabled",("basic_effect",)); VertexColorEnabled=_stock_property(_bool_property,"vertex_color_enabled",("basic_effect","alpha_test_effect","dual_texture_effect"))
    PreferPerPixelLighting=_stock_property(_bool_property,"prefer_per_pixel_lighting",("basic_effect","skinned_effect"))
    DirectionalLight0=property(lambda s:s._light(0)); DirectionalLight1=property(lambda s:s._light(1)); DirectionalLight2=property(lambda s:s._light(2))
    def _light(self,i):
        key=f"light{i}"; self._check();
        if key not in self._state:self._state[key]=DirectionalLight(self,i)
        return self._state[key]
class BasicEffect(Effect, _StockEffect, IEffectFog, IEffectLights, IEffectMatrices):
    __init__=_StockEffect.__init__
class AlphaTestEffect(Effect, _StockEffect, IEffectFog, IEffectMatrices):
    __init__=_StockEffect.__init__; _native_constructor="cna_alpha_test_effect_create"
    AlphaFunction=_enum_property("alpha_test_effect","alpha_function",CompareFunction); ReferenceAlpha=_int_property("alpha_test_effect","reference_alpha")
class DualTextureEffect(Effect, _StockEffect, IEffectFog, IEffectMatrices):
    __init__=_StockEffect.__init__; _native_constructor="cna_dual_texture_effect_create"
    Texture2=_texture_property("dual_texture_effect","texture",Texture2D,1)
class EnvironmentMapEffect(Effect, _StockEffect, IEffectFog, IEffectLights, IEffectMatrices):
    __init__=_StockEffect.__init__; _native_constructor="cna_environment_map_effect_create"
    EnvironmentMap=_texture_property("environment_map_effect","environment_map",TextureCube)
    EnvironmentMapAmount=_float_property("environment_map_effect","amount"); EnvironmentMapSpecular=_vector3_property("environment_map_effect","specular"); FresnelFactor=_float_property("environment_map_effect","fresnel_factor")
    LightingEnabled=_bool_property("effect_lights","enabled")
class SkinnedEffect(Effect, _StockEffect, IEffectFog, IEffectLights, IEffectMatrices):
    __init__=_StockEffect.__init__
    _native_constructor="cna_skinned_effect_create"; MaxBones=72
    LightingEnabled=_bool_property("effect_lights","enabled")
    WeightsPerVertex=_int_property("skinned_effect","weights_per_vertex")
    def SetBoneTransforms(self,boneTransforms):
        values=list(boneTransforms)
        if not 1<=len(values)<=self.MaxBones:raise ValueError(f"boneTransforms must contain between 1 and {self.MaxBones} matrices")
        native=(abi.CNA_Matrix*len(values))(*(_native_matrix(value) for value in values));self._check();lib=get_library();lib.check(lib.cna_skinned_effect_set_bone_transforms(self._require_handle(),native,len(values)),"cna_skinned_effect_set_bone_transforms")
    def GetBoneTransforms(self,count):
        count=int32(count,name="count")
        if not 1<=count<=self.MaxBones:raise ValueError(f"count must be between 1 and {self.MaxBones}")
        values=(abi.CNA_Matrix*count)();written=c.c_uint64();self._check();lib=get_library();lib.check(lib.cna_skinned_effect_copy_bone_transforms(self._require_handle(),count,values,count,c.byref(written)),"cna_skinned_effect_copy_bone_transforms");return [_python_matrix(values[i]) for i in range(written.value)]
class EffectMaterial(Effect):
    def __init__(self,cloneSource):
        if not isinstance(cloneSource,Effect):raise TypeError("cloneSource must be Effect")
        out=c.c_uint64();lib=get_library();lib.check(lib.cna_effect_material_create(cloneSource._require_handle(),c.byref(out)),"cna_effect_material_create");self._initialize_native(cloneSource.GraphicsDevice,int(out.value))

Effect.__xna_arities__={"__init__":{1,2},"Dispose":{0,1}}
EffectMaterial.__xna_arities__={"__init__":{1}}
DirectionalLight.__xna_arities__={"__init__":{4}}
for _s in (BasicEffect,AlphaTestEffect,DualTextureEffect,EnvironmentMapEffect,SkinnedEffect): _s.__xna_arities__={"__init__":{1}}
