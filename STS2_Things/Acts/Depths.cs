using Godot;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Encounters;
using MegaCrit.Sts2.Core.Random;
using MegaCrit.Sts2.Core.Unlocks;
using STS2_Things.Encounters;
using STS2_Things.Hooks;

namespace STS2_Things.Acts;

/// <summary>A complete alternate second act, selected and saved through native ActModel rules.</summary>
public sealed class Depths : ActModel
{
    public override int Index => 1;
    public override bool IsDefault => false;
    public override bool IsUnlocked(UnlockState unlockState) => true;
    protected override int NumberOfWeakEncounters => 2;
    protected override int BaseNumberOfRooms => 14;

    public override Color MapTraveledColor => new("233F4A");
    public override Color MapUntraveledColor => new("506E7C");
    public override Color MapBgColor => new("A6B9BF");
    public override string[] BgMusicOptions => ModelDb.Act<Hive>().BgMusicOptions;
    public override string[] MusicBankPaths => ModelDb.Act<Hive>().MusicBankPaths;
    public override string AmbientSfx => ModelDb.Act<Hive>().AmbientSfx;
    public override string ChestOpenSfx => ModelDb.Act<Hive>().ChestOpenSfx;
    public override string ChestSpineResourcePath => ModelDb.Act<Hive>().ChestSpineResourcePath;
    public override string ChestSpineSkinNameNormal => ModelDb.Act<Hive>().ChestSpineSkinNameNormal;
    public override string ChestSpineSkinNameStroke => ModelDb.Act<Hive>().ChestSpineSkinNameStroke;

    // Keep the established Act 2 ancient rules, but only mod-authored regular events.
    public override IEnumerable<AncientEventModel> AllAncients => ModelDb.Act<Hive>().AllAncients;
    public override IEnumerable<EventModel> AllEvents =>
        ThingsEventCatalog.AddDepthsEvents(ModelDb.Act<Hive>().AllEvents
            .Where(e => e.GetType().Assembly != typeof(ActModel).Assembly));
    public override IEnumerable<AncientEventModel> GetUnlockedAncients(UnlockState state) =>
        ModelDb.Act<Hive>().GetUnlockedAncients(state);
    public override MapPointTypeCounts GetMapPointTypes(Rng mapRng) => ModelDb.Act<Hive>().GetMapPointTypes(mapRng);
    protected override void ApplyActDiscoveryOrderModifications(UnlockState unlockState) { }

    public override IEnumerable<EncounterModel> BossDiscoveryOrder => AllBossEncounters;

    public override IEnumerable<EncounterModel> GenerateAllEncounters()
    {
        yield return ModelDb.Encounter<LanternFishWeak>();
        yield return ModelDb.Encounter<LanternFishEncounter>();
        yield return ModelDb.Encounter<SanguineLeechWeak>();
        yield return ModelDb.Encounter<SanguineLeechEncounter>();
        yield return ModelDb.Encounter<SpongeLeechWeak>();
        yield return ModelDb.Encounter<SpongeLeechEncounter>();
        yield return ModelDb.Encounter<SilkMothWeak>();
        yield return ModelDb.Encounter<SilkMothEncounter>();
        yield return ModelDb.Encounter<CaveMawWeak>();
        yield return ModelDb.Encounter<FleetingEchoWeak>();
        yield return ModelDb.Encounter<CaveMawEncounter>();
        yield return ModelDb.Encounter<SnailTrioWeak>();
        yield return ModelDb.Encounter<HumanFaceColumnEncounter>();
        // Independent entries diversify the native bag; variants inside the column
        // encounter alone cannot dilute the leeches in the other regular fights.
        yield return ModelDb.Encounter<LanternSpongeEncounter>();
        yield return ModelDb.Encounter<SilkSnailEncounter>();
        yield return ModelDb.Encounter<CaveMawSnailEncounter>();
        yield return ModelDb.Encounter<SpongeSnailEncounter>();
        yield return ModelDb.Encounter<LanternMothEncounter>();
        yield return ModelDb.Encounter<CaveMawLanternEncounter>();
        yield return ModelDb.Encounter<DecimillipedeElite>();
        yield return ModelDb.Encounter<EntomancerElite>();
        yield return ModelDb.Encounter<InfestedPrismsElite>();
        yield return ModelDb.Encounter<MycorrhizalTwinsElite>();
        yield return ModelDb.Encounter<ReverseSalamanderElite>();
        yield return ModelDb.Encounter<RadioJellyfishElite>();

        // The shared enabled/weight settings apply in both Hive and Depths.
        // A deliberately disabled Cave God must not leave room generation without a boss.
        EncounterModel caveGod = ModelDb.Encounter<CaveGodBossEncounter>();
        yield return EncounterSelectionPolicy.IsAvailable(caveGod)
            ? caveGod : ModelDb.Encounter<KaiserCrabBoss>();
    }
}
