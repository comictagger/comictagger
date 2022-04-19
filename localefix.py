import locale
import logging
import os
import subprocess
import sys


def _lang_code_mac():
    """
    stolen from https://github.com/mu-editor/mu
    Returns the user's language preference as defined in the Language & Region
    preference pane in macOS's System Preferences.
    """

    # Uses the shell command `defaults read -g AppleLocale` that prints out a
    # language code to standard output. Assumptions about the command:
    # - It exists and is in the shell's PATH.
    # - It accepts those arguments.
    # - It returns a usable language code.
    #
    # Reference documentation:
    # - The man page for the `defaults` command on macOS.
    # - The macOS underlying API:
    #   https://developer.apple.com/documentation/foundation/nsuserdefaults.

    lang_detect_command = "defaults read -g AppleLocale"

    status, output = subprocess.getstatusoutput(lang_detect_command)
    if status == 0:
        # Command was successful.
        lang_code = output
    else:
        logging.warning("Language detection command failed: %r", output)
        lang_code = ""

    return lang_code


def configure_locale():
    if sys.platform == "darwin" and "LANG" not in os.environ:
        code = _lang_code_mac()
        if code != "":
            os.environ["LANG"] = f"{code}.utf-8"

    locale.setlocale(locale.LC_ALL, "")
    sys.stdout.reconfigure(encoding=sys.getdefaultencoding())
    sys.stderr.reconfigure(encoding=sys.getdefaultencoding())
    sys.stdin.reconfigure(encoding=sys.getdefaultencoding())
