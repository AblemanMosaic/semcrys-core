"""Explicit execution/audit separation; roots are correspondence, not signatures.

SPDX-License-Identifier: Apache-2.0
"""
import hashlib,json,os,tempfile
from pathlib import Path
from streaming_legend import fold
from streaming_legend import scratch_io as sio
from streaming_legend.core import canonical
from streaming_app.core import Refusal,protect_outputs

DOSSIER_SCHEMA='semcrys.fold-provenance.v0.1'
MAX_DOSSIER=128*1024
OPERATIONS=['VERIFY_RICH_PROJECTION','ROOT_SOURCE_PROVENANCE','BUILD_COMPACT_EXECUTION_PROJECTION',
    'VERIFY_EXACT_RICH_RECONSTRUCTION','PUBLISH_NEW_BUNDLE']

def digest(data): return hashlib.sha256(data).hexdigest()

def _compact_header(rich,provenance_root):
    return {**{k:v for k,v in rich.items() if k not in fold.AUDIT_FIELDS},
        'schema':fold.COMPACT_SCHEMA,'provenance_sha256':provenance_root}

def _audit_data(compact_data,provenance_data):
    header,entries,signal=fold.parse(compact_data)
    if header['schema']!=fold.COMPACT_SCHEMA: raise Refusal('HELD_FOLD_COMPACT_REQUIRED')
    if len(provenance_data)>MAX_DOSSIER: raise Refusal('HELD_FOLD_PROVENANCE_BUDGET')
    if digest(provenance_data)!=header['provenance_sha256']: raise Refusal('HELD_FOLD_PROVENANCE_MISMATCH')
    try: dossier=json.loads(provenance_data.decode('utf-8'))
    except (ValueError,UnicodeError,RecursionError) as exc: raise Refusal('HELD_FOLD_PROVENANCE_SCHEMA') from exc
    if type(dossier) is not dict or set(dossier)!={'schema','standing','source_projection_sha256','source_header','operation_sequence'}:
        raise Refusal('HELD_FOLD_PROVENANCE_SCHEMA')
    if canonical(dossier)!=provenance_data: raise Refusal('HELD_FOLD_PROVENANCE_NONCANONICAL')
    if dossier['schema']!=DOSSIER_SCHEMA or dossier['standing']!='CANDIDATE_ONLY' or dossier['operation_sequence']!=OPERATIONS:
        raise Refusal('HELD_FOLD_PROVENANCE_SCHEMA')
    rich=dossier['source_header']
    if type(rich) is not dict or rich.get('schema')!=fold.SCHEMA: raise Refusal('HELD_FOLD_PROVENANCE_SOURCE_SCHEMA')
    # Parsing the reconstructed rich artifact independently validates all fields,
    # cardinalities, calibration roots, signal, and original ordering policy.
    reconstructed=fold.serialize(rich,signal)
    if digest(reconstructed)!=dossier['source_projection_sha256']: raise Refusal('HELD_FOLD_PROVENANCE_SOURCE_ROOT')
    if header!=_compact_header(rich,digest(provenance_data)): raise Refusal('HELD_FOLD_PROVENANCE_CORRESPONDENCE')
    return dossier,reconstructed

def _read_dossier(path):
    with Path(path).open('rb') as handle: data=handle.read(MAX_DOSSIER+1)
    if len(data)>MAX_DOSSIER: raise Refusal('HELD_FOLD_PROVENANCE_BUDGET')
    return data

def audit_front(source,provenance):
    header,_,_,data,root=fold.load(source); raw=_read_dossier(provenance)
    dossier,restored=_audit_data(data,raw)
    return {'status':'PASS','schema':'semcrys.fold-provenance-audit.v0.1','standing':'CANDIDATE_ONLY',
        'projection_sha256':root,'provenance_sha256':digest(raw),
        'source_projection_sha256':digest(restored),'exact_rich_reconstruction':True,
        'calibration_roots':dossier['source_header']['calibration_roots'],
        'execution_artifact_bytes':len(data),'audit_dossier_bytes':len(raw),
        'execution_plus_audit_bytes':len(data)+len(raw),
        'base_dependent_validation':'REQUIRES_EXACT_BASE_AT_USE',
        'provenance_claim':'HASH_CORRESPONDENCE_NOT_AUTHOR_AUTHENTICATION_OR_CALIBRATION_TRUTH',
        'authority':'NONE','security_claim':'NONE'}

def compact_front(source,output):
    """Publish a new directory containing .leg, canonical dossier and receipt."""
    source,target=Path(source),Path(output)
    protect_outputs([target],[source])
    if target.exists(): raise Refusal('HELD_OUTPUT_EXISTS')
    header,_,signal,original,source_root=fold.load(source)
    if header['schema']!=fold.SCHEMA: raise Refusal('HELD_FOLD_RICH_SOURCE_REQUIRED')
    dossier={'schema':DOSSIER_SCHEMA,'standing':'CANDIDATE_ONLY','source_projection_sha256':source_root,
        'source_header':header,'operation_sequence':OPERATIONS}
    raw=canonical(dossier)
    if len(raw)>MAX_DOSSIER: raise Refusal('HELD_FOLD_PROVENANCE_BUDGET')
    data=fold.serialize(_compact_header(header,digest(raw)),signal)
    _,restored=_audit_data(data,raw)
    if restored!=original: raise Refusal('HELD_FOLD_RECONSTRUCTION_MISMATCH')
    instance={'schema':'semcrys.fold-compact-instance.v0.1','standing':'CANDIDATE_ONLY',
        'source_projection_sha256':source_root,'operation_sequence':OPERATIONS,
        'artifact_schema':fold.COMPACT_SCHEMA,'base_mutation':False,'source_mutation':False,
        'execution_requires_audit_dossier':False,'source_audit_requires_dossier':True,
        'selection':'EXPLICIT_OPT_IN_NOT_AUTOMATIC','security_claim':'NONE'}
    instance['instance_constitution_sha256']=digest(canonical(instance))
    result={'status':'PASS','standing':'CANDIDATE_ONLY','effective_configuration':instance,
        'projection_sha256':digest(data),'provenance_sha256':digest(raw),'source_projection_sha256':source_root,
        'rich_artifact_bytes':len(original),'execution_artifact_bytes':len(data),'audit_dossier_bytes':len(raw),
        'execution_plus_audit_bytes':len(data)+len(raw),'exact_rich_reconstruction':True,
        'bundle_files':{'execution':'front.leg','audit':'provenance.json','local_receipt':'LOCAL_RECEIPT.json'},
        'byte_scope':'EXECUTION_AND_AUDIT_REPORTED_SEPARATELY; LOCAL_RECEIPT_EXCLUDED',
        'claim':'METADATA_PLACEMENT_NOT_CODEC_BODY_COMPRESSION_OR_SECURITY'}
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sc-prov-',dir=target.parent) as name:
        pending=Path(name)/'bundle'; pending.mkdir()
        sio.write_bytes(pending/'front.leg',data); sio.write_bytes(pending/'provenance.json',raw)
        sio.write_bytes(pending/'LOCAL_RECEIPT.json',canonical(result)+b'\n')
        if target.exists(): raise Refusal('HELD_OUTPUT_EXISTS')
        # rename directory only when complete; Windows rename refuses existing.
        sio.replace(pending,target)
    return result

def restore_rich(source,output,*,provenance):
    source,target=Path(source),Path(output); protect_outputs([target],[source,provenance])
    if target.suffix.lower()!='.leg': raise Refusal('HELD_LEG_SUFFIX_REQUIRED')
    _,_,_,data,root=fold.load(source); raw=_read_dossier(provenance)
    dossier,restored=_audit_data(data,raw)
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sc-restore-',dir=target.parent) as name:
        pending=Path(name)/'rich.leg'; sio.write_bytes(pending,restored); sio.replace(pending,target)
    return {'status':'PASS','standing':'CANDIDATE_ONLY','output_sha256':digest(restored),
        'source_projection_sha256':root,'provenance_sha256':digest(raw),'artifact_bytes':len(restored),
        'operation_sequence':['VERIFY_COMPACT_AND_DOSSIER','RECONSTRUCT_RICH_BYTE_EXACT','PUBLISH'],
        'claim':'ROOT_CORRESPONDENCE_NOT_AUTHENTICATION','security_claim':'NONE'}

def delivery_cost(source,*,policy,provenance=None,receiver_roots=(),container_bytes=0,horizon=1):
    """Explicit audit-inclusive or execution-only charge; no network or mutation."""
    if policy not in ('EXECUTION_ONLY','EXECUTION_AND_AUDIT'): raise Refusal('HELD_FOLD_DELIVERY_POLICY')
    if type(container_bytes) is not int or not 0<=container_bytes<=1<<40 or type(horizon) is not int or not 1<=horizon<=32:
        raise Refusal('HELD_FOLD_DELIVERY_BUDGET')
    h,_,_,data,root=fold.load(source)
    if h['schema']!=fold.COMPACT_SCHEMA: raise Refusal('HELD_FOLD_COMPACT_REQUIRED')
    deps=[{'kind':'EXECUTION_PROJECTION','sha256':root,'bytes':len(data)}]
    if policy=='EXECUTION_AND_AUDIT':
        if provenance is None: raise Refusal('HELD_FOLD_PROVENANCE_REQUIRED')
        raw=_read_dossier(provenance); _audit_data(data,raw)
        deps.append({'kind':'AUDIT_PROVENANCE','sha256':digest(raw),'bytes':len(raw)})
    elif provenance is not None: raise Refusal('HELD_UNUSED_FOLD_PROVENANCE')
    if type(receiver_roots) not in (list,tuple) or any(not fold.root(r) for r in receiver_roots) or len(receiver_roots)!=len(set(receiver_roots)) or not set(receiver_roots)<={r['sha256'] for r in deps}:
        raise Refusal('HELD_FOLD_DELIVERY_RECEIVER_ROOTS')
    missing=[d for d in deps if d['sha256'] not in receiver_roots]
    instance={'schema':'semcrys.fold-delivery-instance.v0.1','standing':'CANDIDATE_ONLY','policy':policy,
        'dependencies':deps,'receiver_roots':sorted(receiver_roots),'container_bytes_per_delivery':container_bytes,'horizon':horizon,
        'operation_sequence':['VERIFY_PROJECTION','VERIFY_DOSSIER_IF_REQUESTED','CHARGE_MISSING_ONCE','ADD_IDENTICAL_DELIVERIES'],
        'byte_scope':'EXTERNAL_PROJECTION_AND_OPTIONAL_AUDIT_PLUS_CALLER_DECLARED_CONTAINERS; BASE_LEGEND_AND_LOCAL_RECEIPTS_EXCLUDED',
        'input_claim':'CONTAINER_BYTES_ARE_CALLER_DECLARATION_NOT_MEASURED_HERE',
        'horizon_scope':'IDENTICAL_WORKLOAD_ONLY','receiver_attestation':False,'network_transfer':False,'security_claim':'NONE'}
    instance['instance_constitution_sha256']=digest(canonical(instance))
    return {'status':'PASS','effective_configuration':instance,'new_dependencies':missing,
        'new_dependency_bytes':sum(d['bytes'] for d in missing),
        'accounted_bytes':container_bytes*horizon+sum(d['bytes'] for d in missing),
        'audit_dossier_transferred':policy=='EXECUTION_AND_AUDIT' and h['provenance_sha256'] not in receiver_roots,
        'audit_status':'VERIFIED_SOURCE_CORRESPONDENCE' if policy=='EXECUTION_AND_AUDIT' else 'UNRESOLVED_ROOT_REFERENCE'}
