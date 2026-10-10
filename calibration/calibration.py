"""Wizard: gewaehltes Edge -> optional DOM -> eingefrorene Pixel -> Livekontrolle."""
import copy
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from pathlib import Path
import uuid

from .geometry import CalibrationError, right_rect, center, validate_rect, assert_same_selection
from .config_io import updated_config, atomic_update
from .dom_picker import DOMSession, suggestions, marker_bounds
from .screenshot_picker import RectanglePicker
from .regions import selection, capture_names, navigation
from .diagnostics import phase, failure


def initial_rects(cfg,bounds):
    rects=selection(cfg)
    result={}
    for name,rect in rects.items():
        try:
            if rect is not None:
                validate_rect(rect,bounds)
            result[name]=copy.deepcopy(rect)
        except CalibrationError:
            result[name]=None
    return result


def choose_dom(root,token):
    win=tk.Toplevel(root)
    win.title("Stufe A: DOM-Auswahl (optional)")
    win.geometry("780x470")
    result={"mode":"cancel","copied":False}
    text=("Standard: Bereiche direkt im Screenshot markieren.\n\n"
          "Optional: HTML-Auswahl als Startvorschlag (experimentell).\n"
          "Hilfsseite oeffnen und dort 'Bookmarklet kopieren' anklicken.\n"
          "In Edge einen Favoriten anlegen/bearbeiten und dessen URL durch den Code ersetzen.\n"
          "Im Zieltab den Favoriten ueber das Favoritenmenue ausfuehren; die Leiste ist optional.\n"
          "Ergebnisdatei speichern und hier importieren. Sitzung gilt 180 Sekunden.\n"
          "F8 / Abbrechen entfernt den Browser-Picker. Wenn das Bookmarklet blockiert\n"
          "wird, 'Manuell ohne HTML' verwenden. Kopieren nur nach Ihrem Klick auf der Hilfsseite.")
    ttk.Label(win,text=text,wraplength=710,padding=15,justify="left").pack(fill="both",expand=True)
    frame=ttk.Frame(win,padding=10)
    frame.pack(fill="x")
    session=None
    def open_helper():
        nonlocal session
        try:
            if session: session.cancel()
            session=DOMSession()
            import edge_capture
            path=session.write_helper(edge_capture.config_root()/"data"/"sessions")
            result["copied"]=True  # browser cleanup needed, no clipboard activity
            if not webbrowser.open(path.as_uri()):
                messagebox.showwarning("Hilfsseite",f"Hilfsseite manuell im Browser oeffnen:\n{path}\nManuell ohne HTML bleibt moeglich.",parent=win)
        except (OSError,CalibrationError) as error:
            messagebox.showwarning("Hilfsseite",str(error)+"\nManuell ohne HTML bleibt moeglich.",parent=win)
    def accept():
        try:
            if session is None: raise CalibrationError("DOM_PICKER_FAILED","Zuerst eine Sitzung starten.")
            path=filedialog.askopenfilename(parent=win,title="Ergebnisdatei importieren",filetypes=[("DOM-Ergebnis","*.json")])
            if not path:return
            result["payload"]=session.import_file(path)
            result["mode"]="dom"
            win.destroy()
        except (OSError,tk.TclError,CalibrationError) as error:
            messagebox.showwarning("DOM_PICKER_FAILED",f"{error}\nManuelle Auswahl bleibt moeglich.",parent=win)
    def manual():
        result["mode"]="manual"
        win.destroy()
    def cancel():
        win.destroy()
    ttk.Button(frame,text="Manuell ohne HTML",command=manual).pack(side="left",padx=3)
    ttk.Button(frame,text="HTML-Hilfsseite",command=open_helper).pack(side="left",padx=3)
    ttk.Button(frame,text="Ergebnis importieren",command=accept).pack(side="left",padx=3)
    ttk.Button(frame,text="Abbrechen",command=cancel).pack(side="left",padx=3)
    win.bind("<Escape>",lambda e:cancel())
    win.protocol("WM_DELETE_WINDOW",cancel)
    root.wait_window(win)
    if session:session.cancel()
    return result


def clean_dom(gui):
    gui.activate_target(cleanup=True)
    before=gui.snapshot(areas=False,check_abort=False)
    if marker_bounds(before,[217,227,37]) is None:
        return before  # helper not executed; do not send F8 to unrelated page handlers
    gui.remove_dom_picker()
    gui.pause(.3,check_abort=False)
    image=gui.snapshot(areas=False,check_abort=False)
    if marker_bounds(image,[217,227,37]) is not None:
        raise CalibrationError("DOM_PICKER_FAILED","Browser-Picker noch sichtbar. Im Zieltab F8/Abbrechen druecken und neu starten.")
    return image


def fresh_image(gui,park=False):
    try:
        gui.activate_target()
        gui.pause(.35)
        if park:
            gui.park()
            gui.pause(.2)
        return gui.snapshot(areas=False)
    except Exception as error:
        code="SCREENSHOT_FAILED" if "SCREENSHOT_FAILED" in str(error) else "TARGET_WINDOW_LOST"
        raise CalibrationError(code,str(error)) from error


def calibrate(gui,cfg,path,expected_digest,validator):
    root=None
    copied=False
    try:
        phase("TARGET_BINDING")
        gui.bind(check_config=False,check_calibration=False)
        phase("CALIBRATION")
        target=gui.target_metadata()
        root=tk.Tk()
        root.withdraw()
        token=uuid.uuid4().hex
        choice=choose_dom(root,token)
        copied=choice["copied"]
        if choice["mode"]=="cancel":
            raise CalibrationError("CALIBRATION_CANCELLED","Keine Einstellungen gespeichert.")
        diagnostic=None
        rects=initial_rects(cfg,target["selection_bounds"])
        if choice["mode"]=="dom":
            try:
                marked=fresh_image(gui)
                proposed,diagnostic=suggestions(choice["payload"],marked,target["selection_bounds"])
                if "regions" in cfg:
                    names=capture_names(rects)
                    for label,value in proposed.items():
                        if label in ("LEFT","RIGHT"):
                            index=0 if label=="LEFT" else 1
                            if index<len(names):
                                rects[names[index]]=value
                        else:
                            rects[label]=value
                else:
                    rects.update(proposed)
            except CalibrationError as error:
                print(error,"-> manueller Screenshot-Picker.",flush=True)
                messagebox.showwarning("DOM-Vorschlaege verworfen",str(error)+"\nAlle Rechtecke koennen manuell gesetzt werden.",parent=root)
        image=clean_dom(gui) if copied else fresh_image(gui)
        copied=False
        paper=cfg.get("paper_format","A4")
        orientation=cfg.get("paper_orientation","portrait")
        mode=navigation(cfg)
        point=cfg["next_point"] if rects["NEXT"] and cfg["button_rect"]==rects["NEXT"] else center(rects["NEXT"]) if rects["NEXT"] else [0,0]
        while True:
            first=RectanglePicker(root,image,rects,point,target["selection_bounds"],paper,orientation,navigation_mode=mode).show()
            if first["action"]=="cancel":
                raise CalibrationError("CALIBRATION_CANCELLED","Keine Einstellungen gespeichert.")
            rects,point,paper,orientation=first["rects"],first["point"],first["paper"],first["orientation"]
            mode=first.get("navigation",mode)
            # Alle Auswahlfenster sind geschlossen, erst jetzt echten Zustand aufnehmen.
            image=fresh_image(gui)
            final=RectanglePicker(root,image,rects,point,target["selection_bounds"],paper,orientation,final=True,navigation_mode=mode).show()
            if final["action"]=="cancel":
                raise CalibrationError("CALIBRATION_CANCELLED","Keine Einstellungen gespeichert.")
            if final["action"]=="recalibrate":
                image=fresh_image(gui)
                diagnostic=None  # alte DOM-Evidenz gilt nicht fuer neuen Zustand
                continue
            candidate=updated_config(cfg,final["rects"],final["point"],target,diagnostic,final.get("navigation",mode))
            candidate.update(paper_format=final["paper"],paper_orientation=final["orientation"])
            candidate["calibration"]["confirmed_at"]=datetime.now().astimezone().isoformat()
            current=fresh_image(gui)  # Zielidentitaet, Fenster und DPI unmittelbar vor Speichern
            # Hintergrund-Ladevorgaenge/Popups nach der Kontrollansicht nicht ignorieren.
            assert_same_selection(image,current,final["rects"])
            atomic_update(path,candidate,expected_digest,lambda c:validator(c,gui.size))
            print("Kalibrierung gespeichert:",path,";",candidate["paper_format"],candidate["paper_orientation"],flush=True)
            print("Keine Capture-Schleife gestartet. --preview oder regulaeren Lauf separat ausfuehren.",flush=True)
            return 0
    except CalibrationError as error:
        failure(error)
        print(error,flush=True)
        return 2
    except Exception as error:
        failure(error)
        print("TARGET_WINDOW_LOST:",error,flush=True)
        return 2
    finally:
        if copied:
            try:
                clean_dom(gui)
            except Exception as error:
                print("DOM_PICKER_FAILED: Cleanup nicht bestaetigt:",error,"; F8 im Zieltab entfernt den Picker, sonst nach 180 s.",flush=True)
        if root is not None:
            root.destroy()


def confirm_capture(gui,cfg):
    """Neue Kalibrierungen verlangen visuelle Kontrolle auch nach einem Neustart.

    Zoom/DevTools/Sidebar sind nicht allein durch das Fensterhandle beweisbar.
    Aenderungen gehoeren in --calibrate, nicht nur in einen fluechtigen Lauf.
    """
    root=tk.Tk()
    root.withdraw()
    try:
        target=gui.target_metadata()
        image=fresh_image(gui,park=True)
        rects=initial_rects(cfg,target["selection_bounds"])
        result=RectanglePicker(root,image,rects,cfg["next_point"],target["selection_bounds"],
                               cfg.get("paper_format","Original"),cfg.get("paper_orientation","portrait"),final=True,save_label="Aufnahme starten",navigation_mode=navigation(cfg)).show()
        if result["action"]!="save":
            raise CalibrationError("CALIBRATION_CANCELLED","Capture nicht gestartet; --calibrate fuer Aenderungen.")
        # Dict equality alone ignores insertion order, which is the PDF order.
        if capture_names(result["rects"])!=capture_names(rects) or result["rects"]!=rects or result["point"]!=cfg["next_point"] or result["paper"]!=cfg.get("paper_format","Original") or result["orientation"]!=cfg.get("paper_orientation","portrait") or result.get("navigation",navigation(cfg))!=navigation(cfg):
            raise CalibrationError("INVALID_RECTANGLE","Auswahl wurde geaendert. Mit --calibrate speichern, danach Aufnahme neu starten.")
        current=fresh_image(gui,park=True)
        assert_same_selection(image,current,rects)
        return current
    finally:
        root.destroy()
