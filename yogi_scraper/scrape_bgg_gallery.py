"""Collect the public BoardGameGeek image gallery for Yogi (Second Edition).

Saves gallery metadata (caption, uploader, links) to CSV/JSON and, with
--download, the large-size images themselves.

Usage:
    python scrape_bgg_gallery.py [--out DIR] [--download] [--objectid 425763]
"""
import argparse
import csv
import json
import os
import time
import urllib.request

API = (
    "https://api.geekdo.com/api/images?ajax=1&gallery=all&nosession=1"
    "&objectid={oid}&objecttype=thing&pageid={page}&showcount=100"
    "&size=original&sort=recent"
)
UA = {"User-Agent": "Mozilla/5.0 (personal gallery index script)"}


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_all(oid):
    images, page = [], 1
    while True:
        data = get_json(API.format(oid=oid, page=page))
        batch = data.get("images", [])
        if not batch:
            break
        images.extend(batch)
        page += 1
        time.sleep(1)  # be polite
    return images


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--objectid", default="425763")
    ap.add_argument("--out", default="output")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    images = fetch_all(args.objectid)

    rows = []
    for im in images:
        rows.append({
            "imageid": im["imageid"],
            "caption": im.get("caption", ""),
            "uploader": im.get("user", {}).get("username", ""),
            "page_url": "https://boardgamegeek.com" + im["href"],
            "image_url": im["imageurl_lg"],
            "original_url": im["imageurl"],
            "recommends": im.get("numrecommend", 0),
        })

    with open(os.path.join(args.out, "gallery.json"), "w") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.out, "gallery.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["imageid"])
        w.writeheader()
        w.writerows(rows)

    if args.download:
        img_dir = os.path.join(args.out, "images")
        os.makedirs(img_dir, exist_ok=True)
        for r in rows:
            ext = os.path.splitext(r["image_url"])[1] or ".jpg"
            path = os.path.join(img_dir, f"{r['imageid']}{ext}")
            if os.path.exists(path):
                continue
            req = urllib.request.Request(r["image_url"], headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp, open(path, "wb") as f:
                f.write(resp.read())
            time.sleep(0.5)

    print(f"{len(rows)} images indexed -> {args.out}")


if __name__ == "__main__":
    main()
