import argparse
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


def clone_template(url: str, dir: Path, branch: str | None = None) -> None:
    run(['git', 'clone', url, dir]).check_returncode()
    if branch:
        run(['git', 'switch', branch], cwd=dir)
        run(['git', 'switch', '--detach', branch], cwd=dir).check_returncode()

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


_url_types = {
    # HACK: hardcoded local path
    'local': lambda x: str(Path('~/Public/').expanduser() / x),
    'raw': lambda x: x,
    'github': lambda x: f'https://github.com/{x}',
}


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-t',
        '--type',
        choices=_url_types.keys(),
        default=list(_url_types.keys())[0],
    )
    parser.add_argument('-b', '--branch')
    parser.add_argument('url')
    parser.add_argument('dir', type=Path)
    return parser


def _cli(argv: Sequence[str] | None = None) -> None:
    parser = _make_parser()
    args = parser.parse_args(argv)
    args.url = _url_types[args.type](args.url)
    if args.dir.exists():
        print(f'directory already exists: {args.dir}', file=sys.stderr)
        sys.exit(1)
    try:
        clone_template(args.url, args.dir, args.branch)
    except Exception as err:
        shutil.rmtree(args.dir, ignore_errors=True)
        print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    _cli(None)
