using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Acts;
using MegaCrit.Sts2.Core.Models.Characters;
using MegaCrit.Sts2.Core.Multiplayer;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;

public partial class DepthsProbeNode
{
    // Test the actual game-end pipeline with a disk-backed save store,
    // scoped to a unique test directory, never a player's progress files.
    private static async Task VerifyActualDepthsVictorySave()
    {
        const string root = "user://depths_ascension_real_victory";
        bool oldModded = UserDataPathProvider.IsRunningModded;
        var isolated = new SaveManager(new GodotFileIo(root), forceSynchronous: true);
        SaveManager.MockInstanceForTesting(isolated);
        UserDataPathProvider.IsRunningModded = true;
        try
        {
            isolated.InitSettingsDataForTest();
            isolated.InitPrefsDataForTest();
            isolated.InitProfileId(1);
            isolated.Progress = ProgressState.CreateDefault();
            var stats = isolated.Progress.GetOrCreateCharacterStats(ModelDb.Character<Ironclad>().Id);
            stats.MaxAscension = 2;
            stats.PreferredAscension = 2;
            var run = CreateRun("actual-end-of-run-depths", players: 1, ascension: 2);
            RunManager.Instance.SetUpTest(run, new NetSingleplayerGameService(), shouldSave: true);
            RunManager.Instance.GenerateRooms();
            await RunManager.Instance.SetActInternal(0);
            await RunManager.Instance.SetActInternal(1);
            Assert(run.Act is STS2_Things.Acts.Depths, "Act 2 is Depths");
            await RunManager.Instance.SetActInternal(2);
            Assert(run.Act is Glory, "Act 3 remains vanilla Glory");
            MegaCrit.Sts2.Core.Context.LocalContext.NetId = run.Players[0].NetId;
            // A real playthrough already has current_run.save. Create it here so
            // finalization also exercises the real clean delete rather than
            // logging an expected missing-file error from the test fixture.
            await isolated.SaveRun(null);
            await isolated.SaveRun(null); // exercise normal on-disk .backup lifecycle

            // Original production method called by WinRun, including history
            // and save logic, rather than calling a bare ProgressSaveManager.
            var victory = RunManager.Instance.OnEnded(isVictory: true);
            Assert(victory.GameMode == GameMode.Standard && victory.Ascension == 2,
                "Real victory serialized as standard A2");
            Assert(victory.Acts[1].Id == ModelDb.Act<STS2_Things.Acts.Depths>().Id &&
                   victory.Acts[2].Id == ModelDb.Act<Glory>().Id,
                "Victory retained Depths and Glory IDs");
            Assert(RunManager.Instance.History?.Win == true, "History recorded an actual victory");
            Assert(isolated.Progress.GetOrCreateCharacterStats(ModelDb.Character<Ironclad>().Id).MaxAscension == 3,
                "Real end-of-run processing unlocks A3");

            const string modded = root + "/modded/profile1/saves/progress.save";
            const string vanilla = root + "/profile1/saves/progress.save";
            const string activeRun = root + "/modded/profile1/saves/current_run.save";
            Assert(Godot.FileAccess.FileExists(modded), "Modded progress.save written to disk");
            Assert(!Godot.FileAccess.FileExists(vanilla), "Vanilla progress file not overwritten");
            Assert(!Godot.FileAccess.FileExists(activeRun), "Completed current_run.save deleted");
            isolated.InitProgressData();
            var persisted = isolated.Progress.GetOrCreateCharacterStats(ModelDb.Character<Ironclad>().Id);
            Assert(persisted.MaxAscension == 3 && persisted.PreferredAscension == 3,
                "A3 persisted through modded disk save and reload");
            GD.Print("PASS actual Depths -> Glory, RunManager.OnEnded(true), modded progress.save A2->A3, vanilla isolation.");
        }
        finally
        {
            SaveManager.ClearInstanceForTesting();
            UserDataPathProvider.IsRunningModded = oldModded;
        }
    }
}
