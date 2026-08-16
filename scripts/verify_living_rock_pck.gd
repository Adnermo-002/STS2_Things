extends SceneTree

const DATA_PATH := "res://STS2_Things/animations/monsters/living_rock/living_rock_skel_data.tres"
const CREATURE_SCENE_PATH := "res://scenes/creature_visuals/living_rock.tscn"
const ENCOUNTER_SCENE_PATH := "res://scenes/encounters/living_rock_boss_encounter.tscn"
const REQUIRED_FILES := [
	"res://STS2_Things/animations/monsters/living_rock/living_rock.skel",
	"res://STS2_Things/animations/monsters/living_rock/living_rock.spskel",
	"res://STS2_Things/animations/monsters/living_rock/living_rock.atlas",
	"res://STS2_Things/animations/monsters/living_rock/living_rock.spatlas",
	DATA_PATH,
	CREATURE_SCENE_PATH,
	ENCOUNTER_SCENE_PATH,
]
const REQUIRED_MAP_TEXTURES := [
	"res://images/map/living_rock_boss_icon.png",
	"res://images/map/living_rock_boss_icon_outline.png",
]
const REQUIRED_ANIMATIONS := [
	"arrive",
	"earthquake",
	"hide",
	"hide_angry",
	"leftpunch",
	"main_01",
	"main_01_angry",
	"main_angry",
	"main_happy",
	"walk",
	"rightpunch",
	"main_01_left_to_right",
	"main_01_right_to_left",
]
const REQUIRED_REGIONS := [
	"arm1_1", "arm1_2", "arm1_2_back", "arm1_2_back_red", "arm1_2_red",
	"arm1_3", "arm1_3_2", "arm2_1", "arm2_2", "arm2_2_red", "arm2_3",
	"arm2_3_2", "beard1", "beard1_red", "beard2", "beard2_red", "beard3",
	"beard3_red", "body", "body_bottom", "body_red", "crastalls_roof",
	"crastalls_roof_red", "eyes", "eyes_red", "head", "head_red", "head_skale",
	"head_skale_red", "horn1", "horn1_red", "horn2", "horn2_red", "neck", "neck_red",
]

var failures: Array[String] = []


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1 or not ProjectSettings.load_resource_pack(args[0], true):
		_fail("usage: verify_living_rock_pck.gd ABSOLUTE_PCK")
		_finish()
		return
	for path: String in REQUIRED_FILES:
		if not FileAccess.file_exists(path):
			_fail("missing PCK asset: %s" % path)
	for texture_path: String in REQUIRED_MAP_TEXTURES:
		var map_texture := ResourceLoader.load(texture_path, "Texture2D") as Texture2D
		if map_texture == null or map_texture.get_size() != Vector2(779, 652):
			_fail("invalid Living Rock map texture: %s" % texture_path)
	var atlas_texture := ResourceLoader.load(
		"res://STS2_Things/animations/monsters/living_rock/living_rock.png",
		"Texture2D"
	) as Texture2D
	if atlas_texture == null or atlas_texture.get_size() != Vector2(2033, 1734):
		_fail("invalid Living Rock atlas page")
	_verify_atlas()
	_verify_spine_data()
	_verify_creature_scene()
	_verify_encounter_scene()
	_verify_localization()
	_finish()


func _verify_atlas() -> void:
	var atlas := _read_text("res://STS2_Things/animations/monsters/living_rock/living_rock.atlas")
	if atlas.count("living_rock.png") != 1:
		_fail("atlas must declare exactly one Living Rock page")
	if not atlas.contains("size: 2033,1734"):
		_fail("atlas page dimensions drifted")
	for region: String in REQUIRED_REGIONS:
		if not atlas.contains("\n%s\n" % region):
			_fail("atlas is missing attachment region: %s" % region)


func _verify_spine_data() -> void:
	var data = load(DATA_PATH)
	if data == null or not data.is_skeleton_data_loaded():
		_fail("Spine skeleton data did not load")
		return
	if not str(data.get_version()).begins_with("4.2.43"):
		_fail("unexpected Spine version: %s" % data.get_version())
	var durations := {}
	for animation in data.get_animations():
		durations[animation.get_name()] = animation.get_duration()
	if durations.size() != 13:
		_fail("expected 13 animations, found %d" % durations.size())
	for animation_name: String in REQUIRED_ANIMATIONS:
		if not durations.has(animation_name) or float(durations[animation_name]) <= 0.0:
			_fail("missing positive-duration animation: %s" % animation_name)
	if absf(float(durations.get("main_01_left_to_right", 0.0)) - 5.0) > 0.001:
		_fail("left-to-right idle duration drifted")
	if absf(float(durations.get("main_01_right_to_left", 0.0)) - 5.0) > 0.001:
		_fail("right-to-left idle duration drifted")
	if absf(float(durations.get("leftpunch", 0.0)) - 4.4) > 0.001 \
		or absf(float(durations.get("rightpunch", 0.0)) - 4.4) > 0.001:
		_fail("punch duration drifted")
	if data.get_bones().size() != 25:
		_fail("expected 25 bones, found %d" % data.get_bones().size())
	if data.get_slots().size() != 34:
		_fail("expected 34 slots, found %d" % data.get_slots().size())


func _verify_creature_scene() -> void:
	var scene := ResourceLoader.load(CREATURE_SCENE_PATH, "PackedScene") as PackedScene
	if scene == null:
		_fail("Living Rock creature scene did not load")
		return
	var scene_text := _read_text(CREATURE_SCENE_PATH)
	if not scene_text.contains('[node name="Visuals" type="SpineSprite" parent="."]'):
		_fail("Living Rock scene lacks SpineSprite visuals")
	if not scene_text.contains('[node name="Bounds" type="Control" parent="."]') \
		or not scene_text.contains("offset_left = -390.0") \
		or not scene_text.contains("offset_top = -690.0") \
		or not scene_text.contains("offset_right = 390.0") \
		or not scene_text.contains("offset_bottom = 75.0"):
		_fail("Living Rock Bounds do not cover the body")
	if not scene_text.contains('[node name="CenterPos" type="Marker2D" parent="."]') \
		or not scene_text.contains("position = Vector2(0, -300)") \
		or not scene_text.contains('[node name="IntentPos" type="Marker2D" parent="."]') \
		or not scene_text.contains("position = Vector2(0, -690)"):
		_fail("Living Rock center/intent marker contract is invalid")


func _verify_encounter_scene() -> void:
	var scene := ResourceLoader.load(ENCOUNTER_SCENE_PATH, "PackedScene") as PackedScene
	if scene == null:
		_fail("Living Rock encounter scene did not load")
		return
	var encounter := scene.instantiate()
	var slot := encounter.get_node_or_null("living_rock") as Marker2D
	if slot == null or not slot.position.is_equal_approx(Vector2(1440, 760)):
		_fail("Living Rock encounter slot is invalid")
	encounter.free()


func _verify_localization() -> void:
	for language: String in ["eng", "zhs"]:
		var monster_json = JSON.parse_string(_read_text(
			"res://STS2_Things/localization/%s/monsters.json" % language
		))
		var encounter_json = JSON.parse_string(_read_text(
			"res://STS2_Things/localization/%s/encounters.json" % language
		))
		for key: String in [
			"THINGS_LIVING_ROCK.name",
			"THINGS_LIVING_ROCK.moves.LEFT_PUNCH.title",
			"THINGS_LIVING_ROCK.moves.RIGHT_PUNCH.title",
		]:
			if not monster_json is Dictionary or not monster_json.has(key):
				_fail("missing monster localization %s: %s" % [language, key])
		for key: String in [
			"LIVING_ROCK_BOSS_ENCOUNTER.title",
			"LIVING_ROCK_BOSS_ENCOUNTER.loss",
		]:
			if not encounter_json is Dictionary or not encounter_json.has(key):
				_fail("missing encounter localization %s: %s" % [language, key])


func _read_text(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	return "" if file == null else file.get_as_text()


func _fail(message: String) -> void:
	failures.append(message)
	printerr("LIVING_ROCK_PCK_VERIFY: %s" % message)


func _finish() -> void:
	if failures.is_empty():
		print("LIVING_ROCK_PCK_VERIFY_PASS")
		quit(0)
	else:
		printerr("LIVING_ROCK_PCK_VERIFY_FAIL count=%d" % failures.size())
		quit(1)
