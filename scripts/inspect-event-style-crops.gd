extends SceneTree
func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	for key: String in ["tea_master", "potion_courier", "sunken_treasury", "hungry_for_mushrooms"]:
		var path: String = args[0].path_join("images/events/%s.png" % key)
		var original := Image.load_from_file(path)
		# Inspection/reference only: preserve the actual native pixels and colours.
		var region := Rect2i(600,350,1550,1190).intersection(Rect2i(Vector2i.ZERO,original.get_size()))
		original.get_region(region).save_png(args[1].path_join("native-%s-crop.png" % key))
	quit(0)
