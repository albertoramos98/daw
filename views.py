import customtkinter as ctk
from PIL import Image, ImageTk
import os

# Importa as peças que vamos usar, do nosso arquivo de componentes
from components import TrackFrame, WaveformCanvas 

# --- Constantes de Cor ---
SELECTED_BG_COLOR = "#F1C40F"

class ContentFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, corner_radius=0)
        self.app = app_instance
        
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Trilhas")
        self.scrollable_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
    def add_new_track(self, track_name, track_index):
        track = TrackFrame(self.scrollable_frame, track_name, self.app, track_index)
        track.pack(fill="x", expand=True, padx=5, pady=5)
        return track

class ArrangementFrame(ctk.CTkFrame):
    def __init__(self, master, app_instance):
        super().__init__(master, corner_radius=0, fg_color="#2B2B2B")
        self.app = app_instance
        self.track_height = 100

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.grid_canvas = ctk.CTkCanvas(self, bg="#2B2B2B", highlightthickness=0)
        self.grid_canvas.grid(row=0, column=0, sticky="nsew")
        
        self.v_scrollbar = ctk.CTkScrollbar(self, orientation="vertical", command=self.grid_canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar = ctk.CTkScrollbar(self, orientation="horizontal", command=self.grid_canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.grid_canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        
        self.grid_canvas.bind("<Configure>", self.redraw)
        self.playhead_id = None
        self.clip_visuals = {}
        
        self._drag_data = {}
        
        self.grid_canvas.tag_bind("clip_body", "<ButtonPress-1>", self.on_press)
        self.grid_canvas.tag_bind("clip_body", "<B1-Motion>", self.on_drag)
        self.grid_canvas.tag_bind("clip_body", "<ButtonRelease-1>", self.on_release)
        self.grid_canvas.tag_bind("clip_body", "<Enter>", lambda e: self.grid_canvas.config(cursor="hand2"))
        self.grid_canvas.tag_bind("clip_body", "<Leave>", lambda e: self.grid_canvas.config(cursor=""))
        
        self.grid_canvas.tag_bind("handle", "<ButtonPress-1>", self.on_press)
        self.grid_canvas.tag_bind("handle", "<B1-Motion>", self.on_drag)
        self.grid_canvas.tag_bind("handle", "<ButtonRelease-1>", self.on_release)
        self.grid_canvas.tag_bind("handle", "<Enter>", lambda e: self.grid_canvas.config(cursor="sb_h_double_arrow"))
        self.grid_canvas.tag_bind("handle", "<Leave>", lambda e: self.grid_canvas.config(cursor=""))
    
    def redraw(self, event=None):
        self.grid_canvas.delete("all")
        self.draw_grid()
        self.draw_clips()
        if self.playhead_id:
            self.move_playhead(self.app.playhead_position_pixels)

    def draw_grid(self):
        canvas_width_virtual = 30000
        canvas_height_virtual = max(self.app.track_count * self.track_height, self.winfo_height())
        
        bpm = self.app.bpm.get()
        beats_per_bar = 4
        self.pixels_per_beat = 100.0
        pixels_per_bar = self.pixels_per_beat * beats_per_bar
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
            clip = item["clip"]
            track_index = item["track_index"]
            start_beat = item["start_beat"]
            
            clip_total_duration_beats = (clip.duration_seconds * self.app.bpm.get()) / 60.0
            clip_total_width_px = clip_total_duration_beats * self.pixels_per_beat
            
            trim_start_pixels = clip_total_width_px * clip.trim_start_ratio
            trim_end_pixels = clip_total_width_px * clip.trim_end_ratio
            trimmed_width = trim_end_pixels - trim_start_pixels
            
            x = start_beat * self.pixels_per_beat
            y = track_index * self.track_height
            height = self.track_height
            
            item_tag = f"clip_{id(clip)}"
            
            body_id = self.grid_canvas.create_rectangle(x + trim_start_pixels, y, x + trim_end_pixels, y + height - 2, fill="#5DADE2", outline="black", width=2, tags=("clip_body", item_tag))
            img_id, text_id = None, None
            
            if os.path.exists(clip.waveform_image_path):
                try:
                    pil_img = Image.open(clip.waveform_image_path)
                    crop_x1 = int(pil_img.width * clip.trim_start_ratio)
                    crop_x2 = int(pil_img.width * clip.trim_end_ratio)
                    if crop_x1 < crop_x2:
                        pil_img_cropped = pil_img.crop((crop_x1, 0, crop_x2, pil_img.height))
                        pil_img_resized = pil_img_cropped.resize((int(trimmed_width), int(height - 4)), Image.Resampling.LANCZOS)
                        tk_img = ImageTk.PhotoImage(pil_img_resized)
                        self.clip_visuals[item_tag] = tk_img 
                        img_id = self.grid_canvas.create_image(x + trim_start_pixels + 2, y + 2, image=tk_img, anchor="nw", tags=("clip_body", item_tag))
                except Exception as e:
                    pass # Evita crash se a imagem estiver corrompida
            
            clip_name = os.path.basename(clip.audio_file_path)
            text_id = self.grid_canvas.create_text(x + trim_start_pixels + 5, y + 5, text=clip_name, anchor="nw", fill="white", tags=("clip_body", item_tag))
            
            handle_width = 8
            start_handle_id = self.grid_canvas.create_rectangle(x + trim_start_pixels, y, x + trim_start_pixels + handle_width, y + height - 2, fill=SELECTED_BG_COLOR, outline="", tags=("handle", "start_handle", item_tag))
            end_handle_id = self.grid_canvas.create_rectangle(x + trim_end_pixels - handle_width, y, x + trim_end_pixels, y + height - 2, fill=SELECTED_BG_COLOR, outline="", tags=("handle", "end_handle", item_tag))

            self.clip_visuals[item_tag] = {"body": body_id, "image_tk": tk_img if 'tk_img' in locals() else None, "image_id": img_id, "text": text_id, "start_handle": start_handle_id, "end_handle": end_handle_id}

    def on_press(self, event):
        canvas_x = self.grid_canvas.canvasx(event.x)
        canvas_y = self.grid_canvas.canvasy(event.y)
        self._drag_data["x"] = canvas_x
        self._drag_data["y"] = canvas_y
        
        try:
            item_id = self.grid_canvas.find_closest(canvas_x, canvas_y)[0]
            self._drag_data["item_tags"] = self.grid_canvas.gettags(item_id)
        except IndexError:
            return

        if "start_handle" in self._drag_data["item_tags"]:
            self._drag_data["drag_type"] = "trim_start"
        elif "end_handle" in self._drag_data["item_tags"]:
            self._drag_data["drag_type"] = "trim_end"
        elif "clip_body" in self._drag_data["item_tags"]:
            self._drag_data["drag_type"] = "move"
        else:
            return
            
        unique_tag = [t for t in self._drag_data["item_tags"] if t.startswith("clip_")][0]
        for item in self.app.arrangement_data:
            if f"clip_{id(item['clip'])}" == unique_tag:
                self._drag_data["clip_object_item"] = item
                break
        
        self.grid_canvas.tag_raise(unique_tag)

    def on_drag(self, event):
        if not self._drag_data.get("clip_object_item"):
            return
        
        current_x = self.grid_canvas.canvasx(event.x)
        delta_x = current_x - self._drag_data["x"]
        
        if self._drag_data["drag_type"] == "move":
            unique_tag = [t for t in self._drag_data["item_tags"] if t.startswith("clip_")][0]
            self.grid_canvas.move(unique_tag, delta_x, 0)
            self._drag_data["x"] = current_x
        else:
            self.on_release(event) # Simplificado para redesenhar no arrasto de handles

    def on_release(self, event):
        if self._drag_data.get("clip_object_item"):
            clip_item = self._drag_data["clip_object_item"]
            clip_obj = clip_item["clip"]
            
            if self._drag_data["drag_type"] == "move":
                current_y = self.grid_canvas.canvasy(event.y)
                unique_tag = [t for t in self._drag_data["item_tags"] if t.startswith("clip_")][0]
                item_coords = self.grid_canvas.coords(unique_tag)
                final_x = item_coords[0] if item_coords else 0
                
                new_track_index = max(0, int(current_y / self.track_height))
                new_start_beat = max(0, round(final_x / self.pixels_per_beat))
                
                clip_item["track_index"] = new_track_index
                clip_item["start_beat"] = new_start_beat
            
            self._drag_data = {}
            self.redraw()
            
    def move_playhead(self, x_pos):
        try:
            scroll_region = self.grid_canvas.cget("scrollregion")
            height = int(scroll_region.split(' ')[3]) if scroll_region else self.winfo_height()
            if self.playhead_id:
                self.coords(self.playhead_id, x_pos, 0, x_pos, height)
            else:
                self.playhead_id = self.grid_canvas.create_line(x_pos, 0, x_pos, height, fill="red", width=2)
            self.tag_raise(self.playhead_id)
        except:
             pass