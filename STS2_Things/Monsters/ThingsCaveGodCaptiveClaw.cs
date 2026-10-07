using System.Collections.Generic;
using Godot;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Bestiary;
using MegaCrit.Sts2.Core.Nodes.Vfx.Utilities;
using MegaCrit.Sts2.Core.Audio;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>
/// 抓取模式下的活体巨岩石爪（岩之手）。
/// 拥有独立 30 点生命值（进阶 35 点，多人使用原版遭遇血量缩放）。
/// 玩家打空此血条即可打碎石爪、解除牌型封印并提前将玩家安全放回地面！
/// </summary>
public sealed class ThingsCaveGodCaptiveClaw : MonsterModel
{
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Stone;
    public override string DeathSfx => FmodSfx.blockBreak;
    public override bool ShouldFadeAfterDeath => false;
    public override bool ShouldDisappearFromDoom => false;
    public override float DeathAnimLengthOverride => 0.5f;

    protected override string VisualsPath => SceneHelper.GetScenePath("creature_visuals/things_cave_god_captive_claw");

    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 35, 30);
    public override int MaxInitialHp => MinInitialHp;

    public bool IsSlamResolved { get; set; }

    private NCaveGodBossBackground? Background =>
        (NCombatRoom.Instance?.Background ?? NBestiary.Instance?.Layout)?.GetNodeOrNull<NCaveGodBossBackground>("%CaveGod");

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState captiveState = new("CAPTIVE_HOLD", CaptiveHoldMove);
        captiveState.FollowUpState = captiveState;
        return new MonsterMoveStateMachine(new[] { captiveState }, captiveState);
    }

    private static Task CaptiveHoldMove(IReadOnlyList<Creature> _) => Task.CompletedTask;

    public override Task AfterCurrentHpChanged(Creature creature, decimal delta)
    {
        if (IsSlamResolved) return Task.CompletedTask;
        if (creature == Creature && delta < 0m)
        {
            Vector2? hitPos = creature.GetCreatureNode()?.VfxSpawnPosition ?? creature.GetCreatureNode()?.GlobalPosition;
            Background?.PlayHurtAnim(forceGroan: true, hitPos: hitPos);
        }
        return Task.CompletedTask;
    }

    public override async Task AfterDeath(PlayerChoiceContext choiceContext,
        Creature creature, bool wasRemovalPrevented, float deathAnimLength)
    {
        if (creature != Creature || wasRemovalPrevented || IsSlamResolved) return;
        ThingsCaveGodBody? body = CombatState?.Enemies.Select(c => c.Monster).OfType<ThingsCaveGodBody>().FirstOrDefault();
        // A successful escape cancels the telegraphed slam. The body never substitutes an unseen hit.
        if (body != null) await body.ReleaseCaptives(stun: true);
        if (NCombatRoom.Instance != null)
        {
            SfxCmd.Play("event:/sfx/enemy/enemy_attacks/waterfall_giant/waterfall_giant_eruption");
            VfxCmd.PlayOnCreatureCenters([Creature], "vfx/vfx_rock_shatter");
            NGame.Instance?.ScreenShake(ShakeStrength.Strong, ShakeDuration.Short);
        }
    }
}
