extends SceneTree

# Patch explicitly named text resources into a verified installed PCK, preserving
# all other files. Useful when unrelated source work is still in progress.
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 5 or not ProjectSettings.load_resource_pack(args[0]):
		_fail("Expected baseline PCK, source root, comma-separated resource paths, output PCK, report")
		return
	var paths: Array[String] = []
	_collect("res://", paths)
	var before := {}
	for path in paths:
		before[path] = FileAccess.get_sha256(path)
	var overrides := {}
	for relative: String in args[2].split(","):
		if relative.contains("..") or not ((relative.begins_with("scenes/") and relative.ends_with(".tscn")) or (relative.begins_with("STS2_Things/localization/") and relative.ends_with(".json"))):
			_fail("Only explicit scenes or localization tables are allowed")
			return
		var path := "res://" + relative
		if not paths.has(path):
			_fail("Resource is not in the baseline pack: " + path)
			return
		overrides[path] = args[1].path_join(relative)
	paths.sort()
	var pack := PCKPacker.new()
	if pack.pck_start(args[3]) != OK:
		_fail("Cannot start output pack")
		return
	for path in paths:
		if pack.add_file(path, overrides.get(path, path)) != OK:
			_fail("Cannot add: " + path)
			return
	if pack.flush() != OK or not ProjectSettings.load_resource_pack(args[3]):
		_fail("Cannot flush or remount final pack")
		return
	var changes := []
	for path in paths:
		var expected: String = FileAccess.get_sha256(overrides[path]) if overrides.has(path) else before[path]
		if FileAccess.get_sha256(path) != expected:
			_fail("Hash mismatch: " + path)
			return
		if expected != before[path]:
			changes.append({"path":path, "before":before[path], "after":expected})
	var report := FileAccess.open(args[4], FileAccess.WRITE)
	report.store_string(JSON.stringify({"baseline_sha256":FileAccess.get_sha256(args[0]),
		"output_sha256":FileAccess.get_sha256(args[3]), "resources_verified":paths.size(), "changes":changes}, "\t") + "\n")
	report.close()
	print("RESOURCE_OVERRIDE_PACK_PASS resources=", paths.size(), " changes=", changes.size())
	quit(0)

func _collect(directory: String, paths: Array[String]) -> void:
	var dir := DirAccess.open(directory)
	dir.include_hidden = true
	for name in dir.get_files():
		if directory == "res://" and name == "project.godot":
			continue # Local pack-helper configuration is never a runtime asset.
		paths.append(directory.path_join(name))
	for name in dir.get_directories():
		_collect(directory.path_join(name), paths)

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
