extends SceneTree

const LAYER_PATHS := [
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_00_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_01_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_02_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_03_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_fg_a.tscn",
]
const REQUIRED_NODES := {
	"gravetide_slug_boss_encounter_bg_00_a.tscn": ["FarEnvironmentArt"],
	"gravetide_slug_boss_encounter_bg_01_a.tscn": [],
	"gravetide_slug_boss_encounter_bg_02_a.tscn": ["WaterSurfaceArt", "WaterReflection"],
	"gravetide_slug_boss_encounter_bg_03_a.tscn": [
		"LowTideMist", "SaltMotes", "TideBubbles"
	],
	"gravetide_slug_boss_encounter_fg_a.tscn": [],
}


func _initialize() -> void:
	for path: String in LAYER_PATHS:
		var packed := ResourceLoader.load(path, "PackedScene") as PackedScene
		if packed == null:
			printerr("Gravetide background layer failed to load: %s" % path)
			quit(2)
			return
		var instance := packed.instantiate()
		if not instance is Control:
			printerr("Gravetide background layer root is not Control: %s" % path)
			quit(3)
			return
		for node_path: String in REQUIRED_NODES[path.get_file()]:
			if instance.get_node_or_null(node_path) == null:
				printerr("Gravetide background layer is missing %s: %s" % [node_path, path])
				quit(3)
				return
		instance.free()

	var material := ResourceLoader.load(
		"res://materials/backgrounds/gravetide_slug_water_reflection.tres",
		"ShaderMaterial",
	) as ShaderMaterial
	if material == null or material.shader == null:
		printerr("Gravetide water reflection material failed to load")
		quit(4)
		return
	var water_mask := material.get_shader_parameter("mask") as Texture2D
	var water_noise := material.get_shader_parameter("noise") as Texture2D
	if (
		water_mask == null
		or Vector2i(water_mask.get_width(), water_mask.get_height()) != Vector2i(2768, 1296)
		or water_noise == null
		or not is_equal_approx(float(material.get_shader_parameter("speed")), 0.08)
		or not is_equal_approx(float(material.get_shader_parameter("strength")), 0.02)
	):
		printerr("Gravetide water reflection mask/noise contract is invalid")
		quit(5)
		return

	print("GRAVETIDE_BACKGROUND_LAYER_VERIFY_PASS")
	quit(0)
