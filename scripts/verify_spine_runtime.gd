extends SceneTree

const RIG_KEYS := [
	"origin_fogmog",
	"bowlbug_progenitor",
	"scale_beetle",
	"soul_roe_1",
	"soul_roe_2",
	"soul_roe_3",
	"soul_roes",
	"the_legacy",
]

const REQUIRED_ANIMATIONS := [
	"idle_loop",
	"attack",
	"cast",
	"hurt",
	"die",
	"summon",
	"power_up",
	"revive",
]


func _initialize() -> void:
	var failures: Array[String] = []
	for key: String in RIG_KEYS:
		var path := "res://animations/monsters/sts2_things/%s/%s_skel_data.tres" % [key, key]
		# Keep a strong reference for the full inspection. Spine's resource wrapper
		# is RefCounted and a temporary load expression can be released too early.
		var data = load(path)
		if data == null:
			failures.append("%s failed to load" % path)
			continue
		if not data.is_skeleton_data_loaded():
			failures.append("%s did not load skeleton data" % key)
		var version: String = str(data.get_version())
		if not version.begins_with("4.2"):
			failures.append("%s uses Spine %s instead of 4.2.x" % [key, version])

		var durations := {}
		for animation in data.get_animations():
			durations[animation.get_name()] = animation.get_duration()
		for required: String in REQUIRED_ANIMATIONS:
			if not durations.has(required):
				failures.append("%s missing %s" % [key, required])
			elif float(durations[required]) <= 0.0:
				failures.append("%s has zero-duration %s" % [key, required])
		print("SPINE_RUNTIME key=%s version=%s animations=%s durations=%s" % [
			key, version, durations.keys(), durations])

	if failures.is_empty():
		print("SPINE_RUNTIME_PASS rigs=%d" % RIG_KEYS.size())
		quit(0)
	else:
		for failure in failures:
			printerr("SPINE_RUNTIME_FAIL: %s" % failure)
		quit(1)
