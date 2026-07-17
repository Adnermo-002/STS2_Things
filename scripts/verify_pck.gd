extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		_fail("usage: verify_pck.gd <absolute-pck-path>")
		_finish()
		return

	var pck_path := args[0]
	if not ProjectSettings.load_resource_pack(pck_path, true):
		_fail("could not mount PCK: %s" % pck_path)
		_finish()
		return

	var background_slugs := [
		"origin_fogmog_boss_encounter",
		"scale_beetle_boss_encounter",
		"the_legacy_boss_encounter",
		"bowlbug_progenitor_boss_encounter",
	]
	for slug in background_slugs:
		_verify_background(slug)

	_finish()


func _verify_background(slug: String) -> void:
	var root := "res://scenes/backgrounds/%s" % slug
	var main_scene := "%s/%s_background.tscn" % [root, slug]
	if not FileAccess.file_exists(main_scene):
		_fail("missing background scene in PCK: %s" % main_scene)

	var layer_dir_path := "%s/layers" % root
	var layer_dir := DirAccess.open(layer_dir_path)
	if layer_dir == null:
		_fail("missing background layer directory in PCK: %s" % layer_dir_path)
		return

	var layer_count := 0
	layer_dir.list_dir_begin()
	var entry := layer_dir.get_next()
	while not entry.is_empty():
		if layer_dir.current_is_dir():
			_fail("unexpected subdirectory in background layers: %s/%s" % [layer_dir_path, entry])
		elif entry.ends_with(".remap"):
			_fail("runtime directory exposes unloadable remap entry: %s/%s" % [layer_dir_path, entry])
		elif not entry.ends_with(".tscn"):
			_fail("unexpected background layer entry: %s/%s" % [layer_dir_path, entry])
		else:
			layer_count += 1
			var scene_path := "%s/%s" % [layer_dir_path, entry]
			var resource := ResourceLoader.load(scene_path, "PackedScene")
			if not resource is PackedScene:
				_fail("background layer is not loadable as PackedScene: %s" % scene_path)
		entry = layer_dir.get_next()
	layer_dir.list_dir_end()

	if layer_count == 0:
		_fail("background has no loadable layer scenes: %s" % slug)


func _fail(message: String) -> void:
	failures.append(message)
	printerr("PCK VERIFY: %s" % message)


func _finish() -> void:
	if failures.is_empty():
		print("STS2_Things PCK runtime background contract: PASS")
		quit(0)
	else:
		printerr("STS2_Things PCK runtime background contract: FAIL (%d)" % failures.size())
		quit(1)
