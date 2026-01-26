import argparse
import json
import shutil
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from subprocess import run
from typing import Any

import combustache

__version__ = 'v0.0.1'


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


def _set_default(value: str) -> None | int:
    assert value in _repo_types, (
        f'default value must be an existing type: {value}'
    )
    if _config_path.exists():
        _user_config = json.loads(_config_path.read_text())
    else:
        _user_config = {}

    if value != 'none':
        _user_config['default'] = value
    else:
        _user_config.pop('default', None)

    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(json.dumps(_user_config, indent=2))


def _set_type(key: str, value: str) -> None | int:
    if _config_path.exists():
        _user_config = json.loads(_config_path.read_text())
    else:
        _user_config = {}

    _user_config.setdefault('types', {})
    if value != 'none':
        _user_config['types'][key] = value
    else:
        _user_config['types'].pop(key, None)

    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(json.dumps(_user_config, indent=2))


class _FuncAndExit(argparse.Action):
    def __init__(
        self,
        option_strings: Sequence[str],
        dest: str,
        const: Callable,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(
            option_strings, dest=dest, const=const, *args, **kwargs
        )

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        _ = namespace, option_string
        assert values
        if isinstance(values, str):
            values = [values]
        try:
            parser.exit(self.const(*values))
        except Exception as err:
            print(err, file=sys.stderr)
            parser.exit(1)


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()
    init_parser = subparsers.add_parser('init')

    config_group = init_parser.add_argument_group()

    parser.add_argument(
        '-v', '--version', action='version', version=__version__
    )

    config_group.add_argument(
        '--set-default',
        nargs=1,
        metavar='VALUE',
        action=_FuncAndExit,
        const=_set_default,
    )
    config_group.add_argument(
        '--set-type',
        nargs=2,
        metavar=('KEY', 'VALUE'),
        action=_FuncAndExit,
        const=_set_type,
    )
    init_parser.add_argument(
        '-t',
        '--type',
        choices=_repo_types.keys(),
        default=_default_type,
    )
    init_parser.add_argument('-b', '--branch')
    init_parser.add_argument('repo')
    init_parser.add_argument('dir', type=Path)
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
