"""Fold-front realization over an immutable base, not a copied Ultra dictionary.

SPDX-License-Identifier: Apache-2.0
"""
from streaming_legend import scratch_io as sio
import hashlib
import os
import sqlite3
import tempfile
from bisect import bisect_right
from pathlib import Path
from .fold_scanner import iter_folded,COMMON_SEPS,TOKENIZER
from .legend_context import governed_context
from streaming_legend.core import canonical,file_sha256
from streaming_legend import fold

BODY_MAGIC=b"SFP1"
OPERATIONS=["SDO:DECOMPOSE_FOLDED_UNIT_ON_MISS","SDO:BUILD_CALIBRATION_ONLY_FOLDED_MACRO_PROJECTION",
            "SDO:RECONSTRUCT_FROZEN_BASE_TAIL","SDO:EMIT_FOLDED_PROJECTION_SIGNAL"]

def split_ranks(value,lookup):
    for suffix in sorted((s.encode("utf-8") for s in COMMON_SEPS),key=len,reverse=True):
        if value.endswith(suffix) and len(value)>len(suffix):
            a=lookup.get(value[:-len(suffix)]); b=lookup.get(suffix)
            if a is not None and b is not None: return (a,b)
    return None

class _CalibrationLookup:
    """Historical candidate-pool semantics; full-base access is not equivalent."""
    def __init__(self,db,lookup): self.db,self.lookup=db,lookup
    def get(self,value):
        if self.db.execute('SELECT 1 FROM candidates WHERE value=?',(value,)).fetchone() is None: return None
        return self.lookup.get(value)

class _ProjectedLookup:
    def __init__(self,view): self.view=view
    def get(self,value): return self.view.find(value)

class FoldView:
    def __init__(self,artifact,base,context):
        from .core import Refusal,_Lookup,_IdResolver
        self.header,self.entries,self.signal,self.data,self.sha256=fold.load(artifact)
        row=context.prepare(base)
        if row["sha256"]!=self.header["base_legend_sha256"] or row["entries"]!=self.header["base_entries"]:
            raise Refusal("HELD_FOLD_BASE_BINDING")
        if row["reader"].header["parent_sha256"] is not None: raise Refusal("HELD_FOLD_BASE_PARENT")
        self.lookup=_Lookup(row["connection"]); self.resolver=_IdResolver([row["path"]],context=context)
        self.front={}; self.values=[]; self.moved=sorted(r[0] for r in self.entries if len(r)==1)
        self.base_front={r[0]:i for i,r in enumerate(self.entries,1) if len(r)==1}
        self.total=self.header["projected_entries"]; self.front_size=len(self.entries)
        value_bytes=0
        for identifier,ranks in enumerate(self.entries,1):
            parts=[self.resolver.get(n) for n in ranks]
            value=b"".join(parts); value_bytes+=len(value)
            if len(value)>fold.MAX_VALUE_BYTES or value_bytes>fold.MAX_FRONT_VALUE_BYTES:
                raise Refusal("HELD_FOLD_EXPANSION_BUDGET")
            if value in self.front: raise Refusal("HELD_FOLD_DUPLICATE_EXPANSION")
            if len(ranks)==2:
                if parts[1] not in {s.encode("utf-8") for s in COMMON_SEPS}: raise Refusal("HELD_FOLD_MACRO_SEPARATOR")
                if self.lookup.get(value) is not None: raise Refusal("HELD_FOLD_MACRO_ALREADY_IN_BASE")
            self.front[value]=identifier; self.values.append(value)
        self.front_value_bytes=value_bytes
        self.projected_lookup=_ProjectedLookup(self)

    def rank_of_base(self,rank):
        # A moved base is represented by its front position, not in the tail.
        if rank in self.base_front: return self.base_front[rank]
        return self.front_size+rank-bisect_right(self.moved,rank)

    def find(self,value):
        if value in self.front: return self.front[value]
        rank=self.lookup.get(value)
        return None if rank is None else self.front_size+rank-bisect_right(self.moved,rank)

    def get(self,identifier):
        from .core import Refusal
        if type(identifier) is not int or not 1<=identifier<=self.total: raise Refusal("HELD_BODY_ID_RANGE")
        if identifier<=self.front_size: return self.values[identifier-1]
        target=identifier-self.front_size
        low,high=1,self.header["base_entries"]
        while low<high:
            mid=(low+high)//2
            if mid-bisect_right(self.moved,mid)<target: low=mid+1
            else: high=mid
        return self.resolver.get(low)

    def encode(self,source,target):
        from .core import _venc
        units=symbols=literals=split_units=literal_bytes=0
        with sio.open_output(Path(target),"wb") as outgoing:
            outgoing.write(BODY_MAGIC)
            for kind,value in iter_folded(source):
                units+=1; identifier=None if kind=="lit" else self.find(value)
                if identifier is not None:
                    outgoing.write(_venc(identifier)); symbols+=1; continue
                parts=None if kind=="lit" else split_ranks(value,self.projected_lookup)
                if parts is not None:
                    for rank in parts: outgoing.write(_venc(rank))
                    symbols+=2; split_units+=1
                else:
                    outgoing.write(b"\0"+_venc(len(value))+value); literals+=1; literal_bytes+=len(value)
        return {"sha256":file_sha256(Path(target)),"bytes":Path(target).stat().st_size,"units":units,
            "symbols":symbols,"literals":literals,"constituent_split_units":split_units,"literal_source_bytes":literal_bytes}

@governed_context
def build_front(source,output,*,external_legends,additional_sources=(),front_cap=4096,
                max_calibration_bytes=64*1024*1024,legend_context=None,progress=None):
    from .core import Refusal,protect_outputs,_Lookup
    target=Path(output); sources=[Path(source),*map(Path,additional_sources)]
    protect_outputs([target],[*sources,*external_legends,*legend_context.protected_paths()])
    if target.suffix.lower()!=".leg": raise Refusal("HELD_LEG_SUFFIX_REQUIRED")
    if len(external_legends)!=1: raise Refusal("HELD_FOLD_REQUIRES_SINGLE_BASE")
    if type(front_cap) is not int or not 0<=front_cap<=fold.MAX_FRONT: raise Refusal("HELD_FOLD_FRONT_BUDGET")
    if type(max_calibration_bytes) is not int or not 0<=max_calibration_bytes<=1024*1024*1024 or len(sources)>512:
        raise Refusal("HELD_FOLD_CALIBRATION_BUDGET")
    row=legend_context.prepare(external_legends[0])
    if row['reader'].header['unit_mode'].startswith('ASSEMBLY_'): raise Refusal('HELD_ASSEMBLY_COMPOSITION_NOT_YET_QUALIFIED')
    if row['reader'].header['unit_mode']!='TOKEN': raise Refusal('HELD_FOLD_REQUIRES_LITERAL_TOKEN_MODE')
    if row["reader"].header["parent_sha256"] is not None: raise Refusal("HELD_FOLD_BASE_PARENT")
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix="sf-",dir=target.parent) as name:
        work=Path(name); snapshots=[]; roots=[]; total=0
        for i,source in enumerate(sources):
            path=work/str(i); digest=hashlib.sha256()
            with source.open("rb") as incoming,sio.open_output(path,"wb") as outgoing:
                for data in iter(lambda:incoming.read(1048576),b""):
                    total+=len(data)
                    if total>max_calibration_bytes: raise Refusal("HELD_FOLD_CALIBRATION_BUDGET")
                    digest.update(data); outgoing.write(data)
            roots.append(digest.hexdigest()); snapshots.append(path)
        instance={"schema":"semcrys.fold-build-instance.v0.1","standing":"CANDIDATE_ONLY",
            "base_legend_sha256":row["sha256"],"calibration_roots":roots,"front_cap":front_cap,
            "tokenizer":TOKENIZER,"max_unit_bytes":4096,"max_calibration_bytes":max_calibration_bytes,
            "ordering":fold.ORDERING,"candidate_policy":fold.CANDIDATE_POLICY,"operation_sequence":OPERATIONS,"security_claim":"NONE",
            "source_role":"CALLER_DESIGNATED_CALIBRATION_NOT_INFERRED","heldout_inputs":False}
        instance["instance_constitution_sha256"]=hashlib.sha256(canonical(instance)).hexdigest()
        if progress: progress({"stage":"FOLD_INSTANCE_COMPILED","effective_configuration":instance})
        db=sio.sqlite_connect(work/"counts.sqlite3")
        try:
            db.execute("PRAGMA journal_mode=OFF"); db.execute("PRAGMA temp_store=FILE"); db.execute("PRAGMA cache_size=-2048")
            db.execute("CREATE TABLE counts(value BLOB PRIMARY KEY,n INTEGER,first_seen INTEGER) WITHOUT ROWID")
            units=0
            for snapshot in snapshots:
                for kind,value in iter_folded(snapshot):
                    if kind!="lit":
                        db.execute("INSERT INTO counts VALUES (?,1,?) ON CONFLICT(value) DO UPDATE SET n=n+1",(value,units))
                    units+=1
                db.commit()
            db.execute('CREATE TABLE candidates(value BLOB PRIMARY KEY) WITHOUT ROWID')
            for (value,) in db.execute('SELECT value FROM counts'):
                db.execute('INSERT OR IGNORE INTO candidates VALUES (?)',(value,))
                for suffix in sorted((s.encode('utf-8') for s in COMMON_SEPS),key=len,reverse=True):
                    if value.endswith(suffix) and len(value)>len(suffix):
                        db.execute('INSERT OR IGNORE INTO candidates VALUES (?)',(value[:-len(suffix)],))
                        db.execute('INSERT OR IGNORE INTO candidates VALUES (?)',(suffix,)); break
            db.commit()
            # Materialize the historical ordering in the already reserved main
            # database. An implicit SQLite temporary sort has no quota owner.
            db.execute('CREATE TABLE ranked(rank INTEGER,first_seen INTEGER,value BLOB,PRIMARY KEY(rank,first_seen)) WITHOUT ROWID')
            for value,count,first_seen in db.execute('SELECT value,n,first_seen FROM counts'):
                db.execute('INSERT INTO ranked VALUES (?,?,?)',(-count,first_seen,value))
            db.commit()
            lookup=_CalibrationLookup(db,_Lookup(row["connection"])); entries=[]; expanded=0; macro=0
            for (value,) in db.execute("SELECT value FROM ranked ORDER BY rank,first_seen"):
                if len(entries)>=front_cap: break
                rank=lookup.get(value)
                ranks=(rank,) if rank is not None else split_ranks(value,lookup)
                if ranks is None: continue
                expanded+=len(value)
                if expanded>fold.MAX_FRONT_VALUE_BYTES: raise Refusal("HELD_FOLD_EXPANSION_BUDGET")
                entries.append(ranks); macro+=int(len(ranks)==2)
        finally: db.close()
        signal=fold.encode_signal(entries)
        header={"schema":fold.SCHEMA,"standing":"CANDIDATE_ONLY","base_legend_sha256":row["sha256"],"base_entries":row["entries"],
            "front_entries":len(entries),"macro_entries":macro,"projected_entries":row["entries"]+macro,
            "signal_sha256":hashlib.sha256(signal).hexdigest(),"signal_codec":fold.SIGNAL_CODEC,
            "tokenizer":TOKENIZER,"max_unit_bytes":4096,"front_cap":front_cap,"ordering":fold.ORDERING,"calibration_roots":roots,
            "candidate_policy":fold.CANDIDATE_POLICY}
        pending=work/"front.leg"; sio.write_bytes(pending,fold.serialize(header,signal))
        view=FoldView(pending,row["path"],legend_context)
        legend_context.verify_used(); sio.replace(pending,target)
    return {"status":"PASS","schema":"semcrys.fold-build-result.v0.1","standing":"CANDIDATE_ONLY",
        "output_sha256":view.sha256,"effective_configuration":instance,"header":header,
        "calibration_bytes":total,"calibration_units":units,"signal_bytes":len(signal),"artifact_bytes":len(view.data),
        "base_legend_bytes":row["path"].stat().st_size,"front_expansion_bytes":expanded,
        "base_mutation":False,"selection_claim":"EXPLICIT_FRONT_CAP_NOT_OPTIMAL","security_claim":"NONE"}

def extract_front(source,output):
    from .core import protect_outputs,Refusal
    from streaming_legend.crys_v2 import inspect_crys
    source,target=Path(source),Path(output); protect_outputs([target],[source])
    if target.suffix.lower()!=".leg": raise Refusal("HELD_LEG_SUFFIX_REQUIRED")
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix="sf-",dir=target.parent) as name:
        from .core import _snapshot
        snapshot=Path(name)/'source.crys'; _snapshot(source,snapshot)
        inspected=inspect_crys(snapshot,capture_directory=Path(name))
        if inspected.get('fold_dependency_status')=='EXTERNAL_NOT_RESOLVED': raise Refusal('HELD_FOLD_PROJECTION_IS_EXTERNAL')
        path=inspected.get("fold_projection_path")
        if path is None: raise Refusal("HELD_FOLD_PROJECTION_MISSING")
        value=fold.inspect(Path(path)); sio.replace(path,target)
    return {**value,"schema":"semcrys.fold-extraction.v0.1","container_sha256":inspected["file_sha256"],"output_sha256":value["sha256"]}

def prefix_front(source,output,*,front_cap):
    """Keep a frozen ordering prefix; no training, new ranking, or base mutation."""
    from .core import protect_outputs,Refusal
    source,target=Path(source),Path(output); protect_outputs([target],[source])
    header,entries,_,data,parent=fold.load(source)
    if header['schema']!=fold.SCHEMA: raise Refusal('HELD_FOLD_PREFIX_RESTORE_RICH_PROVENANCE_FIRST')
    if type(front_cap) is not int or not 0<=front_cap<=header['front_cap']:
        raise Refusal('HELD_FOLD_PREFIX_CAP')
    if target.suffix.lower()!='.leg': raise Refusal('HELD_LEG_SUFFIX_REQUIRED')
    kept=entries[:front_cap]; signal=fold.encode_signal(kept); h=dict(header)
    h.update(front_cap=front_cap,front_entries=len(kept),macro_entries=sum(len(e)==2 for e in kept),
        signal_sha256=hashlib.sha256(signal).hexdigest())
    h['projected_entries']=h['base_entries']+h['macro_entries']
    artifact=fold.serialize(h,signal)
    instance={'schema':'semcrys.fold-prefix-instance.v0.1','standing':'CANDIDATE_ONLY',
        'source_projection_sha256':parent,'front_cap':front_cap,'ordering':'PRESERVE_EXISTING_PREFIX',
        'operation_sequence':['VERIFY_SOURCE_PROJECTION','RETAIN_PREFIX','RECOMPUTE_CARDINALITIES_AND_SIGNAL_ROOT','VALIDATE_ARTIFACT','PUBLISH'],
        'calibration_roots':h['calibration_roots'],'new_calibration':False,'security_claim':'NONE'}
    instance['instance_constitution_sha256']=hashlib.sha256(canonical(instance)).hexdigest()
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sp-',dir=target.parent) as name:
        p=Path(name)/'front.leg'; sio.write_bytes(p,artifact); fold.load(p); sio.replace(p,target)
    return {'status':'PASS','standing':'CANDIDATE_ONLY','effective_configuration':instance,
        'output_sha256':hashlib.sha256(artifact).hexdigest(),'artifact_bytes':len(artifact),
        'front_entries':h['front_entries'],'base_dependent_validation':'REQUIRED_AT_USE'}
