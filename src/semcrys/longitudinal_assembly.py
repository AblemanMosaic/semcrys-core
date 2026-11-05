"""Whole-container selection for append-only assembly deltas."""
import hashlib,os,tempfile
from streaming_legend import scratch_io as sio
from pathlib import Path
from .assembly import build,read_rules
from .assembly_chain import verify_chain,MAX_PARENTS,MAX_LEGEND_BYTES
from .library import _bounded_snapshot
from streaming_app.core import Refusal,protect_outputs,encode_file,decode_file,_capture_controls
from streaming_app.legend_context import VerifiedLegendContext
from streaming_legend.assembly import ExecutionLegendReader,MODES,COMPACT_MODE,ABI,FAMILY_ABI
from streaming_legend.core import canonical,file_sha256
from streaming_legend.crys_v2 import write_crys

OPERATIONS=['SNAPSHOT_SOURCE_RULES_PARENTS','COMPILE_INSTANCE','BUILD_ORDINARY_LONGITUDINAL_CONTAINER',
 'FACTOR_EMBEDDED_DELTA','REBIND_CONFIGURATION','VERIFY_BOTH_INVERSES','COMPARE_COMPLETE_CONTAINERS','PUBLISH_SELECTED_CONTAINER']
MAX_SOURCE=64*1024*1024

def encode(source,output,*,rules,external_legends,outer_codec='NONE',encoding='COMPACT',record_policy='SHORTER',
           selection='MIN_CONTAINER',max_source_bytes=MAX_SOURCE,max_legend_bytes=MAX_LEGEND_BYTES,progress=None):
    source,target,rules=Path(source),Path(output),Path(rules); parents=tuple(map(Path,external_legends))
    protect_outputs([target],[source,rules,*parents])
    if target.suffix.lower()!='.crys': raise Refusal('HELD_CRYS_SUFFIX_REQUIRED')
    if not 1<=len(parents)<=MAX_PARENTS: raise Refusal('HELD_ASSEMBLY_PARENT_CHAIN_COUNT')
    if type(max_source_bytes) is not int or not 0<=max_source_bytes<=MAX_SOURCE: raise Refusal('HELD_LONGITUDINAL_ASSEMBLY_SOURCE_LIMIT')
    if type(max_legend_bytes) is not int or not 0<=max_legend_bytes<=MAX_LEGEND_BYTES: raise Refusal('HELD_ASSEMBLY_LEGEND_BUDGET')
    if outer_codec not in ('NONE','LZMA') or encoding not in ('TAGGED','COMPACT') or record_policy not in ('ALL','SHORTER') or selection not in ('MIN_CONTAINER','ASSEMBLY'):
        raise Refusal('HELD_LONGITUDINAL_ASSEMBLY_CONFIGURATION')
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sd-',dir=target.parent) as name:
        work=Path(name); snapshot=work/'source'; source_root=_bounded_snapshot(source,snapshot,max_source_bytes)
        rule_copy=work/'rules.json'; rule_root=_bounded_snapshot(rules,rule_copy,16*1024*1024); read_rules(rule_copy)
        snapshots=[]; roots=[]; used=0
        for i,p in enumerate(parents):
            dest=work/(str(i)+'.leg'); roots.append(_bounded_snapshot(p,dest,max_legend_bytes-used))
            used+=dest.stat().st_size; snapshots.append(dest)
        with VerifiedLegendContext(max_legend_bytes=max_legend_bytes,max_legends=4096) as context:
            with context.operation(): verify_chain(snapshots,context)
            request={'schema':'semcrys.longitudinal-assembly-instance.v0.1','standing':'CANDIDATE_ONLY',
              'source_sha256':source_root,'rule_pack_sha256':rule_root,'external_legend_roots':roots,
              'profile':'A:LONGITUDINAL_TOKEN_DELTA','legend_policy':'TOTAL','outer_codec':outer_codec,
              'encoding':encoding,'record_policy':record_policy,'selection':selection,
              'max_source_bytes':max_source_bytes,'max_legend_bytes':max_legend_bytes,
              'operation_sequence':OPERATIONS,'comparison_scope':'TWO_CONTAINERS_WITH_IDENTICAL_EXTERNAL_PARENTS',
              'audit_scope':'SEPARATE_RULE_PACK_AND_RECEIPTS_NOT_COUNTED','future_delta_economics':'NOT_PREDICTED',
              'shared_state_mutation':False,'security_claim':'NONE'}
            request['instance_constitution_sha256']=hashlib.sha256(canonical(request)).hexdigest()
            if progress: progress({'stage':'LONGITUDINAL_ASSEMBLY_INSTANCE_COMPILED','effective_configuration':request})
            ordinary=work/'ordinary.crys'
            baseline=encode_file(snapshot,ordinary,profile='A:LONGITUDINAL_TOKEN_DELTA',external_legends=snapshots,
                 outer_codec=outer_codec,legend_context=context)
            captured=work/'captured'; captured.mkdir(); inspected,body,embedded=_capture_controls(ordinary,captured)
            if len(embedded)!=1: raise Refusal('HELD_LONGITUDINAL_ASSEMBLY_EXPECTED_ONE_DELTA')
            delta=work/'factored.leg'
            factored=build(embedded[0],delta,rules=rule_copy,encoding=encoding,policy=record_policy,
                source_parents=snapshots,target_parents=snapshots,max_legend_bytes=max_legend_bytes)
            all_paths=[*snapshots,delta]
            assembly_roots=[file_sha256(p) for p in all_paths if ExecutionLegendReader(p).is_assembly]
            compact=any(ExecutionLegendReader(p).header['unit_mode']==COMPACT_MODE for p in all_paths)
            config=dict(inspected['configuration']); config.pop('instance_constitution_sha256')
            bindings=[('BASE' if i==0 else 'DELTA','EXTERNAL',root) for i,root in enumerate(roots)]
            bindings.append(('DELTA','EMBEDDED',delta))
            config.update(schema='semcrys.instance-constitution.v0.7' if compact else 'semcrys.instance-constitution.v0.6',
                assembly_abi=FAMILY_ABI if compact else ABI,assembly_legend_roots=assembly_roots,
                legend_stack=[*config['legend_stack'][:-1],{'role':'DELTA','mode':'EMBEDDED','sha256':file_sha256(delta)}])
            config['instance_constitution_sha256']=hashlib.sha256(canonical(config)).hexdigest()
            candidate=work/'assembly.crys'
            write_crys(candidate,configuration=config,body=body,legend_stack=bindings,decoded_sha256=source_root,receipts=[baseline['receipt']])
            rows=[]
            for label,path,ic,legend in [('ORDINARY',ordinary,inspected['configuration'],embedded[0]),('ASSEMBLY',candidate,config,delta)]:
                decoded=work/'decoded'; decode_file(path,decoded,external_legends=snapshots,legend_context=context)
                if file_sha256(decoded)!=source_root: raise Refusal('HELD_LONGITUDINAL_ASSEMBLY_INVERSE')
                rows.append({'id':label,'bytes':path.stat().st_size,'sha256':file_sha256(path),
                   'instance_constitution_sha256':ic['instance_constitution_sha256'],'delta_sha256':file_sha256(legend),
                   'delta_bytes':legend.stat().st_size,'byte_exact_inverse':True})
            selected=1 if selection=='ASSEMBLY' or rows[1]['bytes']<rows[0]['bytes'] else 0
            chosen=(ordinary,candidate)[selected]; chosen_config=(inspected['configuration'],config)[selected]
            context.verify_used()
        result={'schema':'semcrys.longitudinal-assembly-result.v0.1','status':'PASS','standing':'CANDIDATE_ONLY',
           'effective_configuration':request,'selected_configuration':chosen_config,'selected_id':rows[selected]['id'],
           'candidates':rows,'output_sha256':rows[selected]['sha256'],'source_sha256':source_root,
           'saved_container_bytes':rows[0]['bytes']-rows[selected]['bytes'],'external_decoder_dependencies':roots,
           'next_delta_binding':{'binding_index':len(parents),'sha256':rows[selected]['delta_sha256'],
             'parent_sha256':roots[-1],'adoption':'CALLER_EXPLICIT_EXTRACT_AND_APPEND_ONLY'},
           'build':factored,'body_bytes_unchanged':True,'shared_state_mutated':False,
           'ordinary_tie_preferred':True,'authority_effect':'NONE','security_claim':'NONE'}
        if progress: progress({'stage':'LONGITUDINAL_ASSEMBLY_SELECTED','selected_id':result['selected_id'],'candidates':rows})
        sio.replace(chosen,target)
    return result
