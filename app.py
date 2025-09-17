import customtkinter as ctk
import tkinter as tk
from customtkinter import filedialog
import random
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write, read
import threading
import time
import matplotlib.pyplot as plt
from PIL import Image, ImageTk
import os
import json
import queue

from core import Clip
from components import TrackFrame, TransportFrame, WaveformCanvas, MixerFrame, MixerChannelStrip, AccordionCategory
from views import ContentFrame, ArrangementFrame
from settings import AudioSettingsWindow

SAMPLE_RATE = 44100; CHANNELS = 1

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DAW Pernambucana")
        self.geometry("1600x900") # Um bom tamanho inicial
        
        self.configure(fg_color="#242424")
        self._create_menubar()
        
        # --- Configuração do Grid Principal CORRETA ---
        self.grid_rowconfigure(0, weight=1) # A linha principal (0) ocupa todo o espaço vertical
        self.grid_columnconfigure(0, weight=1, minsize=250) # Browser
        self.grid_columnconfigure(1, weight=0) # Divisória Vertical
        self.grid_columnconfigure(2, weight=5) # Área Principal (5x maior que o browser)

        # --- Variáveis de Estado ---
        self.tracks, self.track_count, self.output_filename_count = [], 0, 1; self.active_track = None 
        self.is_recording, self.recording_frames, self.recording_thread = False, [], None
        self.is_playing, self.playback_thread, self.metronome_thread = False, None, None
        self.bpm = ctk.IntVar(value=120); self.is_metronome_on = ctk.BooleanVar(value=True); self._generate_metronome_clicks()
        self.arrangement_data = []; self.arrangement_insert_beat = 0
        self.current_view = 'session'; self.playback_start_time = 0; self.playhead_position_pixels = 0
        self.metering_queue = queue.Queue()

        # --- CRIAÇÃO DOS PAINÉIS PRINCIPAIS ---
        self.browser_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#2B2B2B")
        self.browser_frame.grid(row=0, column=0, sticky="nsew") # <-- COLA NORTE, SUL, LESTE, OESTE

        self.v_sash = ctk.CTkFrame(self, width=6, cursor="sb_h_double_arrow", fg_color="#1F1F1F")
        self.v_sash.grid(row=0, column=1, sticky="ns")
        self.v_sash.bind("<B1-Motion>", self._on_vertical_drag)

        self.right_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.right_panel.grid(row=0, column=2, sticky="nsew", padx=(0,10))
        # Configuração do grid interno do painel direito
        self.right_panel.grid_rowconfigure(0, weight=0)
        self.right_panel.grid_rowconfigure(1, weight=1) # <-- LINHA CRÍTICA! Faz a área de conteúdo esticar
        self.right_panel.grid_rowconfigure(2, weight=0)
        self.right_panel.grid_rowconfigure(3, weight=0, minsize=260)
        self.right_panel.grid_columnconfigure(0, weight=1)


        self.top_bar_frame = ctk.CTkFrame(self.right_panel, corner_radius=0, fg_color="#2B2B2B", height=60)
        self.top_bar_frame.grid(row=0, column=0, sticky="ew", pady=(10,0))
        self.top_bar_frame.pack_propagate(False)
        
        self.main_view_container = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.main_view_container.grid(row=1, column=0, sticky="nsew") # <-- COLA
        
        self.h_sash = ctk.CTkFrame(self.right_panel, height=6, cursor="sb_v_double_arrow", fg_color="#1F1F1F")
        self.h_sash.grid(row=2, column=0, sticky="ew", pady=5)
        self.h_sash.bind("<B1-Motion>", self._on_horizontal_drag)

        self.mixer_frame = MixerFrame(self.right_panel, self)
        self.mixer_frame.grid(row=3, column=0, sticky="nsew") # <-- COLA
        
        self.session_view = ContentFrame(self.main_view_container, self)
        self.session_view.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.arrangement_view = ArrangementFrame(self.main_view_container, self)
        self.arrangement_view.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.setup_ui_controls(); self.show_session_view(); self._update_meters()

    def _on_vertical_drag(self, event):
        new_width = self.browser_frame.winfo_x() + event.x
        if 200 < new_width < 500:
            self.grid_columnconfigure(0, minsize=new_width, weight=0)

    def _on_horizontal_drag(self, event):
        new_main_height = self.main_view_container.winfo_y() + event.y
        if 100 < new_main_height < self.right_panel.winfo_height() - 250:
            self.right_panel.grid_rowconfigure(1, minsize=new_main_height, weight=0)

    def setup_ui_controls(self):
        self.add_track_button = ctk.CTkButton(self.browser_frame, text="Adicionar Trilha", command=self.add_track, corner_radius=8, fg_color="#555555", hover_color="#666666")
        self.add_track_button.pack(padx=20, pady=20, side="bottom", fill="x")
        
        self.setup_browser()
        
        transport_frame = TransportFrame(self.top_bar_frame, self)
        transport_frame.pack(side="left", padx=10, pady=10)
        
        view_controls = ctk.CTkFrame(self.top_bar_frame, fg_color="transparent")
        view_controls.pack(side="right", padx=10, pady=10)
        self.session_button = ctk.CTkButton(view_controls, text="Sessão", width=80, command=self.show_session_view, corner_radius=6)
        self.session_button.pack(side="left")
        self.arrangement_button = ctk.CTkButton(view_controls, text="Arranjo", width=80, command=self.show_arrangement_view, corner_radius=6)
        self.arrangement_button.pack(side="left", padx=5)

    def setup_browser(self):
        effects_category = AccordionCategory(self.browser_frame, title="Efeitos Nativos")
        effects_category.pack(fill="x", padx=10, pady=(10,5))
        
        delay_button = ctk.CTkButton(effects_category.content_frame, text="Delay", fg_color="#444444",
                                     command=lambda: self.apply_delay_to_track(self.active_track))
        delay_button.pack(padx=10, pady=2, anchor="w", fill="x")

        samples_category = AccordionCategory(self.browser_frame, title="Samples")
        samples_category.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(samples_category.content_frame, text="(Nenhum sample ainda)").pack(padx=10, pady=2, anchor="w")

        plugins_category = AccordionCategory(self.browser_frame, title="Plugins VST")
        plugins_category.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(plugins_category.content_frame, text="(Suporte não implementado)").pack(padx=10, pady=2, anchor="w")

    def _create_menubar(self):
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0); file_menu.add_command(label="Salvar Projeto", command=self.save_project); file_menu.add_command(label="Carregar Projeto", command=self.load_project); file_menu.add_separator(); file_menu.add_command(label="Sair", command=self.quit); menubar.add_cascade(label="Arquivo", menu=file_menu)
        settings_menu = tk.Menu(menubar, tearoff=0); settings_menu.add_command(label="Áudio...", command=self.open_audio_settings); menubar.add_cascade(label="Configurações", menu=settings_menu)
        self.config(menu=menubar)
        
    # ... (O resto de todas as funções da classe App, como play, record, save, etc., continuam exatamente iguais)
    def open_audio_settings(self):
        if not (hasattr(self, 'audio_settings_window') and self.audio_settings_window.winfo_exists()): self.audio_settings_window = AudioSettingsWindow(self)
        self.audio_settings_window.focus()
    def show_session_view(self): self.current_view = 'session'; self.session_view.tkraise()
    def show_arrangement_view(self): self.current_view = 'arrangement'; self.arrangement_view.tkraise(); self.arrangement_view.redraw()
    def set_active_track(self, track_to_activate):
        for track in self.tracks: track.set_normal_appearance()
        if track_to_activate in self.tracks:
            self.active_track = track_to_activate; self.active_track.set_selected_appearance()
    def add_track(self):
        track_name = f"Trilha {self.track_count + 1}"; new_track = self.session_view.add_new_track(track_name, self.track_count)
        self.tracks.append(new_track); self.mixer_frame.add_channel_strip(new_track); self.set_active_track(new_track); self.track_count += 1
        self.arrangement_view.redraw()
    def toggle_solo_for_track(self, track_index):
        target_track = self.tracks[track_index]
        new_solo_state = not target_track.is_soloed.get()
        if new_solo_state:
            for i, track in enumerate(self.tracks): track.is_soloed.set(i == track_index)
        else: target_track.is_soloed.set(False)
    def _update_meters(self):
        while not self.metering_queue.empty():
            try:
                track_index, level = self.metering_queue.get_nowait()
                if track_index in self.mixer_frame.channel_strips: self.mixer_frame.channel_strips[track_index].set_meter_level(level)
            except queue.Empty: continue
        self.after(50, self._update_meters)
    def on_playback_finished(self):
        self.is_playing = False; self.playhead_position_pixels = 0
        for strip in self.mixer_frame.channel_strips.values(): strip.set_meter_level(0)
    def _record_worker(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32') as stream:
            while self.is_recording: frames, overflowed = stream.read(SAMPLE_RATE // 10); self.recording_frames.append(frames)
    def _playback_worker_with_metering(self, tracks_to_play):
        playhead_pos_samples = 0; active_streams = []; max_len = 0
        for track in tracks_to_play:
            clip = track.get_active_clip()
            if not clip: continue
            audio_data = clip.get_trimmed_data()
            if audio_data.size > 0:
                audio_data_float = (audio_data.astype(np.float32) / np.iinfo(np.int16).max) * track.volume.get()
                active_streams.append({"data": audio_data_float, "pos": 0, "track_index": track.track_index})
                if len(audio_data_float) > max_len: max_len = len(audio_data_float)
        block_size = 1024
        def callback(outdata, frames, time, status):
            nonlocal playhead_pos_samples
            if status: print(status)
            outdata.fill(0); chunk = np.zeros((frames, CHANNELS), dtype=np.float32)
            for stream in active_streams:
                remaining = len(stream["data"]) - stream["pos"]
                if remaining > 0:
                    samples_to_process = min(frames, remaining)
                    audio_chunk = stream["data"][stream["pos"] : stream["pos"] + samples_to_process]
                    chunk[:samples_to_process, 0] += audio_chunk
                    level = np.max(np.abs(audio_chunk)) if audio_chunk.size > 0 else 0.0
                    self.metering_queue.put((stream["track_index"], level)); stream["pos"] += samples_to_process
                else: self.metering_queue.put((stream["track_index"], 0.0))
            outdata[:] = chunk; playhead_pos_samples += frames
        try:
            with sd.OutputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=callback, blocksize=block_size, dtype='float32', finished_callback=self.on_playback_finished):
                while self.is_playing and playhead_pos_samples < max_len: time.sleep(0.1)
        except Exception as e: print(f"Erro no stream de áudio: {e}")
        finally: self.on_playback_finished()
    def _play_arrangement_worker(self, final_mix):
        try: sd.play(final_mix, SAMPLE_RATE); sd.wait()
        finally: self.is_playing = False
    def _metronome_worker(self):
        beat_count = 0
        while self.is_playing or self.is_recording:
            try:
                current_bpm = self.bpm.get();
                if current_bpm <= 0: time.sleep(0.1); continue
                if beat_count % 4 == 0: sd.play(self.click_strong, SAMPLE_RATE)
                else: sd.play(self.click_weak, SAMPLE_RATE)
                beat_count += 1; interval = 60.0 / current_bpm; time.sleep(interval)
            except: break
    def _update_playhead(self):
        if not self.is_playing or self.current_view != 'arrangement': return
        elapsed_time = time.time() - self.playback_start_time; beats_per_second = self.bpm.get() / 60.0
        pixels_per_second = beats_per_second * self.arrangement_view.pixels_per_beat
        self.playhead_position_pixels = elapsed_time * pixels_per_second
        self.arrangement_view.move_playhead(self.playhead_position_pixels); self.after(30, self._update_playhead)
    def _generate_metronome_clicks(self): t_strong = np.linspace(0., 0.05, int(SAMPLE_RATE * 0.05), endpoint=False); self.click_strong = 0.5 * np.sin(2. * np.pi * 1200 * t_strong); t_weak = np.linspace(0., 0.05, int(SAMPLE_RATE * 0.05), endpoint=False); self.click_weak = 0.5 * np.sin(2. * np.pi * 880 * t_weak)
    def _generate_waveform_image(self, wav_path, image_path):
        try: samplerate, data = read(wav_path); fig, ax = plt.subplots(figsize=(8, 1.5)); ax.plot(data, color='cyan'); ax.axis('off'); fig.patch.set_facecolor('#343638'); plt.savefig(image_path, bbox_inches='tight', pad_inches=0, dpi=100); plt.close(fig); return True
        except: return False
    def apply_delay_to_track(self, track):
        if not track: print("Nenhuma trilha selecionada para aplicar o efeito."); return
        clip = track.get_active_clip()
        if not clip or not os.path.exists(clip.audio_file_path): print(f"A trilha '{track.track_name}' não tem clip de áudio para aplicar efeito."); return
        samplerate, audio_data_int = read(clip.audio_file_path); original_dtype = audio_data_int.dtype
        dtype_info = np.iinfo(original_dtype); audio_data_float = audio_data_int.astype(np.float32) / dtype_info.max
        delay_seconds = 0.5; decay = 0.6; delay_samples = int(delay_seconds * samplerate)
        output_data_float = np.zeros(len(audio_data_float) + delay_samples, dtype=np.float32)
        output_data_float[:len(audio_data_float)] = audio_data_float; output_data_float[delay_samples:] += audio_data_float * decay
        peak = np.max(np.abs(output_data_float));
        if peak > 1.0: output_data_float /= peak
        final_audio_int16 = (output_data_float * dtype_info.max).astype(original_dtype)
        base, ext = os.path.splitext(clip.audio_file_path);
        if not base.endswith('_delay'): base = f"{base}_delay"
        new_audio_path = f"{base}{ext}"; write(new_audio_path, samplerate, final_audio_int16)
        new_clip = Clip(new_audio_path); track.clips[0] = new_clip
        if self._generate_waveform_image(new_clip.audio_file_path, new_clip.waveform_image_path): track.display_waveform(new_clip.waveform_image_path)
    def save_project(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".dawpe", filetypes=[("Projetos DAW Pernambucana", "*.dawpe")]);
        if not filepath: return
        project_data = {"bpm": self.bpm.get(), "tracks": [{"name": t.track_name, "volume": t.volume.get(), "is_muted": t.is_muted.get(), "is_soloed": t.is_soloed.get(), "clips": [c.to_dict() for c in t.clips]} for t in self.tracks], "arrangement": [{"clip": item["clip"].to_dict(), "track_index": item["track_index"], "start_beat": item["start_beat"]} for item in self.arrangement_data]}
        with open(filepath, 'w') as f: json.dump(project_data, f, indent=4)
        print(f"Projeto salvo em: {filepath}")
    def load_project(self):
        filepath = filedialog.askopenfilename(filetypes=[("Projetos DAW Pernambucana", "*.dawpe")]);
        if not filepath: return
        for strip in self.mixer_frame.channel_strips.values(): strip.destroy()
        for track in self.tracks: track.destroy()
        self.tracks, self.track_count, self.active_track = [], 0, None;
        with open(filepath, 'r') as f: project_data = json.load(f)
        self.bpm.set(project_data.get("bpm", 120))
        for i, track_data in enumerate(project_data.get("tracks", [])):
            new_track = self.session_view.add_new_track(track_data["name"], i)
            new_track.volume.set(track_data.get("volume", 0.8)); new_track.is_muted.set(track_data.get("is_muted", False)); new_track.is_soloed.set(track_data.get("is_soloed", False))
            for clip_data in track_data.get("clips", []):
                new_clip = Clip.from_dict(clip_data); new_track.add_clip(new_clip)
            self.tracks.append(new_track)
            self.mixer_frame.add_channel_strip(new_track)
        self.track_count = len(self.tracks)
        self.arrangement_data = []
        for item_data in project_data.get("arrangement", []):
            clip_obj = Clip.from_dict(item_data["clip"]); self.arrangement_data.append({"clip": clip_obj, "track_index": item_data["track_index"], "start_beat": item_data["start_beat"]})
        self.arrangement_view.redraw()
        print(f"Projeto '{filepath}' carregado.")
    def add_clip_to_arrangement(self, clip, track_index):
        arrangement_item = {"clip": clip, "track_index": track_index, "start_beat": self.arrangement_insert_beat}
        self.arrangement_data.append(arrangement_item);
        clip_duration_beats = (clip.duration_seconds * self.bpm.get()) / 60.0; self.arrangement_insert_beat += clip_duration_beats; self.arrangement_view.redraw()
    def play_music(self):
        if self.is_playing or self.is_recording: return
        if self.current_view == 'arrangement': self._play_arrangement()
        else: self._play_session()
    def stop_music(self):
        if self.is_recording:
            self.is_recording = False
            if self.recording_thread: self.recording_thread.join()
            audio_data_float = np.concatenate(self.recording_frames, axis=0); audio_data_int16 = (audio_data_float * np.iinfo(np.int16).max).astype(np.int16)
            wav_filename = f"gravacao_{self.output_filename_count}.wav"; self.output_filename_count += 1
            write(wav_filename, SAMPLE_RATE, audio_data_int16)
            if self.active_track:
                new_clip = Clip(wav_filename)
                if self._generate_waveform_image(new_clip.audio_file_path, new_clip.waveform_image_path): self.active_track.add_clip(new_clip)
        elif self.is_playing:
            self.is_playing = False; sd.stop()
            self.playhead_position_pixels = 0
            if hasattr(self, 'arrangement_view'): self.arrangement_view.move_playhead(0)
    def record_audio(self):
        if self.current_view != 'session': print("Mude para a Visão de Sessão para poder gravar."); return
        if self.is_recording or self.is_playing: return
        if not self.active_track: print("Nenhuma trilha selecionada!"); return
        if self.is_metronome_on.get(): self.metronome_thread = threading.Thread(target=self._metronome_worker); self.metronome_thread.start()
        self.is_recording = True; self.recording_frames = []; self.recording_thread = threading.Thread(target=self._record_worker); self.recording_thread.start()
    def _play_session(self):
        tracks_to_play = []; has_solo = any(t.is_soloed.get() for t in self.tracks)
        for track in self.tracks:
            clip = track.get_active_clip()
            if not clip: continue
            if has_solo:
                if track.is_soloed.get(): tracks_to_play.append(track)
            elif not track.is_muted.get(): tracks_to_play.append(track)
        if not tracks_to_play: return
        self.is_playing = True
        self.playback_thread = threading.Thread(target=self._playback_worker_with_metering, args=(tracks_to_play,)); self.playback_thread.start()
    def _play_arrangement(self):
        if not self.arrangement_data: print("Arranjo está vazio."); return
        bpm = self.bpm.get(); samples_per_beat = int(SAMPLE_RATE * 60.0 / bpm)
        total_duration_beats = 0
        for item in self.arrangement_data:
            clip = item["clip"]; trimmed_duration_seconds = clip.duration_seconds * (clip.trim_end_ratio - clip.trim_start_ratio)
            clip_duration_beats = (trimmed_duration_seconds * bpm) / 60.0; end_beat = item["start_beat"] + clip_duration_beats
            if end_beat > total_duration_beats: total_duration_beats = end_beat
        total_samples = int(total_duration_beats * samples_per_beat)
        if total_samples == 0: return
        mixer_buffer = np.zeros(total_samples, dtype=np.float32)
        for item in self.arrangement_data:
            clip, track_index, start_beat = item["clip"], item["track_index"], item["start_beat"]
            if track_index >= len(self.tracks): continue
            track = self.tracks[track_index]; audio_data = clip.get_trimmed_data()
            if audio_data.size == 0: continue
            audio_data_float = (audio_data.astype(np.float32) / np.iinfo(np.int16).max) * track.volume.get()
            start_sample = int(start_beat * samples_per_beat); end_sample = start_sample + len(audio_data_float)
            if end_sample > len(mixer_buffer): end_sample = len(mixer_buffer); audio_data_float = audio_data_float[:end_sample - start_sample]
            mixer_buffer[start_sample:end_sample] += audio_data_float
        peak = np.max(np.abs(mixer_buffer));
        if peak > 1.0: mixer_buffer /= peak
        final_audio_int16 = (mixer_buffer * np.iinfo(np.int16).max).astype(np.int16)
        self.is_playing = True
        if self.is_metronome_on.get(): self.metronome_thread = threading.Thread(target=self._metronome_worker); self.metronome_thread.start()
        self.playback_thread = threading.Thread(target=self._play_arrangement_worker, args=(final_audio_int16,)); self.playback_thread.start()
        self.playback_start_time = time.time(); self.arrangement_view.move_playhead(0); self._update_playhead()