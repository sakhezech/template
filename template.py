import argparse
import shutil
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


def _make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true')
    parser.add_argument('-b', '--branch')
    parser.add_argument('url')
    parser.add_argument('dir', type=Path)
    return parser


def _cli(argv: Sequence[str] | None = None) -> None:
    parser = _make_parser()
    args = parser.parse_args(argv)
    # HACK: hardcoded local path
    if args.local:
        args.url = str(Path('~/Public/').expanduser() / args.url)
    clone_template(args.url, args.dir, args.branch)


if __name__ == '__main__':
    _cli(None)
