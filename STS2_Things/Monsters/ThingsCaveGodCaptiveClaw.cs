using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Audio;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Bestiary;
using STS2_Things.Powers;
using STS2_Things.Visuals;

namespace STS2_Things.Monsters;

/// <summary>
/// 抓取模式下的山神石爪（拘禁之手）。
/// 拥有独立 30 点生命值（进阶 35 点，多人每人 +20 点）。
/// 玩家打空此血条即可打碎石爪、解除牌型封印并提前将玩家安全放回地面！
/// </summary>
public sealed class ThingsCaveGodCaptiveClaw : MonsterModel
{
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/kaiser_crab/kaiser_crab_left_attack_slam";
    public override bool ShouldFadeAfterDeath => false;
    public override bool ShouldDisappearFromDoom => false;
    public override float DeathAnimLengthOverride => 0.5f;

    public override int MinInitialHp
    {
        get
        {
            int baseHp = AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 35, 30);
            int playerCount = CombatState?.Players.Count ?? 1;
            return baseHp + (playerCount > 1 ? (playerCount - 1) * 20 : 0);
        }
    }

    public override int MaxInitialHp => MinInitialHp;

    private NCaveGodBossBackground? Background =>
        (NCombatRoom.Instance?.Background ?? NBestiary.Instance?.Layout)?.GetNodeOrNull<NCaveGodBossBackground>("%CaveGod");

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState captiveState = new("CAPTIVE_HOLD", CaptiveHoldMove);
        captiveState.FollowUpState = captiveState;
        return new MonsterMoveStateMachine(new[] { captiveState }, captiveState);
    }

    private static Task CaptiveHoldMove(IReadOnlyList<Creature> _) => Task.CompletedTask;

    public override async Task BeforeDeath(Creature creature)
    {
        if (creature != Creature)
            return;

        NAudioManager.Instance?.PlayOneShot(DeathSfx);
        VfxCmd.PlayOnCreatureCenters([Creature], "vfx/vfx_heavy_blunt");

        // 1. 通知右手巨臂：石爪已被打破，下回合暴扣落空！
        ThingsCaveGodRightHand? rightHand = CombatState?.Enemies
            .Select(c => c.Monster).OfType<ThingsCaveGodRightHand>().FirstOrDefault();
        rightHand?.OnHandBroken();

        // 2. 移除所有玩家的二选一牌型禁锢
        if (CombatState != null)
        {
            foreach (Creature player in CombatState.PlayerCreatures)
            {
                if (player.HasPower<CaveGodMartialPower>())
                {
                    await PowerCmd.Remove<CaveGodMartialPower>(player);
                }
                if (player.HasPower<CaveGodArcanePower>())
                {
                    await PowerCmd.Remove<CaveGodArcanePower>(player);
                }
            }
        }

        // 3. 将被抓取的玩家安全平稳放回战台地面
        if (Background != null)
        {
            await Background.DropPlayersToGround(isSlam: false);
        }
    }
}
