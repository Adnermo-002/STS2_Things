using System.Net.Http;
using System.Text;
using System.Text.Json.Nodes;

namespace STS2_Things.Diagnostics;

/// <summary>Immutable JSON snapshots and durable files; never queries live game state.</summary>
internal sealed class BugReportStore(string directory)
{
    internal const int MaxEvents = 700;
    internal string DirectoryPath { get; } = directory;
    internal JsonObject? Current { get; private set; }
    private string CurrentPath => Path.Combine(DirectoryPath, "current-run.json");

    internal static void WriteAtomic(string path, string value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        string temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temporary, value, new UTF8Encoding(false));
            if (File.Exists(path))
            {
                // A torn/corrupt primary must not overwrite the good recovery copy.
                bool valid;
                try { valid = JsonNode.Parse(File.ReadAllText(path, Encoding.UTF8)) is not null; }
                catch (System.Text.Json.JsonException) { valid = false; }
                if (valid) File.Copy(path, path + ".backup", true);
            }
            File.Move(temporary, path, true);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    internal static JsonObject? ReadObject(string path)
    {
        foreach (string candidate in new[] { path, path + ".backup" })
        {
            if (!File.Exists(candidate)) continue;
            try { return JsonNode.Parse(File.ReadAllText(candidate, Encoding.UTF8)) as JsonObject; }
            catch (System.Text.Json.JsonException) { }
        }
        return null;
    }

    internal bool Begin(string runKey, JsonObject metadata, JsonObject snapshot)
    {
        if (Current?["local_run_key"]?.GetValue<string>() == runKey) return true;
        // Capture/serialize is deliberately pure. Archiving cannot initialize another run.
        if (Current is not null) Archive();
        JsonObject? disk = ReadObject(CurrentPath);
        bool restored = disk?["local_run_key"]?.GetValue<string>() == runKey;
        if (restored)
            Current = disk;
        else
        {
            if (disk is not null) WriteAtomic(Path.Combine(DirectoryPath, "last-run.json"), disk.ToJsonString());
            Current = new JsonObject {
                ["schema"] = 2, ["client_run_id"] = Guid.NewGuid().ToString("N"),
                ["local_run_key"] = runKey, ["started_at"] = DateTimeOffset.UtcNow.ToString("O"),
                ["events"] = new JsonArray(), ["initial_state"] = snapshot.DeepClone(),
                ["initial_state_kind"] = "first_observed", ["state"] = snapshot.DeepClone(), ["dropped_events"] = 0
            };
        }
        foreach (var item in metadata) Current![item.Key] = item.Value?.DeepClone();
        Update(snapshot);
        return restored;
    }

    internal void Update(JsonObject snapshot)
    {
        if (Current is null) return;
        Current["state"] = snapshot.DeepClone();
        Current["updated_at"] = DateTimeOffset.UtcNow.ToString("O");
    }

    internal void Track(JsonObject record)
    {
        if (Current is null) return;
        var events = Current["events"] as JsonArray ?? new JsonArray();
        Current["events"] = events;
        events.Add(record.DeepClone());
        while (events.Count > MaxEvents)
        {
            events.RemoveAt(0);
            Current["dropped_events"] = (Current["dropped_events"]?.GetValue<int>() ?? 0) + 1;
        }
    }

    internal void Persist()
    {
        if (Current is not null) WriteAtomic(CurrentPath, Current.ToJsonString());
    }

    internal void Archive()
    {
        if (Current is null) return;
        Persist();
        WriteAtomic(Path.Combine(DirectoryPath, "last-run.json"), Current.ToJsonString());
    }

    internal JsonObject JournalForUpload()
    {
        var journal = (JsonObject)(Current?.DeepClone() ?? ReadObject(CurrentPath)
            ?? ReadObject(Path.Combine(DirectoryPath, "last-run.json"))
            ?? new JsonObject { ["schema"] = 2, ["events"] = new JsonArray(), ["state"] = null });
        journal.Remove("local_run_key");
        return journal;
    }
}

internal sealed record ReportSubmission(bool Success, string? ReportId, string Reason, int Pending);

/// <summary>Each explicit submission has an independent, immutable retry body and ID.</summary>
internal sealed class BugReportOutbox(string directory, HttpClient client, Uri endpoint)
{
    internal const int MaxBytes = 300_000;
    private readonly SemaphoreSlim _sending = new(1);
    private string PendingDir => Path.Combine(directory, "pending");
    internal int PendingCount => Directory.Exists(PendingDir) ? Directory.GetFiles(PendingDir, "*.json").Length : 0;

    internal string Enqueue(JsonObject journal, string description)
    {
        string normalized = description.Trim()[..Math.Min(4000, description.Trim().Length)];
        if (Directory.Exists(PendingDir))
            foreach (string file in Directory.GetFiles(PendingDir, "*.json"))
            {
                var prior = ReadPending(file);
                if (prior?["description"]?.GetValue<string>() == normalized
                    && prior["run"]?["client_run_id"]?.GetValue<string>() == journal["client_run_id"]?.GetValue<string>())
                    return prior["client_report_id"]!.GetValue<string>();
            }
        string id = Guid.NewGuid().ToString("N");
        var payload = new JsonObject {
            ["schema"] = 2, ["source"] = "sts2_things", ["client_report_id"] = id,
            ["reported_at"] = DateTimeOffset.UtcNow.ToString("O"), ["description"] = description.Trim(),
            ["run"] = journal.DeepClone()
        };
        string complete = payload.ToJsonString();
        // Always preserve the full description/evidence before applying wire-size limits.
        BugReportStore.WriteAtomic(Path.Combine(directory, "reports", id + ".json"), complete);
        payload["description"] = normalized;
        if (description.Trim().Length > 4000) payload["description_truncated"] = true;
        Reduce(payload);
        BugReportStore.WriteAtomic(Path.Combine(PendingDir, id + ".json"), payload.ToJsonString());
        return id;
    }

    private static JsonObject? ReadPending(string path)
    {
        try { return BugReportStore.ReadObject(path); }
        catch (InvalidOperationException) { return null; }
    }

    private static void Reduce(JsonObject payload)
    {
        if (Encoding.UTF8.GetByteCount(payload.ToJsonString()) <= MaxBytes) return;
        var run = (JsonObject)payload["run"]!;
        var changes = new JsonArray();
        run["upload_truncation"] = changes;
        if (run["initial_state"] is JsonObject initial)
        {
            initial.Remove("route"); initial.Remove("ui");
            changes.Add("initial_state.route/ui");
        }
        var events = run["events"] as JsonArray;
        while (Encoding.UTF8.GetByteCount(payload.ToJsonString()) > MaxBytes && events?.Count > 100)
        {
            events.RemoveAt(0);
            run["dropped_events"] = (run["dropped_events"]?.GetValue<int>() ?? 0) + 1;
        }
        changes.Add("oldest events if needed");
        if (Encoding.UTF8.GetByteCount(payload.ToJsonString()) <= MaxBytes) return;
        if (run["state"] is JsonObject state && state["route"] is JsonArray route)
        {
            foreach (var act in route.OfType<JsonObject>())
            {
                if (act["points"] is JsonArray points)
                    while (points.Count > 15) points.RemoveAt(0);
            }
            changes.Add("oldest route points");
        }
        if (Encoding.UTF8.GetByteCount(payload.ToJsonString()) > MaxBytes)
        {
            run.Remove("initial_state");
            if (run["state"] is JsonObject lastState) lastState.Remove("route");
            changes.Add("initial_state/full route retained in local reports file");
        }
    }

    internal async Task<ReportSubmission> SendAsync(string? requestedId = null)
    {
        await _sending.WaitAsync().ConfigureAwait(false);
        try
        {
            Directory.CreateDirectory(PendingDir);
            Directory.CreateDirectory(Path.Combine(directory, "reports"));
            // Migration keeps the previous version's unsent report instead of overwriting it.
            string legacy = Path.Combine(directory, "pending-report.json");
            var old = BugReportStore.ReadObject(legacy);
            string? oldId = old?["client_report_id"]?.GetValue<string>();
            if (oldId is not null && System.Text.RegularExpressions.Regex.IsMatch(oldId, "^[a-fA-F0-9]{32}$"))
            {
                string target = Path.Combine(PendingDir, oldId + ".json");
                if (!File.Exists(target)) BugReportStore.WriteAtomic(target, old!.ToJsonString());
                File.Move(legacy, legacy + ".migrated", true);
            }
            var files = Directory.GetFiles(PendingDir, "*.json").OrderBy(File.GetCreationTimeUtc).ToArray();
            if (requestedId is not null) files = files.Where(p => Path.GetFileNameWithoutExtension(p) == requestedId).ToArray();
            if (files.Length == 0) return new(true, null, "nothing_pending", PendingCount);
            ReportSubmission? last = null;
            foreach (string file in files)
            {
                string body = File.ReadAllText(file, Encoding.UTF8);
                if (Encoding.UTF8.GetByteCount(body) > MaxBytes) return new(false, null, "too_large_saved_locally", PendingCount);
                try
                {
                    using var content = new StringContent(body, Encoding.UTF8, "application/json");
                    using var response = await client.PostAsync(endpoint, content).ConfigureAwait(false);
                    if (!response.IsSuccessStatusCode) return new(false, null, "http_" + (int)response.StatusCode, PendingCount);
                    string receiptText = await response.Content.ReadAsStringAsync().ConfigureAwait(false);
                    var receipt = JsonNode.Parse(receiptText) as JsonObject;
                    string? reportId = receipt?["report_id"]?.GetValue<string>();
                    if (receipt?["ok"]?.GetValue<bool>() != true || !Guid.TryParseExact(reportId, "D", out _))
                        return new(false, null, "invalid_receipt", PendingCount);
                    BugReportStore.WriteAtomic(Path.Combine(directory, "last-receipt.json"), receiptText);
                    File.Move(file, Path.Combine(directory, "reports", Path.GetFileNameWithoutExtension(file) + ".sent.json"), true);
                    last = new(true, reportId, "uploaded", PendingCount);
                }
                catch (HttpRequestException) { return new(false, null, "network_error", PendingCount); }
                catch (TaskCanceledException) { return new(false, null, "timeout", PendingCount); }
                catch (System.Text.Json.JsonException) { return new(false, null, "invalid_receipt", PendingCount); }
                catch (InvalidOperationException) { return new(false, null, "invalid_receipt", PendingCount); }
            }
            return last!;
        }
        finally { _sending.Release(); }
    }
}
