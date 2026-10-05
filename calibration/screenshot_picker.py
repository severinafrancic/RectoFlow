"""Lokaler Screenshot-Picker. Das Bild bleibt im RAM; Canvas ist nur Anzeige."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageTk

from .geometry import (CalibrationError, center, contains, canvas_transform,
                       to_screen, move_rect, resize_rect, new_rect, fit_aspect,
                       paper_ratio, validate_selection,resize_aspect)
from .regions import capture_names, NAVIGATION

COLORS = {"LEFT":"#ff5252", "RIGHT":"#4ca6ff", "NEXT":"#41ef92", "PROGRESS":"#ffcf48"}


class RectanglePicker:
    def __init__(self, root, image, rects, point, bounds, paper="A4", orientation="portrait", final=False, save_label=None, navigation_mode="next_button"):
        self.root, self.image, self.bounds = root, image, bounds
        self.rects = copy.deepcopy(rects)
        self.rects.setdefault("NEXT",None)
        self.rects.setdefault("PROGRESS",None)
        self.point = list(point) if point and self.rects["NEXT"] and contains(self.rects["NEXT"], point) else center(self.rects["NEXT"]) if self.rects["NEXT"] else None
        self.result = None
        self.selected = capture_names(self.rects)[0] if capture_names(self.rects) else "NEXT"
        self.mode = "edit"
        self.drag = None
        self.window = tk.Toplevel(root)
        self.window.title("RectoFlow: Kontrollvorschau" if final else "RectoFlow: Bereiche auswaehlen")
        self.window.geometry(f"{image.width}x{image.height}+0+0")
        self.window.state("zoomed")
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Escape>", lambda e:self.cancel())
        self.window.bind("<Delete>", lambda e:self.delete())
        self.window.bind("<Return>", lambda e:self.accept())
        toolbar = ttk.Frame(self.window, padding=6)
        toolbar.pack(fill="x")
        self.selected_var=tk.StringVar(value=self.display_name(self.selected))
        self.selector=ttk.Combobox(toolbar,textvariable=self.selected_var,values=[self.display_name(n) for n in self.rects],width=16,state="readonly")
        self.selector.pack(side="left",padx=3)
        self.selector.bind("<<ComboboxSelected>>",lambda e:self.select(list(self.rects)[self.selector.current()]))
        ttk.Button(toolbar,text="+ Bereich",command=self.add_region).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Frueher",command=lambda:self.reorder(-1)).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Spaeter",command=lambda:self.reorder(1)).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Neu aufziehen",command=self.draw_new).pack(side="left",padx=3)
        ttk.Button(toolbar,text="Loeschen",command=self.delete).pack(side="left",padx=3)
        ttk.Button(toolbar,text="Klickpunkt setzen",command=self.set_point).pack(side="left",padx=3)
        formatbar=ttk.Frame(self.window,padding=6)
        formatbar.pack(fill="x")
        ttk.Label(formatbar,text="Papier:").pack(side="left")
        self.paper = tk.StringVar(value=paper)
        self.orientation = tk.StringVar(value=orientation)
        from .geometry import PAPER_MM
        papers = ttk.Combobox(formatbar,textvariable=self.paper,values=["A4","A5","A3","A6","A2","A1","A0","Letter","Legal","Original"],width=8,state="readonly")
        papers.pack(side="left",padx=4)
        direction_label=tk.StringVar(value="Querformat" if orientation=="landscape" else "Hochformat")
        direction = ttk.Combobox(formatbar,textvariable=direction_label,values=["Hochformat","Querformat"],width=12,state="readonly")
        direction.pack(side="left")
        papers.bind("<<ComboboxSelected>>",self.paper_changed)
        def direction_changed(event):
            self.orientation.set("landscape" if direction_label.get()=="Querformat" else "portrait")
            self.paper_changed()
        direction.bind("<<ComboboxSelected>>",direction_changed)
        self.navigation=tk.StringVar(value=navigation_mode)
        ttk.Label(formatbar,text="Navigation:").pack(side="left",padx=5)
        labels={"next_button":"Weiter-Button","manual":"Manuell","none":"Einmal"}
        nav_label=tk.StringVar(value=labels[navigation_mode])
        nav=ttk.Combobox(formatbar,textvariable=nav_label,values=list(labels.values()),width=14,state="readonly")
        nav.pack(side="left")
        nav.bind("<<ComboboxSelected>>",lambda e:self.navigation.set(next(k for k,v in labels.items() if v==nav_label.get())))
        footer = ttk.Frame(self.window,padding=6)
        footer.pack(side="bottom",fill="x")
        ttk.Button(footer,text=save_label or ("Bestaetigt speichern" if final else "Live-Vorschau"),command=self.accept).pack(side="right",padx=3)
        ttk.Button(footer,text="Abbrechen",command=self.cancel).pack(side="right",padx=3)
        if final:
            ttk.Button(footer,text="Neu kalibrieren",command=self.recalibrate).pack(side="right",padx=3)
        self.status = tk.StringVar()
        ttk.Label(footer,textvariable=self.status).pack(side="left")
        self.canvas = tk.Canvas(self.window,background="#23262c",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.render())
        self.canvas.bind("<ButtonPress-1>",self.press)
        self.canvas.bind("<B1-Motion>",self.motion)
        self.canvas.bind("<ButtonRelease-1>",lambda e:setattr(self,"drag",None))
        self.transform = (1,0,0)
        self.photo = None
        self.paper_changed()
        self.window.update_idletasks()
        self.window.focus_force()

    def select(self,name):
        self.selected, self.mode = name, "edit"
        if hasattr(self,"selected_var"):
            self.selected_var.set(self.display_name(name))
        self.render()

    def refresh_selector(self):
        if hasattr(self,"selector"):
            self.selector.configure(values=[self.display_name(n) for n in self.rects])

    def display_name(self,name):
        if name=="NEXT":return "Weiter-Button"
        if name=="PROGRESS":return "Fortschritt"
        return f"Bereich {capture_names(self.rects).index(name)+1}"

    def modernize(self):
        if "LEFT" in self.rects or "RIGHT" in self.rects:
            ordered=[(f"REGION_{i:03d}",self.rects[name]) for i,name in enumerate(capture_names(self.rects),1)]
            old_selected=self.selected
            names=capture_names(self.rects)
            self.rects=dict(ordered+[(n,self.rects.get(n)) for n in ("NEXT","PROGRESS")])
            if old_selected in names:
                self.selected=f"REGION_{names.index(old_selected)+1:03d}"

    def add_region(self):
        self.modernize()
        index=1
        while f"REGION_{index:03d}" in self.rects:
            index+=1
        name=f"REGION_{index:03d}"
        self.rects={**{n:r for n,r in self.rects.items() if n not in ("NEXT","PROGRESS")},name:None,
                    "NEXT":self.rects.get("NEXT"),"PROGRESS":self.rects.get("PROGRESS")}
        self.refresh_selector()
        self.select(name)
        self.draw_new()

    def reorder(self,direction):
        if self.selected not in capture_names(self.rects):
            return
        names=capture_names(self.rects)
        index=names.index(self.selected)
        destination=index+direction
        if 0<=destination<len(names):
            names[index],names[destination]=names[destination],names[index]
            self.rects={name:self.rects[name] for name in names+["NEXT","PROGRESS"]}
            self.refresh_selector()
            self.select(self.selected)

    def draw_new(self):
        self.mode = "draw"
        self.render()

    def delete(self):
        if self.selected in capture_names(self.rects):
            self.modernize()
            del self.rects[self.selected]
            self.refresh_selector()
            self.select(capture_names(self.rects)[0] if capture_names(self.rects) else "NEXT")
            return
        self.rects[self.selected] = None
        if self.selected == "NEXT":
            self.point = None
        self.render()

    def set_point(self):
        self.selected, self.mode = "NEXT", "point"
        self.render()

    def paper_changed(self,event=None):
        try:
            ratio = paper_ratio(self.paper.get(),self.orientation.get())
            for name in capture_names(self.rects):
                if self.rects[name] is not None:
                    self.rects[name] = fit_aspect(self.rects[name],ratio,self.bounds)
            self.render()
        except CalibrationError as error:
            messagebox.showerror("Papierformat",str(error),parent=self.window)

    def copy_right(self):
        rect = self.rects["LEFT"]
        if rect:
            x,y,w,h = rect
            if x + 2*w <= self.bounds[2]:
                self.rects["RIGHT"] = [x+w,y,w,h]
                self.select("RIGHT")
            else:
                messagebox.showwarning("RIGHT","Rechts ist nicht genug Platz. RIGHT manuell aufziehen.",parent=self.window)

    def render(self):
        if not self.canvas.winfo_exists():
            return
        width,height = max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        self.transform = canvas_transform(self.image.size,(width,height))
        s,ox,oy = self.transform
        self.photo = ImageTk.PhotoImage(self.image.resize((max(1,round(self.image.width*s)),max(1,round(self.image.height*s)))),master=self.window)
        self.canvas.delete("all")
        self.canvas.create_image(ox,oy,image=self.photo,anchor="nw")
        self.canvas.create_rectangle(ox+self.bounds[0]*s,oy+self.bounds[1]*s,ox+self.bounds[2]*s,oy+self.bounds[3]*s,outline="white",dash=(4,4))
        for name,rect in self.rects.items():
            if rect is None:
                continue
            x,y,w,h = rect
            l,t,r,b = ox+x*s,oy+y*s,ox+(x+w)*s,oy+(y+h)*s
            color = COLORS.get(name,["#ff5252","#4ca6ff","#e6a646","#c487ff"][capture_names(self.rects).index(name)%4] if name in capture_names(self.rects) else "white")
            self.canvas.create_rectangle(l,t,r,b,outline=color,width=3 if name==self.selected else 2)
            label=f"{self.display_name(name)} [{x},{y},{w},{h}]"
            self.canvas.create_rectangle(l,t,l+max(160,len(label)*8),t+23,fill="#111111",outline=color)
            self.canvas.create_text(l+5,t+3,text=label,fill=color,anchor="nw")
            if name == self.selected:
                for px,py in self.handles(rect).values():
                    cx,cy=ox+px*s,oy+py*s
                    self.canvas.create_rectangle(cx-4,cy-4,cx+4,cy+4,fill=color,outline="#111")
        if self.point:
            x,y=ox+self.point[0]*s,oy+self.point[1]*s
            self.canvas.create_line(x-9,y,x+9,y,fill=COLORS["NEXT"],width=2)
            self.canvas.create_line(x,y-9,x,y+9,fill=COLORS["NEXT"],width=2)
        self.status.set(f"{self.display_name(self.selected)}: ziehen/8 Griffe | {self.paper.get()} | ESC = Abbrechen")

    @staticmethod
    def handles(rect):
        x,y,w,h=rect
        return {"nw":(x,y),"n":(x+w/2,y),"ne":(x+w,y),"e":(x+w,y+h/2),
                "se":(x+w,y+h),"s":(x+w/2,y+h),"sw":(x,y+h),"w":(x,y+h/2)}

    def press(self,event):
        p=to_screen((event.x,event.y),self.transform)
        if not self.bounds[0] <= p[0] < self.bounds[2] or not self.bounds[1] <= p[1] < self.bounds[3]:
            return
        rect=self.rects[self.selected]
        if self.mode == "point":
            if rect and contains(rect,p):
                self.point=p
                self.mode="edit"
                self.render()
            return
        handle=None
        if rect and self.mode != "draw":
            radius=8/self.transform[0]
            handle=next((name for name,pos in self.handles(rect).items() if abs(p[0]-pos[0])<=radius and abs(p[1]-pos[1])<=radius),None)
        kind=handle or ("move" if rect and contains(rect,p) and self.mode!="draw" else "draw")
        self.drag=(p,copy.deepcopy(rect),kind,copy.deepcopy(self.point))
        self.mode="edit"
        if kind=="draw":
            self.rects[self.selected]=new_rect(p,p,self.bounds)
        self.render()

    def motion(self,event):
        if not self.drag:
            return
        start,old,kind,old_point=self.drag
        p=to_screen((event.x,event.y),self.transform)
        dx,dy=p[0]-start[0],p[1]-start[1]
        ratio=paper_ratio(self.paper.get(),self.orientation.get()) if self.selected in capture_names(self.rects) else None
        rect=new_rect(start,p,self.bounds) if kind=="draw" else move_rect(old,dx,dy,self.bounds) if kind=="move" else resize_aspect(old,kind,dx,dy,self.bounds,ratio)
        if self.selected in capture_names(self.rects) and kind=="draw":
            rect=fit_aspect(rect,paper_ratio(self.paper.get(),self.orientation.get()),self.bounds)
        self.rects[self.selected]=rect
        if self.selected == "NEXT":
            shifted=[old_point[0]+rect[0]-old[0],old_point[1]+rect[1]-old[1]] if kind=="move" and old_point and old else None
            self.point=shifted if shifted and contains(rect,shifted) else center(rect)
        self.render()

    def accept(self):
        try:
            mode=self.navigation.get() if hasattr(self,"navigation") else "next_button"
            warn=validate_selection(self.rects,self.point,self.bounds,mode)
            if warn and not messagebox.askyesno("Ueberlappung","Aufnahmebereiche ueberlappen stark. Diese Auswahl ausdruecklich bestaetigen?",parent=self.window):
                return
            if not messagebox.askyesno("Auswahl bestaetigen",f"{self.paper.get()} / {self.orientation.get()}: alle Rechtecke und Klickpunkt kontrolliert?",parent=self.window):
                return
            self.result={"action":"save","rects":copy.deepcopy(self.rects),"point":list(self.point) if self.point else None,"paper":self.paper.get(),"orientation":self.orientation.get(),"navigation":mode}
            self.window.destroy()
        except CalibrationError as error:
            messagebox.showerror("Auswahl pruefen",str(error),parent=self.window)

    def cancel(self):
        self.result={"action":"cancel"}
        self.window.destroy()

    def recalibrate(self):
        self.result={"action":"recalibrate"}
        self.window.destroy()

    def show(self):
        self.root.wait_window(self.window)
        return self.result or {"action":"cancel"}
