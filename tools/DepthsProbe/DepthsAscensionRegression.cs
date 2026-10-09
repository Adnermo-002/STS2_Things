using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Unlocks;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;

public partial class DepthsProbeNode
{
    // Exercise the game's actual ProgressSaveManager after a native 1->Depths->Glory
    // standard run. No custom ascension writes or modified player save fixtures.
    private static void VerifyDepthsAscensionUnlock()
    {
        var saveManager = SaveManager.Instance;
        if (!saveManager.IsProfileInitialized)
            saveManager.InitProfileId(1); // Godot's isolated DepthsProbe user-data path.
        var originalProgress = saveManager.Progress;
        try
        {
            foreach (var (act, mode, ascension, previous, expected) in new[]
            {
                ("depths", GameMode.Standard, 0, 0, 1),
                ("depths", GameMode.Standard, 2, 2, 3),
                ("depths", GameMode.Standard, 2, 3, 3),
                ("hive", GameMode.Standard, 2, 2, 3),
                ("depths", GameMode.Custom, 2, 2, 2),
            })
            {
                // The caller already walked the real native RunManager from act 1
                // through Depths to Glory. Reuse its complete serializable run;
                // SetUpTest cannot be called twice without cleaning the game.
                var snapshot = RunManager.Instance.ToSave(null);
                if (act == "hive")
                    snapshot.Acts[1] = ModelDb.Act<Hive>().ToMutable().ToSave();
                snapshot.Ascension = ascension;
                Assert(snapshot.Acts.Count == 3 && snapshot.Acts[2].Id == ModelDb.Act<Glory>().Id
                    && snapshot.Acts[1].Id == (act == "depths" ? ModelDb.Act<STS2_Things.Acts.Depths>().Id : ModelDb.Act<Hive>().Id),
                    "Real run serialization keeps the alternate act in slot 2 and Glory in slot 3.");
                snapshot.GameMode = mode;
                saveManager.Progress = ProgressState.CreateDefault();
                var character = saveManager.Progress.GetOrCreateCharacterStats(ModelDb.Character<Ironclad>().Id);
                character.MaxAscension = previous;
                character.PreferredAscension = previous;
                saveManager.UpdateProgressWithRunData(snapshot, victory: true);
                Assert(character.MaxAscension == expected,
                    $"Native unlock must be {expected} for {act} {mode} ascension={ascension} previous={previous}, got {character.MaxAscension}");
                Assert(character.PreferredAscension == expected,
                    "Native preferred ascension matches progression result");
                // UpdateWithRunData already wrote progress.save; reload through the
                // original migration/validation path to detect a missing disk write.
                saveManager.InitProgressData();
                var loaded = saveManager.Progress.GetOrCreateCharacterStats(ModelDb.Character<Ironclad>().Id);
                Assert(loaded.MaxAscension == expected && loaded.PreferredAscension == expected,
                    "The unlocked ascension survives the real progress.save round trip");
                GD.Print($"ASCENSION REGRESSION {act} {mode} A{ascension}: {previous} -> {character.MaxAscension}");
            }
        }
        finally
        {
            saveManager.Progress = originalProgress;
        }
    }
}
