"""Fetch immutable WANDS files for retrieval evaluation only, never chatbot SFT."""
import argparse
import json
from pathlib import Path
import urllib.request

from scripts.repository_inventory import sha256

ROOT = Path(__file__).resolve().parents[1]


def verify(directory, manifest):
    for name, digest in manifest['sha256'].items():
        path = Path(directory) / name
        if not path.is_file() or sha256(path) != digest:
            raise ValueError('Missing or changed WANDS file: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='datasets/raw/wands')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'configs/wands_source.json').read_text(encoding='utf-8'))
    output = Path(args.output).resolve()
    if args.verify_only:
        verify(output, manifest)
        print('WANDS revision/files verified; not SFT data')
        return
    if output.exists():
        parser.error('Output exists; use --verify-only or a new destination. Local WANDS is never overwritten.')
    output.mkdir(parents=True)
    for name, digest in manifest['sha256'].items():
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/wayfair/WANDS/{manifest['revision']}/{name}"
        # Exclusive write leaves failed downloads visible; reruns cannot silently overwrite them.
        with urllib.request.urlopen(url, timeout=120) as response, destination.open('xb') as stream:
            while block := response.read(1024 * 1024):
                stream.write(block)
        if sha256(destination) != digest:
            raise ValueError('Checksum mismatch; partial destination retained for inspection: ' + name)
    verify(output, manifest)
    print('Downloaded and verified WANDS; retain upstream LICENSE')


if __name__ == '__main__':
    main()
