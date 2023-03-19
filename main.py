import logging
import os
from http.client import IncompleteRead

import ffmpeg
import PySimpleGUI as sg
from pytube import YouTube, StreamQuery, Stream
from retry import retry


logging.basicConfig(format='%(asctime)s | %(message)s')
logger = logging.getLogger()
logger.setLevel('DEBUG')

DEFAULT_VIDEO_DIR = os.getcwd()
sg.theme('DarkAmber')
layout = [
    [
        sg.Text('Video folder'),
        sg.InputText(DEFAULT_VIDEO_DIR, key='-FOLDER-'),
        sg.FolderBrowse('Change folder'),
    ],
    [sg.Text('URL'), sg.InputText(key='-INPUT-')],
    [
        sg.Radio('mp4', 1, key='-mp4-', default=True),
        sg.Radio('mp3', 1, key='-mp3-')
    ],
    [sg.Button('Download'), sg.Button('Exit')],
    [sg.Text('', key='UserInfo')],
]


class MiniDownloader:
    window: sg.Window
    video_dir: str

    def __init__(self) -> None:
        self.window = sg.Window('MiniDownloader', layout)
        self.window.set_icon(os.path.join(os.getcwd(), 'icon.ico'))
        self.video_dir = DEFAULT_VIDEO_DIR
        self.start()

    @staticmethod
    def convert_file(original_file: str, new_file: str) -> None:
        (
            ffmpeg
            .input(original_file)
            .output(new_file)
            .overwrite_output()
            .run(quiet=True)
        )

    def get_audio(self, streams: StreamQuery) -> Stream:
        sorted_audios: StreamQuery = (
            streams
            .filter(type='audio')
            .order_by('abr')
            [::-1]
        )
        audio: Stream = sorted_audios[0]
        logging.debug(f'Quality audio file: {audio.abr}kbps')
        audio.download(self.video_dir, max_retries=3)
        return audio

    def get_video(self, streams: StreamQuery) -> Stream:
        sorted_videos: StreamQuery = (
            streams
            .filter(type='video')
            .order_by('resolution')
            [::-1]
        )
        video: Stream = sorted_videos[0]
        logging.debug(f'Quality video file: {video.resolution}')
        video.download(self.video_dir, max_retries=3)
        return video

    def save_file(self, stream: Stream, filetype: str) -> str:
        logging.debug(f'Transform from .{stream.subtype} to .mp3')
        original_name = os.path.join(
            self.video_dir,
            f'{stream.default_filename}',
            )
        final_filename = os.path.join(
            self.video_dir,
            f'{stream.default_filename.replace(stream.subtype, filetype)}',
            )
        self.convert_file(original_name, final_filename)
        os.remove(original_name)
        logging.debug(f'Saved as "{final_filename}"')
        return final_filename

    @retry(IncompleteRead, delay=2, tries=3)
    def get_file(self, url: str, is_mp4: bool) -> str | None:
        self.window['UserInfo'].update('Start downloading...')
        try:
            yt = YouTube(url)
            if is_mp4:
                streams = yt.streams.filter(
                    progressive=True,
                    )
            else:
                streams = yt.streams.filter(
                    adaptive=True,
                    )
        except Exception as exc:
            logger.critical(f'{exc.__class__}, {str(exc)}')
            self.window.write_event_value(
                '-FAILED-',
                f'{exc.__class__}! Check URL or try it later.'
                )
            raise Exception
        file_type = 'mp4' if is_mp4 else 'mp3'
        logging.debug(f'Collected {len(streams)} streams')
        stream = self.get_video(streams) if is_mp4 else self.get_audio(streams)

        if is_mp4 and stream.subtype == 'mp4':
            return os.path.join(self.video_dir, stream.default_filename)
        elif not is_mp4 and stream.subtype == 'mp3':
            return os.path.join(self.video_dir, stream.default_filename)

        self.window['UserInfo'].update(f'Transform to {file_type}...')
        path = self.save_file(stream, file_type)
        return path

    def _is_ready2download(self, values: dict) -> bool:
        is_type_selected: bool = any([values['-mp3-'], values['-mp4-']])
        is_input_empty: bool = values['-INPUT-'] == ''
        is_folder_exists: bool = os.path.exists(values['-FOLDER-'])
        return is_type_selected and not is_input_empty and is_folder_exists

    def _close(self) -> None:
        self.window.close()

    def start(self) -> None:
        while True:
            event, values = self.window.read()
            if event == sg.WIN_CLOSED or event == 'Exit':
                logging.info('Program close.')
                break
            if event == 'Download' and self._is_ready2download(values):
                self.video_dir = os.path.abspath(values['-FOLDER-'])
                logging.info(f'Download mp3 {values["-mp3-"]} | mp4 {values["-mp4-"]} | URL: {values["-INPUT-"]}')
                self.window.perform_long_operation(lambda: self.get_file(
                    values['-INPUT-'],
                    values['-mp4-'],
                    ),
                    '-DOWNLOADED-',
                    )
                self.window['Download'].update(disabled=True)
            if event == '-DOWNLOADED-':
                result = values[event]
                self.window['UserInfo'].update(f'Saved to {result}')
                self.window['Download'].update(disabled=False)
            if event == '-FAILED-':
                result = values[event]
                self.window['UserInfo'].update(result)
                self.window['Download'].update(disabled=False)
        self._close()


if __name__ == '__main__':
    MiniDownloader()
