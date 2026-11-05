"""Explicit form-rule lowering into a transport legend, without source mutation.
SPDX-License-Identifier: Apache-2.0
"""
import hashlib,json,os,sqlite3,tempfile
from streaming_legend import scratch_io as sio
from pathlib import Path
from streaming_legend.core import LegendReader,LegendError,write_legend,canonical,file_sha256,_venc
from streaming_legend.assembly import ExecutionLegendReader,UNIT_MODE,COMPACT_MODE,ABI,FAMILY_ABI,OPERATORS,MAX_RULES,MAX_VALUE,apply,program,compact_program
from streaming_app.core import Refusal,protect_outputs,_snapshot

RULE_SCHEMA='semcrys.assembly-rule-pack.v0.1'
OPERATIONS=['VERIFY_SOURCE_AND_RULE_PACK','RESOLVE_LOCAL_BASE_INDICES','COMPILE_TYPED_FORM_PROGRAMS',
 'VERIFY_ALL_EXPANSIONS_AND_ID_ORDER','COMPARE_COSTS','PUBLISH_CANDIDATE']

def read_rules(path):
    with Path(path).open('rb') as f: data=f.read(16*1024*1024+1)
    if len(data)>16*1024*1024: raise Refusal('HELD_ASSEMBLY_RULE_PACK_LIMIT')
    def unique(pairs):
        value={}
        for k,v in pairs:
            if k in value: raise Refusal('HELD_ASSEMBLY_DUPLICATE_JSON_KEY')
            value[k]=v
        return value
    try: value=json.loads(data.decode('utf-8'),object_pairs_hook=unique)
    except (ValueError,UnicodeError,RecursionError) as exc:
        if isinstance(exc,Refusal): raise
        raise Refusal('HELD_ASSEMBLY_RULE_PACK_JSON') from exc
    keys={'schema','standing','jurisdiction','source_refs','rules'}
    if type(value) is not dict or set(value)!=keys or value['schema']!=RULE_SCHEMA or value['standing']!='CANDIDATE_ONLY':
        raise Refusal('HELD_ASSEMBLY_RULE_PACK_SCHEMA')
    if value['jurisdiction']!='ENGLISH_EXPLICIT_SURFACE_FORMS' or type(value['source_refs']) is not list or len(value['source_refs'])>512:
        raise Refusal('HELD_ASSEMBLY_JURISDICTION')
    if any(type(s) is not str or not 1<=len(s)<=512 for s in value['source_refs']): raise Refusal('HELD_ASSEMBLY_SOURCE_REF')
    if type(value['rules']) is not list or len(value['rules'])>MAX_RULES: raise Refusal('HELD_ASSEMBLY_RULE_COUNT')
    rows={}
    for index,r in enumerate(value['rules']):
        try:
            if type(r) is not dict or set(r)!={'surface','base','operator'}: raise Refusal('HELD_ASSEMBLY_RULE_FIELDS')
            if any(type(r[k]) is not str for k in r): raise Refusal('HELD_ASSEMBLY_RULE_TYPE')
            try: surface=r['surface'].encode('utf-8'); base=r['base'].encode('utf-8')
            except UnicodeError as exc: raise Refusal('HELD_ASSEMBLY_RULE_UTF8') from exc
            if not surface or not base or len(surface)>MAX_VALUE or len(base)>MAX_VALUE or surface==base: raise Refusal('HELD_ASSEMBLY_RULE_VALUE')
            if surface in rows: raise Refusal('HELD_ASSEMBLY_DUPLICATE_SURFACE')
            if apply(base,r['operator'],surface if r['operator']=='EXPLICIT_REPLACE' else None)!=surface:
                raise Refusal('HELD_ASSEMBLY_RULE_NOT_EXACT')
        except (Refusal,LegendError) as exc:
            # Preserve the original typed refusal and exception class. Indices,
            # not user content, locate the failure without echoing private text.
            raise type(exc)(exc.code,f'rules[{index}] (zero-based rule index)') from exc
        rows[surface]=(base,r['operator'])
    return value,rows,hashlib.sha256(data).hexdigest()

def build(source,output,*,rules,encoding='TAGGED',policy='ALL',source_parents=(),target_parents=(),max_legend_bytes=1024*1024*1024):
    if encoding not in ('TAGGED','COMPACT') or policy not in ('ALL','SHORTER'): raise Refusal('HELD_ASSEMBLY_BUILD_CONFIGURATION')
    source,target,rules=Path(source),Path(output),Path(rules)
    source_parents,target_parents=tuple(source_parents),tuple(target_parents)
    protect_outputs([target],[source,rules,*source_parents,*target_parents])
    if target.suffix.lower()!='.leg': raise Refusal('HELD_LEG_SUFFIX_REQUIRED')
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sa-',dir=target.parent) as directory:
        work=Path(directory); snap=work/'source.leg'
        if source_parents or target_parents:
            from .library import _bounded_snapshot
            from .assembly_chain import MAX_LEGEND_BYTES
            if type(max_legend_bytes) is not int or not 0<=max_legend_bytes<=MAX_LEGEND_BYTES: raise Refusal('HELD_ASSEMBLY_LEGEND_BUDGET')
            source_root=_bounded_snapshot(source,snap,max_legend_bytes)
        else: source_root=_snapshot(source,snap)
        rule_snapshot=work/'rules.json'
        with rules.open('rb') as f: rule_data=f.read(16*1024*1024+1)
        if len(rule_data)>16*1024*1024: raise Refusal('HELD_ASSEMBLY_RULE_PACK_LIMIT')
        sio.write_bytes(rule_snapshot,rule_data)
        declared,forms,rule_root=read_rules(rule_snapshot)
        reader=LegendReader(snap); reader.verify()
        if reader.header['unit_mode']!='TOKEN': raise Refusal('HELD_ASSEMBLY_SOURCE_REQUIRES_SURFACE_TOKEN')
        parent_root=reader.header['parent_sha256']; correspondence=None
        if parent_root is not None:
            if not source_parents or not target_parents: raise Refusal('HELD_ASSEMBLY_BUILD_DELTA_REQUIRES_EXPLICIT_REBASE')
            from .assembly_chain import verify_rebase
            correspondence=verify_rebase(snap,source_parents,target_parents,max_legend_bytes=max_legend_bytes)
            parent_root=correspondence['target_parent_sha256']
        elif source_parents or target_parents: raise Refusal('HELD_ASSEMBLY_UNUSED_PARENT_CHAINS')
        instance={'schema':'semcrys.assembly-build-instance.v0.1','standing':'CANDIDATE_ONLY',
            'source_legend_sha256':source_root,'rule_pack_sha256':rule_root,'assembly_abi':ABI,
            'selection':'ALL_EXACT_EXPLICIT_MATCHES_NOT_SIZE_OPTIMAL','operation_sequence':OPERATIONS,
            'canonical_csil_identity':False,'security_claim':'NONE'}
        if encoding!='TAGGED' or policy!='ALL':
            instance.update(schema='semcrys.assembly-build-instance.v0.2',encoding=encoding,record_policy=policy,
                assembly_abi=FAMILY_ABI if encoding=='COMPACT' else ABI,selection='EXACT_SERIALIZED_RECORD_POLICY_NOT_WHOLE_DELIVERY_OPTIMUM')
        if correspondence is not None:
            from .assembly_chain import REBASE_OPS
            instance.update(schema='semcrys.assembly-delta-build-instance.v0.1',parent_correspondence=correspondence,
                operation_sequence=REBASE_OPS,encoding=encoding,record_policy=policy)
        instance['instance_constitution_sha256']=hashlib.sha256(canonical(instance)).hexdigest()
        # Only base strings requested by the bounded rule pack are retained.
        wanted={b for b,_ in forms.values()}; bases={}
        for identifier,value in reader.iter_values():
            if value in wanted: bases[value]=identifier
        counts={'literal_entries':0,'reference_forms':0,'inline_base_forms':0,'explicit_replacements':0,'matched_rules':0}
        if policy=='SHORTER': counts['not_shorter_forms']=0
        def encode_program(data): return compact_program(data) if encoding=='COMPACT' else data
        def stored_length(data): return len(_venc(len(data)))+len(data)
        def values():
            for identifier,value in reader.iter_values():
                literal=encode_program(b'\0'+value)
                if value not in forms:
                    if len(value)>MAX_VALUE: raise Refusal('HELD_ASSEMBLY_VALUE_LIMIT')
                    counts['literal_entries']+=1; yield literal; continue
                base,op=forms[value]; rank=bases.get(base); counts['matched_rules']+=1
                compiled=encode_program(program(rank,base,op,value if op=='EXPLICIT_REPLACE' else None))
                if policy=='SHORTER' and stored_length(compiled)>=stored_length(literal):
                    counts['not_shorter_forms']+=1; counts['literal_entries']+=1; yield literal; continue
                counts['reference_forms' if rank is not None else 'inline_base_forms']+=1
                counts['explicit_replacements']+=int(op=='EXPLICIT_REPLACE')
                yield compiled
        pending=work/'assembly.leg'; h=reader.header
        write_legend(pending,values(),entry_count=reader.count,legend_id=h['legend_id'],
            unit_mode=COMPACT_MODE if encoding=='COMPACT' else UNIT_MODE,index_stride=h['index_stride'],parent_sha256=parent_root)
        execution=ExecutionLegendReader(pending); verified=execution.verify()
        for left,right in zip(reader.iter_values(),execution.iter_values(),strict=True):
            if left!=right: raise Refusal('HELD_ASSEMBLY_EXPANSION_CORRESPONDENCE')
        cost={'surface_legend_bytes':snap.stat().st_size,'assembly_legend_bytes':pending.stat().st_size}
        cost['saved_bytes']=cost['surface_legend_bytes']-cost['assembly_legend_bytes']
        result={'status':'PASS','standing':'CANDIDATE_ONLY','schema':'semcrys.assembly-build-result.v0.1',
            'effective_configuration':instance,'source_sha256':source_root,'output_sha256':verified['sha256'],
            'rule_pack_sha256':rule_root,'source_refs':declared['source_refs'],'entry_count':reader.count,
            'counts':counts,'unmatched_rules':len(forms)-counts['matched_rules'],'cost':cost,
            'id_order_and_expansions_preserved':True,'decoder_needs_rule_pack':False,
            'decoder_needs_source_legend':False,'audit_requires_original_sources':True,
            'semantic_claim':'EXACT_DECLARED_SURFACE_TRANSFORMS_NOT_BOUND_SENSE_DISAMBIGUATION'}
        if correspondence is not None:
            result['parent_correspondence']=correspondence
            result['original_surface_parent_sha256']=reader.header['parent_sha256']
            result['output_parent_sha256']=parent_root
            result['expansion_restores_original_parent_automatically']=False
        sio.replace(pending,target)
    return result

def expand(source,output):
    source,target=Path(source),Path(output); protect_outputs([target],[source])
    if target.suffix.lower()!='.leg': raise Refusal('HELD_LEG_SUFFIX_REQUIRED')
    target.parent.mkdir(parents=True,exist_ok=True)
    with sio.TempDirectory(prefix='sa-',dir=target.parent) as directory:
        work=Path(directory); snap=work/'in.leg'; root=_snapshot(source,snap)
        reader=ExecutionLegendReader(snap)
        if not reader.is_assembly: raise Refusal('HELD_NOT_ASSEMBLY_LEGEND')
        reader.verify(); h=reader.header; pending=work/'out.leg'
        result=write_legend(pending,(v for _,v in reader.iter_values()),entry_count=reader.count,
            legend_id=h['legend_id'],unit_mode='TOKEN',parent_sha256=h['parent_sha256'],index_stride=h['index_stride'])
        sio.replace(pending,target)
    return {'status':'PASS','standing':'CANDIDATE_ONLY','source_sha256':root,'output_sha256':result['sha256'],
        'entry_count':reader.count,'canonical_mutation':False}

def inspect(source):
    reader=ExecutionLegendReader(source)
    if not reader.is_assembly: raise Refusal('HELD_NOT_ASSEMBLY_LEGEND')
    return {**reader.verify(),'standing':'CANDIDATE_ONLY','header':reader.header,
        'identity':'LOCAL_EVENT_INDEX_SCOPED_TO_EXACT_LEGEND_ROOT','operators':list(OPERATORS),
        'provenance_status':'BUILD_RECEIPT_SEPARATE_NOT_IMPLICITLY_VERIFIED'}
