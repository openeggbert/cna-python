from __future__ import annotations
import os
from pathlib import Path
import unittest

from _cna_native.errors import NativeError
from Microsoft.Xna.Framework import Color, Game, GraphicsDeviceManager, Matrix, Quaternion, Vector2, Vector3, Vector4
from Microsoft.Xna.Framework.Graphics import (AlphaTestEffect, BasicEffect, CompareFunction,
    DualTextureEffect, Effect, EffectParameterClass, EffectParameterType,
    EnvironmentMapEffect, CubeMapFace, Model, ModelBone, ModelBoneCollection, ModelMesh,
    ModelMeshPart, SkinnedEffect, SurfaceFormat, Texture2D, Texture3D, TextureCube)
from Microsoft.Xna.Framework.Graphics._effects import (_add_native_annotation_for_tests,
    _create_native_parameter_for_tests)

NATIVE = os.environ.get("CNA_NATIVE_LIBRARY")
COMPILED_EFFECT_FIXTURE=os.environ.get("CNA_PYTHON_COMPILED_EFFECT_FIXTURE")

@unittest.skipUnless(NATIVE and Path(NATIVE).is_file(), "CNA_NATIVE_LIBRARY is not configured")
class EffectNativeIdentityTests(unittest.TestCase):
    @unittest.skipUnless(COMPILED_EFFECT_FIXTURE and Path(COMPILED_EFFECT_FIXTURE).is_file(),"CNA_PYTHON_COMPILED_EFFECT_FIXTURE is not configured")
    def test_legal_compiled_effect_reaches_headless_backend_refusal(self):
        case=self;payload=Path(COMPILED_EFFECT_FIXTURE).read_bytes()
        class Probe(Game):
            def __init__(self):super().__init__();self.manager=GraphicsDeviceManager(self);self.checked=False
            def LoadContent(self):
                with case.assertRaises(NativeError) as caught:Effect(self.GraphicsDevice,payload)
                case.assertEqual(caught.exception.result,6);self.checked=True;self.Exit()
        game=Probe()
        try:game.Run()
        finally:game.Dispose()
        self.assertTrue(game.checked)

    def test_stock_effect_pass_identity_and_parent_invalidation(self):
        class Probe(Game):
            def __init__(self):
                super().__init__(); self.manager = GraphicsDeviceManager(self); self.cycles = 0
            def LoadContent(self):
                for _ in range(20):
                    effect = BasicEffect(self.GraphicsDevice)
                    effect.OnApply()
                    passed = None if effect.CurrentTechnique is None else (effect.CurrentTechnique.Passes[0] if effect.CurrentTechnique.Passes.Count else None)
                    if passed is not None: passed.Apply()
                    effect.Dispose()
                    if passed is not None:
                        try: passed.Apply()
                        except RuntimeError: pass
                        else: raise AssertionError("disposed parent left a live pass")
                    self.cycles += 1
                self.Exit()
        game=Probe()
        try:game.Run()
        finally:game.Dispose()
        self.assertEqual(game.cycles, 20)

    def test_every_stock_effect_property_family_and_apply_is_native(self):
        case=self
        class Probe(Game):
            def __init__(self):
                super().__init__();self.manager=GraphicsDeviceManager(self);self.checked=False
            def LoadContent(self):
                texture=Texture2D(self.GraphicsDevice,1,1)
                cube=TextureCube(self.GraphicsDevice,1,False,SurfaceFormat.Color)
                basic=BasicEffect(self.GraphicsDevice)
                basic.World=Matrix.CreateTranslation(1,2,3);basic.View=Matrix.CreateTranslation(4,5,6);basic.Projection=Matrix.CreateScale(2)
                case.assertEqual(basic.World,Matrix.CreateTranslation(1,2,3));case.assertEqual(basic.View,Matrix.CreateTranslation(4,5,6));case.assertEqual(basic.Projection,Matrix.CreateScale(2))
                basic.FogEnabled=True;basic.FogColor=Vector3(.1,.2,.3);basic.FogStart=2.0;basic.FogEnd=9.0
                case.assertTrue(basic.FogEnabled);case.assertEqual(basic.FogColor,Vector3(.1,.2,.3));case.assertEqual(basic.FogStart,2.0);case.assertEqual(basic.FogEnd,9.0)
                basic.LightingEnabled=True;basic.AmbientLightColor=Vector3(.2,.3,.4);basic.EnableDefaultLighting()
                light=basic.DirectionalLight0;case.assertIs(light,basic.DirectionalLight0);light.Enabled=True;light.Direction=Vector3(0,-1,0);light.DiffuseColor=Vector3(.5,.6,.7);light.SpecularColor=Vector3(.8,.9,1)
                case.assertTrue(light.Enabled);case.assertEqual(light.Direction,Vector3(0,-1,0));case.assertEqual(light.DiffuseColor,Vector3(.5,.6,.7));case.assertEqual(light.SpecularColor,Vector3(.8,.9,1))
                basic.DiffuseColor=Vector3(.3,.4,.5);basic.EmissiveColor=Vector3(.1,.2,.3);basic.SpecularColor=Vector3(.7,.8,.9);basic.SpecularPower=12;basic.Alpha=.75
                try:reflected_world=basic.Parameters["World"]
                except KeyError:reflected_world=None
                if reflected_world is not None:
                    case.assertEqual(reflected_world.GetValueMatrix(),basic.World);reflected_world.SetValue(Matrix.CreateScale(3));case.assertEqual(basic.World,Matrix.CreateScale(3))
                basic.TextureEnabled=True;basic.Texture=texture;basic.VertexColorEnabled=True;basic.PreferPerPixelLighting=True
                case.assertIs(basic.Texture,texture);case.assertTrue(basic.TextureEnabled);case.assertTrue(basic.VertexColorEnabled);case.assertTrue(basic.PreferPerPixelLighting)
                clone=BasicEffect(basic);case.assertNotEqual(clone._require_handle(),basic._require_handle());case.assertEqual(clone.World,basic.World);case.assertIs(clone.Texture,texture)
                clone.Alpha=.25;case.assertEqual(basic.Alpha,.75);case.assertEqual(clone.Alpha,.25)
                alpha=AlphaTestEffect(self.GraphicsDevice);alpha.DiffuseColor=Vector3(.2,.4,.6);alpha.Alpha=.5;alpha.Texture=texture;alpha.VertexColorEnabled=True;alpha.AlphaFunction=CompareFunction.Greater;alpha.ReferenceAlpha=123
                case.assertIs(alpha.Texture,texture);case.assertEqual(alpha.AlphaFunction,CompareFunction.Greater);case.assertEqual(alpha.ReferenceAlpha,123)
                dual=DualTextureEffect(self.GraphicsDevice);dual.DiffuseColor=Vector3(.4,.5,.6);dual.Alpha=.6;dual.Texture=texture;dual.Texture2=texture;dual.VertexColorEnabled=True
                case.assertIs(dual.Texture,texture);case.assertIs(dual.Texture2,texture);case.assertTrue(dual.VertexColorEnabled)
                environment=EnvironmentMapEffect(self.GraphicsDevice);environment.DiffuseColor=Vector3(.2,.3,.4);environment.EmissiveColor=Vector3(.1,.1,.1);environment.Alpha=.8;environment.Texture=texture;environment.EnvironmentMap=cube;environment.EnvironmentMapAmount=.7;environment.EnvironmentMapSpecular=Vector3(.6,.5,.4);environment.FresnelFactor=.3
                case.assertIs(environment.Texture,texture);case.assertIs(environment.EnvironmentMap,cube);case.assertAlmostEqual(environment.EnvironmentMapAmount,.7,places=6);case.assertEqual(environment.EnvironmentMapSpecular,Vector3(.6,.5,.4));case.assertAlmostEqual(environment.FresnelFactor,.3,places=6)
                skinned=SkinnedEffect(self.GraphicsDevice);skinned.DiffuseColor=Vector3(.1,.2,.3);skinned.EmissiveColor=Vector3(.2,.3,.4);skinned.SpecularColor=Vector3(.3,.4,.5);skinned.SpecularPower=16;skinned.Alpha=.9;skinned.PreferPerPixelLighting=True;skinned.Texture=texture;skinned.WeightsPerVertex=4
                bones=[Matrix.Identity,Matrix.CreateTranslation(1,0,0)];skinned.SetBoneTransforms(bones);case.assertEqual(skinned.GetBoneTransforms(2),bones)
                for effect in (basic,clone,alpha,dual,environment,skinned):
                    effect.OnApply()
                    if effect.CurrentTechnique is not None and effect.CurrentTechnique.Passes.Count:effect.CurrentTechnique.Passes[0].Apply()
                for effect in (skinned,environment,dual,alpha,clone,basic):effect.Dispose()
                cube.Dispose();texture.Dispose();self.checked=True;self.Exit()
        game=Probe()
        try:game.Run()
        finally:game.Dispose()
        self.assertTrue(game.checked)

    def test_native_parameter_and_annotation_codecs(self):
        case=self
        class Probe(Game):
            def __init__(self):
                super().__init__(); self.manager=GraphicsDeviceManager(self); self.checked=False
            def LoadContent(self):
                effect=Effect(self.GraphicsDevice)
                def parameter(name,kind,parameter_type,rows=1,columns=1):
                    return _create_native_parameter_for_tests(effect,name,"TEST",kind,parameter_type,rows,columns)
                boolean=parameter("Boolean",EffectParameterClass.Scalar,EffectParameterType.Bool)
                integer=parameter("Integer",EffectParameterClass.Scalar,EffectParameterType.Int32)
                single=parameter("Single",EffectParameterClass.Scalar,EffectParameterType.Single)
                vector2=parameter("Vector2",EffectParameterClass.Vector,EffectParameterType.Single,1,2)
                vector3=parameter("Vector3",EffectParameterClass.Vector,EffectParameterType.Single,1,3)
                vector4=parameter("Vector4",EffectParameterClass.Vector,EffectParameterType.Single,1,4)
                quaternion=parameter("Quaternion",EffectParameterClass.Vector,EffectParameterType.Single,1,4)
                matrix=parameter("Matrix",EffectParameterClass.Matrix,EffectParameterType.Single,4,4)
                string=parameter("String",EffectParameterClass.Object,EffectParameterType.String)
                case.assertIs(effect.Parameters["Boolean"],boolean);case.assertIs(effect.Parameters[0],boolean)
                case.assertIs(effect.Parameters.GetParameterBySemantic("TEST"),boolean)
                case.assertIs(boolean.Elements,boolean.Elements);case.assertIs(boolean.StructureMembers,boolean.StructureMembers)
                boolean.SetValue(True);integer.SetValue(-2147483648);single.SetValue(-0.0)
                vector2.SetValue(Vector2(1,2));vector3.SetValue(Vector3(3,4,5));vector4.SetValue(Vector4(6,7,8,9))
                expected_matrix=Matrix.CreateTranslation(10,20,30);matrix.SetValue(expected_matrix);string.SetValue("CNA π")
                case.assertTrue(boolean.GetValueBoolean());case.assertEqual(integer.GetValueInt32(),-2147483648)
                case.assertEqual(single.GetValueSingle(),-0.0);case.assertEqual(vector2.GetValueVector2(),Vector2(1,2))
                case.assertEqual(vector3.GetValueVector3(),Vector3(3,4,5));case.assertEqual(vector4.GetValueVector4(),Vector4(6,7,8,9))
                case.assertEqual(matrix.GetValueMatrix(),expected_matrix);case.assertEqual(string.GetValueString(),"CNA π")
                boolean.SetValue([True,False,True]);case.assertEqual(boolean.GetValueBooleanArray(3),[True,False,True])
                integer.SetValue([-2,0,7]);case.assertEqual(integer.GetValueInt32Array(3),[-2,0,7])
                single.SetValue([1.25,-2.5,3.75]);case.assertEqual(single.GetValueSingleArray(3),[1.25,-2.5,3.75])
                vector2.SetValue([Vector2(1,2),Vector2(3,4)]);case.assertEqual(vector2.GetValueVector2Array(2),[Vector2(1,2),Vector2(3,4)])
                vector3.SetValue([Vector3(1,2,3),Vector3(4,5,6)]);case.assertEqual(vector3.GetValueVector3Array(2),[Vector3(1,2,3),Vector3(4,5,6)])
                vector4.SetValue([Vector4(1,2,3,4),Vector4(5,6,7,8)]);case.assertEqual(vector4.GetValueVector4Array(2),[Vector4(1,2,3,4),Vector4(5,6,7,8)])
                quaternions=[Quaternion.Identity,Quaternion(1,2,3,4)];quaternion.SetValue(quaternions);case.assertEqual(quaternion.GetValueQuaternionArray(2),quaternions)
                quaternion.SetValue(Quaternion(2,3,4,5));case.assertEqual(quaternion.GetValueQuaternion(),Quaternion(2,3,4,5))
                matrices=[expected_matrix,Matrix.Identity];matrix.SetValue(matrices);case.assertEqual(matrix.GetValueMatrixArray(2),matrices)
                matrix.SetValueTranspose(expected_matrix);case.assertEqual(matrix.GetValueMatrixTranspose(),expected_matrix)
                matrix.SetValueTranspose(matrices);case.assertEqual(matrix.GetValueMatrixTransposeArray(2),matrices)
                texture2d=Texture2D(self.GraphicsDevice,1,1);cube=TextureCube(self.GraphicsDevice,1,False,SurfaceFormat.Color)
                texture_parameter=parameter("Texture2D",EffectParameterClass.Object,EffectParameterType.Texture2D)
                cube_parameter=parameter("TextureCube",EffectParameterClass.Object,EffectParameterType.TextureCube)
                volume_parameter=parameter("Texture3D",EffectParameterClass.Object,EffectParameterType.Texture3D)
                texture_parameter.SetValue(texture2d);cube_parameter.SetValue(cube)
                case.assertIs(texture_parameter.GetValueTexture2D(),texture2d);case.assertIs(cube_parameter.GetValueTextureCube(),cube);case.assertIsNone(volume_parameter.GetValueTexture3D())
                with case.assertRaises(TypeError):integer.GetValueSingle()
                with case.assertRaises(TypeError):vector3.SetValue(Vector2.One)
                case.assertEqual(vector3.GetValueVector3Array(1),[Vector3(1,2,3)])
                with case.assertRaises(ValueError):single.SetValue([])
                integer.SetValue(17);case.assertEqual(integer.GetValueInt32(),17)
                _add_native_annotation_for_tests(single,"Scalar","A",EffectParameterClass.Scalar,EffectParameterType.Single,[2.5])
                _add_native_annotation_for_tests(single,"Boolean","AB",EffectParameterClass.Scalar,EffectParameterType.Bool,[1])
                _add_native_annotation_for_tests(single,"Integer","AI",EffectParameterClass.Scalar,EffectParameterType.Int32,[7])
                _add_native_annotation_for_tests(single,"Vector2","A2",EffectParameterClass.Vector,EffectParameterType.Single,[1,2])
                _add_native_annotation_for_tests(single,"Vector","B",EffectParameterClass.Vector,EffectParameterType.Single,[1,2,3])
                _add_native_annotation_for_tests(single,"Vector4","A4",EffectParameterClass.Vector,EffectParameterType.Single,[1,2,3,4])
                _add_native_annotation_for_tests(single,"Matrix","AM",EffectParameterClass.Matrix,EffectParameterType.Single,tuple(Matrix.Identity))
                _add_native_annotation_for_tests(single,"Text","C",EffectParameterClass.Object,EffectParameterType.String,string="hello")
                annotations=single.Annotations;case.assertIs(annotations[0],annotations[0]);case.assertEqual(annotations[0].GetValueSingle(),2.5)
                case.assertTrue(annotations[1].GetValueBoolean());case.assertEqual(annotations[2].GetValueInt32(),7);case.assertEqual(annotations[3].GetValueVector2(),Vector2(1,2))
                case.assertEqual(annotations[4].GetValueVector3(),Vector3(1,2,3));case.assertEqual(annotations[5].GetValueVector4(),Vector4(1,2,3,4));case.assertEqual(annotations[6].GetValueMatrix(),Matrix.Identity);case.assertEqual(annotations[7].GetValueString(),"hello")
                with case.assertRaises(TypeError):annotations[0].GetValueInt32()
                retained=annotations[0];effect.Dispose();texture2d.Dispose();cube.Dispose()
                with case.assertRaises(RuntimeError):retained.GetValueSingle()
                self.checked=True;self.Exit()
        game=Probe()
        try:game.Run()
        finally:game.Dispose()
        self.assertTrue(game.checked)

    def test_volume_texture_routes_are_native_or_structured_backend_blocked(self):
        case=self
        class Probe(Game):
            def __init__(self):
                super().__init__();self.manager=GraphicsDeviceManager(self);self.status={}
            def LoadContent(self):
                try:
                    texture=Texture3D(self.GraphicsDevice,2,2,2,False,SurfaceFormat.Color)
                except NativeError as error:
                    case.assertEqual(error.result,6);self.status["Texture3D"]="BACKEND_BLOCKED"
                    for _ in range(19):
                        with case.assertRaises(NativeError) as caught:Texture3D(self.GraphicsDevice,2,2,2,False,SurfaceFormat.Color)
                        case.assertEqual(caught.exception.result,6)
                else:
                    values=[Color(index,index+1,index+2,255) for index in range(8)]
                    try:texture.SetData(values);output=[Color.Transparent for _ in range(8)];texture.GetData(output);case.assertEqual(output,values);self.status["Texture3D"]="VERIFIED_NATIVE"
                    except NativeError as error:case.assertEqual(error.result,6);self.status["Texture3D"]="TRANSFER_BACKEND_BLOCKED"
                    finally:texture.Dispose()
                try:
                    cube=TextureCube(self.GraphicsDevice,2,False,SurfaceFormat.Color)
                except NativeError as error:
                    case.assertEqual(error.result,6);self.status["TextureCube"]="BACKEND_BLOCKED"
                else:
                    values=[Color.Red,Color.Green,Color.Blue,Color.White]
                    try:
                        for face in CubeMapFace:
                            cube.SetData(face,values);output=[Color.Transparent for _ in range(4)];cube.GetData(face,output);case.assertEqual(output,values)
                        self.status["TextureCube"]="VERIFIED_NATIVE"
                    except NativeError as error:
                        case.assertEqual(error.result,6);self.status["TextureCube"]="TRANSFER_BACKEND_BLOCKED"
                        for _ in range(19):
                            other=TextureCube(self.GraphicsDevice,2,False,SurfaceFormat.Color)
                            try:
                                with case.assertRaises(NativeError) as caught:other.SetData(CubeMapFace.PositiveX,values)
                                case.assertEqual(caught.exception.result,6)
                            finally:other.Dispose()
                    finally:cube.Dispose()
                self.Exit()
        game=Probe()
        try:game.Run()
        finally:game.Dispose()
        self.assertIn(game.status["Texture3D"],("BACKEND_BLOCKED","TRANSFER_BACKEND_BLOCKED","VERIFIED_NATIVE"))
        self.assertIn(game.status["TextureCube"],("BACKEND_BLOCKED","TRANSFER_BACKEND_BLOCKED","VERIFIED_NATIVE"))

class ModelGraphTests(unittest.TestCase):
    def test_bones_meshes_parts_and_copy_isolation(self):
        root = ModelBone("Root", 0)
        child = ModelBone("Child", 1)
        child._parent = root
        root._children = ModelBoneCollection([child], root)
        mesh = ModelMesh("Mesh", root, [ModelMeshPart()])
        model = Model([root, child], [mesh])
        self.assertIs(model.Root, root)
        self.assertIs(model.Meshes["Mesh"], mesh)
        self.assertIs(mesh.MeshParts[0].Effect, None)
        values = [Matrix.Identity, Matrix.CreateTranslation(1, 2, 3)]
        model.CopyBoneTransformsFrom(values)
        out = [Matrix.Identity, Matrix.Identity]
        model.CopyBoneTransformsTo(out)
        self.assertEqual(out[1], values[1])
        out[1].M41 = 99
        self.assertNotEqual(out[1], model.Bones[1].Transform)
