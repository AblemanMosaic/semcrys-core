"""Self-contained assembly realization and complete-container choice.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib,os,tempfile
from streaming_legend import scratch_io as sio
from pathlib import Path
from .assembly import build,read_rules
from .library import _bounded_snapshot
from streaming_app.core import encode_file,decode_file,_capture_controls,Refusal,protect_outputs
from streaming_legend.core import canonical,file_sha256
from streaming_legend.assembly import ABI,FAMILY_ABI
from streaming_legend.crys_v2 import write_crys

MAX_SOURCE=64*1024*1024
OPERATIONS=['BIND_SOURCE_AND_RULE_PACK','BUILD_ORDINARY_CONTAINER','FACTOR_EXACT_LOCAL_LEGEND',
 'BUILD_ASSEMBLY_CONTAINER','VERIFY_BOTH_INVERSES','MEASURE_COMPLETE_CONTAINERS','SELECT_BY_DECLARED_POLICY','PUBLISH']

def encode(source,output,*,rules,outer_codec='NONE',legend_policy='PROFITABLE',encoding='COMPACT',
           record_policy='SHORTER',selection='MIN_CONTAINER',max_source_bytes=MAX_SOURCE,progress=None):
    source,target,rules=Path(source),Path(output),Path(rules); protect_outputs([target],[source,rules])
    if target.suffix.lower()!='.crys': raise Refusal('HELD_CRYS_SUFFIX_REQUIRED')
    if type(max_source_bytes) is not int or not 0<=max_source_bytes<=MAX_SOURCE: raise Refusal('HELD_LOCAL_ASSEMBLY_SOURCE_LIMIT')
    if outer_codec not in ('NONE','LZMA') or legend_policy not in ('TOTAL','PROFITABLE') or encoding not in ('TAGGED','COMPACT') or record_policy not in ('ALL','SHORTER') or selection not in ('MIN_CONTAINER','ASSEMBLY'):
        raise Refusal('HELD_LOCAL_ASSEMBLY_CONFIGURATION')
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sl-',dir=target.parent) as name:
        work=Path(name); snapshot=work/'source'; source_root=_bounded_snapshot(source,snapshot,max_source_bytes)
        rule_copy=work/'rules.json'; rule_root=_bounded_snapshot(rules,rule_copy,16*1024*1024); read_rules(rule_copy)
        request={'schema':'semcrys.local-assembly-selection-instance.v0.1','standing':'CANDIDATE_ONLY',
            'source_sha256':source_root,'rule_pack_sha256':rule_root,'outer_codec':outer_codec,'legend_policy':legend_policy,
            'encoding':encoding,'record_policy':record_policy,'selection':selection,'max_source_bytes':max_source_bytes,
            'operation_sequence':OPERATIONS,'comparison_scope':'TWO_EXACT_SELF_CONTAINED_TOKEN_CONTAINERS_NOT_GLOBAL_OPTIMUM',
            'audit_scope':'RULE_PACK_AND_LOCAL_RECEIPTS_SEPARATE_NOT_COUNTED_IN_CONTAINER','security_claim':'NONE'}
        request['instance_constitution_sha256']=hashlib.sha256(canonical(request)).hexdigest()
        if progress: progress({'stage':'LOCAL_ASSEMBLY_INSTANCE_COMPILED','effective_configuration':request})
        ordinary=work/'ordinary.crys'
        baseline=encode_file(snapshot,ordinary,profile='C:SELF_CONTAINED_TOKEN',outer_codec=outer_codec,legend_policy=legend_policy)
        captured=work/'captured'; captured.mkdir()
        inspected,body,embedded=_capture_controls(ordinary,captured)
        if len(embedded)!=1: raise Refusal('HELD_LOCAL_ASSEMBLY_EXPECTED_ONE_BASE')
        form_legend=work/'forms.leg'; factored=build(embedded[0],form_legend,rules=rule_copy,encoding=encoding,policy=record_policy)
        config=dict(inspected['configuration']); config.pop('instance_constitution_sha256')
        config.update(schema='semcrys.instance-constitution.v0.7' if encoding=='COMPACT' else 'semcrys.instance-constitution.v0.6',
            assembly_abi=FAMILY_ABI if encoding=='COMPACT' else ABI,assembly_legend_roots=[file_sha256(form_legend)],
            legend_stack=[{'role':'BASE','mode':'EMBEDDED','sha256':file_sha256(form_legend)}])
        config['instance_constitution_sha256']=hashlib.sha256(canonical(config)).hexdigest()
        candidate=work/'assembly.crys'
        write_crys(candidate,configuration=config,body=body,legend_stack=[('BASE','EMBEDDED',form_legend)],
            decoded_sha256=source_root,receipts=[baseline['receipt']])
        rows=[]
        for label,path,ic in [('ORDINARY',ordinary,inspected['configuration']),('ASSEMBLY',candidate,config)]:
            decoded=work/'decoded'; decode_file(path,decoded)
            if file_sha256(decoded)!=source_root: raise Refusal('HELD_LOCAL_ASSEMBLY_INVERSE')
            rows.append({'id':label,'bytes':path.stat().st_size,'sha256':file_sha256(path),
                'instance_constitution_sha256':ic['instance_constitution_sha256'],'byte_exact_inverse':True})
        selected=1 if selection=='ASSEMBLY' or rows[1]['bytes']<rows[0]['bytes'] else 0
        chosen=(ordinary,candidate)[selected]; chosen_config=(inspected['configuration'],config)[selected]
        result={'status':'PASS','standing':'CANDIDATE_ONLY','schema':'semcrys.local-assembly-selection-result.v0.1',
            'effective_configuration':request,'selected_configuration':chosen_config,'selected_id':rows[selected]['id'],
            'candidates':rows,'output_sha256':rows[selected]['sha256'],'source_sha256':source_root,
            'saved_container_bytes':rows[0]['bytes']-rows[selected]['bytes'],'external_decoder_dependencies':[],
            'build':factored,'body_bytes_unchanged':True,'ordinary_tie_preferred':True,
            'authority_effect':'NONE','security_claim':'NONE'}
        if progress: progress({'stage':'LOCAL_ASSEMBLY_SELECTED','selected_id':result['selected_id'],'candidates':rows})
        sio.replace(chosen,target)
    return result
