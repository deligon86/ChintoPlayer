import threading
import numpy as np
from adapters.audio_engine.core.channel import CoreAudioChannel


class CoreMixer:

    def __init__(self, sample_rate=44100, buffer_size=512, end_event_reached=None):
        self.buffer_size = buffer_size
        self.sample_rate = sample_rate
        self.channels = []
        self.lock = threading.Lock()
        self.end_event = 1  # 0 playing, 1 stopped, 2 paused
        self.emit_end_event = end_event_reached

    def add_channel(self, channel):
        with self.lock:
            if channel not in self.channels:
                self.channels.append(channel)
                # Set the callback for playback end
                channel.on_playback_end = self.handle_playback_end

    def add_effects(self, effects:list, channel:int=0):
        with self.lock:
            if self.channels:
                try:
                    source = self.channels[channel]
                    source.add_effects(effects)
                except Exception as e:
                    print(f"[Mixer] Add effects to channel: {channel} failed, error: {e}")
    def clear_channels(self):
        """
        Remove all channels
        :return:
        """
        with self.lock:
            for channel in self.channels:
                channel.close()
            self.channels.clear()

    def get_next_buffer(self):
        mix_buffer = np.zeros((self.buffer_size, 2), dtype=np.float32)
        with self.lock:
            for channel in self.channels:
                if channel.playing:
                    data = channel.get_next_buffer()
                    mix_buffer += data

        return np.clip(mix_buffer, -1.0, 1.0)

    def get_active_channel(self):
        """
        Ger channels
        :return:
        """
        with self.lock:
            return [channel for channel in self.channels if channel.playing]

    def get_loaded_channels(self):
        """
        :return:
        """
        with self.lock:
            return [channel for channel in self.channels if channel.audio_file]

    def handle_playback_end(self, channel):
        channel.playing = False
        channel.position = 0
        print(f"[Mixer] Channel {self.channels.index(channel)} playback finished.")
        self.emit_end_event(channel, True)

    def is_playing(self, channel:CoreAudioChannel|int=None):
        with self.lock:
            if channel is None:
                if any([channel for channel in self.channels if channel.playing]):
                    return True
                else:
                    return False
            else:
                if isinstance(channel, int):
                    try:
                        source = self.channels[channel]
                        return source.playing
                    except:
                        return False

                elif isinstance(channel, CoreAudioChannel):
                    return channel.playing

                else:
                    return False
    
    def get_file_length(self, channel:CoreAudioChannel|int=None):
        """
        Args:
            channel (CoreAudioChannel | int, optional): _description_. Defaults to None.
        """
        if isinstance(channel, CoreAudioChannel):
            return channel.file_length
        else:
            if self.channels and 0 <= channel < len(self.channels):
                return self.channels[channel].file_length
            else:
                return 0.0

    def get_pos(self, channel: int = None) -> float:
        """_summary_

        Args:
            channel (_type_): _description_
        """
        if self.channels and 0 <= channel <= len(self.channels):
            return self.channels[channel].get_position()
        else:
            return 0.0

    def load_file_to_channel(self, channel:CoreAudioChannel|int, file):
        """
        :param channel: CorAudioChannel or channel index
        :param file:
        :return:
        """
        if isinstance(channel, CoreAudioChannel):
            if channel not in self.channels:
                self.channels.append(channel)
            channel.load_file(file)
            return channel.do_not_play
        elif isinstance(channel, int):
            try:
                source = self.channels[channel]
                source.load_file(file)
                return source.do_not_play
            except Exception as e:
                print("[Mixer] Could not load channel: {} error: {}".format(channel, e))
                return True
        else:
            return True

    def pause(self, channel:int=None):
        """
        Pause a channel or all if channel is set to None
        :return:
        """
        with self.lock:
            if channel:
                try:
                    self.channels[channel].pause()
                except Exception as e:
                    print(f"[Mixer] Cannot pause channel: {channel} Error: {e}")
            else:
                for channel in self.channels:
                    channel.pause()
                # print("[+] All channels paused")

    def play_channel(self, channel_index):
        """
        :param channel_index:
        :return:
        """
        try:
            self.channels[channel_index].playing = True
            return True
        except Exception as e:
            print("[Mixer] Cannot play channel: {} Error: ".format(channel_index, e))
            return False

    def queue_to_channel(self, channel:CoreAudioChannel|int, file):
        """
        :param channel:
        :param file: str|StrPath
        :return:
        """
        if isinstance(channel, int):
            if 0 <= channel < len(self.channels):
                channel = self.channels[channel]
                channel.queue_file(file)
        elif isinstance(channel, CoreAudioChannel):
            channel.queue_file(file)

    def remove_channel(self, channel:CoreAudioChannel|int):
        """
        Remove channel
        :param channel: CoreAudioChannel object or channel index
        :return:
        """
        with self.lock:
            if isinstance(channel, CoreAudioChannel):
                if channel in self.channels:
                    self.channels.remove(channel)
            elif isinstance(channel, int):
                if 0 <= channel < len(self.channels):
                    self.channels.pop(channel)

    def resume(self, channel:int=None):
        """
        Resume all playing channels
        :return:
        """
        with self.lock:
            if isinstance(channel, int):
                try:
                    self.channels[channel].resume()
                except Exception as e:
                    print("[Mixer] Cannot resume channel {} Error: {}".format(channel, e))
            else:
                for channel in self.channels:
                    channel.resume()
                print("[Mixer] All channels resumed")
    
    def set_volume(self, volume, channel:CoreAudioChannel|int=None):
        """
        Set volume
        :param volume:
        :param channel:
        :return:
        """
        with self.lock:
            if not channel:
                for channel in self.channels:
                    channel.set_volume(volume)
            else:
                if isinstance(channel, CoreAudioChannel):
                    channel.set_volume(volume)
                elif isinstance(channel, int):
                    try:
                        source = self.channels[channel]
                        source.set_volume(volume)
                    except IndexError:
                        print("[Mixer] Cannot set volume channel index does not exist")
                    except Exception as e:
                        print("[Mixer] Set volume error: ", e)

    def stop(self):
        for channel in self.channels:
            channel.stop()
