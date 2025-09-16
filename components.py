import customtkinter as ctk
import random
from PIL import Image, ImageTk
import os

# --- Constantes de Cor ---
NORMAL_BG_COLORS = ["#2E4053", "#512E53", "#2E5345", "#532E2E"]
SELECTED_BG_COLOR = "#F1C40F"
MUTE_ON_COLOR = "#3498DB"
SOLO_ON_COLOR = "#F39C12"

class WaveformCanvas(ctk.CTkCanvas):
    def __init__(self, master, track_frame):
        super().__init__(master, bg="#343638", highlightthickness=0); self.track_frame = track_frame; self.image = None; self.photo_image = None; self.start_handle_pos = 0; self.end_handle_pos = 0; self.image_id, self.start_handle_id, self.end_handle_id, self.dark_overlay_start_id, self.dark_overlay_end_id = None, None, None, None, None; self._drag_data = {"x": 0, "y": 0, "item_tag": None}; self.tag_bind("handle", "<ButtonPress-1>", self.on_press_handle); self.tag_bind("handle", "<B1-Motion>", self.on_drag_handle); self.tag_bind("handle", "<Enter>", lambda e: self.config(cursor="sb_h_double_arrow")); self.tag_bind("handle", "<Leave>", lambda e: self.config(cursor=""))
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
            if active_clip: self.start_handle_pos = int(active_clip.trim_start_ratio * width); self.end_handle_pos = int(active_clip.trim_end_ratio * width)
            self.update_visuals()
        except Exception as e: print(f"Erro ao exibir a imagem: {e}")
    def update_visuals(self): height = self.winfo_height(); self.coords(self.dark_overlay_start_id, 0, 0, self.start_handle_pos, height); self.coords(self.dark_overlay_end_id, self.end_handle_pos, 0, self.winfo_width(), height); self.coords(self.start_handle_id, self.start_handle_pos, 0, self.start_handle_pos, height); self.coords(self.end_handle_id, self.end_handle_pos, 0, self.end_handle_pos, height)
    def on_press_handle(self, event): tags = self.gettags(self.find_withtag("current")[0]); self._drag_data["item_tag"] = "start_handle" if "start_handle" in tags else "end_handle"; self._drag_data["x"] = event.x
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
        super().__init__(master, height=100, border_width=2, border_color="black"); self.track_name = track_name; self.app = app_instance; self.track_index = track_index
        self.normal_bg_color = random.choice(NORMAL_BG_COLORS); self.configure(fg_color=self.normal_bg_color); self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, weight=5)
        controls_frame = ctk.CTkFrame(self, fg_color="transparent"); controls_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=10, sticky="nsew")
        self.name_label = ctk.CTkLabel(controls_frame, text=self.track_name, font=("Arial", 12)); self.name_label.pack(anchor="w", pady=(0, 5))
        self.copy_to_arr_button = ctk.CTkButton(controls_frame, text="-> Arranjo", width=100, command=self.copy_clip_to_arrangement); self.copy_to_arr_button.pack(anchor="w", pady=5)
        self.is_muted = ctk.BooleanVar(value=False); self.is_soloed = ctk.BooleanVar(value=False); self.volume = ctk.DoubleVar(value=0.8)
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
    def select_track(self, event=None):
        if event and event.widget in (self.copy_to_arr_button,): return "break"
        self.app.set_active_track(self)
    def set_selected_appearance(self): self.configure(border_color=SELECTED_BG_COLOR)
    def set_normal_appearance(self): self.configure(border_color="black")
    def display_waveform(self, image_path): self.clips_area_canvas.display_waveform(image_path)

class MixerChannelStrip(ctk.CTkFrame):
    def __init__(self, master, track, app_instance):
        super().__init__(master, fg_color="#3B3B3B", border_color="#2B2B2B", border_width=1, width=120)
        self.track = track; self.app = app_instance
        self.pack_propagate(False); self.grid_columnconfigure(0, weight=1); self.grid_columnconfigure(1, minsize=20)
        self.name_label = ctk.CTkLabel(self, text=self.track.track_name, font=("Arial", 10)); self.name_label.grid(row=0, column=0, columnspan=3, pady=5, padx=5, sticky="ew")
        mute_solo_frame = ctk.CTkFrame(self, fg_color="transparent"); mute_solo_frame.grid(row=1, column=0, columnspan=3, pady=2, padx=5, sticky="ew")
        self.mute_button = ctk.CTkButton(mute_solo_frame, text="M", width=35, command=self.toggle_mute); self.mute_button.pack(side="left", expand=True, padx=(0,2))
        self.solo_button = ctk.CTkButton(mute_solo_frame, text="S", width=35, command=self.toggle_solo); self.solo_button.pack(side="right", expand=True, padx=(2,0))
        fader_frame = ctk.CTkFrame(self, fg_color="transparent"); fader_frame.grid(row=2, column=0, columnspan=3, pady=(5, 10), padx=5, sticky="ns")
        fader_frame.grid_rowconfigure(0, weight=1); fader_frame.grid_columnconfigure(0, weight=1); fader_frame.grid_columnconfigure(1, weight=0)
        self.volume_slider = ctk.CTkSlider(fader_frame, from_=1.0, to=0.0, variable=self.track.volume, number_of_steps=100, orientation="vertical", button_color="#F1C40F", progress_color="#555555"); self.volume_slider.grid(row=0, column=0, sticky="ns", padx=(15, 5))
        db_markers_frame = ctk.CTkFrame(fader_frame, fg_color="transparent"); db_markers_frame.grid(row=0, column=1, sticky="ns")
        for db_level in [ "+6", "0", "-6", "-12", "-24", "-48"]: ctk.CTkLabel(db_markers_frame, text=db_level, font=("Arial", 8)).pack(expand=True, anchor="w")
        self.vu_meter = ctk.CTkProgressBar(self, orientation="vertical", progress_color="#4CAF50", fg_color="#1F1F1F"); self.vu_meter.grid(row=2, column=0, columnspan=3, pady=(5,10), padx=(65,0), sticky="ns"); self.vu_meter.set(0)
        self.track.is_muted.trace_add("write", self.update_button_colors)
        self.track.is_soloed.trace_add("write", self.update_button_colors)
        self.update_button_colors()
    def set_meter_level(self, level): self.vu_meter.set(level)
    def toggle_mute(self): self.track.is_muted.set(not self.track.is_muted.get())
    def toggle_solo(self): self.app.toggle_solo_for_track(self.track.track_index)
    def update_button_colors(self, *args):
        mute_color = MUTE_ON_COLOR if self.track.is_muted.get() else ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        solo_color = SOLO_ON_COLOR if self.track.is_soloed.get() else ctk.ThemeManager.theme["CTkButton"]["fg_color"]
        self.mute_button.configure(fg_color=mute_color); self.solo_button.configure(fg_color=solo_color)

class MixerFrame(ctk.CTkScrollableFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, label_text="Mixer", orientation="horizontal")
        self.app = app_instance; self.channel_strips = {}
    def add_channel_strip(self, track):
        strip = MixerChannelStrip(self, track, self.app); strip.pack(side="left", padx=(0, 2), pady=5, fill="y", expand=True)
        self.channel_strips[track.track_index] = strip

class TransportFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, fg_color="transparent")
        self.play_button = ctk.CTkButton(self, text="▶ Play", width=60, command=app_instance.play_music); self.play_button.pack(side="left", padx=5)
        self.stop_button = ctk.CTkButton(self, text="■ Stop", width=60, command=app_instance.stop_music); self.stop_button.pack(side="left", padx=5)
        self.record_button = ctk.CTkButton(self, text="● Rec", width=60, command=app_instance.record_audio, fg_color="#C0392B", hover_color="#E74C3C"); self.record_button.pack(side="left", padx=5)
        bpm_frame = ctk.CTkFrame(self, fg_color="transparent"); bpm_frame.pack(side="left", padx=20)
        ctk.CTkLabel(bpm_frame, text="BPM:").pack(side="left"); ctk.CTkEntry(bpm_frame, width=50, textvariable=app_instance.bpm).pack(side="left", padx=5)
        metronome_frame = ctk.CTkFrame(self, fg_color="transparent"); metronome_frame.pack(side="left", padx=10)
        ctk.CTkLabel(metronome_frame, text="Metrônomo:").pack(side="left"); ctk.CTkSwitch(metronome_frame, text="", variable=app_instance.is_metronome_on, onvalue=True, offvalue=False).pack(side="left", padx=5)

class AccordionCategory(ctk.CTkFrame):
    def __init__(self, master, title):
        super().__init__(master, fg_color="transparent")
        self.title = title; self.content_visible = False
        self.header_button = ctk.CTkButton(self, text=self.title, command=self.toggle_content); self.header_button.pack(fill="x")
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
    def toggle_content(self):
        for widget in self.master.winfo_children():
            if isinstance(widget, AccordionCategory) and widget != self:
                widget.hide_content()
        if self.content_visible: self.hide_content()
        else: self.show_content()
    def show_content(self): self.content_frame.pack(fill="x", pady=(0, 5)); self.content_visible = True
    def hide_content(self): self.content_frame.pack_forget(); self.content_visible = False