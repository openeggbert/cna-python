#!/usr/bin/env python3
"""Crash-isolated Effect, volume-texture, and Model/XNB ownership stress."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"));sys.path.insert(0,str(ROOT))

from _cna_native.errors import NativeError  # noqa: E402
from Microsoft.Xna.Framework import Color,Game,GraphicsDeviceManager,Matrix,Vector3  # noqa: E402
from Microsoft.Xna.Framework.Content import ResourceContentManager  # noqa: E402
from Microsoft.Xna.Framework.Graphics import (AlphaTestEffect,BasicEffect,CubeMapFace,
    DualTextureEffect,Effect,EffectParameterClass,EffectParameterType,
    EnvironmentMapEffect,Model,ModelBone,ModelMesh,ModelMeshPart,SkinnedEffect,
    SurfaceFormat,Texture3D,TextureCube)  # noqa: E402
from Microsoft.Xna.Framework.Graphics._effects import _create_native_parameter_for_tests  # noqa: E402
from tests.test_content_native import _compressed_model_xnb,_model_xnb  # noqa: E402


def main()->int:
    parser=argparse.ArgumentParser();parser.add_argument("--cycles",type=int,default=20);args=parser.parse_args()
    if args.cycles<20:parser.error("--cycles must be at least 20")
    counts={name:0 for name in ("EFFECT_BASE","EFFECT_CLONE","EFFECT_PARAMETER",
        "EFFECT_PARENT_CHILD","STOCK_EFFECT","MODEL_DIRECT_GRAPH","MODEL_XNB",
        "COMPRESSED_MODEL","MODEL_DRAW","MODEL_UNLOAD_RELOAD","TEXTURE3D_FAILED_CREATE",
        "TEXTURECUBE_FAILED_TRANSFER")}
    assets={"model":_model_xnb(),"compressed/model":_compressed_model_xnb()}

    class StressGame(Game):
        def __init__(self):
            super().__init__();self.graphics=GraphicsDeviceManager(self)
            previous=self.Content;self.Content=ResourceContentManager(self.Services,assets);previous.Dispose()
        def _effect_pass(self,effect):
            return None if effect.CurrentTechnique is None or not effect.CurrentTechnique.Passes.Count else effect.CurrentTechnique.Passes[0]
        def LoadContent(self):
            for _ in range(args.cycles):
                effect=Effect(self.GraphicsDevice);effect.OnApply();effect.Dispose();effect.Dispose();counts["EFFECT_BASE"]+=1
            for _ in range(args.cycles):
                original=BasicEffect(self.GraphicsDevice);original.Alpha=.75;clone=original.Clone()
                if clone._require_handle()==original._require_handle() or clone.Alpha!=original.Alpha:raise RuntimeError("Effect clone identity/state failed")
                clone.Alpha=.25;original.Dispose()
                if clone.Alpha!=.25:raise RuntimeError("disposing original invalidated clone")
                clone.Dispose();counts["EFFECT_CLONE"]+=1
            for _ in range(args.cycles):
                effect=Effect(self.GraphicsDevice);parameter=_create_native_parameter_for_tests(effect,"Value","STRESS",EffectParameterClass.Vector,EffectParameterType.Single,1,3)
                parameter.SetValue([Vector3(1,2,3),Vector3(4,5,6)])
                if parameter.GetValueVector3Array(2)!=[Vector3(1,2,3),Vector3(4,5,6)]:raise RuntimeError("Effect parameter round trip failed")
                effect.Dispose();counts["EFFECT_PARAMETER"]+=1
            for _ in range(args.cycles):
                effect=BasicEffect(self.GraphicsDevice);technique=effect.CurrentTechnique;passed=self._effect_pass(effect);light=effect.DirectionalLight0
                effect.Dispose()
                for operation in ((lambda:technique.Passes),(lambda:passed.Apply()),(lambda:light.Enabled)):
                    try:operation()
                    except RuntimeError:pass
                    else:raise RuntimeError("Effect child survived parent disposal")
                counts["EFFECT_PARENT_CHILD"]+=1
            for _ in range(args.cycles):
                effects=[BasicEffect(self.GraphicsDevice),AlphaTestEffect(self.GraphicsDevice),DualTextureEffect(self.GraphicsDevice),EnvironmentMapEffect(self.GraphicsDevice),SkinnedEffect(self.GraphicsDevice)]
                for effect in effects:
                    effect.World=Matrix.Identity;effect.OnApply();passed=self._effect_pass(effect)
                    if passed is not None:passed.Apply()
                for effect in reversed(effects):effect.Dispose()
                counts["STOCK_EFFECT"]+=1
            for _ in range(args.cycles):
                root=ModelBone("Root",0);child=ModelBone("Child",1);root._add_child(child);mesh=ModelMesh("Mesh",root,[ModelMeshPart()]);model=Model([root,child],[mesh]);retained=model.Meshes[0];model._dispose()
                try:_=retained.Name
                except RuntimeError:pass
                else:raise RuntimeError("direct Model child survived graph invalidation")
                counts["MODEL_DIRECT_GRAPH"]+=1
            for name,key in (("model","MODEL_XNB"),("compressed/model","COMPRESSED_MODEL")):
                for _ in range(args.cycles):
                    model=self.Content.Load(name);part=model.Meshes[0].MeshParts[0]
                    if part.Effect is not model.Meshes[0].MeshParts[1].Effect:raise RuntimeError("shared Effect identity diverged")
                    self.Content.Unload();counts[key]+=1
            for index in range(args.cycles):
                model=self.Content.Load("model" if index%2==0 else "compressed/model");model.Draw(Matrix.Identity,Matrix.Identity,Matrix.Identity);self.Content.Unload();counts["MODEL_DRAW"]+=1
            for _ in range(args.cycles):
                old=self.Content.Load("model");old_mesh=old.Meshes[0];self.Content.Unload();fresh=self.Content.Load("model")
                if fresh is old:raise RuntimeError("Content reload reused invalid Model")
                try:_=old_mesh.Name
                except RuntimeError:pass
                else:raise RuntimeError("retained ModelMesh survived Unload")
                self.Content.Unload();counts["MODEL_UNLOAD_RELOAD"]+=1
            for _ in range(args.cycles):
                try:Texture3D(self.GraphicsDevice,2,2,2,False,SurfaceFormat.Color)
                except NativeError as error:
                    if error.result!=6:raise
                else:raise RuntimeError("qualified HEADLESS unexpectedly created Texture3D")
                counts["TEXTURE3D_FAILED_CREATE"]+=1
            values=[Color.Red,Color.Green,Color.Blue,Color.White]
            for _ in range(args.cycles):
                cube=TextureCube(self.GraphicsDevice,2,False,SurfaceFormat.Color)
                try:
                    try:cube.SetData(CubeMapFace.PositiveX,values)
                    except NativeError as error:
                        if error.result!=6:raise
                    else:raise RuntimeError("qualified HEADLESS unexpectedly stored TextureCube data")
                finally:cube.Dispose()
                counts["TEXTURECUBE_FAILED_TRANSFER"]+=1
            self.Exit()

    game=StressGame()
    try:game.Run()
    finally:game.Dispose();game.Dispose()
    for name,value in counts.items():print(f"{name}_CYCLES={value}")
    print("NATIVE_CRASHES=0");print("OBSERVED_UAF=0");print("DOUBLE_FREE=0");print("SANITIZER_STATUS=NOT_RUN")
    return 0


if __name__=="__main__":raise SystemExit(main())
