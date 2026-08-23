"""XNA Model graph over ordinary buffers, Effects, passes, and indexed draws."""

from __future__ import annotations

import weakref

from .._intersections import BoundingSphere
from .._math import Matrix, Vector3
from ._device import PrimitiveType
from ._effects import Effect, IEffectMatrices


class _Enum:
    def __init__(self,values):self._values=tuple(values);self._index=-1;self._current=None
    @property
    def Current(self):return self._current
    def MoveNext(self):
        if self._index+1>=len(self._values):self._index=len(self._values);self._current=None;return False
        self._index+=1;self._current=self._values[self._index];return True
    def Dispose(self):self._current=None
    def __iter__(self):
        while self.MoveNext():yield self.Current
    def __copy__(self):
        result=type(self)(self._values);result._index=self._index;result._current=self._current;return result
    __deepcopy__=lambda self,memo:self.__copy__()


class _Collection:
    def __init__(self,values=(),owner=None):self._values=list(values);self._owner_ref=None if owner is None else weakref.ref(owner)
    def _owner(self):return None if self._owner_ref is None else self._owner_ref()
    def _check(self):
        owner=self._owner()
        if owner is not None:owner._check()
    @property
    def Count(self):self._check();return len(self._values)
    def __iter__(self):self._check();return iter(tuple(self._values))
    def __getitem__(self,key):
        self._check()
        if isinstance(key,str):
            for value in self._values:
                if value.Name==key:return value
            raise KeyError(key)
        return self._values[key]
    def GetEnumerator(self):self._check();return _Enum(self._values)


class ModelBone:
    def __init__(self,name,index,transform=None):
        if not isinstance(name,str):raise TypeError("name must be str")
        self._name=name;self._index=int(index);self._transform=Matrix.Identity if transform is None else transform.__copy__()
        if not isinstance(self._transform,Matrix):raise TypeError("transform must be Matrix")
        self._owner_ref=None;self._parent_ref=None;self._children=ModelBoneCollection((),self)
    def _owner(self):return None if self._owner_ref is None else self._owner_ref()
    def _check(self):
        owner=self._owner()
        if owner is not None:owner._check()
    @property
    def Name(self):self._check();return self._name
    @property
    def Index(self):self._check();return self._index
    @property
    def Parent(self):self._check();return None if self._parent_ref is None else self._parent_ref()
    @property
    def Children(self):self._check();return self._children
    @property
    def Transform(self):self._check();return self._transform.__copy__()
    @Transform.setter
    def Transform(self,value):
        self._check()
        if not isinstance(value,Matrix):raise TypeError("Transform must be Matrix")
        self._transform=value.__copy__()
    def _add_child(self,child):
        if not isinstance(child,ModelBone):raise TypeError("child must be ModelBone")
        if child is self:raise ValueError("a bone cannot be its own child")
        if child._parent_ref is not None and child._parent_ref() is not self:raise ValueError("a model bone cannot have more than one parent")
        if child not in self._children._values:self._children._values.append(child)
        child._parent_ref=weakref.ref(self)


class ModelBoneCollection(_Collection):
    def TryGetValue(self,boneName,value=None):
        try:return True,self[boneName]
        except KeyError:return False,None


class ModelEffectCollection(_Collection):pass


class ModelMeshPart:
    def __init__(self,effect=None):
        self._effect=None;self._tag=None;self._vertex_buffer=None;self._index_buffer=None
        self._start=0;self._primitive=0;self._offset=0;self._num=0;self._owner_ref=None
        if effect is not None:self._assign_effect(effect,False)
    def _owner(self):return None if self._owner_ref is None else self._owner_ref()
    def _model(self):
        owner=self._owner();return None if owner is None else owner._owner()
    def _check(self):
        model=self._model()
        if model is not None:model._check()
    @property
    def StartIndex(self):self._check();return self._start
    @property
    def PrimitiveCount(self):self._check();return self._primitive
    @property
    def VertexOffset(self):self._check();return self._offset
    @property
    def NumVertices(self):self._check();return self._num
    @property
    def IndexBuffer(self):self._check();return self._index_buffer
    @property
    def VertexBuffer(self):self._check();return self._vertex_buffer
    @property
    def Effect(self):self._check();return self._effect
    @Effect.setter
    def Effect(self,value):self._check();self._assign_effect(value,True)
    def _assign_effect(self,value,rebuild):
        if value is not None and not isinstance(value,Effect):raise TypeError("Effect must be Effect or None")
        if value is not None and value.IsDisposed:raise RuntimeError("Effect is disposed")
        model=self._model()
        if value is not None and model is not None and model._graphics_device is not None and value.GraphicsDevice is not model._graphics_device:raise ValueError("Effect belongs to a different GraphicsDevice")
        self._effect=value
        owner=self._owner()
        if rebuild and owner is not None:owner._rebuild_effects()
    @property
    def Tag(self):self._check();return self._tag
    @Tag.setter
    def Tag(self,value):self._check();self._tag=value
    def _set_resources(self,vertex_buffer,index_buffer):
        self._vertex_buffer=vertex_buffer;self._index_buffer=index_buffer


class ModelMeshPartCollection(_Collection):pass


class ModelMesh:
    def __init__(self,name,parent_bone,parts=(),effects=(),sphere=None):
        if not isinstance(name,str):raise TypeError("name must be str")
        if parent_bone is not None and not isinstance(parent_bone,ModelBone):raise TypeError("parent_bone must be ModelBone or None")
        self._name=name;self._parent_bone=parent_bone;self._owner_ref=None;self._tag=None
        self._sphere=BoundingSphere(Vector3.Zero,0) if sphere is None else sphere.__copy__()
        self._parts=ModelMeshPartCollection(parts,self);self._effects=ModelEffectCollection((),self)
        for part in self._parts._values:part._owner_ref=weakref.ref(self)
        if effects:
            for part,effect in zip(self._parts._values,effects):part._assign_effect(effect,False)
        self._rebuild_effects()
    def _owner(self):return None if self._owner_ref is None else self._owner_ref()
    def _check(self):
        owner=self._owner()
        if owner is not None:owner._check()
    def _rebuild_effects(self):
        values=[]
        for part in self._parts._values:
            if part._effect is not None and all(part._effect is not value for value in values):values.append(part._effect)
        self._effects._values[:]=values
    @property
    def Name(self):self._check();return self._name
    @property
    def ParentBone(self):self._check();return self._parent_bone
    @property
    def BoundingSphere(self):self._check();return self._sphere.__copy__()
    @property
    def MeshParts(self):self._check();return self._parts
    @property
    def Effects(self):self._check();return self._effects
    @property
    def Tag(self):self._check();return self._tag
    @Tag.setter
    def Tag(self,value):self._check();self._tag=value
    def Draw(self):
        self._check()
        for part in self._parts:
            effect=part.Effect;vertex=part.VertexBuffer;indices=part.IndexBuffer
            if effect is None or vertex is None or indices is None:raise RuntimeError("ModelMeshPart is missing a buffer or Effect")
            device=effect.GraphicsDevice
            if vertex.GraphicsDevice is not device or indices.GraphicsDevice is not device:raise ValueError("ModelMeshPart resources belong to different GraphicsDevices")
            device.SetVertexBuffer(vertex);device.Indices=indices
            try:
                technique=effect.CurrentTechnique
                if technique is None:raise RuntimeError("ModelMeshPart Effect has no CurrentTechnique")
                for effect_pass in technique.Passes:
                    effect_pass.Apply()
                    device.DrawIndexedPrimitives(PrimitiveType.TriangleList,part.VertexOffset,0,part.NumVertices,part.StartIndex,part.PrimitiveCount)
            finally:
                device.SetVertexBuffer(None);device.Indices=None


class ModelMeshCollection(_Collection):
    def TryGetValue(self,meshName,value=None):
        try:return True,self[meshName]
        except KeyError:return False,None


ModelBoneCollection.__xna_arities__={"TryGetValue":{1}}
ModelMeshCollection.__xna_arities__={"TryGetValue":{1}}


class Model:
    def __init__(self,bones=(),meshes=(),tag=None,*,root_index=0,graphics_device=None):
        self._disposed=False;self._tag=tag;self._graphics_device=graphics_device
        self._bones=ModelBoneCollection(bones,self);self._meshes=ModelMeshCollection(meshes,self)
        for bone in self._bones._values:bone._owner_ref=weakref.ref(self);bone._children._owner_ref=weakref.ref(bone)
        for mesh in self._meshes._values:
            mesh._owner_ref=weakref.ref(self)
            for part in mesh._parts._values:part._owner_ref=weakref.ref(mesh)
            mesh._rebuild_effects()
        if self._bones._values:
            if root_index<0 or root_index>=len(self._bones._values):raise ValueError("root bone index is outside Bones")
            self._root=self._bones._values[root_index]
        else:self._root=None
    def _check(self):
        if self._disposed:raise RuntimeError("Model graph was invalidated by ContentManager.Unload")
    def _content_before_unload(self):
        if (self._graphics_device is not None and not self._graphics_device.IsDisposed and
                (self._graphics_device._vertex_bindings or self._graphics_device._index_buffer is not None)):
            self._graphics_device.SetVertexBuffer(None);self._graphics_device.Indices=None
    def _dispose(self):self._disposed=True
    def _content_fixups_complete(self):
        self._check()
        for mesh in self._meshes._values:
            for part in mesh._parts._values:
                if part._vertex_buffer is None:raise ValueError(f"Model mesh {mesh._name!r} has a part with no VertexBuffer")
                if part._index_buffer is None:raise ValueError(f"Model mesh {mesh._name!r} has a part with no IndexBuffer")
                if part._effect is None:raise ValueError(f"Model mesh {mesh._name!r} has a part with no Effect")
                for resource in (part._vertex_buffer,part._index_buffer,part._effect):
                    if resource.GraphicsDevice is not self._graphics_device:raise ValueError("Model shared resources belong to a different GraphicsDevice")
            mesh._rebuild_effects()
    @property
    def Root(self):self._check();return self._root
    @property
    def Bones(self):self._check();return self._bones
    @property
    def Meshes(self):self._check();return self._meshes
    @property
    def Tag(self):self._check();return self._tag
    @Tag.setter
    def Tag(self,value):self._check();self._tag=value
    def CopyBoneTransformsTo(self,destinationBoneTransforms):self._copy(destinationBoneTransforms,False)
    def CopyAbsoluteBoneTransformsTo(self,destinationBoneTransforms):self._copy(destinationBoneTransforms,True)
    def CopyBoneTransformsFrom(self,sourceBoneTransforms):
        self._check()
        if len(sourceBoneTransforms)<len(self._bones._values):raise ValueError("source array is too short")
        for bone,value in zip(self._bones._values,sourceBoneTransforms):bone.Transform=value
    def _copy(self,destination,absolute):
        self._check()
        if len(destination)<len(self._bones._values):raise ValueError("destination array is too short")
        calculated={}
        def transform(bone):
            if bone.Index in calculated:return calculated[bone.Index]
            parent=bone.Parent;value=bone.Transform if parent is None or not absolute else bone.Transform*transform(parent)
            calculated[bone.Index]=value;return value
        for bone in self._bones._values:destination[bone.Index]=transform(bone).__copy__()
    def Draw(self,world,view,projection):
        self._check()
        if not all(isinstance(value,Matrix) for value in (world,view,projection)):raise TypeError("Model.Draw matrices must be Matrix values")
        for mesh in self._meshes:
            for effect in mesh.Effects:
                if not isinstance(effect,IEffectMatrices):raise RuntimeError("Model.Draw requires each Effect to implement IEffectMatrices")
                effect.World=world;effect.View=view;effect.Projection=projection
            mesh.Draw()


class ModelBoneCollectionEnumerator(_Enum):pass
class ModelEffectCollectionEnumerator(_Enum):pass
class ModelMeshCollectionEnumerator(_Enum):pass
class ModelMeshPartCollectionEnumerator(_Enum):pass
ModelBoneCollection.GetEnumerator=lambda self:ModelBoneCollectionEnumerator(self._values)
ModelEffectCollection.GetEnumerator=lambda self:ModelEffectCollectionEnumerator(self._values)
ModelMeshCollection.GetEnumerator=lambda self:ModelMeshCollectionEnumerator(self._values)
ModelMeshPartCollection.GetEnumerator=lambda self:ModelMeshPartCollectionEnumerator(self._values)
