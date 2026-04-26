#!/usr/bin/env bash
#
# build.sh — 将 js/ ESM 源码合并回单文件 经营分析模板.html
#
# 用法：
#   ./build.sh                输出 dist/经营分析模板.html
#   ./build.sh --check        仅校验（构建后报告差异行数）
#   ./build.sh --in-place     覆盖根目录的 经营分析模板.html（慎用）
#
# 依赖：bash 3.2+ / sed / awk（macOS 与 Linux 默认环境可用）
#
# 拓扑顺序：
#   1) js/core/*.js   按字母序
#   2) js/modules/*/*.js  按字母序
#
# 注入位置：
#   <!-- BUILD:JS:CORE -->  注释行整行被替换为 <script>...合并代码...</script>
#

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

TEMPLATE="经营分析模板.html"
OUT_DIR="dist"
OUT="$OUT_DIR/经营分析模板.html"

MODE="default"
case "${1:-}" in
  --check)    MODE="check" ;;
  --in-place) MODE="in-place"; OUT="$TEMPLATE" ;;
  "")         MODE="default" ;;
  *)
    echo "未知参数：$1" >&2
    echo "用法：$0 [--check | --in-place]" >&2
    exit 2
    ;;
esac

[[ -f "$TEMPLATE" ]] || { echo "ERROR: 找不到 $TEMPLATE" >&2; exit 1; }

if ! grep -q '<!-- BUILD:JS:CORE -->' "$TEMPLATE"; then
  echo "ERROR: $TEMPLATE 中找不到 <!-- BUILD:JS:CORE --> 标记" >&2
  exit 1
fi

TMP="$(mktemp -t jyfx_build.XXXXXX)"
trap 'rm -f "$TMP" "$TMP.html"' EXIT

# ---- 1) 合并 ESM 源码 ----
strip_esm() {
  # 简易 ESM 剥离：
  #   - 去掉 `export ` 前缀（保留 function/const/let/var/class/async）
  #   - 去掉所有相对路径 import 行（已合并入下方）
  sed -E '
    s/^([[:space:]]*)export[[:space:]]+(default[[:space:]]+)?(async[[:space:]]+)?(function|const|let|var|class)/\1\3\4/;
    /^[[:space:]]*import[[:space:]].*from[[:space:]]+["'\''\`]\.\.?\/.*["'\''\`][[:space:]]*;?[[:space:]]*$/d;
  ' "$1"
}

{
  echo "// === 自动生成 by build.sh ；勿手工修改 ==="
  echo "// 源码：js/core/*.js + js/modules/*/*.js"
  echo "// 重新生成：./build.sh"

  # core/
  for f in js/core/*.js; do
    [[ -e "$f" ]] || continue
    echo
    echo "// ---- $f ----"
    strip_esm "$f"
  done

  # modules/
  for f in js/modules/*/*.js; do
    [[ -e "$f" ]] || continue
    echo
    echo "// ---- $f ----"
    strip_esm "$f"
  done
} > "$TMP"

CORE_LINES=$(wc -l < "$TMP" | tr -d ' ')

# ---- 2) 替换标记 ----
mkdir -p "$OUT_DIR"

awk -v js_file="$TMP" '
  /<!-- BUILD:JS:CORE -->/ {
    print "<!-- 以下区块由 build.sh 自动生成；源码位于 js/ 目录 -->"
    print "<script>"
    while ((getline line < js_file) > 0) print line
    close(js_file)
    print "</script>"
    print "<!-- /build.sh -->"
    next
  }
  { print }
' "$TEMPLATE" > "$TMP.html"

case "$MODE" in
  check)
    TPL_LINES=$(wc -l < "$TEMPLATE" | tr -d ' ')
    OUT_LINES=$(wc -l < "$TMP.html" | tr -d ' ')
    echo "模板行数: $TPL_LINES"
    echo "合并后行数: $OUT_LINES"
    echo "注入 JS 行数: $CORE_LINES"
    echo "(--check 模式不写文件)"
    ;;
  in-place|default)
    cp "$TMP.html" "$OUT"
    echo "✓ Built: $OUT  (注入 $CORE_LINES 行)"
    ;;
esac
