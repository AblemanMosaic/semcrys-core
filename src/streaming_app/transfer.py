"""Receiver-declared accounting is separate from codec identity and security."""
import hashlib
from streaming_legend.core import canonical

def compile_transfer(*,accounting,receiver_roots,dependencies,realization_plan_root):
    from .core import Refusal,_is_root
    if accounting not in ('COLD','WARM'): raise Refusal('HELD_TRANSFER_ACCOUNTING_REQUIRED')
    if type(receiver_roots) not in (list,tuple) or len(receiver_roots)>2 or any(not _is_root(r) for r in receiver_roots):
        raise Refusal('HELD_RECEIVER_ROOTS')
    if len(set(receiver_roots))!=len(receiver_roots): raise Refusal('HELD_RECEIVER_ROOTS')
    available={row['sha256'] for row in dependencies}
    if not set(receiver_roots)<=available: raise Refusal('HELD_UNKNOWN_RECEIVER_ROOT')
    missing=[dict(row) for row in dependencies if row['sha256'] not in receiver_roots]
    if accounting=='WARM' and missing: raise Refusal('HELD_RECEIVER_DEPENDENCIES_NOT_DECLARED')
    value={'schema':'semcrys.transfer-instance.v0.1','standing':'CANDIDATE_ONLY',
        'realization_plan_root':realization_plan_root,'accounting':accounting,
        'receiver_roots':sorted(receiver_roots),'required_external_dependencies':dependencies,
        'new_dependencies':missing,'new_dependency_bytes':sum(row['bytes'] for row in missing),
        'receiver_evidence':'CALLER_DECLARATION_NOT_REMOTE_ATTESTATION',
        'byte_scope':'EXACT_UNCOMPRESSED_EXECUTION_DEPENDENCY_ARTIFACTS_PLUS_CRYS_CONTAINERS; EXCLUDES_LOCAL_RECEIPT_AND_SEPARATE_PROVENANCE_DOSSIER',
        'network_transfer_executed':False,'relationship_state_mutation':False,'security_claim':'NONE'}
    value['instance_constitution_sha256']=hashlib.sha256(canonical(value)).hexdigest()
    return value

def receipt(transfer,containers):
    """Charge each new dependency once per explicit file/batch operation."""
    rows=[{'sha256':r['sha256'],'bytes':r['bytes']} for r in containers]
    wire=sum(r['bytes'] for r in rows)
    value={'schema':'semcrys.transfer-receipt.v0.1','standing':'CANDIDATE_ONLY',
        'effective_configuration':transfer,'containers':rows,'container_wire_bytes':wire,
        'new_dependency_bytes':transfer['new_dependency_bytes'],
        'accounted_bytes':wire+transfer['new_dependency_bytes'],
        'dependency_charge_count':len(transfer['new_dependencies']),
        'claim':'DECLARED_RECEIVER_COST_NOT_NETWORK_DELIVERY_OR_COMPRESSION_OPTIMALITY'}
    value['receipt_sha256']=hashlib.sha256(canonical(value)).hexdigest()
    return value
