using Godot;
using MegaCrit.Sts2.Core.Nodes.Rooms;

namespace STS2_Things.Visuals;

/// <summary>
/// 原生 NCombatBackground 子类，仅为 Mod Godot 场景提供稳定的 C# ScriptPath。
/// 背景层的选择、预加载和挂载全部由 EncounterModel/BackgroundAssets 处理。
/// </summary>
[GlobalClass]
public partial class NThingsCombatBackground : NCombatBackground
{
}
