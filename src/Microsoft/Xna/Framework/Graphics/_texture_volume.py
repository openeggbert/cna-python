"""Native Texture3D and TextureCube resources (Color codec)."""

from __future__ import annotations

import ctypes as c
from collections.abc import MutableSequence, Sequence

from _cna_native import abi
from _cna_native.errors import NativeCapabilityError
from _cna_native.loader import get_library

from .._geometry import Color, Rectangle
from .._numeric import int32
from ._device import CubeMapFace, GraphicsDevice, SurfaceFormat
from ._resources import Texture, _release


def _color_array(data: Sequence[Color]):
    if not isinstance(data, Sequence) or not all(isinstance(value, Color) for value in data):
        raise NativeCapabilityError("volume texture data transfer", 6, None,
                                    "CNA's volume-texture transfer exposes only Color element arrays")
    return (abi.CNA_Color * len(data))(*(abi.CNA_Color(*tuple(value)) for value in data))


def _range(data, start, count):
    start=int32(start,name="startIndex");count=int32(count,name="elementCount")
    if start<0 or count<0 or start+count>len(data):
        raise ValueError("texture data range is outside the supplied array")
    return start,count


class Texture3D(Texture):
    __slots__=("_width","_height","_depth","_level_count","_format")

    def __init__(self,graphicsDevice,width,height,depth,mipMap,format):
        if not isinstance(graphicsDevice,GraphicsDevice):raise TypeError("graphicsDevice must be GraphicsDevice")
        width=int32(width,name="width");height=int32(height,name="height");depth=int32(depth,name="depth")
        if min(width,height,depth)<=0:raise ValueError("texture dimensions must be positive")
        try:selected=SurfaceFormat(format)
        except (TypeError,ValueError) as error:raise ValueError("format is not a SurfaceFormat") from error
        info=abi.CNA_Texture3DCreateInfo();info.struct_size,info.struct_version=c.sizeof(info),1
        info.width,info.height,info.depth=width,height,depth;info.mip_map=bool(mipMap);info.format=int(selected)
        output=c.c_uint64();lib=get_library();lib.check(lib.cna_texture3d_create(graphicsDevice._require_handle(),c.byref(info),c.byref(output)),"cna_texture3d_create")
        self._init_resource(graphicsDevice,int(output.value),_release("cna_texture3d_destroy"));self._read_info()

    @classmethod
    def _from_handle(cls,graphicsDevice,handle):
        self=cls.__new__(cls);self._init_resource(graphicsDevice,handle,_release("cna_texture3d_destroy"));self._read_info();return self

    def _read_info(self):
        value=abi.CNA_Texture3DInfo();value.struct_size,value.struct_version=c.sizeof(value),1
        lib=get_library();lib.check(lib.cna_texture3d_get_info(self._require_handle(),c.byref(value)),"cna_texture3d_get_info")
        self._width,self._height,self._depth=int(value.width),int(value.height),int(value.depth)
        self._level_count,self._format=int(value.level_count),SurfaceFormat(value.format)

    @property
    def Width(self):self._require_handle();return self._width
    @property
    def Height(self):self._require_handle();return self._height
    @property
    def Depth(self):self._require_handle();return self._depth

    def _transfer(self,args):
        if len(args)==1:data=args[0];level=0;left=top=front=0;right,bottom,back=self._width,self._height,self._depth;start=0;count=len(data)
        elif len(args)==3:data,start,count=args;level=0;left=top=front=0;right,bottom,back=self._width,self._height,self._depth
        elif len(args)==10:level,left,top,right,bottom,front,back,data,start,count=args
        else:raise TypeError("Texture3D data transfer expects data; data,start,count; or level,box,data,start,count")
        _color_array(data);level=int32(level,name="level")
        if level<0 or level>=self._level_count:raise ValueError("level is outside the mip chain")
        values=[int32(value,name=name) for value,name in zip((left,top,right,bottom,front,back),("left","top","right","bottom","front","back"))]
        left,top,right,bottom,front,back=values;max_width=max(1,self._width>>level);max_height=max(1,self._height>>level);max_depth=max(1,self._depth>>level)
        if not (0<=left<right<=max_width and 0<=top<bottom<=max_height and 0<=front<back<=max_depth):raise ValueError("Texture3D box is outside the selected mip level")
        start,count=_range(data,start,count);required=(right-left)*(bottom-top)*(back-front)
        if count!=required:raise ValueError(f"Texture3D Color transfer requires exactly {required} elements")
        transfer=abi.CNA_Texture3DTransfer();transfer.struct_size,transfer.struct_version=c.sizeof(transfer),1
        transfer.level,transfer.left,transfer.top,transfer.right,transfer.bottom,transfer.front,transfer.back=level,left,top,right,bottom,front,back
        transfer.start_index,transfer.element_count=start,count
        return data,transfer

    def SetData(self,*args):
        data,transfer=self._transfer(args);native=_color_array(data);lib=get_library()
        lib.check(lib.cna_texture3d_set_data(self._require_handle(),c.byref(transfer),native,len(data)),"cna_texture3d_set_data")

    def GetData(self,*args):
        data,transfer=self._transfer(args)
        if not isinstance(data,MutableSequence):raise TypeError("GetData destination must be mutable")
        native=(abi.CNA_Color*len(data))();required=c.c_uint64();lib=get_library()
        lib.check(lib.cna_texture3d_get_data(self._require_handle(),c.byref(transfer),native,len(data),c.byref(required)),"cna_texture3d_get_data")
        for index in range(transfer.start_index,transfer.start_index+transfer.element_count):
            value=native[index];data[index]=Color(value.r,value.g,value.b,value.a)


class TextureCube(Texture):
    __slots__=("_size","_level_count","_format")

    def __init__(self,graphicsDevice,size,mipMap,format):
        if not isinstance(graphicsDevice,GraphicsDevice):raise TypeError("graphicsDevice must be GraphicsDevice")
        size=int32(size,name="size")
        if size<=0:raise ValueError("size must be positive")
        try:selected=SurfaceFormat(format)
        except (TypeError,ValueError) as error:raise ValueError("format is not a SurfaceFormat") from error
        info=abi.CNA_TextureCubeCreateInfo();info.struct_size,info.struct_version=c.sizeof(info),1
        info.size,info.mip_map,info.format=size,bool(mipMap),int(selected)
        output=c.c_uint64();lib=get_library();lib.check(lib.cna_texturecube_create(graphicsDevice._require_handle(),c.byref(info),c.byref(output)),"cna_texturecube_create")
        self._init_resource(graphicsDevice,int(output.value),_release("cna_texturecube_destroy"));self._read_info()

    @classmethod
    def _from_handle(cls,graphicsDevice,handle):
        self=cls.__new__(cls);self._init_resource(graphicsDevice,handle,_release("cna_texturecube_destroy"));self._read_info();return self

    def _read_info(self):
        value=abi.CNA_TextureCubeInfo();value.struct_size,value.struct_version=c.sizeof(value),1
        lib=get_library();lib.check(lib.cna_texturecube_get_info(self._require_handle(),c.byref(value)),"cna_texturecube_get_info")
        self._size,self._level_count,self._format=int(value.size),int(value.level_count),SurfaceFormat(value.format)

    @property
    def Size(self):self._require_handle();return self._size

    def _transfer(self,args):
        if len(args)==2:face,data=args;level=0;rectangle=None;start=0;count=len(data)
        elif len(args)==4:face,data,start,count=args;level=0;rectangle=None
        elif len(args)==6:face,level,rectangle,data,start,count=args
        else:raise TypeError("TextureCube data transfer expects face,data; face,data,start,count; or face,level,rect,data,start,count")
        try:face=CubeMapFace(face)
        except (TypeError,ValueError) as error:raise ValueError("cubeMapFace is invalid") from error
        _color_array(data);level=int32(level,name="level")
        if level<0 or level>=self._level_count:raise ValueError("level is outside the mip chain")
        mip_size=max(1,self._size>>level)
        if rectangle is not None:
            if not isinstance(rectangle,Rectangle):raise TypeError("rect must be Rectangle or None")
            if rectangle.Width<=0 or rectangle.Height<=0 or rectangle.X<0 or rectangle.Y<0 or rectangle.Right>mip_size or rectangle.Bottom>mip_size:raise ValueError("TextureCube rectangle is outside the selected mip level")
            required=rectangle.Width*rectangle.Height
        else:required=mip_size*mip_size
        start,count=_range(data,start,count)
        if count!=required:raise ValueError(f"TextureCube Color transfer requires exactly {required} elements")
        transfer=abi.CNA_TextureCubeTransfer();transfer.struct_size,transfer.struct_version=c.sizeof(transfer),1
        transfer.face,transfer.level,transfer.has_rectangle=int(face),level,rectangle is not None
        if rectangle is not None:transfer.rectangle=abi.CNA_Rectangle(*tuple(rectangle))
        transfer.start_index,transfer.element_count=start,count
        return data,transfer

    def SetData(self,*args):
        data,transfer=self._transfer(args);native=_color_array(data);lib=get_library()
        lib.check(lib.cna_texturecube_set_data(self._require_handle(),c.byref(transfer),native,len(data)),"cna_texturecube_set_data")

    def GetData(self,*args):
        data,transfer=self._transfer(args)
        if not isinstance(data,MutableSequence):raise TypeError("GetData destination must be mutable")
        native=(abi.CNA_Color*len(data))();required=c.c_uint64();lib=get_library()
        lib.check(lib.cna_texturecube_get_data(self._require_handle(),c.byref(transfer),native,len(data),c.byref(required)),"cna_texturecube_get_data")
        for index in range(transfer.start_index,transfer.start_index+transfer.element_count):
            value=native[index];data[index]=Color(value.r,value.g,value.b,value.a)


Texture3D.__xna_arities__={"__init__":{6},"SetData":{1,3,10},"GetData":{1,3,10},"Dispose":{0,1}}
TextureCube.__xna_arities__={"__init__":{4},"SetData":{2,4,6},"GetData":{2,4,6},"Dispose":{0,1}}
