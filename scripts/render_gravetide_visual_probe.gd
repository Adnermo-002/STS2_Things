extends SceneTree

const VIEWPORT_SIZE := Vector2i(1920, 1080)
const ENCOUNTER_SCENE := \
	"res://scenes/encounters/gravetide_slug_boss_encounter.tscn"
const BOSS_SKELETON_DATA := \
	"res://STS2_Things/animations/monsters/gravetide_slug/gravetide_slug_skel_data.tres"
const MINION_SKELETON_DATA := \
	"res://animations/monsters/corpse_slug/corpse_slug_skel_data.tres"
const CORPSE_TEXTURE := "res://images/monsters/gravetide_slug_corpse.png"
const BACKGROUND_LAYERS := [
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_00_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_01_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_02_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_bg_03_a.tscn",
	"res://scenes/backgrounds/gravetide_slug_boss_encounter/layers/gravetide_slug_boss_encounter_fg_a.tscn",
]


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2 and args.size() != 3:
		printerr(
			"usage: render_gravetide_visual_probe.gd [GAME_PCK] MOD_PCK OUTPUT_DIR"
		)
		quit(2)
		return

	var game_pck := ""
	var mod_pck: String
	var output_dir: String
	if args.size() == 3:
		game_pck = args[0]
		mod_pck = args[1]
		output_dir = args[2]
	else:
		mod_pck = args[0]
		output_dir = args[1]
	if not ResourceLoader.exists(MINION_SKELETON_DATA):
		if game_pck.is_empty() or not ProjectSettings.load_resource_pack(game_pck, false):
			printerr("could not mount game PCK: %s" % game_pck)
			quit(3)
			return
	if not ProjectSettings.load_resource_pack(mod_pck, true):
		printerr("could not mount mod PCK: %s" % mod_pck)
		quit(3)
		return
	if DirAccess.make_dir_recursive_absolute(output_dir) != OK:
		printerr("could not create output directory: %s" % output_dir)
		quit(4)
		return

	var viewport := SubViewport.new()
	viewport.size = VIEWPORT_SIZE
	viewport.transparent_bg = false
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
	root.add_child(viewport)

	var canvas := Control.new()
	canvas.size = Vector2(VIEWPORT_SIZE)
	viewport.add_child(canvas)
	var background_origin := Control.new()
	background_origin.position = Vector2(VIEWPORT_SIZE) * 0.5 + Vector2(23, 0)
	canvas.add_child(background_origin)
	for layer_path: String in BACKGROUND_LAYERS:
		background_origin.add_child(_instantiate(layer_path))
	print("GRAVETIDE_VISUAL_STAGE background_ready")

	var layout := _instantiate(ENCOUNTER_SCENE) as Control
	layout.size = Vector2(VIEWPORT_SIZE)
	viewport.add_child(layout)
	print("GRAVETIDE_VISUAL_STAGE encounter_ready")

	print("GRAVETIDE_VISUAL_STAGE loading_boss_skeleton")
	var boss_skeleton_data := load(BOSS_SKELETON_DATA)
	if boss_skeleton_data == null:
		printerr("failed to load skeleton data: %s" % BOSS_SKELETON_DATA)
		quit(5)
		return
	print("GRAVETIDE_VISUAL_STAGE boss_skeleton_ready")
	print("GRAVETIDE_VISUAL_STAGE loading_minion_skeleton")
	var minion_skeleton_data := load(MINION_SKELETON_DATA)
	if minion_skeleton_data == null:
		printerr("failed to load skeleton data: %s" % MINION_SKELETON_DATA)
		quit(5)
		return
	print("GRAVETIDE_VISUAL_STAGE minion_skeleton_ready")

	print("GRAVETIDE_VISUAL_STAGE creating_boss")
	var boss := _create_spine(boss_skeleton_data, Vector2(0.58, 0.58))
	boss.position = layout.get_node("gravetide_slug").position + Vector2(-15, -28)
	viewport.add_child(boss)
	print("GRAVETIDE_VISUAL_STAGE boss_added")

	var opening_slugs: Array[SpineSprite] = []
	for slot_name: String in [
		"gravetide_corpse_slug_1",
		"gravetide_corpse_slug_6",
	]:
		var slug := _create_spine(minion_skeleton_data, Vector2(0.23, 0.23))
		slug.position = layout.get_node(slot_name).position + Vector2(-6, -27)
		viewport.add_child(slug)
		opening_slugs.append(slug)
	print("GRAVETIDE_VISUAL_STAGE minions_added")

	await _wait_for_spine_and_play(boss, "idle_loop")
	print("GRAVETIDE_VISUAL_STAGE boss_animation_ready")
	for slug: SpineSprite in opening_slugs:
		await _wait_for_spine_and_play(slug, "idle_loop")
	print("GRAVETIDE_VISUAL_STAGE minion_animations_ready")
	await _save_viewport(viewport, output_dir.path_join("opening.png"))

	for slug: SpineSprite in opening_slugs:
		slug.queue_free()
	await process_frame

	var corpse_texture := load(CORPSE_TEXTURE) as Texture2D
	if corpse_texture == null:
		printerr("failed to load corpse texture: %s" % CORPSE_TEXTURE)
		quit(6)
		return
	for index: int in range(1, 7):
		var corpse := Sprite2D.new()
		corpse.texture = corpse_texture
		corpse.scale = Vector2(0.5, 0.5)
		corpse.position = (
			layout.get_node("gravetide_corpse_slug_%d" % index).position + Vector2(-14, -39)
		)
		viewport.add_child(corpse)
	await _save_viewport(viewport, output_dir.path_join("six_corpse_slots.png"))

	print("GRAVETIDE_VISUAL_RENDER_PASS output=%s" % output_dir)
	quit(0)


func _instantiate(path: String) -> Node:
	var packed := load(path) as PackedScene
	if packed == null:
		printerr("failed to load scene: %s" % path)
		quit(5)
		return Node.new()
	return packed.instantiate()


func _create_spine(skeleton_data: Resource, scale_value: Vector2) -> SpineSprite:
	var spine := SpineSprite.new()
	spine.skeleton_data_res = skeleton_data
	spine.scale = scale_value
	return spine


func _wait_for_spine_and_play(spine: SpineSprite, animation: String) -> void:
	for _frame: int in range(180):
		var state := spine.call("get_animation_state") as Object
		if state != null:
			state.call("set_animation", animation, true, 0)
			return
		await process_frame
	printerr("Spine did not initialize for %s" % spine.name)
	quit(7)


func _save_viewport(viewport: SubViewport, path: String) -> void:
	# A few process frames are enough for this always-updating viewport to retire
	# its first graphical render without waiting on the unreliable headless signal.
	for _frame: int in range(3):
		await process_frame
	var image := viewport.get_texture().get_image()
	if image == null:
		printerr("SubViewport did not expose a readable render target")
		quit(8)
		return
	var error := image.save_png(path)
	if error != OK:
		printerr("failed to save %s: %s" % [path, error_string(error)])
		quit(8)
