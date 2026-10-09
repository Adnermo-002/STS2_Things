// Both original schema 1 and the diagnostic schema 2 are supported during client rollout.
const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const text = (value, max = 300) => typeof value === "string" && value.length <= max;
const optional = (parent, key, check) => parent[key] === undefined || parent[key] === null || check(parent[key]);
const list = (value, max, check) => Array.isArray(value) && value.length <= max && value.every(check);
const id = value => text(value, 300);
const card = value => typeof value === "string" ? id(value) : object(value) && id(value.id)
  && optional(value, "energy", Number.isFinite) && optional(value, "upgrade", Number.isInteger);
const power = value => typeof value === "string" ? id(value) : object(value) && id(value.id)
  && optional(value, "amount", Number.isFinite);
const choice = value => object(value) && optional(value, "id", id) && optional(value, "key", id)
  && optional(value, "table", id) && optional(value, "picked", v => typeof v === "boolean");

function player(value) {
  return object(value) && optional(value, "character", id) && optional(value, "deck", v => list(v, 1500, card))
    && optional(value, "relics", v => list(v, 500, id)) && optional(value, "potions", v => list(v, 100, x => x === null || id(x)))
    && optional(value, "powers", v => list(v, 500, power)) && optional(value, "combat", combat);
}
function combat(value) {
  return object(value) && ["hand", "draw_pile", "discard_pile", "exhaust_pile", "play_pile"].every(key => optional(value, key, v => list(v, 1500, card)))
    && ["energy", "stars", "turn"].every(key => optional(value, key, Number.isFinite)) && optional(value, "phase", v => text(v, 80));
}
function routePlayer(value) {
  return object(value) && ["event_choices", "card_choices", "relic_choices", "potion_choices"].every(key => optional(value, key, v => list(v, 500, choice)))
    && ["rest_choices", "cards_gained", "cards_removed"].every(key => optional(value, key, v => list(v, 1500, id)));
}
function route(value) {
  return list(value, 20, act => object(act) && Number.isInteger(act.act_index) && list(act.points, 500, point => object(point)
    && optional(point, "rooms", v => list(v, 50, room => object(room) && optional(room, "type", id)
      && optional(room, "model_id", id) && optional(room, "monster_ids", v => list(v, 100, id))))
    && optional(point, "players", v => list(v, 8, routePlayer))));
}
function snapshot(value) {
  return object(value) && optional(value, "seed", v => text(v, 100))
    && optional(value, "acts", v => list(v, 20, id)) && optional(value, "players", v => list(v, 8, player))
    && optional(value, "route", route) && optional(value, "combat", v => object(v) && optional(v, "monsters", m => list(m, 100,
      monster => object(monster) && id(monster.id) && optional(monster, "powers", p => list(p, 500, power)))))
    && optional(value, "ui", v => object(v) && optional(v, "holders", h => list(h, 1500, object)));
}
function boundedTree(value, depth = 0, counter = {count: 0}) {
  if (++counter.count > 30000 || depth > 20) return false;
  if (value === null || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (typeof value === "string") return value.length <= 8000;
  if (Array.isArray(value)) return value.length <= 1500 && value.every(v => boundedTree(v, depth + 1, counter));
  return object(value) && Object.keys(value).length <= 128 && Object.entries(value).every(([key, v]) =>
    key.length <= 150 && !["__proto__", "constructor", "prototype"].includes(key) && boundedTree(v, depth + 1, counter));
}

export function validateReport(p) {
  return object(p) && [1, 2].includes(p.schema) && p.source === "sts2_things"
    && /^[0-9a-f]{32}$/i.test(p.client_report_id ?? "") && text(p.description, 4000) && p.description.trim().length >= 2
    && object(p.run) && [1, 2].includes(p.run.schema) && text(p.run.game_version ?? "unknown", 80)
    && text(p.run.mod_version ?? "unknown", 80)
    && list(p.run.events, 700, event => object(event) && text(event.kind, 100)
      && optional(event, "at", v => text(v, 80)) && optional(event, "detail", v => text(v, 2000) || object(v)))
    && optional(p.run, "active_mods", v => list(v, 300, m => object(m) && id(m.id) && text(m.version, 80)))
    && optional(p.run, "state", snapshot) && optional(p.run, "initial_state", snapshot) && boundedTree(p);
}

export function canonical(value) {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (object(value)) return "{" + Object.keys(value).sort().map(key => JSON.stringify(key) + ":" + canonical(value[key])).join(",") + "}";
  return JSON.stringify(value);
}
