"""One-time scaffold from the repository's proven standalone native test host."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=ROOT/'tools/QuirkyHopperProbe'
for name in ['QuirkyHopperProbe.csproj','project.godot','main.tscn']:
    text=(source/name).read_text(encoding='utf-8-sig').replace('QuirkyHopper','LanternFish').replace('Quirky Hopper','Lantern Fish')
    (HERE/name.replace('QuirkyHopper','LanternFish')).write_text(text,encoding='utf-8')
text=(source/'QuirkyHopperProbeNode.cs').read_text(encoding='utf-8-sig')
start=text.index('    private static void InitializeModelDb()')
end=text.index('    private static void VerifyEncounterAndMoveContract()')
common=text[start:end].replace('QuirkyHopper','LanternFish')
other=(ROOT/'tools/CaveGodProbe/CaveGodProbeNode.cs').read_text(encoding='utf-8-sig')
begin=other.index('    private static void ActivateSyntheticCombat(')
end=other.index('    private static void EnsureRuntimeDependency(',begin)
common+=other[begin:end]
usings='using MegaCrit.Sts2.Core.Context;\n'+text[:text.index('public partial class')]
(HERE/'LanternFishFixture.cs').write_text(usings+'\npublic partial class LanternFishProbeNode : Node\n{\n'+common+'}\n',encoding='utf-8')
