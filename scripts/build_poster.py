"""Build the README video poster from an actual captured dashboard screenshot.

Optional tooling: ``pip install pillow``. Run after ``capture_walkthrough``.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "docs" / "images" / "dashboard.png"
TARGET = ROOT / "docs" / "media" / "poster.png"
FONT = Path(r"C:\Windows\Fonts\segoeui.ttf")
BOLD = Path(r"C:\Windows\Fonts\segoeuib.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = BOLD if bold else FONT
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def main() -> None:
    width, height = 1600, 900
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            glow = max(0.0, 1.0 - ((x - 1120) ** 2 / 1100**2 + (y - 100) ** 2 / 850**2))
            pixels[x, y] = (int(7 + 11 * glow), int(17 + 31 * glow), int(32 + 40 * glow))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((52, 44, 1548, 856), radius=31, outline="#355066", width=2)
    draw.line((92, 120, 1508, 120), fill="#28465c", width=2)
    draw.polygon([(94, 83), (104, 72), (114, 83), (104, 94)], outline="#69e3dc")
    draw.text((127, 67), "RETAILMIND", font=font(25, True), fill="#f3faff")
    draw.text((306, 67), "AI", font=font(25, True), fill="#6ce8df")
    draw.text((94, 183), "RETAIL", font=font(69, True), fill="#f5faff")
    draw.text((94, 257), "INTELLIGENCE", font=font(69, True), fill="#f5faff")
    draw.rounded_rectangle((94, 374, 168, 380), radius=3, fill="#68e2d9")
    draw.text((94, 412), "Observed sales. Measured forecasts.", font=font(27, True), fill="#c5e0ed")
    draw.text((94, 458), "An honest view of what the data", font=font(25), fill="#a7c2d5")
    draw.text((94, 495), "can and cannot tell you.", font=font(25), fill="#a7c2d5")
    draw.rounded_rectangle((94, 582, 490, 634), radius=11, fill="#15364b", outline="#367280", width=2)
    draw.text((112, 592), "M5 OBSERVED DATA  /  2014–2016", font=font(18, True), fill="#8ce8df")
    draw.ellipse((94, 679, 164, 749), fill="#65ddd6")
    draw.polygon([(122, 697), (122, 731), (147, 714)], fill="#062032")
    draw.text((187, 680), "WATCH THE WORKING APP", font=font(24, True), fill="#f4fcff")
    draw.text((188, 718), "Narration + embedded subtitles", font=font(19), fill="#96b5c9")

    screenshot = Image.open(SCREEN).convert("RGB")
    screenshot = screenshot.crop((300, 92, 1410, 790))
    screenshot.thumbnail((850, 535), Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", (screenshot.width + 26, screenshot.height + 26), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (frame.width + 50, frame.height + 50), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((25, 25, shadow.width - 25, shadow.height - 25), radius=24,
                                  fill=(0, 0, 0, 150))
    image.paste(shadow.filter(ImageFilter.GaussianBlur(20)), (672, 159), shadow.filter(ImageFilter.GaussianBlur(20)))
    frame_draw = ImageDraw.Draw(frame)
    frame_draw.rounded_rectangle((0, 0, frame.width - 1, frame.height - 1), radius=20, fill="#101e30",
                                 outline="#629ba7", width=3)
    frame.paste(screenshot, (13, 13))
    image.paste(frame, (688, 176), frame)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((697, 745, 1467, 796), radius=10, fill="#102b3b", outline="#2c6172")
    draw.text((718, 755), "DASHBOARD   ·   FORECAST   ·   DATA QUALITY   ·   EXPORTS",
              font=font(18, True), fill="#b4d9e5")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    image.save(TARGET, optimize=True)
    print(TARGET)


if __name__ == "__main__":
    main()
