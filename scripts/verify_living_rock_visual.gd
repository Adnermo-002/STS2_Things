extends SceneTree

const SCENE_PATH := "res://scenes/creature_visuals/living_rock.tscn"
const LEFT_TO_RIGHT := "main_01_left_to_right"
const RIGHT_TO_LEFT := "main_01_right_to_left"
const LEFT_PUNCH := "leftpunch"
const RIGHT_PUNCH := "rightpunch"

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1 or not ProjectSettings.load_resource_pack(args[0], true):
		_fail("usage: verify_living_rock_visual.gd ABSOLUTE_PCK")
		_finish()
		return
	var scene := ResourceLoader.load(SCENE_PATH, "PackedScene") as PackedScene
	if scene == null:
		_fail("could not load Living Rock scene")
		_finish()
		return
	var root := scene.instantiate()
	get_root().add_child(root)
	await process_frame
	await process_frame
	var spine = root.get_node_or_null("Visuals")
	if spine == null:
		_fail("scene has no SpineSprite")
		root.free()
		_finish()
		return
	var state = spine.get_animation_state()
	var skeleton = spine.get_skeleton()
	if state == null or skeleton == null:
		_fail("Spine runtime did not initialize")
		root.free()
		_finish()
		return
	await _run_case(root, state, skeleton, RIGHT_TO_LEFT, "LivingRockLeftPunch", false, LEFT_PUNCH, LEFT_TO_RIGHT)
	await _run_case(root, state, skeleton, LEFT_TO_RIGHT, "LivingRockLeftPunch", true, LEFT_PUNCH, LEFT_TO_RIGHT)
	await _run_case(root, state, skeleton, LEFT_TO_RIGHT, "LivingRockRightPunch", false, RIGHT_PUNCH, RIGHT_TO_LEFT)
	await _run_case(root, state, skeleton, RIGHT_TO_LEFT, "LivingRockRightPunch", true, RIGHT_PUNCH, RIGHT_TO_LEFT)
	root.free()
	_finish()


func _run_case(
	root: Node,
	state,
	skeleton,
	current_idle: String,
	trigger: String,
	expects_rewind: bool,
	expected_punch: String,
	expected_idle: String,
) -> void:
	state.clear_tracks()
	var entry = state.set_animation(current_idle, false, 0)
	entry.set_track_time(2.5)
	state.update(0.0)
	state.apply(skeleton)
	await process_frame
	if not _trigger(root, trigger):
		return
	var initial_time := _track_time(state)
	if expects_rewind:
		var previous := initial_time
		var decreased := false
		for _index in range(8):
			await process_frame
			var current := _track_time(state)
			if current > previous + 0.0001:
				_fail("rewind increased track time for %s" % trigger)
			if current < previous - 0.0001:
				decreased = true
			previous = current
		if not decreased:
			_fail("rewind did not decrease track time for %s" % trigger)
	else:
		await process_frame
		await process_frame
		if _track_time(state) < initial_time - 0.0001:
			_fail("natural-complete path rewound for %s" % trigger)
		var current = state.get_current(0)
		if current != null:
			current.set_track_time(current.get_animation_end())
			state.update(0.0)
			state.apply(skeleton)
	var reached_punch: bool = await _wait_for_animation(state, expected_punch, 180)
	if not reached_punch:
		_fail("%s did not transition to %s" % [trigger, expected_punch])
		return
	var punch_entry = state.get_current(0)
	if punch_entry != null:
		punch_entry.set_track_time(punch_entry.get_animation_end())
		state.update(0.0)
		state.apply(skeleton)
	var reached_idle: bool = await _wait_for_animation(state, expected_idle, 180)
	if not reached_idle:
		_fail("%s did not recover to %s" % [trigger, expected_idle])


func _trigger(root: Node, trigger: String) -> bool:
	if root.has_method("trigger_punch"):
		root.call("trigger_punch", trigger)
		return true
	if root.has_method("TriggerPunch"):
		root.call("TriggerPunch", trigger)
		return true
	_fail("NCaveGodVisuals does not expose TriggerPunch")
	return false


func _wait_for_animation(state, expected: String, frame_limit: int) -> bool:
	for _index in range(frame_limit):
		if _animation_name(state) == expected:
			return true
		await process_frame
	return false


func _animation_name(state) -> String:
	var entry = state.get_current(0)
	return "" if entry == null else entry.get_animation().get_name()


func _track_time(state) -> float:
	var entry = state.get_current(0)
	return 0.0 if entry == null else entry.get_track_time()


func _fail(message: String) -> void:
	failures.append(message)
	printerr("LIVING_ROCK_VISUAL_VERIFY: %s" % message)


func _finish() -> void:
	if failures.is_empty():
		print("LIVING_ROCK_VISUAL_VERIFY_PASS")
		quit(0)
	else:
		printerr("LIVING_ROCK_VISUAL_VERIFY_FAIL count=%d" % failures.size())
		quit(1)
