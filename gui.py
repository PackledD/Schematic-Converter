from structs import MC_struct, VS_struct, resource_path
from sys import platform
import pyI18n as I18n
from pyI18n import format
import tkinter as tk
import tkinter.filedialog
import tkinter.font as font
import tkinter.messagebox as box
from threading import Thread
FONTSIZE = 15


class App(object):
    def __init__(self, width, height):
        self.root = tk.Tk()
        self.root.resizable(width=0, height=0)
        self.root.title("MC to VS converter")
        self.width = width
        self.height = height
        self.root.geometry(f"{width}x{height}")
        self.font = font.Font(family="Arial", size=FONTSIZE)
        if platform.startswith('win'):
            self.root.iconbitmap(resource_path("icon.ico"))
        self.file = None
        I18n.set_path(resource_path("./lang"))
        self.lang = tk.StringVar()
        self.lang.set(I18n.get_lang())
        self.elems = []
        self.build()
        self.translate()

    def translate(self):
        I18n.set_lang(self.lang.get())
        for elem in self.elems:
            try:
                elem[0]["label"] = format(elem[1])
            except tk.TclError:
                elem[0]["text"] = format(elem[1])
        self.menu.entryconfig(0, label=format("menu.language"))
        self.menu.entryconfig(1, label=format("menu.credits"))
        for i, lang in enumerate(I18n.get_all_langs()):
            self.langmenu.entryconfig(i, label=format("lang." + lang))

    def start(self):
        self.root.mainloop()

    def build(self):
        self.btn_open = tk.Button(self.root, width=13, font=self.font, command=self.open_schematic)
        self.loaded_file = tk.Label(self.root, font=self.font)
        self.btn_convert = tk.Button(self.root, width=13, font=self.font, command=self.convert)
        self.status = tk.Label(self.root, font=self.font)
        self.add_elem(self.btn_open, "btn.open")
        self.add_elem(self.btn_convert, "btn.convert")
        self.btn_open.place(x=30, y=50)
        self.loaded_file.place(x=195, y=55)
        self.btn_convert.place(x=30, y=170)
        self.status.place(x=195, y=175)
        self.build_menu()

    def add_elem(self, elem, string):
        self.elems.append((elem, string))

    def build_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.langmenu = tk.Menu(self.menu, tearoff=0)
        for lang in I18n.get_all_langs():
            self.langmenu.add_radiobutton(value=lang,
                                          variable=self.lang, command=self.translate)
        self.menu.add_cascade(menu=self.langmenu)
        self.menu.add_command(command=self.show_credits)
        self.root.config(menu=self.menu)

    def show_credits(self):
        content = ""
        for i in range(1, 4):
            content += format(f"credits.content{i}") + "\n"
        box.showinfo(format("credits.head"), content)

    def open_schematic(self):
        self.file = tk.filedialog.askopenfilename(initialdir=".",
                                                  title=format("fdialog.select"),
                                                  filetypes=(
                                                      ("schematic files", "*.schematic *.schem"),))
        self.loaded_file["text"] = self.file

    def convert(self):
        if self.file:
            struct = MC_struct(self.file)
            struct.load_from_file()
            vs_file = "".join(self.file.split(".")[:-1] + [".json"])
            result = VS_struct(vs_file)
            calc = Thread(target=self.converting, args=(result, struct))
            calc.start()
        else:
            box.showerror(format("error.head"), format("error.content"))

    def converting(self, res, struct):
        self.btn_open["state"] = tk.DISABLED
        self.btn_convert["state"] = tk.DISABLED
        self.status["text"] = format("app.start")
        for msg in res.convert_from(struct):
            msg = " ".join([format(word) for word in msg.split()])
            self.status["text"] = msg
        self.status["text"] = format("app.end")
        self.btn_open["state"] = tk.ACTIVE
        self.btn_convert["state"] = tk.ACTIVE
