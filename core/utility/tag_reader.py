import os
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from core import logger


class TagReader:
    """Reads File Metadata"""
    title = ""
    path = ""
    artist = 'Unknown artist'
    album = 'Unknown album'
    year = 'Unknown year'
    genre = 'Unknown genre'
    track_no = '0'
    composer = 'Unknown'
    producer = 'Unknown'
    filetype = None
    file_length = 0
    file_length_formated = '00:00'
    raw_image_data = None
    tag_dict = {}

    def __init__(self, path=None, autoextract=False, verbose=False, logger_=None):

        self.verbosity = verbose
        self.tags = None
        self.logger = logger_ if logger_ else logger

        self.__path = path
        if path and autoextract:
            self.read_tags()

    @property
    def song_path(self):
        return self.__path

    @song_path.setter
    def song_path(self, value):
        self.__path = value
        # read tags
        self.read_tags()

    def read_tags(self, path=None):
        """
        Read tags from file and update attributes.
        """
        self.__path = path or self.__path
        try:
            self.tags = ID3(self.__path)
            self.logger.info('[Tag Reader] Valid for ID3 tagging')
            self.set_valid_tags()
        except Exception as error:
            self.logger.warning(f'[Tag Reader] Failed to load tags: {error}')
            self.set_non_id3_tags()

        self.__set_tag_dict()

        return self

    def set_valid_tags(self):
        tags_methods = [
            ('TIT2', self.__get_title),
            ('TPE1', self.__get_artist),
            ('TALB', self.__get_album),
            ('TCON', self.__get_genre),
            ('TDRC', self.__get_year),
            ('TRCK', self.__get_trackno),
            ('TCOM', self.__get_composer),
            ('TPRO', self.__get_producer)
        ]

        for tag, method in tags_methods:
            if tag in self.tags:
                method()
            else:
                if tag == "TIT2":
                    self.title = os.path.basename(self.__path)

        self.__get_audio_length()
        self.__get_audio_image_data()
        self._format_file_length()

    def set_non_id3_tags(self):
        self.title = os.path.basename(self.__path) if self.__path else self.title
        self.__get_audio_length()
        self._format_file_length()

    def __get_title(self):
        self.title = str(self.tags.get("TIT2", os.path.basename(self.__path)))

    def __get_artist(self):
        self.artist = str(self.tags.get('TPE1', self.artist))

    def __get_album(self):
        self.album = str(self.tags.get('TALB', self.album))

    def __get_genre(self):
        self.genre = str(self.tags.get('TCON', self.genre))

    def __get_year(self):
        self.year = str(self.tags.get('TDRC', self.year))

    def __get_trackno(self):
        self.track_no = str(self.tags.get('TRCK', self.track_no))

    def __get_composer(self):
        self.composer = str(self.tags.get('TCOM', self.composer))

    def __get_producer(self):
        self.producer = str(self.tags.get('TPRO', self.producer))

    def __get_audio_length(self, return_value=False):
        filetype = self.__get_filetype()
        if filetype == 'MP3':
            self.file_length = self.__get_length_mp3()
        elif filetype == 'MP4':
            self.file_length = self.__get_length_mp4()

        # Add other file formats as needed for now I will tag mp3/mp4
        if return_value:
            self._format_file_length()
            return self.file_length_formated
        else:
            self._format_file_length()
            return None

    def __get_length_mp3(self):
        try:
            mp3 = MP3(self.__path)
            return mp3.info.length
        except Exception as e:
            self.logger.warning(f'[MP3 ERROR] {e}')
            return 0

    def __get_length_mp4(self):
        try:
            mp4 = MP4(self.__path)
            return mp4.info.length
        except Exception as e:
            self.logger.warning(f'[MP4 ERROR] {e}')
            return 0

    def __get_audio_image_data(self):
        if 'APIC:' in self.tags:
            self.raw_image_data = self.tags['APIC:'].data

    def __get_filetype(self):
        if self.tags and 'TFLT' in self.tags:
            self.filetype = str(self.tags['TFLT'])
        else:
            ext = os.path.splitext(self.__path)[-1]
            self.filetype = ext[1:].upper()
        return self.filetype

    def __get_file_size(self):
        try:
            return os.path.getsize(self.__path) / (1024*1024)
        except:
            return 0

    def _format_file_length(self, value=None):
        if self.file_length > 1:
            minutes, seconds = divmod(int(self.file_length), 60)
            self.file_length_formated = f'{int(minutes):02d}:{int(seconds):02d}'
            return self.file_length_formated
        else:
            return "--:--"

    def __set_tag_dict(self):
        self.tag_dict = {
            "Artist": self.artist,
            "Title": self.title,
            "Album": self.album,
            "Genre": self.genre,
            "Composer": self.composer,
            "Producer": self.producer,
            "Track No:": self.track_no,
            "File size": self.__get_file_size(),
            "Duration": self.file_length_formated,
            "File Type": self.filetype,
            "Year": self.year
            }
