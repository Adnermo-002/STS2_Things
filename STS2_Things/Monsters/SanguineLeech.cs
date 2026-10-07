using MegaCrit.Sts2.Core.Animation;
using MegaCrit.Sts2.Core.Audio;
using MegaCrit.Sts2.Core.Bindings.MegaSpine;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Ascension;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions.Multiplayer;
using MegaCrit.Sts2.Core.Helpers;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.TestSupport;
using MegaCrit.Sts2.Core.ValueProps;
using STS2_Things.Cards;
using STS2_Things.Powers;
using static STS2_Things.Compatibility.Sts2VersionCompatibility;

namespace STS2_Things.Monsters;

public sealed class SanguineLeech : ThingsSpineMonster
{
    public const float BiteContact = .46f;
    public const float ParasiteRelease = .62f;
    public const float CurlContact = .38f;
    public const int CurlBlock = 8;
    public const string ReinfestMoveId = "REINFEST_MOVE";
    private int _openingPhase;
    private MoveState? _reinfest;
    private bool _reinfestPending;
    public int OpeningPhase => _openingPhase;
    public void SetOpeningPhase(int phase) { AssertMutable(); _openingPhase = Math.Clamp(phase, 0, 3); }
    public override int MinInitialHp => AscensionHelper.GetValueIfAscension(AscensionLevel.ToughEnemies, 38, 34);
    public override int MaxInitialHp => MinInitialHp + 4;
    public override float HpBarSizeReduction => 130f;
    private int BiteDamage => AscensionHelper.GetValueIfAscension(AscensionLevel.DeadlyEnemies, 8, 7);
    protected override string AttackSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_attack_light";
    protected override string CastSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_devour";
    public override string DeathSfx => "event:/sfx/enemy/enemy_attacks/gravetide_slug/gravetide_slug_die";
    public override DamageSfxType TakeDamageSfxType => DamageSfxType.Magic;
    public override IEnumerable<string> AssetPaths => base.AssetPaths.Concat([
        ModelDb.Card<LeechParasite>().PortraitPath]);

    public override async Task BeforeCombatStart()
    {
        if (!Creature.IsAlive) return;
        await PowerCmd.Apply<LeechInfestationPower>(new ThrowingPlayerChoiceContext(), Creature, 1, Creature, null);
        // Opening parasites are generated directly into the hand with skipVisuals: true
        // so that pre-combat initialization doesn't create invalid UI holders at (0, 0).
        // Visual holders will be safely attached at the start of turn 1 in BeforeHandDraw.
        foreach (var player in CombatState.Players.Where(p => p.Creature.IsAlive))
        {
            var card = CombatState.CreateCard<LeechParasite>(player);
            await CardPileCmd.Add(card, PileType.Hand, CardPilePosition.Bottom, null, skipVisuals: true);
        }
    }

    public override Task BeforeHandDraw(Player player, PlayerChoiceContext choiceContext, ICombatState combatState)
    {
        if (!TestMode.IsOn && LocalContext.IsMe(player) && player.PlayerCombatState?.TurnNumber == 1 &&
            NCombatRoom.Instance?.Ui?.Hand is { } handUi)
        {
            var unassignedList = player.PlayerCombatState.Hand.Cards
                .OfType<LeechParasite>()
                .Where(c => handUi.GetCardHolder(c) == null)
                .ToList();
            if (unassignedList.Count > 0)
            {
                var card = unassignedList[0];
                var nCard = NCard.Create(card);
                if (nCard != null)
                {
                    nCard.GlobalPosition = Creature.GetCreatureNode()?.GlobalPosition ?? handUi.GlobalPosition;
                    handUi.Add(nCard);
                }

                var otherLivingLeeches = combatState.Enemies
                    .Select(e => e.Monster)
                    .OfType<SanguineLeech>()
                    .Where(l => l != this && l.Creature.IsAlive);
                if (!otherLivingLeeches.Any())
                {
                    for (int i = 1; i < unassignedList.Count; i++)
                    {
                        var extraCard = unassignedList[i];
                        var extraNode = NCard.Create(extraCard);
                        if (extraNode != null)
                        {
                            extraNode.GlobalPosition = handUi.GlobalPosition;
                            handUi.Add(extraNode);
                        }
                    }
                }
                handUi.ForceRefreshCardIndices();
            }
        }
        return Task.CompletedTask;
    }

    public void RequestReinfestation()
    {
        AssertMutable();
        if (!Creature.IsAlive || CombatManager.Instance.IsOverOrEnding) return;
        // Keep the already advertised action. Consume the request only when
        // preparing a later turn, including when the current move is Infest.
        _reinfestPending = true;
    }

    public override Task AfterSideTurnEnd(PlayerChoiceContext choiceContext, CombatSide side, IEnumerable<Creature> participants)
    {
        if (side == CombatSide.Enemy && participants.Contains(Creature)) PrepareReinfestation();
        return Task.CompletedTask;
    }

    private void PrepareReinfestation()
    {
        if (!_reinfestPending || _reinfest == null || !Creature.IsAlive ||
            IsPerformingMove || !NextMove.CanTransitionAway || CombatManager.Instance.IsOverOrEnding) return;
        // Insert without advancing or resetting the normal cycle. Stun uses a
        // follow-up ID; a stun that resumes this insertion must retain its cursor.
        MonsterState resume = NextMove.FollowUpState ?? MoveStateMachine!.States[NextMove.FollowUpStateId!];
        if (resume != _reinfest) _reinfest.FollowUpState = resume;
        // The mandatory insertion survives the native next-turn roll. Further
        // requests during it keep the same saved normal action.
        SetMoveImmediate(_reinfest);
        _reinfestPending = false;
    }

    protected override void AddExtraAnimationStates(CreatureAnimator animator, AnimState idle)
    {
        animator.AddAnyState("Curl", new AnimState("curl") { NextState = idle });
        animator.AddAnyState("Feed", new AnimState("feed") { NextState = idle });
    }

    protected override MonsterMoveStateMachine GenerateMoveStateMachine()
    {
        MoveState[] cycle = [
            new("SIP_MOVE", Sip, new SingleAttackIntent(BiteDamage)),
            new("INFEST_MOVE", Infest, new StatusIntent(1)),
            new("SIP_AGAIN_MOVE", Sip, new SingleAttackIntent(BiteDamage)),
            new("CURL_MOVE", Curl, new DefendIntent())];
        for (int i = 0; i < cycle.Length; i++) cycle[i].FollowUpState = cycle[(i + 1) % cycle.Length];
        _reinfestPending = false;
        _reinfest = new MoveState(ReinfestMoveId, Infest, new StatusIntent(1))
        {
            MustPerformOnceBeforeTransitioning = true,
            FollowUpState = cycle[_openingPhase],
        };
        return new MonsterMoveStateMachine([.. cycle, _reinfest], cycle[_openingPhase]);
    }

    private async Task WaitForPose(string animation, float moment, float fallback)
    {
        var sprite = Creature.GetCreatureNode()?.Visuals?.SpineBody;
        float wait = fallback;
        using (TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? track))
            if (track != null && track.GetAnimationName() == animation)
                wait = Math.Max(0, moment - track.GetTrackTime());
        await Cmd.Wait(wait);
        using var scope = TrackEntryScope(sprite?.TryGetAnimationState()?.GetCurrent(0), out MegaTrackEntry? current);
        if (current != null && current.GetAnimationName() == animation && current.GetTrackTime() < moment)
        {
            current.SetMixDuration(0);
            current.SetTrackTime(moment);
            sprite!.BoundObject.Call("update_skeleton", 0f);
        }
    }

    private async Task Begin(string trigger, string animation, float contact)
    {
        await CreatureCmd.TriggerAnim(Creature, trigger, 0f);
        await WaitForPose(animation, contact, contact);
    }

    private async Task Sip(IReadOnlyList<Creature> targets)
    {
        var attack = await DamageCmd.Attack(BiteDamage).FromMonster(this).WithNoAttackerAnim()
            .AfterAttackerAnim(() => Begin("Attack", "attack", BiteContact))
            .WithAttackerFx(null, AttackSfx).WithHitFx("vfx/vfx_bite").Execute(null);
        await WaitForPose("attack", 1.12f, 0);
        int stolen = attack.Results.SelectMany(hit => hit).Sum(hit => Math.Max(0, hit.UnblockedDamage - hit.OverkillDamage));
        if (Creature.IsAlive && Creature.CurrentHp < Creature.MaxHp && stolen > 0)
        {
            await Begin("Feed", "feed", .30f);
            await CreatureCmd.Heal(Creature, stolen);
            await WaitForPose("feed", .85f, 0);
        }
    }

    private async Task Infest(IReadOnlyList<Creature> targets)
    {
        SfxCmd.Play(CastSfx);
        await Begin("Cast", "cast", ParasiteRelease);
        await CardPileCmd.AddToCombatAndPreview<LeechParasite>(targets.Where(c => c.IsAlive),
            PileType.Hand, 1, null);
        await WaitForPose("cast", 1.45f, 0);
    }

    private async Task Curl(IReadOnlyList<Creature> targets)
    {
        await Begin("Curl", "curl", CurlContact);
        await CreatureCmd.GainBlock(Creature, CurlBlock, ValueProp.Move, null);
        await WaitForPose("curl", 1.1f, 0);
    }
}
