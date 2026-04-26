import argparse
import enum
import json
import logging
import os
import shlex
import shutil
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from subprocess import run
from typing import Any

import combustache

__version__ = 'v0.0.1'
_config_path = Path('~/.config/template/config.json').expanduser()

logger = logging.getLogger('template')


class YesNoAsk(enum.StrEnum):
    YES = 'yes'
    NO = 'no'
    ASK = 'ask'


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
                logger.warning(f'{new_path} {err}')


def clone_template(
    repo: str,
    dir: Path,
    message: str,
    data: dict[str, Any],
    run_post_script: bool | Callable[[Path], bool],
    branch: str | None = None,
) -> None:
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
    } | data

    shutil.rmtree(dir / '.git')

    process_files(dir, data)

    post_script = (dir / 'template_post_script').resolve()
    if post_script.exists() and os.access(post_script, os.EX_OK):
        if callable(run_post_script):
            run_post_script = run_post_script(post_script)
        if run_post_script:
            run([post_script], cwd=dir)
        else:
            logger.info('Skipped post script execution.')
        post_script.unlink()

    run(['git', 'init'], cwd=dir).check_returncode()
    run(['git', 'add', '-A'], cwd=dir).check_returncode()
    run(['git', 'commit', '-m', message], cwd=dir).check_returncode()


def make_default_config() -> dict:
    return {
        'types': {'raw': '{}', 'github': 'https://github.com/{}'},
        'default': 'raw',
        'message': 'feat: initial commit',
        'run-post-script': YesNoAsk.ASK,
        'data': {},
    }


def merge_configs(config: dict, user_config: dict) -> None:
    for key, user_value in user_config.items():
        if key not in config:
            continue

        config_value = config[key]
        if type(config_value) is not type(user_value):
            try:
                user_value = type(config_value)(user_value)
            except Exception:
                raise TypeError(
                    f"config and user value types don't match: "
                    f'{type(config_value)} != {type(user_value)} for {key}'
                )
        if isinstance(config_value, dict):
            config_value.update(user_value)
        else:
            config[key] = user_value


def load_config() -> dict:
    config = make_default_config()
    if _config_path.exists():
        user_config = json.loads(_config_path.read_text())
        merge_configs(config, user_config)
    return config


def make_parser(config: dict) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='subparser')
    init_parser = subparsers.add_parser('init')
    init_parser.set_defaults(func=do_init)
    config_parser = subparsers.add_parser('config')
    config_parser.set_defaults(func=do_config)

    parser.add_argument(
        '-v', '--version', action='version', version=__version__
    )

    init_parser.add_argument(
        '-m',
        '--message',
        default=config['message'],
    )
    init_parser.add_argument(
        '-t',
        '--type',
        choices=config['types'].keys(),
        default=config['default'],
        dest='type_',
    )
    init_parser.add_argument('-b', '--branch')
    init_parser.add_argument(
        '--run-post-script',
        choices=YesNoAsk.__members__.values(),
        default=config['run-post-script'],
        type=YesNoAsk,
    )
    init_parser.add_argument('repo')
    init_parser.add_argument('dir', type=Path)

    config_parser.add_argument('key')
    config_parser.add_argument('value', nargs='?')

    parser.set_defaults(logging='NOTSET')
    for subparser in [init_parser, config_parser]:
        subparser.add_argument(
            '--logging',
            default='INFO',
            choices=logging.getLevelNamesMapping().keys(),
        )

    return parser


def cli(argv: Sequence[str] | None = None) -> None:
    try:
        config = load_config()
    except json.JSONDecodeError as err:
        print(f"couldn't decode config: {err}", file=sys.stderr)
        sys.exit(1)
    except TypeError as err:
        print(f'user config error: {err}', file=sys.stderr)
        sys.exit(1)

    parser = make_parser(config)
    args = parser.parse_args(argv)

    logging.basicConfig(format='%(message)s')
    logger.setLevel(args.logging)

    if args.subparser:
        args.func(**args.__dict__, config=config)
    else:
        parser.print_help(file=sys.stderr)
        sys.exit(1)


def do_config(key: str, value: str | None, **_) -> None:
    if _config_path.exists():
        user_config = json.loads(_config_path.read_text())
    else:
        user_config = {}
    *keys, last_key = key.split('.')

    curr = user_config
    for key in keys:
        curr.setdefault(key, {})
        curr = curr[key]

    if value is None:
        print(curr.get(last_key, 'not set!'))
        sys.exit(0)
    elif value == 'none':
        curr.pop(last_key, None)
    else:
        curr[last_key] = value
        # NOTE: acts as a check
        # if we can merge the default config with the new user config
        # then the change is valid
        try:
            merge_configs(make_default_config(), user_config)
        except TypeError as err:
            print(f"couldn't modify config: {err}", file=sys.stderr)
            sys.exit(1)

    _config_path.parent.mkdir(parents=True, exist_ok=True)
    _config_path.write_text(json.dumps(user_config, indent=2))


def _display_and_ask(post_script_path: Path) -> bool:
    pager_cmd = shlex.split(os.environ.get('PAGER', 'less'))
    run([*pager_cmd, '--', post_script_path])
    return input('Execute? (Y/n): ').lower() in ('', 'y', 'yes')


def do_init(
    repo: str,
    dir: Path,
    type_: str,
    message: str,
    run_post_script: YesNoAsk,
    branch: str | None,
    config: dict,
    **_,
) -> None:
    repo = config['types'][type_].format(repo)
    if dir.exists():
        print(f'directory already exists: {dir}', file=sys.stderr)
        sys.exit(1)
    try:
        clone_template(
            repo,
            dir,
            message,
            config['data'],
            {
                YesNoAsk.YES: True,
                YesNoAsk.NO: False,
                YesNoAsk.ASK: _display_and_ask,
            }[run_post_script],
            branch,
        )
    except Exception as err:
        shutil.rmtree(dir, ignore_errors=True)
        print(err, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    cli(None)
