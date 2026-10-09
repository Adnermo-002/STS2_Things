using System.Collections;
using System.Diagnostics;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;
using System.Text.Json.Nodes;
using Godot;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Things.Diagnostics;

internal static class BugSnapshot
{
    private static readonly string Session = Guid.NewGuid().ToString("N")[..8];
    private sealed class Identity { internal string Value { get; } = "entity-" + Session + "-" + Interlocked.Increment(ref _next); }
    private static long _next;
    private static readonly ConditionalWeakTable<object, Identity> Ids = new();
    internal static string? InstanceId(object? value) => value is null ? null : Ids.GetValue(value, _ => new Identity()).Value;
    internal static JsonObject Object(object value) => JsonSerializer.SerializeToNode(value)!.AsObject();

    private static object Card(CardModel card)
    {
        try { return new {
            instance_id = InstanceId(card), id = card.Id.ToString(), upgrade = card.CurrentUpgradeLevel,
            energy = card.EnergyCost.GetWithModifiers(CostModifiers.All), costs_x = card.EnergyCost.CostsX,
            stars = card.CurrentStarCost, type = card.Type.ToString(), target_type = card.TargetType.ToString(),
            playable = card.Pile?.Type == PileType.Hand ? (bool?)card.CanPlay() : null,
            affliction = card.Affliction?.Id.ToString(), enchantment = card.Enchantment?.Id.ToString()
        }; }
        catch (Exception ex) { return new { instance_id = InstanceId(card), id = card.Id.ToString(), unavailable = true, error = Error(ex) }; }
    }

    private static object[] Powers(IEnumerable<PowerModel> powers) => powers.Select(p => (object)new {
        id = p.Id.ToString(), amount = p.Amount
    }).ToArray();

    internal static object? Error(Exception? exception) => exception is null ? null : new {
        type = exception.GetBaseException().GetType().FullName,
        // Method names have diagnostic value without carrying paths, messages or credentials.
        frames = new StackTrace(exception).GetFrames()?.Take(15).Select(f => {
            var method = f.GetMethod(); return method?.DeclaringType?.FullName + "." + method?.Name;
        }).ToArray()
    };

    internal static JsonObject Capture(RunState run, GameAction? waitingAction = null)
    {
        var manager = CombatManager.Instance;
        var combat = manager.DebugOnlyGetState();
        var action = RunManager.Instance.ActionExecutor?.CurrentlyRunningAction ?? waitingAction;
        return Object(new {
            seed = run.Rng.StringSeed, numeric_seed = run.Rng.Seed.ToString(), game_mode = run.GameMode.ToString(),
            ascension = run.AscensionLevel, current_act_index = run.CurrentActIndex, current_act = run.Act.Id.ToString(),
            current_floor = run.ActFloor, total_floor = run.TotalFloor, map_coord = run.CurrentMapCoord?.ToString(),
            current_room = run.CurrentRoom?.GetType().Name, acts = run.Acts.Select(a => a.Id.ToString()).ToArray(),
            players = run.Players.Select((p, index) => new {
                index, character = p.Character.Id.ToString(), hp = p.Creature.CurrentHp, max_hp = p.Creature.MaxHp,
                block = p.Creature.Block, gold = p.Gold,
                deck = p.Deck.Cards.Select(Card).ToArray(), relics = p.Relics.Select(r => r.Id.ToString()).ToArray(),
                potions = p.PotionSlots.Select(potion => potion?.Id.ToString()).ToArray(), powers = Powers(p.Creature.Powers),
                combat = p.PlayerCombatState is { } pc ? new {
                    energy = pc.Energy, stars = pc.Stars, turn = pc.TurnNumber, phase = pc.Phase.ToString(),
                    hand = pc.Hand.Cards.Select(Card).ToArray(), draw_pile = pc.DrawPile.Cards.Select(Card).ToArray(),
                    discard_pile = pc.DiscardPile.Cards.Select(Card).ToArray(), exhaust_pile = pc.ExhaustPile.Cards.Select(Card).ToArray(),
                    play_pile = pc.PlayPile.Cards.Select(Card).ToArray()
                } : null
            }).ToArray(),
            route = run.MapPointHistory.Select((act, ai) => new {
                act_index = ai, points = act.Select((point, fi) => new {
                    floor_index = fi, map_point_type = point.MapPointType.ToString(),
                    rooms = point.Rooms.Select(room => new {
                        type = room.RoomType.ToString(), model_id = room.ModelId?.ToString(),
                        monster_ids = room.MonsterIds.Select(id => id.ToString()).ToArray(), turns = room.TurnsTaken
                    }).ToArray(),
                    players = point.PlayerStats.Select((ps, pi) => new {
                        index = pi, hp = ps.CurrentHp, max_hp = ps.MaxHp, gold = ps.CurrentGold,
                        damage_taken = ps.DamageTaken, healed = ps.HpHealed,
                        event_choices = ps.EventChoices.Select(c => new { key = c.Title.LocEntryKey, table = c.Title.LocTable }).ToArray(),
                        relic_choices = ps.RelicChoices.Select(c => new { id = c.choice.ToString(), picked = c.wasPicked }).ToArray(),
                        potion_choices = ps.PotionChoices.Select(c => new { id = c.choice.ToString(), picked = c.wasPicked }).ToArray(),
                        card_choices = ps.CardChoices.Select(c => new { id = c.Card.Id?.ToString(), picked = c.wasPicked }).ToArray(),
                        rest_choices = ps.RestSiteChoices.Select(c => c.ToString()).ToArray(),
                        cards_gained = ps.CardsGained.Select(c => c.ToString()).ToArray(), cards_removed = ps.CardsRemoved.Select(c => c.ToString()).ToArray()
                    }).ToArray()
                }).ToArray()
            }).ToArray(),
            combat = manager.IsInProgress && combat is not null ? new {
                round = combat.RoundNumber, side = combat.CurrentSide.ToString(), actions_disabled = manager.PlayerActionsDisabled,
                monsters = combat.Enemies.Select(c => new {
                    instance_id = InstanceId(c), id = c.ModelId.ToString(), hp = c.CurrentHp, max_hp = c.MaxHp, block = c.Block,
                    alive = c.IsAlive, hittable = c.IsHittable, powers = Powers(c.Powers), next_move = c.Monster?.NextMove?.Id,
                    intents = c.Monster?.NextMove?.Intents.Select(i => i.GetType().Name).ToArray()
                }).ToArray()
            } : null,
            execution = action is null ? null : new {
                type = action.GetType().Name, id = action.Id, state = action.State.ToString(), error = Error(action.Exception)
            },
            ui = CaptureUi()
        });
    }

    // Only fixed game fields cross the compatibility seam, never report/user-supplied reflection names.
    private static object? Field(object value, string name)
    {
        for (var type = value.GetType(); type is not null; type = type.BaseType)
            if (type.GetField(name, BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly) is { } field)
                return field.GetValue(value);
        return null;
    }

    private static object? Read(object? value, string name) => value?.GetType().GetProperty(name)?.GetValue(value);
    private static List<object> Items(object? value) => value is IEnumerable items ? items.Cast<object>().Take(200).ToList() : [];

    private static object? CaptureUi()
    {
        try
        {
            var hand = NPlayerHand.Instance;
            if (hand is null) return null;
            var holders = hand.CardHolderContainer.GetChildren().Where(n => n.GetType().Name.Contains("HandCardHolder"))
                .Concat(Items(Field(hand, "_selectedHandCardContainer") is { } container ? Read(container, "Holders") : null).OfType<Node>()).ToList();
            var selected = Items(Field(hand, "_selectedCards"));
            var prefs = Field(hand, "_prefs");
            var confirm = Field(hand, "_selectModeConfirmButton") as Control;
            return new {
                mode = hand.CurrentMode.ToString(), selection_active = hand.IsInCardSelection, in_card_play = hand.InCardPlay,
                selected = selected.Select(InstanceId).ToArray(), min = Read(prefs, "MinSelect"), max = Read(prefs, "MaxSelect"),
                confirm_enabled = confirm?.IsVisibleInTree() == true && Read(confirm, "IsEnabled") is true,
                dragged_holder_index = Field(hand, "_draggedHolderIndex"), awaiting_queue = Items(Field(hand, "_holdersAwaitingQueue")).Count,
                holders = holders.Select(h => {
                    var card = Read(Read(h, "CardNode"), "Model");
                    var cardNode = Read(h, "CardNode") as Node;
                    var cost = cardNode?.GetNodeOrNull<Label>("%EnergyLabel");
                    return new {
                        instance_id = InstanceId(card), id = Read(card, "Id")?.ToString(),
                        visible = h is CanvasItem item && item.IsVisibleInTree(), clickable = Field(h, "_isClickable"),
                        shown_cost = cost?.Text, cost_visible = cost?.IsVisibleInTree()
                    };
                }).ToArray()
            };
        }
        catch (Exception ex) { return new { unavailable = true, error_type = ex.GetType().Name }; }
    }
}
