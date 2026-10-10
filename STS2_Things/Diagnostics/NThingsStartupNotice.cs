using System;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Localization;
using MegaCrit.Sts2.Core.Logging;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Multiplayer;
using MegaCrit.Sts2.Core.Nodes.Screens.MainMenu;
using MegaCrit.Sts2.Core.TestSupport;

namespace STS2_Things.Diagnostics;

/// <summary>A menu-owned waiter; the native modal owns all input, styling and dismissal.</summary>
public partial class NThingsStartupNotice : Node
{
    internal static bool ShownThisProcess { get; private set; }
    private double _delay = 2.1; // Let the native menu fade and startup dialogs finish first.

    public override void _Process(double delta)
    {
        if (ShownThisProcess || TestMode.IsOn)
        {
            QueueFree();
            return;
        }

        var menu = GetParent<NMainMenu>();
        if (!menu.IsVisibleInTree() || menu.SubmenuStack.SubmenusOpen ||
            NModalContainer.Instance is not { OpenModal: null } modal)
        {
            _delay = Math.Max(_delay, 0.25);
            return;
        }

        _delay -= delta;
        if (_delay > 0) return;

        NGenericPopup? popup = null;
        try
        {
            popup = NGenericPopup.Create();
            if (popup is null) return;
            popup.Name = "ThingsStartupNotice";
            modal.Add(popup);
            _ = popup.WaitForConfirmation(
                new LocString("settings_ui", "THINGS_STARTUP_NOTICE.body"),
                new LocString("settings_ui", "THINGS_STARTUP_NOTICE.title"),
                null,
                new LocString("settings_ui", "THINGS_STARTUP_NOTICE.confirm"));
            ShownThisProcess = true;
            Log.Info("[Things] Startup bug-report notice shown.");
        }
        catch (Exception exception)
        {
            // An informational notice must never prevent the game from starting.
            if (ReferenceEquals(modal.OpenModal, popup) && popup is not null) modal.Clear();
            else if (popup is not null && GodotObject.IsInstanceValid(popup)) popup.QueueFree();
            Log.Warn("[Things] Could not show startup notice: " + exception.Message);
        }
        finally
        {
            QueueFree();
        }
    }
}

[HarmonyPatch(typeof(NMainMenu), nameof(NMainMenu._Ready))]
internal static class ThingsStartupNoticePatch
{
    private static void Postfix(NMainMenu __instance)
    {
        if (!NThingsStartupNotice.ShownThisProcess && !TestMode.IsOn)
            __instance.AddChildSafely(new NThingsStartupNotice { Name = "ThingsStartupNoticeWaiter" });
    }
}
