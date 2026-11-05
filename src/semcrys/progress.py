"""Presentation only: full event receipts remain in operation results."""
import json
import sys

def emit(event, mode='full'):
    if mode == 'quiet': return
    if mode == 'human':
        stage=str(event.get('stage') or event.get('operation') or event.get('status') or 'WORKING').replace('_',' ').title()
        counts=[]
        for done,total,label in (('files','total_files','files'),('chunks','total_chunks','chunks'),
                                 ('segment','total_segments','segments')):
            if done in event:
                value=event[done]
                if total in event: value=f"{value}/{event[total]}"
                counts.append(f"{label} {value}")
        if 'path' in event: counts.append(str(event['path']))
        if 'kind' in event: counts.append(str(event['kind']).lower().replace('_',' '))
        if 'composition_selected' in event:
            counts.append('composition selected' if event['composition_selected'] else 'control selected')
        if 'potential_savings_upper_bound_bytes' in event:
            counts.append(f"composition upper bound {event['potential_savings_upper_bound_bytes']} bytes")
        if event.get('cache_hit'): counts.append('verified cache hit')
        if 'reason' in event and event['reason']: counts.append(str(event['reason']).lower().replace('_',' '))
        print(stage+(' | '+' | '.join(counts) if counts else ''),file=sys.stderr,flush=True)
        return
    if mode == 'full':
        print(json.dumps(event,ensure_ascii=True,sort_keys=True),file=sys.stderr,flush=True)
        return
    if mode != 'summary': raise ValueError('HELD_PROGRESS_MODE')
    summary={k:event[k] for k in ('stage','operation','status','code') if k in event}
    config=event.get('effective_configuration',{})
    if 'instance_constitution_sha256' in config:
        summary['instance_constitution_sha256']=config['instance_constitution_sha256']
    print(json.dumps(summary,ensure_ascii=True,sort_keys=True),file=sys.stderr,flush=True)
