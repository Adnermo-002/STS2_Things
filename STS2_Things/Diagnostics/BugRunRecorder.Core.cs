using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Saves;

namespace STS2_Things.Diagnostics;

/// <summary>Main-thread read-only journal. Only explicit F2 submissions perform network I/O.</summary>
internal static class BugRunRecorder
{
    private static readonly System.Net.Http.HttpClient Client = new() { Timeout = TimeSpan.FromSeconds(18) };
    private static readonly Uri Endpoint = new("https://reports.adnermo.online/api/reports");
    private static BugReportStore? _store;
    private static BugReportOutbox? _outbox;
    private static RunState? _run;
    private static ActionExecutor? _executor;
    private static readonly HashSet<GameAction> TrackedActions = [];
    private static bool _ready;
    private static long _lastErrorPoll;
    private static GameAction? _reportedErrorAction;
    internal static ReportSubmission? LastSubmission { get; private set; }
    private static string DataDir => Path.Combine(OS.GetUserDataDir(), "mod_data", "STS2_Things", "bug_reports");
    private static BugReportStore Store => _store ??= new(DataDir);
    private static BugReportOutbox Outbox => _outbox ??= new(DataDir, Client, ReportEndpoint());

    private static Uri ReportEndpoint()
    {
        string? value = System.Environment.GetEnvironmentVariable("STS2_THINGS_REPORT_TEST_URL");
        if (OS.GetUserDataDir().Contains("ReportTest", StringComparison.OrdinalIgnoreCase)
            && Uri.TryCreate(value, UriKind.Absolute, out var uri) && uri.Scheme == "http" && uri.Host == "127.0.0.1") return uri;
        return Endpoint;
    }

    internal static void Initialize()
    {
        if (_ready) return;
        RunManager.Instance.RunStarted += OnStarted;
        RunManager.Instance.RoomEntered += () => Track("room_entered", persist: true);
#if STS2_V111
        CombatManager.Instance.CombatBegan += _ => Track("combat_started", persist: true);
#endif
        CombatManager.Instance.TurnStarted += _ => Track("turn_started", persist: true);
        CombatManager.Instance.CombatEnded += _ => Track("combat_ended", persist: true);
        if (Engine.GetMainLoop() is SceneTree tree) tree.ProcessFrame += PollFailedAction;
        _ready = true;
        var current = RunManager.Instance.DebugOnlyGetState();
        if (current is not null) OnStarted(current);
        Log.Info("[Things BugReport] Local journal enabled. Explicit F2 submissions only.");
    }

    private static string RunKey(RunState run)
    {
        long started = (long)(AccessTools.Field(typeof(RunManager), "_startTime").GetValue(RunManager.Instance) ?? 0L);
        int profile;
        try { profile = SaveManager.Instance.CurrentProfileId; } catch (InvalidOperationException) { profile = 0; }
        string input = profile + "|" + started + "|" + run.Rng.StringSeed + "|" + run.GameMode + "|" + run.AscensionLevel
            + "|" + string.Join(',', run.Players.Select(p => p.Character.Id.ToString()));
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(input)));
    }

    private static void OnStarted(RunState run)
    {
        try
        {
            if (ReferenceEquals(_run, run)) return;
            if (_run is not null) Store.Archive(); // Pure frozen serialization; no live state reads.
            DetachExecutor();
            _reportedErrorAction = null;
            var metadata = BugSnapshot.Object(new {
                game_version = GameVersion(),
                mod_version = typeof(BugRunRecorder).Assembly.GetName().Version?.ToString() ?? "unknown",
                active_mods = ModManager.GetLoadedMods().Select(m => new {
                    id = m.manifest?.id ?? "unknown", version = m.version?.ToString() ?? "unknown"
                }).ToArray()
            });
            bool resumed = Store.Begin(RunKey(run), metadata, BugSnapshot.Capture(run));
            _run = run;
            _executor = RunManager.Instance.ActionExecutor;
            if (_executor is not null)
            {
                _executor.BeforeActionExecuted += BeforeAction;
                _executor.AfterActionExecuted += AfterAction;
            }
            Track(resumed ? "run_resumed" : "run_first_observed", persist: true);
        }
        catch (Exception ex) { Log.Warn("[Things BugReport] Start journal: " + ex.GetType().Name); }
    }

    private static string GameVersion()
    {
        try { return MegaCrit.Sts2.Core.Debug.ReleaseInfoManager.Instance.ReleaseInfo?.Version ?? "unknown"; }
        catch (Exception) { return "unknown"; }
    }

    private static void DetachExecutor()
    {
        if (_executor is not null)
        {
            _executor.BeforeActionExecuted -= BeforeAction;
            _executor.AfterActionExecuted -= AfterAction;
        }
        foreach (var action in TrackedActions) DetachAction(action);
        TrackedActions.Clear(); _executor = null;
    }

    private static void DetachAction(GameAction action)
    {
        action.BeforePausedForPlayerChoice -= BeforeChoice;
        action.BeforeResumedAfterPlayerChoice -= AfterChoice;
        action.BeforeCancelled -= Cancelled;
    }

    private static JsonObject ActionRecord(GameAction action) => BugSnapshot.Object(new {
        action_id = action.Id, action_type = action.GetType().Name, action_state = action.State.ToString(),
        card = action is PlayCardAction card ? card.CardModelId.ToString() : null,
        target = action is PlayCardAction targetCard ? targetCard.TargetId : action is UsePotionAction potion ? potion.TargetId : null,
        potion_slot = action is UsePotionAction use ? (int?)use.PotionIndex : null,
        player_index = _run?.Players.ToList().FindIndex(p => p.NetId == action.OwnerId), error = BugSnapshot.Error(action.Exception)
    });

    private static void BeforeAction(GameAction action)
    {
        if (TrackedActions.Add(action))
        {
            action.BeforePausedForPlayerChoice += BeforeChoice;
            action.BeforeResumedAfterPlayerChoice += AfterChoice;
            action.BeforeCancelled += Cancelled;
        }
        Track("action_started", ActionRecord(action), persist: true);
    }
    private static void BeforeChoice(GameAction action) => Track("action_waiting_for_choice", ActionRecord(action), persist: true);
    private static void AfterChoice(GameAction action) => Track("action_resumed", ActionRecord(action), persist: true);
    private static void Cancelled(GameAction action)
    {
        Track("action_cancelled", ActionRecord(action), persist: true);
        DetachAction(action); TrackedActions.Remove(action);
    }
    private static void AfterAction(GameAction action)
    {
        Track("action_completed", ActionRecord(action), persist: true);
        DetachAction(action); TrackedActions.Remove(action);
    }

    private static void PollFailedAction()
    {
        if (System.Environment.TickCount64 - _lastErrorPoll < 1000) return;
        _lastErrorPoll = System.Environment.TickCount64;
        if (RunManager.Instance.DebugOnlyGetState() is null && _run is not null)
        {
            try { Store.Archive(); } catch (IOException) { }
            DetachExecutor(); _run = null; return;
        }
        var action = _executor?.CurrentlyRunningAction;
        if (action?.Exception is not null && !ReferenceEquals(action, _reportedErrorAction))
        {
            _reportedErrorAction = action; Track("action_failed", ActionRecord(action), persist: true);
        }
    }

    private static void Track(string kind, JsonObject? detail = null, bool persist = false)
    {
        try
        {
            var run = RunManager.Instance.DebugOnlyGetState();
            if (run is null) return;
            if (!ReferenceEquals(_run, run)) OnStarted(run);
            if (!ReferenceEquals(_run, run)) return;
            Store.Track(new JsonObject {
                ["at"] = DateTimeOffset.UtcNow.ToString("O"), ["kind"] = kind, ["detail"] = detail?.DeepClone(),
                ["act_index"] = run.CurrentActIndex, ["floor"] = run.ActFloor, ["room"] = run.CurrentRoom?.GetType().Name
            });
            Store.Update(BugSnapshot.Capture(run, TrackedActions.LastOrDefault()));
            if (persist) Store.Persist();
        }
        catch (Exception ex) { Log.Warn("[Things BugReport] Journal event: " + ex.GetType().Name); }
    }

    internal static async Task<bool> SubmitAsync(string description, bool retryPending = false)
    {
        try
        {
            var outbox = Outbox;
            string? report = null;
            if (!retryPending)
            {
                string text = description.Trim();
                if (text.Length < 2) { LastSubmission = new(false, null, "description_too_short", outbox.PendingCount); return false; }
                Track("report_requested", persist: true);
                report = outbox.Enqueue(Store.JournalForUpload(), text);
            }
            LastSubmission = await outbox.SendAsync(report).ConfigureAwait(false);
            return LastSubmission.Success;
        }
        catch (Exception ex)
        {
            LastSubmission = new(false, null, "local_storage_error", _outbox?.PendingCount ?? 0);
            Log.Warn("[Things BugReport] Submission retained locally: " + ex.GetType().Name); return false;
        }
    }
}
