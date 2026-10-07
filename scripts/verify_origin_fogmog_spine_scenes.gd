extends SceneTree

# Smoke-tests Origin Fogmog and its exclusive illusion Eye native Spine 4.2 scenes:
# optionally mounts an exported PCK, instantiates both shipping scenes and plays every
# animation to completion through the SpineSprite state machine.
# usage: godot --headless --path <project> --script res://scripts/verify_origin_fogmog_spine_scenes.gd -- [PCK]

const SCENES := {
	"res://scenes/creature_visuals/origin_fogmog.tscn":
		["idle_loop", "attack", "cast", "hurt", "die", "summon", "power_up", "revive", "headbutt", "triple_attack"],
	"res://scenes/creature_visuals/origin_eye_with_teeth.tscn":
		["idle_loop", "attack", "hurt", "die", "revive"],
}
var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _fail(message: String) -> void:
	failures.append(message)
	printerr("ORIGIN_FOGMOG SPINE VERIFY: %s" % message)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() >= 1:
		if not ProjectSettings.load_resource_pack(args[0], true):
			_fail("could not mount PCK: %s" % args[0])
			return _finish()
		print("mounted %s" % args[0])
	for scene_path: String in SCENES:
		var packed = load(scene_path)
		if packed == null:
			_fail("%s failed to load" % scene_path)
			continue
		var root: Node = packed.instantiate()
		get_root().add_child(root)
		var sprite = root.get_node_or_null("Visuals")
		if sprite == null or sprite.get_class() != "SpineSprite":
			_fail("%s Visuals is not a SpineSprite" % scene_path)
			continue
		var data = sprite.skeleton_data_res
		if data == null or not data.is_skeleton_data_loaded():
			_fail("%s skeleton data not loaded" % scene_path)
			continue
		if not str(data.get_version()).begins_with("4.2"):
			_fail("%s is not Spine 4.2 data" % scene_path)
		if scene_path.ends_with("origin_eye_with_teeth.tscn") and not sprite.scale.is_equal_approx(Vector2(0.35, 0.35)):
			_fail("origin eye must use the vanilla eye_with_teeth placement scale 0.35")
		print("%s spine %s bones=%d slots=%d scale=%s" % [scene_path, data.get_version(), data.get_bones().size(), data.get_slots().size(), sprite.scale])
		var durations := {}
		for a in data.get_animations():
			durations[a.get_name()] = a.get_duration()
		for name: String in SCENES[scene_path]:
			if not durations.has(name):
				_fail("%s missing animation %s" % [scene_path, name])
				continue
			var state = sprite.get_animation_state()
			var entry = state.set_animation(name, name == "idle_loop", 0)
			var start_ms := Time.get_ticks_msec()
			var target_ms := int((float(durations[name]) + 0.2) * 1000.0)
			while Time.get_ticks_msec() - start_ms < target_ms:
				await process_frame
			var ok: bool = state.get_current(0) != null and (name == "idle_loop" or entry.is_complete())
			print("  played %s duration=%.2f complete=%s" % [name, durations[name], ok])
			if not ok and name != "idle_loop":
				_fail("%s animation %s did not complete" % [scene_path, name])
		root.queue_free()
	_finish()


func _finish() -> void:
	if failures.is_empty():
		print("ORIGIN_FOGMOG_SPINE_SCENES_PASS")
		quit(0)
	else:
		printerr("ORIGIN_FOGMOG_SPINE_SCENES_FAIL (%d)" % failures.size())
		quit(1)
