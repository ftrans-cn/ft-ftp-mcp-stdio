"""PoC 测试数据集生成脚本（对应 PRD v0.8 第七章基准任务集与 7.1 兼容矩阵）。

在本地生成 fixtures/ 目录树，供 upload_fixtures.py 推送到 FTP/SFTP 测试服务器。
覆盖验收所需的数据形态：

- GBK 命名目录与文件（编码验证第一杀手，PRD 5.3 ③）
- UTF-8 命名目录与文件
- 深层嵌套目录（5 层，命中 search_files 递归深度上限）
- 空目录（delete/make_dir/download_dir 边界用例）
- 中文表头 CSV（报表拉取任务、read_text_preview 用例）
- 批量、文本预览、覆盖冲突、软链接与低阈值超限用例
- 可选超大文件（--big-gb，上传逐文件大小上限用例，稀疏文件不占真实磁盘）

用法：
    python scripts/make_fixtures.py            # 默认生成到 ./fixtures/
    python scripts/make_fixtures.py -o /tmp/fx # 指定输出目录
    python scripts/make_fixtures.py --big-gb 2 # 追加一个 2GB 稀疏大文件
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

GKB = "gbk"


def write_csv(path: Path, rows: int = 200) -> None:
    """生成中文表头 CSV：日期,门店,商品,数量,金额。"""
    rnd = random.Random(42)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["日期", "门店", "商品", "数量", "金额"])
        for i in range(rows):
            w.writerow(
                [
                    f"2026-09-{(i % 28) + 1:02d}",
                    rnd.choice(["南京新街口店", "苏州工业园店", "上海徐汇店", "杭州西湖店"]),
                    rnd.choice(["矿泉水", "方便面", "咖啡豆", "纸巾", "洗衣液"]),
                    rnd.randint(1, 99),
                    f"{rnd.uniform(10, 5000):.2f}",
                ]
            )


def build(root: Path, with_symlink: bool = False) -> None:
    root.mkdir(parents=True, exist_ok=True)

    # ① GBK 命名区（模拟国内 GBK 服务器上常见的中文目录/文件名）
    gbk = root / "报表"
    gbk.mkdir(exist_ok=True)
    write_csv(gbk / "昨日订单.csv", rows=200)
    (gbk / "上周对账单.csv").write_text("对账单编号,金额,状态\nDZ-2026-001,1280.00,已确认\n", encoding="utf-8")
    (gbk / "2026-08月度汇总.txt").write_text("8月汇总：详见附件。\n", encoding="utf-8")

    # ② UTF-8 命名区（现代服务器默认编码）
    utf8 = root / "reports_2026" / "analysis"
    utf8.mkdir(parents=True, exist_ok=True)
    (utf8 / "summary_2026-08.csv").write_text("month,revenue\n2026-08,98213.50\n", encoding="utf-8")
    (utf8 / "README.txt").write_text("UTF-8 encoding zone for compat tests.\n", encoding="utf-8")

    # ③ 深层嵌套（5 层，验证 search_files 递归深度上限）
    deep = root / "archive" / "2024" / "Q4" / "十二月" / "结算"
    deep.mkdir(parents=True, exist_ok=True)
    (deep / "deep_target.csv").write_text("层级,说明\n5,最深目标文件\n", encoding="utf-8")

    # ④ 空目录（删除/建目录/批量传输边界）
    (root / "空目录测试").mkdir(exist_ok=True)

    # ⑤ 边界文件名（通配符搜索/特殊字符）
    boundary = root / "边界用例"
    boundary.mkdir(exist_ok=True)
    (boundary / "对账 v2(终版).csv").write_text("id,note\n1,括号空格用例\n", encoding="utf-8")
    (boundary / "NOTES.md").write_text("# should match *.md search\n", encoding="utf-8")
    (boundary / "大写.TXT").write_text("uppercase ext test\n", encoding="utf-8")

    # ⑥ MVP 共用：批量传输、文本预览、覆盖冲突与低阈值超限。
    batch = root / "批量传输" / "嵌套"
    batch.mkdir(parents=True, exist_ok=True)
    for index in range(12):
        (batch / f"item-{index:02d}.txt").write_text(f"batch item {index}\n", encoding="utf-8")
    (root / "批量传输" / "空子目录").mkdir(exist_ok=True)
    preview = root / "文本预览"
    preview.mkdir(exist_ok=True)
    preview_text = "列一,列二\n" + "中文,preview\n" * 1024
    (preview / "utf8.csv").write_text(preview_text, encoding="utf-8")
    (preview / "gbk.csv").write_text(preview_text, encoding="gbk")
    (boundary / "单文件超限.bin").write_bytes(b"x" * 2049)
    (boundary / "覆盖冲突.txt").write_text("existing target\n", encoding="utf-8")
    (boundary / "软链接目标.txt").write_text("symlink target\n", encoding="utf-8")
    if with_symlink:
        link = boundary / "软链接用例.txt"
        if not link.exists():
            link.symlink_to("软链接目标.txt")


def make_big_file(path: Path, size_gb: float) -> None:
    """稀疏大文件：秒级生成，不占真实磁盘（NTFS/APFS/ext4 均支持）。"""
    with path.open("wb") as f:
        f.seek(int(size_gb * 1024**3) - 1)
        f.write(b"\0")


def main() -> None:
    ap = argparse.ArgumentParser(description="生成 PoC 测试数据集")
    ap.add_argument("-o", "--out", default="fixtures", help="输出目录（默认 ./fixtures）")
    ap.add_argument("--big-gb", type=float, default=0.0, help="额外生成 N GB 稀疏大文件（默认不生成）")
    ap.add_argument("--with-symlink", action="store_true", help="创建软链接用例（需要操作系统权限）")
    args = ap.parse_args()

    root = Path(args.out)
    build(root, with_symlink=args.with_symlink)
    if args.big_gb > 0:
        make_big_file(root / "报表" / f"bigfile_{args.big_gb:g}GB.bin", args.big_gb)

    n_files = sum(1 for p in root.rglob("*") if p.is_file())
    print(f"测试数据集已生成：{root.resolve()}（{n_files} 个文件）")
    print("下一步：python scripts/upload_fixtures.py --server <alias> --confirm 推送到隔离测试目录")


if __name__ == "__main__":
    main()
