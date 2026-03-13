#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Terminal input helpers for CLI applications.

Provides:
- Password input with asterisk masking
- Smart input with proper backspace handling
- TTY detection for piped input support
"""
import getpass
import sys
from typing import Optional


def _is_tty() -> bool:
    return sys.stdin.isatty()


def get_password(prompt: str = "Password: ") -> str:
    """Get password input (masked in TTY, plain in piped mode)."""
    if _is_tty():
        return getpass.getpass(prompt)
    else:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return sys.stdin.readline().rstrip("\n")


def masked_input(prompt: str = "") -> str:
    """Read password input with asterisk masking."""
    try:
        import tty
        import termios

        sys.stdout.write(prompt)
        sys.stdout.flush()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        password = []
        try:
            tty.setraw(fd)
            while True:
                char = sys.stdin.read(1)
                if char in ('\r', '\n'):
                    sys.stdout.write('\r\n')
                    break
                elif char in ('\x7f', '\x08'):
                    if password:
                        password.pop()
                        sys.stdout.write('\b \b')
                elif char == '\x1b':
                    _consume_escape_sequence()
                elif char == '\x03':
                    sys.stdout.write('\r\n')
                    raise KeyboardInterrupt
                elif ord(char) < 32:
                    pass
                else:
                    password.append(char)
                    sys.stdout.write('*')
                sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return ''.join(password)
    except (ImportError, OSError, Exception):
        return getpass.getpass(prompt)


def smart_input(prompt: str = "") -> str:
    """Read input with proper backspace handling."""
    try:
        import tty
        import termios

        sys.stdout.write(prompt)
        sys.stdout.flush()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        chars = []
        try:
            tty.setraw(fd)
            while True:
                char = sys.stdin.read(1)
                if char in ('\r', '\n'):
                    sys.stdout.write('\r\n')
                    break
                elif char in ('\x7f', '\x08'):
                    if chars:
                        chars.pop()
                        sys.stdout.write('\b \b')
                elif char == '\x1b':
                    _consume_escape_sequence()
                elif char == '\x03':
                    sys.stdout.write('\r\n')
                    raise KeyboardInterrupt
                elif ord(char) < 32:
                    pass
                else:
                    chars.append(char)
                    sys.stdout.write(char)
                sys.stdout.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return ''.join(chars)
    except (ImportError, OSError, Exception):
        return input(prompt)


def _consume_escape_sequence():
    try:
        next_char = sys.stdin.read(1)
        if next_char == '[':
            while True:
                seq_char = sys.stdin.read(1)
                if seq_char.isalpha() or seq_char == '~':
                    break
    except Exception:
        pass


def confirm(prompt: str, default: Optional[bool] = None) -> bool:
    """Ask for yes/no confirmation."""
    if default is None:
        suffix = "(y/n): "
    elif default:
        suffix = "[Y/n]: "
    else:
        suffix = "[y/N]: "

    while True:
        response = smart_input(f"{prompt} {suffix}").strip().lower()
        if response == "" and default is not None:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'.")


def prompt_with_default(prompt: str, default: str = "") -> str:
    """Prompt for input with a default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    response = smart_input(full_prompt).strip()
    return response if response else default
