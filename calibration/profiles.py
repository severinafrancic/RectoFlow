"""Indexless UUID profiles; stable locks and immutable per-run snapshots."""
from contextlib import ExitStack
import copy
import hashlib
import json
import os
from pathlib import Path
import uuid

from .storage import exclusive, config_exclusive, atomic_json, atomic_bytes, config_transaction
from .regions import navigation

TEMPLATES={"enabled":"button_enabled.png","disabled":"button_disabled.png"}


def profile_id(value):
    normalized=str(uuid.UUID(str(value)))
    if normalized != str(value):raise ValueError("Ungueltige Profil-UUID.")
    return normalized


def validate_profile_config(cfg):
    import edge_capture
    edge_capture.validate(cfg,(32768,32768))


def validate_templates(cfg,templates):
    if cfg["button_mode"]=="template" and navigation(cfg)=="next_button":
        from io import BytesIO
        from PIL import Image
        if set(templates)!=set(TEMPLATES):raise ValueError("Beide Button-Templates werden benoetigt.")
        for data in templates.values():
            with Image.open(BytesIO(data)) as image:
                image.load()
                if image.size!=tuple(cfg["button_rect"][2:]):raise ValueError("Template-Groesse ungueltig.")


class ProfileStore:
    def __init__(self,data_root):
        self.data=Path(data_root).resolve()
        self.folder=self.data/"profiles"
        self.locks=self.data/".locks"

    def path(self,identifier):
        return self.folder/profile_id(identifier)

    def transaction(self,identifiers):
        stack=ExitStack()
        try:
            stack.enter_context(exclusive(self.locks/"profiles.lock"))
            for identifier in sorted(set(identifiers)):
                stack.enter_context(exclusive(self.locks/("profile-"+profile_id(identifier)+".lock")))
            for identifier in sorted(set(identifiers)):
                stack.enter_context(config_exclusive(self.path(identifier)/"config.json"))
            return stack
        except BaseException:
            stack.close();raise

    def _snapshot(self,identifier,include_templates=True):
        path=self.path(identifier)
        if path.is_symlink() or getattr(path,"is_junction",lambda:False)():raise ValueError("Profilordner darf keine Umleitung sein.")
        meta=json.loads((path/"profile.json").read_bytes())
        if not isinstance(meta,dict) or meta.get("schema")!=1 or meta.get("uuid")!=identifier or not isinstance(meta.get("name"),str) or not meta["name"].strip():
            raise ValueError("Profilmetadaten ungueltig.")
        raw=(path/"config.json").read_bytes()
        cfg=json.loads(raw.decode("utf-8-sig"));validate_profile_config(cfg)
        templates={key:(path/name).read_bytes() for key,name in TEMPLATES.items()} if include_templates and cfg["button_mode"]=="template" and navigation(cfg)=="next_button" else {}
        if include_templates:validate_templates(cfg,templates)
        provenance={"uuid":identifier,"config_sha256":hashlib.sha256(raw).hexdigest(),"template_sha256":{key:hashlib.sha256(data).hexdigest() for key,data in templates.items()}}
        return {"metadata":meta,"config":cfg,"config_bytes":raw,"templates":templates,"profile":provenance,
                "output_root":self.data/"captures"/identifier,"config_path":path/"config.json"}

    def snapshot(self,identifier,include_templates=True):
        with self.transaction([identifier]):return self._snapshot(identifier,include_templates)

    def enumerate(self):
        self.folder.mkdir(parents=True,exist_ok=True)
        result=[]
        with exclusive(self.locks/"profiles.lock"):
            for path in sorted(self.folder.iterdir()):
                if not path.is_dir() or path.name.startswith("."):continue
                try:
                    identifier=profile_id(path.name)
                    with exclusive(self.locks/("profile-"+identifier+".lock")),config_exclusive(path/"config.json"):
                        snap=self._snapshot(identifier)
                    result.append({"uuid":identifier,"name":snap["metadata"]["name"],"ready":True,"reason":""})
                except (ValueError,OSError,RuntimeError,KeyError,TypeError) as error:
                    result.append({"uuid":path.name,"name":path.name,"ready":False,"reason":str(error)})
        return result

    def _create(self,identifier,name,raw,templates):
        if not isinstance(name,str) or not name.strip():raise ValueError("Profilname fehlt.")
        cfg=json.loads(raw.decode("utf-8-sig"));validate_profile_config(cfg);validate_templates(cfg,templates)
        target=self.path(identifier)
        self.folder.mkdir(parents=True,exist_ok=True)
        stage=self.folder/(".pending-"+identifier);stage.mkdir(exist_ok=False)
        atomic_bytes(stage/"config.json",raw)
        for key,data in templates.items():
            if key not in TEMPLATES:raise ValueError("Unbekanntes Template.")
            atomic_bytes(stage/TEMPLATES[key],data)
        atomic_json(stage/"profile.json",{"schema":1,"uuid":identifier,"name":name.strip()})
        os.rename(stage,target)
        return identifier

    def create(self,name,cfg,templates=None):
        identifier=str(uuid.uuid4())
        raw=json.dumps(cfg,ensure_ascii=False,indent=2,allow_nan=False).encode("utf-8")
        with self.transaction([identifier]):return self._create(identifier,name,raw,templates or {})

    def import_config(self,path,name):
        path=Path(path).resolve();identifier=str(uuid.uuid4())
        with config_transaction(path):
            raw=path.read_bytes();cfg=json.loads(raw.decode("utf-8-sig"))
            templates={key:(path.parent/file).read_bytes() for key,file in TEMPLATES.items()} if cfg["button_mode"]=="template" and navigation(cfg)=="next_button" else {}
        with self.transaction([identifier]):return self._create(identifier,name,raw,templates)

    def duplicate(self,identifier,name):
        new=str(uuid.uuid4())
        with self.transaction([identifier,new]):
            snap=self._snapshot(identifier)
            return self._create(new,name,snap["config_bytes"],snap["templates"])

    def rename(self,identifier,name):
        if not isinstance(name,str) or not name.strip():raise ValueError("Profilname fehlt.")
        with self.transaction([identifier]):
            snap=self._snapshot(identifier)
            meta=copy.deepcopy(snap["metadata"]);meta["name"]=name.strip()
            atomic_json(self.path(identifier)/"profile.json",meta)
