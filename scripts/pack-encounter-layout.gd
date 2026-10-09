extends SceneTree

# Repack an already verified runtime PCK, changing only authored encounter slots.
# Run with --path pointing to an empty directory so the resource listing contains
# only the mounted baseline. No imported textures or unrelated assets are rebuilt.
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 4:
		_fail("Expected baseline PCK, source root, output PCK, report path")
		return
	var baseline: String = args[0]
	var source_root: String = args[1]
	var output: String = args[2]
	if baseline.simplify_path() == output.simplify_path():
		_fail("Output must be separate from the baseline")
		return
	if not ProjectSettings.load_resource_pack(baseline):
		_fail("Cannot mount baseline PCK")
		return
	var paths: Array[String] = []
	_collect("res://", paths)
	paths.sort()
	var hashes := {}
	var replacements := {}
	for path in paths:
		hashes[path] = FileAccess.get_sha256(path)
		if path.begins_with("res://scenes/encounters/") and path.ends_with(".tscn"):
			var source: String = source_root.path_join(path.trim_prefix("res://"))
			if not FileAccess.file_exists(source):
				_fail("Missing encounter source: " + source)
				return
			if FileAccess.get_sha256(source) != hashes[path]:
				replacements[path] = source
	if replacements.is_empty():
		_fail("No changed encounter scenes found")
		return
	DirAccess.make_dir_recursive_absolute(output.get_base_dir())
	var packer := PCKPacker.new()
	if packer.pck_start(output) != OK:
		_fail("Cannot create output PCK")
		return
	for path in paths:
		var source: String = replacements.get(path, path)
		if packer.add_file(path, source) != OK:
			_fail("Cannot pack: " + path)
			return
	if packer.flush() != OK or not ProjectSettings.load_resource_pack(output):
		_fail("Cannot finish or mount output PCK")
		return
	var changes: Array[Dictionary] = []
	for path in paths:
		var expected: String = FileAccess.get_sha256(replacements[path]) if replacements.has(path) else hashes[path]
		if FileAccess.get_sha256(path) != expected:
			_fail("Packaged bytes differ: " + path)
			return
		if replacements.has(path):
			changes.append({"path": path, "before_sha256": hashes[path], "after_sha256": expected})
	var report := {"baseline": baseline, "baseline_sha256": FileAccess.get_sha256(baseline),
		"output": output, "output_sha256": FileAccess.get_sha256(output),
		"resources_verified": paths.size(), "changes": changes}
	var file := FileAccess.open(args[3], FileAccess.WRITE)
	file.store_string(JSON.stringify(report, "\t") + "\n")
	file.close()
	print("PASS: ", paths.size(), " packaged resources verified; ", changes.size(), " encounter scenes updated.")
	quit(0)

func _collect(directory: String, paths: Array[String]) -> void:
	var access := DirAccess.open(directory)
	access.include_hidden = true
	for name in access.get_files():
		paths.append(directory.path_join(name))
	for name in access.get_directories():
		_collect(directory.path_join(name), paths)

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
