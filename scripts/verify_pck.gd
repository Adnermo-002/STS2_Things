extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		_fail("usage: verify_pck.gd <absolute-pck-path>")
		_finish()
		return

	var pck_path := args[0]
	if not ProjectSettings.load_resource_pack(pck_path, true):
		_fail("could not mount PCK: %s" % pck_path)
		_finish()
		return

	var background_slugs := [
		"gravetide_slug_boss_encounter",
		"origin_fogmog_boss_encounter",
		"scale_beetle_boss_encounter",
		"the_legacy_boss_encounter",
		"bowlbug_progenitor_boss_encounter",
		"cave_god_boss_encounter",
	]
	for slug in background_slugs:
		_verify_background(slug)

	_verify_texture("res://images/powers/things_quirk_power.png", Vector2i(256, 256))
	_verify_texture("res://images/powers/things_quirk_power_packed.png", Vector2i(64, 64))
	_verify_texture("res://images/powers/quirky_flutter_power.png", Vector2i(256, 256))
	_verify_texture("res://images/powers/quirky_flutter_power_packed.png", Vector2i(64, 64))
	var card_portraits := [
		"res://images/packed/card_portraits/defect/things_reuse.png",
		"res://images/packed/card_portraits/ironclad/things_collision.png",
		"res://images/packed/card_portraits/silent/things_pack_up.png",
		"res://images/packed/card_portraits/silent/things_recall.png",
		"res://images/packed/card_portraits/silent/soulfysh_disease.png",
	]
	for portrait_path in card_portraits:
		_verify_texture(portrait_path, Vector2i(1000, 760))
	for merchant_hand in [
		["res://images/ui/merchant_bargain/merchant_paper.png", 360],
		["res://images/ui/merchant_bargain/merchant_rock.png", 320],
		["res://images/ui/merchant_bargain/merchant_scissors.png", 360],
	]:
		_verify_texture_visible_width(
			merchant_hand[0],
			Vector2i(422, 1200),
			merchant_hand[1],
		)
	_verify_absent("res://images/relics/energy_bottle.png")
	_verify_absent("res://images/atlases/relic_atlas.sprites/energy_bottle.tres")
	_verify_absent(
		"res://images/atlases/relic_outline_atlas.sprites/energy_bottle.tres"
	)
	_verify_texture(
		"res://images/events/cutting_it_close.png",
		Vector2i(3440, 1616),
	)
	_verify_texture(
		"res://images/enchantments/things_split.png",
		Vector2i(64, 64),
	)
	_verify_event_localization("eng")
	_verify_event_localization("zhs")
	_verify_texture(
		"res://STS2_Things/animations/monsters/quirky_hopper/quirkyhopper.png",
		Vector2i(1269, 269),
	)
	_verify_texture(
		"res://STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_bow.png",
		Vector2i(141, 91),
	)
	_verify_file("res://scenes/creature_visuals/quirky_hopper.tscn")
	_verify_texture(
		"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.png",
		Vector2i(3132, 608),
	)
	_verify_file(
		"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.spatlas"
	)
	_verify_file(
		"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug_skel_data.tres"
	)
	_verify_file("res://scenes/creature_visuals/gravetide_slug.tscn")
	_verify_file("res://animations/monsters/cave_god/cave_god.spatlas")
	_verify_file("res://animations/monsters/cave_god/cave_god.spskel")
	_verify_file("res://animations/monsters/cave_god/cave_god_skeleton_data.tres")
	_verify_file("res://scenes/creature_visuals/things_cave_god.tscn")
	_verify_file("res://scenes/creature_visuals/things_cave_god_left_hand.tscn")
	_verify_file("res://scenes/creature_visuals/things_cave_god_right_hand.tscn")
	if _verify_csharp_placeholder_tree("res://STS2_Things") == 0:
		_fail("PCK exposes no C# script placeholders under res://STS2_Things")

	_finish()


func _verify_background(slug: String) -> void:
	var root := "res://scenes/backgrounds/%s" % slug
	var main_scene := "%s/%s_background.tscn" % [root, slug]
	if not FileAccess.file_exists(main_scene):
		_fail("missing background scene in PCK: %s" % main_scene)

	var layer_dir_path := "%s/layers" % root
	var layer_dir := DirAccess.open(layer_dir_path)
	if layer_dir == null:
		_fail("missing background layer directory in PCK: %s" % layer_dir_path)
		return

	var layer_count := 0
	layer_dir.list_dir_begin()
	var entry := layer_dir.get_next()
	while not entry.is_empty():
		if layer_dir.current_is_dir():
			_fail("unexpected subdirectory in background layers: %s/%s" % [layer_dir_path, entry])
		elif entry.ends_with(".remap"):
			_fail("runtime directory exposes unloadable remap entry: %s/%s" % [layer_dir_path, entry])
		elif not entry.ends_with(".tscn"):
			_fail("unexpected background layer entry: %s/%s" % [layer_dir_path, entry])
		else:
			layer_count += 1
			var scene_path := "%s/%s" % [layer_dir_path, entry]
			var resource := ResourceLoader.load(scene_path, "PackedScene")
			if not resource is PackedScene:
				_fail("background layer is not loadable as PackedScene: %s" % scene_path)
		entry = layer_dir.get_next()
	layer_dir.list_dir_end()

	if layer_count == 0:
		_fail("background has no loadable layer scenes: %s" % slug)


func _verify_texture(path: String, expected_size: Vector2i) -> void:
	var resource := ResourceLoader.load(path, "Texture2D")
	if not resource is Texture2D:
		_fail("texture is not loadable as Texture2D: %s" % path)
		return

	var texture := resource as Texture2D
	var actual_size := Vector2i(texture.get_width(), texture.get_height())
	if actual_size != expected_size:
		_fail("texture has size %s, expected %s: %s" % [actual_size, expected_size, path])


func _verify_texture_visible_width(
	path: String,
	expected_size: Vector2i,
	minimum_visible_width: int,
) -> void:
	_verify_texture(path, expected_size)
	var texture := ResourceLoader.load(path, "Texture2D") as Texture2D
	if texture == null:
		return
	var image := texture.get_image()
	var visible_bounds := image.get_used_rect()
	if visible_bounds.size.x < minimum_visible_width:
		_fail(
			"texture visible width is %d, expected at least %d: %s"
			% [visible_bounds.size.x, minimum_visible_width, path]
		)
	var cuff_color := image.get_pixel(211, 610)
	if cuff_color.a < 0.95 or cuff_color.g >= 0.55 or cuff_color.b <= cuff_color.g * 1.35:
		_fail("merchant sleeve is absent at the top-edge sample: %s" % path)
	if path.ends_with("merchant_rock.png"):
		for y in range(0, 160):
			for x in range(40, 310):
				var color := image.get_pixel(x, y)
				if (
					color.a > 0.2
					and color.r > 0.72
					and color.g > 0.68
					and color.b > 0.62
				):
					_fail(
						"dorsal rock fist exposes a four-finger nail at (%d, %d): %s"
						% [x, y, path]
					)
					return


func _verify_absent(path: String) -> void:
	if ResourceLoader.exists(path) or FileAccess.file_exists(path):
		_fail("unpublished asset is present in PCK: %s" % path)


func _verify_event_localization(language: String) -> void:
	var path := "res://STS2_Things/localization/%s/events.json" % language
	if not FileAccess.file_exists(path):
		_fail("missing event localization table in PCK: %s" % path)
		return

	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_fail("could not open Cutting It Close localization table in PCK: %s" % path)
		return
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		_fail("Cutting It Close localization table is not valid JSON: %s" % path)
		return

	var table := parsed as Dictionary
	var expected_prefix_counts := {
		"ROBBERY_FAKE_MERCHANT.": 13,
		"THINGS_BACKROOMS.": 22,
		"THINGS_MEDUSA.": 15,
		"CUTTING_IT_CLOSE.": 11,
	}
	for prefix in expected_prefix_counts:
		var actual_count := 0
		for key in table:
			if str(key).begins_with(prefix):
				actual_count += 1
		if actual_count != expected_prefix_counts[prefix]:
			_fail(
				"unexpected %s localization key count in %s: %d"
				% [prefix, path, actual_count]
			)

	if table.has("ROBBERY_FAKE_MERCHANT.pages.TAKERGOLDS.description"):
		_fail("stale fake-merchant gold result key remains in %s" % path)

	var required_fragments := {}
	if language == "eng":
		required_fragments = {
			"ROBBERY_FAKE_MERCHANT.pages.INITIAL.description": "LOWEST PRICES IN THE SPIRE",
			"ROBBERY_FAKE_MERCHANT.pages.TAKEGOLDS.description": "real gold",
			"THINGS_BACKROOMS.pages.SEARCH_FAIL.description": "This place is learning you.",
			"THINGS_MEDUSA.pages.GREET.description": "Courtesy repaid.",
		}
	else:
		required_fragments = {
			"ROBBERY_FAKE_MERCHANT.pages.INITIAL.description": "全塔最低价",
			"ROBBERY_FAKE_MERCHANT.pages.TAKEGOLDS.description": "真金子",
			"THINGS_BACKROOMS.pages.SEARCH_FAIL.description": "这里正一点点记住你。",
			"THINGS_MEDUSA.pages.GREET.description": "礼尚往来。",
		}
	for key in required_fragments:
		if not table.has(key) or not str(table[key]).contains(required_fragments[key]):
			_fail("event localization is stale for %s in %s" % [key, path])

	_verify_event_narrative_wraps(table, path)

	var required_placeholders := {
		"ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.TAKERELICS.description": ["{FakeRelicsCount}"],
		"ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.TAKEGOLDS.description": ["{GoldsCount}"],
		"ROBBERY_FAKE_MERCHANT.pages.INITIAL.options.BEGINFIGHT.description": ["{TrueRelicsCount}"],
		"THINGS_BACKROOMS.pages.INITIAL.options.SEARCH_EXIT.description": ["{HpLoss}", "{SearchChance}"],
		"THINGS_BACKROOMS.pages.INITIAL.options.REST.description": ["{MaxHpLoss}", "{Heal}"],
		"THINGS_BACKROOMS.pages.SEARCH_FAIL.options.SEARCH_EXIT.description": ["{HpLoss}", "{SearchChance}"],
		"THINGS_BACKROOMS.pages.SEARCH_FAIL.options.REST.description": ["{MaxHpLoss}", "{Heal}"],
		"THINGS_BACKROOMS.pages.EXIT.options.ENCHANT_DISSOLVE.description": ["{Cards}"],
		"THINGS_MEDUSA.pages.INITIAL.options.OFFER_GOLD.description": ["{Gold}"],
		"THINGS_MEDUSA.pages.INITIAL.options.OFFER_GOLD_LOCKED.description": ["{Gold}"],
		"THINGS_MEDUSA.pages.OFFER_GOLD.description": ["{Gold}"],
	}
	for key in required_placeholders:
		if not table.has(key):
			_fail("missing event localization key %s in %s" % [key, path])
			continue
		var value := str(table[key])
		for placeholder in required_placeholders[key]:
			if not value.contains(placeholder):
				_fail("missing placeholder %s in %s (%s)" % [placeholder, key, path])

	var required_keys := [
		"CUTTING_IT_CLOSE.title",
		"CUTTING_IT_CLOSE.pages.INITIAL.description",
		"CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.title",
		"CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.description",
		"CUTTING_IT_CLOSE.pages.INITIAL.options.THROW.title",
		"CUTTING_IT_CLOSE.pages.INITIAL.options.THROW.description",
		"CUTTING_IT_CLOSE.pages.IMPROVISE.selectionScreenPrompt",
		"CUTTING_IT_CLOSE.pages.THROW.selectionScreenPrompt",
		"CUTTING_IT_CLOSE.pages.ABORTED.description",
		"CUTTING_IT_CLOSE.pages.IMPROVISE.description",
		"CUTTING_IT_CLOSE.pages.THROW.description",
	]
	for key in required_keys:
		if not table.has(key):
			_fail("missing localization key %s in %s" % [key, path])
		elif not table[key] is String or (table[key] as String).strip_edges().is_empty():
			_fail("empty localization key %s in %s" % [key, path])

	var improvise_key := "CUTTING_IT_CLOSE.pages.INITIAL.options.IMPROVISE.description"
	if table.has(improvise_key):
		var description := str(table[improvise_key])
		if not description.contains("{Enchantment}") or not description.contains("[blue]2[/blue]"):
			_fail("improvise option does not describe two enchanted copies in %s" % path)


func _verify_event_narrative_wraps(table: Dictionary, path: String) -> void:
	for key in table:
		var key_text := str(key)
		if not key_text.ends_with(".description") or key_text.contains(".options."):
			continue
		if str(table[key]).contains("\n"):
			_fail(
				"event narrative retains explicit hard line breaks: %s in %s"
				% [key_text, path]
			)


func _verify_file(path: String) -> void:
	if not FileAccess.file_exists(path):
		_fail("missing required file in PCK: %s" % path)


func _verify_csharp_script_placeholder(path: String) -> void:
	if not FileAccess.file_exists(path):
		_fail("missing C# script path placeholder in PCK: %s" % path)
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_fail("could not open C# script path placeholder in PCK: %s" % path)
		return
	if file.get_length() > 1:
		_fail("C# source content leaked into PCK placeholder: %s" % path)


func _verify_csharp_placeholder_tree(root: String) -> int:
	var dir := DirAccess.open(root)
	if dir == null:
		_fail("missing C# placeholder directory in PCK: %s" % root)
		return 0

	var entries: Array[Dictionary] = []
	dir.list_dir_begin()
	var entry := dir.get_next()
	while not entry.is_empty():
		entries.append({"name": entry, "is_dir": dir.current_is_dir()})
		entry = dir.get_next()
	dir.list_dir_end()

	var placeholder_count := 0
	for item in entries:
		var path := "%s/%s" % [root, item["name"]]
		if item["is_dir"]:
			placeholder_count += _verify_csharp_placeholder_tree(path)
		elif path.ends_with(".cs"):
			placeholder_count += 1
			_verify_csharp_script_placeholder(path)
	return placeholder_count


func _fail(message: String) -> void:
	failures.append(message)
	printerr("PCK VERIFY: %s" % message)


func _finish() -> void:
	if failures.is_empty():
		print("STS2_Things PCK runtime asset contract: PASS")
		quit(0)
	else:
		printerr("STS2_Things PCK runtime asset contract: FAIL (%d)" % failures.size())
		quit(1)
