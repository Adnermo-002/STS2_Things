extends SceneTree

# Real Spine runtime and exported-scene contract, including the linked whip combo.
const SCENE_PATH := "res://scenes/creature_visuals/things_scale_beetle.tscn"
const ANIMATIONS := ["idle_loop", "attack", "whip", "cast", "molt", "power_up", "hurt", "die", "revive", "summon"]
var failures: Array[String] = []

func _initialize() -> void:
	call_deferred("_run")

func _fail(message: String) -> void:
	failures.append(message)
	printerr("SCALE_BEETLE: %s" % message)

func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() > 0 and not ProjectSettings.load_resource_pack(args[0], true):
		_fail("could not mount PCK")
		return _finish()
	var packed = load(SCENE_PATH)
	if packed == null:
		_fail("scene failed to load")
		return _finish()
	var root = packed.instantiate()
	get_root().add_child(root)
	var sprite = root.get_node_or_null("Visuals")
	if sprite == null or sprite.get_class() != "SpineSprite":
		_fail("Visuals must be a SpineSprite")
		return _finish()
	if not sprite.position.is_equal_approx(Vector2.ZERO) or not sprite.scale.is_equal_approx(Vector2(0.52, 0.52)):
		_fail("painting placement or scale changed")
	for marker in ["Bounds", "CenterPos", "IntentPos"]:
		if root.get_node_or_null(marker) == null:
			_fail("missing creature anchor %s" % marker)
	var data = sprite.skeleton_data_res
	if data == null or not data.is_skeleton_data_loaded() or not str(data.get_version()).begins_with("4.2"):
		_fail("Spine 4.2 skeleton not loaded")
		return _finish()
	sprite.set_update_mode(SpineConstant.UpdateMode_Manual)
	var durations := {}
	for animation in data.get_animations():
		durations[animation.get_name()] = animation.get_duration()
	var samples := 0
	for name: String in ANIMATIONS:
		if not durations.has(name):
			_fail("missing %s" % name)
			continue
		var state = sprite.get_animation_state()
		state.clear_tracks()
		sprite.get_skeleton().set_to_setup_pose()
		var entry = state.set_animation(name, false, 0)
		var duration: float = float(durations[name])
		for frame in range(int(ceil(duration * 120.0)) + 1):
			entry.set_track_time(minf(float(frame) / 120.0, duration))
			sprite.update_skeleton(0.0)
			samples += 1
		if not entry.is_complete():
			_fail("%s did not complete" % name)
		print("played %s duration=%.3f complete=%s" % [name, duration, entry.is_complete()])
	# All three contacts belong to one track; reactions can interrupt that track.
	var state = sprite.get_animation_state()
	var whip = state.set_animation("whip", false, 0)
	for contact in [0.60, 1.12, 1.68]:
		whip.set_track_time(contact)
		sprite.update_skeleton(0.0)
		if not is_equal_approx(whip.get_track_time(), contact):
			_fail("whip did not reach contact %.2f" % contact)
	state.set_animation("hurt", false, 0)
	sprite.update_skeleton(0.1)
	state.set_animation("idle_loop", true, 0)
	sprite.update_skeleton(0.2)
	for factor in [1.0, 1.160969, 1.347849, 2.0]:
		root.scale = Vector2.ONE * factor
		sprite.update_skeleton(0.0)
		if not sprite.global_scale.is_equal_approx(Vector2.ONE * 0.52 * factor):
			_fail("external ScaleUp scale was not inherited")
	print("bones=%d slots=%d sampled_frames=%d" % [data.get_bones().size(), data.get_slots().size(), samples])
	root.queue_free()
	_finish()

func _finish() -> void:
	if failures.is_empty():
		print("SCALE_BEETLE_SPINE_SCENE_PASS")
		quit(0)
	else:
		printerr("SCALE_BEETLE_SPINE_SCENE_FAIL count=%d" % failures.size())
		quit(1)
