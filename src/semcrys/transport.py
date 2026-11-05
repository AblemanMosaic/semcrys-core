"""Transport-independent negotiation and rooted control frames.

No function here opens a socket, transfers a payload, mutates relationship
state, supplies cryptography, or substitutes lineage for exact legend custody.
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from streaming_app.core import Refusal, _validate_configuration
from streaming_legend.core import canonical, file_sha256
from streaming_legend.crys_v2 import inspect_crys

PEER_SCHEMA = "semcrys.transport-peer-capabilities.v0.2"
NEGOTIATION_SCHEMA = "semcrys.transport-negotiation.v0.2"
FRAME_SCHEMA = "semcrys.transport-frame.v0.2"
PATHWAYS = ("EXTERNAL_CHANNEL", "FILE_TRANSFER")
CODECS = ("CRYS_V02",)
PROJECTIONS = ("GLYPH", "INTEGER", "PACKED", "RAW")
PRIMARY_PROFILES = ("A:LONGITUDINAL_TOKEN_DELTA", "C:RAW_BYTES", "C:SELF_CONTAINED_TOKEN", "T:PRESHARED_TOKEN")
MAX_CONTROL_BYTES = 16 * 1024 * 1024
MAX_LEGENDS = 4096
MAX_LINEAGE = 4096
MAX_LOCATIONS = 128
SECURITY_MODES = {
    "NONE": "EXECUTABLE_NO_CONFIDENTIALITY_CLAIM",
    "NATIVE_OPACITY": "EXECUTABLE_ONLY_WITH_NONEMPTY_EXACT_PRESHARED_CHAIN_NO_CONFIDENTIALITY_CLAIM",
    "PUBLIC_ADAPTIVE_PERMUTATION": "HELD_ADAPTIVE_PERMUTATION_NOT_PACKAGED",
    "KEYED_LOCAL_ID_SHUFFLE": "HELD_KEYED_LOCAL_ID_SHUFFLE_ADAPTER",
    "FULL_TRANSPORT_HOMOPHONIC_KEYED_PROJECTION": "HELD_FULL_TRANSPORT_HOMOPHONIC_ADAPTER_NOT_PACKAGED",
    "DELEGATED_AEAD": "HELD_DELEGATED_CRYPTOGRAPHIC_EXECUTION",
    "SEALED_LEGEND": "HELD_DELEGATED_CRYPTOGRAPHIC_EXECUTION",
}


def _root(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _digest(value: dict) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _rooted(value: dict, field: str) -> dict:
    out = dict(value);out[field] = _digest(value);return out


def _clone(value: dict) -> dict:
    return json.loads(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")))


def capabilities() -> dict:
    value = {
        "schema": "semcrys.transport-capability-surface.v0.2", "standing": "CANDIDATE_ONLY",
        "pathways": list(PATHWAYS), "codecs": list(CODECS), "projections": list(PROJECTIONS),
        "security_modes": dict(SECURITY_MODES), "legend_resolution": "EXACT_ORDERED_ROOT_CHAIN_ONLY_FOR_EXECUTION",
        "lineage": "REGISTERED_REFERENCE_METADATA_NEVER_SUBSTITUTES_FOR_HELD_EXACT_ROOT",
        "peer_schema": PEER_SCHEMA, "negotiation_schema": NEGOTIATION_SCHEMA, "frame_schema": FRAME_SCHEMA,
        "max_control_bytes": MAX_CONTROL_BYTES, "network_stack": False,
        "relationship_state_mutation": False, "security_claim": "NONE",
    }
    return _rooted(value, "capability_surface_root")


def _load_json(path: Path) -> dict:
    path = Path(path)
    try:
        size = path.stat().st_size
        if size > MAX_CONTROL_BYTES: raise Refusal("HELD_TRANSPORT_CONTROL_SIZE", str(size))
        value = json.loads(path.read_text(encoding="utf-8"))
    except Refusal: raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal("HELD_TRANSPORT_JSON", str(exc)) from exc
    if not isinstance(value, dict):raise Refusal("HELD_TRANSPORT_SCHEMA", "top level must be an object")
    return value


def validate_peer(value: dict) -> dict:
    expected = {"schema", "standing", "peer_id", "pathways", "codecs", "projections", "legends", "security_modes"}
    if not isinstance(value, dict) or set(value) != expected or value.get("schema") != PEER_SCHEMA or value.get("standing") != "CANDIDATE_ONLY":
        raise Refusal("HELD_TRANSPORT_PEER_SCHEMA")
    if not isinstance(value.get("peer_id"), str) or not 1 <= len(value["peer_id"]) <= 128:
        raise Refusal("HELD_TRANSPORT_PEER_ID")
    for key, allowed in (("pathways", PATHWAYS), ("codecs", CODECS), ("projections", PROJECTIONS)):
        rows=value.get(key)
        if not isinstance(rows,list) or rows!=sorted(set(rows)) or any(row not in allowed for row in rows):
            raise Refusal("HELD_TRANSPORT_PEER_"+key.upper())
    modes=value.get("security_modes")
    if not isinstance(modes,list) or modes!=sorted(set(modes)) or any(mode not in SECURITY_MODES for mode in modes):
        raise Refusal("HELD_TRANSPORT_PEER_SECURITY_MODES")
    legends=value.get("legends")
    if not isinstance(legends,list) or len(legends)>MAX_LEGENDS:
        raise Refusal("HELD_TRANSPORT_PEER_LEGENDS")
    roots=[];legend_keys={"legend_id","sha256","version","custody","supersedes","compatible_with","locations"}
    for row in legends:
        if not isinstance(row,dict) or set(row)!=legend_keys:raise Refusal("HELD_TRANSPORT_LEGEND_SCHEMA")
        if not isinstance(row["legend_id"],str) or not 1<=len(row["legend_id"])<=128:raise Refusal("HELD_TRANSPORT_LEGEND_ID")
        if not _root(row["sha256"]) or row["sha256"] in roots:raise Refusal("HELD_TRANSPORT_LEGEND_ROOT")
        roots.append(row["sha256"])
        if type(row["version"]) is not int or not 1<=row["version"]<=2**31-1:raise Refusal("HELD_TRANSPORT_LEGEND_VERSION")
        if row["custody"] not in ("HELD","REGISTERED_REFERENCE"):raise Refusal("HELD_TRANSPORT_LEGEND_CUSTODY")
        for key in ("supersedes","compatible_with"):
            vals=row[key]
            if (not isinstance(vals,list) or len(vals)>MAX_LINEAGE or vals!=sorted(set(vals)) or
                    any(not _root(v) or v==row["sha256"] for v in vals)):
                raise Refusal("HELD_TRANSPORT_LEGEND_"+key.upper())
        locations=row["locations"]
        if (not isinstance(locations,list) or len(locations)>MAX_LOCATIONS or locations!=sorted(set(locations)) or
                any(not isinstance(v,str) or not v or len(v)>2048 for v in locations)):
            raise Refusal("HELD_TRANSPORT_LEGEND_LOCATIONS")
    if roots!=sorted(roots):raise Refusal("HELD_TRANSPORT_LEGEND_ORDER", "peer inventory must sort by sha256")
    return _clone(value)


def load_peer(path: Path) -> dict:return validate_peer(_load_json(path))


def _legend_index(peer: dict) -> dict[str,dict]:return {row["sha256"]:row for row in peer["legends"]}


def negotiate(local: dict, remote: dict, *, requested_pathway: str | None = None,
              requested_codec: str | None = None, requested_projection: str | None = None,
              requested_legend_roots: list[str] | tuple[str,...] | None = None,
              self_contained: bool = False, requested_security_mode: str = "NONE") -> dict:
    local=validate_peer(local);remote=validate_peer(remote)
    if requested_pathway not in PATHWAYS:raise Refusal("HELD_REQUESTED_PATHWAY_REQUIRED")
    if requested_codec not in CODECS:raise Refusal("HELD_REQUESTED_CODEC_REQUIRED")
    if requested_projection not in PROJECTIONS:raise Refusal("HELD_REQUESTED_PROJECTION_REQUIRED")
    if requested_pathway not in local["pathways"] or requested_pathway not in remote["pathways"]:
        raise Refusal("HELD_NO_SHARED_PATHWAY",requested_pathway)
    if requested_codec not in local["codecs"] or requested_codec not in remote["codecs"]:
        raise Refusal("HELD_NO_SHARED_CODEC",requested_codec)
    if requested_projection not in local["projections"] or requested_projection not in remote["projections"]:
        raise Refusal("HELD_NO_SHARED_PROJECTION",requested_projection)
    if requested_legend_roots is None or type(self_contained) is not bool:
        raise Refusal("HELD_LEGEND_REQUIREMENT_REQUIRED","declare ordered exact roots or self-contained")
    requested=list(requested_legend_roots)
    if self_contained and requested:raise Refusal("HELD_LEGEND_REQUIREMENT_CONFLICT")
    if len(requested)>1023 or len(set(requested))!=len(requested) or any(not _root(root) for root in requested):
        raise Refusal("HELD_REQUESTED_LEGEND_ROOTS")
    if not self_contained and not requested:
        raise Refusal("HELD_LEGEND_REQUIREMENT_REQUIRED","empty external chain requires self-contained")
    if requested_security_mode not in SECURITY_MODES:raise Refusal("HELD_SECURITY_MODE_UNKNOWN")
    disposition=SECURITY_MODES[requested_security_mode]
    if disposition.startswith("HELD_"):raise Refusal(disposition)
    if requested_security_mode not in local["security_modes"] or requested_security_mode not in remote["security_modes"]:
        raise Refusal("HELD_NO_SHARED_SECURITY_MODE",requested_security_mode)
    if requested_security_mode=="NATIVE_OPACITY" and (self_contained or not requested):
        raise Refusal("HELD_NATIVE_OPACITY_REQUIRES_PRESHARED_LEGEND")
    li,ri=_legend_index(local),_legend_index(remote)
    missing=[]
    for root in requested:
        if root not in li or root not in ri or li[root]["custody"]!="HELD" or ri[root]["custody"]!="HELD":missing.append(root)
    if missing:
        target=missing[0];holders=[]
        for peer,index in ((local,li),(remote,ri)):
            if target in index and index[target]["custody"]=="HELD":holders.append({"peer":peer["peer_id"],"locations":index[target]["locations"]})
        registry=[]
        for peer,index in ((local,li),(remote,ri)):
            if target in index:registry.append({"peer":peer["peer_id"],"custody":index[target]["custody"],"locations":index[target]["locations"]})
        related=[]
        for peer in (local,remote):
            for row in peer["legends"]:
                if target in row["supersedes"] or target in row["compatible_with"]:
                    related.append({"peer":peer["peer_id"],"sha256":row["sha256"],"version":row["version"],
                                    "custody":row["custody"],"declares_compatible":target in row["compatible_with"]})
        detail={"requested_legend_root":target,"exact_root_holders":holders,"registry_records":registry,
                "related_lineage":sorted(related,key=lambda x:(x["peer"],x["sha256"])),
                "repair":"ACQUIRE_EXACT_ROOT; lineage or registry knowledge never substitutes for HELD custody"}
        raise Refusal("HELD_NO_SHARED_LEGEND",json.dumps(detail,sort_keys=True,separators=(",",":")))
    for root in requested:
        if li[root]["version"]!=ri[root]["version"]:raise Refusal("HELD_LEGEND_VERSION_METADATA_MISMATCH",root)
    value={
      "schema":NEGOTIATION_SCHEMA,"standing":"CANDIDATE_ONLY",
      "local_peer_id":local["peer_id"],"local_capabilities_sha256":_digest(local),
      "remote_peer_id":remote["peer_id"],"remote_capabilities_sha256":_digest(remote),
      "pathway":requested_pathway,"codec":requested_codec,"projection":requested_projection,
      "legend_requirement":"SELF_CONTAINED" if self_contained else "EXACT_EXTERNAL_CHAIN","legend_roots":requested,
      "legend_versions":[{"sha256":root,"version":li[root]["version"]} for root in requested],
      "security_mode":requested_security_mode,"security_claim":"NONE","network_transfer_executed":False,
      "relationship_state_mutation":False,"selection_rule":"CALLER_EXPLICIT_VALUES_VALIDATED_AGAINST_BOTH_ROOTED_CAPABILITY_RECORDS"}
    return _rooted(value,"negotiation_root")


def validate_negotiation(value: dict) -> dict:
    expected={"schema","standing","local_peer_id","local_capabilities_sha256","remote_peer_id","remote_capabilities_sha256",
      "pathway","codec","projection","legend_requirement","legend_roots","legend_versions","security_mode","security_claim",
      "network_transfer_executed","relationship_state_mutation","selection_rule","negotiation_root"}
    if not isinstance(value,dict) or set(value)!=expected or value.get("schema")!=NEGOTIATION_SCHEMA or value.get("standing")!="CANDIDATE_ONLY":
        raise Refusal("HELD_TRANSPORT_NEGOTIATION_SCHEMA")
    root=value["negotiation_root"];base=dict(value);base.pop("negotiation_root")
    if not _root(root) or _digest(base)!=root:raise Refusal("HELD_TRANSPORT_NEGOTIATION_ROOT")
    roots=value["legend_roots"]
    if (not all(isinstance(value[k],str) and 1<=len(value[k])<=128 for k in ("local_peer_id","remote_peer_id")) or
        not _root(value["local_capabilities_sha256"]) or not _root(value["remote_capabilities_sha256"]) or
        value["pathway"] not in PATHWAYS or value["codec"] not in CODECS or value["projection"] not in PROJECTIONS or
        value["legend_requirement"] not in ("SELF_CONTAINED","EXACT_EXTERNAL_CHAIN") or not isinstance(roots,list) or
        len(roots)>1023 or len(set(roots))!=len(roots) or any(not _root(v) for v in roots) or
        value["security_mode"] not in ("NONE","NATIVE_OPACITY") or value["security_claim"]!="NONE" or
        value["network_transfer_executed"] is not False or value["relationship_state_mutation"] is not False or
        value["selection_rule"]!="CALLER_EXPLICIT_VALUES_VALIDATED_AGAINST_BOTH_ROOTED_CAPABILITY_RECORDS"):
        raise Refusal("HELD_TRANSPORT_NEGOTIATION_VALUES")
    if (value["legend_requirement"]=="SELF_CONTAINED")!=(roots==[]):raise Refusal("HELD_TRANSPORT_NEGOTIATION_LEGEND_REQUIREMENT")
    if value["security_mode"]=="NATIVE_OPACITY" and not roots:raise Refusal("HELD_NATIVE_OPACITY_REQUIRES_PRESHARED_LEGEND")
    versions=value["legend_versions"]
    if (not isinstance(versions,list) or len(versions)!=len(roots) or
        any(not isinstance(row,dict) or set(row)!={"sha256","version"} or row["sha256"]!=roots[i] or
            type(row["version"]) is not int or not 1<=row["version"]<=2**31-1 for i,row in enumerate(versions))):
        raise Refusal("HELD_TRANSPORT_NEGOTIATION_VERSIONS")
    return _clone(value)


def _body_projection(config: dict) -> str:
    return "RAW" if config.get("profile")=="C:RAW_BYTES" else config.get("projection","PACKED")


def compile_frame(body: Path, negotiation: dict) -> dict:
    negotiation=validate_negotiation(negotiation);path=Path(body);inspection=inspect_crys(path);config=inspection["configuration"]
    _validate_configuration(config,inspection["header"])
    profile=config.get("profile")
    if profile not in PRIMARY_PROFILES:raise Refusal("HELD_TRANSPORT_BODY_PROFILE",str(profile))
    body_roots=config.get("external_legend_roots",[])
    if body_roots!=negotiation["legend_roots"]:raise Refusal("HELD_TRANSPORT_BODY_LEGEND_CHAIN")
    projection=_body_projection(config)
    if projection!=negotiation["projection"]:raise Refusal("HELD_TRANSPORT_BODY_PROJECTION")
    if (negotiation["legend_requirement"]=="SELF_CONTAINED")!=(body_roots==[]):raise Refusal("HELD_TRANSPORT_BODY_LEGEND_REQUIREMENT")
    ic_root=config.get("instance_constitution_sha256")
    if not _root(ic_root):raise Refusal("HELD_TRANSPORT_BODY_INSTANCE_CONSTITUTION")
    value={
      "schema":FRAME_SCHEMA,"standing":"CANDIDATE_ONLY","body_sha256":file_sha256(path),"body_bytes":path.stat().st_size,
      "body_profile":profile,"body_instance_constitution_sha256":ic_root,"negotiation_root":negotiation["negotiation_root"],
      "local_capabilities_sha256":negotiation["local_capabilities_sha256"],"remote_capabilities_sha256":negotiation["remote_capabilities_sha256"],
      "legend_requirement":negotiation["legend_requirement"],"legend_roots":negotiation["legend_roots"],
      "codec":negotiation["codec"],"projection":negotiation["projection"],"pathway":negotiation["pathway"],
      "security_mode":negotiation["security_mode"],"security_claim":"NONE","body_embedded":False,"network_transfer_executed":False}
    return _rooted(value,"frame_root")


def validate_frame(value: dict) -> dict:
    expected={"schema","standing","body_sha256","body_bytes","body_profile","body_instance_constitution_sha256","negotiation_root",
      "local_capabilities_sha256","remote_capabilities_sha256","legend_requirement","legend_roots","codec","projection","pathway",
      "security_mode","security_claim","body_embedded","network_transfer_executed","frame_root"}
    if not isinstance(value,dict) or set(value)!=expected or value.get("schema")!=FRAME_SCHEMA or value.get("standing")!="CANDIDATE_ONLY":
        raise Refusal("HELD_TRANSPORT_FRAME_SCHEMA")
    root=value["frame_root"];base=dict(value);base.pop("frame_root")
    if not _root(root) or _digest(base)!=root:raise Refusal("HELD_TRANSPORT_FRAME_ROOT")
    roots=value["legend_roots"]
    if (type(value["body_bytes"]) is not int or value["body_bytes"]<0 or not _root(value["body_sha256"]) or
        value["body_profile"] not in PRIMARY_PROFILES or not _root(value["body_instance_constitution_sha256"]) or
        not _root(value["negotiation_root"]) or not _root(value["local_capabilities_sha256"]) or not _root(value["remote_capabilities_sha256"]) or
        value["legend_requirement"] not in ("SELF_CONTAINED","EXACT_EXTERNAL_CHAIN") or not isinstance(roots,list) or
        len(roots)>1023 or len(set(roots))!=len(roots) or any(not _root(v) for v in roots) or
        value["codec"] not in CODECS or value["projection"] not in PROJECTIONS or value["pathway"] not in PATHWAYS or
        value["security_mode"] not in ("NONE","NATIVE_OPACITY") or value["security_claim"]!="NONE" or
        value["body_embedded"] is not False or value["network_transfer_executed"] is not False):
        raise Refusal("HELD_TRANSPORT_FRAME_VALUES")
    if (value["legend_requirement"]=="SELF_CONTAINED")!=(roots==[]):raise Refusal("HELD_TRANSPORT_FRAME_LEGEND_REQUIREMENT")
    if value["security_mode"]=="NATIVE_OPACITY" and not roots:raise Refusal("HELD_NATIVE_OPACITY_REQUIRES_PRESHARED_LEGEND")
    return _clone(value)


def verify_frame(frame: dict, body: Path, negotiation: dict) -> dict:
    frame=validate_frame(frame);negotiation=validate_negotiation(negotiation)
    if frame["negotiation_root"]!=negotiation["negotiation_root"]:raise Refusal("HELD_TRANSPORT_FRAME_NEGOTIATION_ROOT")
    fields=("local_capabilities_sha256","remote_capabilities_sha256","legend_requirement","legend_roots","codec","projection","pathway","security_mode")
    if any(frame[key]!=negotiation[key] for key in fields):raise Refusal("HELD_TRANSPORT_FRAME_NEGOTIATION_MISMATCH")
    path=Path(body)
    if path.stat().st_size!=frame["body_bytes"] or file_sha256(path)!=frame["body_sha256"]:raise Refusal("HELD_TRANSPORT_BODY_DIGEST")
    inspection=inspect_crys(path);config=inspection["configuration"]
    _validate_configuration(config,inspection["header"])
    if config.get("profile")!=frame["body_profile"]:raise Refusal("HELD_TRANSPORT_BODY_PROFILE")
    if config.get("instance_constitution_sha256")!=frame["body_instance_constitution_sha256"]:
        raise Refusal("HELD_TRANSPORT_BODY_INSTANCE_CONSTITUTION")
    if config.get("external_legend_roots",[])!=frame["legend_roots"]:raise Refusal("HELD_TRANSPORT_BODY_LEGEND_CHAIN")
    if _body_projection(config)!=frame["projection"]:raise Refusal("HELD_TRANSPORT_BODY_PROJECTION")
    return {"schema":"semcrys.transport-frame-verification.v0.2","standing":"CANDIDATE_ONLY","frame_root":frame["frame_root"],
      "negotiation_root":negotiation["negotiation_root"],"body_sha256":frame["body_sha256"],"verified":True,
      "network_transfer_executed":False,"security_claim":"NONE"}


def load_frame(path: Path) -> dict:return _load_json(path)
