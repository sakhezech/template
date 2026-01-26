import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from subprocess import run
from typing import Any

import combustache

__version__ = 'v0.0.1'
_config_path = Path('~/.config/template/config.json').expanduser()


def process_files(path: Path, data: dict[str, Any]) -> None:
    for file_path in path.iterdir():
        new_path = Path(combustache.render(str(file_path), data))
        file_path.rename(new_path)

        if new_path.is_dir():
            process_files(new_path, data)
        else:
            try:
                content = combustache.render(new_path.read_text(), data)
                new_path.write_text(content)
            except UnicodeDecodeError as err:
                print(new_path, err, file=sys.stderr)


def clone_template(repo: str, dir: Path, branch: str | None = None) -> None:
    clone_cmd = [
        'git',
        '-c',
        'advice.detachedHead=false',
        'clone',
        repo,
        dir,
        '--single-branch',
        '--depth',
        '1',
    ]
    if branch:
        clone_cmd.extend(('--branch', branch))
    run(clone_cmd).check_returncode()

    data = {
        'project': {'name': dir.name},
        'git': {
            'name': run(
                ['git', 'config', 'get', 'user.name'], capture_output=True
            )
            .stdout.decode()
            .strip(),
            'email': run(
                ['git', 'config', 'get', 'user.email'], capture_output=True
            )
            .stdout.decode()
            .strip(),
        },
        'date': datetime.now(),
    }

    shutil.rmtree(dir / '.git')

    process_files(dir, data)

    run(['git', 'init'], cwd=dir).check_returncode()
    run(['git', 'add', '-A'], cwd=dir).check_returncode()
    run(
        ['git', 'commit', '-m', 'feat: initial commit'], cwd=dir
    ).check_returncode()


def load_config() -> dict:
    config = {
        'types': {'raw': '{}', 'github': 'https://github.com/{}'},
        'default': 'raw',
    }
    try:
        if _config_path.exists():
            user_config = json.loads(_config_path.read_text())
            if 'types' in user_config:
                config['types'].update(user_config['types'])
            if 'default' in user_config:
                config['default'] = user_config['default']
    except json.JSONDecodeError as err:
        print(f"couldn't decode config: {err}", file=sys.stderr)
    return config


def _make_parser() -> argparse.ArgumentParser:
    config = load_config()

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    init_parser = subparsers.add_parser('init')
    init_parser.set_defaults(func=do_init)
    config_parser = subparsers.add_parser('config')
    config_parser.set_defaults(func=do_config)

    parser.add_argument(
        '-v', '--version', action='version', version=__version__
    )

    init_parser.add_argument(
        '-t',
        '--type',
        choices=config['types'].keys(),
        default=config['default'],
    )
    init_parser.add_argument('-b', '--branch')
    init_parser.add_argument('repo')
    init_parser.add_argument('dir', type=Path)

    config_parser.add_argument('key')
    config_parser.add_argument('value')

    return parser


def _cli(argv: Sequence[str] | None = None) -> None:
    parser = _make_parser()
    args = parser.parse_args(argv)
    args.func(**args.__dict__)


def do_config(key: str, value: str, **_) -> None:
    if _config_path.exists():
        user_config = json.loads(_config_path.read_text())
    else:
        user_config = {}
    *keys, last_key = key.split('.')
    # TODO: needs better validation
    if not ((not keys and last_key == 'default') or (keys == ['types'])):
        raise ValueError(f'bad config key: {key}')

    curr = user_config
    for key in keys:
        curr.setdefault(key, {})
        curr = curr[key]

    if value == 'none':
        del curr[last_key]
    else:
        curr[last_key] = value

    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(json.dumps(user_config, indent=2))


def do_init(repo: str, dir: Path, type: str, branch: str | None, **_) -> None:
    config = load_config()
    repo = config['types'][type].format(repo)
    if dir.exists():
        print(f'directory already exists: {dir}', file=sys.stderr)
        sys.exit(1)
    try:
        clone_template(repo, dir, branch)
    except Exception as err:
        shutil.rmtree(dir, ignore_errors=True)
        print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    _cli(None)
