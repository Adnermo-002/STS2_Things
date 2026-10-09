extends SceneTree

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 5 or not ProjectSettings.load_resource_pack(args[0]):
		push_error("Expected baseline PCK, source root, texture import root, output PCK, report")
		quit(2)
		return
	var paths: Array[String] = []
	_collect("res://", paths)
	paths.sort()
	var changes := {}
	for path in ["scale_beetle_boss_encounter_background.tscn",
			"layers/scale_beetle_boss_encounter_bg_00_a.tscn",
			"layers/scale_beetle_boss_encounter_bg_01_a.tscn",
			"layers/scale_beetle_boss_encounter_fg_a.tscn"]:
		var res: String = "res://scenes/backgrounds/scale_beetle_boss_encounter/" + path
		changes[res] = args[1].path_join(res.trim_prefix("res://"))
	for name in ["backdrop", "floor", "foreground"]:
		var res: String = "res://images/backgrounds/scale_beetle_remake/%s.png" % name
		changes[res] = args[1].path_join(res.trim_prefix("res://"))
		changes[res + ".import"] = args[2].path_join(res.trim_prefix("res://") + ".import")
		var config := ConfigFile.new()
		if config.load(changes[res + ".import"]) != OK:
			push_error("Missing texture import: " + res)
			quit(3)
			return
		for imported: String in config.get_value("deps", "dest_files"):
			changes[imported] = args[2].path_join(imported.trim_prefix("res://"))
	var previous := {}
	for path in paths:
		previous[path] = FileAccess.get_sha256(path)
	for path: String in changes:
		if not paths.has(path):
			paths.append(path)
	paths.sort()
	var pack := PCKPacker.new()
	if pack.pck_start(args[3]) != OK:
		quit(4)
		return
	for path in paths:
		if pack.add_file(path, changes.get(path, path)) != OK:
			push_error("Pack failure: " + path)
			quit(5)
			return
	if pack.flush() != OK or not ProjectSettings.load_resource_pack(args[3]):
		quit(6)
		return
	var modified := []
	for path in paths:
		var expected: String = FileAccess.get_sha256(changes[path]) if changes.has(path) else previous[path]
		if FileAccess.get_sha256(path) != expected:
			push_error("Resource hash differs: " + path)
			quit(7)
			return
		if previous.get(path, "") != expected:
			modified.append({"path":path, "before":previous.get(path, "added"), "after":expected})
	var file := FileAccess.open(args[4], FileAccess.WRITE)
	file.store_string(JSON.stringify({"baseline":args[0], "baseline_sha256":FileAccess.get_sha256(args[0]),
		"output":args[3], "output_sha256":FileAccess.get_sha256(args[3]),
		"resources_verified":paths.size(), "changes":modified}, "\t") + "\n")
	file.close()
	print("SCALE_BEETLE_BACKGROUND_PACK_PASS resources=", paths.size(), " changes=", modified.size())
	quit(0)

func _collect(directory: String, paths: Array[String]) -> void:
	var dir := DirAccess.open(directory)
	dir.include_hidden = true
	for name in dir.get_files():
		paths.append(directory.path_join(name))
	for name in dir.get_directories():
		_collect(directory.path_join(name), paths)
