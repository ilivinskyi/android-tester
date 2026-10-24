"""Change detection on synthetic screens at the signature size."""

from PIL import Image, ImageDraw

from mobiletester.core import screen

W, H = screen.SIGNATURE_SIZE


def _screen() -> Image.Image:
    img = Image.new("L", (W, H), 240)
    ImageDraw.Draw(img).rectangle([40, 300, 500, 360], fill=200)  # a card
    return img


def test_identical_screens_dont_differ():
    assert not screen.differs(_screen(), _screen())


def test_a_changed_digit_is_a_change():
    # A quantity stepper going from 1 to 2: about 15x22 px at signature scale.
    before, after = _screen(), _screen()
    ImageDraw.Draw(before).rectangle([420, 320, 425, 342], fill=20)            # "1"
    ImageDraw.Draw(after).rectangle([418, 320, 433, 342], outline=20, width=3)  # "2"
    assert screen.differs(before, after)


def test_blinking_text_cursor_is_not_a_change():
    before, after = _screen(), _screen()
    ImageDraw.Draw(after).rectangle([100, 320, 101, 345], fill=20)
    assert not screen.differs(before, after)


def test_status_bar_changes_are_ignored():
    before, after = _screen(), _screen()
    ImageDraw.Draw(after).rectangle([20, 10, 80, 40], fill=20)  # clock ticks over
    assert not screen.differs(before, after)


def test_a_few_noisy_pixels_are_not_a_change():
    before, after = _screen(), _screen()
    for x in range(5):
        after.putpixel((200 + x * 40, 700), 0)
    assert not screen.differs(before, after)


def test_cursor_plus_a_real_change_is_a_change():
    before, after = _screen(), _screen()
    draw = ImageDraw.Draw(after)
    draw.rectangle([100, 320, 101, 345], fill=20)
    draw.rectangle([300, 600, 380, 640], fill=20)
    assert screen.differs(before, after)
