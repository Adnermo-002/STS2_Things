extends SceneTree

const SIZE := Vector2i(3440, 1616)
const IDS := ["biting_chest", "crowded_ward"]

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 1:
		push_error("Expected project root")
		quit(1)
		return
	var records := []
	for key: String in IDS:
		var directory: String = args[0].path_join("source_assets/events/%s_20261010" % key)
		var path: String = directory.path_join("portrait-selected.png")
		var image := Image.load_from_file(path)
		if image == null:
			push_error("Missing final portrait: " + path)
			quit(2)
			return
		image.convert(Image.FORMAT_RGBA8)
		var original_size := image.get_size()
		var ratio := maxf(float(SIZE.x) / image.get_width(), float(SIZE.y) / image.get_height())
		image.resize(roundi(image.get_width() * ratio), roundi(image.get_height() * ratio), Image.INTERPOLATE_LANCZOS)
		image = image.get_region(Rect2i((image.get_size() - SIZE) / 2, SIZE))
		image.save_png(directory.path_join("portrait-unframed.png"))
		var mask := Image.create(SIZE.x, SIZE.y, false, Image.FORMAT_L8)
		for y in SIZE.y:
			var native_y := float(y) * (1251.0 / 1616.0) - 79.0
			var vertical := _smooth((native_y + 115.0) / 345.0) * (1.0 - _smooth((native_y - 885.0) / 330.0))
			for x in SIZE.x:
				var native_x := float(x) * (2662.0 / 3440.0) - 371.0
				# A continuous room-wide falloff, not an oval aperture around the object.
				var light := vertical * _smooth((native_x + 100.0) / 330.0) * (1.0 - _smooth((native_x - 710.0) / 780.0))
				var pixel := image.get_pixel(x,y)
				image.set_pixel(x,y,Color(pixel.r * light, pixel.g * light, pixel.b * light, 1.0))
				mask.set_pixel(x,y,Color(light,light,light,1.0))
		image.save_png(directory.path_join("portrait-master.png"))
		mask.save_png(directory.path_join("peripheral-fade-mask.png"))
		var runtime: String = args[0].path_join("images/events/%s.png" % key)
		image.save_png(runtime)
		records.append({"key":key, "selected":path, "selected_sha256":FileAccess.get_sha256(path),
			"original_size":[original_size.x,original_size.y], "runtime":runtime,
			"runtime_size":[SIZE.x,SIZE.y], "runtime_sha256":FileAccess.get_sha256(runtime)})
	var file := FileAccess.open(args[0].path_join("build/depths-risk-events-20261010/portrait-export.json"),FileAccess.WRITE)
	file.store_string(JSON.stringify({"generator":"built-in image_gen; model name not exposed",
		"preparation":"native Godot size/canvas preparation and continuous UI peripheral dimming", "portraits":records},"\t") + "\n")
	file.close()
	print("DEPTHS_RISK_PORTRAITS_PASS count=",records.size())
	quit(0)

func _smooth(value: float) -> float:
	var t := clampf(value,0.0,1.0)
	return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
