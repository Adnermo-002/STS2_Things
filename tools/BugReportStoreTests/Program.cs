using System.Net;
using System.Text;
using System.Text.Json.Nodes;
using STS2_Things.Diagnostics;

static class Tests
{
    private static int _checks;
    private static void Check(bool pass, string detail) { if (!pass) throw new Exception(detail); _checks++; }
    private static JsonObject Snapshot(string seed, int hp = 70) => new() {
        ["seed"] = seed, ["players"] = new JsonArray(new JsonObject { ["hp"] = hp, ["combat"] = new JsonObject {
            ["hand"] = new JsonArray(new JsonObject { ["id"] = "CARD.LEECH_PARASITE", ["energy"] = 1 })
        } })
    };
    private static JsonObject Metadata() => new() { ["game_version"] = "v0.111.0", ["mod_version"] = "test", ["active_mods"] = new JsonArray() };

    public static async Task Main()
    {
        string root = Path.Combine(Path.GetTempPath(), "ThingsReportStoreTests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var store = new BugReportStore(root);
            Check(!store.Begin("first", Metadata(), Snapshot("a")), "first observation starts a run");
            string runId = store.Current!["client_run_id"]!.GetValue<string>();
            store.Track(new JsonObject { ["kind"] = "action_started" }); store.Update(Snapshot("a", 55)); store.Persist();
            var restored = new BugReportStore(root);
            Check(restored.Begin("first", Metadata(), Snapshot("a", 50)), "same saved run restores");
            Check(restored.Current!["client_run_id"]!.GetValue<string>() == runId, "resume ID is stable");
            Check(restored.Current["events"]!.AsArray().Count == 1, "actions survive restart");
            Check(restored.Current["initial_state"]!["players"]![0]!["hp"]!.GetValue<int>() == 70, "initial snapshot remains immutable");
            Check(!restored.Begin("second", Metadata(), Snapshot("b")), "second run starts without lifecycle recursion");
            Check(BugReportStore.ReadObject(Path.Combine(root, "last-run.json"))!["state"]!["seed"]!.GetValue<string>() == "a", "previous journal remains the previous run");
            restored.Track(new JsonObject { ["kind"] = "sample" }); restored.Persist(); restored.Persist();
            File.WriteAllText(Path.Combine(root, "current-run.json"), "{broken");
            Check(BugReportStore.ReadObject(Path.Combine(root, "current-run.json")) is not null, "corrupted primary recovers backup");
            for (int i = 0; i < 750; i++) restored.Track(new JsonObject { ["kind"] = "sample" });
            Check(restored.Current!["events"]!.AsArray().Count == 700 && restored.Current["dropped_events"]!.GetValue<int>() == 51, "bounded event history declares drops");
            Check(restored.JournalForUpload()["local_run_key"] is null, "local fingerprint is not uploaded");

            var handler = new Transport(); using var http = new HttpClient(handler);
            var outbox = new BugReportOutbox(root, http, new Uri("http://127.0.0.1/report"));
            string id = outbox.Enqueue(restored.JournalForUpload(), "手牌费用消失");
            Check((await outbox.SendAsync(id)).Reason == "network_error", "network failure preserves queue");
            string original = File.ReadAllText(Path.Combine(root, "pending", id + ".json"));
            Check(outbox.Enqueue(restored.JournalForUpload(), "手牌费用消失") == id, "same failed submission preserves immutable ID");
            string second = outbox.Enqueue(restored.JournalForUpload(), "另一个问题");
            Check(second != id && outbox.PendingCount == 2, "distinct failed reports do not overwrite each other");
            handler.Mode = "bad_receipt";
            Check((await outbox.SendAsync(id)).Reason == "invalid_receipt" && outbox.PendingCount == 2, "invalid acknowledgement cannot delete a report");
            handler.Mode = "success";
            Check((await outbox.SendAsync(id)).Success && outbox.PendingCount == 1, "validated receipt acknowledges only selected report");
            Check(handler.Bodies[^1] == original, "retry sends original body verbatim");
            Check((await outbox.SendAsync()).Success && outbox.PendingCount == 0, "explicit queue retry sends remaining report");
            Check((await outbox.SendAsync()).Reason == "nothing_pending", "empty queue is explicit");

            var large = restored.JournalForUpload();
            large["initial_state"] = new JsonObject { ["padding"] = new string('x', 400_000) };
            string bigId = outbox.Enqueue(large, "超限报告也必须保存描述");
            string full = File.ReadAllText(Path.Combine(root, "reports", bigId + ".json"));
            string wire = File.ReadAllText(Path.Combine(root, "pending", bigId + ".json"));
            Check(Encoding.UTF8.GetByteCount(wire) <= BugReportOutbox.MaxBytes, "oversized report shrinks optional evidence");
            Check(full.Contains("超限报告也必须保存描述") || JsonNode.Parse(full)!["description"]!.GetValue<string>() == "超限报告也必须保存描述", "complete description saved locally");
            Check(JsonNode.Parse(wire)!["run"]!["upload_truncation"] is JsonArray, "truncation is explicit");
            Console.WriteLine($"BugReportStoreTests: PASS ({_checks} assertions)");
        }
        finally {
            string absolute = Path.GetFullPath(root);
            if (!absolute.StartsWith(Path.GetFullPath(Path.GetTempPath()), StringComparison.OrdinalIgnoreCase)
                || !Path.GetFileName(absolute).StartsWith("ThingsReportStoreTests-", StringComparison.Ordinal)) throw new Exception("Unexpected cleanup target");
            Directory.Delete(absolute, true);
        }
    }

    private sealed class Transport : HttpMessageHandler
    {
        internal string Mode = "network_error";
        internal readonly List<string> Bodies = [];
        protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Bodies.Add(await request.Content!.ReadAsStringAsync(cancellationToken));
            if (Mode == "network_error") throw new HttpRequestException("test-only disconnect");
            string text = Mode == "bad_receipt" ? "{\"ok\":true}" : "{\"ok\":true,\"report_id\":\"" + Guid.NewGuid().ToString("D") + "\"}";
            return new HttpResponseMessage(HttpStatusCode.Created) { Content = new StringContent(text) };
        }
    }
}
