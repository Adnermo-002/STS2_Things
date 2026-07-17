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
	"thief_raider",
]

var failures: Array[String] = []


func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		_fail("usage: verify_spine_pck.gd <absolute-pck-path>")
		_finish()
		return

	if not ProjectSettings.load_resource_pack(args[0], true):
		_fail("could not mount PCK: %s" % args[0])
		_finish()
		return

	for key: String in RIG_KEYS:
		var root := "res://animations/monsters/sts2_things/%s/%s" % [key, key]
		for suffix: String in [".spjson", ".spatlas", ".atlas", ".png", "_skel_data.tres"]:
			var path := root + suffix
			# Imported textures are represented by a .png.import remap plus the
			# generated .ctex in an exported pack; ResourceLoader follows that remap.
			var exists := ResourceLoader.exists(path, "Texture2D") if suffix == ".png" \
				else FileAccess.file_exists(path)
			if not exists:
				_fail("missing Spine asset in PCK: %s" % path)

	_verify_excluded_directory("res://addons/spine")
	_verify_excluded_directory("res://images/monsters/rig_parts")
	_finish()


func _verify_excluded_directory(path: String) -> void:
	if DirAccess.open(path) != null:
		_fail("build-only directory leaked into PCK: %s" % path)


func _fail(message: String) -> void:
	failures.append(message)
	printerr("PCK SPINE VERIFY: %s" % message)


func _finish() -> void:
	if failures.is_empty():
		print("STS2_Things PCK Spine contract: PASS")
		quit(0)
	else:
		printerr("STS2_Things PCK Spine contract: FAIL (%d)" % failures.size())
		quit(1)
