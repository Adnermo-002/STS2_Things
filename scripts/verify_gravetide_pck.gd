extends SceneTree

const EXPECTED_FILES := [
	"res://scenes/creature_visuals/gravetide_slug.tscn",
	"res://scenes/creature_visuals/gravetide_slug_corpse.tscn",
	"res://scenes/encounters/gravetide_slug_boss_encounter.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/gravetide_slug_boss_encounter_background.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_00_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_01_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_02_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_03_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_fg_a.tscn",
	"res://materials/backgrounds/gravetide_slug_water_reflection.tres",
	"res://images/backgrounds/gravetide_slug/gravetide_slug_far.png",
	"res://images/backgrounds/gravetide_slug/gravetide_slug_water.png",
	"res://images/map/gravetide_slug_boss_icon.png",
	"res://images/map/gravetide_slug_boss_icon_outline.png",
	"res://images/ui/run_history/gravetide_slug_boss_encounter.png",
	"res://images/ui/run_history/gravetide_slug_boss_encounter_outline.png",
	"res://images/powers/gravetide_digestion_power.png",
	"res://images/powers/gravetide_digestion_power_packed.png",
	"res://images/atlases/power_atlas.sprites/gravetide_digestion_power.tres",
	"res://images/monsters/gravetide_slug_corpse.png",
	"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.png",
	"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.spatlas",
	"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug_skel_data.tres",
	"res://music/gravetide_slug/gravetide_slug_boss_theme.wav",
	"res://sfx/gravetide_slug/gravetide_slug_attack_light-01.wav",
	"res://sfx/gravetide_slug/gravetide_slug_attack_light-02.wav",
	"res://sfx/gravetide_slug/gravetide_slug_attack_light-03.wav",
	"res://sfx/gravetide_slug/gravetide_slug_attack-01.wav",
	"res://sfx/gravetide_slug/gravetide_slug_attack-02.wav",
	"res://sfx/gravetide_slug/gravetide_slug_hurt-01.wav",
	"res://sfx/gravetide_slug/gravetide_slug_hurt-02.wav",
	"res://sfx/gravetide_slug/gravetide_slug_hurt-03.wav",
	"res://sfx/gravetide_slug/gravetide_slug_hurt-04.wav",
	"res://sfx/gravetide_slug/gravetide_slug_die-01.wav",
	"res://sfx/gravetide_slug/gravetide_slug_die-02.wav",
	"res://sfx/gravetide_slug/gravetide_slug_devour-01.wav",
	"res://sfx/gravetide_slug/gravetide_slug_devour-02.wav",
	"res://sfx/gravetide_slug/gravetide_slug_devour_end-01.wav",
	"res://sfx/gravetide_slug/gravetide_slug_devour_end-02.wav",
]
const BACKGROUND_ROOT := (
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/"
)
const BACKGROUND_LAYERS := {
	"layers/gravetide_slug_boss_encounter_bg_00_a.tscn": "GravetideSlugFarBackground",
	"layers/gravetide_slug_boss_encounter_bg_01_a.tscn": "GravetideSlugNarrativeMidground",
	"layers/gravetide_slug_boss_encounter_bg_02_a.tscn": "GravetideSlugTideSurface",
	"layers/gravetide_slug_boss_encounter_bg_03_a.tscn": "GravetideSlugAtmosphere",
	"layers/gravetide_slug_boss_encounter_fg_a.tscn": "GravetideSlugForeground",
}
const BACKGROUND_LAYER_NODES := {
	"layers/gravetide_slug_boss_encounter_bg_00_a.tscn": ["FarEnvironmentArt"],
	"layers/gravetide_slug_boss_encounter_bg_01_a.tscn": [],
	"layers/gravetide_slug_boss_encounter_bg_02_a.tscn": [
		"WaterSurfaceArt", "WaterReflection"
	],
	"layers/gravetide_slug_boss_encounter_bg_03_a.tscn": [
		"LowTideMist", "SaltMotes", "TideBubbles"
	],
	"layers/gravetide_slug_boss_encounter_fg_a.tscn": [],
}
const REQUIRED_SLOTS := [
	"gravetide_slug",
	"gravetide_corpse_slug_1",
	"gravetide_corpse_slug_2",
	"gravetide_corpse_slug_3",
	"gravetide_corpse_slug_4",
	"gravetide_corpse_slug_5",
	"gravetide_corpse_slug_6",
]
const REQUIRED_MONSTER_LOCALIZATION_KEYS := [
	"GRAVETIDE_SLUG.name",
	"GRAVETIDE_SLUG.moves.GROW.title",
	"GRAVETIDE_CORPSE_SLUG.name",
	"GRAVETIDE_SLUG_CORPSE.name",
]


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1 or not ProjectSettings.load_resource_pack(args[0], true):
		printerr("usage: verify_gravetide_pck.gd ABSOLUTE_PCK")
		quit(2)
		return

	for path: String in EXPECTED_FILES:
		var exists := FileAccess.file_exists(path)
		if path.ends_with(".png"):
			exists = ResourceLoader.load(path, "Texture2D") != null
		elif path.ends_with(".wav"):
			exists = ResourceLoader.load(path, "AudioStream") != null
		if not exists:
			printerr("missing Gravetide asset: %s" % path)
			quit(3)
			return

	for language: String in ["eng", "zhs"]:
		var localization_path := "res://STS2_Things/localization/%s/monsters.json" % language
		var parsed_localization: Variant = JSON.parse_string(_read_text(localization_path))
		if not parsed_localization is Dictionary:
			printerr("Gravetide monster localization is invalid: %s" % localization_path)
			quit(3)
			return
		var localization: Dictionary = parsed_localization
		for key: String in REQUIRED_MONSTER_LOCALIZATION_KEYS:
			if not localization.has(key) or String(localization[key]).is_empty():
				printerr("Gravetide monster localization is missing %s: %s" % [key, localization_path])
				quit(3)
				return

	var background_scene_text := _read_text(
		BACKGROUND_ROOT + "gravetide_slug_boss_encounter_background.tscn"
	)
	if not background_scene_text.contains("NThingsCombatBackground.cs"):
		printerr("Gravetide background does not use the native NCombatBackground shell")
		quit(4)
		return
	for container_name: String in [
		"Layer_00", "Layer_01", "Layer_02", "Layer_03", "Foreground"
	]:
		if not background_scene_text.contains('[node name="%s"' % container_name):
			printerr("Gravetide background is missing native container: %s" % container_name)
			quit(5)
			return

	for relative_path: String in BACKGROUND_LAYERS:
		var layer_path := BACKGROUND_ROOT + relative_path
		var layer_scene := ResourceLoader.load(layer_path, "PackedScene") as PackedScene
		if layer_scene == null:
			printerr("Gravetide background layer is not loadable: %s" % layer_path)
			quit(6)
			return
		var layer := layer_scene.instantiate()
		if not layer is Control or layer.name != StringName(BACKGROUND_LAYERS[relative_path]):
			printerr("Gravetide background layer has an invalid Control root: %s" % layer_path)
			quit(7)
			return
		for node_path: String in BACKGROUND_LAYER_NODES[relative_path]:
			if layer.get_node_or_null(node_path) == null:
				printerr(
					"Gravetide background layer is missing %s: %s" % [node_path, layer_path]
				)
				quit(7)
				return
		layer.free()

	var water_material := ResourceLoader.load(
		"res://materials/backgrounds/gravetide_slug_water_reflection.tres",
		"ShaderMaterial",
	) as ShaderMaterial
	if water_material == null or water_material.shader == null:
		printerr("Gravetide water reflection material is not loadable")
		quit(8)
		return
	var water_mask := water_material.get_shader_parameter("mask") as Texture2D
	var water_noise := water_material.get_shader_parameter("noise") as Texture2D
	if (
		water_mask == null
		or Vector2i(water_mask.get_width(), water_mask.get_height()) != Vector2i(2768, 1296)
		or water_noise == null
		or not is_equal_approx(float(water_material.get_shader_parameter("speed")), 0.08)
		or not is_equal_approx(float(water_material.get_shader_parameter("strength")), 0.02)
	):
		printerr("Gravetide water reflection material has an invalid mask/noise contract")
		quit(8)
		return
	for background_texture_path: String in [
		"res://images/backgrounds/gravetide_slug/gravetide_slug_far.png",
		"res://images/backgrounds/gravetide_slug/gravetide_slug_water.png",
	]:
		var background_texture := ResourceLoader.load(
			background_texture_path, "Texture2D"
		) as Texture2D
		if (
			background_texture == null
			or Vector2i(background_texture.get_width(), background_texture.get_height())
			!= Vector2i(2768, 1296)
		):
			printerr("Gravetide background texture has an invalid size: %s" % background_texture_path)
			quit(9)
			return

	var texture := ResourceLoader.load(
		"res://images/monsters/gravetide_slug_corpse.png", "Texture2D"
	) as Texture2D
	if texture == null or Vector2i(texture.get_width(), texture.get_height()) != Vector2i(544, 195):
		printerr("Gravetide corpse texture has an invalid runtime size")
		quit(10)
		return
	var boss_atlas_texture := ResourceLoader.load(
		"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug.png",
		"Texture2D",
	) as Texture2D
	if (
		boss_atlas_texture == null
		or Vector2i(boss_atlas_texture.get_width(), boss_atlas_texture.get_height())
		!= Vector2i(3132, 608)
	):
		printerr("Gravetide boss atlas texture has an invalid runtime size")
		quit(10)
		return

	var ui_texture_contracts := {
		"res://images/map/gravetide_slug_boss_icon.png": Vector2i(352, 300),
		"res://images/map/gravetide_slug_boss_icon_outline.png": Vector2i(352, 300),
		"res://images/ui/run_history/gravetide_slug_boss_encounter.png": Vector2i(88, 88),
		"res://images/ui/run_history/gravetide_slug_boss_encounter_outline.png": Vector2i(88, 88),
		"res://images/powers/gravetide_digestion_power.png": Vector2i(256, 256),
		"res://images/powers/gravetide_digestion_power_packed.png": Vector2i(64, 64),
	}
	for ui_path: String in ui_texture_contracts:
		var ui_texture := ResourceLoader.load(ui_path, "Texture2D") as Texture2D
		if (
			ui_texture == null
			or Vector2i(ui_texture.get_width(), ui_texture.get_height())
			!= ui_texture_contracts[ui_path]
		):
			printerr("Gravetide UI texture has an invalid contract: %s" % ui_path)
			quit(10)
			return
	var packed_power := ResourceLoader.load(
		"res://images/atlases/power_atlas.sprites/gravetide_digestion_power.tres",
		"AtlasTexture",
	) as AtlasTexture
	if packed_power == null or packed_power.region.size != Vector2(64, 64):
		printerr("Gravetide packed Power icon is not loadable")
		quit(10)
		return

	for audio_path: String in EXPECTED_FILES.filter(
		func(path: String) -> bool: return path.ends_with(".wav")
	):
		if ResourceLoader.load(audio_path, "AudioStream") == null:
			printerr("Gravetide audio stream is not loadable: %s" % audio_path)
			quit(10)
			return

	var encounter := (
		ResourceLoader.load(
			"res://scenes/encounters/gravetide_slug_boss_encounter.tscn",
			"PackedScene",
		) as PackedScene
	)
	if encounter == null:
		printerr("Gravetide encounter scene is not loadable")
		quit(11)
		return
	var layout := encounter.instantiate()
	for slot_name: String in REQUIRED_SLOTS:
		if layout.get_node_or_null(slot_name) == null:
			printerr("Gravetide encounter is missing slot: %s" % slot_name)
			quit(12)
			return
	var boss_slot := layout.get_node("gravetide_slug") as Marker2D
	if boss_slot == null or not boss_slot.position.is_equal_approx(Vector2(1440, 710)):
		printerr("Gravetide boss is not grounded at its validated encounter position")
		quit(12)
		return
	var expected_slot_positions := {
		"gravetide_corpse_slug_1": Vector2(1070, 735),
		"gravetide_corpse_slug_2": Vector2(1210, 785),
		"gravetide_corpse_slug_3": Vector2(1440, 825),
		"gravetide_corpse_slug_4": Vector2(1360, 775),
		"gravetide_corpse_slug_5": Vector2(1580, 760),
		"gravetide_corpse_slug_6": Vector2(1770, 805),
	}
	for slot_name: String in expected_slot_positions:
		var slot := layout.get_node(slot_name) as Marker2D
		if slot == null or not slot.position.is_equal_approx(expected_slot_positions[slot_name]):
			printerr("Gravetide encounter has unsafe slot position: %s" % slot_name)
			quit(12)
			return
	layout.free()

	print("GRAVETIDE_PCK_VERIFY_PASS")
	quit(0)


func _read_text(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	return file.get_as_text()
