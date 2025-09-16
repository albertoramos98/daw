import customtkinter as ctk
import sounddevice as sd

class AudioSettingsWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Configurações de Áudio")
        self.geometry("600x250")
        self.transient(master)
        self.grab_set()

        try:
            self.devices = sd.query_devices()
            self.hostapis = sd.query_hostapis()
        except Exception as e:
            print(f"Erro ao consultar dispositivos de áudio: {e}")
            self.devices, self.hostapis = [], []

        # --- Seleção da API de Áudio (ASIO, MME, etc) ---
        api_frame = ctk.CTkFrame(self)
        api_frame.pack(padx=20, pady=10, fill="x")
        ctk.CTkLabel(api_frame, text="API de Áudio (Driver):", width=150, anchor="w").pack(side="left")
        
        api_names = [api['name'] for api in self.hostapis]
        self.selected_api = ctk.StringVar()
        self.api_menu = ctk.CTkOptionMenu(api_frame, variable=self.selected_api, values=api_names, command=self.update_device_lists)
        self.api_menu.pack(side="left", expand=True, fill="x")

        # --- Seleção do Dispositivo de Entrada ---
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(padx=20, pady=10, fill="x")
        ctk.CTkLabel(input_frame, text="Dispositivo de Entrada:", width=150, anchor="w").pack(side="left")
        self.input_devices_map = {}
        self.selected_input = ctk.StringVar()
        self.input_menu = ctk.CTkOptionMenu(input_frame, variable=self.selected_input, values=["Nenhum"])
        self.input_menu.pack(side="left", expand=True, fill="x")

        # --- Seleção do Dispositivo de Saída ---
        output_frame = ctk.CTkFrame(self)
        output_frame.pack(padx=20, pady=10, fill="x")
        ctk.CTkLabel(output_frame, text="Dispositivo de Saída:", width=150, anchor="w").pack(side="left")
        self.output_devices_map = {}
        self.selected_output = ctk.StringVar()
        self.output_menu = ctk.CTkOptionMenu(output_frame, variable=self.selected_output, values=["Nenhum"])
        self.output_menu.pack(side="left", expand=True, fill="x")
        
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(padx=20, pady=20, side="bottom")
        ctk.CTkButton(button_frame, text="OK", command=self.apply_and_close).pack(side="left", padx=10)
        ctk.CTkButton(button_frame, text="Cancelar", command=self.destroy).pack(side="left", padx=10)

        # Popula as listas iniciais
        try:
            default_api_name = sd.query_hostapis(sd.default.hostapi)['name']
            self.selected_api.set(default_api_name)
            self.update_device_lists(default_api_name)
        except Exception as e:
            if api_names:
                self.selected_api.set(api_names[0])
                self.update_device_lists(api_names[0])

    def update_device_lists(self, selected_api_name):
        try:
            api_index = [i for i, api in enumerate(self.hostapis) if api['name'] == selected_api_name][0]
        except (ValueError, IndexError):
            api_index = -1

        # Atualiza lista de entrada
        input_names, self.input_devices_map = [], {}
        for i, dev in enumerate(self.devices):
            if dev['hostapi'] == api_index and dev['max_input_channels'] > 0:
                name = f"({i}) {dev['name']}"
                input_names.append(name)
                self.input_devices_map[name] = i
        self.input_menu.configure(values=input_names if input_names else ["Nenhum"])
        
        try:
            default_input_id = sd.default.device[0]
            default_input_name = [name for name, index in self.input_devices_map.items() if index == default_input_id]
            if default_input_name: self.selected_input.set(default_input_name[0])
            elif input_names: self.selected_input.set(input_names[0])
            else: self.selected_input.set("Nenhum")
        except:
             if input_names: self.selected_input.set(input_names[0])
             else: self.selected_input.set("Nenhum")

        # Atualiza lista de saída
        output_names, self.output_devices_map = [], {}
        for i, dev in enumerate(self.devices):
            if dev['hostapi'] == api_index and dev['max_output_channels'] > 0:
                name = f"({i}) {dev['name']}"
                output_names.append(name)
                self.output_devices_map[name] = i
        self.output_menu.configure(values=output_names if output_names else ["Nenhum"])
        
        try:
            default_output_id = sd.default.device[1]
            default_output_name = [name for name, index in self.output_devices_map.items() if index == default_output_id]
            if default_output_name: self.selected_output.set(default_output_name[0])
            elif output_names: self.selected_output.set(output_names[0])
            else: self.selected_output.set("Nenhum")
        except:
            if output_names: self.selected_output.set(output_names[0])
            else: self.selected_output.set("Nenhum")
    
    def apply_and_close(self):
        try:
            input_id = self.input_devices_map.get(self.selected_input.get(), -1)
            output_id = self.output_devices_map.get(self.selected_output.get(), -1)
            sd.default.device = (input_id, output_id)
            print(f"Dispositivo de áudio definido -> Entrada: {self.selected_input.get()}, Saída: {self.selected_output.get()}")
            self.destroy()
        except Exception as e:
            print(f"Erro ao aplicar configurações de áudio: {e}")