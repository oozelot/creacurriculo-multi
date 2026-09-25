import pathlib

p = pathlib.Path(r"c:\Users\andrea\Desktop\CURRICOLO\main.py")
src = p.read_text(encoding="utf-8")
lines = src.splitlines()
try:
    compile(src, str(p), "exec")
    print("OK")
except SyntaxError as e:
    print("line", e.lineno)
    print("offset", e.offset)
    print("text", repr(e.text))
    start = max(1, e.lineno - 3)
    end = min(len(lines), e.lineno + 3)
    for i in range(start, end + 1):
        print(f"{i}: {lines[i - 1]!r}")
