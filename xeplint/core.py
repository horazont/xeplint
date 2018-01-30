import pathlib

import lxml.etree

from . import context, checkers


def process_file(path: pathlib.Path):
    with path.open() as f:
        tree = lxml.etree.parse(f)

    ctx = context.XeplintContext(tree, str(path))

    for checker in checkers.CHECKERS:
        instance = checker(ctx)
        instance.check()

    ctx.messages.print()


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "infiles",
        nargs="+",
        metavar="FILE",
        help="XEP file to analyse",
        type=pathlib.Path,
    )

    args = parser.parse_args()

    for path in args.infiles:
        process_file(path)
