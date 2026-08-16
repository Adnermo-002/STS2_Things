extends SceneTree

const HAND_PATHS := [
	"res://images/ui/merchant_bargain/merchant_paper.png",
	"res://images/ui/merchant_bargain/merchant_rock.png",
	"res://images/ui/merchant_bargain/merchant_scissors.png",
]
const EXPECTED_SIZE := Vector2i(422, 1200)
const TRANSPARENT_FROM_Y := 1120
const CUFF_SAMPLE_POINT := Vector2i(211, 610)
const MIN_VISIBLE_WIDTHS := {
	"res://images/ui/merchant_bargain/merchant_paper.png": 360,
	"res://images/ui/merchant_bargain/merchant_rock.png": 320,
	"res://images/ui/merchant_bargain/merchant_scissors.png": 360,
}


func _initialize() -> void:
	for path in HAND_PATHS:
		if not _verify_hand(path):
			quit(1)
			return
	print("Merchant bargain resource probe: PASS")
	quit(0)


func _verify_hand(path: String) -> bool:
	var source := Image.load_from_file(ProjectSettings.globalize_path(path))
	if source.is_empty():
		printerr("could not load source PNG: %s" % path)
		return false
	source.convert(Image.FORMAT_RGBA8)
	if source.get_size() != EXPECTED_SIZE:
		printerr("unexpected source size for %s: %s" % [path, source.get_size()])
		return false
	var visible_bounds := source.get_used_rect()
	var minimum_width: int = MIN_VISIBLE_WIDTHS[path]
	if visible_bounds.size.x < minimum_width:
		printerr(
			"merchant gesture is undersized for %s: visible width %d, expected at least %d"
			% [path, visible_bounds.size.x, minimum_width]
		)
		return false

	for corner in [
		Vector2i(0, 0),
		Vector2i(EXPECTED_SIZE.x - 1, 0),
		Vector2i(0, EXPECTED_SIZE.y - 1),
		EXPECTED_SIZE - Vector2i.ONE,
	]:
		if source.get_pixelv(corner).a != 0.0:
			printerr("non-transparent corner in %s at %s" % [path, corner])
			return false

	var cuff_color := source.get_pixelv(CUFF_SAMPLE_POINT)
	if (
		cuff_color.a < 0.95
		or cuff_color.g >= 0.55
		or cuff_color.b <= cuff_color.g * 1.35
	):
		printerr(
			"merchant sleeve is not visible at the top-edge sample for %s: %s"
			% [path, cuff_color]
		)
		return false
	if path.ends_with("merchant_rock.png") and not _verify_rock_nails_hidden(source, path):
		return false

	for y in range(EXPECTED_SIZE.y):
		for x in range(EXPECTED_SIZE.x):
			var color := source.get_pixel(x, y)
			if y >= TRANSPARENT_FROM_Y and color.a > 0.0:
				printerr("visible pixel below fade boundary in %s at (%d, %d)" % [path, x, y])
				return false
			if color.a > 0.01 and color.r > 0.9 and color.g < 0.2 and color.b > 0.9:
				printerr("magenta key residue in %s at (%d, %d)" % [path, x, y])
				return false

	var texture := ResourceLoader.load(path) as Texture2D
	if texture == null:
		printerr("could not load imported texture: %s" % path)
		return false
	var imported := texture.get_image()
	imported.convert(Image.FORMAT_RGBA8)
	if imported.get_size() != EXPECTED_SIZE or imported.get_data() != source.get_data():
		printerr("imported RGBA pixels differ from source PNG: %s" % path)
		return false

	print(
		"verified merchant bargain hand: %s (visible_bounds=%s, cuff=%s)"
		% [path, visible_bounds, cuff_color]
	)
	return true


func _verify_rock_nails_hidden(image: Image, path: String) -> bool:
	for y in range(0, 160):
		for x in range(40, 310):
			var color := image.get_pixel(x, y)
			if (
				color.a > 0.2
				and color.r > 0.72
				and color.g > 0.68
				and color.b > 0.62
			):
				printerr(
					"visible four-finger nail pixel in dorsal rock fist %s at (%d, %d): %s"
					% [path, x, y, color]
				)
				return false
	return true
