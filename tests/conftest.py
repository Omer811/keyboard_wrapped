import sys
import types
from types import SimpleNamespace

try:
    import pynput  # noqa: F401
except ImportError:
    class StubKey:
        def __init__(self, name: str):
            self.name = name

        def __str__(self) -> str:
            return f"Key.{self.name}"

        def __repr__(self) -> str:
            return str(self)

    class StubKeyCode:
        def __init__(self, char: str):
            self.char = char

        @classmethod
        def from_char(cls, char: str) -> "StubKeyCode":
            return cls(char)

        def __hash__(self) -> int:
            return hash(self.char)

    class StubListener:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self) -> "StubListener":
            return self

        def __exit__(self, *_) -> None:
            pass

        def join(self) -> None:
            pass

        def stop(self) -> None:
            pass

    keyboard_mod = types.SimpleNamespace(
        Key=SimpleNamespace(
            space=StubKey("space"),
            enter=StubKey("enter"),
            tab=StubKey("tab"),
            shift_r=StubKey("shift_r"),
        ),
        KeyCode=StubKeyCode,
        Listener=StubListener,
    )

    pynput_stub = types.SimpleNamespace(keyboard=keyboard_mod)
    sys.modules["pynput"] = pynput_stub
    sys.modules["pynput.keyboard"] = keyboard_mod
