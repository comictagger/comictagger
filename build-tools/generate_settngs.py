from __future__ import annotations

import pathlib

import settngs

import comictaggerlib.main


def generate() -> str:
    app = comictaggerlib.main.App()
    app.load_plugins(app.initial_arg_parser.parse_known_args()[0])
    app.register_settings()
    imports, types = settngs.generate_dict(app.manager.definitions)
    imports2, types2 = settngs.generate_ns(app.manager.definitions)
    i = imports.splitlines()
    i.extend(set(imports2.splitlines()) - set(i))
    return "\n\n".join((imports, types2, types))


if __name__ == "__main__":
    src = generate()
    pathlib.Path("./comictaggerlib/ctsettings/settngs_namespace.py").write_text(src)
    print(src, end="")
