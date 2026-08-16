extends SceneTree

const DATA_PATH := "res://STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_skel_data.tres"
const BOW_PATH := "res://STS2_Things/animations/monsters/quirky_hopper/quirky_hopper_bow.png"
const REQUIRED_ANIMATIONS := [
	"idle_loop",
	"flee",
	"flee_hover",
	"hurt",
	"hurt_hover",
	"attack",
	"attack_hover",
	"die",
	"take_off",
	"hover_loop",
	"steal",
]
const SAMPLES := [
	["idle_loop", 0.0],
	["idle_loop", 0.5],
	["steal", 0.5],
	["take_off", 0.5],
	["hover_loop", 0.5],
	["hurt", 0.5],
	["attack", 0.5],
	["die", 0.0],
	["die", 0.25],
	["die", 0.5],
	["die", 0.75],
	["die", 0.98],
	["flee", 0.5],
]
const VIEWPORT_SIZE := Vector2i(1200, 900)
const BACKGROUND_COLOR := Color("20242a")


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		printerr("usage: render_quirky_hopper_visual_probe.gd OUTPUT_DIR")
		quit(2)
		return

	var output_dir: String = args[0]
	if DirAccess.make_dir_recursive_absolute(output_dir) != OK:
		printerr("could not create output directory: %s" % output_dir)
		quit(3)
		return

	var data = load(DATA_PATH)
	if data == null or not data.is_skeleton_data_loaded():
		printerr("failed to load Quirky Hopper skeleton data")
		quit(4)
		return
	var version: String = str(data.get_version())
	if not version.begins_with("4.2"):
		printerr("expected Spine 4.2 data, got %s" % version)
		quit(5)
		return

	var durations := {}
	for animation_data in data.get_animations():
		durations[animation_data.get_name()] = animation_data.get_duration()
	for animation_name: String in REQUIRED_ANIMATIONS:
		if not durations.has(animation_name) or float(durations[animation_name]) <= 0.0:
			printerr("missing positive-duration animation: %s" % animation_name)
			quit(6)
			return

	var bow_texture = load(BOW_PATH)
	if not bow_texture is Texture2D:
		printerr("failed to load Quirky Hopper bow texture")
		quit(7)
		return

	var viewport := SubViewport.new()
	viewport.size = VIEWPORT_SIZE
	viewport.transparent_bg = false
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.render_target_clear_mode = SubViewport.CLEAR_MODE_ALWAYS
	get_root().add_child(viewport)

	var background := ColorRect.new()
	background.color = BACKGROUND_COLOR
	background.size = Vector2(VIEWPORT_SIZE)
	viewport.add_child(background)

	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.position = Vector2(600.0, 650.0)
	sprite.scale = Vector2(0.425, 0.425)
	viewport.add_child(sprite)

	var bow_bone := SpineBoneNode.new()
	bow_bone.name = "BowBoneNode"
	bow_bone.bone_name = "head"
	bow_bone.show_behind_parent = true
	sprite.add_child(bow_bone)

	var bow := Sprite2D.new()
	bow.name = "Bow"
	bow.position = Vector2(-45.0, 90.0)
	bow.texture = bow_texture
	bow_bone.add_child(bow)

	await process_frame
	await process_frame

	var frames: Array[Dictionary] = []
	for index: int in range(SAMPLES.size()):
		var animation_name: String = SAMPLES[index][0]
		var fraction: float = SAMPLES[index][1]
		var duration: float = float(durations[animation_name])
		var time_seconds: float = min(duration * fraction, max(duration - (1.0 / 120.0), 0.0))
		var file_name := "%02d_%s_%0.2f.png" % [index, animation_name, fraction]
		var output_path := output_dir.path_join(file_name)
		var sample := await _render_sample(
			sprite,
			bow_bone,
			animation_name,
			time_seconds,
			fraction,
			output_path,
		)
		sample["file"] = file_name
		frames.append(sample)

	var report := {
		"version": version,
		"viewport": [VIEWPORT_SIZE.x, VIEWPORT_SIZE.y],
		"background_rgb": [
			int(BACKGROUND_COLOR.r8),
			int(BACKGROUND_COLOR.g8),
			int(BACKGROUND_COLOR.b8),
		],
		"durations": durations,
		"bow_bone": "head",
		"bow_behind_parent": bow_bone.show_behind_parent,
		"frames": frames,
	}
	var report_path := output_dir.path_join("report.json")
	var report_file := FileAccess.open(report_path, FileAccess.WRITE)
	if report_file == null:
		printerr("failed to open visual probe report: %s" % report_path)
		quit(8)
		return
	report_file.store_string(JSON.stringify(report, "  "))
	report_file.close()
	print("QUIRKY_HOPPER_VISUAL_RENDER_PASS frames=%d report=%s" % [frames.size(), report_path])
	quit(0)


func _render_sample(
	sprite: SpineSprite,
	bow_bone: SpineBoneNode,
	animation_name: String,
	time_seconds: float,
	fraction: float,
	output_path: String,
) -> Dictionary:
	var skeleton = sprite.get_skeleton()
	var state = sprite.get_animation_state()
	skeleton.set_to_setup_pose()
	state.clear_tracks()
	var entry = state.set_animation(animation_name, false, 0)
	entry.set_track_time(time_seconds)
	state.update(0.0)
	state.apply(skeleton)
	skeleton.update_world_transform(0)
	sprite.queue_redraw()
	await process_frame
	await RenderingServer.frame_post_draw
	var image := sprite.get_viewport().get_texture().get_image()
	var error := image.save_png(output_path)
	if error != OK:
		printerr("failed to save %s: %s" % [output_path, error])
		quit(9)
	return {
		"animation": animation_name,
		"fraction": fraction,
		"time": time_seconds,
		"bow_global_position": [bow_bone.global_position.x, bow_bone.global_position.y],
		"bow_global_rotation": bow_bone.global_rotation,
	}

