import csv
import re
from datetime import datetime, timedelta
import pandas as pd
import srt
from pathlib import Path
from . import tts_audio

def format_timedelta(td: timedelta) -> str:
    """
    Convert a timedelta to an SRT‐style timestamp 'HH:MM:SS,mmm'.
    """
    total_ms = int(td.total_seconds() * 1000)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    hours = total_s // 3600
    minutes = (total_s % 3600) // 60
    seconds = total_s % 60
    return f"{hours:02}:{minutes:02}:{seconds:02},{ms:03}"




def srt_to_csv(srt_file, csv_file):
    def fallback_parse_srt(srt_text):
        """Minimal fallback parser if srt.parse() fails."""
        lines = srt_text.replace('\ufeff', '').replace('\r\n', '\n').split('\n')
        entries = []
        subtitle_number = None
        start_time = None
        end_time = None
        subtitle_text = []

        for line in lines:
            line = line.strip()
            if line.isdigit():
                subtitle_number = int(line)
            elif re.match(r'\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}', line):
                times = line.split(' --> ')
                start_time = times[0]
                end_time = times[1]
            elif line == "":
                if subtitle_number and start_time and end_time and subtitle_text:
                    text = ' '.join(subtitle_text)
                    start_dt = datetime.strptime(start_time, '%H:%M:%S,%f')
                    end_dt = datetime.strptime(end_time, '%H:%M:%S,%f')
                    entries.append(srt.Subtitle(index=subtitle_number, start=start_dt - datetime(1900, 1, 1),
                                                end=end_dt - datetime(1900, 1, 1), content=text))
                subtitle_number = None
                start_time = None
                end_time = None
                subtitle_text = []
            else:
                subtitle_text.append(line)

        # Final subtitle block
        if subtitle_number and start_time and end_time and subtitle_text:
            text = ' '.join(subtitle_text)
            start_dt = datetime.strptime(start_time, '%H:%M:%S,%f')
            end_dt = datetime.strptime(end_time, '%H:%M:%S,%f')
            entries.append(srt.Subtitle(index=subtitle_number, start=start_dt - datetime(1900, 1, 1),
                                        end=end_dt - datetime(1900, 1, 1), content=text))
        return entries

    # Read the file
    with open(srt_file, 'r', encoding='utf-8') as f:
        srt_text = f.read()

    # Try to parse with srt module
    try:
        subtitles = list(srt.parse(srt_text))
    except Exception as e:
        print(f"[Warning] Failed to parse with `srt` module: {e}")
        subtitles = fallback_parse_srt(srt_text)

    # Write CSV
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, quoting=csv.QUOTE_ALL)
        writer.writerow(['Number', 'Start Time', 'End Time', 'Duration', 'Symbol Duration', 'Text'])

        for sub in subtitles:
            start_str = format_timedelta(sub.start)
            end_str = format_timedelta(sub.end)
            duration = (sub.end - sub.start).total_seconds()
            text = sub.content.replace('\n', ' ').strip()
            symbol_duration = duration / len(text) if len(text) > 0 else 0

            writer.writerow([sub.index, start_str, end_str, duration, symbol_duration, text])
            print("\t".join(map(str, [sub.index, start_str, end_str, duration, symbol_duration, text])))



def add_speaker_columns(input_csv, output_csv, speakers=[]):
    with open(input_csv, 'r', encoding='utf-8') as input_file, open(output_csv, 'w', newline='',
                                                                     encoding='utf-8') as output_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames[:-1] + ['Speaker', 'Text']
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()

        for row in reader:
            text = row['Text']
            # Extract the first occurrence of [ ... ]
            match = re.search(r"\[(.*?)\]: ", text)
            first_bracket_content =  match.group(1) if match else None
            # Remove only the first occurrence
            cleaned_text = re.sub(r"\[.*?\]: ", "", text, count=1).strip()
            if first_bracket_content:
                row["Speaker"] = first_bracket_content
                row["Text"] = cleaned_text
            else:
                row["Speaker"] = ""
            writer.writerow(row)
            print("\t".join(map(str, row.values())))

def find_closest_from_floor_value_index(value, array):
    """
    Find the closest floor value (largest value ≤ input value) and its index in a sorted array.
    
    :param value: The target value to compare against.
    :param array: A list of numbers (assumed to be sorted in ascending order).
    :return: A tuple (floor_value, index) where:
             - floor_value is the closest value ≤ target value.
             - index is the position of floor_value in the array.
    """
    max_value, index = array[0], 0  # Initialize with the first element
    
    for i, arr in enumerate(array):
        if arr < value:
            max_value, index = arr, i 
            break  # Stop when we find the first value greater than the target
        max_value, index = arr, i  # Update max_value and index
    
    return max_value, index


def add_speed_columns_with_speakers(output_csv_with_speakers, speakers, output_with_preview_speeds_csv):
    with open(output_csv_with_speakers, 'r', encoding='utf-8') as input_file, open(output_with_preview_speeds_csv, 'w', newline='', encoding='utf-8') as output_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames[:-2] + ['TTS Symbol Duration', 'TTS Speed Closest', 'Speaker', 'Text']
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()    

        for row in reader:
            symbol_duration = float(row['Symbol Duration'])
            speaker_name = row['Speaker']
            try:
                speaker = speakers[speaker_name]
            except KeyError:
                print(f"Speaker {speaker_name} not found in speakers")
                speaker_name = speakers["default_speaker_name"]
                speaker = speakers[speaker_name]
                print(f"Speaker not found in speakers, using default speaker {speaker_name}")
            closest_duration, index = find_closest_from_floor_value_index(symbol_duration, speaker['symbol_durations'])
            closet_speed = speaker['speeds'][index]
            row['TTS Symbol Duration'] = closest_duration
            row['TTS Speed Closest'] = closet_speed
            row['Speaker'] = speaker_name
            writer.writerow(row)
            print("\t".join(map(str, row.values())))

def get_speakers_from_folder(voice_folder):
    speakers = {}
    default_speaker_name = ""
    for snd_file in Path(voice_folder).glob("*.wav"):
        snd_file_name = snd_file.stem
        if default_speaker_name == "":
            default_speaker_name = snd_file_name
        speakers[snd_file_name] = {}
        speakers[snd_file_name]["ref_file"] = snd_file
        text_file_path = snd_file.with_suffix('.txt')
        if text_file_path.is_file():
            with open(text_file_path) as text_file:
                ref_text = text_file.read().strip()
                speakers[snd_file_name]["ref_text"] = ref_text
        
        speeds_file = Path(voice_folder) / Path(snd_file).stem / "speeds.csv"
        if speeds_file.is_file():
            with open(speeds_file) as sf:
                csv_reader = csv.DictReader(sf)
                speeds = []
                durations = []
                symbol_durations = []
                for row in csv_reader:
                    speeds.append(float(row["speed"]))
                    durations.append(float(row["duration"]))
                    symbol_durations.append(float(row["symbol_duration"]))
                speakers[snd_file_name]["speeds"] = speeds
                speakers[snd_file_name]["durations"] = durations
                speakers[snd_file_name]["symbol_durations"] = symbol_durations

    speakers["default_speaker_name"] = default_speaker_name
    speakers["speakers_names"] = list(speakers.keys())
    return speakers

def check_texts(voice_dir):
    for sound_file in Path(voice_dir).glob("*.wav"):
        text_file_path = sound_file.with_suffix(".txt")
        if not text_file_path.is_file():
            print(f"I need text file {text_file_path}")
            exit(1)
    print("All text files are OK!")

def check_speeds_csv(voice_dir, language):
    for sound_file in Path(voice_dir).glob("*.wav"):
        text_file_path = sound_file.with_suffix(".txt")
        with open(text_file_path) as text_file:
            text = text_file.read().strip()

        speeds_file = Path(voice_dir) / Path(sound_file).stem / "speeds.csv"
        if not speeds_file.is_file():
            tts_audio.F5TTS(language=language).generate_speeds_csv(speeds_file, text, sound_file)
    print("All speeds.csv are OK!")

def take_first(dct):
    return next(iter(dct.items()))

def csv2excel(csv_file, excel_file, 
                delimiter=';', 
                sort_columns=["similarity"], ascending=True, 
                drop_rows_with=({"gen_error":["0"]},), 
                drop_columns=["Duration","Symbol Duration","TTS Symbol Duration","TTS Speed Closest","Speaker"]):
    df = pd.read_csv(csv_file, delimiter=delimiter)
    
    df.drop(drop_columns, axis=1, inplace=True)

    match drop_rows_with:
        case tuple():
            for drop_row in drop_rows_with:
                column_name, values = take_first(drop_row)
                df = df[~df[column_name].astype(str).isin(values)]                
        case dict():
            column_name, values = take_first(drop_rows_with)
            df = df[~df[column_name].astype(str).isin(values)]
    
    df = df.sort_values(by=sort_columns, ascending=ascending)
    df.to_excel(excel_file, index=False)
    

