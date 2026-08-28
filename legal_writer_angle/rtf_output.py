from pathlib import Path
from typing import Iterable


def write_txt_lines(out_path: str, lines: Iterable[str]):
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_rtf_lines(out_path: str, lines: Iterable[str]):
    def esc(text: str) -> str:
        return text.replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}')

    body = "\\par\n".join(esc(line) for line in lines)
    rtf = r"{\rtf1\ansi\deff0{\fonttbl{\f0 Times New Roman;}}\f0\fs24 " + body + "}"
    Path(out_path).write_text(rtf, encoding="utf-8")
