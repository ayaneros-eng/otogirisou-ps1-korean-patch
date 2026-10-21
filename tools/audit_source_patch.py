"""Inspect actual patch operations and compare both independent outputs."""
from __future__ import annotations
import argparse,base64,collections,hashlib,json,mmap
from pathlib import Path
from apply_source_patch import load,sha
from build_source_patch import FILES,extents,gather,SOURCE_SHA,TARGET_SHA

def audit(source,patch,cs_output,py_output,report):
    d=load(patch);counts=collections.Counter();literal_chunks=[];literal_totals=collections.Counter()
    matches=[];image_overlap=0;video_overlap=0
    with source.open('rb') as sf:
        original=mmap.mmap(sf.fileno(),0,access=mmap.ACCESS_READ)
        code=gather(original,extents(FILES['SLPS_016.45'][0],0,FILES['SLPS_016.45'][1]))
        code_keys={code[i:i+16] for i in range(len(code)-15)}
        image_ranges=collections.defaultdict(list);video_ranges=collections.defaultdict(list)
        for m in d['mdec']:
            remaining=m['stream_length'];ranges=image_ranges if m['label'].startswith('image/') else video_ranges
            for p,n in m['extents']:
                take=min(n,remaining)
                if take:ranges[p//2352].append((p,p+take));remaining-=take
        for w in d['writes']:
            pos=w['offset'];data=base64.b64decode(w['data']);literal_chunks.append(data)
            counts['literal_bytes']+=len(data)
            counts['same_position_original_literal_bytes']+=sum(a==b for a,b in zip(data,original[pos:pos+len(data)]))
            for name,(lba,size) in FILES.items():
                if lba<=pos//2352<lba+(size+2047)//2048:literal_totals[name]+=len(data)
            image_overlap+=sum(max(0,min(pos+len(data),b)-max(pos,a)) for a,b in image_ranges[pos//2352])
            video_overlap+=sum(max(0,min(pos+len(data),b)-max(pos,a)) for a,b in video_ranges[pos//2352])
            for i in range(len(data)-15):
                if data[i:i+16] in code_keys:matches.append({'destination':pos+i,'length':16})
        counts['original_executable_16byte_matches_in_literals']=len(matches)
        # Look for long unchanged CDIMG spans at any address, not just the
        # target address. Short generic numeric coincidences are not classified
        # as copyrightable original content by this technical inspection.
        keys={b[i:i+32] for b in literal_chunks for i in range(len(b)-31)}
        cdimg=gather(original,extents(FILES['CDIMG.BIN'][0],0,FILES['CDIMG.BIN'][1]));cd_matches=[]
        for i in range(len(cdimg)-31):
            if cdimg[i:i+32] in keys:cd_matches.append(i)
        counts['original_CDIMG_32byte_window_matches_in_literals']=len(cd_matches)
        counts['literal_bytes_in_complete_BS_image_streams']=image_overlap
        counts['literal_bytes_in_video_BS_streams']=video_overlap
        counts['source_copy_bytes']=sum(c[2] for c in d['copies'])
        counts['fill_bytes']=sum(f[1] for f in d['fills'])
        counts['source_relative_MDEC_streams']=len(d['mdec'])
        counts['source_relative_video_frames']=sum(not m['label'].startswith('image/') for m in d['mdec'])
        counts['source_relative_BS_images']=sum(m['label'].startswith('image/') for m in d['mdec'])
        original.close()
    outputs=[{'implementation':name,'size':p.stat().st_size,'sha256':sha(p)} for name,p in [('windows-csharp',cs_output),('independent-python',py_output)]]
    original_hash=sha(source)
    checks={'source_preserved':original_hash==SOURCE_SHA,'both_outputs_equal_R152':all(x['sha256']==TARGET_SHA for x in outputs),
            'no_same_position_original_literals':counts['same_position_original_literal_bytes']==0,
            'no_original_code_16byte_literals':not matches,'no_CDIMG_32byte_literals':not cd_matches,
            'no_completed_media_literals':image_overlap==video_overlap==0,
            'all_275_frames_source_relative':counts['source_relative_video_frames']==275}
    result={'result':'PASS' if all(checks.values()) else 'REVIEW_REQUIRED','checks':checks,'counts':dict(counts),
            'literal_bytes_by_source_file':dict(literal_totals),'outputs':outputs,
            'patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),
            'original_code_match_examples':matches[:20],'original_CDIMG_match_offsets':cd_matches[:30],
            'scope':'Decoded literal operands, source references, source-relative quantized-coefficient edits. Small byte coincidences and derivative-work rights are not a zero-copyright guarantee.'}
    report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','patch','cs-output','py-output','report']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();audit(a.source,a.patch,a.cs_output,a.py_output,a.report)
