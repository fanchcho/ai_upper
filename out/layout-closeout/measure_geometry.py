import json
from pathlib import Path
for label in ["before", "after"]:
    blocks = json.loads(Path("out/layout-closeout/"+label+"-layout.json").read_text())["blocks"]
    def item(text): return next(b for b in blocks if text in b["text"])
    print(label,
          "list_advance", item("再看依赖")["y"]-item("先读 README")["y"],
          "list_boundary_advance", item("无序项一")["y"]-item("最后跑测试")["y"],
          "last_cell_to_paragraph", item("要点：")["y"]-item("依赖清单")["y"]-item("依赖清单")["height"],
          "quote_line_advance", item("嵌套引用第二层")["y"]-item("引用第一层")["y"])
