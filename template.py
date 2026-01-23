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


def process_files(path: Path, data: dict[str, Any]) -> None:
    for file_path in path.iterdir():
        new_path = Path(combustache.render(str(file_path), data))
        file_path.rename(new_path)

        if new_path.is_dir():
            process_files(new_path, data)
        else:
            new_path.write_text(combustache.render(new_path.read_text(), data))


def clone_template(repo: str, dir: Path, branch: str | None = None) -> None:
    run(['git', 'clone', repo, dir]).check_returncode()
    if branch:
        run(
            ['git', '-c', 'advice.detachedHead=false', 'checkout', branch],
            cwd=dir,
        ).check_returncode()

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


_config = {
    'types': {'raw': '{}', 'github': 'https://github.com/{}'},
    'default': 'raw',
}
_config_path = Path('~/.config/template/config.json').expanduser()
try:
    if _config_path.exists():
        _user_config = json.loads(_config_path.read_text())
        if 'types' in _user_config:
            _config['types'].update(_user_config['types'])
        if 'default' in _user_config:
            _config['default'] = _user_config['default']
except json.JSONDecodeError as err:
    print(f"couldn't decode config: {err}", file=sys.stderr)
_repo_types = _config['types']
_default_type = _config['default']


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t',
        '--type',
        choices=_repo_types.keys(),
        default=_default_type,
    )
    parser.add_argument('-b', '--branch')
    parser.add_argument('repo')
    parser.add_argument('dir', type=Path)
    return parser


def _cli(argv: Sequence[str] | None = None) -> None:
    parser = _make_parser()
    args = parser.parse_args(argv)
    args.repo = _repo_types[args.type].format(args.repo)
    if args.dir.exists():
        print(f'directory already exists: {args.dir}', file=sys.stderr)
        sys.exit(1)
    try:
        clone_template(args.repo, args.dir, args.branch)
    except Exception as err:
        shutil.rmtree(args.dir, ignore_errors=True)
        print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    _cli(None)
