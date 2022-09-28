import os
import yaml
from typing import List
from argparse import ArgumentParser
from allosaurus.app import read_recognizer
from PIL import Image
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip


class Frames:
    def __init__(self, config_data: dict, folder: str):
        self.folder = folder
        self.data = config_data
        self.image_cache = {}

    def get_image_filename(self, phoneme: str) -> str:
        for image_data in self.data["images"]:
            if phoneme in image_data["symbols"]:
                return self.folder + os.path.sep + image_data["image"]
        return None

    def get_image(self, phoneme: str) -> Image.Image:
        filename = self.get_image_filename(phoneme)
        if filename is None:
            return None

        if filename in self.image_cache:
            return self.image_cache[filename]
        else:
            image = Image.open(filename)
            self.image_cache[filename] = image
            return image

    def get_symbols(self):
        for image_data in self.data["images"]:
            for symbol in image_data["symbols"]:
                yield symbol

    def has_phoneme_image(self, phoneme: str):
        for image_data in self.data["images"]:
            if phoneme in image_data["symbols"]:
                return True
        return False


class Phoneme:
    start_time: float
    duration: float
    phoneme: str

    def __init__(self, start_time: float, duration: float, phoneme: str):
        self.start_time = start_time
        self.duration = duration
        self.phoneme = phoneme

    def __str__(self):
        return f"Phoneme({self.start_time}, {self.duration}, {self.phoneme})"


class LSG:
    def __init__(
        self,
        config_file: str,
        silence_duration_threshold: float = 0.25,
        silence_duration: float = 0.05,
    ):
        self.config_file = config_file
        self.config_folder = os.path.dirname(config_file)
        self.config_data = yaml.load(
            open(config_file, "r", encoding='utf8'), Loader=yaml.FullLoader
        )
        self.frames = Frames(self.config_data, self.config_folder)
        self.silence_duration_threshold = silence_duration_threshold
        self.silence_duration = silence_duration

    def run(self, file_audio: str, output: str):
        phonemes = self.generate_phonemes(
            file_audio, self.silence_duration_threshold, self.silence_duration
        )
        clips = self.generate_clips(phonemes)
        self.create_video(clips, file_audio, output)

    def generate_phonemes(
        self,
        audio_file: str,
        silence_duration_threshold: int = 0.25,
        silence_duration: int = 0.05,
    ) -> list:
        model = read_recognizer()
        result = model.recognize(audio_file, timestamp=True)
        phonemes = []
        for str_phoneme in result.split("\n"):
            values = str_phoneme.split(" ")
            phonemes.append(
                Phoneme(float(values[0]), float(values[1]), values[2])
            )

        for i, phoneme in enumerate(phonemes):
            if i == len(phonemes) - 1:
                duration = phoneme.duration
            else:
                duration = phonemes[i + 1].start_time - phoneme.start_time
            phoneme.duration = duration
            if (
                duration > silence_duration_threshold
                and phonemes[i - 1].phoneme != "-"
            ):
                phoneme.duration -= silence_duration
                phonemes.insert(
                    i + 1,
                    Phoneme(
                        phoneme.start_time + phoneme.duration,
                        silence_duration,
                        "-",
                    ),
                )

        # Add silence to end.
        phonemes.append(
            Phoneme(phonemes[-1].start_time + phonemes[-1].duration, 0.1, "-")
        )

        for phoneme in phonemes:
            print(phoneme)

        phonemes = self.replace_phonemes_with_available(phonemes)
        return phonemes

    def replace_phonemes_with_available(self, phonemes: List[Phoneme]):
        available_symbols = list(self.frames.get_symbols())
        last_available_phoneme = available_symbols[0]
        for phoneme in phonemes:
            if phoneme.phoneme in available_symbols:
                last_available_phoneme = phoneme.phoneme
            else:
                phoneme.phoneme = last_available_phoneme
        return phonemes

    def add_phoneme_with_duration_to_video(self, clips, phoneme, duration):
        clip = ImageClip(
            self.frames.get_image_filename(phoneme),
            transparent=True,
            duration=duration,
        )
        clips.append(clip)

    def generate_clips(self, phonemes) -> List[ImageClip]:
        clips = []
        duration = 0.0
        for i, phoneme in enumerate(phonemes):
            if i == len(phonemes) - 1:
                duration = phoneme.duration
            else:
                duration = phonemes[i + 1].start_time - phoneme.start_time
            if self.frames.has_phoneme_image(phoneme.phoneme):
                self.add_phoneme_with_duration_to_video(
                    clips, phoneme.phoneme, duration
                )
            else:
                # No initial image
                if i == 0:
                    self.add_phoneme_with_duration_to_video(
                        clips, "-", duration
                    )
                else:
                    self.add_phoneme_with_duration_to_video(
                        clips, phonemes[i].phoneme, duration
                    )
        return clips

    def create_video(self, clips: List[ImageClip], file_audio: str, output: str):
        video = concatenate_videoclips(clips, method="compose")
        audio = AudioFileClip(file_audio)
        video.audio = audio
        video.write_videofile(output, fps=24)


def main():
    default_config = os.path.dirname(__file__)
    default_config = os.path.join(default_config, "config", "config.yml")

    parser = ArgumentParser()
    parser.add_argument(
        "--audio", help="Path to audio file", type=str, required=True
    )
    parser.add_argument(
        "--config",
        help="YAML describing which images to use for each phoneme",
        type=str,
        default=default_config
    )
    parser.add_argument(
        "--output", help="Path to output file", type=str,
        default="output.mp4"
    )
    parser.add_argument(
        "--silence_duration_threshold",
        help="Minimum duration of a phoneme to add silence after it",
        type=str,
        required=False,
        default=0.25,
    )
    parser.add_argument(
        "--silence_duration",
        help="Duration of the silence phoneme after threshold is reached.",
        type=str,
        required=False,
        default=0.05,
    )
    args = parser.parse_args()

    if args.audio is None:
        parser.print_help()
        return

    lsg = LSG(
        args.config, args.silence_duration_threshold, args.silence_duration
    )
    lsg.run(args.audio, args.output)

    print("Audio file: ", args.audio)
    print("Frames directory: ", args.config)


if __name__ == "__main__":
    main()
