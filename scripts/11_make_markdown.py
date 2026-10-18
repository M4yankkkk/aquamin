"""
Build the Markdown reports (report/REPORT_full.md, report/REPORT_trimmed.md)
from the LaTeX sources, so the two formats never diverge.

Pipeline: expand \\iffull blocks for the chosen version -> resolve
cross-references (numbers read from the version's .aux) and citations
(numbered as in the PDF) -> pandoc LaTeX->GFM -> tidy figures, tables and
title page. Requires main_<version>.aux, i.e. compile with
`tectonic --keep-intermediates main_<version>.tex` first.
"""

import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LATEX = BASE / "report" / "latex"
OUT_DIR = BASE / "report"
PANDOC = "pandoc"

KIND = {"fig": ("Figure", "Figures"), "tab": ("Table", "Tables"), "sec": ("Section", "Sections"),
        "app": ("Appendix", "Appendices"), "eq": ("Eq.", "Eqs.")}


def expand_inputs(text):
    def rep(m):
        name = m.group(1)
        f = LATEX / (name if name.endswith(".tex") else name + ".tex")
        return expand_inputs(f.read_text())
    return re.sub(r"\\input\{([^}]+)\}", rep, text)


def resolve_if(text, full):
    pat = re.compile(r"\\iffull(.*?)(?:\\else(?![a-zA-Z])(.*?))?\\fi(?![a-zA-Z])(\{\})?", re.S)
    while True:
        m = pat.search(text)
        if not m:
            return text
        repl = m.group(1) if full else (m.group(2) or "")
        text = text[:m.start()] + repl + text[m.end():]


def read_labels(aux):
    labels = {}
    for line in aux.read_text(errors="ignore").splitlines():
        m = re.match(r"\\newlabel\{([^}@]+)\}\{\{([^}]*)\}", line)
        if m:
            labels[m.group(1)] = m.group(2)
    return labels


def cref_text(keys, labels, capital):
    keys = [k.strip() for k in keys.split(",")]
    kinds = {k.split(":")[0] for k in keys}
    nums = [labels.get(k, "?") for k in keys]
    kind = kinds.pop() if len(kinds) == 1 else "sec"
    sing, plur = KIND.get(kind, ("", ""))
    if kind == "eq":
        nums = [f"({n})" for n in nums]
    if len(nums) == 1:
        return f"{sing} {nums[0]}"
    return f"{plur} " + ", ".join(nums[:-1]) + f" and {nums[-1]}"


def read_bib():
    refs = (LATEX / "references.tex").read_text()
    items = re.findall(r"\\bibitem\[([^\]]*)\]\{([^}]+)\}", refs)
    bib = {}
    for i, (opt, key) in enumerate(items, 1):
        author = re.sub(r"\(.*", "", opt).replace("et~al.", "et al.").strip() or "CPCB"
        bib[key] = (i, author)
    return bib


def preprocess(text, labels, bib, full):
    # title page -> handled in post-processing
    text = re.sub(r"\\begin\{titlepage\}.*?\\end\{titlepage\}", "TITLEPAGE_PLACEHOLDER\n", text, flags=re.S)
    text = text.replace("\\tableofcontents", "TOC_PLACEHOLDER")
    text = re.sub(r"\\setcounter\{tocdepth\}\{\d\}", "", text)
    text = text.replace("\\begin{abstract}", "\\section*{Abstract}").replace("\\end{abstract}", "")
    text = re.sub(r"\\begin\{keybox\}\[([^\]]*)\]", r"\\begin{quote}\\textbf{\1}\\par ", text)
    text = text.replace("\\end{keybox}", "\\end{quote}")
    # numbered display equations: keep the PDF number
    text = re.sub(r"\\label\{(eq:[^}]+)\}", lambda m: f"\\tag{{{labels.get(m.group(1), '')}}}", text)
    # cross-references
    text = re.sub(r"\\optref\{([^}]+)\}",
                  lambda m: f" ({cref_text(m.group(1), labels, False)})" if full else "", text)
    text = re.sub(r"\\Cref\{([^}]+)\}", lambda m: cref_text(m.group(1), labels, True), text)
    text = re.sub(r"\\cref\{([^}]+)\}", lambda m: cref_text(m.group(1), labels, False), text)
    # citations
    def citep(m):
        pre = m.group(1) or ""
        nums = ", ".join(str(bib[k.strip()][0]) for k in m.group(2).split(","))
        return f"[{pre + ' ' if pre else ''}{nums}]"
    text = re.sub(r"\\citep(?:\[([^\]]*)\]\[\])?\{([^}]+)\}", citep, text)
    text = re.sub(r"\\citet\{([^}]+)\}",
                  lambda m: "; ".join(f"{bib[k.strip()][1]} [{bib[k.strip()][0]}]" for k in m.group(1).split(",")),
                  text)
    text = re.sub(r"\\paragraph\{([^}]*)\}", lambda m: "\\textbf{" + m.group(1).rstrip(".") + ".} ", text)
    # units and macros pandoc does not know
    text = text.replace("\\si{\\micro S/cm}", "µS/cm").replace("\\si{\\celsius}", "°C")
    text = re.sub(r"\\sub\{([^}]*)\}", r"\\texttt{\1}", text)
    text = text.replace("\\clearpage", "").replace("\\appendix", "APPENDIX_PLACEHOLDER")
    text = text.replace("\\begin{small}", "").replace("\\end{small}", "")
    # bibliography -> numbered list (same order/numbers as the PDF)
    text = re.sub(r"\\begin\{thebibliography\}\{\d+\}", r"\\section*{References}\\begin{enumerate}", text)
    text = text.replace("\\end{thebibliography}", "\\end{enumerate}")
    text = re.sub(r"\\bibitem\[[^\]]*\]\{[^}]+\}", r"\\item ", text)
    text = text.replace("\\newblock", "")
    # figures -> PNG paths relative to report/
    def img(m):
        name = Path(m.group(1)).stem
        if (LATEX / "diagrams" / f"{name}.png").exists():
            path = f"latex/diagrams/{name}.png"
        else:
            path = f"../figures/{name}.png"
        return f"\\includegraphics{{{path}}}"
    text = re.sub(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", img, text)
    return text


def postprocess(md, labels, full):
    # figures: <figure id=..><img ...><figcaption>..</figcaption></figure>
    def fig(m):
        block = m.group(0)
        fid = re.search(r'<figure id="([^"]+)"', block)
        srcs = re.findall(r'<(?:img|embed) src="([^"]+)"', block)
        caps = re.findall(r"<figcaption>(.*?)</figcaption>", block, re.S)
        num = labels.get(fid.group(1), "") if fid else ""
        cap = re.sub(r"\s+", " ", caps[-1]).strip() if caps else ""
        imgs = "\n".join(f'<img src="{s}" width="{900 if len(srcs) == 1 else 440}">' for s in srcs)
        head = f"**Figure {num}.** " if num else ""
        return f'<p align="center">\n{imgs}\n</p>\n\n> {head}{cap}\n'
    md = re.sub(r"<figure[^>]*>.*?</figure>\n?(?:\s*</figure>)?", fig, md, flags=re.S)
    # tables: <div id="tab:x"> table caption </div> -> caption first
    def tab(m):
        tid, body = m.group(1), m.group(2).strip()
        parts = body.rsplit("\n\n", 1)
        table, cap = (parts[0], parts[1]) if len(parts) == 2 else (body, "")
        return f"**Table {labels.get(tid, '')}.** {cap.strip()}\n\n{table}\n"
    md = re.sub(r'<div id="(tab:[^"]+)">\s*(.*?)\s*</div>', tab, md, flags=re.S)
    md = re.sub(r'<div[^>]*>\s*', "", md).replace("</div>", "")
    md = md.replace("<!-- -->", "")
    for a, b in [("R$`^2`$", "R²"), ("$`\\pm`$", "±"), ("$`\\approx`$", "≈"), ("$`\\ge`$", "≥"),
                 ("$`\\le`$", "≤"), ("$`\\times`$", "×"), ("$`\\to`$", "→"), ("$`k`$", "*k*"),
                 ("$`\\leftrightarrow`$", "↔"), ("$`>`$", ">"), ("$`<`$", "<")]:
        md = md.replace(a, b)
    # section numbers from the aux file
    return md


def number_headings(md, full):
    out, h1, h2, h3, appendix, fence = [], 0, 0, 0, False, False
    for line in md.splitlines():
        if line.startswith("```"):
            fence = not fence
        if fence or line.startswith("    "):
            out.append(line)
            continue
        if line.strip() == "APPENDIX_PLACEHOLDER":
            appendix, h1 = True, 0
            continue
        m = re.match(r"^(#{1,3}) (.*)$", line)
        if m and not line.startswith("# Abstract") and not line.startswith("# References"):
            lvl, title = len(m.group(1)), m.group(2)
            if lvl == 1:
                h1, h2, h3 = h1 + 1, 0, 0
                tag = chr(64 + h1) if appendix else str(h1)
                line = f"## {'Appendix ' if appendix else ''}{tag}. {title}" if appendix else f"## {tag}. {title}"
            elif lvl == 2:
                h2, h3 = h2 + 1, 0
                tag = chr(64 + h1) if appendix else str(h1)
                line = f"### {tag}.{h2} {title}"
            else:
                h3 += 1
                line = f"#### {title}"
        elif line.startswith("# Abstract"):
            line = "## Abstract"
        elif line.startswith("# References"):
            line = "## References"
        elif line.startswith("#### "):
            # \paragraph -> bold lead-in
            line = "**" + line[5:].rstrip(".") + ".**"
        out.append(line)
    return "\n".join(out)


def toc(md):
    lines = ["## Contents", ""]
    for line in md.splitlines():
        m = re.match(r"^(##|###) (.*)$", line)
        if m and m.group(2) not in ("Contents",):
            title = m.group(2)
            anchor = re.sub(r"[^\w\- ]", "", title.lower()).strip().replace(" ", "-")
            indent = "" if m.group(1) == "##" else "  "
            lines.append(f"{indent}- [{title}](#{anchor})")
    return "\n".join(lines)


TITLE = """<p align="center"><b>NATIONAL INSTITUTE OF TECHNOLOGY KARNATAKA, SURATHKAL</b></p>

<p align="center"><img src="latex/figures/nitk_logo.png" width="260"></p>

<h1 align="center">Reduced-Parameter Water Quality Index Prediction for Data-Scarce River Systems</h1>

<p align="center"><i>Evidence from the CPCB National Water Quality Monitoring Programme, 2018–2021</i><br>
Final Project Report{version}</p>

<p align="center"><b>Course:</b> CV301: Environmental Engineering &nbsp;·&nbsp; <b>Faculty:</b> Saranya P</p>

<div align="center">

| Team member | Roll number |
|---|---|
| Mayank Tiwari | 241CV235 |
| Krupa Marol | 241CV231 |
| Srushti Dongre | 241CV248 |
| Sreenidhi Golamaru | 241CV247 |
| Bharath Chowdary | 241CV213 |

October 2026

</div>

---
"""


def build(version):
    full = version == "full"
    aux = LATEX / f"main_{version}.aux"
    labels = read_labels(aux)
    bib = read_bib()
    tex = expand_inputs((LATEX / "body.tex").read_text())
    tex = resolve_if(tex, full)
    tex = preprocess(tex, labels, bib, full)
    macros = (LATEX / "preamble.tex").read_text()
    macros = "\n".join(l for l in macros.splitlines() if l.startswith("\\newcommand{\\R}")
                       or l.startswith("\\newcommand{\\wqi}"))
    src = "\\documentclass{article}\n" + macros + "\n\\begin{document}\n" + tex + "\n\\end{document}\n"
    tmp = OUT_DIR / f".tmp_{version}.tex"
    tmp.write_text(src)
    md = subprocess.run([PANDOC, str(tmp), "-f", "latex", "-t", "gfm", "--wrap=none"],
                        capture_output=True, text=True, check=True).stdout
    tmp.unlink()
    md = postprocess(md, labels, full)
    md = number_headings(md, full)
    md = md.replace("TITLEPAGE_PLACEHOLDER", TITLE.format(version="" if full else " (condensed version)"))
    md = md.replace("TOC_PLACEHOLDER", toc(md))
    md = re.sub(r"\n{3,}", "\n\n", md)
    out = OUT_DIR / f"REPORT_{version}.md"
    out.write_text(md)
    print(f"wrote {out} ({len(md.splitlines())} lines)")


if __name__ == "__main__":
    for v in (sys.argv[1:] or ["full", "trimmed"]):
        build(v)
