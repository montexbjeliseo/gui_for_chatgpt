
# Imports
import PySimpleGUI as sg
import openai
import os
from openai.error import APIConnectionError, AuthenticationError
import threading

from datetime import datetime

from peewee import SqliteDatabase, Model, CharField, TextField

# Envs
from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())

openai.api_key  = os.getenv('openai.api_key')

# Definitions
APP_TITLE="GUI para Chat GPT"

FILE="Archivo"
RESET_CONTEXT="Restablecer contexto"
SAVE_CHAT="Exportar chat"
QUIT="Salir"

OPTIONS="Opciones"
LOAD_API_KEY="Cargar API Key"

HELP="Ayuda"
ABOUT="Acerca de"

DEFAULT_THEME="DarkGrey1"

CHAT_RESULT_KEY="-chat_result-"
PROMPT_KEY="-prompt_input-"
SUBMIT_KEY="-send_prompt-"
CHAT_LISTBOX = "-select-a-chat"
DELETE_CHAT_BUTTON = "-delete-chat-button"
REGENERATE_CHAT_BUTTON = "-regenerate-chat-button"

THEMES=["Temas", ["Default", "Black", "Dark15", "DarkGrey2", "DarkGrey3", "DarkBrown1"]]

ABOUT_TEXT = "ACERCA DE "

# Define  database connection
db = SqliteDatabase('my_chats.db')

# Define table
class Chat(Model):
    title = CharField()
    query = TextField()
    response = TextField()
    
    class Meta:
        database = db
        
# Migrate
db.create_tables([Chat])

# Program
class Application:
    def __init__(self):
        # Tema por defecto
        sg.theme(DEFAULT_THEME)
        
        # Lista de chats
        self.chats = Chat.select()
        
        # Contexto predeterminado
        self.default_context = {"role": "system",
           "content": "Eres un asistente muy útil."}
        
        # Mensajes
        self.messages = [self.default_context]
        
        # Crea los elementos de la barra de menus
        self.menu_def = [
            [FILE, [RESET_CONTEXT, SAVE_CHAT, "---", QUIT]],
            [OPTIONS, [THEMES, LOAD_API_KEY]],
            [HELP, [ABOUT]]
        ]
        self.menu_bar = sg.Menu(self.menu_def)
        
        # Left frame
        self.chat_list = sg.Listbox(values=list(map(lambda c : c.title, self.chats)), size=(25, 10), expand_y=True, enable_events=True, key=CHAT_LISTBOX)
        self.new_chat_button = sg.Button("Regenerar consulta", key=REGENERATE_CHAT_BUTTON)
        self.delete_chat_button = sg.Button("Eliminar", key=DELETE_CHAT_BUTTON)
        self.left_frame_layout = [[self.chat_list],[self.new_chat_button, self.delete_chat_button]]
        self.left_frame = sg.Frame(title="Historial de conversaciones", layout=self.left_frame_layout, expand_y=True)
        
        # Crea los elementos del panel de la derecha
        self.chat_result = sg.Multiline(size=(100, 25), key=CHAT_RESULT_KEY)
        self.prompt_label = sg.Text("Sobre qué quieres hablar?:")
        self.prompt = sg.Multiline(key=PROMPT_KEY, expand_x=True, size=(100, 5))
        self.submit_button = sg.Button("Enviar", key=SUBMIT_KEY, enable_events=True, bind_return_key=True, expand_x=True)
        self.right_frame_layout = [
            [self.chat_result],
            [self.prompt_label],
            [self.prompt],
            [self.submit_button]
        ]
        self.right_frame = sg.Frame(title="Conversación", layout=self.right_frame_layout)
        
        # Crea la ventana
        self.layout = [
            [self.menu_bar],
            [self.left_frame, sg.VerticalSeparator(), self.right_frame]
        ]
        self.window = sg.Window(APP_TITLE, self.layout)
        
    # Inicia un bucle para manejar los eventos de la ventana
    def start(self):
        first_load = True
        while True:
            # Leer eventos
            event, values = self.window.read()
            
            if first_load:
                self.refresh_chat_list()
                first_load = False
            
            # Cierra la ventana
            if event == sg.WIN_CLOSED or event == QUIT:
                break
            
            # Click en Enviar
            if event in (SUBMIT_KEY, 'Return:'+PROMPT_KEY):
                
                # Si necesita clave de la api
                if self.needs_api_key():
                    # Informar que tiene que cargar una clave
                    sg.popup("No se cargó ninguna API Key", "No se cargó ninguna API Key. Para conseguir una visita https://platform.openai.com\nLuego puedes cargarla a través de Opciones>Cargar API Key")
                else:
                    # Obtener la consulta del usuario
                    query = values[PROMPT_KEY]
                    # Se pasa al método encargado de procesar la consulta
                    self.send_query(query)
                    # Limpiar el cuadro de consultas
                    self.window[PROMPT_KEY].update(value="")
            # Cargar API KEY
            elif event == LOAD_API_KEY:
                self.load_api_key()
            # Guardar conversacion en un archivo
            elif event == SAVE_CHAT:
                # Se solicita al usuario que escoga donde guardar
                filename = sg.tk.filedialog.asksaveasfilename(
                    defaultextension='txt',
                    filetypes=(("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")),
                    parent=self.window.TKroot,
                    title="Guardar como",
                    initialfile=self.chat_list.get()[0]
                )
                # Si se escogió un archivo
                if filename != None and len(filename) > 0:
                    # Se exporta la conversacion
                    self.save_chat_to(filename)
            # Acerca de 
            elif event == ABOUT:
                # Muestra cuadro acerca de
                sg.popup(ABOUT_TEXT)
            # Nuevo chat
            elif event == RESET_CONTEXT:
                self.reset_context()
            elif event == CHAT_LISTBOX:
                # Si la lista tiene al menos un elemento
                if self.chat_list.get():
                    # Obtener el elemento seleccionado
                    selected_title = self.chat_list.get()[0]
                    # Cargar chat
                    self.load_chat(selected_title)
                    # Obtener el indice
                    index = self.chat_list.get_list_values().index(selected_title)
                    # Establecer como seleccionado
                    self.chat_list.update(set_to_index=index)
                    
            elif event == DELETE_CHAT_BUTTON:
                delete = sg.popup_yes_no("Desea eliminar la conversación seleccionada?")
                if delete == "Yes":
                    self.delete_chat(self.chat_list.get()[0])
                    
            elif event == REGENERATE_CHAT_BUTTON:
                self.regenerate_query(self.chat_list.get()[0])
                
        # Destruir/cerrar la ventana cuando finaliza el bucle           
        self.window.close()
    
    # Procesar una consulta
    def send_query(self, query):
        # Crea un nuevo recurso
        new_chat = Chat(title=query[:45]+str(datetime.now()), query=query, response="Esperando respuesta")
        # Guarda en la db
        new_chat.save()
        # Delegacion de la carga
        self.load_chat(new_chat.title)
        # Crear un hilo para escuchar la respuesta del servidor sin bloquear la app
        threading.Thread(target=self.push_response, args=[new_chat.title, query]).start()
        
    def set_query_response(self, title, response):
        # Busca por query
        selected_chat = Chat.get(Chat.title == title)
        # Actualiza la respuesta
        selected_chat.response = response
        # Guarda
        selected_chat.save()
        # Carga/muestra el resultado
        self.load_chat(title)
        
    def delete_chat(self, title):
        selected_chat = Chat.get(Chat.title == title)
        selected_chat.delete_instance()
        self.refresh_chat_list()
        
    def load_chat(self, title):
        # Buscar consulta
        chat_from_db = Chat.get(Chat.title == title)
        # Armar el texto
        chat_text = f"Usuario: {chat_from_db.query}\n"
        chat_text += f"ChatBot: {chat_from_db.response}\n"
        # Mostrar el texto en el chat view/result
        self.window[CHAT_RESULT_KEY].update(value=chat_text)
        self.refresh_chat_list()
        
    def refresh_chat_list(self):
        # Recargar la lista de chats
        self.chats = Chat.select()
        # Actualizar el listbox con los titulos
        self.chat_list.update(values=[chat.title for chat in self.chats], set_to_index=len(self.chats)-1)
    
    def regenerate_query(self, title):
        # Buscamos el chat en la db
        selected_chat = Chat.get(Chat.title == title)
        # Y volvemos a enviar la consulta
        self.send_query(selected_chat.query)
        
    def load_api_key(self):
        # Solicitar al usuario que ingrese la clave mediante ventana emergente 
        new_api_key = sg.popup_get_text(title="Cargar API Key", message="Pega aquí tu API Key:", default_text=openai.api_key)
        # Si la nueva clave es ingresada, se guarda, sino se mantiene la anterior
        openai.api_key = new_api_key if new_api_key != None else openai.api_key
        
        with open(".env", "w") as file:
            file.write(f"openai.api_key={openai.api_key}")
        
    # Nuevo chat
    def create_new_chat(self, title, content):
        new_chat = {
            "title": title,
            "messages": content
        }
        self.chats.append(new_chat)
        self.chat_list.update(values=[chat.title for chat in self.chats])
                
    # Reiniciar chat
    def reset_context(self):
        self.messages = [self.default_context]
        self.window[CHAT_RESULT_KEY].update(value="")
        self.window[PROMPT_KEY].update(value="")
        
    # Añadir texto al chat
    def push_to_chat(self, name, text):
        
        if len(self.chats) == 0:
            self.create_new_chat(text[:20], text)
        
        chat = self.window[CHAT_RESULT_KEY].get()
        chat += "\n" if chat != "" else "" # Ahre
        chat += name
        chat += ": "
        chat += text
        chat += "\n"
        self.window[CHAT_RESULT_KEY].update(value=chat)

    def push_response(self, title, query):
        try:
            # Se agrega la consulta al contexto
            self.messages.append({"role": "user", "content": query})
            # Se envía la consulta
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo", messages=self.messages)
            # Se saca lo importante de la respuesta
            response_content = response.choices[0].message.content
            # Lo agregamos al contexto
            self.messages.append({"role": "assistant", "content": response_content})
            # Lo asociamos con la consulta
            self.set_query_response(title, response_content)
        except APIConnectionError as ace:
            self.push_to_chat("Sistema", "Ocurrió un error al conectarse con el servidor. Asegurate de que tienes accesso a internet")
        except AuthenticationError as authEx:
            self.push_to_chat("Sistema", "Error de autenticación. Asegúrese de haber proporcionado una API KEY válida")
            
        
    def needs_api_key(self):
        return openai.api_key == ""

    def save_chat_to(self, filename):
        with open(filename, "w") as file:
            file.write(self.window[CHAT_RESULT_KEY].get())

app = Application()
app.start()