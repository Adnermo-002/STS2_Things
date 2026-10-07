using System.Reflection;
using Godot;
using Godot.Bridge;
using HarmonyLib;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.addons.mega_text;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Saves;
using STS2_Things.Cards;
using STS2_Things.Monsters;
using STS2_Things.Powers;
using STS2_Things.Visuals;

public partial class LanternFishProbeNode
{
    private async Task RenderProbe(string root)
    {
        // The test backend intentionally rejects UI listeners. This fixture mounts
        // real UI and explicitly refreshes it; suppress only that test-host guard.
        var uiHost = new Harmony("LanternFishProbe.VisualHost");
        uiHost.Patch(AccessTools.Method(typeof(CombatStateTracker), "NotifyCombatStateChanged"),
            prefix: new HarmonyMethod(typeof(LanternFishProbeNode), nameof(SkipBackendUiNotification)));
        string output = Path.Combine(root, "build/lantern_fish/visuals"); Directory.CreateDirectory(output);
        var status = GDExtensionManager.LoadExtension(Path.Combine(root, "addons/spine/spine_godot_extension.gdextension"));
        Assert(status is GDExtensionManager.LoadStatus.Ok or GDExtensionManager.LoadStatus.AlreadyLoaded, "Spine extension loaded.");
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(NCard).Assembly);
        ScriptManagerBridge.LookupScriptsInAssembly(typeof(LanternFish).Assembly);
        // V111 creates atlas .tres resources dynamically during normal game startup.
        Type? atlasLoaderType = typeof(ModelDb).Assembly.GetType("MegaCrit.Sts2.Core.Assets.AtlasResourceLoader");
        ResourceFormatLoader? atlasLoader = atlasLoaderType == null ? null : (ResourceFormatLoader)Activator.CreateInstance(atlasLoaderType)!;
        if (atlasLoader != null) ResourceLoader.AddResourceFormatLoader(atlasLoader, atFront: true);
        typeof(MegaCrit.Sts2.Core.Runs.RunManager).GetProperty("NetService")!.SetValue(
            MegaCrit.Sts2.Core.Runs.RunManager.Instance, new MegaCrit.Sts2.Core.Multiplayer.NetSingleplayerGameService());
        SaveManager.Instance.SettingsSave.Language = "zhs";
        MegaCrit.Sts2.Core.Localization.LocManager.Initialize();
        GetTree().Root.Size = new Vector2I(1920,1080);
        var view = new SubViewport { Size = new Vector2I(1920,1080), Disable3D = true, RenderTargetUpdateMode = SubViewport.UpdateMode.Always };
        AddChild(view);
        var bg = MegaCrit.Sts2.Core.Nodes.Rooms.NCombatBackground.Create(
            new MegaCrit.Sts2.Core.Rooms.BackgroundAssets("lantern_fish_encounter", new MegaCrit.Sts2.Core.Random.Rng()));
        bg.Position = new Vector2(983,540);
        view.AddChild(bg);
        var s = Scenario();
        var hero = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
        typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(hero, s.Player.Creature);
        var heroVisuals = GD.Load<PackedScene>("res://scenes/creature_visuals/ironclad.tscn").Instantiate<NCreatureVisuals>();
        typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(hero, heroVisuals);
        hero.Position = new Vector2(480,746); view.AddChild(hero);
        var nodes = new List<NCreature>();
        var sprites = new List<Node2D>();
        var slots = GD.Load<PackedScene>("res://scenes/encounters/lantern_fish_encounter.tscn").Instantiate<Control>();
        view.AddChild(slots);
        for (int i=0;i<3;i++)
        {
            var fish = s.Encounter.MonstersWithSlots[i].Item1; fish.RollMove([s.Player.Creature]);
            var creature = GD.Load<PackedScene>("res://scenes/combat/creature.tscn").Instantiate<NCreature>();
            typeof(NCreature).GetProperty(nameof(NCreature.Entity))!.SetValue(creature, fish.Creature);
            var visuals = GD.Load<PackedScene>("res://scenes/creature_visuals/lantern_fish.tscn").Instantiate<NCreatureVisuals>();
            typeof(NCreature).GetProperty(nameof(NCreature.Visuals))!.SetValue(creature, visuals);
            creature.Position = slots.GetNode<Node2D>(s.Encounter.Slots[i]).Position; view.AddChild(creature);
            await creature.UpdateIntent([s.Player.Creature]);
            creature.IntentContainer.Modulate = Colors.White;
            nodes.Add(creature); sprites.Add(visuals.GetNode<Node2D>("Visuals"));
        }
        foreach (var sprite in sprites) sprite.Call("set_update_mode", ClassDB.ClassGetIntegerConstant("SpineConstant","UpdateMode_Manual"));
        foreach (var (trigger,animation) in new[]{("Attack","attack"),("Cast","cast"),("Guard","guard"),("TailSwipe","tail_swipe")})
        {
            nodes[0].SetAnimationTrigger(trigger);
            var state=sprites[0].Call("get_animation_state").AsGodotObject();
            var track=state.Call("get_current",0).AsGodotObject();
            Assert(track.Call("get_animation").AsGodotObject().Call("get_name").AsString()==animation,
                $"Native creature animation trigger {trigger}.");
        }
        void Pose(Node2D sprite,string name,float t)
        {
            var skeleton = sprite.Call("get_skeleton").AsGodotObject(); skeleton.Call("set_to_setup_pose");
            var state = sprite.Call("get_animation_state").AsGodotObject(); state.Call("clear_tracks");
            var track = state.Call("set_animation",name,false,0).AsGodotObject();
            track.Call("set_track_time",t); track.Call("set_mix_duration",0f); sprite.Call("update_skeleton",0f);
            sprite.GetNode<NLanternGlow>("LampBone/Glow")._Process(0);
        }
        async Task Capture(string name)
        {
            await ToSignal(GetTree(), SceneTree.SignalName.ProcessFrame);
            await ToSignal(RenderingServer.Singleton, RenderingServer.SignalName.FramePostDraw);
            using var frame = view.GetTexture().GetImage();
            Assert(frame.SavePng(Path.Combine(output,name+".png")) == Error.Ok, "Saved native render.");
        }
        for (int i=0;i<20;i++) await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        for(int i=0;i<3;i++) Pose(sprites[i],"idle_loop",i*.8f);
        await Capture("encounter_idle");
        Pose(sprites[1],"cast",.72f); await Capture("encounter_flash");

        // Instantiate the actual game's NCard scene, not a mock card or a screenshot overlay.
        var normal=Put<StrikeIronclad>(s,s.Player,PileType.Hand);
        var blinded=Put<DefendIronclad>(s,s.Player,PileType.Hand);
        var wound=Put<Wound>(s,s.Player,PileType.Hand);
        await Blind(s.Player,4);
        var power=s.Player.Creature.GetPower<LanternBlindnessPower>()!;
        await power.AfterCardDrawn(Choice,blinded,false); await power.AfterCardDrawn(Choice,wound,false);
        NCard MakeCard(CardModel model,float x)
        {
            var card=GD.Load<PackedScene>("res://scenes/cards/card.tscn").Instantiate<NCard>();
            card.Model=model; card.Position=new Vector2(x,926); card.Scale=Vector2.One*.53f;
            view.AddChild(card); card.UpdateVisuals(PileType.Hand,CardPreviewMode.Normal); return card;
        }
        var cards = new[]{MakeCard(normal,300),MakeCard(blinded,557),MakeCard(wound,814)};
        int rngBefore=RngCounter(s.Run.Rng.CombatEnergyCosts);
        string nativeDescription=blinded.GetDescriptionForPile(PileType.Hand,null);
        var desc=cards[1].GetNode<MegaRichTextLabel>("%DescriptionLabel");
        string firstText=desc.Text;
        Assert(!firstText.Contains(nativeDescription), "Native description visually obscured.");
        await Capture("cards_blinded");
        for(int i=0;i<24;i++)
        {
            float t=i/12f;
            Pose(sprites[0],"idle_loop",t); Pose(sprites[1],"cast",Math.Min(t,1.8f)); Pose(sprites[2],"idle_loop",t+1.6f);
            cards[1].GetNode<NBlindCardVeil>("LanternBlindVeil")._Process(1.0/12);
            cards[2].GetNode<NBlindCardVeil>("LanternBlindVeil")._Process(1.0/12);
            await Capture($"sequence_{i:000}");
        }
        Assert(desc.Text!=firstText, "Description animates.");
        Assert(blinded.GetDescriptionForPile(PileType.Hand,null)==nativeDescription, "Underlying model text untouched.");
        Assert(RngCounter(s.Run.Rng.CombatEnergyCosts)==rngBefore, "Visuals consume no gameplay RNG.");
        s.Player.PlayerCombatState!.EndOfTurnCleanup();
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        GD.Print($"Restored description: {desc.Text}; expected: {nativeDescription}");
        Assert(desc.Text.Contains(nativeDescription), "Native description restored after cleanup.");
        Assert(cards[2].GetNode<MegaRichTextLabel>("%DescriptionLabel").Text.Contains(wound.GetDescriptionForPile(PileType.Hand,null)), "Unplayable description also restored.");
        Assert(!cards[1].GetNode<ColorRect>("CardContainer/PortraitCanvasGroup/Portrait/BlindStatic").Visible, "Portrait veil removed.");
        await Capture("cards_restored");
        cards[1].Model=normal; cards[1].UpdateVisuals(PileType.Hand,CardPreviewMode.Normal);
        Assert(cards[1].GetNode<MegaLabel>("%TitleLabel").Text==cards[0].GetNode<MegaLabel>("%TitleLabel").Text, "Pooled view refreshes correctly.");
        foreach(var card in cards) card.QueueFree();
        foreach(string name in OS.GetCmdlineUserArgs().Contains("--quick") ? Array.Empty<string>() : new[]{"idle_loop","attack","tail_swipe","cast","guard","hurt","die","revive","summon","power_up"})
        {
            var data=sprites[0].Get("skeleton_data_res").AsGodotObject();
            var anim=data.Call("find_animation",name).AsGodotObject();
            Assert(anim!=null,$"Packaged {name} exists.");
            float duration=anim!.Call("get_duration").AsSingle();
            for(int i=0;i<4;i++)
            {
                Pose(sprites[0],name,duration*i/3);
                Pose(sprites[1],name,duration*i/3);
                Pose(sprites[2],name,duration*i/3);
                await Capture($"pose_{name}_{i}");
            }
        }
        view.QueueFree(); await ToSignal(GetTree(),SceneTree.SignalName.ProcessFrame);
        DeactivateSyntheticCombat();
        uiHost.UnpatchAll(uiHost.Id);
        if (atlasLoader != null) ResourceLoader.RemoveResourceFormatLoader(atlasLoader);
    }

    private static bool SkipBackendUiNotification() => false;
}
