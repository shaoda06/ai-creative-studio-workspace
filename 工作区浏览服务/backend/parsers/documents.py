"""Common document rendering without project directory or business-flow rules."""
import codecs
import hashlib
import html
import posixpath
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

TEXT_PREVIEW_LIMIT = 256 * 1024



INLINE_PATTERN = r"(\x60+)(.+?)\1|!?\[([^\]]*)\]\((<[^>]+>|[^)\n]+)\)|\*\*(.+?)\*\*"



STATUS_COLORS = {
    **dict.fromkeys(("已完成", "已确认", "已定稿", "通过", "批准采用", "已采用", "成功", "success"), "green"),
    **dict.fromkeys(("进行中", "运行中", "running"), "blue"),
    **dict.fromkeys(("待确认", "部分确认", "待审核", "待核对", "修改后再审", "状态不明", "unknown"), "orange"),
    **dict.fromkeys(("失败", "异常", "不通过", "failed"), "red"),
    **dict.fromkeys(("未开始", "未确认", "排队中", "未采用", "不采用", "未送审", "已被替换／归档", "已结束未采用", "未记录", "不适用", "待完成", "queued"), "gray"),
}



STATUS_FIELDS = {"状态", "当前状态", "确认状态", "画风确认状态", "画幅确认状态", "适配确认状态", "执行状态", "真实执行状态", "技术检查结论", "文件核对结论",
                 "agent 技术审查结论", "agent 内容审查状态", "agent 初审结论", "agent初审结论", "agent 画面初审结论", "用户采用状态", "用户决定"}



def plain_text_preview(path):
    digest, prefix, total = hashlib.sha256(), bytearray(), 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
            total += len(chunk)
            prefix.extend(chunk[:max(0, TEXT_PREVIEW_LIMIT - len(prefix))])
    truncated = total > TEXT_PREVIEW_LIMIT
    notice = "仅截取前256 KiB供预览；完整内容请打开原文件。" if truncated else ""
    try:
        text = codecs.getincrementaldecoder("utf-8-sig")().decode(bytes(prefix), final=not truncated)
    except UnicodeDecodeError:
        text, notice = "", "文件不是有效的UTF-8文本，无法页内预览；请打开原文件。"
    return {"text": text, "notice": notice}, digest.hexdigest()



def status_markup(value, source):
    """Style a declared status only; retain qualifiers and never infer approval."""
    names = "|".join(re.escape(s) for s in sorted(STATUS_COLORS, key=len, reverse=True))
    match = re.match(r"^(" + names + r")(?=$|[\s；;，,。：（(])", value)
    label = match.group(1) if match else value
    suffix = value[len(label):]
    color = STATUS_COLORS.get(label, "gray")
    return '<span class="status-badge status-' + color + '">' + inline(label, source) + '</span>' + inline(suffix, source)



def field_markup(text, source):
    match = re.match(r"^([^：:]+)([：:][ \t]*)(.*)$", text)
    if match and match.group(1).strip() in STATUS_FIELDS:
        return inline(match.group(1) + match.group(2), source) + status_markup(match.group(3), source)
    return inline(text, source)



def safe_link(target, source):
    """Resolve a Markdown link relative to its source, not relative to the HTML."""
    target = target.strip().strip("<>")
    if any(ord(c) < 32 for c in target) or "\\" in target:
        return None, None
    parsed = urlsplit(target)
    if parsed.scheme:
        if parsed.scheme.lower() not in ("https", "http", "thread", "mailto"):
            return None, None
        return target, None
    if target.startswith("//"):
        return None, None
    path = unquote(parsed.path)
    if path.startswith("/"):
        return None, None
    source = source.replace("\\", "/")
    key = posixpath.normpath(posixpath.join(posixpath.dirname(source), path)) if path else source
    href = quote(key, safe="/-._~") + ("?" + parsed.query if parsed.query else "")
    if parsed.fragment:
        href += "#" + quote(unquote(parsed.fragment), safe="-._~")
    return href, key



def inline(text, source):
    output, offset = [], 0
    for match in re.finditer(INLINE_PATTERN, text):
        output.append(html.escape(text[offset:match.start()]))
        if match.group(1):
            output.append("<code>" + html.escape(match.group(2)) + "</code>")
        elif match.group(3) is not None:
            href, key = safe_link(match.group(4), source)
            label = html.escape(match.group(3))
            if href is None:
                output.append(label + "（不支持的链接）")
            else:
                attrs = (' data-doc="' + html.escape(key, quote=True) + '"') if key else ""
                output.append('<a href="' + html.escape(href, quote=True) + '"' + attrs
                              + '>' + label + "</a>")
        else:
            output.append("<strong>" + html.escape(match.group(5)) + "</strong>")
        offset = match.end()
    output.append(html.escape(text[offset:]))
    return "".join(output)



def cells(line):
    return [part.strip().replace(r"\|", "|") for part in re.split(r"(?<!\\)\|", line.strip().strip("|"))]



def phase_list(text, source):
    items = [re.sub(r"^-\s+", "", item.strip()) for item in text.split("<br>")]
    return "<ul>" + "".join("<li>" + inline(item, source) + "</li>" for item in items) + "</ul>"



def slug(text):
    return re.sub(r"[^\w\u3400-\u9fff -]", "", text.lower()).replace(" ", "-")



def markdown(text, source, *, style_samples=False):
    """Render headings, paragraphs, lists, tables, quotes and code.
    Raw HTML is escaped; unknown Markdown stays readable as source text.
    """
    lines, out, i, anchors = text.splitlines(), [], 0, {}
    in_header = True
    metadata_field = r"^(?:项目名称或代号|文档版本|更新日期|确认状态|确认范围|确认依据|确认说明|制作目标|阅读边界)[:：]"
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        fence = re.match(r"^\s*(\x60{3,}|~{3,})", line)
        if fence:
            marker, chunk = fence.group(1), []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith(marker):
                chunk.append(lines[i])
                i += 1
            out.append("<pre><code>" + html.escape("\n".join(chunk)) + "</code></pre>")
            i += 1
            continue
        sample = re.fullmatch(r"\s*!\[([^\]]*)\]\(([^)]+)\)\s*", line) if style_samples else None
        if sample:
            href, key = safe_link(sample.group(2), source)
            if key and not key.startswith("../") and Path(key).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                url = html.escape(href, quote=True)
                label = html.escape(sample.group(1), quote=True)
                figure = ('<figure class="style-sample"><a href="' + url
                           + '" target="_blank" rel="noopener"><img src="' + url
                           + '" alt="' + label + '" loading="lazy"></a><figcaption>'
                           + label + '</figcaption></figure>')
                if out and re.match(r"<p>(女性|男性)样例", out[-1]):
                    caption = out.pop()
                    gender = "male" if caption.startswith("<p>男性") else "female"
                    out.append('<div class="style-sample-card" data-gender="' + gender + '">' + caption + figure + '</div>')
                else:
                    out.append(figure)
                i += 1
                continue
        if line.strip() == "——编制信息——":
            out.append('<details class="intro"><summary>编制信息</summary>'
                       + markdown("\n".join(lines[i + 1:]), source, style_samples=style_samples) + "</details>")
            break
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level, content = len(heading.group(1)), heading.group(2)
            if level >= 2:
                in_header = False
            anchor = slug(content)
            count = anchors.get(anchor, 0)
            anchors[anchor] = count + 1
            if count:
                anchor += "-" + str(count)
            out.append(f'<h{level} id="{html.escape(anchor, quote=True)}">'
                       + inline(content, source) + f"</h{level}>")
            i += 1
            continue
        separator = i + 1
        if "|" in line:
            while separator < len(lines) and not lines[separator].strip():
                separator += 1
        if separator < len(lines) and "|" in line and re.fullmatch(
                r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*", lines[separator]):
            headers = cells(line)
            progress_table = headers == ["阶段名称", "对应会话入口", "当前状态", "成果入口", "待决事项", "下一步"]
            i = separator + 1
            rows = []
            while i < len(lines):
                if not lines[i].strip():
                    i += 1
                    continue
                if "|" not in lines[i]:
                    break
                row = cells(lines[i])
                anchor = ' id="phase-' + slug(row[0]) + '"' if progress_table else ""
                rows.append("<tr" + anchor + ">" + "".join("<td>" + (
                    status_markup(c, source) if j < len(headers) and headers[j] in STATUS_FIELDS
                    else phase_list(c, source) if progress_table and j in (4, 5)
                    else inline(c, source)) + "</td>" for j, c in enumerate(row)) + "</tr>")
                i += 1
            out.append('<div class="table-scroll"><table><thead><tr>'
                       + "".join("<th>" + inline(c, source) + "</th>" for c in headers)
                       + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
            continue
        bullet = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$", line)
        if bullet:
            ordered = bool(re.match(r"^\s*\d", line))
            tag, items = ("ol" if ordered else "ul"), []
            while i < len(lines):
                item = re.match(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$", lines[i])
                if not item or bool(re.match(r"^\s*\d", lines[i])) != ordered:
                    break
                note = in_header and re.match(metadata_field, item.group(1))
                css = ' class="document-note"' if note else ""
                items.append(f"<li{css}>" + field_markup(item.group(1), source) + "</li>")
                i += 1
            css = ' class="document-notes"' if all(item.startswith('<li class="document-note">') for item in items) else ""
            out.append(f"<{tag}{css}>" + "".join(items) + f"</{tag}>")
            continue
        if re.fullmatch(r"\s*(---+|\*\*\*+)\s*", line):
            out.append("<hr>")
        elif line.startswith(">"):
            out.append("<blockquote>" + inline(line.lstrip("> "), source) + "</blockquote>")
        else:
            css = ' class="document-note"' if in_header and re.match(metadata_field, line) else ""
            out.append(f"<p{css}>" + field_markup(line, source) + "</p>")
        i += 1
    rendered = "\n".join(out)
    if style_samples:
        # Fixed sample sections own their title, approved image and record fields.
        def sample_section(match):
            heading, content = match[1], match[3]
            resolution = re.search(r'<li>分辨率[:：]\s*(.*?)</li>', content, re.S)
            if resolution:
                heading = heading.replace('</h4>', '，' + resolution[1] + '</h4>')
                content = content[:resolution.start()] + content[resolution.end():]
            content = re.sub(r'<figcaption>.*?</figcaption>', '', content, flags=re.S)
            if '<figure class="style-sample">' not in content:
                return heading + content
            return ('<div class="style-sample-card" data-gender="'
                    + ('male' if match[2] == '男性样例' else 'female') + '">'
                    + heading + content + '</div>')
        rendered = re.sub(r'(<h4 id="[^"]+">(男性样例|女性样例)</h4>\n)(.*?)(?=\n<h[1-4]\b|\Z)',
                          sample_section,
                          rendered, flags=re.S)
        rendered = re.sub(r'(?:<div class="style-sample-card"[^>]*>.*?</div>\n?)+',
                          lambda match: '<div class="style-samples">' + match[0] + '</div>',
                          rendered, flags=re.S)
    return rendered
