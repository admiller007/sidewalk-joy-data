#!/usr/bin/env python3

import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


MAP_ID = "16gC7wi4LEptziD05ONmbiPyn0DWwjn0"
KML_URL = f"https://www.google.com/maps/d/kml?mid={MAP_ID}&forcekml=1"
NS = {"k": "http://www.opengis.net/kml/2.2"}

CATEGORY_MAP = {
    "Mug Exchanges": "mugExchanges",
    "Toy & Trinket Swaps": "toyTrinketSwaps",
    "Plant and Seed Swaps": "plantSeedSwaps",
    "Puzzle Libraries": "puzzleLibraries",
    "Free Little Art Galleries": "freeLittleArtGalleries",
    "Yard and Window Installations": "yardWindowInstallations",
    "Mini Galleries": "miniGalleries",
    "Variety Exchanges": "varietyExchanges",
}


def fetch_kml() -> str:
    with urllib.request.urlopen(KML_URL, timeout=30) as response:
        return response.read().decode("utf-8")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "spot"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def strip_html_lines(description: str) -> list[str]:
    description = html.unescape(description or "")
    description = re.sub(r"<br\s*/?>", "\n", description, flags=re.IGNORECASE)
    description = re.sub(r"</p\s*>", "\n", description, flags=re.IGNORECASE)
    description = re.sub(r"<[^>]+>", "", description)
    return [clean_text(line) for line in description.splitlines() if clean_text(line)]


def parse_description(description: str) -> tuple[str, str, str | None]:
    raw = html.unescape(description or "")
    image_match = re.search(r'<img[^>]+src="([^"]+)"', raw, re.IGNORECASE)
    image_url = image_match.group(1) if image_match else None

    lines = strip_html_lines(raw)
    location = ""
    body_lines: list[str] = []

    for line in lines:
        if line.lower().startswith("location:"):
            location = clean_text(line.split(":", 1)[1])
        else:
            body_lines.append(line)

    detail = "\n\n".join(body_lines).strip()
    summary_source = body_lines[0] if body_lines else location
    summary = clean_text(summary_source)
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."

    return location, detail, image_url


def media_links(placemark: ET.Element) -> list[str]:
    links: list[str] = []
    for node in placemark.findall(".//k:Data[@name='gx_media_links']/k:value", NS):
        if node.text:
            links.extend([clean_text(part) for part in node.text.splitlines() if clean_text(part)])
    return links


def placemark_to_spot(folder_name: str, placemark: ET.Element, seen_ids: dict[str, int]) -> dict:
    name = clean_text(placemark.findtext("k:name", default="", namespaces=NS))
    if not name:
        raise ValueError("Placemark is missing a name")

    description = placemark.findtext("k:description", default="", namespaces=NS)
    location, detail, image_url = parse_description(description)
    if not image_url:
        image_url = next(iter(media_links(placemark)), None)

    coordinates = clean_text(placemark.findtext(".//k:coordinates", default="", namespaces=NS))
    longitude_text, latitude_text, *_ = [part.strip() for part in coordinates.split(",")]

    base_id = slugify(name)
    suffix = seen_ids.get(base_id, 0)
    seen_ids[base_id] = suffix + 1
    spot_id = base_id if suffix == 0 else f"{base_id}-{suffix + 1}"

    summary = detail.split(". ", 1)[0].strip() if detail else location
    summary = clean_text(summary)
    if len(summary) > 160:
        summary = summary[:157].rstrip() + "..."

    return {
        "id": spot_id,
        "name": name,
        "category": CATEGORY_MAP[folder_name],
        "locationDescription": location,
        "summary": summary,
        "detail": detail,
        "latitude": float(latitude_text),
        "longitude": float(longitude_text),
        "imageURL": image_url,
        "isFeatured": False,
    }


def main() -> int:
    # Output paths can be overridden on the command line; otherwise refresh
    # both the Flutter asset and the legacy SwiftUI resource.
    if len(sys.argv) > 1:
        output_paths = [Path(arg) for arg in sys.argv[1:]]
    else:
        output_paths = [
            Path("flutter_app/assets/spots.json"),
            Path("SidewalkJoy/Resources/spots.json"),
        ]

    kml_text = fetch_kml()
    root = ET.fromstring(kml_text)

    spots: list[dict] = []
    seen_ids: dict[str, int] = {}

    for folder in root.findall(".//k:Folder", NS):
        folder_name = clean_text(folder.findtext("k:name", default="", namespaces=NS))
        if folder_name not in CATEGORY_MAP:
            continue

        for placemark in folder.findall("k:Placemark", NS):
            try:
                spots.append(placemark_to_spot(folder_name, placemark, seen_ids))
            except Exception as exc:  # keep import moving, but surface what failed
                print(f"Skipping placemark in {folder_name}: {exc}", file=sys.stderr)

    spots.sort(key=lambda spot: (spot["category"], spot["name"].lower()))

    featured_counts: dict[str, int] = {}
    for spot in spots:
        category = spot["category"]
        count = featured_counts.get(category, 0)
        if count < 3:
            spot["isFeatured"] = True
            featured_counts[category] = count + 1

    payload = json.dumps(spots, indent=2, ensure_ascii=True) + "\n"
    for output_path in output_paths:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload)

    counts: dict[str, int] = {}
    for spot in spots:
        counts[spot["category"]] = counts.get(spot["category"], 0) + 1

    print(f"Wrote {len(spots)} spots to {', '.join(str(p) for p in output_paths)}")
    for category, count in sorted(counts.items()):
        print(f"{category}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
