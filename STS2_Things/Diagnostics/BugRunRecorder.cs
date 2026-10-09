using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Modding;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.FeedbackScreen;
using MegaCrit.Sts2.Core.Runs;
using MegaCrit.Sts2.Core.Runs.History;
using MegaCrit.Sts2.Core.Models;

namespace STS2_Things.Diagnostics;

/// <summary>Adds one optional category to the original F2 dropdown; other categories remain unchanged.</summary>
[HarmonyPatch(typeof(NFeedbackCategoryDropdown), "PopulateOptions")]
internal static class ThingsFeedbackCategoryPatch
{
    internal static readonly string[] Entries = ["things_bug", "things_bug_retry"];
    internal static string Title(string entry) => MegaCrit.Sts2.Core.Localization.LocManager.Instance.Language == "zhs"
        ? entry == "things_bug_retry" ? "琐事 Bug（重试待发送）" : "琐事 Bug（上传本局）"
        : entry == "things_bug_retry" ? "Things Bug (retry pending)" : "Things Bug (upload run)";
    private static void Postfix(NFeedbackCategoryDropdown __instance)
    {
        var type = typeof(NFeedbackCategoryDropdown);
        var categoriesField = AccessTools.Field(type, "_categories");
        var locField = AccessTools.Field(type, "_categoryLoc");
        var sceneField = AccessTools.Field(type, "_dropdownItemScene");
        var categories = (string[])categoriesField.GetValue(__instance)!;
        if (categories.Contains("things_bug")) return;
        categoriesField.SetValue(__instance, categories.Concat(Entries).ToArray());
        var localized = (MegaCrit.Sts2.Core.Localization.LocString[])locField.GetValue(__instance)!;
        locField.SetValue(__instance, localized.Concat(Entries.Select(_ => new MegaCrit.Sts2.Core.Localization.LocString("settings_ui", "FEEDBACK_CATEGORY.bug"))).ToArray());
        var scene = (PackedScene)sceneField.GetValue(__instance)!;
        var container = __instance.GetNode<Control>("DropdownContainer/VBoxContainer");
        for (int i = 0; i < Entries.Length; i++)
        {
            var item = scene.Instantiate<NFeedbackCategoryDropdownItem>();
            container.AddChild(item);
            item.Connect(NDropdownItem.SignalName.Selected, Callable.From<NDropdownItem>(selected =>
                AccessTools.Method(type, "OnDropdownItemSelected").Invoke(__instance, [selected])));
            item.Init(categories.Length + i, Title(Entries[i]));
        }
        container.GetParent<NDropdownContainer>().RefreshLayout();
    }
}

[HarmonyPatch(typeof(NFeedbackCategoryDropdown), "OnDropdownItemSelected")]
internal static class ThingsFeedbackSelectionPatch
{
    private static void Postfix(NFeedbackCategoryDropdown __instance)
    {
        if (!ThingsFeedbackCategoryPatch.Entries.Contains(__instance.CurrentCategory)) return;
        var label = (MegaCrit.Sts2.addons.mega_text.MegaLabel)AccessTools.Field(
            typeof(NDropdown), "_currentOptionLabel").GetValue(__instance)!;
        label.SetTextAutoSize(ThingsFeedbackCategoryPatch.Title(__instance.CurrentCategory));
        if (__instance.CurrentCategory == "things_bug_retry")
        {
            for (Node? parent = __instance.GetParent(); parent is not null; parent = parent.GetParent())
                if (parent is NSendFeedbackScreen screen)
                {
                    var input = (TextEdit)AccessTools.Field(typeof(NSendFeedbackScreen), "_descriptionInput").GetValue(screen)!;
                    if (string.IsNullOrWhiteSpace(input.Text))
                    {
                        input.Text = "Retry pending Things reports";
                        input.EmitSignal(TextEdit.SignalName.TextChanged);
                    }
                    break;
                }
        }
    }
}

/// <summary>Intercept only our opt-in category; vanilla sends other categories directly to MegaCrit.</summary>
[HarmonyPatch(typeof(NSendFeedbackScreen), "SendFeedback")]
internal static class ThingsFeedbackSendPatch
{
    private static bool Prefix(FeedbackData data, Stream screenshotStream, Stream logsMemoryStream, ref Task<bool> __result)
    {
        if (!ThingsFeedbackCategoryPatch.Entries.Contains(data.category)) return true;
        screenshotStream.Dispose(); logsMemoryStream.Dispose();
        __result = BugRunRecorder.SubmitAsync(data.description ?? "", data.category == "things_bug_retry");
        return false;
    }
}

[HarmonyPatch(typeof(NSendFeedbackScreen), "OnFeedbackSuccess")]
internal static class ThingsFeedbackReceiptPatch
{
    private static void Prefix(NSendFeedbackScreen __instance) => SetLabel(__instance, "_successLabel", true);
    internal static void SetLabel(NSendFeedbackScreen screen, string field, bool success)
    {
        var dropdown = (NFeedbackCategoryDropdown)AccessTools.Field(typeof(NSendFeedbackScreen), "_categoryDropdown").GetValue(screen)!;
        if (!ThingsFeedbackCategoryPatch.Entries.Contains(dropdown.CurrentCategory)) return;
        bool chinese = MegaCrit.Sts2.Core.Localization.LocManager.Instance.Language == "zhs";
        var result = BugRunRecorder.LastSubmission;
        string reason = result?.Reason switch {
            "description_too_short" => chinese ? "请至少填写两个字符" : "Please enter at least two characters",
            "network_error" or "timeout" => chinese ? "网络连接失败，请稍后重试" : "Connection failed; retry later",
            "http_429" => chinese ? "提交过于频繁，请稍后重试" : "Submission limit reached; retry later",
            "invalid_receipt" => chinese ? "服务器回执异常" : "Invalid server receipt",
            "local_storage_error" => chinese ? "未能保存报告，请检查本机存储" : "Unable to save the report locally",
            "too_large_saved_locally" => chinese ? "报告过大，完整内容已保存在本机" : "Report too large; full evidence is saved locally",
            _ => chinese ? "服务暂时不可用，请稍后重试" : "Service unavailable; retry later"
        };
        string message = success
            ? result?.ReportId is { } id ? (chinese ? "琐事报告已收到\n编号：" : "Things report received\nID: ") + id[..8]
                : chinese ? "没有待发送的报告" : "No pending reports"
            : result?.Pending > 0 ? (chinese ? "报告已保存在本机，可选择“重试待发送”\n" : "Report saved locally; choose retry pending\n") + reason : reason;
        ((MegaCrit.Sts2.addons.mega_text.MegaLabel)AccessTools.Field(typeof(NSendFeedbackScreen), field).GetValue(screen)!).SetTextAutoSize(message);
    }
}

[HarmonyPatch(typeof(NSendFeedbackScreen), "OnFeedbackFailed")]
internal static class ThingsFeedbackFailurePatch
{
    private static void Prefix(NSendFeedbackScreen __instance) => ThingsFeedbackReceiptPatch.SetLabel(__instance, "_failedLabel", false);
    private static void Postfix(NSendFeedbackScreen __instance, ref Task __result)
    {
        var dropdown = (NFeedbackCategoryDropdown)AccessTools.Field(typeof(NSendFeedbackScreen), "_categoryDropdown").GetValue(__instance)!;
        if (ThingsFeedbackCategoryPatch.Entries.Contains(dropdown.CurrentCategory)) __result = EnableRetry(__result, __instance);
    }
    private static async Task EnableRetry(Task nativeFailure, NSendFeedbackScreen screen)
    {
        await nativeFailure; // Resume on the existing Godot synchronization context.
        if (GodotObject.IsInstanceValid(screen) && screen.IsVisibleInTree())
            ((NButton)AccessTools.Field(typeof(NSendFeedbackScreen), "_sendButton").GetValue(screen)!).Enable();
    }
}
