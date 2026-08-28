\
def _rtf_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    return s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\par\n")

def write_rtf_lines(out_path: str, lines):
    body = "\n".join(lines).rstrip()
    rtf = (
        "{\\rtf1\\ansi\\deff0"
        "{\\fonttbl{\\f0 Times New Roman;}}"
        "\\fs24\n"
        + _rtf_escape(body) +
        "\n}"
    )
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rtf)

def write_txt_lines(out_path: str, lines):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
