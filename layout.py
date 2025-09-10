import customtkinter as ctk
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

# --- CONFIGURAÇÃO INICIAL E CLASSES ---
ctk.set_appearance_mode("dark"); ctk.set_default_color_theme("blue")
SAMPLE_RATE = 44100; CHANNELS = 1
NORMAL_BG_COLORS = ["#2E4053", "#512E53", "#2E5345", "#532E2E"]
SELECTED_BG_COLOR = "#F1C40F"; MUTE_ON_COLOR = "#3498DB"; SOLO_ON_COLOR = "#F39C12"

class Clip:
    def __init__(self, audio_file_path):
        self.audio_file_path = audio_file_path
        self.waveform_image_path = audio_file_path.replace(".wav", ".png")
        self.trim_start_ratio = 0.0
        self.trim_end_ratio = 1.0
        
        try:
            samplerate, data = read(self.audio_file_path)
            self.duration_samples = len(data)
            self.duration_seconds = self.duration_samples / samplerate
        except FileNotFoundError:
            self.duration_samples = 0
            self.duration_seconds = 0
        
    def get_trimmed_data(self):
        if not os.path.exists(self.audio_file_path): return np.array([], dtype=np.int16)
        samplerate, data = read(self.audio_file_path)
        start_sample = int(len(data) * self.trim_start_ratio)
        end_sample = int(len(data) * self.trim_end_ratio)
        return data[start_sample:end_sample]
        
    def to_dict(self):
        return {
            "audio_file_path": self.audio_file_path,
            "waveform_image_path": self.waveform_image_path,
            "trim_start_ratio": self.trim_start_ratio,
            "trim_end_ratio": self.trim_end_ratio
        }

    @classmethod
    def from_dict(cls, data):
        clip = cls(data["audio_file_path"])
        clip.waveform_image_path = data["waveform_image_path"]
        clip.trim_start_ratio = data["trim_start_ratio"]
        clip.trim_end_ratio = data["trim_end_ratio"]
        return clip

class WaveformCanvas(ctk.CTkCanvas):
    def __init__(self, master, track_frame):
        super().__init__(master, bg="#343638", highlightthickness=0)
        self.track_frame = track_frame; self.image = None; self.photo_image = None
        self.start_handle_pos = 0; self.end_handle_pos = 0
        self.image_id, self.start_handle_id, self.end_handle_id, self.dark_overlay_start_id, self.dark_overlay_end_id = None, None, None, None, None
        self._drag_data = {"x": 0, "y": 0, "item_tag": None}
        self.tag_bind("handle", "<ButtonPress-1>", self.on_press_handle)
        self.tag_bind("handle", "<B1-Motion>", self.on_drag_handle)
        self.tag_bind("handle", "<Enter>", lambda e: self.config(cursor="sb_h_double_arrow"))
        self.tag_bind("handle", "<Leave>", lambda e: self.config(cursor=""))

    def display_waveform(self, image_path):
        try:
            width, height = self.winfo_width(), self.winfo_height()
            if width <= 1 or height <= 1: self.after(50, lambda: self.display_waveform(image_path)); return
            self.delete("all")
            self.image = Image.open(image_path).resize((width, height), Image.Resampling.LANCZOS); self.photo_image = ImageTk.PhotoImage(self.image); self.image_id = self.create_image(0, 0, image=self.photo_image, anchor="nw")
            self.dark_overlay_start_id = self.create_rectangle(0,0,0,0, fill="#000000", stipple="gray50", outline="")
            self.dark_overlay_end_id = self.create_rectangle(0,0,0,0, fill="#000000", stipple="gray50", outline="")
            self.start_handle_id = self.create_line(0,0,0,0, fill=SELECTED_BG_COLOR, width=3, tags=("handle", "start_handle"))
            self.end_handle_id = self.create_line(0,0,0,0, fill=SELECTED_BG_COLOR, width=3, tags=("handle", "end_handle"))
            active_clip = self.track_frame.get_active_clip()
            if active_clip:
                self.start_handle_pos = int(active_clip.trim_start_ratio * width)
                self.end_handle_pos = int(active_clip.trim_end_ratio * width)
            self.update_visuals()
        except Exception as e: print(f"Erro ao exibir a imagem: {e}")

    def update_visuals(self):
        height = self.winfo_height()
        self.coords(self.dark_overlay_start_id, 0, 0, self.start_handle_pos, height)
        self.coords(self.dark_overlay_end_id, self.end_handle_pos, 0, self.winfo_width(), height)
        self.coords(self.start_handle_id, self.start_handle_pos, 0, self.start_handle_pos, height)
        self.coords(self.end_handle_id, self.end_handle_pos, 0, self.end_handle_pos, height)

    def on_press_handle(self, event):
        tags = self.gettags(self.find_withtag("current")[0]); self._drag_data["item_tag"] = "start_handle" if "start_handle" in tags else "end_handle"; self._drag_data["x"] = event.x

    def on_drag_handle(self, event):
        if self._drag_data["item_tag"]:
            new_x = max(0, min(event.x, self.winfo_width()))
            if self._drag_data["item_tag"] == "start_handle" and new_x < self.end_handle_pos - 10: self.start_handle_pos = new_x
            elif self._drag_data["item_tag"] == "end_handle" and new_x > self.start_handle_pos + 10: self.end_handle_pos = new_x
            self.update_visuals(); self.update_trim_points()

    def update_trim_points(self):
        canvas_width = self.winfo_width()
        if canvas_width > 0: start_ratio = self.start_handle_pos / canvas_width; end_ratio = self.end_handle_pos / canvas_width; self.track_frame.set_trim_points(start_ratio, end_ratio)

class TrackFrame(ctk.CTkFrame):
    def __init__(self, master, track_name, app_instance, track_index):
        super().__init__(master, height=100, border_width=2, border_color="black")
        self.track_name = track_name; self.app = app_instance; self.track_index = track_index
        self.normal_bg_color = random.choice(NORMAL_BG_COLORS); self.configure(fg_color=self.normal_bg_color)
        self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=5)
        
        controls_frame = ctk.CTkFrame(self, fg_color="transparent"); controls_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        self.name_label = ctk.CTkLabel(controls_frame, text=self.track_name, font=("Arial", 12)); self.name_label.pack(anchor="w", pady=(0, 5))
        
        mute_solo_frame = ctk.CTkFrame(controls_frame, fg_color="transparent"); mute_solo_frame.pack(anchor="w", pady=5)
        self.is_muted = False; self.mute_button = ctk.CTkButton(mute_solo_frame, text="M", width=30, command=self.toggle_mute); self.mute_button.pack(side="left", padx=(0, 5))
        self.is_soloed = False; self.solo_button = ctk.CTkButton(mute_solo_frame, text="S", width=30, command=self.toggle_solo); self.solo_button.pack(side="left")
        
        self.copy_to_arr_button = ctk.CTkButton(controls_frame, text="-> Arranjo", width=100, command=self.copy_clip_to_arrangement)
        self.copy_to_arr_button.pack(anchor="w", pady=5)
        self.delay_button = ctk.CTkButton(controls_frame, text="Aplicar Delay", width=100, command=self.on_apply_delay_click); self.delay_button.pack(anchor="w", pady=5)
        
        self.volume = ctk.DoubleVar(value=0.8); self.volume_slider = ctk.CTkSlider(controls_frame, from_=0.0, to=1.0, variable=self.volume, number_of_steps=100); self.volume_slider.pack(anchor="w", pady=5, fill="x", expand=True)
        
        self.clips_area_canvas = WaveformCanvas(self, self); self.clips_area_canvas.grid(row=0, column=1, rowspan=2, padx=10, pady=10, sticky="nsew")
        
        self.clips = []
        
        self.bind("<Button-1>", self.select_track)
        for widget in self.winfo_children():
            widget.bind("<Button-1>", self.select_track)
            if hasattr(widget, 'winfo_children'):
                for child in widget.winfo_children(): child.bind("<Button-1>", self.select_track)

    def add_clip(self, clip):
        self.clips = [clip] 
        if os.path.exists(clip.waveform_image_path): self.display_waveform(clip.waveform_image_path)
    def get_active_clip(self): return self.clips[0] if self.clips else None
    def set_trim_points(self, start_ratio, end_ratio):
        clip = self.get_active_clip()
        if clip: clip.trim_start_ratio = start_ratio; clip.trim_end_ratio = end_ratio
    def copy_clip_to_arrangement(self):
        clip = self.get_active_clip()
        if clip: self.app.add_clip_to_arrangement(clip, self.track_index)
    def on_apply_delay_click(self, event=None): self.app.apply_delay_to_track(self); return "break"
    def toggle_mute(self): self.is_muted = not self.is_muted; new_color = MUTE_ON_COLOR if self.is_muted else ctk.ThemeManager.theme["CTkButton"]["fg_color"]; self.mute_button.configure(fg_color=new_color)
    def toggle_solo(self): self.is_soloed = not self.is_soloed; new_color = SOLO_ON_COLOR if self.is_soloed else ctk.ThemeManager.theme["CTkButton"]["fg_color"]; self.solo_button.configure(fg_color=new_color)
    def select_track(self, event=None):
        if event and event.widget in (self.mute_button, self.solo_button, self.delay_button, self.volume_slider, self.copy_to_arr_button): return "break"
        self.app.set_active_track(self)
    def set_selected_appearance(self): self.configure(border_color=SELECTED_BG_COLOR)
    def set_normal_appearance(self): self.configure(border_color="black")
    def display_waveform(self, image_path): self.clips_area_canvas.display_waveform(image_path)
    
class ContentFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, corner_radius=0); self.app = app_instance
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Trilhas"); self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
    def add_new_track(self, track_name, track_index):
        track = TrackFrame(self.scrollable_frame, track_name, self.app, track_index); track.pack(fill="x", expand=True, padx=5, pady=5); return track
        
class TransportFrame(ctk.CTkFrame):
    def __init__(self, master, play_command, stop_command, record_command):
        super().__init__(master, fg_color="transparent")
        self.play_button = ctk.CTkButton(self, text="▶ Play", command=play_command); self.play_button.pack(side="left", padx=5)
        self.stop_button = ctk.CTkButton(self, text="■ Stop", command=stop_command); self.stop_button.pack(side="left", padx=5)
        self.record_button = ctk.CTkButton(self, text="● Rec", command=record_command, fg_color="#C0392B", hover_color="#E74C3C"); self.record_button.pack(side="left", padx=5)

class ArrangementFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, corner_radius=0, fg_color="#2B2B2B")
        self.app = app_instance; self.track_height = 100
        self.grid_rowconfigure(0, weight=1); self.grid_columnconfigure(0, weight=1)
        self.grid_canvas = ctk.CTkCanvas(self, bg="#2B2B2B", highlightthickness=0)
        self.grid_canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.grid_canvas.yview); self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.grid_canvas.xview); self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.grid_canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        self.grid_canvas.bind("<Configure>", self.redraw); self.playhead_id = None; self.clip_visuals = {}
        self._drag_data = {"x": 0, "y": 0, "item_tags": None, "clip_object_item": None, "drag_type": None}
        self.grid_canvas.tag_bind("clip_body", "<ButtonPress-1>", self.on_clip_press)
        self.grid_canvas.tag_bind("clip_body", "<B1-Motion>", self.on_clip_drag)
        self.grid_canvas.tag_bind("clip_body", "<ButtonRelease-1>", self.on_clip_release)
        self.grid_canvas.tag_bind("clip_body", "<Enter>", lambda e: self.grid_canvas.config(cursor="hand2"))
        self.grid_canvas.tag_bind("clip_body", "<Leave>", lambda e: self.grid_canvas.config(cursor=""))
        self.grid_canvas.tag_bind("handle", "<ButtonPress-1>", self.on_clip_press)
        self.grid_canvas.tag_bind("handle", "<B1-Motion>", self.on_clip_drag)
        self.grid_canvas.tag_bind("handle", "<ButtonRelease-1>", self.on_clip_release)
        self.grid_canvas.tag_bind("handle", "<Enter>", lambda e: self.grid_canvas.config(cursor="sb_h_double_arrow"))
        self.grid_canvas.tag_bind("handle", "<Leave>", lambda e: self.grid_canvas.config(cursor=""))
    
    def redraw(self, event=None):
        self.grid_canvas.delete("all"); self.draw_grid(); self.draw_clips()
        if self.playhead_id: self.move_playhead(self.app.playhead_position_pixels)

    def draw_grid(self):
        canvas_width_virtual = 30000; canvas_height_virtual = max(self.app.track_count * self.track_height, self.winfo_height())
        bpm = self.app.bpm.get(); beats_per_bar = 4
        self.pixels_per_beat = 100.0; pixels_per_bar = self.pixels_per_beat * beats_per_bar
        total_bars = int(canvas_width_virtual / pixels_per_bar)
        for bar in range(total_bars):
            x = bar * pixels_per_bar
            self.grid_canvas.create_line(x, 0, x, canvas_height_virtual, fill="#555555", width=2)
            self.grid_canvas.create_text(x + 5, 10, text=str(bar + 1), anchor="nw", fill="white", font=("Arial", 10))
            for beat in range(1, beats_per_bar):
                x_beat = x + (beat * self.pixels_per_beat)
                self.grid_canvas.create_line(x_beat, 0, x_beat, canvas_height_virtual, fill="#444444", width=1)
        self.grid_canvas.config(scrollregion=(0, 0, canvas_width_virtual, canvas_height_virtual))

    def draw_clips(self):
        self.clip_visuals = {}
        for item in self.app.arrangement_data:
            clip, track_index, start_beat = item["clip"], item["track_index"], item["start_beat"]
            clip_total_duration_beats = (clip.duration_seconds * self.app.bpm.get()) / 60.0; clip_total_width_px = clip_total_duration_beats * self.pixels_per_beat
            trim_start_pixels = clip_total_width_px * clip.trim_start_ratio; trim_end_pixels = clip_total_width_px * clip.trim_end_ratio
            trimmed_width = trim_end_pixels - trim_start_pixels
            x, y = start_beat * self.pixels_per_beat, track_index * self.track_height; height = self.track_height
            item_tag = f"clip_{id(clip)}"
            body_id = self.grid_canvas.create_rectangle(x + trim_start_pixels, y, x + trim_end_pixels, y + height - 2, fill="#5DADE2", outline="black", width=2, tags=("clip_body", item_tag))
            img_id, text_id = None, None
            if os.path.exists(clip.waveform_image_path):
                try:
                    pil_img = Image.open(clip.waveform_image_path)
                    crop_x1 = int(pil_img.width * clip.trim_start_ratio); crop_x2 = int(pil_img.width * clip.trim_end_ratio)
                    if crop_x1 < crop_x2:
                        pil_img_cropped = pil_img.crop((crop_x1, 0, crop_x2, pil_img.height))
                        pil_img_resized = pil_img_cropped.resize((int(trimmed_width), int(height - 4)), Image.Resampling.LANCZOS)
                        tk_img = ImageTk.PhotoImage(pil_img_resized); self.clip_visuals[img_id] = tk_img
                        img_id = self.grid_canvas.create_image(x + trim_start_pixels + 2, y + 2, image=tk_img, anchor="nw", tags=("clip_body", item_tag))
                except: pass
            clip_name = os.path.basename(clip.audio_file_path)
            text_id = self.grid_canvas.create_text(x + trim_start_pixels + 5, y + 5, text=clip_name, anchor="nw", fill="white", tags=("clip_body", item_tag))
            handle_width = 8
            start_handle_id = self.grid_canvas.create_rectangle(x + trim_start_pixels, y, x + trim_start_pixels + handle_width, y + height - 2, fill=SELECTED_BG_COLOR, outline="", tags=("handle", "start_handle", item_tag))
            end_handle_id = self.grid_canvas.create_rectangle(x + trim_end_pixels - handle_width, y, x + trim_end_pixels, y + height - 2, fill=SELECTED_BG_COLOR, outline="", tags=("handle", "end_handle", item_tag))
            self.clip_visuals[item_tag] = {"body": body_id, "image": img_id, "text": text_id, "start_handle": start_handle_id, "end_handle": end_handle_id}
            
    def on_clip_press(self, event):
        canvas_x = self.grid_canvas.canvasx(event.x); canvas_y = self.grid_canvas.canvasy(event.y)
        self._drag_data["x"] = canvas_x; self._drag_data["y"] = canvas_y
        try:
            item_id = self.grid_canvas.find_closest(canvas_x, canvas_y)[0]
            self._drag_data["item_tags"] = self.grid_canvas.gettags(item_id)
        except IndexError: return
        if "start_handle" in self._drag_data["item_tags"]: self._drag_data["drag_type"] = "trim_start"
        elif "end_handle" in self._drag_data["item_tags"]: self._drag_data["drag_type"] = "trim_end"
        elif "clip_body" in self._drag_data["item_tags"]: self._drag_data["drag_type"] = "move"
        else: return
        unique_tag = [t for t in self._drag_data["item_tags"] if t.startswith("clip_")][0]
        for item in self.app.arrangement_data:
            if f"clip_{id(item['clip'])}" == unique_tag:
                self._drag_data["clip_object_item"] = item; self._drag_data["original_start_beat"] = item["start_beat"]; self._drag_data["original_trim_start_ratio"] = item["clip"].trim_start_ratio; self._drag_data["original_trim_end_ratio"] = item["clip"].trim_end_ratio; break
        self.grid_canvas.tag_raise(unique_tag)

    def on_clip_drag(self, event):
        if not self._drag_data.get("clip_object_item"): return
        current_x = self.grid_canvas.canvasx(event.x); delta_x = current_x - self._drag_data["x"]
        unique_tag = f"clip_{id(self._drag_data['clip_object_item']['clip'])}"
        visuals = self.clip_visuals.get(unique_tag, {})
        if self._drag_data["drag_type"] == "move":
            self.grid_canvas.move(unique_tag, delta_x, 0)
            self._drag_data["x"] = current_x
        else:
            if self._drag_data["drag_type"] == "trim_start" and "start_handle" in visuals:
                self.grid_canvas.move(visuals["start_handle"], delta_x, 0)
            elif self._drag_data["drag_type"] == "trim_end" and "end_handle" in visuals:
                self.grid_canvas.move(visuals["end_handle"], delta_x, 0)
            self._drag_data["x"] = current_x
    
    def on_clip_release(self, event):
        if self._drag_data.get("clip_object_item"):
            clip_item = self._drag_data["clip_object_item"]; clip_obj = clip_item["clip"]
            if self._drag_data["drag_type"] == "move":
                current_y = self.grid_canvas.canvasy(event.y)
                unique_tag = [t for t in self._drag_data["item_tags"] if t.startswith("clip_")][0]
                item_coords = self.grid_canvas.coords(unique_tag)
                final_x = item_coords[0] if item_coords else 0
                new_track_index = max(0, int(current_y / self.track_height)); new_start_beat = max(0, round(final_x / self.pixels_per_beat))
                clip_item["track_index"] = new_track_index; clip_item["start_beat"] = new_start_beat
            else:
                clip_total_width_px = (clip_obj.duration_seconds * self.app.bpm.get() / 60.0) * self.pixels_per_beat
                if clip_total_width_px > 0:
                    visuals = self.clip_visuals.get(f"clip_{id(clip_obj)}", {})
                    if self._drag_data["drag_type"] == "trim_start" and "start_handle" in visuals:
                        handle_pos_x = self.grid_canvas.coords(visuals["start_handle"])[0]
                        original_clip_start_pos_px = self._drag_data["original_start_beat"] * self.pixels_per_beat
                        new_trim_start_px = handle_pos_x - original_clip_start_pos_px
                        clip_obj.trim_start_ratio = max(0, new_trim_start_px / clip_total_width_px)
                    elif self._drag_data["drag_type"] == "trim_end" and "end_handle" in visuals:
                        handle_pos_x = self.grid_canvas.coords(visuals["end_handle"])[2]
                        original_clip_start_pos_px = self._drag_data["original_start_beat"] * self.pixels_per_beat
                        new_trim_end_px = handle_pos_x - original_clip_start_pos_px
                        clip_obj.trim_end_ratio = min(1.0, new_trim_end_px / clip_total_width_px)
            self._drag_data = {}
            self.redraw()
        
    def move_playhead(self, x_pos):
        try:
            scroll_region = self.grid_canvas.cget("scrollregion"); height = int(scroll_region.split(' ')[3]) if scroll_region else self.winfo_height()
            if self.playhead_id: self.coords(self.playhead_id, x_pos, 0, x_pos, height)
            else: self.playhead_id = self.grid_canvas.create_line(x_pos, 0, x_pos, height, fill="red", width=2)
            self.tag_raise(self.playhead_id)
        except: pass

class App(ctk.CTk):
    def __init__(self):
        super().__init__(); self.title("DAW Pernambucana"); self.geometry("1200x800")
        self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=3); self.grid_rowconfigure(0, weight=1); self.grid_rowconfigure(1, weight=0)
        self.tracks, self.track_count, self.output_filename_count = [], 0, 1; self.active_track = None 
        self.is_recording, self.recording_frames, self.recording_thread = False, [], None
        self.is_playing, self.playback_thread, self.metronome_thread = False, None, None
        self.bpm = ctk.IntVar(value=120); self.is_metronome_on = ctk.BooleanVar(value=True); self._generate_metronome_clicks()
        self.arrangement_data = []; self.arrangement_insert_beat = 0
        self.current_view = 'session'; self.playback_start_time = 0; self.playhead_position_pixels = 0
        self.browser_frame = ctk.CTkFrame(self, corner_radius=0); self.browser_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.transport_frame = ctk.CTkFrame(self, corner_radius=0, height=70); self.transport_frame.grid(row=1, column=1, sticky="nsew", padx=10, pady=10)
        self.main_view_container = ctk.CTkFrame(self, fg_color="transparent"); self.main_view_container.grid(row=0, column=1, sticky="nsew", padx=10, pady=(10,0))
        self.session_view = ContentFrame(self.main_view_container, self); self.session_view.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.arrangement_view = ArrangementFrame(self.main_view_container, self); self.arrangement_view.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.setup_ui_controls(); self.show_session_view()
    def setup_ui_controls(self):
        self.browser_label = ctk.CTkLabel(self.browser_frame, text="Projeto"); self.browser_label.pack(padx=20, pady=20)
        self.save_button = ctk.CTkButton(self.browser_frame, text="Salvar Projeto", command=self.save_project); self.save_button.pack(padx=20, pady=10, fill="x")
        self.load_button = ctk.CTkButton(self.browser_frame, text="Carregar Projeto", command=self.load_project); self.load_button.pack(padx=20, pady=10, fill="x")
        self.add_track_button = ctk.CTkButton(self.browser_frame, text="Adicionar Trilha", command=self.add_track); self.add_track_button.pack(padx=20, pady=10, side="bottom", fill="x")
        transport_controls = TransportFrame(self.transport_frame, self.play_music, self.stop_music, self.record_audio); transport_controls.pack(side="left", fill="y", padx=(0, 20))
        bpm_frame = ctk.CTkFrame(self.transport_frame, fg_color="transparent"); bpm_frame.pack(side="left", padx=20)
        ctk.CTkLabel(bpm_frame, text="BPM:").pack(side="left"); ctk.CTkEntry(bpm_frame, width=50, textvariable=self.bpm).pack(side="left", padx=5)
        ctk.CTkLabel(bpm_frame, text="Metrônomo:").pack(side="left", padx=(10,0)); ctk.CTkSwitch(bpm_frame, text="", variable=self.is_metronome_on, onvalue=True, offvalue=False).pack(side="left", padx=5)
        view_controls = ctk.CTkFrame(self.transport_frame, fg_color="transparent"); view_controls.pack(side="right", padx=10)
        self.session_button = ctk.CTkButton(view_controls, text="Sessão", command=self.show_session_view); self.session_button.pack(pady=5)
        self.arrangement_button = ctk.CTkButton(view_controls, text="Arranjo", command=self.show_arrangement_view); self.arrangement_button.pack(pady=5)
    def show_session_view(self): self.current_view = 'session'; self.session_view.tkraise()
    def show_arrangement_view(self): self.current_view = 'arrangement'; self.arrangement_view.tkraise(); self.arrangement_view.redraw()
    def _record_worker(self):
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32') as stream:
            while self.is_recording: frames, overflowed = stream.read(SAMPLE_RATE // 10); self.recording_frames.append(frames)
    def _play_worker(self, audio_data):
        try: sd.play(audio_data, SAMPLE_RATE); sd.wait()
        finally: self.is_playing = False; self.playhead_position_pixels = 0
    def _metronome_worker(self):
        beat_count = 0
        while self.is_playing or self.is_recording:
            try:
                current_bpm = self.bpm.get();
                if current_bpm <= 0: time.sleep(0.1); continue
                if beat_count % 4 == 0: sd.play(self.click_strong, SAMPLE_RATE)
                else: sd.play(self.click_weak, SAMPLE_RATE)
                beat_count += 1; interval = 60.0 / current_bpm; time.sleep(interval)
            except Exception as e:
                print(f"Erro no metrônomo: {e}"); break
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
        clip = track.get_active_clip()
        if not clip or not os.path.exists(clip.audio_file_path): print("Nenhum clip na trilha para aplicar efeito."); return
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
        project_data = {
            "bpm": self.bpm.get(),
            "tracks": [{"name": t.track_name, "volume": t.volume.get(), "is_muted": t.is_muted, "is_soloed": t.is_soloed, "clips": [c.to_dict() for c in t.clips]} for t in self.tracks],
            "arrangement": [{"clip": item["clip"].to_dict(), "track_index": item["track_index"], "start_beat": item["start_beat"]} for item in self.arrangement_data]
        }
        with open(filepath, 'w') as f: json.dump(project_data, f, indent=4)
    def load_project(self):
        filepath = filedialog.askopenfilename(filetypes=[("Projetos DAW Pernambucana", "*.dawpe")]);
        if not filepath: return
        for track in self.tracks: track.destroy()
        self.tracks, self.track_count, self.active_track = [], 0, None
        with open(filepath, 'r') as f: project_data = json.load(f)
        self.bpm.set(project_data.get("bpm", 120))
        for i, track_data in enumerate(project_data.get("tracks", [])):
            new_track = self.session_view.add_new_track(track_data["name"], i)
            new_track.volume.set(track_data.get("volume", 0.8))
            if track_data.get("is_muted"): new_track.toggle_mute()
            if track_data.get("is_soloed"): new_track.toggle_solo()
            for clip_data in track_data.get("clips", []):
                new_clip = Clip.from_dict(clip_data); new_track.add_clip(new_clip)
            self.tracks.append(new_track)
        self.track_count = len(self.tracks)
        self.arrangement_data = []
        for item_data in project_data.get("arrangement", []):
            clip_obj = Clip.from_dict(item_data["clip"])
            self.arrangement_data.append({"clip": clip_obj, "track_index": item_data["track_index"], "start_beat": item_data["start_beat"]})
        self.arrangement_view.redraw()
    def add_clip_to_arrangement(self, clip, track_index):
        arrangement_item = {"clip": clip, "track_index": track_index, "start_beat": self.arrangement_insert_beat}
        self.arrangement_data.append(arrangement_item);
        clip_duration_beats = (clip.duration_seconds * self.bpm.get()) / 60.0; self.arrangement_insert_beat += clip_duration_beats; self.arrangement_view.redraw()
    def set_active_track(self, track_to_activate):
        for track in self.tracks: track.set_normal_appearance()
        if track_to_activate in self.tracks: self.active_track = track_to_activate; self.active_track.set_selected_appearance()
    def add_track(self):
        track_name = f"Trilha {self.track_count + 1}"; new_track = self.session_view.add_new_track(track_name, self.track_count)
        self.tracks.append(new_track); self.set_active_track(new_track); self.track_count += 1
    def play_music(self):
        if self.is_playing or self.is_recording: return
        if self.current_view == 'arrangement': self._play_arrangement()
        else: self._play_session()
    def _play_session(self):
        if self.is_metronome_on.get(): self.metronome_thread = threading.Thread(target=self._metronome_worker); self.metronome_thread.start()
        tracks_to_play = []; has_solo = any(t.is_soloed for t in self.tracks)
        for track in self.tracks:
            clip = track.get_active_clip()
            if not clip: continue
            if has_solo:
                if track.is_soloed: tracks_to_play.append(track)
            elif not track.is_muted: tracks_to_play.append(track)
        if not tracks_to_play: return
        all_audio_data, max_length = [], 0
        for track in tracks_to_play:
            trimmed_data = track.get_active_clip().get_trimmed_data()
            all_audio_data.append({"track": track, "data": trimmed_data});
            if len(trimmed_data) > max_length: max_length = len(trimmed_data)
        if max_length == 0: return
        mixer_buffer = np.zeros(max_length, dtype=np.float32)
        for item in all_audio_data:
            track, data = item["track"], item["data"]
            data_float = data.astype(np.float32) / np.iinfo(data.dtype).max; data_float *= track.volume.get()
            mixer_buffer[:len(data_float)] += data_float
        peak = np.max(np.abs(mixer_buffer));
        if peak > 1.0: mixer_buffer /= peak
        final_audio_int16 = (mixer_buffer * np.iinfo(np.int16).max).astype(np.int16)
        self.is_playing = True; self.playback_thread = threading.Thread(target=self._play_worker, args=(final_audio_int16,)); self.playback_thread.start()
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
            audio_data_float = (audio_data.astype(np.float32) / np.iinfo(audio_data.dtype).max) * track.volume.get()
            start_sample = int(start_beat * samples_per_beat); end_sample = start_sample + len(audio_data_float)
            if end_sample > len(mixer_buffer): end_sample = len(mixer_buffer); audio_data_float = audio_data_float[:end_sample - start_sample]
            mixer_buffer[start_sample:end_sample] += audio_data_float
        peak = np.max(np.abs(mixer_buffer));
        if peak > 1.0: mixer_buffer /= peak
        final_audio_int16 = (mixer_buffer * np.iinfo(np.int16).max).astype(np.int16)
        self.is_playing = True
        if self.is_metronome_on.get(): self.metronome_thread = threading.Thread(target=self._metronome_worker); self.metronome_thread.start()
        self.playback_thread = threading.Thread(target=self._play_worker, args=(final_audio_int16,)); self.playback_thread.start()
        self.playback_start_time = time.time(); self.arrangement_view.move_playhead(0); self._update_playhead()
    def stop_music(self):
        if self.is_recording:
            self.is_recording = False
            if self.recording_thread: self.recording_thread.join()
            audio_data_float = np.concatenate(self.recording_frames, axis=0); audio_data_int16 = (audio_data_float * np.iinfo(np.int16).max).astype(np.int16)
            wav_filename = f"gravacao_{self.output_filename_count}.wav"; self.output_filename_count += 1
            write(wav_filename, SAMPLE_RATE, audio_data_int16)
            if self.active_track:
                new_clip = Clip(wav_filename)
                if self._generate_waveform_image(new_clip.audio_file_path, new_clip.waveform_image_path):
                    self.active_track.add_clip(new_clip)
        elif self.is_playing:
            self.is_playing = False; sd.stop()
            self.playhead_position_pixels = 0
            self.arrangement_view.move_playhead(0)
    def record_audio(self):
        if self.current_view != 'session': print("Mude para a Visão de Sessão para poder gravar."); return
        if self.is_recording or self.is_playing: return
        if not self.active_track: print("Nenhuma trilha selecionada!"); return
        if self.is_metronome_on.get(): self.metronome_thread = threading.Thread(target=self._metronome_worker); self.metronome_thread.start()
        self.is_recording = True; self.recording_frames = []
        self.recording_thread = threading.Thread(target=self._record_worker); self.recording_thread.start()

if __name__ == "__main__":
    app = App()
    app.mainloop()