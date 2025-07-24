import re
from pathlib import Path

def check_vocabular(voice_dir):
    vocabular_pth = Path(voice_dir) / "vocabular.txt"
    if vocabular_pth.is_file():
        return vocabular_pth
    else:
        print(f"I need vocabulary file {vocabular_pth}")
        exit(1)
    print(f"Vocabulary file is {vocabular_pth}.")

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


def modify_subtitles_with_vocabular_wholefile_even_partishally(subtitle_path, vocabular_path, output_path):
    replacements = parse_vocabular_file(vocabular_path)

    with open(subtitle_path, 'r', encoding='utf-8') as infile:
        text = infile.read()

    for old, new in replacements:
        text = text.replace(old, new)

    with open(output_path, 'w', encoding='utf-8') as outfile:
        outfile.write(text)

    return text

def modify_subtitles_with_vocabular_wholefile(subtitle_path, vocabular_path, output_path):
    """Apply replacements only to subtitle text lines.

    Replacements are performed on full words only. Timestamp and index lines
    remain untouched so that subtitle formatting is preserved.
    """

    replacements = parse_vocabular_file(vocabular_path)

    time_re = re.compile(r"\d{2}:\d{2}:\d{2}[,.]\d{3} --> \d{2}:\d{2}:\d{2}[,.]\d{3}")

    def apply(text: str) -> str:
        for old, new in replacements:
            pattern = rf"(?<!\w){re.escape(old)}(?!\w)"
            text = re.sub(pattern, new, text)
        return text

    with open(subtitle_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            stripped = line.strip()
            if stripped.isdigit() or time_re.match(stripped) or stripped == "":
                outfile.write(line)
            else:
                outfile.write(apply(line))

    return output_path

def apply_replacements(line, replacements):
    """
    Applies each replacement (old->new) in order to a single line.
    Because we sorted by length in parse_vocabular_file,
    longer strings get replaced first.
    """
    for old, new in replacements:
        pattern = rf"(?<!\w){re.escape(old)}(?!\w)"
        line = re.sub(pattern, new, line)
    return line

def modify_subtitles_with_vocabular(subtitle_path, vocabular_path, output_path):
    """
    Reads `subtitle_path` line-by-line, applies the replacements
    from `vocabular_path`, and writes to `output_path`.
    """
    # Get the replacements
    replacements = parse_vocabular_file(vocabular_path)

    time_re = re.compile(r"\d{2}:\d{2}:\d{2}[,.]\d{3} --> \d{2}:\d{2}:\d{2}[,.]\d{3}")

    with open(subtitle_path, 'r', encoding='utf-8') as infile, \
         open(output_path, 'w', encoding='utf-8') as outfile:
        for line in infile:
            stripped = line.strip()
            if stripped.isdigit() or time_re.match(stripped) or stripped == "":
                outfile.write(line)
            else:
                new_line = apply_replacements(line, replacements)
                outfile.write(new_line)

