"""Paper choice from saved images; never clicks or recaptures the browser."""
import copy
import hashlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import uuid

from PIL import Image, ImageTk
from .geometry import PAPER_MM
from .regions import image_names


def preview_images(folder,manifest):
    pair=manifest["pairs"][0]
    names=image_names(manifest["config"],1)
    if pair["index"]!=1 or len(pair["images"])!=len(names):
        raise ValueError("Ungueltiger erster Aufnahme-Datensatz.")
    result=[]
    for expected,entry in zip(names,pair["images"]):
        if entry["file"]!=expected:
            raise ValueError("Ungueltige Bildnamen/Reihenfolge.")
        path=Path(folder)/expected
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry["sha256"]:
            raise ValueError("Zwischenbild wurde veraendert.")
        with Image.open(path) as im:
            result.append(im.convert("RGB"))
    return result


def paper_preview(images,paper,orientation,layout):
    group=images if layout=="spread" else images[:1]
    w,h=sum(im.width for im in group),max(im.height for im in group)
    pw,ph=PAPER_MM[paper] if paper!="Original" else (w,h)
    if paper!="Original" and orientation=="landscape":
        pw,ph=ph,pw
    factor=min(600/pw,440/ph)
    page=Image.new("RGB",(max(1,round(pw*factor)),max(1,round(ph*factor))),"white")
    scale=min(page.width/w,page.height/h)
    x,y=(page.width-w*scale)/2,(page.height-h*scale)/2
    for im in group:
        thumb=im.resize((max(1,round(im.width*scale)),max(1,round(im.height*scale))),Image.Resampling.LANCZOS)
        page.paste(thumb,(round(x),round(y)))
        x+=im.width*scale
    return page


def export_dialog(folder,manifest,builder):
    if not manifest["pairs"]:
        raise ValueError("Keine gespeicherten Aufnahmen vorhanden.")
    images=preview_images(folder,manifest)
    root=tk.Tk()
    root.title("RectoFlow: PDF-Format am Ende")
    root.geometry("760x680")
    cfg=manifest["config"]
    paper=tk.StringVar(value=cfg.get("paper_format","A4"))
    direction=tk.StringVar(value="Querformat" if cfg.get("paper_orientation")=="landscape" else "Hochformat")
    layout=tk.StringVar(value="Nebeneinander" if cfg.get("pdf_layout")=="spread" else "Eine Seite je Bereich")
    top=ttk.Frame(root,padding=12)
    top.pack(fill="x")
    ttk.Label(top,text="Gespeicherte Bilder als PDF ausgeben. Die Aufnahmebereiche bleiben erhalten.",wraplength=700).pack(anchor="w")
    row=ttk.Frame(top)
    row.pack(fill="x",pady=10)
    for variable,values,width in ((paper,["A4","A5","A3","A6","A2","A1","A0","Letter","Legal","Original"],10),
                                   (direction,["Hochformat","Querformat"],14),(layout,["Eine Seite je Bereich","Nebeneinander"],22)):
        box=ttk.Combobox(row,textvariable=variable,values=values,state="readonly",width=width)
        box.pack(side="left",padx=5)
        box.bind("<<ComboboxSelected>>",lambda e:render())
    canvas=ttk.Label(root,anchor="center")
    canvas.pack(fill="both",expand=True,pady=10)
    info=ttk.Label(root,text="Vorschau: erste Ansicht / erste PDF-Seite. Alle Ansichten werden in Reihenfolge exportiert.",wraplength=720)
    info.pack(pady=5)
    result=None
    def options():
        return {"paper_format":paper.get(),"paper_orientation":"landscape" if direction.get()=="Querformat" else "portrait",
                "pdf_layout":"spread" if layout.get()=="Nebeneinander" else "separate"}
    def render():
        values=options()
        canvas.photo=ImageTk.PhotoImage(paper_preview(images,values["paper_format"],values["paper_orientation"],values["pdf_layout"]),master=root)
        canvas.configure(image=canvas.photo)
    def save():
        nonlocal result
        values=options()
        if not messagebox.askyesno("PDF bestaetigen",f"{paper.get()}, {direction.get()}, {layout.get()}: PDF jetzt erstellen?",parent=root):
            return
        try:
            candidate=copy.deepcopy(manifest)
            candidate["config"].update(values)
            prefix="gesamt" if manifest["status"]=="COMPLETE" else "gesamt_TEILSTAND"
            path=Path(folder)/f"{prefix}_{uuid.uuid4().hex[:8]}.pdf"
            if not builder(folder,candidate,path):
                raise ValueError("Keine Aufnahmen fuer PDF vorhanden.")
            result={"file":path.name,"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"options":values}
            root.destroy()
        except Exception as error:
            messagebox.showerror("PDF-Export fehlgeschlagen",str(error),parent=root)
    footer=ttk.Frame(root,padding=12)
    footer.pack(fill="x")
    ttk.Button(footer,text="PDF bestaetigen und erstellen",command=save).pack(side="right",padx=5)
    ttk.Button(footer,text="Spaeter / Abbrechen",command=root.destroy).pack(side="right",padx=5)
    root.bind("<Escape>",lambda e:root.destroy())
    render()
    try:
        root.mainloop()
    finally:
        try:root.destroy()
        except tk.TclError:pass
    return result
