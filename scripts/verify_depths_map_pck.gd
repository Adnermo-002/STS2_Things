extends SceneTree

# Run from an isolated project: successful loads must come from the shipped PCK.
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 3:
		printerr("Usage: verify_depths_map_pck.gd <pck> <workspace> <report.json>")
		quit(2)
		return
	var pack_path := args[0]
	var workspace := args[1]
	var report := {"pck": pack_path, "passed": true, "textures": []}
	if not ProjectSettings.load_resource_pack(pack_path, true):
		printerr("Cannot mount PCK: " + pack_path)
		quit(1)
		return
	for part in ["top", "middle", "bottom"]:
		var relative: String = "images/packed/map/map_bgs/depths/map_" + part + "_depths.png"
		var import_config := ConfigFile.new()
		var source_import := workspace.path_join(relative + ".import")
		if import_config.load(source_import) != OK:
			printerr("Cannot read expected import: " + source_import)
			quit(1)
			return
		var imported_path: String = import_config.get_value("remap", "path")
		var expected := FileAccess.get_file_as_bytes(workspace.path_join(imported_path.trim_prefix("res://")))
		var packed := FileAccess.get_file_as_bytes(imported_path)
		var texture := ResourceLoader.load("res://" + relative, "Texture2D") as Texture2D
		var valid_size := texture != null and texture.get_width() == 2036 and texture.get_height() == 1440
		var identical := not expected.is_empty() and expected == packed
		var passed := valid_size and identical
		report.textures.append({
			"path": "res://" + relative,
			"loaded_at_native_size": valid_size,
			"matches_selected_import": identical,
			"expected_import_sha256": FileAccess.get_sha256(workspace.path_join(imported_path.trim_prefix("res://"))),
			"packed_import_sha256": FileAccess.get_sha256(imported_path),
		})
		report.passed = report.passed and passed
		print(part, ": native size=", valid_size, ", selected texture match=", identical)
	var file := FileAccess.open(args[2], FileAccess.WRITE)
	if file == null:
		printerr("Cannot write report: " + args[2])
		quit(1)
		return
	file.store_string(JSON.stringify(report, "\t") + "\n")
	file.close()
	print("Depths map PCK verification: ", "PASS" if report.passed else "FAIL")
	quit(0 if report.passed else 1)
