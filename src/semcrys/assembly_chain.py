"""Exact ordered parent-chain correspondence. No implicit reparenting."""
from streaming_app.core import Refusal
from streaming_app.legend_context import VerifiedLegendContext
from streaming_legend.assembly import MODES

MAX_PARENTS=1023
MAX_LEGEND_BYTES=1024*1024*1024
REBASE_OPS=['SNAPSHOT_INPUTS','VERIFY_SOURCE_AND_TARGET_CHAINS','PROVE_ORDERED_PARENT_EQUIVALENCE',
 'FACTOR_DELTA','VERIFY_EXPANSION_AND_NEW_PARENT_BINDING','PUBLISH_NEW_ARTIFACT']

def verify_chain(paths,context):
    if not 1<=len(paths)<=MAX_PARENTS: raise Refusal('HELD_ASSEMBLY_PARENT_CHAIN_COUNT')
    rows=[]; previous=None
    for path in paths:
        row=context.prepare(path); h=row['reader'].header
        if h['unit_mode'] not in ('TOKEN',*MODES): raise Refusal('HELD_ASSEMBLY_PARENT_UNIT_MODE')
        if h['parent_sha256']!=previous: raise Refusal('HELD_ASSEMBLY_PARENT_CHAIN_BINDING')
        rows.append(row); previous=row['sha256']
    context.stack(paths)
    return rows

def verify_rebase(source,source_parents,target_parents,*,max_legend_bytes=MAX_LEGEND_BYTES):
    if type(max_legend_bytes) is not int or not 0<=max_legend_bytes<=MAX_LEGEND_BYTES:
        raise Refusal('HELD_ASSEMBLY_LEGEND_BUDGET')
    if len(source_parents)!=len(target_parents) or not source_parents:
        raise Refusal('HELD_ASSEMBLY_PARENT_CHAIN_CORRESPONDENCE')
    if len(source_parents)>MAX_PARENTS: raise Refusal('HELD_ASSEMBLY_PARENT_CHAIN_COUNT')
    with VerifiedLegendContext(max_legend_bytes=max_legend_bytes,max_legends=4096) as context:
        with context.operation():
            left=verify_chain(source_parents,context); right=verify_chain(target_parents,context)
            delta=context.prepare(source)
            if delta['reader'].header['parent_sha256']!=left[-1]['sha256']:
                raise Refusal('HELD_ASSEMBLY_SOURCE_DELTA_PARENT')
            context.stack([*source_parents,source])
            pairs=[]
            for a,b in zip(left,right,strict=True):
                if a['entries']!=b['entries']: raise Refusal('HELD_ASSEMBLY_PARENT_VALUE_CORRESPONDENCE')
                if a['sha256']!=b['sha256']:
                    for x,y in zip(a['reader'].iter_values(),b['reader'].iter_values(),strict=True):
                        if x!=y: raise Refusal('HELD_ASSEMBLY_PARENT_VALUE_CORRESPONDENCE')
                pairs.append({'source_sha256':a['sha256'],'target_sha256':b['sha256'],'entry_count':a['entries']})
            return {'schema':'semcrys.exact-parent-chain-correspondence.v0.1','standing':'CANDIDATE_ONLY',
             'source_parent_roots':[a['sha256'] for a in left],'target_parent_roots':[a['sha256'] for a in right],
             'member_correspondence':pairs,'ordered_values_identical':True,
             'target_parent_sha256':right[-1]['sha256'],'max_legend_bytes':max_legend_bytes,
             'source_delta_sha256':delta['sha256'],'authority_effect':'NONE'}

