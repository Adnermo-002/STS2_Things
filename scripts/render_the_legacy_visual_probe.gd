extends SceneTree

# Renders frame sequences of The Legacy's native Spine 4.2 rig for review.
# usage: godot --path <project> --script res://scripts/render_the_legacy_visual_probe.gd -- OUTPUT_DIR [FPS]

const DATA_PATH := "res://STS2_Things/animations/monsters/the_legacy/the_legacy_skel_data.tres"
const REQUIRED_ANIMATIONS := [
	"idle_loop", "attack", "cast", "hurt", "die", "summon", "power_up", "revive",
]
const VIEWPORT_SIZE := Vector2i(1000, 560)
const BACKGROUND_COLOR := Color("20242a")


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() < 1:
		printerr("usage: render_the_legacy_visual_probe.gd OUTPUT_DIR [FPS]")
		quit(2)
		return
	var output_dir: String = args[0]
	var fps := 10.0
	if args.size() > 1:
		fps = float(args[1])
	DirAccess.make_dir_recursive_absolute(output_dir)

	var data = load(DATA_PATH)
	if data == null or not data.is_skeleton_data_loaded():
		printerr("failed to load The Legacy skeleton data")
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
	sprite.position = Vector2(500.0, 500.0)
	sprite.scale = Vector2(0.62, 0.62)
	viewport.add_child(sprite)
	await process_frame
	await process_frame

	var count := 0
	for animation_name: String in REQUIRED_ANIMATIONS:
		var duration: float = float(durations[animation_name])
		var n := int(floor(duration * fps + 0.0001)) + 1
		for i in range(n):
			var t: float = min(i / fps, duration - 1.0 / 240.0)
			var skeleton = sprite.get_skeleton()
			var state = sprite.get_animation_state()
			skeleton.set_to_setup_pose()
			state.clear_tracks()
			var entry = state.set_animation(animation_name, false, 0)
			entry.set_track_time(t)
			state.update(0.0)
			state.apply(skeleton)
			skeleton.update_world_transform(0)
			sprite.queue_redraw()
			await process_frame
			await RenderingServer.frame_post_draw
			var image := viewport.get_texture().get_image()
			image.save_png(output_dir.path_join("%s_%03d.png" % [animation_name, i]))
			count += 1
	var report := {"version": version, "durations": durations, "frames": count, "fps": fps}
	var f := FileAccess.open(output_dir.path_join("report.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify(report, "  "))
	f.close()
	print("THE_LEGACY_VISUAL_RENDER_PASS frames=%d" % count)
	quit(0)
