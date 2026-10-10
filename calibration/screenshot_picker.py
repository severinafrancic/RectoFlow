"""Lokaler Screenshot-Picker. Das Bild bleibt im RAM; Canvas ist nur Anzeige."""
import copy
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import ImageTk

from .geometry import (CalibrationError, center, contains, canvas_transform,
                       to_screen, move_rect, resize_rect, new_rect, fit_aspect,
                       paper_ratio, validate_selection,resize_aspect,align_rect)
from .geometry import magnifier_pixels, magnifier_position, adjacent_rect
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
        self.locked = set()
        self.active_handle = None
        self.magnifier_point = None
        self.undo_stack=[]
        self.redo_stack=[]
        self.drag_before=None
        self.next_region_id=1
        self.window = tk.Toplevel(root)
        self.window.title("RectoFlow: Kontrollvorschau" if final else "RectoFlow: Bereiche auswaehlen")
        self.window.geometry(f"{image.width}x{image.height}+0+0")
        self.window.state("zoomed")
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Escape>", lambda e:self.cancel())
        self.window.bind("<Delete>", lambda e:self.editor_shortcut(e,self.delete))
        self.window.bind("<Return>", lambda e:self.editor_shortcut(e,self.accept))
        for key in ("Left", "Right", "Up", "Down"):
            self.window.bind("<"+key+">",self.key_move)
            self.window.bind("<Shift-"+key+">",self.key_move)
        self.window.bind("<Control-z>",lambda e:self.history_key(e,False))
        self.window.bind("<Control-y>",lambda e:self.history_key(e,True))
        self.window.bind("<Control-Shift-Z>",lambda e:self.history_key(e,True))
        toolbar = ttk.Frame(self.window, padding=6)
        toolbar.pack(fill="x")
        self.selected_var=tk.StringVar(value=self.display_name(self.selected))
        self.selector=ttk.Combobox(toolbar,textvariable=self.selected_var,values=[self.display_name(n) for n in self.rects],width=16,state="readonly")
        self.selector.pack(side="left",padx=3)
        self.selector.bind("<<ComboboxSelected>>",lambda e:self.select(list(self.rects)[self.selector.current()]))
        ttk.Button(toolbar,text="+ Bereich",command=self.add_region).pack(side="left",padx=2)
        ttk.Button(toolbar,text="↑",command=lambda:self.reorder(-1)).pack(side="left",padx=2)
        ttk.Button(toolbar,text="↓",command=lambda:self.reorder(1)).pack(side="left",padx=2)
        ttk.Button(toolbar,text="Neu aufziehen",command=self.draw_new).pack(side="left",padx=3)
        ttk.Button(toolbar,text="Loeschen",command=self.delete).pack(side="left",padx=3)
        ttk.Button(toolbar,text="Klickpunkt setzen",command=self.set_point).pack(side="left",padx=3)
        self.lock_var=tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar,text="Groesse fixieren",variable=self.lock_var,command=self.toggle_lock).pack(side="left",padx=3)
        formatbar=ttk.Frame(self.window,padding=6)
        formatbar.pack(fill="x")
        ttk.Label(formatbar,text="Optionales Seitenverhaeltnis:").pack(side="left")
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
        ttk.Button(formatbar,text="Ausgewaehlten Bereich anpassen",command=self.fit_selected).pack(side="left",padx=4)
        self.navigation=tk.StringVar(value=navigation_mode)
        ttk.Label(formatbar,text="Navigation:").pack(side="left",padx=5)
        labels={"next_button":"Weiter-Button","manual":"Manuell","none":"Einmal"}
        nav_label=tk.StringVar(value=labels[navigation_mode])
        nav=ttk.Combobox(formatbar,textvariable=nav_label,values=list(labels.values()),width=14,state="readonly")
        nav.pack(side="left")
        nav.bind("<<ComboboxSelected>>",lambda e:self.navigation.set(next(k for k,v in labels.items() if v==nav_label.get())))
        geometrybar=ttk.Frame(self.window,padding=6);geometrybar.pack(fill="x")
        ttk.Button(geometrybar,text="Duplizieren",command=self.duplicate_region).pack(side="left",padx=2)
        ttk.Label(geometrybar,text="Referenz:").pack(side="left")
        self.reference=ttk.Combobox(geometrybar,values=[self.display_name(n) for n in capture_names(self.rects)],state="readonly",width=12)
        self.reference.pack(side="left");self.reference.current(0)
        ttk.Label(geometrybar,text="Abstand px:").pack(side="left")
        self.gap=tk.StringVar(value="0");ttk.Entry(geometrybar,textvariable=self.gap,width=5).pack(side="left")
        for label,op in (("Links","left"),("Oben","top"),("Gleiche Groesse","size"),("Direkt rechts","right")):
            ttk.Button(geometrybar,text=label,command=lambda o=op:self.align_selected(o)).pack(side="left",padx=2)
        adjacentbar=ttk.Frame(self.window,padding=6);adjacentbar.pack(fill="x")
        for label,direction in (("+ Links","left"),("+ Rechts","right"),("+ Oben","up"),("+ Unten","down")):
            ttk.Button(adjacentbar,text=label,command=lambda d=direction:self.add_adjacent(d)).pack(side="left",padx=3)
        ttk.Button(adjacentbar,text="Rueckgaengig",command=self.undo).pack(side="left",padx=3)
        ttk.Button(adjacentbar,text="Wiederholen",command=self.redo).pack(side="left",padx=3)
        footer = ttk.Frame(self.window,padding=6)
        footer.pack(side="bottom",fill="x")
        ttk.Button(footer,text=save_label or ("Bestaetigt speichern" if final else "Live-Vorschau"),command=self.accept).pack(side="right",padx=3)
        ttk.Button(footer,text="Abbrechen",command=self.cancel).pack(side="right",padx=3)
        if final:
            ttk.Button(footer,text="Neu kalibrieren",command=self.recalibrate).pack(side="right",padx=3)
        self.status = tk.StringVar()
        ttk.Label(footer,textvariable=self.status).pack(side="left")
        workspace=ttk.Frame(self.window);workspace.pack(fill="both",expand=True)
        self.region_list=tk.Listbox(workspace,width=24,exportselection=False)
        self.region_list.pack(side="left",fill="y")
        self.region_list.bind("<<ListboxSelect>>",self.list_selected)
        self.canvas = tk.Canvas(workspace,background="#23262c",highlightthickness=0)
        self.canvas.pack(side="left",fill="both",expand=True)
        self.canvas.bind("<Configure>",lambda e:self.render())
        self.canvas.bind("<ButtonPress-1>",self.press)
        self.canvas.bind("<B1-Motion>",self.motion)
        self.canvas.bind("<ButtonRelease-1>",self.release)
        self.transform = (1,0,0)
        self.photo = None
        self.refresh_selector()
        self.paper_changed()
        self.window.update_idletasks()
        self.window.focus_force()

    def select(self,name):
        self.selected, self.mode = name, "edit"
        self.active_handle = None
        self.magnifier_point = None
        if hasattr(self,"lock_var"):
            self.lock_var.set(name in self.locked)
        if hasattr(self,"selected_var"):
            self.selected_var.set(self.display_name(name))
        if hasattr(self,"region_list"):
            self.region_list.selection_clear(0,"end")
            self.region_list.selection_set(list(self.rects).index(name))
            self.region_list.see(list(self.rects).index(name))
        self.render()

    def list_selected(self,event):
        selected=self.region_list.curselection()
        if selected:self.select(list(self.rects)[selected[0]])

    def refresh_selector(self):
        if hasattr(self,"region_list"):
            self.region_list.delete(0,"end")
            names=capture_names(self.rects)
            for name in self.rects:
                label=f"{names.index(name)+1}. Bereich" if name in names else self.display_name(name)
                self.region_list.insert("end",label+(" [fixiert]" if name in self.locked else ""))
            if self.selected in self.rects:
                self.region_list.selection_set(list(self.rects).index(self.selected))
        if hasattr(self,"selector"):
            self.selector.configure(values=[self.display_name(n) for n in self.rects])
        if hasattr(self,"reference"):
            names=capture_names(self.rects)
            self.reference.configure(values=[self.display_name(n) for n in names])
            if names:self.reference.current(0)

    def display_name(self,name):
        if name=="NEXT":return "Weiter-Button"
        if name=="PROGRESS":return "Fortschritt"
        return f"Bereich {capture_names(self.rects).index(name)+1}"

    def modernize(self):
        if "LEFT" in self.rects or "RIGHT" in self.rects:
            ordered=[(f"REGION_{i:03d}",self.rects[name]) for i,name in enumerate(capture_names(self.rects),1)]
            old_selected=self.selected
            names=capture_names(self.rects)
            self.locked={f"REGION_{names.index(n)+1:03d}" if n in names else n for n in getattr(self,"locked",set())}
            self.rects=dict(ordered+[(n,self.rects.get(n)) for n in ("NEXT","PROGRESS")])
            if old_selected in names:
                self.selected=f"REGION_{names.index(old_selected)+1:03d}"

    def add_region(self):
        before=self.snapshot()
        self.modernize()
        name=self.new_id()
        self.rects={**{n:r for n,r in self.rects.items() if n not in ("NEXT","PROGRESS")},name:None,
                    "NEXT":self.rects.get("NEXT"),"PROGRESS":self.rects.get("PROGRESS")}
        self.refresh_selector()
        self.select(name)
        self.draw_new()
        self.remember(before)

    def new_id(self):
        index=getattr(self,"next_region_id",1)
        while f"REGION_{index:03d}" in self.rects:index+=1
        self.next_region_id=index+1
        return f"REGION_{index:03d}"

    def reorder(self,direction):
        if self.selected not in capture_names(self.rects):
            return
        names=capture_names(self.rects)
        index=names.index(self.selected)
        destination=index+direction
        if 0<=destination<len(names):
            before=self.snapshot()
            names[index],names[destination]=names[destination],names[index]
            self.rects={name:self.rects[name] for name in names+["NEXT","PROGRESS"]}
            self.refresh_selector()
            self.select(self.selected)
            self.remember(before)

    def draw_new(self):
        if self.is_locked():
            return
        self.mode = "draw"
        self.render()

    def delete(self):
        before=self.snapshot()
        if self.selected in capture_names(self.rects):
            if len(capture_names(self.rects))==1:
                messagebox.showwarning("Bereich behalten","Mindestens ein Aufnahmebereich muss erhalten bleiben.",parent=self.window)
                return
            self.modernize()
            self.locked.discard(self.selected)
            del self.rects[self.selected]
            self.refresh_selector()
            self.select(capture_names(self.rects)[0] if capture_names(self.rects) else "NEXT")
            self.remember(before)
            return
        self.rects[self.selected] = None
        if self.selected == "NEXT":
            self.point = None
        self.render()
        self.remember(before)

    def set_point(self):
        self.selected, self.mode = "NEXT", "point"
        self.render()

    def paper_changed(self,event=None):
        self.render()

    def fit_selected(self):
        if self.is_locked():
            return
        try:
            ratio = paper_ratio(self.paper.get(),self.orientation.get())
            if self.selected not in capture_names(self.rects) or self.rects[self.selected] is None:
                return
            proposed = fit_aspect(self.rects[self.selected],ratio,self.bounds)
            if messagebox.askyesno("Bereich anpassen",f"{self.rects[self.selected]} → {proposed}\nDiese Geometrie uebernehmen?",parent=self.window):
                before=self.snapshot()
                self.rects[self.selected] = proposed
                self.remember(before)
            self.render()
        except CalibrationError as error:
            messagebox.showerror("Papierformat",str(error),parent=self.window)

    def duplicate_region(self):
        if self.selected not in capture_names(self.rects) or self.rects[self.selected] is None:return
        for direction in ("right","down","left","up"):
            try:
                proposed=adjacent_rect(self.rects[self.selected],direction,self.bounds)
            except CalibrationError:
                continue
            if proposed not in [self.rects[n] for n in capture_names(self.rects)]:
                self.insert_region(proposed)
                return
        messagebox.showwarning("Duplizieren","Kein Platz fuer eine versetzte Kopie gleicher Groesse. Auswahl unveraendert.",parent=self.window)

    def add_adjacent(self,direction):
        if self.selected not in capture_names(self.rects) or self.rects[self.selected] is None:return
        try:
            proposed=adjacent_rect(self.rects[self.selected],direction,self.bounds,int(self.gap.get()))
            if proposed in [self.rects[n] for n in capture_names(self.rects)]:
                raise CalibrationError("INVALID_RECTANGLE","An dieser Position existiert bereits ein Bereich.")
            self.insert_region(proposed)
        except (ValueError,CalibrationError) as error:
            messagebox.showwarning("Nachbarbereich unveraendert",str(error),parent=self.window)

    def insert_region(self,rect):
        before=self.snapshot()
        self.modernize()
        names=capture_names(self.rects)
        name=self.new_id()
        names.insert(names.index(self.selected)+1,name)
        self.rects[name]=list(rect)
        # Ordered mapping is the adapter to the persisted ordered rectangle list.
        self.rects={n:self.rects[n] for n in names+["NEXT","PROGRESS"]}
        self.refresh_selector();self.select(name)
        self.remember(before)

    def align_selected(self,operation):
        if operation=="size" and self.is_locked():
            return
        try:
            names=capture_names(self.rects)
            if self.selected not in names or self.rects[self.selected] is None:return
            index=self.reference.current()
            if not 0<=index<len(names) or self.rects[names[index]] is None:return
            proposed=align_rect(self.rects[self.selected],self.rects[names[index]],operation,self.bounds,int(self.gap.get()))
            before=self.snapshot()
            self.rects[self.selected]=proposed;self.render()
            self.remember(before)
        except (ValueError,CalibrationError) as error:
            messagebox.showwarning("Geometrie unveraendert",str(error),parent=self.window)

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
            label=f"{self.display_name(name)} [{x},{y},{w},{h}]"+(" FIXIERT" if name in getattr(self,"locked",set()) else "")
            self.canvas.create_rectangle(l,t,l+max(160,len(label)*8),t+23,fill="#111111",outline=color)
            self.canvas.create_text(l+5,t+3,text=label,fill=color,anchor="nw")
            if name == self.selected and not self.is_locked():
                for handle,(px,py) in self.handles(rect).items():
                    cx,cy=ox+px*s,oy+py*s
                    self.canvas.create_rectangle(cx-4,cy-4,cx+4,cy+4,fill="white" if handle==self.active_handle else color,outline="#111")
        if self.point:
            x,y=ox+self.point[0]*s,oy+self.point[1]*s
            self.canvas.create_line(x-9,y,x+9,y,fill=COLORS["NEXT"],width=2)
            self.canvas.create_line(x,y-9,x,y+9,fill=COLORS["NEXT"],width=2)
        self.render_magnifier(width,height)
        mode="Groesse fixiert: nur verschieben" if self.is_locked() else "ziehen/8 Griffe"
        self.status.set(f"{self.display_name(self.selected)}: {mode} | Pfeil 1 px / Shift 10 px | ESC = Abbrechen")

    def is_locked(self):
        return self.selected in getattr(self,"locked",set())

    def toggle_lock(self):
        if self.rects.get(self.selected) is None:
            self.lock_var.set(False)
            return
        before=self.snapshot()
        if self.lock_var.get():
            self.locked.add(self.selected)
        else:
            self.locked.discard(self.selected)
        self.active_handle=None
        self.magnifier_point=None
        self.mode="edit"
        self.refresh_selector()
        self.render()
        self.remember(before)

    def render_magnifier(self,width,height):
        if self.magnifier_point is None:
            return
        s,ox,oy=self.transform
        x,y=self.magnifier_point
        position=magnifier_position((ox+x*s,oy+y*s),(width,height))
        if position is None:
            return
        left,top=position
        pixels,crosshair=magnifier_pixels(self.image,(x,y))
        self.loupe_photo=ImageTk.PhotoImage(pixels,master=self.window)
        self.canvas.create_rectangle(left,top,left+184,top+210,fill="#111",outline="white",width=2)
        self.canvas.create_image(left+8,top+8,image=self.loupe_photo,anchor="nw")
        cx,cy=left+8+crosshair[0],top+8+crosshair[1]
        for color,thickness in (("black",3),("white",1)):
            self.canvas.create_line(cx-14,cy,cx+14,cy,fill=color,width=thickness)
            self.canvas.create_line(cx,cy-14,cx,cy+14,fill=color,width=thickness)
        text=f"8x | X {round(x)} Y {round(y)}\n{self.active_handle or 'Neue Ecke'}"
        self.canvas.create_text(left+8,top+178,text=text,fill="white",anchor="nw")

    def key_move(self,event):
        if isinstance(event.widget,(tk.Entry,ttk.Entry,ttk.Combobox,tk.Text,tk.Spinbox,ttk.Spinbox)):
            return
        old=self.rects.get(self.selected)
        if old is None:
            return
        before=self.snapshot()
        step=10 if event.state & 1 else 1
        dx,dy={"Left":(-step,0),"Right":(step,0),"Up":(0,-step),"Down":(0,step)}[event.keysym]
        handle=getattr(self,"active_handle",None) if not self.is_locked() else None
        self.rects[self.selected]=resize_rect(old,handle,dx,dy,self.bounds) if handle else move_rect(old,dx,dy,self.bounds)
        rect=self.rects[self.selected]
        if self.selected=="NEXT":
            if not handle and self.point:
                self.point=[self.point[0]+rect[0]-old[0],self.point[1]+rect[1]-old[1]]
            if not self.point or not contains(rect,self.point):self.point=center(rect)
        self.magnifier_point=self.handles(rect)[handle] if handle else None
        self.render()
        self.remember(before)
        return "break"

    def release(self,event):
        self.drag=None
        if getattr(self,"drag_before",None) is not None:
            self.remember(self.drag_before)
            self.drag_before=None
        if self.active_handle is None:self.magnifier_point=None
        self.render()

    def snapshot(self):
        return copy.deepcopy((list(self.rects.items()),getattr(self,"point",None),self.selected,getattr(self,"locked",set())))

    def remember(self,before):
        if before==self.snapshot():return
        if not hasattr(self,"undo_stack"):self.undo_stack=[];self.redo_stack=[]
        self.undo_stack.append(before)
        self.undo_stack=self.undo_stack[-100:]
        self.redo_stack.clear()

    def restore_state(self,state):
        items,self.point,self.selected,self.locked=copy.deepcopy(state)
        self.rects=dict(items)
        self.drag=None;self.drag_before=None;self.active_handle=None;self.magnifier_point=None
        self.refresh_selector();self.select(self.selected)

    def undo(self):
        if self.drag:return
        if getattr(self,"undo_stack",[]):
            self.redo_stack.append(self.snapshot());self.restore_state(self.undo_stack.pop())

    def redo(self):
        if self.drag:return
        if getattr(self,"redo_stack",[]):
            self.undo_stack.append(self.snapshot());self.restore_state(self.redo_stack.pop())

    def history_key(self,event,redo):
        if isinstance(event.widget,(tk.Entry,ttk.Entry,ttk.Combobox,tk.Text,tk.Spinbox,ttk.Spinbox)):return
        self.redo() if redo else self.undo()
        return "break"

    @staticmethod
    def editor_shortcut(event,action):
        if isinstance(event.widget,(tk.Entry,ttk.Entry,ttk.Combobox,tk.Text,tk.Spinbox,ttk.Spinbox)):return
        action()
        return "break"

    @staticmethod
    def handles(rect):
        x,y,w,h=rect
        return {"nw":(x,y),"n":(x+w/2,y),"ne":(x+w,y),"e":(x+w,y+h/2),
                "se":(x+w,y+h),"s":(x+w/2,y+h),"sw":(x,y+h),"w":(x,y+h/2)}

    def press(self,event):
        if hasattr(self,"canvas"):self.canvas.focus_set()
        p=to_screen((event.x,event.y),self.transform)
        if not self.bounds[0] <= p[0] < self.bounds[2] or not self.bounds[1] <= p[1] < self.bounds[3]:
            return
        rect=self.rects[self.selected]
        if self.mode == "point":
            if rect and contains(rect,p):
                before=self.snapshot()
                self.point=p
                self.mode="edit"
                self.render()
                self.remember(before)
            return
        handle=None
        if rect and self.mode != "draw" and not self.is_locked():
            radius=8/self.transform[0]
            handle=next((name for name,pos in self.handles(rect).items() if abs(p[0]-pos[0])<=radius and abs(p[1]-pos[1])<=radius),None)
        if not handle and self.mode!="draw":
            hits=[n for n,r in self.rects.items() if r and contains(r,p)]
            if hits and self.selected not in hits:
                self.select(hits[-1]);rect=self.rects[self.selected]
        kind=handle or ("move" if rect and contains(rect,p) and self.mode!="draw" else "draw")
        if self.is_locked() and kind=="draw":
            return
        self.drag_before=self.snapshot()
        self.active_handle=handle
        self.magnifier_point=p if kind=="draw" else self.handles(rect)[handle] if handle else None
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
        rect=new_rect(start,p,self.bounds) if kind=="draw" else move_rect(old,dx,dy,self.bounds) if kind=="move" else resize_rect(old,kind,dx,dy,self.bounds)
        self.rects[self.selected]=rect
        self.magnifier_point=p if kind=="draw" else self.handles(rect)[kind] if kind!="move" else None
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
