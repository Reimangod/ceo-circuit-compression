"""Read content-addressed, lossless data objects without the author's filesystem."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


class Archive:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.manifest = json.loads((self.root/'data/metadata/archive-manifest.json').read_text())
        self.entries = {x['source_path']: x for x in self.manifest['files'] if x.get('object_sha256')}
        for a in self.manifest['aliases']:
            self.entries[a['source_path']] = self.entries[a['same_as']]

    @staticmethod
    def key(path):
        path = str(path)
        if path.startswith('archive://'):
            return path[len('archive://'):]
        if '/outputs/' in path:
            return 'outputs/' + path.split('/outputs/', 1)[1]
        return path

    def file(self, path):
        entry = self.entries[self.key(path)]
        p = self.root/'data/raw/objects'/entry['object_sha256']
        if not p.is_file():
            raise FileNotFoundError('Data package missing. Run python tools/fetch_data.py first.')
        return p

    def json(self, path):
        return json.loads(self.file(path).read_bytes())

    def jsonl(self, path):
        return [json.loads(x) for x in self.file(path).read_bytes().splitlines() if x.strip()]
