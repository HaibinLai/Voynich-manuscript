"""Redownload exact Yale originals and recreate only the three recorded crops."""
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request
from PIL import Image

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a new output directory'
    args.output.mkdir(parents=True)
    records = json.loads((HERE / 'visual_review.json').read_text())['records']
    for record in records:
        source = record['source']
        path = args.output / (record['id'] + '_original.jpg')
        with urllib.request.urlopen(source['url'], timeout=60) as response:
            raw = response.read()
        assert hashlib.sha256(raw).hexdigest() == source['sha256'], 'Official image bytes changed; inspect before altering coordinates'
        path.write_bytes(raw)
        image = Image.open(path)
        assert image.size == (source['width'], source['height'])
        crop = args.output / Path(record['crop']).name
        image.crop(tuple(record['pixels'])).save(crop)
        assert hashlib.sha256(crop.read_bytes()).hexdigest() == record['crop_sha256']
        print(json.dumps(dict(anchor=record['id'], source_and_crop_hashes_match=True)))


if __name__ == '__main__':
    main()
