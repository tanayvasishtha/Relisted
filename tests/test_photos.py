import io

from PIL import Image

from relisted.photos import PhotoScore, border_white, open_image


def white_with_dark_centre() -> Image.Image:
    img = Image.new("RGB", (200, 200), "white")
    img.paste(Image.new("RGB", (100, 100), (30, 30, 30)), (50, 50))
    return img


def test_listing_photo_has_a_white_border():
    assert border_white(white_with_dark_centre()) > 0.9


def test_lab_photo_does_not():
    assert border_white(Image.new("RGB", (200, 200), (10, 10, 10))) < 0.1
    assert border_white(Image.new("RGB", (200, 200), (200, 200, 190))) < 0.1  # grey table top


def test_listing_style_threshold():
    assert PhotoScore("u", "", 0.70, 10, 10).listing_style
    assert not PhotoScore("u", "", 0.69, 10, 10).listing_style


def test_open_image_reads_the_first_frame_of_a_gif():
    frames = [Image.new("P", (20, 20), 0), Image.new("P", (20, 20), 255)]
    buffer = io.BytesIO()
    frames[0].save(buffer, format="GIF", save_all=True, append_images=frames[1:])
    assert open_image(buffer.getvalue()).size == (20, 20)
