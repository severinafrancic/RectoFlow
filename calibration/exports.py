"""Frozen capture → persisted plan bytes → verified PNG bytes → PDF/result."""
import copy
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import uuid

from PIL import Image, ImageChops, ImageStat
from .geometry import PAPER_MM
from .regions import capture_rects, image_names
from .storage import atomic_json, exclusive, LockBusy


def digest(data):return hashlib.sha256(data).hexdigest()


def readable_manifest(manifest):
    schema=manifest.get("schema",1)
    if schema not in (1,2,3):raise ValueError("Unbekanntes Aufnahmemanifest-Schema.")
    if manifest.get("status")=="RUNNING":raise ValueError("RUNNING: Aufnahme nicht abgeschlossen; Wiederherstellung erforderlich.")
    if schema==3:
        if manifest.get("status") not in ("COMPLETE","STOPPED") or not manifest.get("finished"):
            raise ValueError("Aufnahme ist nicht eingefroren.")
    elif manifest.get("status") not in (None,"COMPLETE","STOPPED","PDF_FAILED"):
        raise ValueError("Unbekannter Aufnahmestatus.")
    if schema==2 and "regions" not in manifest["config"]:raise ValueError("Schema 2 braucht regions.")
    pairs=manifest["pairs"]
    if not isinstance(pairs,list):raise ValueError("Ungueltige Ansichten.")
    for index,pair in enumerate(pairs,1):
        if type(pair.get("index")) is not int or pair["index"]!=index:raise ValueError("Ungueltige Ansichtsindizes.")


def source_snapshot(folder):
    raw=(Path(folder)/"manifest.json").read_bytes()
    manifest=json.loads(raw.decode("utf-8-sig"));readable_manifest(manifest)
    return manifest,digest(raw)


def running_state(folder):
    folder=Path(folder)
    manifest=json.loads((folder/"manifest.json").read_bytes())
    if manifest.get("status")!="RUNNING":return manifest.get("status","UNKNOWN")
    if manifest.get("schema")!=3:return "RECOVERY_REQUIRED: Aktivitaet ungeklaert"
    try:
        with exclusive(folder/".writer.lock",timeout=0):return "INTERRUPTED / RECOVERY_REQUIRED"
    except LockBusy:return "RUNNING: Aufnahme aktiv"
    except OSError:return "RECOVERY_REQUIRED: Aktivitaet ungeklaert"


def view_images(folder,manifest,index):
    cfg=manifest["config"]
    if type(index) is not int or not 1<=index<=len(manifest["pairs"]):raise ValueError("Ansicht nicht vorhanden.")
    pair=manifest["pairs"][index-1]
    names=image_names(cfg,index);rects=capture_rects(cfg)
    if pair["index"]!=index or len(pair["images"])!=len(names):raise ValueError("Ungueltige Regionsanzahl.")
    result=[]
    for expected,rect,entry in zip(names,rects,pair["images"]):
        if entry["file"]!=expected:raise ValueError("Ungueltige Bildnamen/Reihenfolge.")
        raw=(Path(folder)/expected).read_bytes()  # exactly one path read per image
        if digest(raw)!=entry["sha256"]:raise ValueError("Zwischenbild wurde veraendert: "+expected)
        with Image.open(BytesIO(raw)) as decoded:
            decoded.load()
            if decoded.size!=tuple(rect[2:]):raise ValueError("Bildgroesse passt nicht zur Aufnahme.")
            result.append(decoded.convert("RGB"))
    return result


def pdf_options(cfg,overrides=None):
    result={"paper_format":cfg.get("paper_format","Original"),"paper_orientation":cfg.get("paper_orientation","portrait"),
            "pdf_layout":cfg.get("pdf_layout","separate"),"pdf_dpi":cfg.get("pdf_dpi",120)}
    if overrides:
        if set(overrides)-set(result):raise ValueError("Unbekannte PDF-Einstellungen.")
        result.update(overrides)
    if result["paper_format"] not in (*PAPER_MM,"Original") or result["paper_orientation"] not in ("portrait","landscape") or result["pdf_layout"] not in ("separate","spread"):
        raise ValueError("Ungueltige PDF-Einstellungen.")
    dpi=result["pdf_dpi"]
    if isinstance(dpi,bool) or not isinstance(dpi,(int,float)) or not math.isfinite(dpi) or dpi<=0:raise ValueError("Ungueltige PDF-DPI.")
    return result


def validate_plan(plan,manifest,source_hash):
    if type(plan.get("schema")) is not int or plan["schema"]!=1 or plan.get("source_manifest_sha256")!=source_hash:
        raise ValueError("ExportPlan gehoert nicht zum gespeicherten Manifest.")
    selected=plan.get("selected_view_indices")
    if not isinstance(selected,list) or not selected or any(type(v) is not int or not 1<=v<=len(manifest["pairs"]) for v in selected) or len(set(selected))!=len(selected):
        raise ValueError("Exportansichten muessen vorhanden, eindeutig und nicht leer sein.")
    options=plan.get("pdf_options")
    if not isinstance(options,dict) or set(options)!=set(pdf_options(manifest["config"])):raise ValueError("Unvollstaendige PDF-Einstellungen.")
    pdf_options(manifest["config"],options)


def create_plan(folder,selected=None,options=None,expected_manifest_hash=None):
    folder=Path(folder).resolve();manifest,source_hash=source_snapshot(folder)
    if expected_manifest_hash is not None and source_hash!=expected_manifest_hash:raise ValueError("Manifest seit Review geaendert.")
    plan={"schema":1,"source_manifest_sha256":source_hash,"selected_view_indices":list(selected) if selected is not None else list(range(1,len(manifest["pairs"])+1)),
          "pdf_options":pdf_options(manifest["config"],options),"analysis":{"schema":1,"similarity_threshold":.995,"low_contrast_stddev":2.0}}
    validate_plan(plan,manifest,source_hash)
    destination=folder/"exports"/uuid.uuid4().hex;destination.mkdir(parents=True,exist_ok=False)
    path=destination/"export_plan.json";atomic_json(path,plan)
    return path


def execute_plan(folder,plan_path):
    import edge_capture
    folder=Path(folder).resolve();plan_path=Path(plan_path).resolve()
    manifest,source_hash=source_snapshot(folder)
    plan_bytes=plan_path.read_bytes();plan_hash=digest(plan_bytes)
    plan=json.loads(plan_bytes.decode("utf-8-sig"));validate_plan(plan,manifest,source_hash)
    # A copied/imported plan is materialized in its own new export directory.
    expected_parent=folder/"exports"
    if plan_path.parent.parent!=expected_parent or plan_path.name!="export_plan.json":
        target=expected_parent/uuid.uuid4().hex;target.mkdir(parents=True,exist_ok=False)
        from .storage import atomic_bytes
        plan_path=target/"export_plan.json";atomic_bytes(plan_path,plan_bytes)
        stored=plan_path.read_bytes()
        if digest(stored)!=plan_hash:raise ValueError("Persistierter Plan stimmt nicht ueberein.")
        plan_bytes=stored;plan=json.loads(stored.decode("utf-8-sig"));validate_plan(plan,manifest,source_hash)
    output=plan_path.parent/"document.pdf";result_path=plan_path.parent/"result.json"
    with exclusive(plan_path.parent/".export.lock"):
        if output.exists() or result_path.exists():raise ValueError("Export existiert bereits; neuen Plan erzeugen.")
        result={"schema":1,"export_plan_sha256":plan_hash,"source_manifest_sha256":source_hash,"status":"RUNNING"}
        atomic_json(result_path,result)
        try:
            cfg=copy.deepcopy(manifest["config"]);cfg.update(plan["pdf_options"])
            candidate={**manifest,"config":cfg}
            edge_capture._render_pdf(folder,candidate,output,selected=plan["selected_view_indices"])
            pdf_bytes=output.read_bytes()
            if digest((folder/"manifest.json").read_bytes())!=source_hash or digest(plan_path.read_bytes())!=plan_hash:
                raise ValueError("Manifest oder ExportPlan waehrend Export geaendert.")
            result.update(status="COMPLETE",pdf_sha256=digest(pdf_bytes))
            atomic_json(result_path,result)
            return output
        except BaseException as error:
            result.update(status="CANCELLED" if isinstance(error,KeyboardInterrupt) else "FAILED",error=f"{type(error).__name__}: {error}")
            atomic_json(result_path,result)
            raise


def region_statistics(image):
    small=image.convert("RGB").resize((64,64),Image.Resampling.LANCZOS)
    pixels=getattr(small,"get_flattened_data",small.getdata)()
    luminances=[.299*r+.587*g+.114*b for r,g,b in pixels]
    mean=sum(luminances)/len(luminances)
    std=math.sqrt(sum((v-mean)**2 for v in luminances)/len(luminances))
    return small,std


def analyze_view(folder,manifest,index):
    images=view_images(folder,manifest,index)
    stats=[region_statistics(im) for im in images]
    warnings=[f"Bereich {i}: geringer Kontrast" for i,(_,std) in enumerate(stats,1) if std<=2.0]
    similarity=None
    if index>1:
        try:
            previous=view_images(folder,manifest,index-1)
            if len(previous)!=len(images):raise ValueError("Unvollstaendige Regionen.")
            similarities=[]
            for (small,_),old in zip(stats,previous):
                old=old.convert("RGB").resize((64,64),Image.Resampling.LANCZOS)
                mean=sum(ImageStat.Stat(ImageChops.difference(small,old)).mean)/3
                similarities.append(1-mean/255)
            similarity=sum(similarities)/len(similarities)
            if similarity>=.995:warnings.append(f"Aehnlich zu Ansicht {index-1}: {similarity:.3%}")
        except (OSError,ValueError,KeyError):warnings.append("Vergleich nicht auswertbar")
    return {"schema":1,"similarity":similarity,"low_contrast_stddev":[std for _,std in stats],"warnings":warnings}
