"""The colours of a DESIGN.md front matter token, as 8-digit hex."""

import math
import re

CSS_HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])")
CSS_RGB = re.compile(
    r"rgba?\(\s*([\d.]+%?)[ ,]+([\d.]+%?)[ ,]+([\d.]+%?)(?:\s*[,/]\s*([\d.]+%?))?\s*\)"
)
DART_HEX = re.compile(r"(?:Color\(|\.new\()\s*0x([0-9a-fA-F]{8})\s*\)")
DART_ARGB = re.compile(
    r"Color\.fromARGB\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)"
)
DART_RGBO = re.compile(
    r"Color\.fromRGBO\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)"
)
DART_FROM = re.compile(
    r"Color\.from\(\s*alpha:\s*([\d.]+)\s*,\s*red:\s*([\d.]+)\s*,\s*green:\s*([\d.]+)\s*,\s*blue:\s*([\d.]+)\s*,?\s*\)"
)
CSS_FUNCTION = re.compile(r"\b(hsla?|oklch|oklab)\(([^()]*)\)")
ARGUMENT_SPLIT = re.compile(r"[\s,/]+")
DART_NAMED_COLOUR = re.compile(r"\bColors\.([A-Za-z]+)(?![\w.\[])")
MATERIAL_COLOURS = {
    "red": "f44336",
    "pink": "e91e63",
    "purple": "9c27b0",
    "deepPurple": "673ab7",
    "indigo": "3f51b5",
    "blue": "2196f3",
    "lightBlue": "03a9f4",
    "cyan": "00bcd4",
    "teal": "009688",
    "green": "4caf50",
    "lightGreen": "8bc34a",
    "lime": "cddc39",
    "yellow": "ffeb3b",
    "amber": "ffc107",
    "orange": "ff9800",
    "deepOrange": "ff5722",
    "brown": "795548",
    "grey": "9e9e9e",
    "blueGrey": "607d8b",
    "white": "ffffff",
    "black": "000000",
}
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def channel_byte(word: str) -> int:
    return half_up(float(word[:-1]) * 2.55 if word.endswith("%") else float(word))


def half_up(value: float) -> int:
    return math.floor(value + 0.5)


def rgba(red: int, green: int, blue: int, alpha: float) -> str:
    return f"{red:02x}{green:02x}{blue:02x}{half_up(alpha * 255):02x}"


def unit_value(word: str, scale: float = 1.0) -> float:
    return (
        float(word[:-1]) / 100 * scale
        if word.endswith("%")
        else float(word.removesuffix("deg"))
    )


def clip_byte(value: float) -> int:
    return half_up(max(0.0, min(1.0, value)) * 255)


def srgb_encode(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055


def hsl_channels(hue: float, saturation: float, lightness: float) -> tuple[float, ...]:
    amount = saturation * min(lightness, 1 - lightness)

    def channel(offset: int) -> float:
        position = (offset + hue / 30) % 12
        return lightness - amount * max(-1.0, min(position - 3, 9 - position, 1.0))

    return channel(0), channel(8), channel(4)


def oklab_channels(light: float, a: float, b: float) -> tuple[float, ...]:
    cone_l = (light + 0.3963377774 * a + 0.2158037573 * b) ** 3
    cone_m = (light - 0.1055613458 * a - 0.0638541728 * b) ** 3
    cone_s = (light - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        srgb_encode(
            4.0767416621 * cone_l - 3.3077115913 * cone_m + 0.2309699292 * cone_s
        ),
        srgb_encode(
            -1.2684380046 * cone_l + 2.6097574011 * cone_m - 0.3413193965 * cone_s
        ),
        srgb_encode(
            -0.0041960863 * cone_l - 0.7034186147 * cone_m + 1.7076147010 * cone_s
        ),
    )


def function_colour(name: str, arguments: str) -> str | None:
    words = [word for word in ARGUMENT_SPLIT.split(arguments.strip()) if word]
    if len(words) not in (3, 4):
        return None
    try:
        alpha = unit_value(words[3]) if len(words) == 4 else 1.0
        if name.startswith("hsl"):
            red, green, blue = hsl_channels(
                unit_value(words[0]) % 360, unit_value(words[1]), unit_value(words[2])
            )
        else:
            light = unit_value(words[0])
            if name == "oklch":
                chroma = unit_value(words[1], 0.4)
                angle = math.radians(unit_value(words[2]))
                red, green, blue = oklab_channels(
                    light, chroma * math.cos(angle), chroma * math.sin(angle)
                )
            else:
                red, green, blue = oklab_channels(
                    light, unit_value(words[1], 0.4), unit_value(words[2], 0.4)
                )
    except ValueError:
        return None
    return "".join(f"{clip_byte(v):02x}" for v in (red, green, blue, alpha))


def colours_in(text: str) -> set[str]:
    found: set[str] = set()
    for hit in CSS_HEX.finditer(text):
        digits = hit[1].lower()
        digits = "".join(c * 2 for c in digits) if len(digits) < 6 else digits
        found.add(digits if len(digits) == 8 else digits + "ff")
    for hit in CSS_RGB.finditer(text):
        alpha = hit[4] or "1"
        value = float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
        found.add(
            rgba(
                channel_byte(hit[1]), channel_byte(hit[2]), channel_byte(hit[3]), value
            )
        )
    found |= {
        hit[1][2:].lower() + hit[1][:2].lower() for hit in DART_HEX.finditer(text)
    }
    found |= {
        rgba(int(hit[2]), int(hit[3]), int(hit[4]), int(hit[1]) / 255)
        for hit in DART_ARGB.finditer(text)
    }
    found |= {
        rgba(int(hit[1]), int(hit[2]), int(hit[3]), float(hit[4]))
        for hit in DART_RGBO.finditer(text)
    }
    found |= {
        colour
        for hit in CSS_FUNCTION.finditer(text)
        if (colour := function_colour(hit[1], hit[2]))
    }
    found |= {
        "".join(f"{half_up(float(hit[i]) * 255):02x}" for i in (2, 3, 4, 1))
        for hit in DART_FROM.finditer(text)
    }
    found |= {
        MATERIAL_COLOURS[hit[1]] + "ff"
        for hit in DART_NAMED_COLOUR.finditer(text)
        if hit[1] in MATERIAL_COLOURS
    }
    return {value for value in found if not value.endswith("00")}
