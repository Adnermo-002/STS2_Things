extends SceneTree

const KEYS := ["bottled_echo", "shadow_claim_ticket", "mycelial_deposit", "borrowed_ember", "things_medusa_hair"]

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 5 or not ProjectSettings.load_resource_pack(args[0]):
		_fail("Expected baseline PCK, source root, texture import root, output PCK, report")
		return
	var paths: Array[String] = []
	_collect("res://", paths)
	var changes := {}
	for key: String in KEYS:
		for path: String in ["images/relics/%s.png" % key, "images/relics/%s_packed.png" % key,
				"images/atlases/relic_outline_atlas.sprites/%s_outline.png" % key]:
			var res := "res://" + path
			# Normal Godot exports load texture import remaps; keep existing raw files
			# only when the baseline exported them explicitly.
			if paths.has(res):
				changes[res] = args[1].path_join(path)
			changes[res + ".import"] = args[2].path_join(path + ".import")
			var config := ConfigFile.new()
			if config.load(changes[res + ".import"]) != OK:
				_fail("Missing texture import: " + res)
				return
			for imported: String in config.get_value("deps", "dest_files"):
				changes[imported] = args[2].path_join(imported.trim_prefix("res://"))
		for atlas: String in ["relic_atlas", "relic_outline_atlas"]:
			var res: String = "res://images/atlases/%s.sprites/%s.tres" % [atlas, key]
			changes[res] = args[1].path_join(res.trim_prefix("res://"))
	var previous := {}
	for path in paths:
		previous[path] = FileAccess.get_sha256(path)
	for path: String in changes:
		if not FileAccess.file_exists(changes[path]):
			_fail("Missing override: " + str(changes[path]))
			return
		if not paths.has(path):
			paths.append(path)
	paths.sort()
	var pack := PCKPacker.new()
	if pack.pck_start(args[3]) != OK:
		_fail("Cannot start output pack")
		return
	for path in paths:
		if pack.add_file(path, changes.get(path, path)) != OK:
			_fail("Pack failure: " + path)
			return
	if pack.flush() != OK or not ProjectSettings.load_resource_pack(args[3]):
		_fail("Cannot flush or mount final pack")
		return
	var modified := []
	for path in paths:
		var expected: String = FileAccess.get_sha256(changes[path]) if changes.has(path) else previous[path]
		if FileAccess.get_sha256(path) != expected:
			_fail("Resource hash differs: " + path)
			return
		if previous.get(path, "") != expected:
			modified.append({"path":path, "before":previous.get(path, "added"), "after":expected})
	var file := FileAccess.open(args[4], FileAccess.WRITE)
	file.store_string(JSON.stringify({"baseline":args[0], "baseline_sha256":FileAccess.get_sha256(args[0]),
		"output":args[3], "output_sha256":FileAccess.get_sha256(args[3]),
		"resources_verified":paths.size(), "changes":modified}, "\t") + "\n")
	file.close()
	print("DEPTHS_EVENT_RELIC_PACK_PASS resources=", paths.size(), " changes=", modified.size())
	quit(0)

func _collect(directory: String, paths: Array[String]) -> void:
	var dir := DirAccess.open(directory)
	dir.include_hidden = true
	for name in dir.get_files():
		paths.append(directory.path_join(name))
	for name in dir.get_directories():
		_collect(directory.path_join(name), paths)

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
