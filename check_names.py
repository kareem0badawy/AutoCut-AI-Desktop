from pathlib import Path
import json

CONFIG_PATH = Path(__file__).resolve().parent / 'config.json'


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8-sig') as f:
        return json.load(f)


def main():
    config = load_config()
    base_path = Path(config['base_path'])

    for folder in [base_path / 'output' / 'images', base_path / 'assets' / 'images']:
        print(f'\n=== {folder} ===')
        if not folder.exists():
            print('folder not found')
            continue

        files = sorted([p.name for p in folder.iterdir() if p.is_file()])
        if not files:
            print('empty folder')
            continue

        for name in files:
            print(repr(name))


if __name__ == '__main__':
    main()
