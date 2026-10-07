extends SceneTree

# Smoke-tests Bowlbug Progenitor creature scene with its native Spine 4.2 rig:
# optionally mounts an exported PCK, instantiates the shipping scene and
# plays every animation to completion through the SpineSprite state machine.
# usage: godot --headless --path <project> --script res://scripts/verify_bowlbug_progenitor_spine_scene.gd -- [PCK]

const SCENE_PATH := "res://scenes/creature_visuals/bowlbug_progenitor.tscn"
const ANIMATIONS := ["idle_loop", "attack", "cast", "hurt", "die", "summon", "power_up", "revive"]
var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _fail(message: String) -> void:
	failures.append(message)
	printerr("BOWLBUG_PROGENITOR SPINE VERIFY: %s" % message)


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	print("user args %s" % [args])
	if args.size() >= 1:
		if not ProjectSettings.load_resource_pack(args[0], true):
			_fail("could not mount PCK: %s" % args[0])
			return _finish()
		print("mounted %s" % args[0])
	var packed = load(SCENE_PATH)
	if packed == null:
		_fail("scene failed to load")
		return _finish()
	var root: Node = packed.instantiate()
	get_root().add_child(root)
	var sprite = root.get_node_or_null("Visuals")
	if sprite == null or sprite.get_class() != "SpineSprite":
		_fail("Visuals is not a SpineSprite")
		return _finish()
	var data = sprite.skeleton_data_res
	if data == null or not data.is_skeleton_data_loaded():
		_fail("skeleton data not loaded")
		return _finish()
	print("spine version %s bones=%d slots=%d" % [data.get_version(), data.get_bones().size(), data.get_slots().size()])
	var durations := {}
	for a in data.get_animations():
		durations[a.get_name()] = a.get_duration()
	for name: String in ANIMATIONS:
		if not durations.has(name):
			_fail("missing animation %s" % name)
			continue
		var state = sprite.get_animation_state()
		var entry = state.set_animation(name, name == "idle_loop", 0)
		var start_ms := Time.get_ticks_msec()
		var target_ms := int((float(durations[name]) + 0.2) * 1000.0)
		while Time.get_ticks_msec() - start_ms < target_ms:
			await process_frame
		var current = state.get_current(0)
		var ok: bool = current != null and (name == "idle_loop" or entry.is_complete())
		print("played %s duration=%.2f complete=%s" % [name, durations[name], ok])
		if not ok and name != "idle_loop":
			_fail("animation %s did not complete" % name)
	_finish()


func _finish() -> void:
	if failures.is_empty():
		print("BOWLBUG_PROGENITOR_SPINE_SCENE_PASS")
		quit(0)
	else:
		printerr("BOWLBUG_PROGENITOR_SPINE_SCENE_FAIL (%d)" % failures.size())
		quit(1)
