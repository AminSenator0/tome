from pathlib import Path
p = Path(r"E:\SITE\tran\web\src\views\PipelineView.tsx")
src = p.read_text(encoding="utf-8")
old = "                </Button>\n              )\n            </CardHeader>"
new = "                </Button>\n              )}\n            </CardHeader>"
assert src.count(old) == 1, f"count={src.count(old)}"
p.write_text(src.replace(old, new), encoding="utf-8")
print("fixed OK")
