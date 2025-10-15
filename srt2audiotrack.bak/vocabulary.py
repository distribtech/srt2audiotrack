import re
from pathlib import Path
from functools import reduce

def check_vocabular(voice_dir):
    """Ensure a vocabulary file exists in ``voice_dir``.

    If the ``vocabular.txt`` file is missing, an empty file will be created so
    the pipeline can continue without manual intervention.  The path to the
    vocabulary file is always returned.
    """

    vocabular_pth = Path(voice_dir) / "vocabular.txt"
    if not vocabular_pth.is_file():
        print(f"Vocabulary file not found at {vocabular_pth}, creating default.")
        vocabular_pth.parent.mkdir(parents=True, exist_ok=True)
        vocabular_pth.write_text("", encoding="utf-8")
    else:
        print(f"Vocabulary file is {vocabular_pth}.")
    return vocabular_pth

def two_cases(title):
    if not title:
       return '',''
    return title[0].upper() + title[1:], title[0].lower() + title[1:]

def parse_vocabular_file(vocabular_path):
    """
    Parses a vocabular file with lines like:
        Kiyv<=>Kiev
        Ekaterina II<=>Ekaterina druga
    Returns a list of tuples [("Kiyv","Kiev"), ("Ekaterina II","Ekaterina druga")].
    """
    replacements = []
    with open(vocabular_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            # Expect a separator <=>
            if '<=>' in line:
                old, new = line.split('<=>', 1)
                new_upper, new_lower = two_cases(new.strip())
                old_strip = old.strip()
                replacements.append((old_strip, new_upper))
                replacements.append((old_strip, new_lower))
    # Sort by length of the old string, descending (longest first).
    replacements.sort(key=lambda x: len(x[0]), reverse=True)
    return replacements



def apply_replacements(line, replacements, whole_words=True):
    """
    Applies replacements sequentially in the order given (longest first),
    with optional word boundary matching.
    """
    for old, new in replacements:
        if whole_words:
            pattern = fr'\b{re.escape(old)}\b'
            line = re.sub(pattern, new, line)
        else:
            line = line.replace(old, new)
    return line


def modify_subtitles_with_vocabular_text_only(subtitle_path, vocabular_path, output_path):
    replacements = parse_vocabular_file(vocabular_path)

    with open(subtitle_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:

        for line in infile:
            line_strip = line.strip()

            # Skip numeric lines (e.g. 1, 2, 3...) or timecodes
            if line_strip.isdigit() or "-->" in line_strip:
                outfile.write(line)
                continue

            # Apply replacements only to actual text lines
            new_line = apply_replacements(line, replacements)
            outfile.write(new_line)