"""Versioned slot policy. Geometry and runtime navigation remain separate authorities."""
import copy

from .regions import capture_rects


def default_policy(count):
    return {"schema": 1, "slot_count": count, "first": list(range(1, count+1)),
            "middle": list(range(1, count+1)), "last": list(range(1, count+1)), "overrides": {}}


def validate_policy(policy, count, max_views=None):
    if max_views is not None and (type(max_views) is not int or max_views < 1):
        raise ValueError("Ungueltiges Aufnahmelimit fuer die Seitenbelegung.")
    if not isinstance(policy, dict) or set(policy) != {"schema", "slot_count", "first", "middle", "last", "overrides"}:
        raise ValueError("Seitenbelegung: unvollstaendige oder unbekannte Einstellungen.")
    if type(policy["schema"]) is not int or policy["schema"] != 1 or type(policy["slot_count"]) is not int or policy["slot_count"] != count:
        raise ValueError("Seitenbelegung passt nicht zur aktuellen Anzahl der Capture-Slots. Neu einstellen.")
    def mask(values):
        if not isinstance(values, list) or not values or any(type(v) is not int or not 1 <= v <= count for v in values):
            raise ValueError("Jede Ansicht braucht mindestens einen gueltigen Capture-Slot.")
        if values != sorted(set(values)):
            raise ValueError("Capture-Slots muessen eindeutig in Capture-Reihenfolge stehen.")
    for key in ("first", "middle", "last"):
        mask(policy[key])
    if not isinstance(policy["overrides"], dict):
        raise ValueError("Ansichtsausnahmen muessen nach Ansichtsnummer gespeichert sein.")
    for view, values in policy["overrides"].items():
        if not isinstance(view, str) or not view.isascii() or not view.isdecimal() or str(int(view)) != view or not 1 <= int(view) <= (max_views or 1000000):
            raise ValueError("Ausnahmen: Ansichtsnummer ausserhalb des Aufnahmelimits.")
        mask(values)
    return policy


def policy_for(cfg):
    count = len(capture_rects(cfg))
    return validate_policy(cfg.get("page_layout_policy", default_policy(count)), count, cfg.get("max_spreads"))


def resolve_view(policy, index, is_last=False):
    """Pure port for a future explicit Pause/Override/Continue adapter.

    Overrides win; last wins over first when a run contains exactly one view.
    Unknown-length callers must establish the terminal view before publication.
    """
    source = "override" if str(index) in policy["overrides"] else "last" if is_last else "first" if index == 1 else "middle"
    slots = policy["overrides"][str(index)] if source == "override" else policy[source]
    return list(slots), {"source": source, "is_last": is_last}


class PolicyDialog:
    """Optional pre-capture editor; never opened by the capture loop."""
    def __init__(self, root, count, initial=None, max_views=1000000):
        import tkinter as tk
        from tkinter import ttk
        self.root, self.count, self.max_views = root, count, max_views
        self.result = None
        self.policy = copy.deepcopy(initial or default_policy(count))
        validate_policy(self.policy, count, max_views)
        self.window = tk.Toplevel(root)
        self.window.title("Seitenbelegung vor der Aufnahme")
        self.window.geometry("720x610")
        ttk.Label(self.window, text="Slots entsprechen den sichtbaren Bereichsnummern im Editor.\n"
                  "Defaults: alle Slots. Keine automatische Leer-Seiten-Erkennung.\n"
                  "Bei genau einer Ansicht gilt Letzte; eine Ausnahme hat Vorrang.", padding=12).pack(anchor="w")
        self.masks = {}
        body=ttk.Frame(self.window);body.pack(fill="both",expand=True,padx=12)
        canvas=tk.Canvas(body,height=230,highlightthickness=0)
        scrollbar=ttk.Scrollbar(body,orient="vertical",command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right",fill="y");canvas.pack(side="left",fill="both",expand=True)
        choices=ttk.Frame(canvas)
        item=canvas.create_window(0,0,window=choices,anchor="nw")
        choices.bind("<Configure>",lambda e:canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",lambda e:canvas.itemconfigure(item,width=e.width))
        labels = ["Links (Bereich 1)", "Rechts (Bereich 2)"] if count == 2 else [f"Bereich {i}" for i in range(1, count+1)]
        for key, label in (("first", "Erste Ansicht"), ("middle", "Mittlere Ansichten"), ("last", "Letzte Ansicht"), ("override", "Ausnahme fuer eine Ansicht")):
            frame = ttk.LabelFrame(choices, text=label, padding=8)
            frame.pack(fill="x", pady=4)
            variables = [tk.BooleanVar(value=i in self.policy.get(key, list(range(1, count+1)))) for i in range(1, count+1)]
            self.masks[key] = variables
            for i,(label,var) in enumerate(zip(labels,variables)):
                ttk.Checkbutton(frame,text=label,variable=var).grid(row=i//4,column=i%4,sticky="w",padx=6)
        line = ttk.Frame(self.window); line.pack(fill="x", padx=12)
        ttk.Label(line, text="Ansichtsnummer:").pack(side="left")
        self.view = tk.StringVar(value="1")
        ttk.Entry(line, textvariable=self.view, width=8).pack(side="left", padx=6)
        ttk.Button(line, text="Ausnahme setzen/ersetzen", command=self.set_override).pack(side="left")
        ttk.Button(line, text="Ausnahme entfernen", command=self.remove_override).pack(side="left", padx=6)
        self.listing = tk.Listbox(self.window, height=6)
        self.listing.pack(fill="x", padx=12, pady=8)
        self.listing.bind("<<ListboxSelect>>", self.select_override)
        footer = ttk.Frame(self.window, padding=12); footer.pack(fill="x")
        ttk.Button(footer, text="Uebernehmen", command=self.accept).pack(side="right")
        ttk.Button(footer, text="Abbrechen", command=self.window.destroy).pack(side="right", padx=8)
        self.window.bind("<Escape>", lambda e: self.window.destroy())
        self.refresh()

    def values(self, key):
        return [i for i, var in enumerate(self.masks[key], 1) if var.get()]

    def refresh(self):
        self.listing.delete(0, "end")
        self.rows = sorted(self.policy["overrides"], key=int)
        for view in self.rows:
            self.listing.insert("end", f"Ansicht {view}: Bereiche {', '.join(map(str, self.policy['overrides'][view]))}")

    def select_override(self, event=None):
        if not self.listing.curselection(): return
        view = self.rows[self.listing.curselection()[0]]
        self.view.set(view)
        for i, var in enumerate(self.masks["override"], 1): var.set(i in self.policy["overrides"][view])

    def set_override(self):
        from tkinter import messagebox
        candidate = copy.deepcopy(self.policy)
        candidate["overrides"][self.view.get()] = self.values("override")
        try:
            validate_policy(candidate, self.count, self.max_views)
            self.policy = candidate; self.refresh()
        except ValueError as error: messagebox.showerror("Seitenbelegung unveraendert", str(error), parent=self.window)

    def remove_override(self):
        self.policy["overrides"].pop(self.view.get(), None); self.refresh()

    def accept(self):
        from tkinter import messagebox
        candidate = copy.deepcopy(self.policy)
        candidate.update({key: self.values(key) for key in ("first", "middle", "last")})
        try:
            validate_policy(candidate, self.count, self.max_views)
            self.result = candidate; self.window.destroy()
        except ValueError as error: messagebox.showerror("Seitenbelegung pruefen", str(error), parent=self.window)

    def show(self):
        self.root.wait_window(self.window)
        return self.result
