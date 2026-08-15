from __future__ import annotations

import pathlib

import settngs

import comictaggerlib.main


def generate() -> str:
    app = comictaggerlib.main.App()
    app.load_plugins(app.initial_arg_parser.parse_known_args()[0])
    app.register_settings()
    return settngs.generate_ns(app.manager.definitions)


if __name__ == "__main__":
    src = generate()
    pathlib.Path("./comictaggerlib/ctsettings/settngs_namespace.py").write_text(src)
    print(src, end="")
