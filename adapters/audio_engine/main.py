import os
from collections import deque
import time
from core.engine import CoreEngine
from utils.threads import CustomThread, data_ready
from effects.allpassrverb import AllpassReverb, MultiAllpassReverb, AllpassReverbUnit
from effects.reverb import ReverbEffect
#from effects.fdn_v2 import ReverbFilter


class CorePlayer:

    def __init__(self):
        self.engine = CoreEngine(buffer_size=4096*2, sample_rate=44100)
        self.playlist = deque()
        self.play_index = -1
        self.load_songs()
        #self.engine.add_effect(ReverbEffect(sr=self.engine.sample_rate, pre_delay=2))
        #self.engine.add_effect(AllpassReverbUnit(sample_rate=self.engine.sample_rate, delay_ms=[2000, 1200, 3000]))
        self.engine.add_effect(AllpassReverb(sample_rate=self.engine.sample_rate, feedback=.2, decay=.85, delay_ms=60, wet=.4, mix=0.82, er_gain=.25, room=.8, damp=.4))
        #self.engine.add_effect(ReverbFilter(sr=self.engine.sample_rate, room_scale=70))

    def play_next(self, channel=0):
        """
        :return:
        """
        self.play_index += 1
        if self.play_index >= len(self.playlist):
            self.play_index = 0
        next_song = self.playlist[self.play_index]
        self.engine.load_file(next_song, channel)
        if self.engine.do_not_play:
            self.play_next()
        else:
            self.engine.play(0)
        if self.engine.mixer:
            print(self.engine.mixer.channels)

    def load_songs(self):
        """
        :return:
        """
        music_dir = os.path.expanduser("~") + "/Music"
        for file in os.listdir(music_dir):
            if file.endswith(".mp3"):
                self.playlist.append(os.path.join(music_dir, file))

    def check_end_event(self):
        """
        :return:
        """
        while True:
            if self.engine.is_playing():
                pos = self.engine.get_pos(0)
                #print(f"\rPos: {pos:.1f} / {self.engine.get_file_length(0)} ", end="", flush=True)
                if pos + 1 >= self.engine.get_file_length(0):
                    self.play_index += 1
                    if self.play_index >= len(self.playlist):
                        self.play_index = 0
                    self.engine.queue_file(self.playlist[self.play_index], 0)
            #else:
                #print("\rNot active ", end="", flush=True)
            time.sleep(.5)


player = CorePlayer()
end_thread = CustomThread(target=player.check_end_event, daemon=True)
player.play_next()
try:
    print(f"""
    Commands:\n
    n - next song
    v int - volume
    p - pause
    r - resume
    q - stop
    """)
    time.sleep(1)
    end_thread.start()
    while True:
        cmd = input(">: ")
        if cmd == "n":
            player.play_next()
        elif "v" in cmd:
            c, v = cmd.split(" ")
            player.engine.set_volume(float(v))
        elif cmd == "q":
            end_thread.stop()
            player.engine.stop()
            break
        elif cmd == "p":
            player.engine.pause(0)
        elif cmd == "r":
            player.engine.resume(0)
        elif "i" in cmd:
            _, idx = cmd.split()
            player.play_index = int(idx) - 1
            player.play_next()

except KeyboardInterrupt:
    end_thread.stop()
    player.engine.stop()


                        