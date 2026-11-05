"""Explicit multi-document reuse of verified legends; no group-legend inference."""
import hashlib
import os
import tempfile
import time
from pathlib import Path
from streaming_app.core import Refusal,encode_file,protect_outputs
from streaming_app.legend_context import VerifiedLegendContext
from streaming_legend.core import canonical,file_sha256
from streaming_legend import scratch_io as sio

def encode_batch(output,*,sources,profile,external_legends=(),outer_codec='NONE',legend_policy=None,
                 projection='PACKED',glyph_registry=None,glyph_placement='EMBEDDED',fold_front=None,progress=None,
                 fold_placement='EMBEDDED',accounting=None,receiver_roots=(),
                 max_source_bytes=1024*1024*1024,max_legend_bytes=1024*1024*1024,
                 lookup_backend='AUTO',backend_payload_budget_bytes=512*1024*1024,persistent_lookup_cache=None):
    output=Path(output); sources=[Path(p) for p in sources]
    if not 1<=len(sources)<=256: raise Refusal('HELD_BATCH_SOURCE_COUNT')
    if any(type(n) is not int or not 0<=n<=1<<40 for n in (max_source_bytes,max_legend_bytes)):
        raise Refusal('HELD_BATCH_BUDGET')
    if output.exists(): raise Refusal('HELD_BATCH_DESTINATION_EXISTS')
    inputs=[*sources,*external_legends,*([glyph_registry] if glyph_registry else [])]
    if fold_front is not None: inputs.append(fold_front)
    protect_outputs([output],inputs)
    if sum(p.stat().st_size for p in sources)>max_source_bytes: raise Refusal('HELD_BATCH_SOURCE_BUDGET')
    roots=[file_sha256(p) for p in sources]
    legend_roots=[file_sha256(Path(p)) for p in external_legends]
    instance={'schema':'semcrys.batch-instance.v0.1','standing':'CANDIDATE_ONLY','source_roots':roots,
        'external_legend_roots':legend_roots,'profile':profile,'outer_codec':outer_codec,'legend_policy':legend_policy,
        'projection':projection,'glyph_sha256':file_sha256(Path(glyph_registry)) if glyph_registry else None,'glyph_placement':glyph_placement,
        'max_source_bytes':max_source_bytes,'max_legend_bytes':max_legend_bytes,
        'lookup_backend':lookup_backend,'backend_payload_budget_bytes':backend_payload_budget_bytes,
        'persistent_lookup_cache':persistent_lookup_cache is not None,
        'operation_sequence':['BIND_INPUT_ROOTS','PREPARE_VERIFIED_CONTEXT','ENCODE_EACH_WITH_RECONSTRUCTION','GUARD_CONTEXT','PUBLISH_NEW_DIRECTORY'],
        'relationship_state_mutation':False,'security_claim':'NONE','group_legend':'NOT_APPLIED'}
    if fold_front is not None: instance['fold_front_sha256']=file_sha256(Path(fold_front))
    if fold_placement!='EMBEDDED' or accounting is not None or receiver_roots:
        instance.update(fold_placement=fold_placement,accounting=accounting,receiver_roots=sorted(receiver_roots))
    instance['instance_constitution_sha256']=hashlib.sha256(canonical(instance)).hexdigest()
    if progress: progress({'stage':'BATCH_INSTANCE_COMPILED','effective_configuration':instance})
    output.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sb-',dir=output.parent) as name:
        stage=Path(name)/'result'; stage.mkdir(); rows=[]; total=0
        with VerifiedLegendContext(max_legend_bytes=max_legend_bytes,progress=progress,lookup_backend=lookup_backend,
                backend_payload_budget_bytes=backend_payload_budget_bytes,persistent_lookup_cache=persistent_lookup_cache) as context:
            bound=context.rows(external_legends)
            if [r['sha256'] for r in bound]!=legend_roots: raise Refusal('HELD_BATCH_DEPENDENCY_CHANGED')
            for index,(source,root) in enumerate(zip(sources,roots)):
                began=time.perf_counter()
                frozen=Path(name)/'source.snapshot'; digest=hashlib.sha256()
                with source.open('rb') as incoming,sio.open_output(frozen,'wb') as outgoing:
                    for chunk in iter(lambda:incoming.read(1048576),b''):
                        total+=len(chunk)
                        if total>max_source_bytes: raise Refusal('HELD_BATCH_SOURCE_BUDGET')
                        outgoing.write(chunk); digest.update(chunk)
                if digest.hexdigest()!=root: raise Refusal('HELD_BATCH_SOURCE_CHANGED')
                if progress: progress({'stage':'BATCH_DOCUMENT_STARTED','index':index})
                target=stage/f'{index:06d}.crys'
                realized=encode_file(frozen,target,profile=profile,external_legends=[r['path'] for r in bound],outer_codec=outer_codec,
                    legend_policy=legend_policy,projection=projection,glyph_registry=glyph_registry,glyph_placement=glyph_placement,fold_front=fold_front,
                    fold_placement=fold_placement,accounting=accounting,receiver_roots=receiver_roots,legend_context=context)
                if realized['source_sha256']!=root: raise Refusal('HELD_BATCH_SOURCE_CHANGED')
                if glyph_registry and realized['effective_configuration'].get('glyph_registry_sha256')!=instance['glyph_sha256']:
                    raise Refusal('HELD_BATCH_DEPENDENCY_CHANGED')
                if fold_front is not None and realized['effective_configuration']['fold_projection']['sha256']!=instance['fold_front_sha256']:
                    raise Refusal('HELD_BATCH_DEPENDENCY_CHANGED')
                rows.append({'index':index,'file':target.name,'result':realized,'realization_seconds':time.perf_counter()-began})
                if progress: progress({'stage':'BATCH_DOCUMENT_FINISHED','index':index,'output_sha256':realized['output_sha256']})
            context.verify_used(); execution=context.receipt()
        result={'status':'PASS','schema':'semcrys.batch-result.v0.1','standing':'CANDIDATE_ONLY',
            'effective_configuration':instance,'documents':rows,'execution_context':execution,
            'publication':'NEW_DIRECTORY_RENAME_NO_REPLACEMENT_NOT_POWER_FAILURE_DURABILITY'}
        if accounting is not None:
            from streaming_app.transfer import compile_transfer,receipt
            dependencies=rows[0]['result']['transfer']['effective_configuration']['required_external_dependencies']
            if any(r['result']['transfer']['effective_configuration']['required_external_dependencies']!=dependencies for r in rows):
                raise Refusal('HELD_BATCH_DEPENDENCY_CHANGED')
            transfer=compile_transfer(accounting=accounting,receiver_roots=receiver_roots,dependencies=dependencies,
                realization_plan_root=instance['instance_constitution_sha256'])
            result['transfer']=receipt(transfer,[{'sha256':r['result']['output_sha256'],'bytes':(stage/r['file']).stat().st_size} for r in rows])
            result['transfer_scope']='BATCH_TOTAL_CHARGES_EACH_NEW_DEPENDENCY_ONCE; DOCUMENT_RECEIPTS_ARE_STANDALONE_ALTERNATIVES_NOT_ADDITIVE'
        result['batch_root']=hashlib.sha256(canonical(result)).hexdigest()
        sio.write_bytes(stage/'BATCH_RECEIPT.json',canonical(result))
        if output.exists(): raise Refusal('HELD_BATCH_DESTINATION_EXISTS')
        sio.replace(stage,output)
    return result
