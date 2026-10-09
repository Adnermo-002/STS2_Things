extends SceneTree

const KEYS := ["bottled_echo", "shadow_claim_ticket", "mycelial_deposit", "borrowed_ember", "things_medusa_hair"]
const BIG := 256
const SMALL := 85
const LONGEST_SIDE := 236

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		_fail("Expected generated source directory and project root")
		return
	var report := []
	for key: String in KEYS:
		var source := args[0].path_join(key + "-v1.png")
		var raw := Image.load_from_file(source)
		if raw == null:
			_fail("Missing generated relic: " + source)
			return
		raw.convert(Image.FORMAT_RGBA8)
		var min_point := raw.get_size()
		var max_point := Vector2i.ZERO
		for y in raw.get_height():
			for x in raw.get_width():
				var color := raw.get_pixel(x, y)
				if color.a <= 1.0 / 255.0:
					raw.set_pixel(x, y, Color(0, 0, 0, 0))
				if color.a >= 0.05:
					min_point.x = mini(min_point.x, x)
					min_point.y = mini(min_point.y, y)
					max_point.x = maxi(max_point.x, x + 1)
					max_point.y = maxi(max_point.y, y + 1)
		var rect := Rect2i(min_point, max_point - min_point)
		rect = rect.grow(3).intersection(Rect2i(Vector2i.ZERO, raw.get_size()))
		var cutout := raw.get_region(rect)
		var ratio := float(LONGEST_SIDE) / maxf(cutout.get_width(), cutout.get_height())
		cutout.resize(roundi(cutout.get_width() * ratio), roundi(cutout.get_height() * ratio), Image.INTERPOLATE_LANCZOS)
		var icon := Image.create(BIG, BIG, false, Image.FORMAT_RGBA8)
		icon.fill(Color.TRANSPARENT)
		icon.blit_rect(cutout, Rect2i(Vector2i.ZERO, cutout.get_size()), Vector2i((BIG - cutout.get_width()) / 2, (BIG - cutout.get_height()) / 2))
		var small := icon.duplicate()
		small.resize(SMALL, SMALL, Image.INTERPOLATE_LANCZOS)
		var outline := Image.create(SMALL, SMALL, false, Image.FORMAT_RGBA8)
		outline.fill(Color.TRANSPARENT)
		for y in SMALL:
			for x in SMALL:
				var alpha := 0.0
				for dy in range(-2, 3):
					for dx in range(-2, 3):
						if x + dx >= 0 and x + dx < SMALL and y + dy >= 0 and y + dy < SMALL:
							alpha = maxf(alpha, small.get_pixel(x + dx, y + dy).a)
				outline.set_pixel(x, y, Color(1, 1, 1, alpha))
		var big_path: String = args[1].path_join("images/relics/" + key + ".png")
		var small_path: String = args[1].path_join("images/relics/" + key + "_packed.png")
		var outline_path: String = args[1].path_join("images/atlases/relic_outline_atlas.sprites/" + key + "_outline.png")
		if icon.save_png(big_path) != OK or small.save_png(small_path) != OK or outline.save_png(outline_path) != OK:
			_fail("Cannot save relic exports: " + key)
			return
		_write_atlas(args[1].path_join("images/atlases/relic_atlas.sprites/" + key + ".tres"), "res://images/relics/" + key + "_packed.png")
		_write_atlas(args[1].path_join("images/atlases/relic_outline_atlas.sprites/" + key + ".tres"), "res://images/atlases/relic_outline_atlas.sprites/" + key + "_outline.png")
		report.append({"key":key, "source":source, "source_sha256":FileAccess.get_sha256(source),
			"crop":[rect.position.x,rect.position.y,rect.size.x,rect.size.y], "big":[BIG,BIG], "packed":[SMALL,SMALL],
			"outline":[SMALL,SMALL], "outline_dilation":2, "exports":[big_path,small_path,outline_path]})
	var output: String = args[0].get_base_dir().path_join("export-record.json")
	var file := FileAccess.open(output, FileAccess.WRITE)
	file.store_string(JSON.stringify({"generator":"built-in image_gen; exact model not exposed", "exporter":"Godot PNG/AtlasTexture preparation",
		"relics":report}, "\t") + "\n")
	file.close()
	print("DEPTHS_RELIC_EXPORT_PASS count=", report.size())
	quit(0)

func _write_atlas(path: String, texture: String) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string("[gd_resource type=\"AtlasTexture\" load_steps=2 format=3]\n\n[ext_resource type=\"Texture2D\" path=\"" + texture + "\" id=\"1\"]\n\n[resource]\natlas = ExtResource(\"1\")\nregion = Rect2(0, 0, 85, 85)\n")
	file.close()

func _fail(message: String) -> void:
	push_error(message)
	quit(1)
