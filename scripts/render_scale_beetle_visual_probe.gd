extends SceneTree

# Deterministic real-runtime frames, with enough margin for both feeler whips.
# godot --path . --script res://scripts/render_scale_beetle_visual_probe.gd -- OUTPUT [FPS] [ANIMATION]
const DATA_PATH := "res://STS2_Things/animations/monsters/scale_beetle/scale_beetle_skel_data.tres"
const VIEWPORT_SIZE := Vector2i(1550, 920)
const ANIMATIONS := ["idle_loop", "attack", "whip", "cast", "molt", "power_up", "hurt", "die", "revive", "summon"]

func _initialize() -> void:
	call_deferred("_run")

func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.is_empty():
		printerr("usage: render_scale_beetle_visual_probe.gd OUTPUT [FPS] [ANIMATION]")
		quit(2)
		return
	var output: String = args[0]
	var fps := float(args[1]) if args.size() > 1 else 15.0
	var silhouette := args.size() > 3 and args[3] == "silhouette"
	if fps <= 0.0:
		quit(2)
		return
	DirAccess.make_dir_recursive_absolute(output)
	var data = load(DATA_PATH)
	if data == null or not data.is_skeleton_data_loaded():
		printerr("Scale Beetle skeleton failed to load")
		quit(3)
		return
	var durations := {}
	for animation in data.get_animations():
		durations[animation.get_name()] = animation.get_duration()
	for name: String in ANIMATIONS:
		if not durations.has(name) or float(durations[name]) <= 0.0:
			printerr("Missing positive-duration animation: %s" % name)
			quit(4)
			return
	var viewport := SubViewport.new()
	viewport.size = VIEWPORT_SIZE
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	get_root().add_child(viewport)
	var background := ColorRect.new()
	background.color = Color("20242a")
	if silhouette:
		background.color = Color.BLACK
	background.size = Vector2(VIEWPORT_SIZE)
	viewport.add_child(background)
	var sprite := SpineSprite.new()
	sprite.set_update_mode(SpineConstant.UpdateMode_Manual)
	sprite.skeleton_data_res = data
	sprite.position = Vector2(980, 805)
	sprite.scale = Vector2(0.72, 0.72)
	if silhouette:
		var mask_shader := Shader.new()
		mask_shader.code = "shader_type canvas_item; render_mode unshaded; void fragment(){if(texture(TEXTURE,UV).a<0.28){discard;} COLOR=vec4(1.0);}"
		var mask_material := ShaderMaterial.new()
		mask_material.shader = mask_shader
		sprite.set_normal_material(mask_material)
		var hidden_shader := Shader.new()
		hidden_shader.code = "shader_type canvas_item; render_mode unshaded,blend_add; void fragment(){COLOR=vec4(0.0);}"
		var hidden_material := ShaderMaterial.new()
		hidden_material.shader = hidden_shader
		sprite.set_additive_material(hidden_material)
	viewport.add_child(sprite)
	await process_frame
	await process_frame
	var count := 0
	for name: String in ANIMATIONS:
		if args.size() > 2 and args[2] != "all" and not args[2].split(",").has(name):
			continue
		var duration: float = float(durations[name])
		var samples := int(ceil(duration * fps)) + 1
		for i in range(samples):
			var time := minf(float(i) / fps, duration)
			var skeleton = sprite.get_skeleton()
			var state = sprite.get_animation_state()
			state.clear_tracks()
			skeleton.set_to_setup_pose()
			var entry = state.set_animation(name, false, 0)
			entry.set_track_time(time)
			sprite.update_skeleton(0.0)
			await process_frame
			RenderingServer.force_draw(false)
			viewport.get_texture().get_image().save_png(output.path_join("%s_%03d.png" % [name, i]))
			count += 1
	var report := {"key": "scale_beetle", "spine": data.get_version(), "fps": fps,
		"frames": count, "durations": durations, "position": [980, 805], "scale": 0.72, "silhouette": silhouette}
	var file := FileAccess.open(output.path_join("report.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "  "))
	file.close()
	print("SCALE_BEETLE_VISUAL_RENDER_PASS frames=%d" % count)
	quit()
