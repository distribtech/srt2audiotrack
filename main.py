import argparse
from pathlib import Path
from subtitle_csv import get_speakers_from_folder, check_texts, check_speeds_csv
from vocabulary import check_vocabular
from pipeline import SubtitlePipeline


def main():
    # Initialize the argument parser
    parser = argparse.ArgumentParser(description="Script that processes a subtitle file")

    # Add a folder argument
    parser.add_argument('--subtitle', type=str, help="Path to the subtitle folder/file to be processed",
                        default=r"records")
    # Add default tts speeds file
    parser.add_argument('--speeds', type=str, help="Path to the speeds of tts",
                        default="speeds.csv")
    # Add delay to think that must be only one sentences, default value very very low
    parser.add_argument('--delay', type=float, help="Delay to think that must be only one sentences",
                        default=0.00001) 
    # Add voice
    parser.add_argument('--voice', type=str, help="Path to voice", default="basic_ref_en.wav")
    # Add text
    parser.add_argument('--text', type=str, help="Path to text for voice", default="some call me nature, others call me mother nature.")
    # Add video extension
    parser.add_argument('--videoext', type=str, help="Video extension of video files", default=".mp4")
    # Add subtitles extension
    parser.add_argument('--srtext', type=str, help="Subtitle extension of files", default=".srt")
    # Add out video ending
    parser.add_argument('--outfileending', type=str, help="Out video file ending", default="_out_mix.mp4")
    # Add vocabular
    parser.add_argument('--vocabular', type=str, help="Vocabular of transcriptions", default="vocabular.txt")
    # Add config
    parser.add_argument('--config', "-c", type=str, help="Config file", default="basic.toml")
    # Add acomponiment coeficient
    parser.add_argument('--acomponiment_coef', type=float, help="Acomponiment coeficient", default=0.3)
    # Add voice coeficient
    parser.add_argument('--voice_coef', type=float, help="Voice coeficient", default=0.2)
    # Add output folder
    parser.add_argument('--output_folder', type=str, help="Output folder", default="")

    # Parse the arguments
    args = parser.parse_args()

    # Extract the folder argument
    subtitle = args.subtitle
    speeds = args.speeds
    delay = args.delay
    voice = args.voice
    text = args.text
    videoext = args.videoext
    srtext = args.srtext
    outfileending = args.outfileending
    vocabular = args.vocabular
    acomponiment_coef = args.acomponiment_coef
    voice_coef = args.voice_coef
    output_folder = args.output_folder #It must be done in future. Now output file in the same directory than input file

    print(f"Processing folder: {subtitle}")

    voice_dir = Path(subtitle)/"VOICE"

    vocabular_pth = check_vocabular(voice_dir)
    check_texts(voice_dir)
    check_speeds_csv(voice_dir)

    speakers = get_speakers_from_folder(voice_dir)
    if not speakers:
        print("I need at least one speaker.")
        exit(1)
    default_speaker = speakers.get(speakers["default_speaker_name"])

    sbt_files = SubtitlePipeline.list_subtitle_files(
        subtitle, srtext, exclude_ext="_0_mod.srt"
    )
    # we need exclude srt modified files that we used for right pronunciation
    if Path(subtitle).is_file():
        sbt_files = [subtitle]
    for subtitle in sbt_files:
        subtitle = Path(subtitle)
        video_path = subtitle.with_suffix(videoext)
        ready_video_file_name = subtitle.stem + "_out_mix.mp4"
        ready_video_path = video_path.parent / ready_video_file_name
        if video_path.is_file() and not ready_video_path.is_file():
            pipeline = SubtitlePipeline(
                subtitle,
                vocabular_pth,
                speakers,
                default_speaker,
                acomponiment_coef,
                voice_coef,
                output_folder,
            )
            pipeline.run(video_path)



if __name__ == "__main__":
    main()


