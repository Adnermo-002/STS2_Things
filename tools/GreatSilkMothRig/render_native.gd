extends SceneTree

# Real Spine interpolation, exported as deterministic render frames.
# godot --path PROJECT --script THIS_FILE -- OUTPUT [FPS]
const DATA_PATH := "res://STS2_Things/animations/monsters/great_silk_moth/great_silk_moth_skel_data.tres"
const CLIPS := ["idle_loop", "attack", "cast", "flutter", "hurt", "die", "revive", "summon", "power_up"]

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		quit(2)
		return
	var output: String = args[0]
	var fps := float(args[1]) if args.size() > 1 else 20.0
	var data = load(DATA_PATH)
	if data == null or not data.is_skeleton_data_loaded():
		push_error("Great moth skeleton failed to load")
		quit(3)
		return
	var durations := {}
	for clip in data.get_animations():
		durations[clip.get_name()] = clip.get_duration()
	var viewport := SubViewport.new()
	viewport.size = Vector2i(1000, 720)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	get_root().add_child(viewport)
	var bg := ColorRect.new()
	bg.color = Color("242b31")
	bg.size = Vector2(1000, 720)
	viewport.add_child(bg)
	var sprite := SpineSprite.new()
	sprite.set_update_mode(SpineConstant.UpdateMode_Manual)
	sprite.skeleton_data_res = data
	sprite.position = Vector2(490, 610)
	sprite.scale = Vector2(.46, .46)
	viewport.add_child(sprite)
	await process_frame
	await process_frame
	var count := 0
	for name: String in CLIPS:
		if not durations.has(name):
			push_error("Missing clip: " + name)
			quit(4)
			return
		var folder := output.path_join(name)
		DirAccess.make_dir_recursive_absolute(folder)
		var duration: float = durations[name]
		for i in range(int(ceil(duration * fps)) + 1):
			var state = sprite.get_animation_state()
			state.clear_tracks()
			sprite.get_skeleton().set_to_setup_pose()
			var entry = state.set_animation(name, false, 0)
			entry.set_mix_duration(0.0)
			entry.set_track_time(minf(float(i) / fps, duration))
			sprite.update_skeleton(0.0)
			await process_frame
			RenderingServer.force_draw(false)
			var pixels := viewport.get_texture().get_image()
			if pixels.save_png(folder.path_join("%03d.png" % i)) != OK:
				push_error("Cannot save native frame")
				quit(5)
				return
			count += 1
		print("Captured native Great Silk Moth: ", name)
	# Exercise the resource's actual mixes and return to a moving idle pose.
	for name: String in ["attack", "cast", "flutter", "hurt"]:
		var folder := output.path_join("transition_" + name)
		DirAccess.make_dir_recursive_absolute(folder)
		var state = sprite.get_animation_state()
		state.clear_tracks()
		sprite.get_skeleton().set_to_setup_pose()
		state.set_animation("idle_loop", true, 0)
		sprite.update_skeleton(.45)
		state.set_animation(name, false, 0)
		var duration: float = durations[name]
		var returned := false
		for i in range(int(ceil((duration + .4) * fps)) + 1):
			if float(i) / fps >= duration and not returned:
				state.set_animation("idle_loop", true, 0)
				returned = true
			sprite.update_skeleton(1.0 / fps if i > 0 else 0.0)
			await process_frame
			RenderingServer.force_draw(false)
			var pixels := viewport.get_texture().get_image()
			pixels.save_png(folder.path_join("%03d.png" % i))
			count += 1
	var file := FileAccess.open(output.path_join("report.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify({"renderer": "native Spine/Godot", "spine": data.get_version(),
		"frames": count, "fps": fps, "durations": durations, "screen": [1000, 720]}, "\t"))
	file.close()
	sprite.get_animation_state().clear_tracks()
	sprite.skeleton_data_res = null
	viewport.queue_free()
	await process_frame
	data = null
	print("GREAT_MOTH_NATIVE_RENDER_PASS frames=", count)
	quit(0)
