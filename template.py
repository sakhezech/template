import argparse
import shutil
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from subprocess import run

import combustache


def clone_template(url: str, dir: Path, branch: str | None = None) -> None:
    run(['git', 'clone', url, dir]).check_returncode()
    if branch:
        run(['git', 'switch', '--detach', branch], cwd=dir).check_returncode()

    ls_proc = run(
        ['git', 'ls-tree', '-r', '--name-only', 'HEAD'],
        cwd=dir,
        capture_output=True,
    )
    ls_proc.check_returncode()

    # HACK: hardcoded data
    data = {
        'project_name': 'PROJECT',
        'author': 'AUTHOR',
        'date': datetime.now(),
    }

    for rel_file_path_str in ls_proc.stdout.decode().splitlines():
        file_path = dir / rel_file_path_str

        file_path.write_text(combustache.render(file_path.read_text(), data))
        shutil.move(file_path, Path(combustache.render(str(file_path), data)))

    shutil.rmtree(dir / '.git')
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
