import os
import re
import shutil
import subprocess
import tempfile

ATTACHMENT_DIR = "upload_dir/attachment"
BEGIN_DOCUMENT = r'\documentclass[german,10pt]{book}      \input{preambel.tex}         \begin{document}  \setcounter{chapter}{0}'

PRECHECK_TIMEOUT = 20
BUILD_TIMEOUT = 240

# Topic image folders that the existing chapter sources expect under a specific name.
TOPIC_IMAGE_TARGETS = {
    "Bilder": ["Klass_03_Zeitgleichung", "Klass_05_Uhren", "Klass_08_Nachthimmel",
               "Klass_10_Landkarten", "Klass_11_Hebelgesetze", "Thermo_01_Prozess",
               "Thermo_03_Entropie"],
    "Bilder_ART": ["ART_02_Grundlagen", "ART_05_GravWellen"],
    "Bilder_SRT": ["SRT_03_Kette"],
    "Bilder_QM": ["QM_01_QuBit", "QM_06_EPR_Bell_CHSH"],
}

FILE_LINE_ERROR_RE = re.compile(r"^(?:\./)?([^:\s]+\.tex):(\d+): (.*)$")


class LatexError(Exception):
    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


def copy_dir_files(src, dst):
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isfile(path):
            shutil.copy2(path, dst)


def copy_item_assets(build_dir, item_name, topic_folder_name):
    copy_dir_files(os.path.join(ATTACHMENT_DIR, "Preambel"), build_dir)
    # The preamble's page background lives with the cover page images.
    copy_dir_files(os.path.join(ATTACHMENT_DIR, "Deckblatt", "Bilder"), os.path.join(build_dir, "Bilder"))
    copy_dir_files(os.path.join(ATTACHMENT_DIR, "Bilder"), os.path.join(build_dir, "Bilder"))
    for target, item_names in TOPIC_IMAGE_TARGETS.items():
        if item_name in item_names:
            copy_dir_files(os.path.join(ATTACHMENT_DIR, topic_folder_name, "Bilder"),
                           os.path.join(build_dir, target))


def is_wrapper_line(line):
    return r"\documentclass[german,10pt]" in line or r"\end{document}" in line


def _read_log(build_dir, jobname):
    log_path = os.path.join(build_dir, jobname + ".log")
    if not os.path.exists(log_path):
        return ""
    with open(log_path, encoding="latin-1") as f:
        return f.read()


FOLLOW_UP_MESSAGES = ("Emergency stop.", "==> Fatal error occurred")


def _parse_log(log):
    """Yield (file_name, line_no, message) for each LaTeX error in the log.
    "! ..." errors carry no position, so they take the next reported one."""
    lines = log.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("! "):
            message = line[2:]
            file_name, line_no = None, None
            for follow in lines[i + 1:i + 12]:
                match = FILE_LINE_ERROR_RE.match(follow)
                if match:
                    file_name, line_no = os.path.basename(match.group(1)), int(match.group(2))
                    break
        else:
            match = FILE_LINE_ERROR_RE.match(line)
            if not match:
                continue
            file_name, line_no, message = os.path.basename(match.group(1)), int(match.group(2)), match.group(3)
        if not message.strip().startswith(FOLLOW_UP_MESSAGES):
            yield file_name, line_no, message


def _log_tail(log):
    return [l for l in log.strip().splitlines()[-10:] if l.strip()] or ["Unbekannter LaTeX-Fehler."]


def _extract_errors(log, line_offset=0, main_file=None):
    errors = []
    for file_name, line_no, message in _parse_log(log):
        if line_no is None:
            errors.append(message)
        elif file_name == main_file:
            errors.append(f"Zeile {line_no - line_offset}: {message}")
        else:
            errors.append(f"{file_name}, Zeile {line_no}: {message}")
    return list(dict.fromkeys(errors))[:10] or _log_tail(log)


def run_pdflatex(build_dir, tex_file, timeout, jobname="file"):
    """Run pdflatex non-interactively. Returns (succeeded, log)."""
    env = dict(os.environ, max_print_line="10000")
    cmd = ["pdflatex", "-interaction=nonstopmode", "-file-line-error", "-no-shell-escape",
           "-jobname", jobname, tex_file]
    try:
        result = subprocess.run(cmd, cwd=build_dir, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise LatexError([f"Zeitüberschreitung: LaTeX lief länger als {timeout} Sekunden "
                          "(z. B. durch eine Endlosschleife in einem Makro)."])
    return result.returncode == 0, _read_log(build_dir, jobname)


def run_makeindex(build_dir, jobname="file", timeout=60):
    if not os.path.exists(os.path.join(build_dir, jobname + ".idx")):
        return
    try:
        subprocess.run(["makeindex", jobname + ".idx"], cwd=build_dir, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        pass


def precheck_chapter(source_path, item_name, topic_folder_name):
    """Compile a single chapter the way the PDF export would. Returns a list of
    error messages (empty if the chapter compiles)."""
    build_dir = tempfile.mkdtemp(prefix="check_")
    try:
        copy_item_assets(build_dir, item_name, topic_folder_name)
        with open(source_path, encoding="utf-8", errors="replace") as f_in:
            lines = f_in.readlines()
        with open(os.path.join(build_dir, "check.tex"), "w", encoding="utf-8") as f_out:
            f_out.write(BEGIN_DOCUMENT + "\n")
            for line in lines:
                # Blank out wrapper lines instead of dropping them so line numbers match the upload.
                f_out.write("\n" if is_wrapper_line(line) else line)
            f_out.write("\n\\end{document}\n")
        try:
            ok, log = run_pdflatex(build_dir, "check.tex", PRECHECK_TIMEOUT, jobname="check")
        except LatexError as e:
            return e.errors
        if ok and os.path.exists(os.path.join(build_dir, "check.pdf")):
            return []
        return _extract_errors(log, line_offset=1, main_file="check.tex")
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


def build_pdf(build_dir, chapter_starts):
    """Compile final.tex in build_dir (two passes + index). chapter_starts is a
    list of (first_line, item_name) used to name the chapter an error is in.
    Returns (pdf_path, errors). If LaTeX recovered from errors the PDF is still
    returned together with the errors; raises LatexError if no PDF was produced."""
    ok, log = run_pdflatex(build_dir, "final.tex", BUILD_TIMEOUT)
    run_makeindex(build_dir)
    ok, log = run_pdflatex(build_dir, "final.tex", BUILD_TIMEOUT)
    pdf_path = os.path.join(build_dir, "file.pdf")
    if ok and os.path.exists(pdf_path):
        return pdf_path, []

    errors = []
    for file_name, line_no, message in _parse_log(log):
        if file_name == "final.tex" and line_no is not None:
            chapter = next((name for start, name in reversed(chapter_starts) if start <= line_no), None)
            errors.append(f"{chapter or 'Deckblatt/Vorspann'}: {message}")
        else:
            errors.append(message)
    errors = list(dict.fromkeys(errors))[:10] or _log_tail(log)
    if os.path.exists(pdf_path):
        return pdf_path, errors
    raise LatexError(errors)
