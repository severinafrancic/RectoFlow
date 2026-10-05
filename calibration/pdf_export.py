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
    from .exports import view_images
    return view_images(folder,manifest,1)


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
    from .exports import source_snapshot,view_images,analyze_view,create_plan,execute_plan
    manifest,source_hash=source_snapshot(folder)
    if not manifest["pairs"]:
        raise ValueError("Keine gespeicherten Aufnahmen vorhanden.")
    root=tk.Tk()
    root.title("RectoFlow: Aufnahmen pruefen und PDF erstellen")
    root.geometry("1000x780")
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
    content=ttk.Frame(root);content.pack(fill="both",expand=True)
    listing=ttk.Treeview(content,columns=("include","view","warnings"),show="headings",selectmode="browse",height=14)
    for name,label,width in (("include","Export",55),("view","Ansicht",70),("warnings","Kontrolle",225)):
        listing.heading(name,text=label);listing.column(name,width=width)
    listing.pack(side="left",fill="y",padx=10)
    scrollbar=ttk.Scrollbar(content,orient="vertical",command=listing.yview);scrollbar.pack(side="left",fill="y")
    listing.configure(yscrollcommand=scrollbar.set)
    ordered=list(range(1,len(manifest["pairs"])+1));included=set(ordered);warnings={}
    images=[]
    def refresh():
        selected=listing.selection()
        listing.delete(*listing.get_children())
        for index in ordered:listing.insert("","end",iid=str(index),values=("Ja" if index in included else "Nein",index,warnings.get(index,"Noch nicht geprueft")))
        if selected and listing.exists(selected[0]):listing.selection_set(selected[0])
    canvas=ttk.Label(content,anchor="center");canvas.pack(side="left",fill="both",expand=True,pady=10)
    info=ttk.Label(root,text="Ansichten auswaehlen, ausschliessen und umordnen. Warnungen entfernen nichts automatisch.",wraplength=920)
    info.pack(pady=5)
    result=None
    def options():
        return {"paper_format":paper.get(),"paper_orientation":"landscape" if direction.get()=="Querformat" else "portrait",
                "pdf_layout":"spread" if layout.get()=="Nebeneinander" else "separate"}
    def render():
        if not images:
            canvas.configure(image="");return
        values=options()
        canvas.photo=ImageTk.PhotoImage(paper_preview(images,values["paper_format"],values["paper_orientation"],values["pdf_layout"]),master=root)
        canvas.configure(image=canvas.photo)
    def selected_index():
        return int(listing.selection()[0]) if listing.selection() else None
    def select(event=None):
        nonlocal images
        index=selected_index()
        if index is None:return
        try:
            images=view_images(folder,manifest,index)
            analysis=analyze_view(folder,manifest,index)
            warnings[index]="; ".join(analysis["warnings"]) or "Geprueft"
            info.configure(text=f"Vorschau Ansicht {index}, erste PDF-Seite. "+warnings[index])
        except Exception as error:
            images=[];warnings[index]="FEHLER: "+str(error)
            info.configure(text=f"Ansicht {index} ungueltig. Fuer Export ausdruecklich ausschliessen.")
        listing.item(str(index),values=("Ja" if index in included else "Nein",index,warnings[index]))
        render()
    def toggle():
        index=selected_index()
        if index is None:return
        if index in included:included.remove(index)
        else:included.add(index)
        refresh()
    def reorder(delta):
        index=selected_index()
        if index is None:return
        position=ordered.index(index);dest=position+delta
        if 0<=dest<len(ordered):ordered[position],ordered[dest]=ordered[dest],ordered[position];refresh()
    listing.bind("<<TreeviewSelect>>",select)
    controls=ttk.Frame(root,padding=8);controls.pack(fill="x")
    for label,command in (("Ein-/Ausschliessen",toggle),("Frueher",lambda:reorder(-1)),("Spaeter",lambda:reorder(1))):
        ttk.Button(controls,text=label,command=command).pack(side="left",padx=4)
    def save():
        nonlocal result
        values=options()
        if not messagebox.askyesno("PDF bestaetigen",f"{paper.get()}, {direction.get()}, {layout.get()}: PDF jetzt erstellen?",parent=root):
            return
        try:
            selected=[index for index in ordered if index in included]
            plan=create_plan(folder,selected,values,expected_manifest_hash=source_hash)
            path=execute_plan(folder,plan)
            result={"file":path.relative_to(folder).as_posix(),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"options":values}
            root.destroy()
        except Exception as error:
            messagebox.showerror("PDF-Export fehlgeschlagen",str(error),parent=root)
    footer=ttk.Frame(root,padding=12)
    footer.pack(fill="x")
    ttk.Button(footer,text="PDF bestaetigen und erstellen",command=save).pack(side="right",padx=5)
    ttk.Button(footer,text="Spaeter / Abbrechen",command=root.destroy).pack(side="right",padx=5)
    root.bind("<Escape>",lambda e:root.destroy())
    refresh();listing.selection_set(str(ordered[0]));select()
    try:
        root.mainloop()
    finally:
        try:root.destroy()
        except tk.TclError:pass
    return result
